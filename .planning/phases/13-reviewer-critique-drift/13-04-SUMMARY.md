---
phase: 13-reviewer-critique-drift
plan: 04
subsystem: cli
tags: [cli, experiment, review, lessons, error-handling, tdd-green]
requires: ["13-01", "13-02", "13-03"]
provides:
  - "kajiba experiment review command (EREV-01)"
  - "kajiba experiment lessons command (EREV-02)"
  - "cli._mutate_experiment / _parse_lesson / _read_critique_input helpers"
  - "WR-01/02/03 friendly error handling in experiment log"
  - "update_experiment + compute_drift re-exported from kajiba/__init__.py"
affects:
  - src/kajiba/cli.py
  - src/kajiba/__init__.py
tech-stack:
  added: []
  patterns:
    - "Single CLI write funnel (_mutate_experiment -> update_experiment, D-03/CR-01)"
    - "str.partition(':') first-colon lesson parse (preserves colons in text)"
    - "Friendly ClickException over raw ValidationError/JSONDecodeError"
key-files:
  created: []
  modified:
    - src/kajiba/cli.py
    - src/kajiba/__init__.py
decisions:
  - "WR-02: a --from fragment missing record_kind raises a friendly ClickException naming the field (NOT silent default-inject) — required by test_missing_record_kind_friendly case (1) which asserts exit_code != 0"
metrics:
  duration: ~14m
  completed: 2026-06-04
  tasks: 2
  files: 2
---

# Phase 13 Plan 04: Experiment Review + Lessons CLI Summary

Added the `kajiba experiment review` (EREV-01) and `kajiba experiment lessons` (EREV-02) subcommands plus their shared helpers, routed every write through the 13-02 `update_experiment` single write path, re-exported the new store/drift functions from the package, and swept the WR-01/02/03 friendly-error fixes in `experiment log` — turning 17 RED tests GREEN (320 passed) with the 2 13-05 drift CLI tests still RED by design and `schema.py` byte-for-byte untouched.

## What Was Built

**Task 1 — Shared helpers + re-exports (commit 868099f):**
- `cli.py`: added `_mutate_experiment(record_id, mutate)` (the CLI-side single write funnel, D-03/CR-01 — loads via path-safe `_load_experiment`, mutates in place, persists via `update_experiment`), `_parse_lesson(lesson) -> (category, text)` (first-colon `str.partition`, lowercased category, `uncategorized` fallback, colons-in-text preserved), and `_read_critique_input(critique, from_path) -> str` (precedence `--critique` > `--from` .txt/.json > interactive stdin paste, offline; WR-03 JSON idiom).
- Added `UNCATEGORIZED = "uncategorized"` constant; imports `sys`, `Callable`, `pydantic.ValidationError`, `ModelMetadata`, `RECOMMENDED_ACTIONS`, `update_experiment`. Did NOT add a `compute_drift` import to `cli.py` (that is 13-05's, where it is first used).
- `__init__.py`: re-exported `update_experiment` and `compute_drift`.

**Task 2 — review + lessons commands + WR fixes (commit 3cae4c7):**
- `experiment review <id>` — flags `--critique`, `--from`, `--reviewer-model`, `--action` (`click.Choice(RECOMMENDED_ACTIONS)`); sets `outcome.reviewer_critique` (replace, D-07), conditional `experiment.reviewer_model = ModelMetadata(...)` (D-05) and `outcome.recommended_action` (D-06); all via `_mutate_experiment`.
- `experiment lessons [<id>]` — `--add` (repeatable), `--category`; three modes: add (`"category: text"` or raw via `_mutate_experiment`), read (filtered by category), and cross-record query (`--category` no id, per-file-guarded store glob, D-11).
- WR-03: each `json.loads` in `experiment_log` wrapped → "Malformed JSON in ..." ClickException.
- WR-02: missing `record_kind` fragment → friendly ClickException naming the field; `load_record` wrapped in `try/except ValidationError` so any incomplete fragment yields a friendly error (no raw traceback).
- WR-01: partial scalar flags (some-but-not-all of `--score`/`--type`/`--task-category`, no `--from`) → friendly ClickException listing the missing flags instead of silently dropping into the interactive prompt.

## Deviations from Plan

### 1. [Rule 1 - Bug] WR-02 missing record_kind: friendly-error, not silent default-inject

- **Found during:** Task 2 verification — `test_missing_record_kind_friendly` case (1) failed (exit_code 0 != expected non-zero).
- **Issue:** The plan's `<action>` specified `data.setdefault("record_kind", "model_experiment")` so a fragment missing `record_kind` would route to `ExperimentRecord` and validate. But the LOCKED 13-01 test asserts `exit_code != 0` for an otherwise-valid fixture with `record_kind` removed — i.e. a missing `record_kind` must be a friendly ERROR, not a silent success.
- **Fix:** Replaced the setdefault with an explicit pre-load guard: if `record_kind` is absent, raise a friendly `click.ClickException` naming the missing field. The `try/except ValidationError` wrap (WR-02 part 2) is retained for incomplete/malformed fragments. The locked test is authoritative over the plan's specified idiom (plan note: "delegate baseline/idiom choice to executor where tests disagree").
- **Files modified:** src/kajiba/cli.py
- **Commit:** 3cae4c7

## Verification

- `python -m pytest tests/test_cli_experiment.py -k "review or lessons or parse_lesson or partial_flags or missing_record_kind or malformed_json" -q` — all GREEN.
- `python -c "import kajiba; kajiba.update_experiment; kajiba.compute_drift"` — succeeds.
- `python -m pytest -q` — 320 passed, 2 skipped (pre-existing yaml soft-dep), 2 failed = ONLY `test_drift_idempotent_persists_and_clears` + `test_drift_id_group_writes_whole_group` (13-05's drift CLI subcommand, RED by design). 0 regressions vs the 303-passing baseline (+17 newly green).
- `git diff --quiet src/kajiba/schema.py` — exits 0 (schema untouched).

## TDD Gate Compliance

This is a Wave 3 GREEN plan: the RED tests were authored by 13-01. Per-task commits are `feat(...)` (the implementation turning existing tests GREEN); no new `test(...)` commit is expected in this plan. RED→GREEN transition confirmed: 19 failing before → 2 failing after (the 2 remaining belong to 13-05).

## Known Stubs

None. All review/lessons input/read/filter/cross-record modes are fully wired through the real store write path; no placeholder data sources.

## Self-Check: PASSED

- SUMMARY.md present
- Commits 868099f, 3cae4c7 in history
- cli.py defines _parse_lesson + experiment_review
