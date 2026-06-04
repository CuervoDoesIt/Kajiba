# Phase 11: Experiment Logging & Private Store - Context

**Gathered:** 2026-06-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the dual-use experiment capability **usable for the first time**. Phase 10
delivered the frozen `ExperimentRecord` schema; Phase 11 delivers the way to
*write* one:

1. A `kajiba experiment` CLI command group that records an eval run as an
   `ExperimentRecord` with no live Hermes session (ELOG-01).
2. A programmatic logging entry point so an external script (the Phase 15
   practice project) can persist `ExperimentRecord`s directly (ELOG-02).
3. A **private local store** — a namespace distinct from coding-session
   staging/outbox — that is structurally and defensively excluded from every
   community path (publish / browse / download) (ELOG-03).

**Out of scope (later phases):** eval-specific scoring and experiment-aware
scrub tuning (Phase 12); reviewer critique, `lessons_learned` query, drift
detection (Phase 13); live Hermes capture (Phase 14); analysis export +
practice-project integration (Phase 15). No scrubbing happens at log time in
this phase — records are stored raw.

</domain>

<decisions>
## Implementation Decisions

### Private Store Layout
- **D-01:** Single flat store at `~/.hermes/kajiba/experiments/`, **one JSON
  file per run** named `exp_<record_id>.json` (e.g.
  `exp_kajiba_exp_<12hex>.json` — mirror the existing
  `record_{record_id}` naming idiom; exact filename prefix is planner's
  discretion as long as it is one file per run and clearly an experiment).
- **D-02:** **No staging→outbox promotion gate.** Coding sessions need the
  two-stage gate because they get promoted toward publishing; experiments
  never publish, so a single store is correct. Records land directly in the
  store on log.
- **D-03:** The store base path derives from the **same base constant as
  `STAGING_DIR`/`OUTBOX_DIR`** (`KAJIBA_BASE` in `cli.py`), so it inherits
  HERMES_HOME profile isolation automatically when v1.1 Phase 6 lands. Do not
  hardcode a second `~/.hermes` literal — add `EXPERIMENTS_DIR = KAJIBA_BASE /
  "experiments"` and include it in `_ensure_dirs()`.
- **D-04:** Format is one-JSON-per-run (not append-only JSONL) for easy
  inspection and per-record read-back by Phases 13/15.

### Programmatic API (ELOG-02)
- **D-05:** New module `src/kajiba/experiment_store.py` owns persistence
  (single-responsibility, matching the module-per-concern convention).
- **D-06:** Two public functions:
  - `log_experiment(record: ExperimentRecord) -> Path` — computes IDs
    (`compute_record_id()` / `compute_submission_hash()` from Phase 10),
    writes the JSON to the store, returns the written path.
  - `build_experiment_record(**fields) -> ExperimentRecord` — convenience
    constructor for callers that prefer kwargs over assembling the nested
    model by hand.
- **D-07:** Both functions are **re-exported from `kajiba/__init__.py`** so
  the practice project imports `from kajiba import log_experiment,
  build_experiment_record`. (`__init__.py` currently exports only
  `__version__` — extend it.)
- **D-08:** Validation stays at the Pydantic boundary — `log_experiment`
  accepts an already-validated `ExperimentRecord`; `build_experiment_record`
  validates on construction. `log_experiment` is the single write path the
  CLI also calls (no duplicate persistence logic).

### CLI Input Model (ELOG-01)
- **D-09:** Add a `kajiba experiment` **Click group** (new `@cli.group()`,
  the same pattern as the existing `config` group). Primary subcommand:
  `kajiba experiment log`. (Subcommand name `log` is planner's discretion;
  reads cleanly.)
- **D-10:** **File-first input:** `kajiba experiment log --from run.json`
  loads a JSON, validates it into an `ExperimentRecord` (reuse Phase 10's
  `load_record()` / `ExperimentRecord.model_validate`), then calls
  `log_experiment()`. This is the same file shape an eval script produces, so
  CLI and programmatic paths share one format.
- **D-11:** A few **scalar convenience flags** (`--score`, `--type`,
  `--task-category`, and similar top-level scalars) override or fill fields
  on top of `--from`, for quick adjustments without editing the file.
- **D-12:** **Interactive fallback:** when neither `--from` nor the required
  flags are supplied, prompt for the essential fields via Rich (matches the
  project's HITL preference). Nested `ModelMetadata` is awkward to prompt for
  field-by-field — planner may accept a `--model-from`/`--local-model` JSON
  snippet or reuse hardware/model auto-detection; capture the cleanest path.

### Publish Exclusion (ELOG-03)
- **D-13:** **Structural + active guard (defense in depth).**
  - *Structural:* experiments live only in `EXPERIMENTS_DIR`; `publish`
    globs `OUTBOX_DIR` and `browse`/`download` hit the remote dataset, so the
    separate dir already excludes them. The experiment store **must never**
    write into `STAGING_DIR`/`OUTBOX_DIR` (assert/guard this in
    `experiment_store.py`).
  - *Active:* `publish` (and `submit`, if a path could reach it) explicitly
    **skip or refuse any record where `record_kind == "model_experiment"`**,
    so a misplaced experiment file can never enter the community path.
- **D-14:** A regression test must assert that an `ExperimentRecord` written
  by `log_experiment()` does **not** appear in `publish`/`browse`/`download`
  output (proves ELOG-03 structurally and via the guard).

### Claude's Discretion
Left to researcher/planner — capture the cleanest approach, don't re-ask:
- **Read-back command:** lean toward a minimal `kajiba experiment list` so the
  user can confirm runs landed and demonstrate they are absent from `browse`.
  A richer `show`/query interface is Phase 13/15 — keep Phase 11 to log (+
  optional minimal list).
- **Exact `run.json` schema/example:** the canonical example file the ELOG-02
  callers follow (likely just a serialized `ExperimentRecord`). Document it.
- **Duplicate / overwrite handling:** content-addressable IDs mean re-logging
  the same experiment yields the same `exp_<id>.json`; decide overwrite vs
  skip-with-notice (suggested: skip + inform, since the content is identical).
- **Interactive-mode field coverage** and how nested `ModelMetadata` is
  gathered (see D-12).
- Filename prefix exact spelling (D-01) and where the store dir constant lives.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Requirements
- `.planning/REQUIREMENTS.md` — ELOG-01, ELOG-02, ELOG-03 (the three locked
  requirements this phase satisfies)

### Schema Foundation (Phase 10 — this phase builds directly on it)
- `src/kajiba/schema.py` — `ExperimentRecord` / `ExperimentMetadata` /
  `ExperimentOutcome` (frozen field sets), `RecordBase`, `load_record()`
  dispatch by `record_kind`, `compute_record_id()` /
  `compute_submission_hash()` (`kajiba_exp_<12hex>` identity), the
  `EXPERIMENT_TYPES` / `RECOMMENDED_ACTIONS` vocabularies. MUST read — Phase
  11 constructs and persists these models.
- `.planning/phases/10-experiment-schema-foundation/10-SPEC.md` — locked
  schema requirements/boundaries Phase 11 must respect.
- `.planning/phases/10-experiment-schema-foundation/10-CONTEXT.md` — Phase 10
  decisions (D-04/D-05/D-06 identity/prefix rules, no community dedup).

### CLI & Persistence Integration Points
- `src/kajiba/cli.py` — `KAJIBA_BASE` / `STAGING_DIR` / `OUTBOX_DIR`
  constants, `_ensure_dirs()`, the `config` `@cli.group()` pattern to mirror,
  and the `publish` / `browse` / `download` commands the active guard must
  touch (publish globs `OUTBOX_DIR`).
- `src/kajiba/__init__.py` — the package export surface to extend with
  `log_experiment` / `build_experiment_record` (currently `__version__` only).

### Design Source & Rationale
- `docs/dual-use-roadmap.md` — dual-use direction, experiment store /
  private-namespace strategy, open questions.
- `.planning/seeds/v1.2-experiment-logging.md` — converged dual-use decisions
  (shared core / divergent tail, private/no-publish).
- `.planning/notes/dual-use-direction-decisions.md` — decision log behind the
  v1.2 milestone.
- `docs/kajiba-project-spec.md` — full pipeline/schema design and controlled
  vocabularies.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Phase 10 schema** (`schema.py`): `ExperimentRecord` + `build`/identity
  methods are complete and frozen — Phase 11 only constructs, validates, and
  persists them. `load_record()` already dispatches by `record_kind`.
- **`cli.py` directory plumbing:** `KAJIBA_BASE`, `STAGING_DIR`, `OUTBOX_DIR`,
  and `_ensure_dirs()` are the template for `EXPERIMENTS_DIR`.
- **`config` `@cli.group()`** (cli.py ~line 677) is the structural template
  for the new `experiment` group.
- **Rich prompts / Console** already used throughout `cli.py` for the
  interactive fallback.

### Established Patterns
- One module per responsibility (schema / scrubber / scorer / collector /
  cli) → new `experiment_store.py` for persistence.
- Records serialized with `model_dump(mode="json", by_alias=True)`; loaded
  with `model_validate` / `load_record`.
- `Optional[X]` typing, Google-style docstrings, module-level `logger`,
  double-quote strings, `UPPER_SNAKE_CASE` module constants — match these.
- Private/no-publish is a locked project decision; the store and guards
  enforce it.

### Integration Points
- **Write path:** CLI `experiment log` → `build_experiment_record` (or
  `--from` load) → `log_experiment` → `EXPERIMENTS_DIR/exp_<id>.json`.
- **Guard path:** `publish` (and `submit`) gain a `record_kind ==
  "model_experiment"` skip/refuse check.
- **Export surface:** `kajiba/__init__.py` re-exports the two functions.

</code_context>

<specifics>
## Specific Ideas

- The `kajiba_exp_` ID prefix (Phase 10) and the separate `experiments/` store
  together make private experiment data visually and structurally distinct
  from community coding records at every layer.
- CLI and programmatic paths deliberately share **one file format** (a
  serialized `ExperimentRecord`) so `--from run.json` and the ELOG-02 script
  path are interchangeable.
- Belt-and-suspenders privacy: directory separation is the primary mechanism,
  the `record_kind` refusal in `publish` is the backstop, and a regression
  test proves both.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (Read-back beyond a minimal
`experiment list`, querying `lessons_learned`, drift detection, scrubbing, and
eval scoring were all correctly identified as Phase 12/13 scope and left
there.)

</deferred>

---

*Phase: 11-experiment-logging-private-store*
*Context gathered: 2026-06-03*
