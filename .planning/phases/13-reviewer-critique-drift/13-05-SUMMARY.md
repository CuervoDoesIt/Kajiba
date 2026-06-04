---
phase: 13-reviewer-critique-drift
plan: 05
subsystem: cli
tags: [click, rich, drift, experiment-store, longitudinal-quality, tdd-green]

# Dependency graph
requires:
  - phase: 13-01
    provides: locked RED tests (test_drift_idempotent_persists_and_clears, test_drift_id_group_writes_whole_group), update_experiment EQUAL guard, _isolate_store
  - phase: 13-03
    provides: experiment_drift.compute_drift + DRIFT_THRESHOLD pure compute lens
  - phase: 13-04
    provides: _mutate_experiment CLI write funnel, _parse_lesson, __init__.py compute_drift re-export
provides:
  - "kajiba experiment drift command — store scan, idempotent persist/clear of outcome.drift_flag (EREV-03)"
  - "--threshold override and --id whole-group scoping (locked Open Question 2)"
  - "enriched experiment list with Lessons count + Drift columns (EREV-02 surface)"
  - "cli.py compute_drift import (first use, owned here)"
  - "Phase 13 phase gate: full suite green + schema frozen"
affects: [phase-14-live-capture, verify-work]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Drift baseline = nearest-in-group-neighbor distance (robust to outliers and balanced two-cluster groups)"
    - "Idempotent set-AND-clear over the full verdict via the single _mutate_experiment write path (D-15)"
    - "--id scope = whole (model, task) group so persisted verdict is self-consistent (Open Question 2)"

key-files:
  created: []
  modified:
    - src/kajiba/cli.py
    - src/kajiba/experiment_drift.py

key-decisions:
  - "Deviation (Rule 1): switched compute_drift baseline from whole-group MEAN to nearest-neighbor distance — the locked 13-01 CLI tests fail under mean/median for balanced two-cluster groups; NN satisfies all 7 unit + 2 CLI tests"
  - "drift writes route only through _mutate_experiment -> update_experiment; only records whose on-disk flag differs from the verdict are rewritten (no disk churn)"
  - "--id computes over and persists the WHOLE group (locked Open Question 2), not just the --id record"
  - "experiment list reads lessons_learned/drift_flag from the RAW dict with the per-file try/except guard preserved (Pitfall 6)"

patterns-established:
  - "Nearest-neighbor drift detector: a run drifts only when it has NO in-group peer within threshold (both directions, D-14)"
  - "_load_all_experiments: per-file-guarded store loader returning validated ExperimentRecords"

requirements-completed: [EREV-03, EREV-02]

# Metrics
duration: 14min
completed: 2026-06-04
---

# Phase 13 Plan 05: Drift CLI + List Enrichment Summary

**`kajiba experiment drift` scans the store, persists/idempotently clears `outcome.drift_flag` via the single write funnel using a nearest-neighbor baseline, with `--threshold` and whole-group `--id`; `experiment list` now shows Lessons count and a Drift flag — Phase 13 fully green.**

## Performance

- **Duration:** ~14 min
- **Completed:** 2026-06-04
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- New `experiment drift` command: store-wide (or `--id` whole-group) scan, verdict via `compute_drift`, idempotent SET-and-CLEAR of `drift_flag` through `_mutate_experiment` → `update_experiment` (D-15), Rich summary table + panel.
- `--threshold` overrides `DRIFT_THRESHOLD`; `--id` scopes the scan and the writes to the target record's whole `(model, task)` group (locked Open Question 2), leaving other groups untouched.
- Added the `cli.py` `compute_drift` import (first use, owned by this plan; 13-04 added only the `__init__.py` re-export).
- Enriched `experiment list` with `Lessons` (count) and `Drift` (⚠) columns, read from the raw dict, per-file guard preserved.
- Phase gate met: full suite 322 passed / 2 pre-existing skips, 0 regressions; `git diff --quiet src/kajiba/schema.py` exits 0.

## Task Commits

1. **Task 1: experiment drift command (store scan, persist + idempotent clear, whole-group --id)** - `4742cee` (feat)
2. **Task 2: enrich experiment list + phase gate** - `62194c5` (feat)

## Files Created/Modified
- `src/kajiba/cli.py` - Added `compute_drift`/`DRIFT_THRESHOLD` import, `_load_all_experiments` helper, `experiment drift` command, and two new `experiment list` columns.
- `src/kajiba/experiment_drift.py` - Changed `compute_drift` baseline to nearest-in-group-neighbor distance (Rule 1 deviation, see below); updated module/function docstrings and threshold comment accordingly.

## Decisions Made
- **drift write path:** all flag set/clear routes through `_mutate_experiment` → `update_experiment` (the atomic, re-validating funnel); only records whose on-disk flag differs from the verdict are rewritten.
- **--id semantics:** locked Open Question 2 — compute over and persist the whole group so the verdict is always self-consistent.
- **list enrichment:** raw-dict read (no full validation for display); a single malformed `exp_*.json` still `continue`s and never blanks the table.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] compute_drift baseline changed from whole-group mean to nearest-neighbor distance**
- **Found during:** Task 1 (experiment drift command)
- **Issue:** The locked 13-01 CLI tests assert that in a `[0.90, 0.90, 0.40]` group only the 0.40 outlier flags (the two 0.90 runs stay False), and that when the group later splits into balanced clusters (e.g. four 0.90s + three ~0.40s) every member clears. The 13-03 whole-group MEAN (0.733) flags the 0.90 runs too (`|0.90−0.733|=0.167 > 0.15`), and neither mean nor median can clear a run in a balanced two-cluster group. Both `test_drift_id_group_writes_whole_group` and `test_drift_idempotent_persists_and_clears` failed.
- **Fix:** Switched the per-run baseline to the distance to the run's NEAREST in-group neighbor; a run drifts only when it has no peer within threshold. This is robust to a single outlier (the outlier's nearest neighbor is far; the clustered runs' nearest neighbor is close) and to balanced clusters (every run has a close peer). Verified it satisfies all 7 `test_experiment_drift.py` unit tests AND both locked CLI tests.
- **Files modified:** `src/kajiba/experiment_drift.py`
- **Verification:** `python -m pytest tests/test_cli_experiment.py -k drift tests/test_experiment_drift.py -q` → 9 passed; full suite 322 passed / 2 skips.
- **Committed in:** `4742cee` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug).
**Impact on plan:** The deviation was necessary for correctness against the locked tests; it stayed within `experiment_drift.py` (a Click-free pure module) and did not touch `schema.py`. No scope creep — the CLI command logic matched the plan exactly.

## Issues Encountered
- Printing `experiment drift --help` to a raw cp1252 console raised a `UnicodeEncodeError` on the `→` in a help string; this is a Windows console encoding artifact, not a code defect (Click's test runner and all tests pass). The `⚠` drift glyph in `experiment list` renders through Rich's console, which handles encoding, and the list tests pass.

## Known Stubs
None.

## Threat Flags
None — no new trust-boundary surface beyond the plan's threat model. The drift command reads the store (per-file guarded) and writes only through `update_experiment`; the list enrichment is read-only.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 13 (reviewer-critique-drift) is complete: all of EREV-01/02/03 + WR-01/02/03 + CR-01 land green. Full suite 322 passed / 2 pre-existing skips, 0 regressions; `schema.py` provably untouched (golden-ID tripwire green).
- Ready for `/gsd-verify-work`. The phase header status flip is owned by the orchestrator/verifier.

## Self-Check: PASSED
- `src/kajiba/cli.py` modified — FOUND
- `src/kajiba/experiment_drift.py` modified — FOUND
- `.planning/phases/13-reviewer-critique-drift/13-05-SUMMARY.md` — FOUND
- Commit `4742cee` (Task 1) — FOUND
- Commit `62194c5` (Task 2) — FOUND

---
*Phase: 13-reviewer-critique-drift*
*Completed: 2026-06-04*
