# Phase 12: Eval Scoring & Scrub Tuning - Context

**Gathered:** 2026-06-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 12 makes a logged `ExperimentRecord` **assessable and shareable-safe**, the
"divergent tail" counterparts to the community scorer/scrubber:

1. **Eval-specific scorer (EEVAL-01):** assigns a quality result to an
   `ExperimentRecord` using signals appropriate to model-output evaluation —
   *not* coding-trajectory coherence. It is a **trust/completeness lens**, not a
   re-judgment of the model's answer (the caller/reviewer-set `eval_score` from
   Phase 10 remains the answer-quality signal).
2. **Experiment-aware scrub (EEVAL-02):** redacts PII from an experiment's
   free-text fields while **preserving** the model-identity and hardware fields
   that make an experiment analytically useful.

**Out of scope (later phases):**
- Quality-**drift** detection and reviewer-**critique** attachment / `lessons_learned`
  querying → **Phase 13**. (The scorer may *read* `drift_flag`/`reviewer_critique`
  if present, but does not compute or require them.)
- The analysis-**export** format and practice-project integration (where
  scrub-on-export actually fires) → **Phase 15**.
- Live capture → Phase 14.

</domain>

<decisions>
## Implementation Decisions

### Eval Scorer — what it measures (EEVAL-01)
- **D-01:** The scorer is a **completeness/confidence** assessment of the eval
  *record*, not a re-judgment of the model output. It scores how complete and
  trustworthy the eval is — e.g. local_model_output present, reviewer critique
  attached, `lessons_learned` captured, model + hardware metadata present,
  `eval_score` within range. Signals are eval-appropriate; the existing
  `eval_score` (Phase 10) stays the answer-quality judgment and stands *beside*
  the confidence result.
- **D-04:** The score is **advisory / analysis-only**. Experiments never publish,
  so it never gates anything — it is a filtering/triage signal for the user and
  for Phase 15 analysis.

### Eval Scorer — result shape & timing (EEVAL-01)
- **D-02:** Result is a **`QualityResult`-like dataclass**: a confidence
  composite (`0.0–1.0`) + **eval-native bands** (e.g. `complete / partial / thin`,
  or high/med/low confidence) + a per-check breakdown. **Distinct vocabulary
  from the coding scorer's `gold/silver/bronze`** — those signal *training-data
  value* and must never be confused with eval trustworthiness.
- **D-03:** **Compute-on-read** via a new `kajiba experiment score` subcommand,
  and surface the result in `kajiba experiment list`. The score is **NOT
  persisted** into the record → **no change to the Phase-10-frozen
  `ExperimentRecord`/`ExperimentOutcome` schema**. Re-scorable as the scorer
  evolves; Phase 11's `log_experiment` stays a pure write path (preserves D-08
  single-write-path).

### Experiment Scrub — preserve vs redact (EEVAL-02)
- **D-05:** **Preserve model identity + hardware EXACT.** Experiments **bypass
  `privacy.py`'s hardware anonymization** (`generalize_gpu_name`, `round_to_tier`
  VRAM, OS strip, cuda strip) entirely. Keep `model_name`, `model_family`,
  `parameter_count`, `quantization`, `provider`, `model_hash`, and all
  `HardwareProfile` fields intact — for both `RecordBase.model` and
  `experiment.local_model`/`reviewer_model`. This is the deliberate inverse of
  the community pipeline.
- **D-06:** **`model_hash` must be explicitly protected.** It is hex and the
  scrubber's `hex_tokens` pattern would otherwise redact it. The experiment
  scrub must operate on a **field allowlist/denylist**, not blindly walk every
  string.
- **D-07:** **Scrub ALL caller-supplied free text** through the existing
  `scrub_text` regex engine (shared core): `local_model_output`,
  `reviewer_critique`, `task_description`, and `lessons_learned`. Max-scrub
  default per CLAUDE.md's over-redact stance.

### Experiment Scrub — timing (EEVAL-02)
- **D-08:** **Store raw, scrub at the export/share boundary** (Phase 15) or via
  an explicit `kajiba experiment scrub` command — **NOT at log time**. This
  preserves the real model output for the Phase 13 reviewer + drift detection,
  and the private store makes raw-at-rest acceptable. Closes Phase 11's
  accepted-risk **AR-11-01** at the *share* boundary rather than the log.

### Architecture / placement
- **D-09:** New single-responsibility module(s) per the locked **"shared core,
  divergent tail"** stance + the one-module-per-responsibility convention
  (mirrors Phase 11's `experiment_store.py`). Leaning: a new eval-scorer module
  for the scorer; experiment-aware scrub as a new function/module that **reuses
  `scrub_text`/`SCRUB_PATTERNS`** (do **not** fork the regex engine).
- **D-10:** **Reuse, don't rewrite.** The scrub regex engine, the `ScrubLog`
  accounting model, and the `QualityResult` dataclass *shape* are reused; only
  the orchestration (which fields, which record_kind) diverges.

### Claude's Discretion
Left to researcher/planner — capture the cleanest approach, don't re-ask:
- Exact module/file names, and whether experiment scrub lives in `scrubber.py`
  via `record_kind` dispatch vs a new `experiment_scrub`-style module (D-09).
- The exact set of completeness sub-checks and their weights in the confidence
  composite (D-01/D-02).
- Exact band labels/thresholds (`complete/partial/thin` vs high/med/low) — pick
  the clearest; just keep them distinct from gold/silver/bronze.
- Whether `experiment score` renders a Rich per-check breakdown table and whether
  `list` gains a confidence column.
- Whether the scrub emits a `ScrubLog` (consistent with the existing scrubber)
  recording what was redacted; lean yes.
- Whether the two new public functions are re-exported from `kajiba/__init__.py`
  (lean yes if the Phase 15 practice project needs them programmatically).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Requirements
- `.planning/REQUIREMENTS.md` — **EEVAL-01, EEVAL-02** (the two locked
  requirements this phase satisfies).

### Schema Foundation (Phase 10 — FROZEN, do not add fields)
- `src/kajiba/schema.py` — `ExperimentRecord` / `ExperimentMetadata` /
  `ExperimentOutcome` (fields the scorer reads and scrub touches),
  `ModelMetadata` / `HardwareProfile` (the **preserve-list** source),
  `RecordBase` (`record_kind`, `model`, `hardware`, `consent_level`),
  `load_record()`, `EXPERIMENT_TYPES` / `RECOMMENDED_ACTIONS`. Phase 12 is
  **compute-on-read** (D-03) — must NOT mutate this schema.
- `.planning/phases/10-experiment-schema-foundation/10-SPEC.md` and
  `.planning/phases/10-experiment-schema-foundation/10-CONTEXT.md` — locked
  schema rules/rationale.

### Patterns to MIRROR or REUSE (shared core)
- `src/kajiba/scorer.py` — coding-trajectory scorer: the `QualityResult`
  dataclass shape, `WEIGHTS`/threshold idiom, `compute_quality_score()`
  structure. **Mirror the structure; do NOT reuse the 5 coding sub-scores** —
  they assume `trajectory.conversations`/`tool_calls` and coding coherence.
- `src/kajiba/scrubber.py` — `scrub_text()`, `SCRUB_PATTERNS`,
  `_scrub_string_fields_in_turn()`, `scrub_record()` (the
  `model_dump → scrub → re-validate` pattern), `ScrubLog`. **Reuse the
  `scrub_text` engine**; build experiment-aware orchestration with a preserve
  allowlist on top (D-06/D-07/D-10).
- `src/kajiba/privacy.py` — `anonymize_hardware()`, `generalize_gpu_name()`,
  `round_to_tier()`, `apply_consent_level()`. **This is exactly what experiments
  must SKIP (D-05)** — it would destroy the analysis fields EEVAL-02 preserves.

### Phase 11 Integration Points
- `src/kajiba/experiment_store.py` — `log_experiment` (pure write path; scoring
  and scrub do **not** hook in here per D-03/D-08), `EXPERIMENTS_DIR`,
  `build_experiment_record`.
- `src/kajiba/cli.py` — the `experiment` Click group + `log`/`list` (Phase 11);
  add `score` and `scrub` subcommands here and enrich `list`.
- `src/kajiba/__init__.py` — package export surface (Phase 11 re-exports the two
  store functions; extend if new public funcs are needed by external callers).
- `.planning/phases/11-experiment-logging-private-store/11-CONTEXT.md` (D-01..D-14)
  and `.planning/phases/11-experiment-logging-private-store/11-SECURITY.md`
  (**AR-11-01** raw-PII-at-rest accepted risk this phase addresses at export).

### Design Source & Rationale
- `docs/dual-use-roadmap.md` — dual-use direction; "shared core / divergent tail".
- `.planning/seeds/v1.2-experiment-logging.md` — converged dual-use decisions
  (private/no-publish, divergent scorer/scrub/export).
- `.planning/notes/dual-use-direction-decisions.md` — v1.2 decision log.
- `docs/kajiba-project-spec.md` — full pipeline/scrub/score design + controlled
  vocabularies.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`scrub_text` + `SCRUB_PATTERNS`** (`scrubber.py`): the regex PII engine to
  reuse on selected experiment free-text fields (D-07/D-10).
- **`QualityResult` dataclass + `compute_quality_score` structure**
  (`scorer.py`): the structural template for the eval scorer's result (D-02).
- **`ScrubLog`** (`schema.py`): redaction-accounting model to reuse for the
  experiment scrub.
- **`experiment` group + `list`** (`cli.py`, Phase 11): where `score`/`scrub`
  subcommands attach.

### Established Patterns
- One module per responsibility; new modules for the divergent tail
  (`experiment_store.py` precedent).
- Records serialized via `model_dump(mode="json", by_alias=True)`; loaded via
  `load_record`/`model_validate`.
- **Compute-on-read for derived signals** (no schema mutation) — keeps the
  Phase-10 schema frozen (D-03).
- `Optional[X]` typing, double quotes, Google-style docstrings, module-level
  `logger`, `UPPER_SNAKE_CASE` constants.

### Integration Points
- **Score path:** `kajiba experiment score <id|--from>` → load record → eval
  scorer → confidence composite + eval-native bands (Rich breakdown); surface in
  `experiment list`.
- **Scrub path:** `kajiba experiment scrub` / Phase 15 export → load record →
  experiment-aware scrub (`scrub_text` on a free-text allowlist, preserve
  model + hardware) → `ScrubLog`.
- **Privacy boundary:** experiments explicitly **SKIP** `privacy.anonymize_hardware`.

</code_context>

<specifics>
## Specific Ideas

- The eval scorer is a **trust/completeness lens**, not a quality re-judgment —
  `eval_score` stays the answer-quality signal; the scorer answers "is this eval
  record complete and reliable enough to analyze?"
- **Distinct band vocabulary** from gold/silver/bronze so eval trustworthiness is
  never mistaken for training-data tier.
- **Raw model output is deliberately preserved at rest** (private store) so the
  Phase 13 reviewer sees what the model actually produced; scrub is a
  share-boundary transform, not a log-time one.
- **`model_hash` and hardware are first-class analysis fields here** — the exact
  inverse of the community pipeline that anonymizes them.

</specifics>

<deferred>
## Deferred Ideas

- **Quality-drift detection** across repeated runs of the same model+task →
  **Phase 13**. The scorer reads `drift_flag` if present but does not compute it.
- **Reviewer critique attachment** + **`lessons_learned` querying** → **Phase 13**.
- **Analysis-export format** + practice-project integration (where scrub-on-export
  actually fires) → **Phase 15**.
- **Persisting the computed eval score** into the schema → out of scope
  (compute-on-read chosen, D-03); revisit only if a stored score becomes necessary.

### Reviewed Todos (not folded)
- `2026-06-04-fix-experiment-relog-dedup-cr01.md` (CR-01 + Phase 11 review
  warnings) — considered, **not folded**: it is experiment-*store* dedup
  correctness, not scoring/scrubbing. Remains tracked in `.planning/todos/pending/`
  for a patch or a later phase.

</deferred>

---

*Phase: 12-eval-scoring-scrub-tuning*
*Context gathered: 2026-06-04*
