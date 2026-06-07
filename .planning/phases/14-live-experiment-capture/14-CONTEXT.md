# Phase 14: Live Experiment Capture - Context

**Gathered:** 2026-06-06
**Status:** Ready for planning

<domain>
## Phase Boundary

An eval run performed **inside a live Hermes session** is captured automatically
into an `ExperimentRecord` in the private experiments store — through the **same
shared plugin hooks** (Phases 6–7) that today build a coding-session
`KajibaRecord`. This is the cross-milestone bridge: it joins the v1.1 live-capture
machinery (plugin + turn buffering) to the v1.2 experiment pipeline (schema +
private store + eval scorer/reviewer/drift). Single requirement: **ECAP-01**.

**Success criteria this phase must make TRUE (ROADMAP §Phase 14):**
1. Running an evaluation inside a live Hermes session produces an `ExperimentRecord`
   via the shared plugin hooks.
2. A live-captured experiment record carries the same metadata/outcome structure as
   a deliberately-logged one (`kajiba experiment log`).

**Explicitly NOT in Phase 14 (belongs elsewhere):**
- Analysis-oriented export and the Nemotron/Qwen/Gemma practice-project workflow →
  **Phase 15** (EEXP-01/02). The practice project supplies its own `eval_score`;
  live Hermes capture does not.
- Reviewer-model critique, `lessons_learned` query, drift detection → **Phase 13**
  (already shipped; attached/computed *after* capture via existing subcommands).
- Eval scoring and experiment-aware scrub → **Phase 12** (already shipped; run *after*
  capture as explicit CLI steps).
- Any new community-publish path — experiments stay private/no-publish (locked).

</domain>

<decisions>
## Implementation Decisions

### Eval-run Trigger (how the plugin knows it's an eval)
- **D-01:** **Env-var / config opt-in.** The shared plugin reads a flag (e.g.
  `KAJIBA_EXPERIMENT=1`) at `on_session_start` and routes the whole session to
  experiment capture. When the flag is absent, behavior is **exactly today's
  coding-session capture — unchanged** (no regression to the v1.1 path). The
  trigger must NOT depend on a Hermes command/slash-command surface: the plugin
  registers only the four confirmed v0.15.x lifecycle hooks (`on_session_start`,
  `post_llm_call`, `post_tool_call`, `on_session_end`). Inference from session
  metadata was rejected (misclassification = privacy risk, since experiments are
  private and coding records can publish).
- **D-02:** **Whole opted-in session = one eval run = one `ExperimentRecord`.**
  Multiple evals = multiple sessions. No in-session segment markers (would need an
  in-session boundary signal we haven't verified). Mirrors the existing
  one-staging-file-per-session finalize shape.

### Field Mapping (live turns → experiment fields)
- **D-03:** **`local_model_output` = the final assistant response** (the model's
  answer turn). The full conversation is preserved separately in `trajectory`
  (D-06), so nothing is lost. Note this field is part of `compute_record_id()` —
  see the finalize-once correctness item in Claude's Discretion.
- **D-04:** **`task_description` = the first user turn** (the task as asked).
  **`task_category` and `experiment_type` come from optional env vars with sensible
  defaults** (suggested defaults: category `"coding"`, type `"model_evaluation"` —
  must be a valid `EXPERIMENT_TYPES` value). Planner picks the exact env-var names;
  keep them in the `KAJIBA_EXPERIMENT*` namespace.
- **D-05:** **`eval_score` = documented placeholder (`0.0`) at capture.** A live
  session has no automatic quality judge, and the Phase 12 scorer measures record
  *completeness* (complete/partial/thin), not output *quality*. The real evaluative
  score is filled later via `kajiba experiment score` / `kajiba experiment review`.
  The field is present and valid → structural parity with a deliberate log (SC#2).
  Document the `0.0 = captured-but-unscored` convention so it isn't read as
  "scored zero." (Schema is frozen — `eval_score` is required and cannot be made
  nullable.)
- **D-06:** **Populate `ExperimentRecord.trajectory` with the full captured
  session.** This is the optional field designed for exactly this; it gives the
  eval scorer/reviewer material to work with and is what makes a live-captured
  record richer than a scalar `experiment log`.

### Capture Architecture
- **D-07:** **Mode flag on the existing `KajibaCollector` — shared buffering,
  divergent finalize** ("shared core, divergent tail", the v1.2 architecture
  stance). `on_session_start` sets `self._experiment_mode` from the trigger;
  turn/tool buffering is **identical** to the coding path. At finalize, experiment
  mode builds an `ExperimentRecord` (trajectory + mapped fields per D-03..D-06) via
  Phase 11's `build_experiment_record` and writes via `log_experiment()` →
  `EXPERIMENTS_DIR`, **fully bypassing `staging`/`outbox`/continuous-mode
  auto-submit**. Rejected: capture-as-`KajibaRecord`-then-convert (a coding record
  would briefly land in `staging`, a community path → privacy risk). A separate
  `ExperimentCollector` over a shared base was considered cleaner but is more
  refactor than one requirement warrants.
- **D-08 (derived constraint, not re-asked):** In experiment mode the collector
  **must never** touch `STAGING_DIR`/`OUTBOX_DIR` or the `contribution_mode ==
  "continuous"` auto-submit branch. Experiments are private/no-publish (locked
  project decision); the only write target is `EXPERIMENTS_DIR` via
  `log_experiment()`.

### Capture-time Pipeline
- **D-09:** **Store raw at capture; scrub/score/review/drift all run later** via the
  existing `kajiba experiment scrub` (P12) / `score` (P12) / `review` (P13) /
  `drift` (P13) subcommands. This mirrors Phase 11 deliberate logging (records land
  raw, D-02 of Phase 11), keeps the finalize path fast and fault-tolerant, and
  honors the carried hard rule **"scrub is a CLI step, never in a hook."** Rejected:
  auto-scrub at finalize (puts scrubbing work in the lifecycle-hook path — rule
  violation).
- **D-10:** **Reviewer model is NOT in the live loop.** Live capture records only
  the local model's output; `reviewer_model` / `reviewer_critique` stay `None` at
  capture and are attached later via `kajiba experiment review` (Phase 13).

### Claude's Discretion (delegated to researcher/planner — capture, don't re-ask)
- **Finalize-once for experiments (CORRECTNESS — must solve):** `on_session_end`
  fires after **every** `run_conversation` turn AND at CLI exit (turn-scoped, per
  `06-HOOK-KWARGS.md` finding 2 / 07-CONTEXT). Because `local_model_output` (the
  final assistant response, D-03) changes each turn and feeds
  `compute_record_id()`, naive per-turn writes would emit **N different**
  `exp_<id>.json` files. Planner MUST finalize once per session (accumulate across
  turns, compute the content-addressed ID + write only on the true session end /
  CLI exit), keyed by `session_id` — the same finalize-once discipline the coding
  path uses (it sidesteps this by writing a fixed `session_{id}.json` and
  overwriting; the experiment path is content-addressed so it needs explicit
  finalize-once). Consider the existing `self._finalized` guard as the starting
  point.
- **`experiment_id` derivation for a live run:** likely derived from `session_id`
  (e.g. a `live_<session_id>` scheme) so re-runs are traceable; planner's call.
- **`local_model` metadata reuse:** the collector already assembles
  `self._model_metadata` via `_extract_model_metadata` / `_enrich_from_ollama`
  (CAPT-04). Reuse it directly as `ExperimentMetadata.local_model` — including
  Ollama param-count/quantization when local, and the remote-degrade path when not.
- **Remote model under "eval mode":** the `local_model` field may hold a remote
  model (`is_local=false`) when the opted-in session runs a remote backend. That is
  acceptable — the field captures the model under evaluation regardless of locality;
  do not block capture on locality.
- **Exact env-var names + defaults** (`KAJIBA_EXPERIMENT`, and the optional
  type/category knobs) and where the flag is read/stored on the collector.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Requirements & Scope
- `.planning/REQUIREMENTS.md` — **ECAP-01** (the single locked requirement; depends
  on v1.1 Phase 6–7) and the upstream CAPT-02/03/04 it reuses.
- `.planning/ROADMAP.md` §"Phase 14: Live Experiment Capture" — goal + the two
  success criteria this phase must make TRUE.

### Live-Capture Foundation (v1.1 Phase 6–7 — the cross-milestone dependency, READ FIRST)
- `.planning/phases/06-environment-plugin-foundation/06-HOOK-KWARGS.md` — **THE
  authoritative live v0.15.x payload contract** for the four hooks; settles the
  turn-scoped `on_session_end` behavior that drives the finalize-once requirement.
- `.planning/phases/06-environment-plugin-foundation/06-CONTEXT.md` — plugin package
  layout, `register(ctx)`, HERMES_HOME resolution, fault-tolerant hooks.
- `.planning/phases/07-turn-capture-semantic-pii-scrubbing/07-CONTEXT.md` — paired
  turn / tool-buffer capture decisions and the finalize-once (accumulate +
  finalize on last end) discipline this phase must reuse.

### Experiment Pipeline (v1.2 Phase 10–13 — the divergent tail this phase feeds)
- `.planning/phases/10-experiment-schema-foundation/10-CONTEXT.md` and
  `.planning/phases/10-experiment-schema-foundation/10-SPEC.md` — frozen
  `ExperimentRecord` / `ExperimentMetadata` / `ExperimentOutcome` field sets,
  `record_kind` discriminator, `kajiba_exp_<12hex>` identity rules.
- `.planning/phases/11-experiment-logging-private-store/11-CONTEXT.md` — private
  store (`EXPERIMENTS_DIR`, `exp_<id>.json`, no staging gate), the
  `log_experiment` / `build_experiment_record` write path, and the publish-exclusion
  guard (D-13/D-14) live capture must not violate.

### Design Source & Rationale
- `docs/dual-use-roadmap.md` — dual-use direction, private/no-publish strategy.
- `.planning/seeds/v1.2-experiment-logging.md` — "shared core / divergent tail"
  converged decision (D-07 implements it for the capture layer).
- `.planning/notes/dual-use-direction-decisions.md` — decision log behind v1.2.
- `docs/kajiba-project-spec.md` — full pipeline/schema design and controlled
  vocabularies (`EXPERIMENT_TYPES`, `RECOMMENDED_ACTIONS`).

### Existing Code (the integration surface)
- `src/kajiba/collector.py` — `KajibaCollector`: `on_session_start` (set the mode
  flag here), the turn/tool buffer (`on_llm_turn` / `on_tool_call`),
  `on_session_end` (the divergent finalize), `_build_record` (the coding-path
  analog), `self._model_metadata` / `self._hardware`, `self._finalized` guard.
- `src/kajiba/plugin/hooks.py` + `src/kajiba/plugin/__init__.py` — the four
  registered hooks and `set_collector`; where the trigger flag is first observable.
- `src/kajiba/experiment_store.py` — `build_experiment_record(**fields)`,
  `log_experiment(record)`, `EXPERIMENTS_DIR`; the finalize target (D-07).
- `src/kajiba/schema.py` — `ExperimentRecord` (+ `trajectory` optional field),
  `ExperimentMetadata`, `ExperimentOutcome`, `EXPERIMENT_TYPES`,
  `compute_record_id()` (note: hashes `local_model_output` → finalize-once concern).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`KajibaCollector` turn/tool buffer** (`on_llm_turn`, `on_tool_call`, pending-turn
  buffer) — captures identically for both kinds; D-07 reuses it wholesale and only
  branches the finalize tail.
- **`self._model_metadata`** assembled via `_extract_model_metadata` /
  `_enrich_from_ollama` (CAPT-04) — drops straight into
  `ExperimentMetadata.local_model`, including Ollama param-count/quantization or the
  remote-degrade path.
- **`build_experiment_record(**fields)` + `log_experiment()`** (Phase 11) — the
  single experiment write path; CLI deliberate-logging already uses it, so reusing
  it here guarantees SC#2 structural parity for free.
- **`EXPERIMENTS_DIR`** (HERMES_HOME-isolated, separate from staging/outbox) — the
  only write target in experiment mode; the publish-exclusion guard (Phase 11 D-13)
  already protects it.
- **`self._finalized` guard + idempotent finalize** (coding path) — the template for
  the experiment finalize-once-per-session requirement.
- **`ExperimentRecord.trajectory`** (optional) — purpose-built home for the captured
  conversation (D-06).

### Established Patterns
- **Fault-tolerant hooks** — every handler wraps its body in try/except and never
  propagates to Hermes. Keep this on the experiment path.
- **Scrub at CLI step, never in hooks** — carried hard rule; D-09 honors it
  (store raw, scrub later).
- **One module per responsibility** — branching belongs in `collector.py` (mode
  flag) + reuse of `experiment_store.py`; avoid a new persistence path.
- **Records serialized with `model_dump(mode="json", by_alias=True)`** and loaded
  via `load_record` (dispatches on `record_kind`).

### Integration Points
- Trigger flag → `register`/`on_session_start` → `KajibaCollector._experiment_mode`.
- `post_llm_call` / `post_tool_call` → shared turn/tool buffer (unchanged).
- `on_session_end` (turn-scoped) → finalize-once → **experiment mode:**
  `build_experiment_record(... trajectory=...)` → `log_experiment()` →
  `EXPERIMENTS_DIR/exp_<id>.json`; **coding mode:** existing `_save_to_staging` /
  auto-submit (unchanged).
- Downstream (later, manual): `kajiba experiment scrub|score|review|drift` operate on
  the stored record.

</code_context>

<specifics>
## Specific Ideas

- The whole point of Phase 14 is the **bridge**: prove the v1.1 plugin and the v1.2
  store meet, with **zero new schema and zero new persistence module** — only a mode
  flag and a finalize branch. If the planner finds itself adding a new model or a new
  store, that's a smell.
- **SC#2 is satisfied by construction** if live capture routes through the same
  `build_experiment_record` / `log_experiment` the deliberate `kajiba experiment log`
  uses — the structures are then identical by definition (the only systematic
  differences are a populated `trajectory` and the `0.0` placeholder score).
- **No regression to the coding path** is a first-class constraint: with the env var
  unset, the v1.1 capture behavior must be byte-for-byte what it is today.

</specifics>

<deferred>
## Deferred Ideas

- **Auto-scoring/scrubbing at capture** — rejected for Phase 14 (D-09, rule
  conflict); remains a manual post-capture step. Could revisit only if the
  no-scrub-in-hooks rule is ever relaxed (unlikely).
- **In-session eval segmentation** (multiple eval records per session) — deferred
  (D-02); would need a verified in-session boundary signal.
- **Practice-project / analysis-export integration** that supplies a real
  `eval_score` at write time → **Phase 15** (EEXP-01/02).

### Reviewed Todos (not folded)
- **`2026-06-04-fix-experiment-relog-dedup-cr01.md`** — "Fix experiment re-log dedup
  data loss (CR-01) + Phase 11 review warnings." Matched at 0.6 on generic keyword
  overlap (`experiment`, `phase`) only. **Already resolved in Phase 13** (PROJECT.md:
  "CR-01 closed" via `update_experiment` in-place overwrite). Not Phase 14
  live-capture scope — left closed/deferred, not folded.

</deferred>

---

*Phase: 14-live-experiment-capture*
*Context gathered: 2026-06-06*
