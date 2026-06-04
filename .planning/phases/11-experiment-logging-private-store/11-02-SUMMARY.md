---
phase: 11-experiment-logging-private-store
plan: 02
subsystem: cli
tags: [experiment-logging, cli, click, rich, dual-use, private-store, elog-01]

# Dependency graph
requires:
  - phase: 11-experiment-logging-private-store
    plan: 01
    provides: "log_experiment(record, store_dir), build_experiment_record(**fields), EXPERIMENTS_DIR (cli.py), tests/fixtures/experiment_run.example.json"
  - phase: 10-experiment-schema-foundation
    provides: "ExperimentRecord, EXPERIMENT_TYPES, load_record() dispatch"
provides:
  - "kajiba experiment Click group (log + list subcommands)"
  - "experiment log: --from file-first input, scalar override flags, interactive Rich fallback — all via the single log_experiment write path (D-08)"
  - "experiment list: read-back Rich table over the private store"
affects: [11-03-publish-exclusion-guard, experiment-logging]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Three-mode log command (file-first --from / scalar flags / interactive) converging on one write path"
    - "Scalar overrides applied to the raw dict BEFORE validation (mutate-then-validate; models have no validate_assignment) (D-11)"
    - "load_record dispatch + isinstance(ExperimentRecord) guard rejecting non-experiment files via click.ClickException (D-10, Pitfall 1)"

key-files:
  created:
    - tests/test_cli_experiment.py
  modified:
    - src/kajiba/cli.py

key-decisions:
  - "Prompt order for the interactive fallback fixed as: experiment_id, task_category, task_description, eval_score, experiment_type, local_model.model_name, local_model_output — only the minimal required fields incl. one nested ModelMetadata field (Pitfall 3), not all nine"
  - "--local-model accepts a JSON snippet of ModelMetadata fields; in --from mode it merges into experiment.local_model, in flag/interactive mode it supplies model_name"
  - "list reads each exp_*.json via json.loads (not full Pydantic load) for a lightweight read-back table"

requirements-completed: [ELOG-01]

# Metrics
duration: 2min
completed: 2026-06-04
---

# Phase 11 Plan 02: Experiment CLI Surface Summary

**The `kajiba experiment` Click group with `log` (file-first `--from`, scalar override flags, and an interactive Rich fallback) and `list` read-back — every write funneled through `experiment_store.log_experiment`, non-experiment files rejected, all four CLI tests green.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-06-04T02:30:40Z
- **Completed:** 2026-06-04T02:32:40Z
- **Tasks:** 2
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments
- `tests/test_cli_experiment.py`: four CLI behavior tests (test_log_from_file, test_log_scalar_overrides, test_log_interactive, test_list) isolating the store via `monkeypatch.setattr("kajiba.cli.EXPERIMENTS_DIR", tmp_path / "experiments")` + `KAJIBA_BASE` so nothing touches the real `~/.hermes` (Pitfall 2).
- `kajiba experiment log`:
  - **--from** path loads JSON, applies scalar overrides to the raw dict before validation (D-11), validates via `load_record` (NOT `validate_record`, Pitfall 1), and rejects any non-`model_experiment` record with a clear `click.ClickException` (D-10, threat T-11-05).
  - **scalar-flag** path builds via `build_experiment_record(**fields)` when `--score`/`--type`/`--task-category` are present (D-11).
  - **interactive** fallback prompts the minimal essential fields plus the single required nested `local_model.model_name` (D-12, Pitfall 3) — does not field-by-field prompt all nine ModelMetadata fields.
  - All three modes call `log_experiment(rec, EXPERIMENTS_DIR)` only — the CLI never writes the file itself (D-08, threat T-11-06) — and print a Rich success panel containing the written `exp_<id>.json` path.
- `kajiba experiment list`: globs `EXPERIMENTS_DIR.glob("exp_*.json")` by mtime descending into a Rich table (Record ID / Type / Task / Score), or prints "No experiments logged." when empty.
- Full suite: 274 passed, 2 pre-existing yaml-soft-dep skips (was 270 + 2) — no regressions.

## Task Commits

Each task committed atomically (TDD: RED → GREEN):

1. **Task 1: Wave-0 failing CLI test stubs (ELOG-01)** - `f7c7b91` (test)
2. **Task 2: experiment group + log + list subcommands** - `4b2dc5f` (feat)

## Files Created/Modified
- `tests/test_cli_experiment.py` - New CLI test file; four functions named exactly per 11-VALIDATION.md, store isolated per-test, scripted `input=` for the interactive path, written JSON read back with `json.loads`.
- `src/kajiba/cli.py` - Extended the `kajiba.schema` import with `EXPERIMENT_TYPES, ExperimentRecord, load_record`; added `from kajiba.experiment_store import build_experiment_record, log_experiment`; added the `experiment` group with `log` and `list` commands.

## Decisions Made
- **Interactive prompt order locked** (experiment_id → task_category → task_description → eval_score → experiment_type → local_model.model_name → local_model_output) so the scripted-input test and the command stay in lockstep.
- **list does a lightweight json.loads read** rather than a full Pydantic round-trip — list is a confirmation read-back, not a validation gate; the data was already validated at log time.
- Followed plan task order and the TDD gate sequence exactly (test → feat).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None. Git emitted expected LF→CRLF warnings on Windows (cosmetic, no impact).

## TDD Gate Compliance
- RED gate: `f7c7b91` is a `test(11-02)` commit; all four tests failed (`No such command 'experiment'`) before implementation, as expected.
- GREEN gate: `4b2dc5f` is a `feat(11-02)` commit adding the `experiment` group; all four tests pass, full suite green.
- No REFACTOR commit needed (implementation was clean on first pass).

## Threat Surface Notes
- T-11-05 (hostile --from JSON) mitigated: `json.loads` (no eval) + `load_record` Pydantic validation; overrides applied to the raw dict before validation so eval_score bound [0,1] and EXPERIMENT_TYPES vocab are enforced; non-experiment records rejected with a `click.ClickException`.
- T-11-06 (write outside private store) mitigated: the CLI only calls `log_experiment(rec, EXPERIMENTS_DIR)`; the store's D-13 structural guard refuses any non-`experiments` dir.
- No new security surface introduced beyond the plan's threat register. No external packages installed (T-11-SC N/A).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- 11-03 (publish exclusion guard) can proceed: the CLI surface is complete and the structural store separation holds. The active `record_kind == "model_experiment"` skip in `publish` remains for 11-03.
- No blockers.

## Self-Check: PASSED

All created/modified files verified present (tests/test_cli_experiment.py, src/kajiba/cli.py, 11-02-SUMMARY.md) and both task commits (f7c7b91, 4b2dc5f) exist in git history.

---
*Phase: 11-experiment-logging-private-store*
*Completed: 2026-06-04*
