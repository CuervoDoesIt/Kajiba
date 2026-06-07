---
phase: 14-live-experiment-capture
reviewed: 2026-06-06T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - src/kajiba/collector.py
  - tests/test_collector.py
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: issues_found
---

# Phase 14: Code Review Report

**Reviewed:** 2026-06-06
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Reviewed the Phase 14 experiment-capture additions to `KajibaCollector`
(diff base `61f0146..HEAD`): the extracted `_build_trajectory()` helper, the new
`_build_experiment_record()` assembly, the Design-B self-cleaning
`_finalize_experiment()`, the `on_session_end` experiment branch (placed before
the `contribution_mode` read with an unconditional `return` — the D-08 privacy
guard), the call-time `KAJIBA_EXPERIMENT*` env reads in `on_session_start`, and
the `TestExperimentCapture` test class.

Overall the design is sound and the high-value invariants hold:

- **Fault tolerance** — `_finalize_experiment` is only ever called from inside
  `on_session_end`'s `try/except Exception` block, so any exception (including a
  D-13 `ValueError` from `update_experiment` or a Pydantic `ValidationError`) is
  caught and logged, never propagated to the Hermes host. Verified.
- **Privacy invariant (T-14-priv / D-08)** — the `if self._experiment_mode:`
  branch returns BEFORE the `contribution_mode` read, so the staging /
  continuous-auto-submit code that touches `STAGING_DIR`/`OUTBOX_DIR` is
  structurally unreachable in experiment mode. `_finalize_experiment` itself only
  touches `experiment_store.EXPERIMENTS_DIR`. Verified, and pinned by
  `test_no_staging_or_outbox_in_experiment_mode` (continuous mode forced).
- **Finalize-once self-cleaning** — `record_id` is content-addressed on
  `local_model_output` (the last gpt turn) which moves each turn, while
  `experiment_id`/`started_at`/`task_description` stay session-stable, so the
  prior-turn file is correctly unlinked as the id moves. The `_last_experiment_path`
  anchor is an instance attribute that survives the turn-scoped `on_session_end`
  firings (set to `None` only in the once-per-session `on_session_start`).
  Verified, and pinned by `test_opted_in_session_writes_one_record`.
- **Conventions** — `Optional[X]` used (no `X | None`), double quotes, Google
  docstrings, `%s` lazy logging, no `print()`. Compliant.

All 34 collector tests pass. No BLOCKER-class defects found. The findings below
are robustness gaps and quality issues that should be addressed but do not block
shipping.

## Warnings

### WR-01: Unlink-before-write leaves a write-failure window that can lose the session's only record

**File:** `src/kajiba/collector.py:674-681`
**Issue:** `_finalize_experiment` unlinks the prior-turn file BEFORE calling
`experiment_store.update_experiment`:

```python
if self._last_experiment_path and self._last_experiment_path != new_path:
    self._last_experiment_path.unlink(missing_ok=True)
experiment_store.update_experiment(rec, experiment_store.EXPERIMENTS_DIR)
self._last_experiment_path = new_path
```

If `update_experiment` raises (a D-13 `ValueError` from a misconfigured store
dir, a Pydantic `ValidationError` from the re-validation step, or a disk error),
the prior file has already been deleted and the new file was never written. The
exception is swallowed by `on_session_end`'s `try/except`, so the host is not
disrupted — but the session can end up with ZERO persisted records after having
had a valid one from a previous turn. This is a silent partial data-loss window
that is invisible to the user (only a logged exception). `update_experiment`
already uses an atomic temp-file + `os.replace`, so writing first and unlinking
the stale path only after a successful write would close the window.
**Fix:** Write first, then unlink the stale path:
```python
experiment_store.update_experiment(rec, experiment_store.EXPERIMENTS_DIR)
if self._last_experiment_path and self._last_experiment_path != new_path:
    self._last_experiment_path.unlink(missing_ok=True)
self._last_experiment_path = new_path
```
Because `update_experiment` overwrites in place, writing the new id first never
collides with the old file; the stale file is only ever a *different* id, so the
ordering swap is safe and removes the data-loss window.

### WR-02: `record_id` is computed twice per finalize; the local recompute can silently diverge from the on-disk filename

**File:** `src/kajiba/collector.py:667-681`
**Issue:** `_finalize_experiment` calls `rec.compute_record_id()` to derive
`new_path`, and then `experiment_store.update_experiment` independently
re-validates the record (`model_validate(model_dump(...))`) and calls
`compute_record_id()` again to derive the file it actually writes. The two ids
match TODAY only because every field in the identity payload
(`experiment_id`, `task_description`, `local_model_name`, `local_model_output`,
`started_at`) survives a `model_dump`/`model_validate` round-trip unchanged. This
is an undocumented coupling: if a future identity field is added that is mutated
or normalized during re-validation (e.g. a datetime precision change, a
default-applied field), `new_path` (used for the unlink) would point at a
different file than `update_experiment` actually writes, silently orphaning one
file per turn — the exact bug the self-cleaning logic exists to prevent. The
self-cleaning correctness depends on `update_experiment` returning the path it
wrote, but that return value is discarded.
**Fix:** Use the path `update_experiment` actually wrote instead of recomputing
it locally:
```python
written = experiment_store.update_experiment(rec, experiment_store.EXPERIMENTS_DIR)
if self._last_experiment_path and self._last_experiment_path != written:
    self._last_experiment_path.unlink(missing_ok=True)
self._last_experiment_path = written
```
This makes the anchor authoritative (sourced from the writer) and removes the
fragile dual-compute coupling. The local `rec.compute_record_id()` can then be
dropped entirely.

### WR-03: `task_description`/`local_model_output` empty-string fallback can produce a misleading or unstable record on a missing-role session

**File:** `src/kajiba/collector.py:885-890`
**Issue:** `_build_experiment_record` defensively falls back to `""` when no
`human` or no `gpt` turn exists:

```python
first_user = next((t.value for t in self._conversations if t.from_ == "human"), "")
last_gpt = next((t.value for t in reversed(self._conversations) if t.from_ == "gpt"), "")
```

`_finalize_experiment` only guards on `if not self._conversations:` — so a
session with turns but no `gpt` turn (e.g. a human-only turn captured via
`on_turn_complete`, or a malformed paired-turn path) passes the guard and writes
a record with `local_model_output == ""`. Since `record_id` is content-addressed
on `local_model_output`, an empty output collides in identity with any other
empty-output session for the same `experiment_id`/`started_at`, and persists a
record that represents no actual model output (eval_score 0.0 + empty output is
indistinguishable from a genuinely empty generation). This is captured-but-junk
data in the private store. The `_drive_turns` helper always pairs human+gpt so
no test exercises the human-only / gpt-missing path.
**Fix:** Either tighten the finalize guard to require a non-empty model output:
```python
last_gpt = next((t.value for t in reversed(self._conversations) if t.from_ == "gpt"), "")
if not last_gpt:
    logger.debug("Experiment finalize skipped: no gpt turn captured")
    return
```
or assert the precondition and add a test that drives a human-only session
through experiment-mode `on_session_end` and asserts no `exp_*.json` is written.

### WR-04: `_finalize_experiment` performs disk I/O with no success/lifecycle logging, breaking the module's logging convention

**File:** `src/kajiba/collector.py:633-681`
**Issue:** Every other persistence path in this module logs its outcome
(`_save_to_staging` logs `"Saved session to staging: %s"`; the continuous-mode
auto-submit logs `"Auto-submitted record (tier: %s)"`; `on_session_end` logs the
session-end lifecycle event). `_finalize_experiment` writes a file and unlinks a
prior file with NO `logger.info`/`logger.debug` at all. Per CLAUDE.md the
collector uses `logger.info()` for lifecycle events and the project never uses
`print()`; a privacy-sensitive divergent write path that produces no audit trail
makes it impossible to confirm from logs whether an experiment record was
written or which prior file was reaped. (`experiment_store.update_experiment`
logs `"Experiment updated in place: %s"`, but that does not cover the
collector-side unlink or the experiment-mode branch decision.)
**Fix:** Add lifecycle logging in the experiment branch / finalize, e.g.:
```python
logger.info("Experiment finalize for session %s -> %s", session_id, new_path)
```
and a `logger.debug` when a stale prior-turn file is reaped.

## Info

### IN-01: `build_experiment_record` is imported as a bound name while the store dir and writer are accessed via the module — inconsistent indirection

**File:** `src/kajiba/collector.py:17-18`
**Issue:** The code imports `from kajiba.experiment_store import build_experiment_record`
(bound name) but deliberately accesses `experiment_store.EXPERIMENTS_DIR` and
`experiment_store.update_experiment` via the module object (for monkeypatch
reachability, per the docstrings). Mixing a bound name and module-attribute
access for symbols from the same module is inconsistent and invites a future
maintainer to "tidy up" by binding the others too — which would break the test
monkeypatch isolation that the design depends on. The bound `build_experiment_record`
happens to be safe today only because no test patches it.
**Fix:** For consistency and to make the indirection intent explicit, call
`experiment_store.build_experiment_record(...)` via the module as well, and drop
the bound import (or add a comment explaining why this one symbol is bound while
the others are not).

### IN-02: `ExperimentRecord` is imported only for a type annotation

**File:** `src/kajiba/collector.py:23`
**Issue:** `ExperimentRecord` is imported from `kajiba.schema` but is used solely
as the return annotation of `_build_experiment_record`. This is correct and
necessary at runtime (it is not under `TYPE_CHECKING`), but worth noting that it
is the only purely-annotation use among the schema imports. No action strictly
required; flagged for completeness during import-graph review.
**Fix:** None required. If the project later adopts `from __future__ import annotations`,
this could move under a `TYPE_CHECKING` guard.

### IN-03: `experiment_id` includes the raw `session_id` with no sanitization, and is interpolated into a filename via `record_id`

**File:** `src/kajiba/collector.py:892` and `:671`
**Issue:** `experiment_id=f"live_{session_id}"` accepts the session id verbatim.
The id is not used directly in the filename (the filename comes from the SHA-256
`record_id`, so there is no path-traversal vector), but the raw session id flows
into the persisted record content and into the content-hash input. Since the
session id originates from the Hermes host rather than end-user free text, this
is low risk, but a session id containing control characters or newlines would be
persisted verbatim in the experiment record's `experiment_id` field. Noted as a
defensive-input observation, not an exploitable defect.
**Fix:** None required for v1. If session ids ever become user-influenced,
consider constraining `experiment_id` to a safe charset.

### IN-04: Test suite does not cover the finalize-mid-session failure path or the human-only/gpt-missing path

**File:** `tests/test_collector.py:958-1143`
**Issue:** `TestExperimentCapture` covers the happy single-record case, the
flag-absent coding path, structural parity, field mapping, the
no-staging/outbox privacy invariant, and the zero-turn guard — good coverage.
But there is no test asserting that a raised `update_experiment` (e.g. a D-13
`ValueError` from a mismatched store dir) is swallowed by `on_session_end`
without crashing (the experiment-mode analogue of
`test_fault_tolerance_scrub_raises`), and none driving a session with turns but
no gpt turn (see WR-03). Adding these would pin the fault-tolerance and
empty-output invariants that the current tests assume but do not exercise.
**Fix:** Add a fault-tolerance test that monkeypatches
`experiment_store.update_experiment` to raise and asserts `on_session_end` does
not propagate, plus a human-only-session test asserting no `exp_*.json` is
written.

---

_Reviewed: 2026-06-06_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
