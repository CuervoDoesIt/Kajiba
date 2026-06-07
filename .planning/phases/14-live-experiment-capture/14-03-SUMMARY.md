---
phase: 14-live-experiment-capture
plan: 03
subsystem: collector
tags: [collector, experiment-capture, tdd, finalize-once, privacy-guard, hermes-hooks]

# Dependency graph
requires:
  - phase: 14-live-experiment-capture
    plan: 02
    provides: "_build_experiment_record(session_id) + experiment-mode __init__ attrs + call-time KAJIBA_EXPERIMENT env reads + experiment_store MODULE import"
  - phase: 14-live-experiment-capture
    plan: 01
    provides: "_build_trajectory() shared helper + TestExperimentCapture six-test harness + _drive_turns turn-scoped lifecycle driver"
  - phase: 13-experiment-review
    provides: "update_experiment(record, store_dir, *, expected_base=None) overwrite-safe write path + EQUAL D-13 guard"
  - phase: 11-experiment-store
    provides: "EXPERIMENTS_DIR module attr + build_experiment_record convenience constructor"
provides:
  - "KajibaCollector._finalize_experiment(session_id): Design B self-cleaning finalize-once → exactly one content-addressed exp_*.json per opted-in session"
  - "on_session_end experiment branch (if self._experiment_mode: ...; return) placed BEFORE the contribution_mode read (D-08 privacy guard)"
  - "_last_experiment_path consumed for the self-cleaning unlink as the content id moves each turn"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Design B self-cleaning finalize-once: track _last_experiment_path, unlink the stale prior-turn file when the content id moves, then overwrite-write the latest — collapses N turn-scoped on_session_end firings into exactly ONE record despite a content-addressed filename that changes every turn"
    - "compute_record_id() BEFORE computing the destination path so the self-cleaning unlink targets the real prior file (rec.record_id is None on a freshly built record; the experiment identity includes local_model_output which moves the id each turn)"
    - "Divergent-tail branch (if self._experiment_mode: ...; return) at the TOP of on_session_end, BEFORE the contribution_mode read — structural privacy guard so experiment mode can never reach _save_to_staging / continuous auto-submit (D-08)"
    - "Store dir referenced as the LIVE module attribute experiment_store.EXPERIMENTS_DIR and passed as store_dir so it resolves EQUAL to the call-time D-13 expected_base (no ValueError, monkeypatch-isolated); update_experiment NEVER log_experiment (skip-on-exists would orphan files)"

key-files:
  created: []
  modified:
    - "src/kajiba/collector.py"

key-decisions:
  - "Added rec.compute_record_id() before computing new_path. rec.record_id is None on a freshly built record (it is computed inside update_experiment at write time), so without an explicit pre-compute the self-cleaning unlink would target exp_None.json and miss the real prior-turn files — orphaning one exp_*.json per turn (test_opted_in_session_writes_one_record asserted 3 != 1 until this was added). compute_record_id is idempotent and update_experiment recomputes it again at write time, so the on-disk filename is identical."
  - "Task 2 required no code changes: the TestExperimentCapture scaffold from plan 01 already carried the exact assertions the plan's Task 2 action specifies (test_flag_absent_unchanged_coding_path asserts session_*.json in STAGING_DIR + empty EXPERIMENTS_DIR; test_no_staging_or_outbox_in_experiment_mode forces contribution_mode=='continuous' and asserts empty STAGING/OUTBOX + one exp_*.json). The branch + finalize from Task 1 turned both GREEN. No assertions were weakened."

patterns-established:
  - "Wave 3 (FINAL) of the 3-wave red->green: turned the last two RED tests green (finalize-once + privacy isolation), completing ECAP-01."

requirements-completed: [ECAP-01]

# Metrics
duration: 4min
completed: 2026-06-07
---

# Phase 14 Plan 03: Experiment Finalize-Once + Privacy Branch Summary

**Added `_finalize_experiment(session_id)` (Design B self-cleaning finalize-once) and the `on_session_end` experiment branch that returns BEFORE the `contribution_mode` read — making an opted-in session emit exactly ONE content-addressed `exp_*.json` despite the turn-scoped `on_session_end` firing N times, while leaving the coding path byte-for-byte unchanged and structurally unreachable in experiment mode (D-07/D-08). All six ECAP-01 tests GREEN; full suite green.**

## Performance

- **Duration:** ~4 min
- **Tasks:** 2 (Task 1 implementation; Task 2 verification — scaffold assertions already final)
- **Files modified:** 1 (`src/kajiba/collector.py`)

## Accomplishments

- Added `KajibaCollector._finalize_experiment(self, session_id: str) -> None` implementing RESEARCH Pattern 2 Design B (self-cleaning overwrite-latest):
  1. `if not self._conversations: return` — Pitfall 3, a zero-turn / interrupted end writes nothing.
  2. `rec = self._build_experiment_record(session_id)` (reuses the plan-02 assembly).
  3. `rec.compute_record_id()` then `new_path = experiment_store.EXPERIMENTS_DIR / f"exp_{rec.record_id}.json"` — the LIVE module attribute, never a bound name.
  4. `if self._last_experiment_path and self._last_experiment_path != new_path: self._last_experiment_path.unlink(missing_ok=True)` — drops the stale prior-turn file as the content id moves (the experiment identity includes `local_model_output` = last gpt turn, D-03, which changes each turn).
  5. `experiment_store.update_experiment(rec, experiment_store.EXPERIMENTS_DIR)` — overwrite-safe write; the same live module attribute is passed as `store_dir` so it resolves EQUAL to the call-time D-13 `expected_base` (no ValueError, monkeypatch-isolated). NEVER `log_experiment` (skip-on-exists would orphan files).
  6. `self._last_experiment_path = new_path`.
- Inserted the divergent-tail guard as the FIRST thing in `on_session_end` after the session-id mismatch warning and BEFORE the `contribution_mode = _load_config_value(...)` read: `if self._experiment_mode: self._finalize_experiment(session_id); return`. The unconditional `return` means the coding path (staging / continuous auto-submit / `_save_to_staging`) is never reached in experiment mode (D-08, T-14-priv).
- Kept everything inside the existing outer `try/except Exception` → `logger.exception("Error in on_session_end")` so a finalize fault never propagates to Hermes (T-14-dos).
- Left every line of the existing coding path below the guard byte-for-byte unchanged (Pitfall 2 — no-regression).
- Google-style docstring on `_finalize_experiment` citing D-07/D-08/D-09 and the finalize-once rationale.

## Task Commits

1. **Task 1: _finalize_experiment (Design B) + on_session_end experiment branch** — `cac1040` (feat)
2. **Task 2: no-regression + privacy isolation** — no code change required; verification only (the plan-01 scaffold already carried the final assertions; Task 1 turned both tests GREEN).

## Files Created/Modified

- `src/kajiba/collector.py` — Added `_finalize_experiment(session_id)` (self-cleaning finalize-once) immediately before `on_session_end`; inserted the `if self._experiment_mode: ...; return` branch at the top of `on_session_end`'s try block before the `contribution_mode` read. +58 lines, 0 deletions.

## Decisions Made

- **`rec.compute_record_id()` before computing `new_path`.** On a freshly built `ExperimentRecord`, `record_id` is `None` (it is computed inside `update_experiment` at write time). Without an explicit pre-compute, `new_path` would be `exp_None.json` and the self-cleaning unlink would miss the real prior-turn files — leaving one orphan `exp_*.json` per turn (`test_opted_in_session_writes_one_record` reported `3 != 1` until this was added). `compute_record_id` is idempotent and `update_experiment` recomputes it again at write time, so the on-disk filename is byte-identical to `new_path`.
- **Task 2 was verification-only.** The `TestExperimentCapture` scaffold from plan 01 already contained the exact assertions the plan's Task 2 action describes for both privacy/regression tests. No assertions were added, removed, or weakened; Task 1's branch + finalize turned both from RED to GREEN.

## Deviations from Plan

None. The `compute_record_id()` pre-compute is the correct realization of the plan's stated requirement that `new_path` match the file `update_experiment` actually writes (the plan's `<action>` step 3 says compute the destination using `f"exp_{rec.record_id}.json"`; that requires a populated `record_id`). No structural or architectural change.

## Threat Surface

- **T-14-priv (Information Disclosure, HIGH) — mitigated.** The `if self._experiment_mode: ...; return` guard sits BEFORE the `contribution_mode` read, so experiment mode never reaches `_save_to_staging`/auto-submit. Proven by `test_no_staging_or_outbox_in_experiment_mode` (forces `contribution_mode=="continuous"`; STAGING_DIR + OUTBOX_DIR remain empty; exactly one `exp_*.json`).
- **T-14-dos (host DoS) — mitigated.** `_finalize_experiment` runs inside the existing `try/except Exception` → `logger.exception`; `unlink(missing_ok=True)` cannot raise on a missing file; never propagates to Hermes.
- **T-14-orphan (data integrity) — mitigated.** Design B self-cleaning unlink + overwrite-safe `update_experiment` (never `log_experiment`) → exactly one file. Proven by `test_opted_in_session_writes_one_record`.
- **T-14-pii (at-rest, LOW/accepted) — accept.** D-09: raw turns persisted to EXPERIMENTS_DIR at finalize; scrub later via `kajiba experiment scrub` CLI, never in the hook. Local/private store, no network.

No new threat surface beyond the phase threat model.

## Known Stubs

None. `eval_score=0.0` is a documented D-05 placeholder (the answer-quality score is supplied later via the `kajiba experiment score`/`review` CLI), not a stub that blocks the plan goal.

## Verification

- `python -m pytest tests/test_collector.py::TestExperimentCapture -x -q` → **6 passed**.
- `python -m pytest -q` → **471 passed, 2 skipped** (pre-existing PyYAML soft-dep), **0 failures** (was 469 passed / 2 failed before this plan — the 2 finalize tests are now green; `test_experiment_store.py`, `test_experiment_exclusion.py`, `test_schema_experiment.py` all green — no regression).

## Issues Encountered

- Initial run of Task 1 produced 3 `exp_*.json` files instead of 1 because `rec.record_id` is `None` before `update_experiment` runs, so the self-cleaning unlink targeted `exp_None.json`. Fixed by calling `rec.compute_record_id()` before computing `new_path` (see Decisions). Single fix attempt; resolved.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- ECAP-01 satisfied; SC#1 (bridge proof: opted-in session → one `exp_*.json`) and SC#2 (structural parity with `kajiba experiment log`) made TRUE in automated tests.
- Manual SC#1 live proof remains out-of-band per 14-VALIDATION.md (a multi-turn-then-exit Hermes v0.15.x session with `KAJIBA_EXPERIMENT=1` yields exactly one `exp_*.json` and nothing in STAGING/OUTBOX). Recommended on the DGX Spark per the Loop-B lab decision.
- Phase 14 all 3 plans complete — ready for /gsd-verify-work.
- No blockers.

## Self-Check: PASSED

- FOUND: `.planning/phases/14-live-experiment-capture/14-03-SUMMARY.md`
- FOUND: commit `cac1040` (Task 1 feat)
- VERIFIED: `def _finalize_experiment(self, session_id: str)` present in src/kajiba/collector.py
- VERIFIED: `if self._experiment_mode:` branch with unconditional `return` present in on_session_end, before the `contribution_mode` read
- VERIFIED: `experiment_store.update_experiment(` used in the finalize; `log_experiment(` NOT used there
- VERIFIED: full suite 471 passed / 2 skipped / 0 failed

---
*Phase: 14-live-experiment-capture*
*Completed: 2026-06-07*
