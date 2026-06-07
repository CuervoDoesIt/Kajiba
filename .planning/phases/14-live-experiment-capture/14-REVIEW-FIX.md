---
phase: 14-live-experiment-capture
fixed_at: 2026-06-06T00:00:00Z
review_path: .planning/phases/14-live-experiment-capture/14-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 14: Code Review Fix Report

**Fixed at:** 2026-06-06
**Source review:** .planning/phases/14-live-experiment-capture/14-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (WR-01..WR-04; the 4 INFO items are out of scope)
- Fixed: 4
- Skipped: 0

All fixes target `_finalize_experiment` / `_build_experiment_record` in
`src/kajiba/collector.py` (the privacy-critical, fault-tolerant experiment
write path). The D-08 privacy invariant (experiment mode never touches
STAGING_DIR/OUTBOX_DIR) and the `on_session_end` fault-tolerance boundary are
preserved. `src/kajiba/schema.py` was not modified (frozen-schema invariant).
No test was altered.

**Verification:** Full suite green via the project venv
(`.venv/Scripts/python.exe -m pytest -q`): **471 passed, 2 skipped, 0 failed**.
`tests/test_collector.py::TestExperimentCapture`: **6 passed**.

## Fixed Issues

### WR-01 / WR-02: Write-first finalize using the writer's returned authoritative path

**Files modified:** `src/kajiba/collector.py`
**Commit:** 455ba8b
**Applied fix:** Reordered `_finalize_experiment` so
`experiment_store.update_experiment(rec, experiment_store.EXPERIMENTS_DIR)` runs
BEFORE the stale-file unlink, closing the WR-01 write-failure window — a raised
write (D-13 `ValueError`, Pydantic `ValidationError`, disk error) now leaves the
previous turn's record intact instead of leaving the session with zero records.
The fix also captures the `Path` that `update_experiment` actually wrote and uses
it as the self-cleaning anchor, dropping the local `rec.compute_record_id()` +
manual `new_path` construction (WR-02). This removes the undocumented dual
record_id compute that could silently diverge from the on-disk filename. WR-01
and WR-02 were interrelated and fixed together in one atomic commit. Preserved:
the zero-turn guard, `unlink(missing_ok=True)`, and the live-module-attribute
store-dir reference required for monkeypatch reachability and the D-13 guard.

### WR-03: Skip experiment finalize when no gpt turn was captured

**Files modified:** `src/kajiba/collector.py`
**Commit:** f2033ed
**Applied fix:** Added an early-return guard in `_finalize_experiment` that
resolves the last `gpt` turn and returns (with a `logger.debug`) when it is
empty. A turns-but-no-`gpt` session (human-only, or a malformed paired-turn
path) no longer persists a junk record whose `local_model_output == ""`, which
would collide in content-addressed identity with any other empty-output session
for the same `experiment_id`/`started_at` and is indistinguishable from a genuine
empty generation. The existing zero-turn guard (`if not self._conversations`)
and `test_zero_turn_session_writes_nothing` stay green; the six ECAP-01 tests
pair human+gpt (via `_drive_turns`) so they are unaffected.

### WR-04: Lifecycle logging on the experiment finalize path

**Files modified:** `src/kajiba/collector.py`
**Commit:** b75e573
**Applied fix:** Added `logger.info("Experiment finalized for session %s -> %s",
...)` after a successful write and `logger.debug` when a stale prior-turn record
is reaped, matching the audit-trail convention of the module's other persistence
paths (`_save_to_staging`, continuous auto-submit). Uses `%s` lazy formatting,
no `print()`, per CLAUDE.md. This gives the privacy-sensitive divergent write
path an audit trail confirming whether — and where — an experiment record was
written and which prior file was reaped.

## Skipped Issues

None — all in-scope findings were fixed. The 4 INFO findings (IN-01..IN-04) were
out of scope for the `critical_warning` fix scope and were not attempted.

---

_Fixed: 2026-06-06_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
