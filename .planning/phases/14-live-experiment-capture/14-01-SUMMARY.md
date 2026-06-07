---
phase: 14-live-experiment-capture
plan: 01
subsystem: testing
tags: [collector, experiment-store, tdd, pytest, hermes-hooks]

# Dependency graph
requires:
  - phase: 11-experiment-store
    provides: "experiment_store.update_experiment / build_experiment_record / EXPERIMENTS_DIR + D-13 store guard"
  - phase: 07-turn-capture
    provides: "collector.on_llm_turn (v0.15.x post_llm_call paired-turn entry point) + finalize-once on_session_end"
provides:
  - "TestExperimentCapture (six RED ECAP-01 tests) — the verification harness for the plan 02-03 implementation"
  - "_build_trajectory() shared helper on KajibaCollector — one trajectory assembly for coding + experiment paths"
  - "_drive_turns test helper — on_session_start -> N x (on_llm_turn + on_session_end) turn-scoped finalize driver"
affects: [14-02, 14-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Extract-in-place shared sub-assembly (_build_trajectory) to guarantee structural parity by construction"
    - "SINGLE store-dir monkeypatch target (experiment_store.EXPERIMENTS_DIR) so the call-time D-13 guard resolves to the same tmp dir the collector writes"

key-files:
  created: []
  modified:
    - "src/kajiba/collector.py"
    - "tests/test_collector.py"

key-decisions:
  - "Extracted _build_trajectory() verbatim from _build_record as a non-breaking refactor (byte-identical Trajectory) before any experiment wiring, so plan 02 reuses the exact coding trajectory shape (SC#2 parity by construction)."
  - "Tests isolate the store with a SINGLE monkeypatch target (experiment_store.EXPERIMENTS_DIR); STAGING_DIR/OUTBOX_DIR patched on the collector module — matches the call-time D-13 guard and the module-attr finalize use-site."
  - "_drive_turns drives on_llm_turn (v0.15.x turn entry point), NOT on_turn_complete, reproducing the turn-scoped on_session_end finalize-once scenario."

patterns-established:
  - "RED-baseline-first: six exactly-named ECAP-01 tests written ahead of implementation; they collect cleanly and fail pending plans 02-03."
  - "Parity assertion: compare live model_dump(by_alias=True) top-level + nested experiment/outcome keys against a direct build_experiment_record, permitting populated trajectory + eval_score==0.0."

requirements-completed: []

# Metrics
duration: 3min
completed: 2026-06-07
---

# Phase 14 Plan 01: Live Experiment Capture Wave 0 Foundation Summary

**Extracted `_build_trajectory()` as a non-breaking shared helper and landed the six RED `TestExperimentCapture` tests (ECAP-01) that form the verification harness for the plan 02-03 live-capture implementation.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-06-07T00:35:07Z
- **Completed:** 2026-06-07T00:38:13Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Extracted the trajectory-assembly block from `_build_record` into `KajibaCollector._build_trajectory()` — byte-identical Trajectory, `_build_record` now calls `self._build_trajectory()`. This is the shared sub-assembly both the coding and experiment finalize paths will use, guaranteeing SC#2 structural parity by construction.
- Added `TestExperimentCapture` with all six exactly-named ECAP-01 methods, a `_drive_turns` lifecycle helper (`on_session_start` -> N x (`on_llm_turn` + `on_session_end`)), and a parity helper comparing `model_dump(by_alias=True)` shape against a direct `build_experiment_record`.
- Isolation uses the SINGLE `experiment_store.EXPERIMENTS_DIR` monkeypatch target so the call-time D-13 guard inside `update_experiment` resolves to the same tmp dir the collector will write to (no ValueError once implementation lands); `STAGING_DIR`/`OUTBOX_DIR` patched on the collector module.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract _build_trajectory() shared helper** - `40d6ab6` (refactor)
2. **Task 2: Scaffold TestExperimentCapture (six ECAP-01 tests, RED)** - `97021a1` (test)

_Note: Task 2 is the TDD RED gate; GREEN lands in plans 02-03._

## Files Created/Modified
- `src/kajiba/collector.py` - Added `_build_trajectory()` method; `_build_record` now delegates to it (behavior identical).
- `tests/test_collector.py` - Added `from kajiba import collector as collector_mod` + `experiment_store` + `build_experiment_record` imports, the module-level `_drive_turns` helper, and the `TestExperimentCapture` class with six ECAP-01 methods.

## Decisions Made
- Followed the plan as specified. The `_build_trajectory()` extraction is a pure refactor-in-place; the six tests assert the intended (not-yet-implemented) behavior and are intentionally RED.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None. Note on the RED baseline observed in this environment: running the six tests yields **4 failed, 2 passed**. The 2 passing are the no-op / no-regression safety cases (`test_flag_absent_unchanged_coding_path`, which exercises the already-working coding path, and `test_zero_turn_session_writes_nothing`, which holds trivially because no experiment write path exists yet). The 4 failing tests are the behaviors that require the plan 02-03 implementation. The plan's authoritative scoped verify is `--collect-only` (six collected) — that passed. A full `pytest -q` will show these as the intended RED baseline, not a regression.

`test_no_staging_or_outbox_in_experiment_mode` is notable: with `KAJIBA_EXPERIMENT=1` set but no `_experiment_mode` branch yet, the collector falls through to the coding path and (under forced continuous mode) writes to the outbox — exactly the leak the test guards against. It will go green when plan 02-03 adds the early-return finalize branch (T-14-priv mitigation).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The verification harness is in place and collecting cleanly; plan 02 can implement `_build_experiment_record` + the `_experiment_mode` env read + finalize branch, then plan 03 the finalize-once `_finalize_experiment`, turning the four RED tests green.
- `_build_trajectory()` is ready to be reused verbatim by `_build_experiment_record` (D-06 trajectory population).
- No blockers.

## Self-Check: PASSED

- FOUND: `.planning/phases/14-live-experiment-capture/14-01-SUMMARY.md`
- FOUND: commit `40d6ab6` (Task 1 refactor)
- FOUND: commit `97021a1` (Task 2 test RED)

---
*Phase: 14-live-experiment-capture*
*Completed: 2026-06-07*
