---
phase: 14-live-experiment-capture
plan: 02
subsystem: collector
tags: [collector, experiment-capture, tdd, env-trigger, hermes-hooks]

# Dependency graph
requires:
  - phase: 14-live-experiment-capture
    plan: 01
    provides: "_build_trajectory() shared helper + TestExperimentCapture six-test harness + _drive_turns lifecycle driver"
  - phase: 11-experiment-store
    provides: "build_experiment_record convenience constructor + EXPERIMENTS_DIR module attr + D-13 store guard"
  - phase: 10-experiment-schema
    provides: "ExperimentRecord family + EXPERIMENT_TYPES vocab + frozen identity hash methods"
provides:
  - "KajibaCollector experiment-mode state: _experiment_mode/_experiment_type/_task_category/_last_experiment_path"
  - "Call-time KAJIBA_EXPERIMENT/_TYPE/_CATEGORY env reads in on_session_start (per-session opt-in trigger, D-01)"
  - "_build_experiment_record(session_id) -> ExperimentRecord (D-03..D-06 field mapping, routes through build_experiment_record for SC#2 parity by construction)"
  - "experiment_store MODULE import (store dir referenced as experiment_store.EXPERIMENTS_DIR at call time, never bound)"
affects: [14-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Call-time env read (per-session opt-in) — copies the KAJIBA_DEBUG idiom but reads at on_session_start, NOT import time, so one loaded plugin serves both coding and experiment sessions"
    - "Defensive turn search (next(...) with empty-string fallback) instead of [0]/[-1] indexing — assembles cleanly when a human or gpt turn is absent (Pitfall 3)"
    - "Route record assembly through the deliberate-log constructor (build_experiment_record) so live-captured records have structural parity with kajiba experiment log by construction (SC#2)"
    - "Rich-metadata promotion (rec.experiment.local_model = self._model_metadata) before any write; write path re-validates + recomputes IDs (Pitfall 4)"

key-files:
  created: []
  modified:
    - "src/kajiba/collector.py"
    - "tests/test_collector.py"

key-decisions:
  - "Imported the experiment_store MODULE (`from kajiba import experiment_store`) plus `build_experiment_record` by name — but the store DIR is only ever referenced as `experiment_store.EXPERIMENTS_DIR` (call-time module attr), never bound, so a test monkeypatch reaches it and the D-13 guard resolves to the same dir the collector will write (per plan 03)."
  - "KAJIBA_EXPERIMENT_TYPE is validated against EXPERIMENT_TYPES with a fallback to model_evaluation (T-14-input mitigation); KAJIBA_EXPERIMENT_CATEGORY is free-form."
  - "Rewrote test_field_mapping and test_structural_parity_with_deliberate_log to exercise _build_experiment_record DIRECTLY on the buffered state (assembly), not via disk glob — disk persistence is the plan 03 finalize branch. Added a local _drive_session helper that drives on_session_start + N x on_llm_turn WITHOUT on_session_end, so the still-RED finalize tests keep their own (disk-based) coverage intact."

patterns-established:
  - "Wave 2 of the 3-wave red->green: turned exactly two RED tests green (field mapping + structural parity); the two finalize/no-staging tests stay RED by design for plan 03."

requirements-completed: []

# Metrics
duration: 2min
completed: 2026-06-07
---

# Phase 14 Plan 02: Experiment-Mode Trigger + Record Assembly Summary

**Wired the `KAJIBA_EXPERIMENT*` per-session opt-in trigger and the `_build_experiment_record()` assembly into `KajibaCollector`, mapping buffered turns to an `ExperimentRecord` via the deliberate-log constructor for SC#2 parity by construction — turning the field-mapping and structural-parity tests GREEN while the finalize/no-staging tests stay RED for plan 03.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-06-07T00:43:16Z
- **Completed:** 2026-06-07T00:45:38Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added `import os`, `from kajiba import experiment_store`, `from kajiba.experiment_store import build_experiment_record`, and `EXPERIMENT_TYPES`/`ExperimentRecord` to the `kajiba.schema` import block in `collector.py`. The store DIR is referenced only as the live module attribute `experiment_store.EXPERIMENTS_DIR` (never bound at import time), so a test `monkeypatch.setattr(experiment_store, "EXPERIMENTS_DIR", tmp)` reaches it and the call-time D-13 guard resolves to the same dir.
- Declared four new `__init__` attrs mirroring `self._finalized`: `_experiment_mode: bool = False`, `_experiment_type: str = "model_evaluation"`, `_task_category: str = "coding"`, `_last_experiment_path: Optional[Path] = None` (the last is consumed by plan 03; declared now so `__init__` is complete).
- `on_session_start` now reads `KAJIBA_EXPERIMENT`/`KAJIBA_EXPERIMENT_TYPE`/`KAJIBA_EXPERIMENT_CATEGORY` at CALL TIME (per-session semantics), validates the type against `EXPERIMENT_TYPES` (fallback `model_evaluation`, T-14-input), and resets `_last_experiment_path`. No coding-path reset line was altered.
- Added `_build_experiment_record(self, session_id) -> ExperimentRecord`: first `human` turn -> `task_description`, last `gpt` turn -> `local_model_output` (defensive `next(...)`, no `[0]`/`[-1]`), `eval_score=0.0` (D-05 placeholder), `started_at=self._created_at`, `experiment_id=f"live_{session_id}"`, and `model`/`hardware`/`trajectory` forwarded through `build_experiment_record(**extra)`. After construction it promotes `self._model_metadata` into `rec.experiment.local_model` before any write (Pattern 3 / Pitfall 4).
- Rewrote `test_field_mapping` and `test_structural_parity_with_deliberate_log` to call `_build_experiment_record` directly (assembly path) and added a local `_drive_session` helper (start + N x `on_llm_turn`, no `on_session_end`) so the disk-based finalize tests keep their distinct RED coverage.

## Task Commits

Each task was committed atomically:

1. **Task 1: experiment-mode state + module imports + call-time env reads** - `47d1d4f` (feat)
2. **Task 2: _build_experiment_record assembly + green field/parity tests** - `9bbe774` (feat)

## Files Created/Modified
- `src/kajiba/collector.py` - Added os/experiment_store/build_experiment_record/EXPERIMENT_TYPES/ExperimentRecord imports; four experiment-mode `__init__` attrs; call-time env reads in `on_session_start`; new `_build_experiment_record(session_id)` method.
- `tests/test_collector.py` - Rewrote the two target tests to exercise the assembly helper directly; added `_drive_session` (no `on_session_end`) helper.

## Decisions Made
- See key-decisions in frontmatter. The central call was redirecting the two parity/mapping tests away from disk glob (which depends on plan 03's finalize write) toward the in-memory `_build_experiment_record` assembly, exactly as the plan's Task 2 action specifies ("call the assembly, assert the D-03..D-06 mapping and parity"). The original scaffold versions globbed `exp_*.json`; those disk assertions are preserved for the still-RED finalize tests.

## Deviations from Plan

None - plan executed exactly as written. The plan's Task 2 action explicitly directs making the two tests "exercise this helper"; the scaffold (plan 01) had them globbing disk, so adapting them to call the assembly directly is the specified behavior, not a deviation.

## Threat Surface
- T-14-input (KAJIBA_EXPERIMENT_TYPE tampering): mitigated — value validated against `EXPERIMENT_TYPES`, falls back to `model_evaluation`.
- T-14-priv (write to EXPERIMENTS_DIR): not applicable to this plan — `_build_experiment_record` ASSEMBLES only and writes nothing; the never-staging/outbox structural guard is enforced by the plan 03 finalize branch (`test_no_staging_or_outbox_in_experiment_mode` remains RED here, GREEN in plan 03).

## Issues Encountered
None. The Task 1 scoped verify (`-x -k "lifecycle or ExperimentCapture"`) halts at the first plan-03 RED test (`test_opted_in_session_writes_one_record`); the coding-path lifecycle subset (`-k "lifecycle"`) passes 4/4, which is the Task 1 acceptance gate. Full suite: 469 passed / 2 skipped (pre-existing yaml soft-dep) / 2 failed — the 2 failures are exactly the plan-03 finalize tests (`test_opted_in_session_writes_one_record`, `test_no_staging_or_outbox_in_experiment_mode`), the intended RED for Wave 3. Zero regressions.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 03 can now add `_finalize_experiment(session_id)` + the early-return experiment branch at the top of `on_session_end`, using the already-assembled `_build_experiment_record` and the declared `_last_experiment_path` anchor for the self-cleaning finalize-once write via `update_experiment`. That turns the two remaining RED tests green.
- No blockers.

## Self-Check: PASSED

- FOUND: `.planning/phases/14-live-experiment-capture/14-02-SUMMARY.md`
- FOUND: commit `47d1d4f` (Task 1 feat)
- FOUND: commit `9bbe774` (Task 2 feat)
- VERIFIED: `def _build_experiment_record(self, session_id: str)` present in src/kajiba/collector.py
- VERIFIED: `from kajiba import experiment_store` present; no `from kajiba.experiment_store import EXPERIMENTS_DIR` bound-name import

---
*Phase: 14-live-experiment-capture*
*Completed: 2026-06-07*
