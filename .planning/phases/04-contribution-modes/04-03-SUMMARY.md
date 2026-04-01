---
phase: 04-contribution-modes
plan: 03
subsystem: collector
tags: [continuous-mode, auto-submit, staging, outbox, quality-gate, fault-tolerant]

# Dependency graph
requires:
  - phase: 04-contribution-modes
    plan: 01
    provides: config.py module with _load_config_value, tier_meets_threshold, _log_activity
provides:
  - Extended on_session_end with continuous mode auto-submit logic
  - _save_to_staging helper for session data persistence
  - STAGING_DIR, OUTBOX_DIR module-level constants in collector.py
affects: [hermes-integration, cli-review-workflow]

# Tech tracking
tech-stack:
  added: []
  patterns: [inline privacy pipeline in collector for circular-import avoidance, monkeypatch-based test isolation for filesystem and config]

key-files:
  created: []
  modified:
    - src/kajiba/collector.py
    - tests/test_collector.py

key-decisions:
  - "Auto-submit pipeline inlined in on_session_end rather than calling cli._submit_record to avoid circular imports"
  - "STAGING_DIR/OUTBOX_DIR constants duplicated from cli.py to collector.py for same circular import reason"

patterns-established:
  - "Continuous mode pattern: check config -> build -> scrub -> anonymize -> score -> threshold check -> submit or stage"
  - "Staging file naming: session_{session_id}.json"

requirements-completed: [CONT-02]

# Metrics
duration: 3min
completed: 2026-04-01
---

# Phase 04 Plan 03: Continuous Mode Auto-Submit Summary

**Extended collector on_session_end with continuous mode quality-gated auto-submit to outbox, staging fallback for below-threshold records, and activity logging**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-01T13:23:57Z
- **Completed:** 2026-04-01T13:27:38Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Extended on_session_end to support continuous mode auto-submit with full privacy pipeline (scrub, anonymize, jitter, consent, quality scoring, record IDs)
- Added _save_to_staging helper that writes raw session data to staging directory for manual review
- Quality gate: records meeting min_quality_tier are auto-submitted to outbox, below-threshold records saved to staging
- Activity logging: auto_submitted and queued_for_review entries written to activity.jsonl for notification display
- All operations fault-tolerant: exceptions caught and logged, never propagated to host agent session
- 11 new tests (9 continuous mode + 2 staging), 313 total passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend on_session_end for continuous mode and add _save_to_staging helper**
   - `cbc7b17` (test: failing tests for continuous mode and _save_to_staging)
   - `e974479` (feat: continuous mode auto-submit and _save_to_staging in collector)

_TDD task had separate RED (test) and GREEN (feat) commits._

## Files Created/Modified
- `src/kajiba/collector.py` - Extended on_session_end with continuous mode, added _save_to_staging, STAGING_DIR/OUTBOX_DIR constants, config/activity imports, QualityMetadata import
- `tests/test_collector.py` - TestContinuousMode (9 tests) and TestSaveToStaging (2 tests)

## Decisions Made
- Auto-submit pipeline inlined in on_session_end (15 lines) rather than calling _submit_record from cli.py -- avoids circular import risk since collector.py already imports everything needed (scrubber, privacy, scorer, schema)
- STAGING_DIR and OUTBOX_DIR constants duplicated from cli.py rather than importing -- collector module should be self-contained and not depend on the CLI layer

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all functions are fully implemented with real logic.

## Next Phase Readiness
- Continuous mode fully operational: auto-submit on session end for qualifying records
- Integrates with Plan 01's config infrastructure (contribution_mode, min_quality_tier settings)
- Integrates with Plan 02's review command (below-threshold records land in staging for review)
- Activity logging feeds into _show_pending_notifications for CLI notification display

## Self-Check: PASSED

- All 2 files exist (collector.py, test_collector.py)
- Both commits verified (cbc7b17, e974479)
- All collector exports importable (KajibaCollector, STAGING_DIR, OUTBOX_DIR)
- 313 tests passing, zero failures

---
*Phase: 04-contribution-modes*
*Completed: 2026-04-01*
