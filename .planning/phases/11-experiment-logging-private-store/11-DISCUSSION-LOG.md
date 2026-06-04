# Phase 11: Experiment Logging & Private Store - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-03
**Phase:** 11-experiment-logging-private-store
**Areas discussed:** Private store layout, Programmatic API, CLI input model, Publish exclusion

---

## Private Store Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Single store, 1 JSON/run | Flat `~/.hermes/kajiba/experiments/`, one `exp_<record_id>.json` per run, no staging→outbox gate. Experiments never publish so the promotion gate doesn't apply. | ✓ |
| Two-stage (mirror coding) | Reuse staging→outbox pattern for a future review/scrub gate. More structure now for later flexibility. | |
| Append-only JSONL log | One `experiments.jsonl`, each run appended as a line. Compact, less convenient for per-record editing. | |

**User's choice:** Single store, one JSON per run (recommended).
**Notes:** Drives D-01..D-04. No promotion gate; store base derives from `KAJIBA_BASE` for HERMES_HOME isolation.

---

## Programmatic API (ELOG-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Function + builder helper | New `experiment_store.py` with `log_experiment(record)->Path` + `build_experiment_record(**fields)->ExperimentRecord`, both re-exported from `kajiba`. | ✓ |
| Single kwargs function | One `log_experiment(**fields)->Path` that assembles + validates + writes internally. Simplest call site, hides the model. | |
| ExperimentStore class | Stateful `ExperimentStore(dir)` with `.log()/.list()/.get()`. OO style, heavier for one-shot writes. | |

**User's choice:** Function + builder helper (recommended).
**Notes:** Drives D-05..D-08. `log_experiment` is the single write path the CLI also calls; validation stays at the Pydantic boundary.

---

## CLI Input Model (ELOG-01)

| Option | Description | Selected |
|--------|-------------|----------|
| File-first + key flags | `kajiba experiment log --from run.json` primary (same shape scripts produce) + scalar convenience flags + interactive fallback. | ✓ |
| Pure flags | Every field as a flag, including nested ModelMetadata flags. Explicit but verbose/awkward. | |
| Pure interactive | Rich prompts for every field. Friendly for one-off, tedious for repeated runs, not script-friendly. | |

**User's choice:** File-first + key flags (recommended).
**Notes:** Drives D-09..D-12. New `@cli.group()` mirroring `config`; CLI and programmatic paths share one file format.

---

## Publish Exclusion (ELOG-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Structural + active guard | Separate dir (structural) PLUS publish/submit refuse `record_kind=model_experiment`, plus store asserts no writes to staging/outbox. Belt-and-suspenders. | ✓ |
| Structural only | Rely solely on directory separation. Simplest, correct unless a future path globs the experiment dir. | |
| Active guard only | record_kind refusal in publish/submit without special store location. | |

**User's choice:** Structural + active guard (recommended).
**Notes:** Drives D-13..D-14. Regression test must prove experiments are absent from publish/browse/download.

---

## Claude's Discretion

- Minimal `kajiba experiment list` read-back command (lean to include); richer query is Phase 13/15.
- No scrubbing at log time — store raw; experiment-aware scrubbing is Phase 12.
- Exact `run.json` example schema for ELOG-02 callers.
- Duplicate/overwrite handling (suggested: skip + inform, since content-addressable IDs make re-logs identical).
- Interactive-mode field coverage and how nested `ModelMetadata` is gathered.
- Exact `exp_<id>.json` filename prefix and store-dir constant location.

## Deferred Ideas

None — discussion stayed within phase scope.

---

## Process Note (tooling)

`gsd-tools init.phase-op 11` reported `phase_found: false` with all phase fields null. Root cause: it derives `phase_found` from the on-disk phase-directory lookup (`find-phase`), not the roadmap. `roadmap get-phase 11` returns `found: true`. Phase 11 simply had no directory yet (normal for a fresh phase). This false negative also leaves `expected_phase_dir` null, so the workflow's own `mkdir` fallback can't fire. Worked around by deriving `padded_phase=11`, slug `experiment-logging-private-store`, and dir `.planning/phases/11-experiment-logging-private-store` from the roadmap. The same false negative will recur for any not-yet-started phase (e.g. 7, 8, 9, 12–15).
