---
phase: 13-reviewer-critique-drift
plan: 03
subsystem: testing
tags: [drift, statistics, pure-compute, eval, experiment, tdd-green]

# Dependency graph
requires:
  - phase: 13-reviewer-critique-drift (13-01)
    provides: RED scaffold tests/test_experiment_drift.py + ExperimentRecord schema fields
  - phase: 10-experiment-schema
    provides: ExperimentRecord / ExperimentMetadata / ExperimentOutcome models + compute_record_id
provides:
  - "Pure compute_drift(records, threshold=DRIFT_THRESHOLD) -> dict[str, bool]"
  - "DRIFT_THRESHOLD = 0.15 module constant (flag-overridable)"
  - "Click-free, stdlib-only experiment_drift.py compute module"
affects: [13-04, 13-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure compute module mirroring eval_scorer.py shape but verdict PERSISTED by caller (D-02)"
    - "Group-mean drift baseline with <2-run guard before any mean() call"

key-files:
  created:
    - src/kajiba/experiment_drift.py
  modified: []

key-decisions:
  - "Used whole-group-mean baseline (not leave-one-out) to satisfy the locked 13-01 RED tests"
  - "Threshold is flag-only (DRIFT_THRESHOLD constant); module never reads config.yaml (D-14)"

patterns-established:
  - "Drift compute lens: pure read-only function, verdict spans ALL records for idempotent set/clear (D-15)"

requirements-completed: [EREV-03]

# Metrics
duration: 9min
completed: 2026-06-04
---

# Phase 13 Plan 03: Experiment Drift Compute Module Summary

**Pure stdlib `compute_drift` that groups runs by (model_name, task_category), flags eval_score drift in both directions beyond DRIFT_THRESHOLD=0.15, with a <2-run guard and a verdict spanning every record for idempotent flag set/clear.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-06-04T21:10:00Z
- **Completed:** 2026-06-04T21:19:00Z
- **Tasks:** 1
- **Files modified:** 1 (created)

## Accomplishments
- New `src/kajiba/experiment_drift.py` — Click-free, stdlib-only, pure-compute module mirroring `eval_scorer.py`'s shape (module logger, `UPPER_SNAKE_CASE` threshold, single `compute_*` entrypoint).
- `compute_drift` groups by `(local_model.model_name, task_category)`, flags both regressions and improvements (D-14) beyond `threshold`, guards `<2`-run groups before any `mean()` call (no `mean([])` crash), and returns a verdict spanning ALL record_ids (D-15).
- `DRIFT_THRESHOLD = 0.15` constant, overridable via the function arg / 13-05 `--threshold` flag (flag-only, no config read).
- All 7 drift unit tests GREEN; schema.py byte-for-byte untouched; zero regressions in the rest of the suite.

## Task Commits

1. **Task 1: Create experiment_drift.py — compute_drift + DRIFT_THRESHOLD** - `2bd3530` (feat)

**Plan metadata:** (this commit) (docs: complete plan)

## Files Created/Modified
- `src/kajiba/experiment_drift.py` - Pure drift compute lens: `compute_drift` + `DRIFT_THRESHOLD`, no Click/store/schema coupling.

## Decisions Made
- **Whole-group-mean baseline over leave-one-out.** RESEARCH Pattern 3 and the plan text both described a leave-one-out baseline (mean of the OTHER runs in a group). Implementing that verbatim flagged the non-outlier runs too: in a 0.90/0.90/0.50 group, the 0.90 runs see a leave-one-out baseline of mean(0.90, 0.50)=0.70 → |0.90-0.70|=0.20 > 0.15 → flagged, which the locked 13-01 tests assert must be False. The whole-group mean (e.g. 0.7667 for that group) leaves the 0.90 runs at deviation 0.133 < 0.15 (unflagged) while still flagging the 0.50 outlier (0.267 > 0.15). Verified all 7 tests pass under group-mean for both regression and improvement directions, under-threshold, group-of-one, threshold override, verdict-coverage, and group-isolation cases. RESEARCH A1 / Discretion #4 explicitly delegate the baseline choice, so this is within sanctioned latitude.
- **Threshold flag-only.** `DRIFT_THRESHOLD` is a module constant; the module never reads `~/.hermes/config.yaml` (D-14, Discretion #3).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Baseline algorithm corrected from leave-one-out to whole-group mean**
- **Found during:** Task 1 (compute_drift implementation)
- **Issue:** The leave-one-out baseline specified in the plan/RESEARCH (mean of OTHER runs) contradicted the locked 13-01 RED tests: it flagged non-outlier runs because a single outlier contaminates each peer's leave-one-out baseline. `test_flags_regression` and `test_flags_improvement` failed (2 failed, 5 passed).
- **Fix:** Switched the baseline to the whole-group mean (`mean(eval_score across the whole group)`), which the tests' numeric assertions actually require. The `<2`-run guard, both-directions `abs`, strict `>` threshold, and verdict-over-all-records behavior are unchanged. Updated module docstring and `compute_drift` docstring to document the baseline choice and why it diverges from the RESEARCH sketch.
- **Files modified:** src/kajiba/experiment_drift.py
- **Verification:** `python -m pytest tests/test_experiment_drift.py -q` → 7 passed. Full suite: 303 passed (was 296 at 13-02 baseline, +7 drift), zero new failures outside the by-design RED CLI tests.
- **Committed in:** 2bd3530 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — algorithm/test reconciliation)
**Impact on plan:** Necessary to honor the locked RED-test contract (the GREEN target). Baseline choice was an explicit Discretion item (A1 / Discretion #4); no scope creep. Algorithm structure (grouping, threshold, both-directions, <2-run guard, verdict coverage) is exactly as the plan specified.

## Issues Encountered
- None beyond the baseline reconciliation documented above.

## Test Results
- `python -m pytest tests/test_experiment_drift.py -q` → **7 passed** (GREEN).
- `python -m pytest -q` → 303 passed, 19 failed, 2 skipped. All 19 failures are confined to `tests/test_cli_experiment.py` (the `experiment review`/`lessons`/`drift` CLI subcommands + `_parse_lesson` + WR-01/02/03 error paths) — owned by plans 13-04/13-05 and RED by design. Zero regressions vs the 13-02 baseline (296 passed; now 303 = 296 + 7 drift).
- `git diff --quiet src/kajiba/schema.py` → exit 0 (schema untouched).
- Source assertions: defines `DRIFT_THRESHOLD = 0.15` + `compute_drift`; `from statistics import mean`; no `click` / `kajiba.cli` / `kajiba.experiment_store` import; `<2`-run branch precedes any `mean(...)` call.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `compute_drift` + `DRIFT_THRESHOLD` ready for the 13-04 `__init__.py` re-export and the 13-05 `drift` CLI subcommand (which will SET/CLEAR `outcome.drift_flag` via `update_experiment`).
- CLI subcommand tests in `test_cli_experiment.py` remain RED by design until 13-04/13-05.

## Self-Check: PASSED
- FOUND: src/kajiba/experiment_drift.py
- FOUND: commit 2bd3530

---
*Phase: 13-reviewer-critique-drift*
*Completed: 2026-06-04*
