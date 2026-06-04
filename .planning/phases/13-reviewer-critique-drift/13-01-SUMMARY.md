---
phase: 13-reviewer-critique-drift
plan: 01
subsystem: testing
tags: [pytest, tdd, red-scaffold, experiment-store, drift, cli, click]

# Dependency graph
requires:
  - phase: 11-experiment-store
    provides: log_experiment / build_experiment_record / experiment store + EXPERIMENTS_DIR (cli.py), D-13 structural guard
  - phase: 12-eval-confidence-scrub
    provides: _isolate_store CLI test idiom, _load_experiment store-load helper, experiment CLI group
provides:
  - RED test scaffolds locking every Phase 13 behavior contract before implementation
  - update_experiment EQUAL-predicate guard contract (accept store_dir==expected_base; reject otherwise; default base read at call time)
  - EXPERIMENTS_DIR literal-drift parity guard (cli.py vs experiment_store.py)
  - compute_drift pure-function contract (leave-one-out mean, both directions, <2-run guard, all-records verdict, group isolation)
  - review/lessons/drift CLI + _parse_lesson + WR-01/02/03 error-path contracts
  - _isolate_store extension that also isolates experiment_store.EXPERIMENTS_DIR
affects: [13-02-update-experiment, 13-03-compute-drift, 13-04-review-lessons-cli, 13-05-drift-cli]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "RED-import scaffold: tests fail at collection/import on the missing target symbol, not on syntax"
    - "EQUAL-predicate store guard locked test-first: every accept path passes store_dir==expected_base, every reject path passes store_dir!=expected_base"
    - "Default-base-at-call-time: monkeypatch experiment_store.EXPERIMENTS_DIR to assert production default path"
    - "Literal-drift parity test: assert two source-of-truth constants stay equal so CI fails fast instead of fail-closing at runtime"

key-files:
  created:
    - tests/test_experiment_drift.py
  modified:
    - tests/test_experiment_store.py
    - tests/test_cli_experiment.py

key-decisions:
  - "Migrated the 3 pre-existing log_experiment tests to pass expected_base=store; they are RED now (TypeError: unexpected kwarg) and go GREEN once 13-02 adds the param — exactly the plan's intent (their GREEN is verified by 13-02's full-suite check, not this RED plan)."
  - "Used monkeypatch.setattr(..., raising=False) for kajiba.experiment_store.EXPERIMENTS_DIR in _isolate_store so existing CLI tests don't break at setup time before 13-02 adds the constant."
  - "Strengthened test_missing_record_kind_friendly to require a NON-EMPTY user-facing message (today the load crashes with an unhandled ValidationError → empty output), making WR-02 RED for the right reason instead of passing on the existing silent-exit behavior."

patterns-established:
  - "Pure-compute drift tests build records via a local _make_record varying model_name/task_category/eval_score with distinct started_at so record_id differs."
  - "CLI drift groups seeded directly via log_experiment (_drift_record helper) rather than the RED review/lessons subcommands, so drift tests don't depend on other unbuilt commands."

requirements-completed: [EREV-01, EREV-02, EREV-03]

# Metrics
duration: 18min
completed: 2026-06-04
---

# Phase 13 Plan 01: Wave 0 RED Test Scaffolds Summary

**RED test scaffolds locking all Phase 13 contracts — update_experiment EQUAL-guard + EXPERIMENTS_DIR parity, pure compute_drift (both-directions/<2-run/all-records/group-isolation), and review/lessons/drift CLI + WR error paths — all failing for missing implementation, schema.py untouched.**

## Performance

- **Duration:** ~18 min
- **Completed:** 2026-06-04
- **Tasks:** 3
- **Files modified:** 3 (1 created, 2 extended)

## Accomplishments
- New `tests/test_experiment_drift.py` with 7 pure `compute_drift` tests (regression + improvement flag, under-threshold no-flag, single-run guard, threshold override, all-records verdict, group isolation) — RED on `ModuleNotFoundError: kajiba.experiment_drift`.
- `tests/test_experiment_store.py`: 5 new RED tests using the EQUAL guard shape (overwrite-in-place, identity-stable, dir-outside-base reject, production-shape default-base accept+reject, EXPERIMENTS_DIR cli/store parity) + migration of the 3 pre-existing `log_experiment` tests to pass `expected_base=store`.
- `tests/test_cli_experiment.py`: 19 new RED tests (review set/replace/reviewer-model/action/from-txt/from-json/interactive; lessons add/read/filter/cross-record + 3 `_parse_lesson` units; drift idempotent persist+clear and whole-group `--id` write+clear; WR-01/02/03 error paths) + `_isolate_store` extended to also patch `experiment_store.EXPERIMENTS_DIR`.
- Pre-existing suite stays green (10/10 prior CLI tests pass; 275 passed + 2 skipped across all other files); `git diff --quiet src/kajiba/schema.py` exits 0.

## Task Commits

1. **Task 1: Extend test_experiment_store.py (update_experiment + parity, migrate log_experiment)** - `a45cedd` (test)
2. **Task 2: New test_experiment_drift.py (pure compute_drift)** - `dff5f75` (test)
3. **Task 3: Extend test_cli_experiment.py (review/lessons/drift/WR + _parse_lesson)** - `ac8d1cb` (test)

## Files Created/Modified
- `tests/test_experiment_drift.py` - NEW: 7 pure compute_drift unit tests, RED on missing module.
- `tests/test_experiment_store.py` - +5 RED update_experiment/parity tests; 3 log_experiment tests migrated to expected_base=store; test_refuses_outbox_dir gains an explicit-base reject assertion.
- `tests/test_cli_experiment.py` - +19 RED review/lessons/drift/WR/_parse_lesson tests; _isolate_store also isolates experiment_store.EXPERIMENTS_DIR.

## RED Verification (this is the success state for a Wave 0 plan)
- `tests/test_experiment_drift.py` — collection ERROR: `ModuleNotFoundError: No module named 'kajiba.experiment_drift'` (names the missing target — correct RED).
- `test_experiment_store.py` 5 new tests — `ImportError`/`AttributeError` on `update_experiment` / `experiment_store.EXPERIMENTS_DIR` (correct RED). The 3 migrated `log_experiment` tests are RED now with `TypeError: unexpected keyword argument 'expected_base'` and go GREEN once 13-02 adds the param (verified by 13-02's full-suite check, per plan).
- `test_cli_experiment.py` 19 new tests — fail on missing `review`/`lessons`/`drift` subcommands, missing `_parse_lesson` import, and unimplemented WR fixes; 10 pre-existing CLI tests still PASS.
- All other test files: 275 passed, 2 pre-existing skips, 0 regressions.
- `git diff --quiet src/kajiba/schema.py` exits 0 (schema frozen).
- No test references a real `~/.hermes` path — store dirs are tmp_path-scoped; default-base test monkeypatches the store constant; parity test compares only source-of-truth literals.

## Decisions Made
- Migrated `log_experiment` tests pass `expected_base=store` and are intentionally RED now (TypeError) → GREEN post-13-02. This is the plan's locked behavior, not a defect.
- `_isolate_store` uses `raising=False` when patching `experiment_store.EXPERIMENTS_DIR` (constant doesn't exist until 13-02) so the 10 existing CLI tests don't break at fixture setup.
- Strengthened `test_missing_record_kind_friendly`: asserts a non-empty user-facing message and no leaked exception, because the EXISTING code already exits non-zero (with empty output + an unhandled ValidationError swallowed by Click) — the weaker "no traceback / non-zero" form would have passed pre-implementation and not been RED.

## Deviations from Plan
None - plan executed exactly as written. The three notes above are clarifications of plan-specified behavior (migrated-tests-RED-now, raising=False isolation) and a within-scope test strengthening to keep WR-02 genuinely RED.

## Issues Encountered
- `test_missing_record_kind_friendly` initially PASSED against current code (existing `experiment log --from` already exits non-zero without printing a traceback). Resolved by asserting the WR-02 contract more precisely (a friendly non-empty message must be shown), so it is RED until 13-04 wraps the load in try/except ValidationError.

## Next Phase Readiness
- All Phase 13 behavior contracts are locked by failing automated tests (the Nyquist gate from 13-VALIDATION.md is satisfied).
- 13-02 turns the store tests GREEN by adding `update_experiment` + `experiment_store.EXPERIMENTS_DIR` and the `expected_base` param on `log_experiment` (EQUAL predicate, default base read at call time).
- 13-03 turns drift unit tests GREEN by adding `kajiba.experiment_drift.compute_drift` + `DRIFT_THRESHOLD = 0.15`.
- 13-04/13-05 turn CLI tests GREEN via the `review`/`lessons`/`drift` Click commands, `_parse_lesson`, and the WR-01/02/03 fixes.

---
*Phase: 13-reviewer-critique-drift*
*Completed: 2026-06-04*

## Self-Check: PASSED
- All 4 files exist (3 tests + SUMMARY).
- All 3 task commits present in history (a45cedd, dff5f75, ac8d1cb).
