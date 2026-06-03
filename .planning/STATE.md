---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Hermes Pipeline Validation
status: executing
stopped_at: Completed 10-02-PLAN.md
last_updated: "2026-06-03T23:58:00.000Z"
last_activity: 2026-06-03 -- Completed Phase 10 Plan 02 (experiment schema refactor)
progress:
  total_phases: 2
  completed_phases: 0
  total_plans: 3
  completed_plans: 2
  percent: 67
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-02)

**Core value:** Real-world AI session data, tagged with full runtime context, flowing into a community dataset that accelerates local model fine-tuning for everyone.
**Current focus:** Phase 10 — experiment-schema-foundation
**Parallel milestone:** v1.2 Experiment Logging (Dual-Use), Phases 10-15 — recommended start: Phase 10 (schema, v1.1-independent). See `.planning/seeds/v1.2-experiment-logging.md`.

## Current Position

Phase: 10 (experiment-schema-foundation) — EXECUTING
Plan: 3 of 3
Status: Executing Phase 10 (10-01, 10-02 complete)
Last activity: 2026-06-03 -- Completed Phase 10 Plan 02 (experiment schema refactor)

Progress: [███████░░░] 67%

## Performance Metrics

**Velocity:**

- Total plans completed: 13 (v1.0)
- Average duration: --
- Total execution time: --

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1-5 (v1.0) | 13/13 | -- | -- |

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

### Pending Todos

None.

### Blockers/Concerns

- Hermes hook kwargs need empirical verification (no formal payload schema published)
- GLiNER false positive rate on code content needs calibration in Phase 7
- WSL2 CUDA driver stub overwrite risk -- install only cuda-toolkit, not cuda meta-package

## Session Continuity

Last session: 2026-06-03T23:58:00.000Z
Stopped at: Completed 10-02-PLAN.md (experiment schema refactor)
Resume file: .planning/phases/10-experiment-schema-foundation/10-03-PLAN.md
