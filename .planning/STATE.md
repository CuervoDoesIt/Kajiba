---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Hermes Pipeline Validation
status: executing
stopped_at: Completed 11-03-PLAN.md (final plan of Phase 11)
last_updated: "2026-06-04T08:53:44.637Z"
last_activity: 2026-06-04
progress:
  total_phases: 3
  completed_phases: 2
  total_plans: 6
  completed_plans: 6
  percent: 67
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-02)

**Core value:** Real-world AI session data, tagged with full runtime context, flowing into a community dataset that accelerates local model fine-tuning for everyone.
**Current focus:** Phase 11 — experiment-logging-private-store
**Parallel milestone:** v1.2 Experiment Logging (Dual-Use), Phases 10-15 — recommended start: Phase 10 (schema, v1.1-independent). See `.planning/seeds/v1.2-experiment-logging.md`.

## Current Position

Phase: 11
Plan: Not started
Status: Executing Phase 11 (11-01, 11-02, 11-03 complete)
Last activity: 2026-06-04

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**

- Total plans completed: 19 (v1.0)
- Average duration: --
- Total execution time: --

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1-5 (v1.0) | 13/13 | -- | -- |
| 10 | 3 | - | - |
| 11 | 3 | - | - |

**Recent Trend:**

- Last 5 plans: --
- Trend: Starting new milestone

*Updated after each plan completion*

## Accumulated Context

### Decisions

- Hermes 3 8B Q4 for data collection, Llama 3.2 3B for fine-tuning target
- HITL-heavy approach -- manual verification at every pipeline step
- GLiNER for semantic PII scrubbing (not Presidio/spaCy or generative LLM prompting)
- WSL2 required on Windows for Hermes Agent
- Plugin rewrite is greenfield (current Protocol-based integration is wrong)
- Scrubbing deferred to CLI step, never in hook callbacks (avoid blocking Hermes event loop)
- Dual-use decided 2026-06-03 (`/gsd-explore`): experiment/eval logging → parallel v1.2 milestone (Phases 10-15), separate `ExperimentRecord` on shared base, private/no-publish, shared core + divergent tail. v1.1 left intact; Phases 6-7 are shared foundation for v1.2 live capture (Phase 14).
- 10-01: ESCH-04 golden baseline (`tests/fixtures/golden_ids.json`) captured from pre-refactor schema over the 5 `*_trajectory.json` fixtures and committed BEFORE any schema edit; `enriched_catalog.json` excluded (no trajectory). Stored as committed JSON (not hardcoded constants); `minimal_trajectory.json` → `kajiba_c2eac32fcdc4`. `schema.py` untouched.
- 10-02: Extracted `RecordBase`; reparented `KajibaRecord(RecordBase)` with hash methods frozen — all 5 golden record_id/submission_hash byte-identical (ESCH-04 confirmed). Added `ExperimentRecord` family + `load_record()` manual factory (no discriminated union). `SCHEMA_VERSION` bumped 0.1.0→0.2.0. Experiment-id format LOCKED: `kajiba_exp_<12hex>` over experiment-identity payload with `started_at.isoformat()`. `validate_record`/`ConversationTurn` unchanged. ESCH-01/02/03/05 done.
- 11-01: Built the experiment-store persistence foundation. New `src/kajiba/experiment_store.py` (Click-free, single-responsibility, D-05) owns the only write path: `log_experiment(record, store_dir)` computes identity via the frozen Phase 10 methods, writes one flat `exp_<record_id>.json` atomically (`tempfile.mkstemp` + `os.replace`, cleanup on `BaseException`), dedups skip-with-notice (D-01/D-02), and enforces a D-13 structural guard (`store_dir.resolve().name != "experiments"` → ValueError). `build_experiment_record(**fields)` is a keyword-only constructor (D-06). `EXPERIMENTS_DIR = KAJIBA_BASE / "experiments"` added to `cli.py` + `_ensure_dirs()` (D-03, no new `~/.hermes` literal); package re-exports added to `__init__.py` (D-07). Decision: `store_dir` is an argument (not a constant baked into the store) so the module stays Click-free and test-isolatable. ELOG-02 complete; ELOG-03 structural half done (active publish guard still pending 11-03). Full suite 270 passed / 2 pre-existing skips, 0 regressions. Commits: test 0b57f65, feat 0be30da, feat 1255a07.
- 11-02: Added the `kajiba experiment` CLI surface (ELOG-01). New `experiment` Click group with `log` + `list`. `experiment log` has three input modes — `--from FILE` (load JSON, apply scalar overrides to the raw dict BEFORE validation per D-11, validate via `load_record` NOT `validate_record` per Pitfall 1, reject non-`model_experiment` with `click.ClickException`), scalar flags (`--score`/`--type`/`--task-category`/`--local-model` → `build_experiment_record`), and an interactive Rich fallback (prompts experiment_id/task_category/task_description/eval_score/experiment_type/local_model.model_name/local_model_output — minimal nested field only, Pitfall 3). All three modes funnel through `log_experiment(rec, EXPERIMENTS_DIR)` (D-08, CLI never writes the file). `experiment list` globs `exp_*.json` into a Rich table read-back. Decision: interactive prompt order locked to match the scripted-input test; list uses lightweight `json.loads` (data already validated at log time). Full suite 274 passed / 2 pre-existing skips, 0 regressions. Commits: test f7c7b91, feat 4b2dc5f.
- 11-03: Closed the active half of ELOG-03 (publish exclusion guard + D-14 regression). `publish` Step 4 loop now skips any outbox record whose raw-dict `record_kind == "model_experiment"` BEFORE `validate_record` (Pitfall 1 / T-11-10), printing `Skipping experiment record (never published): <name>` and `continue` — defense in depth over the structural `OUTBOX_DIR`/`EXPERIMENTS_DIR` split from 11-01 (T-11-08, D-13). `submit` gained a defensive `model_experiment` `click.ClickException` (T-11-09, Assumption A2 — structurally unreachable today, single guard not dead branching). New `tests/test_experiment_exclusion.py`: `test_publish_skips_experiment` (misplaced experiment in outbox skipped, network-free via a `GitHubOps` stub whose `check_auth` passes so the guard loop is reached but no PR opens) + `test_experiment_absent_from_community_paths` (D-14: real `log_experiment` write proven absent from outbox glob, byte-identical on disk, never in publish output). Full suite 276 passed / 2 pre-existing yaml-soft-dep skips, 0 regressions. ELOG-03 fully satisfied. Phase 11 ready for /gsd-verify-work (phase header owned by orchestrator). Commits: test c43d63f, feat 5610028.
- 10-03: Authored `tests/test_schema_backcompat.py` (parametrized golden-ID tripwire over all 5 fixtures + legacy-load + record_kind default + base inheritance + load dispatch) and `tests/test_schema_experiment.py` (round-trip equality + vocab rejection + recommended_action=None + lessons_learned=[] + eval_score bounds). Schema untouched (`git diff --quiet src/kajiba/schema.py` exits 0). Full suite: 264 passed, 2 PRE-EXISTING skips (yaml soft-dep not installed in test_cli.py/test_config.py), 0 failures. All ESCH-01..05 now covered by passing automated tests. Phase 10 COMPLETE. (Note: 10-VALIDATION.md `wave_0_complete`/`nyquist_compliant` flip deferred to verify-work.)

### Pending Todos

None.

### Blockers/Concerns

- Hermes hook kwargs need empirical verification (no formal payload schema published)
- GLiNER false positive rate on code content needs calibration in Phase 7
- WSL2 CUDA driver stub overwrite risk -- install only cuda-toolkit, not cuda meta-package

## Session Continuity

Last session: 2026-06-04T03:00:00Z
Stopped at: Completed 11-03-PLAN.md (final plan of Phase 11)
Resume file: None — Phase 11 ready for /gsd-verify-work
