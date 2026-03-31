---
phase: 02-data-quality-transparency
plan: 01
subsystem: schema, cli
tags: [pydantic, quality-scoring, persistence, backward-compat]

# Dependency graph
requires:
  - phase: 01-privacy-foundation
    provides: Privacy pipeline (scrub, anonymize, jitter, consent strip) wired into submit/export
provides:
  - QualityMetadata Pydantic model on KajibaRecord
  - Quality persistence in submit and export commands
  - Stored quality reads in history and stats (no recomputation)
  - Score column in history table
  - Backward-compatible fallback for old records without quality field
affects: [02-02, 02-03, quality-browsing, dataset-consumers]

# Tech tracking
tech-stack:
  added: []
  patterns: [stored-quality-read-pattern, fallback-recompute-pattern]

key-files:
  created: []
  modified:
    - src/kajiba/schema.py
    - src/kajiba/cli.py
    - tests/test_schema.py
    - tests/test_cli.py

key-decisions:
  - "Quality computed on final record (post-privacy-pipeline) at submit/export time, not on original"
  - "History/stats read stored quality_tier directly from JSON dict, falling back to recompute for old records"
  - "Score column added to history table alongside quality tier (per D-11)"

patterns-established:
  - "Stored quality read pattern: data.get('quality') with fallback to compute_quality_score for backward compat"
  - "Quality persistence pattern: compute_quality_score -> QualityMetadata -> attach to record before writing"

requirements-completed: [QUAL-01, QUAL-05]

# Metrics
duration: 4min
completed: 2026-03-31
---

# Phase 02 Plan 01: Quality Persistence Summary

**QualityMetadata Pydantic model with 5 sub-scores stored at submit/export time, read back in history/stats with backward-compatible fallback**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-31T10:16:10Z
- **Completed:** 2026-03-31T10:19:58Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 4

## Accomplishments
- QualityMetadata Pydantic model added to schema.py with quality_tier, composite_score (ge=0.0, le=1.0), sub_scores dict, and scored_at timestamp
- Submit and export commands now persist quality scores in the record before writing to outbox/export
- History command reads stored quality_tier and composite_score without recomputing (Score column added)
- Stats command reads stored quality_tier without recomputing
- Old records without quality field still work via fallback to compute_quality_score
- User annotations (outcome, pain_points) confirmed to survive the submit pipeline alongside quality
- All 173 tests passing (9 new + 164 existing)

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests** - `632446d` (test)
2. **Task 1 (GREEN): Implementation** - `4967539` (feat)

_TDD task with RED/GREEN commits. No refactor needed._

## Files Created/Modified
- `src/kajiba/schema.py` - Added QualityMetadata Pydantic model, added quality field to KajibaRecord
- `src/kajiba/cli.py` - Quality persistence in submit/export, stored quality reads in history/stats, Score column in history table
- `tests/test_schema.py` - TestQualityMetadata class (5 tests: valid construction, boundary validation, backward compat, round-trip)
- `tests/test_cli.py` - TestSubmitQualityPersistence, TestHistoryStoredQuality, TestExportAnnotations (4 tests)

## Decisions Made
- Quality is computed on the final record (post-privacy-pipeline) rather than the original -- this ensures the quality score reflects what is actually stored/exported
- History and stats read stored quality_tier directly from the raw JSON dict (not validated record) for efficiency and to avoid failing on slightly different schema versions
- Score column added to history table showing composite_score alongside quality_tier (per D-11)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all quality persistence is fully wired.

## Next Phase Readiness
- Quality scores now persisted in records, ready for:
  - Plan 02-02: Redaction diff display in preview
  - Plan 02-03: Rate/report CLI commands for user annotation refinement
- All quality data (tier, composite, sub-scores, timestamp) available for future browsing/filtering features

---
*Phase: 02-data-quality-transparency*
*Completed: 2026-03-31*
