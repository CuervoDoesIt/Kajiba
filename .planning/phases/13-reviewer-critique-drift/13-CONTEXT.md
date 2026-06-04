# Phase 13: Reviewer Critique & Drift - Context

**Gathered:** 2026-06-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 13 makes a logged `ExperimentRecord` **reviewable and drift-aware** — the
human/model feedback and longitudinal-quality layer of the dual-use eval-logging
milestone. It adds three CLI capabilities on top of the Phase 11 store and the
Phase 10 frozen schema, all writing through a single new update path:

1. **Reviewer critique attachment (EREV-01):** a reviewer (human or a model such
   as Grok) attaches a free-text critique — plus optional reviewer identity and a
   verdict — to an existing experiment record via `kajiba experiment review <id>`.
2. **Queryable lessons (EREV-02):** `lessons_learned` can be recorded in a
   queryable form (category-tagged strings) and read back per-record and across
   the store via `kajiba experiment lessons`.
3. **Quality-drift detection (EREV-03):** `kajiba experiment drift` computes
   eval-score drift across repeated runs of the same model+task and persists a
   `drift_flag` on affected records.

**Out of scope (later phases):**
- Analysis-**export** format + practice-project integration → **Phase 15**.
- **Live capture** of eval runs from Hermes sessions → **Phase 14**.
- Any change to the Phase-10-frozen `ExperimentRecord`/`ExperimentMetadata`/
  `ExperimentOutcome` schema — this phase only writes into existing fields.

</domain>

<decisions>
## Implementation Decisions

### Persistence model (cross-cutting — all 3 commands)
- **D-01: Mutate `exp_<id>.json` in place.** Reviewer-authored fields (critique,
  reviewer_model, recommended_action, lessons_learned) and `drift_flag` are
  written back into the existing record file. This is **safe** because
  `ExperimentRecord.compute_record_id()` / `compute_submission_hash()`
  (`schema.py:445-492`) hash only experiment **identity**
  (experiment_id, task_description, local_model.model_name, local_model_output,
  started_at) and **exclude all `outcome` fields** — so the filename/ID stay
  stable across re-writes. No sidecar files.
- **D-02: `drift_flag` is persisted** on the record (not compute-on-read). The
  `drift` command computes, then writes. (Contrast with Phase 12's eval score,
  which stays compute-on-read — drift is a longitudinal verdict worth freezing on
  the record.)
- **D-03: One `update_experiment()` write path** in `experiment_store.py`. All
  three commands (review, lessons, drift) funnel through it. It performs an
  **in-place overwrite when identity matches** (load → mutate outcome/metadata →
  re-validate → atomic replace of the same `exp_<id>.json`).
  **This closes CR-01** (the `log_experiment` dedup-skip data-loss bug — see
  Folded Todos) by giving outcome-mutating writes a path that intentionally
  overwrites rather than early-returning on `dest.exists()`.

### Critique & reviewer ID (EREV-01)
- **D-04: Critique input = file + interactive + inline.** `kajiba experiment
  review <id>` accepts `--from FILE` (paste a model's reply — e.g. Grok — into a
  file), a Rich **interactive paste** prompt when no flag is given, and
  `--critique "..."` inline for short notes. Core stays offline — the critique is
  *brought in*, never pulled from a live API.
- **D-05: Reviewer identity via optional `--reviewer-model NAME`.** Builds
  `ModelMetadata(model_name=NAME)` into `experiment.reviewer_model` for model
  reviewers; **omitting it = human reviewer**, `reviewer_model` stays `None`.
- **D-06: `review` also captures the verdict** via an optional `--action` flag →
  `outcome.recommended_action` (one of the frozen `RECOMMENDED_ACTIONS`:
  `use_as_is` / `needs_fine_tune` / `route_to_reviewer` / `discard`). Optional, so
  a reviewer can critique without setting an action.
- **D-07: Re-review replaces.** `reviewer_critique` is a single `Optional[str]`;
  a new review overwrites the prior critique via `update_experiment()`, matching
  the in-place persistence model. (No append/multi-reviewer accumulation.)

### Lessons structure (EREV-02)
- **D-08: Tagged-string convention** makes the frozen `list[str]` queryable with
  **zero schema change**: each lesson is stored as `"category: lesson text"`
  (e.g. `"prompting: needs explicit output format"`); the category prefix is
  parsed on read for filtering.
- **D-09: Dedicated `kajiba experiment lessons <id>` command.** `--add "..."`
  (repeatable) with optional `--category X` appends lessons; **no `--add` = read
  mode** (print the record's lessons); `--category X` filters. Writes funnel
  through `update_experiment()`.
- **D-10: Free-form category strings.** No controlled vocabulary is frozen
  (schema stays `list[str]`); common categories are suggested in `--help`.
- **D-11: Per-record + cross-record read-back.** `lessons <id>` prints one
  record's lessons; `lessons --category X` (no id) queries **across the whole
  store**; `experiment list` surfaces a lessons count/flag.

### Drift definition (EREV-03)
- **D-12: Grouping key = `(local_model.model_name, task_category)`.** Coarse
  enough to tolerate `task_description` wording variance and to accumulate enough
  runs per group to detect drift.
- **D-13: Metric = `eval_score` deviation from the group baseline.** Compare a
  run's `eval_score` to the group's prior mean (or first/baseline run); a
  deviation beyond the threshold flags drift. `eval_score` is the answer-quality
  signal (the reviewer/caller-set one from Phase 10).
- **D-14: Both directions, configurable threshold.** Flag regressions **and**
  improvements beyond a default of **0.15**, overridable via `--threshold`.
- **D-15: Store-wide scan that writes flagged records.** `kajiba experiment
  drift` scans the store, groups runs, computes per group, and writes `drift_flag`
  via `update_experiment()` on affected records; prints a Rich summary. Accepts
  `--id` to scan just one record's group. **Idempotent** — a re-run must also
  *clear* `drift_flag` on records that no longer meet the drift condition.

### Claude's Discretion
Left to researcher/planner — capture the cleanest approach, don't re-ask:
- Exact signature/placement of `update_experiment()` and whether review/lessons/
  drift share a common load→mutate→validate→write helper (lean yes).
- Whether `--from` for critique accepts both `.txt` (raw) and `.json` (a record
  fragment) and how each is parsed.
- Whether the drift `--threshold` default (0.15) is also readable from
  `~/.hermes/config.yaml` (mirrors the existing `scrub_strictness` config idiom)
  vs flag-only — lean flag-only with a named module constant.
- Exact baseline choice for D-13 (prior mean vs first run vs rolling window) and
  how groups with `<2` runs are handled (no drift, not flagged).
- The lesson category-prefix parse rule (delimiter, case handling,
  uncategorized-lesson fallback) and how `lessons --category` matches.
- Rich rendering details (drift summary table columns; lessons/critique display).
- Whether the new public funcs are re-exported from `kajiba/__init__.py`
  (lean yes if the Phase 15 practice project needs them programmatically).

### Folded Todos
- **`2026-06-04-fix-experiment-relog-dedup-cr01.md`** (CR-01 + WR-01..04) —
  folded into scope via **D-03**. CR-01 (critical data-loss: `log_experiment`
  dedups on `dest.exists()` keyed off an identity-only `record_id`, so a
  corrected re-log silently keeps the stale outcome) is resolved by routing all
  outcome-mutating writes through `update_experiment()` (intentional in-place
  overwrite). The companion warnings (WR-01 partial-scalar-flag fall-through,
  WR-02 missing `record_kind` ValidationError, WR-03 raw `JSONDecodeError`,
  WR-04 D-13 write-guard only checks leaf name) are localized error-handling /
  guard fixes in the `experiment` CLI/store that should be swept in while this
  phase is already editing those files.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Requirements
- `.planning/REQUIREMENTS.md` — **EREV-01, EREV-02, EREV-03** (the three locked
  requirements this phase satisfies).

### Schema Foundation (Phase 10 — FROZEN, do NOT add fields)
- `src/kajiba/schema.py` — `ExperimentRecord` / `ExperimentMetadata` /
  `ExperimentOutcome` (the fields written this phase: `reviewer_critique`,
  `reviewer_model`, `recommended_action`, `lessons_learned`, `drift_flag`),
  `compute_record_id()` / `compute_submission_hash()` (`:445-492` — prove that
  identity excludes outcome, which is **why in-place mutation is safe**, D-01),
  `RECOMMENDED_ACTIONS` / `RecommendedActionType` (`:117-118` — the `--action`
  vocab), `load_record()` (record_kind dispatch).
- `.planning/phases/10-experiment-schema-foundation/10-SPEC.md` and
  `10-CONTEXT.md` — locked schema rules/rationale (no schema mutation allowed).

### Phase 11 / 12 Integration Points
- `src/kajiba/experiment_store.py` — `log_experiment` (pure write path, the
  CR-01 dedup-skip lives here at `dest.exists()`), `EXPERIMENTS_DIR`,
  `build_experiment_record`. **Add `update_experiment()` here** (D-03).
- `src/kajiba/cli.py` — the `experiment` Click group (`:855+`), `log`
  (`experiment_log` at `:894`, the option/branch pattern to mirror), `list`,
  `_load_experiment` (`:82`, reuse for load-by-id). **Add `review` / `lessons` /
  `drift` subcommands here** and enrich `list`.
- `src/kajiba/eval_scorer.py` — Phase 12 **compute-on-read precedent**
  (eval score is NOT persisted); contrast for D-02 (drift_flag IS persisted).
- `src/kajiba/experiment_scrub.py` — **already scrubs** `reviewer_critique` and
  each `lessons_learned` element at the share boundary (`:12-14`, `:83-87`); the
  `"category: lesson"` tagged convention (D-08) is scrubbed whole, so no scrub
  changes are needed for this phase.
- `.planning/phases/12-eval-scoring-scrub-tuning/12-CONTEXT.md` (D-01..D-10;
  scorer reads `drift_flag`/`reviewer_critique` if present but does not compute
  them) and `.planning/phases/11-experiment-logging-private-store/11-CONTEXT.md`
  (store/write-path decisions) + `11-SECURITY.md` (AR-11-01 raw-at-rest).

### Folded Todo
- `.planning/todos/pending/2026-06-04-fix-experiment-relog-dedup-cr01.md` —
  CR-01 + WR-01..04 (resolved via D-03; see Folded Todos above).

### Design Source & Rationale
- `docs/dual-use-roadmap.md` — dual-use "shared core / divergent tail" direction.
- `.planning/seeds/v1.2-experiment-logging.md` and
  `.planning/notes/dual-use-direction-decisions.md` — converged v1.2 decisions
  (private/no-publish).
- `docs/kajiba-project-spec.md` — full pipeline + controlled vocabularies.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`experiment` Click group + `experiment_log` pattern** (`cli.py:855+`): the
  option-parsing, `_ensure_dirs()`, override-before-validate, and Rich-error
  idiom to mirror for the three new subcommands.
- **`_load_experiment(record_id)`** (`cli.py:82`): load-by-id with record_kind
  validation — reuse for review/lessons/drift.
- **`log_experiment` + atomic temp-file-replace** (`experiment_store.py:49-105`):
  the write mechanics `update_experiment()` should reuse (`os.replace`, D-13
  store guard).
- **`compute_record_id`/`compute_submission_hash`** (`schema.py:445-492`):
  proof that identity excludes outcome → in-place mutation keeps ID stable.

### Established Patterns
- One module per responsibility; single write path through `experiment_store.py`.
- Records serialized via `model_dump(mode="json", by_alias=True)`; loaded via
  `load_record`/`model_validate`; **re-validate after mutation** before writing.
- Compute-on-read for derived signals (eval score) vs **persisted** longitudinal
  verdict (drift_flag) — a deliberate split (D-02).
- `Optional[X]` typing, double quotes, Google-style docstrings, module-level
  `logger`, `UPPER_SNAKE_CASE` constants (e.g. a `DRIFT_THRESHOLD` constant).

### Integration Points
- **Review path:** `experiment review <id>` → `_load_experiment` → set
  `reviewer_critique` (+ optional `reviewer_model`, `recommended_action`) →
  `update_experiment()`.
- **Lessons path:** `experiment lessons <id> [--add --category | read | --category
  filter]` → `update_experiment()` for adds; store-wide read for cross-record.
- **Drift path:** `experiment drift [--id] [--threshold]` → scan store → group by
  (model_name, task_category) → compute eval_score deviation → write/clear
  `drift_flag` via `update_experiment()` → Rich summary.
- **Privacy:** scrubbing of the new free text is already handled by
  `experiment_scrub.py` at the share boundary (Phase 12) — no change here.

</code_context>

<specifics>
## Specific Ideas

- Reviewer can be a model (e.g. **Grok**) or a human — same command, identity
  optional. Critiques are pasted/file-fed because core must work offline.
- The single `update_experiment()` funnel is the structural fix for CR-01, not a
  bolt-on `--force` flag — making "correct a logged eval" a first-class,
  non-lossy operation.
- Lessons are lightweight tagged strings, not a new schema model — flexibility
  over ceremony, consistent with the frozen `list[str]`.
- Drift flags **both** regressions and improvements (instability in either
  direction is signal), and the scan is idempotent so the flag reflects current
  reality on every run.

</specifics>

<deferred>
## Deferred Ideas

- **Multi-reviewer history** (multiple critiques per record) — out of scope;
  `reviewer_critique` is a single string and re-review replaces (D-07). Revisit
  only if structured multi-reviewer provenance becomes a requirement.
- **Controlled lesson-category vocabulary** — deferred (D-10 chose free-form);
  promote to a frozen `LESSON_CATEGORIES` constant later if querying needs it.
- **Drift threshold in `~/.hermes/config.yaml`** — flag-only for now; config
  integration is a later convenience.
- **Cross-record lessons/drift in the analysis export** → **Phase 15**.
- **Live-captured review/drift** (from Hermes sessions) → **Phase 14**.

### Reviewed Todos (not folded)
None — the only pending todo (CR-01) was folded into scope.

</deferred>

---

*Phase: 13-reviewer-critique-drift*
*Context gathered: 2026-06-04*
