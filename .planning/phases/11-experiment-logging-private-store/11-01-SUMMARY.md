---
phase: 11-experiment-logging-private-store
plan: 01
subsystem: infra
tags: [experiment-logging, persistence, atomic-write, pydantic, dual-use, private-store]

# Dependency graph
requires:
  - phase: 10-experiment-schema-foundation
    provides: "ExperimentRecord/ExperimentMetadata/ExperimentOutcome models, frozen compute_record_id/compute_submission_hash (kajiba_exp_<12hex>), load_record() dispatch"
provides:
  - "log_experiment(record, store_dir) — the single atomic write path for private experiment records (ELOG-02)"
  - "build_experiment_record(**fields) — keyword-only convenience constructor for ExperimentRecord (ELOG-02)"
  - "D-13 structural write guard: refuses any store_dir not named 'experiments'"
  - "EXPERIMENTS_DIR constant in cli.py (KAJIBA_BASE / 'experiments'), created in _ensure_dirs()"
  - "Package-level re-exports: from kajiba import log_experiment, build_experiment_record (D-07)"
  - "tests/fixtures/experiment_run.example.json — canonical --from / run.json example"
affects: [11-02-cli-surface, 11-03-publish-exclusion-guard, experiment-logging]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single atomic write path (tempfile.mkstemp in-dir + os.replace, cleanup on BaseException)"
    - "Structural privacy guard (store_dir.resolve().name == 'experiments') as a write-time invariant"
    - "Content-addressable skip-with-notice dedup via frozen schema identity methods"
    - "Click-free single-responsibility persistence module callable by both CLI and external scripts"

key-files:
  created:
    - src/kajiba/experiment_store.py
    - src/kajiba/__init__.py
    - tests/test_experiment_store.py
    - tests/fixtures/experiment_run.example.json
  modified:
    - src/kajiba/cli.py

key-decisions:
  - "store_dir passed as an argument to log_experiment (not a hardcoded constant) — keeps the store module Click-free and test-isolatable; EXPERIMENTS_DIR lives in cli.py per D-03"
  - "Dedup is skip-with-notice (return existing path, log .info) rather than overwrite — identical content never needs rewriting (D-02)"
  - "build_experiment_record is keyword-only with **extra passthrough for optional top-level fields (model/hardware/trajectory)"

patterns-established:
  - "Atomic write: tempfile.mkstemp(dir=store_dir, suffix='.tmp') -> os.fdopen write -> os.replace; unlink(missing_ok=True) on BaseException"
  - "Privacy-by-structure: a write helper enforces its own destination namespace and raises ValueError otherwise"

requirements-completed: [ELOG-02, ELOG-03]

# Metrics
duration: 3min
completed: 2026-06-04
---

# Phase 11 Plan 01: Experiment Store Persistence Foundation Summary

**Single atomic write path (`log_experiment`) plus a `build_experiment_record` constructor for private model-experiment records, with a D-13 structural guard, `EXPERIMENTS_DIR` constant, and package re-exports — all green via six TDD tests.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-06-04T02:24:25Z
- **Completed:** 2026-06-04T02:27:00Z
- **Tasks:** 3
- **Files modified:** 5 (4 created, 1 modified)

## Accomplishments
- `src/kajiba/experiment_store.py`: the single direct-to-store write path for experiment records, computing identity via the frozen Phase 10 schema methods, writing one flat `exp_<record_id>.json` atomically (D-01/D-02/D-05/D-08).
- D-13 structural privacy guard: `log_experiment` refuses any `store_dir` whose resolved name is not `experiments`, so an experiment can never land in `staging`/`outbox`.
- `build_experiment_record(**fields)`: keyword-only convenience constructor assembling the nested `ExperimentMetadata`/`ExperimentOutcome`/`ModelMetadata` tree, validated on construction.
- `EXPERIMENTS_DIR` derived from `KAJIBA_BASE` in `cli.py` and created in `_ensure_dirs()` (D-03); package re-exports so `from kajiba import log_experiment, build_experiment_record` resolves (D-07).
- Canonical `tests/fixtures/experiment_run.example.json` fixture (doubles as the documented `--from` example for 11-02).
- Full suite: 270 passed, 2 skipped (was 264 + 2 pre-existing yaml-soft-dep skips) — no regressions.

## Task Commits

Each task was committed atomically (TDD: RED test → GREEN impl → wire-up):

1. **Task 1: Wave-0 test stubs + canonical run.json fixture** - `0b57f65` (test)
2. **Task 2: experiment_store.py — log_experiment + build_experiment_record** - `0be30da` (feat)
3. **Task 3: EXPERIMENTS_DIR constant + package re-exports** - `1255a07` (feat)

## Files Created/Modified
- `src/kajiba/experiment_store.py` - New single-responsibility persistence module: `log_experiment` (atomic write + D-13 guard + dedup) and `build_experiment_record` (convenience constructor).
- `src/kajiba/__init__.py` - Added `from kajiba.experiment_store import build_experiment_record, log_experiment` (D-07 export surface; project has no `__all__` convention).
- `src/kajiba/cli.py` - Added `EXPERIMENTS_DIR = KAJIBA_BASE / "experiments"` and its `mkdir` in `_ensure_dirs()` (D-03); no new `~/.hermes` literal introduced.
- `tests/test_experiment_store.py` - Six pytest functions (test_build_record, test_log_writes_file, test_atomic_write, test_dedup_skip, test_public_exports, test_refuses_outbox_dir).
- `tests/fixtures/experiment_run.example.json` - Canonical `model_experiment` run example (omits record_id/submission_hash; `log_experiment` computes them).

## Decisions Made
- **store_dir as argument (not module constant in the store):** keeps `experiment_store.py` Click-free for ELOG-02 callers and lets tests pass `tmp_path / "experiments"` directly — cleaner than monkeypatching CLI constants. `EXPERIMENTS_DIR` itself lives in `cli.py` per D-03, derived from the single `KAJIBA_BASE` literal.
- **skip-with-notice dedup:** identical content returns the existing path and logs at `.info` — no rewrite, consistent with content-addressable identity (D-01/D-02).
- Followed plan task order and TDD gate sequence exactly (test → feat → feat).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None. Git emitted expected LF→CRLF warnings on Windows (cosmetic, no impact).

## TDD Gate Compliance
- RED gate: `0b57f65` is a `test(11-01)` commit; the six tests failed (ModuleNotFoundError) before implementation, as expected.
- GREEN gate: `0be30da` is a `feat(11-01)` commit landing `experiment_store.py`; the five store/build tests passed.
- Wire-up: `1255a07` (`feat(11-01)`) added the constant + re-exports; `test_public_exports` and the full file went green.
- No REFACTOR commit needed (implementation was clean on first pass).

## User Setup Required
None - no external service configuration required. (Phase 11 installs no external packages; all stdlib + already-pinned pydantic/click/rich — threat T-11-SC accepted, no package-legitimacy gate.)

## Next Phase Readiness
- 11-02 (CLI surface) can now call `log_experiment(record, EXPERIMENTS_DIR)` and use `tests/fixtures/experiment_run.example.json` as its `--from` test input.
- 11-03 (publish exclusion guard) can rely on the structural separation; the active `record_kind == "model_experiment"` skip in `publish` remains to be added there.
- No blockers.

## Self-Check: PASSED

All created files verified present (experiment_store.py, __init__.py, test_experiment_store.py, experiment_run.example.json, 11-01-SUMMARY.md) and all three task commits (0b57f65, 0be30da, 1255a07) exist in git history.

---
*Phase: 11-experiment-logging-private-store*
*Completed: 2026-06-04*
