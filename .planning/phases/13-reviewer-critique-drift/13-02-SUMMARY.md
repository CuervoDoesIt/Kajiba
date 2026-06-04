---
phase: 13-reviewer-critique-drift
plan: 02
subsystem: database
tags: [experiment-store, atomic-write, pydantic, os-replace, dual-use, tdd-green]

# Dependency graph
requires:
  - phase: 13-reviewer-critique-drift (13-01)
    provides: RED store tests (update_experiment overwrite/identity/EQUAL-guard/default-base), 3 migrated log_experiment tests, EXPERIMENTS_DIR parity test
  - phase: 11-experiment-logging (11-01)
    provides: log_experiment atomic write path, build_experiment_record, D-13 structural guard
  - phase: 10-schema-dual-use
    provides: ExperimentRecord + frozen compute_record_id/compute_submission_hash (identity excludes outcome)
provides:
  - "update_experiment() in-place overwrite write path (CR-01 closed, D-03)"
  - "EXPERIMENTS_DIR module constant in experiment_store.py (Click-free guard default base)"
  - "EQUAL expected_base store guard (WR-04) on both log_experiment and update_experiment"
affects: [13-03, 13-04, 13-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "In-body call-time default resolution for monkeypatchable module constant (never def-time binding)"
    - "EQUAL expected_base store guard predicate (store_dir.resolve() == expected_base.resolve())"
    - "Re-validate-after-mutation before durable write (models lack validate_assignment)"

key-files:
  created: []
  modified:
    - src/kajiba/experiment_store.py
    - tests/test_experiment_exclusion.py

key-decisions:
  - "update_experiment OMITS the dest.exists() early-return so corrections always overwrite (CR-01); log_experiment keeps dedup-skip for identical first-log re-logs (D-03 funnel)"
  - "WR-04 guard tightened from leaf-name (resolved.name != 'experiments') to EQUAL (store_dir.resolve() == expected_base.resolve()) on BOTH write functions"
  - "expected_base defaults to None and resolves to EXPERIMENTS_DIR IN-BODY at call time so monkeypatch is honored; never bound as def-time default"
  - "EXPERIMENTS_DIR duplicated from cli.py:70 stdlib Path expression (NOT imported) to keep store Click-free; parity test guards drift"

patterns-established:
  - "Call-time module-constant default: resolve None → MODULE_CONST inside the body, not the signature, for monkeypatchability"
  - "EQUAL store guard: privacy boundary enforced by exact resolved-path equality, not name heuristics"

requirements-completed: [EREV-01, EREV-02, EREV-03]

# Metrics
duration: 12min
completed: 2026-06-04
---

# Phase 13 Plan 02: update_experiment In-Place Overwrite + EQUAL Store Guard Summary

**Added `update_experiment()` — the non-lossy in-place corrective write path (CR-01 closed) — plus a tightened EQUAL `expected_base` store guard (WR-04) and a Click-free `EXPERIMENTS_DIR` constant, turning all eight 13-01 store RED tests GREEN with zero regressions and schema untouched.**

## Performance

- **Duration:** ~12 min
- **Completed:** 2026-06-04
- **Tasks:** 1 (TDD GREEN; RED authored in 13-01)
- **Files modified:** 2

## Accomplishments
- `update_experiment(record, store_dir, *, expected_base=None) -> Path`: in-place overwrite write path with NO `dest.exists()` early-return — corrections always overwrite, closing CR-01 (the `log_experiment` dedup-skip data-loss bug). Atomic `tempfile.mkstemp` + `os.replace` with `BaseException` temp cleanup, copied verbatim from `log_experiment`.
- Re-validate-after-mutation: `ExperimentRecord.model_validate(record.model_dump(mode="json", by_alias=True))` before write, so an out-of-range forced value is rejected by Pydantic, not persisted (Pitfall 3; models lack `validate_assignment`).
- Identity stays byte-stable across outcome/metadata mutation (D-01): `compute_record_id` excludes outcome (schema.py:445-467), so `record_id` and the on-disk filename never move under a correction.
- WR-04 guard tightened from leaf-name to EQUAL `expected_base` predicate (`store_dir.resolve() == expected_base.resolve()`), applied identically to BOTH `log_experiment` (now with a keyword-only `expected_base` param) and `update_experiment`. `expected_base` defaults to `None` → `EXPERIMENTS_DIR` resolved IN-BODY at call time (monkeypatchable).
- New `EXPERIMENTS_DIR = Path.home() / ".hermes" / "kajiba" / "experiments"` module constant, stdlib `Path` only, no `kajiba.cli` import — store stays Click-free; mirrors cli.py:70 so production default base resolves equal.

## Task Commits

1. **Task 1: update_experiment + EQUAL guard + EXPERIMENTS_DIR** - `299c5ec` (feat)

_Note: This is the GREEN half of a TDD cycle; the RED commits live in 13-01 (`test(13-01)` commits dff5f75/ac8d1cb/c0401b0)._

## Files Created/Modified
- `src/kajiba/experiment_store.py` - Added `EXPERIMENTS_DIR` constant, `update_experiment()`, EQUAL guard + keyword-only `expected_base` on both write functions.
- `tests/test_experiment_exclusion.py` - `_isolate_dirs` now also patches `experiment_store.EXPERIMENTS_DIR` (deviation Rule 1, see below).

## Decisions Made
- Kept `log_experiment`'s dedup-skip for identical re-logs; CR-01 is closed by routing corrections through `update_experiment`, not by changing `log_experiment` (D-03 / Open Question 1 / A5).
- Stated production semantics accurately: the guard tightening DOES change behavior vs the old leaf-name check (any dir merely named `experiments` used to pass; now only a dir EQUAL to the expected base passes). Production is accepted because callers pass the real store dir and fall back to the matching module default base.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-existing exclusion test broke under the tightened EQUAL guard**
- **Found during:** Task 1 (full-suite regression check)
- **Issue:** `tests/test_experiment_exclusion.py::test_experiment_absent_from_community_paths` calls `log_experiment(record, experiments)` with NO `expected_base` (production semantics). Its `_isolate_dirs` helper (authored in Phase 11) patched only `kajiba.cli.EXPERIMENTS_DIR`, not `kajiba.experiment_store.EXPERIMENTS_DIR`. After the WR-04 tightening, the guard's default base fell back to the real `~/.hermes` dir and rejected the tmp store → `ValueError`. This is the same isolation pattern 13-01 already applied to its `_isolate_store` helper; this older Phase 11 helper was missed during the 13-01 migration.
- **Fix:** Added `monkeypatch.setattr("kajiba.experiment_store.EXPERIMENTS_DIR", experiments)` to `_isolate_dirs`, matching the documented 13-01 isolation pattern, so the call-time default base resolves to the tmp store.
- **Files modified:** tests/test_experiment_exclusion.py
- **Verification:** `python -m pytest tests/test_experiment_exclusion.py -q` → 2 passed.
- **Committed in:** 299c5ec (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — test isolation broken by the in-scope guard change)
**Impact on plan:** The fix is a test-only isolation patch that restores production-faithful semantics (no `expected_base`, default base used). No source/scope creep; the guard change itself is the intended WR-04 fix.

## Issues Encountered
- The full `python -m pytest -q` run halts at a collection error in `tests/test_experiment_drift.py` (`ModuleNotFoundError: kajiba.experiment_drift`) — that module is owned by 13-03 and is RED by design. Ran the suite with `--ignore=tests/test_experiment_drift.py` to confirm the rest; the remaining 19 failures are all in `tests/test_cli_experiment.py` (the `experiment review`/`lessons`/`drift` subcommands owned by 13-04/13-05), also RED by design. No previously-passing test regressed.

## Verification
- `python -m pytest tests/test_experiment_store.py -q` → 11 passed (incl. the 4 new update tests, 3 migrated log_experiment tests, EXPERIMENTS_DIR parity, `test_refuses_outbox_dir`).
- `python -m pytest tests/test_experiment_exclusion.py -q` → 2 passed.
- `git diff --quiet src/kajiba/schema.py` → exit 0 (schema provably untouched).
- Source assertions: `update_experiment` has NO `dest.exists()` early-return (only docstring/comment mentions), calls `os.replace` and `ExperimentRecord.model_validate`; both functions guard via `store_dir.resolve() == expected_base.resolve()` with in-body `if expected_base is None` resolution; old `resolved.name` leaf-name check gone; no `kajiba.cli` import (only docstring/comment references).
- Full suite (excluding 13-03 drift collection error): 296 passed, 2 pre-existing skips; the only failures are 13-03/04/05-owned RED tests.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `update_experiment` is the funnel the 13-04/13-05 CLI subcommands (`review`/`lessons`/`drift`) write through; it is ready for them to import and re-export from `__init__.py` (re-export owned by 13-04).
- 13-03's `compute_drift` module and 13-04/05's CLI subcommands remain RED by design; no blockers introduced.

## Self-Check: PASSED

- FOUND: src/kajiba/experiment_store.py
- FOUND: .planning/phases/13-reviewer-critique-drift/13-02-SUMMARY.md
- FOUND: commit 299c5ec

---
*Phase: 13-reviewer-critique-drift*
*Completed: 2026-06-04*
