---
phase: 04-contribution-modes
plan: 02
subsystem: cli
tags: [click, rich, review, ad-hoc, activity-notifications]

# Dependency graph
requires:
  - phase: 04-contribution-modes/01
    provides: config.py module with _show_pending_notifications, _submit_record helper, _load_all_staging
provides:
  - kajiba review command with one-at-a-time approve/reject/skip/quit flow
  - Activity notification display in CLI group callback
affects: [04-03, continuous-mode]

# Tech tracking
tech-stack:
  added: []
  patterns: [one-at-a-time review loop with safe staging deletion, CLI group callback notification hook]

key-files:
  created: []
  modified:
    - src/kajiba/cli.py
    - tests/test_cli.py

key-decisions:
  - "Staging file only removed after successful _submit_record call (Pitfall 5 data loss prevention)"
  - "Activity notification displayed via _show_pending_notifications in cli() group callback before any command output"
  - "Review uses click.prompt with Choice for approve/reject/skip/quit with skip as safe default"

patterns-established:
  - "Review loop: iterate _load_all_staging, preview each, prompt action, handle result"
  - "CLI group callback as notification hook point for cross-cutting concerns"

requirements-completed: [CONT-01]

# Metrics
duration: 3min
completed: 2026-04-01
---

# Phase 04 Plan 02: Review Command Summary

**Ad-hoc review command with one-at-a-time approve/reject/skip/quit flow, safe staging deletion, and activity notification banner in CLI group callback**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-01T13:24:30Z
- **Completed:** 2026-04-01T13:27:29Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Added `kajiba review` command with full preview + action prompt for each staged record
- Implemented data-loss-safe staging deletion (only after successful outbox write)
- Wired activity notification display into CLI group callback via `_show_pending_notifications()`
- 11 new tests (8 review command + 3 activity notification), 313 total passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Add kajiba review command with one-at-a-time flow and activity notifications**
   - `8a6f6d2` (test: failing tests for review command and activity notifications)
   - `2976c90` (feat: review command and activity notifications)

_TDD task had separate RED (test) and GREEN (feat) commits._

## Files Created/Modified
- `src/kajiba/cli.py` - Added review command, imported _show_pending_notifications, added notification display to cli() group callback
- `tests/test_cli.py` - Added TestReviewCommand (8 tests) and TestActivityNotification (3 tests)

## Decisions Made
- Staging file only removed after successful `_submit_record()` call -- if submit raises, the staging file is preserved for retry (Pitfall 5 data loss prevention)
- Activity notification displayed in `cli()` group callback so it appears before any command output (D-10)
- Review uses `click.prompt("Action", type=click.Choice(["approve", "reject", "skip", "quit"]), default="skip")` -- skip is safe default per UI-SPEC

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all functions are fully implemented with real logic.

## Next Phase Readiness
- Review command ready for ad-hoc contribution workflow
- Activity notifications ready for continuous mode (Plan 03) to show auto-submit summaries
- _submit_record reuse pattern established for both review approve and continuous auto-submit

## Self-Check: PASSED

- All 2 files exist (cli.py, test_cli.py)
- All 2 commits verified (8a6f6d2, 2976c90)
- review command present in cli.py
- _show_pending_notifications imported and called in cli.py
- TestReviewCommand and TestActivityNotification classes present in test_cli.py
- 313 tests passing, zero failures

---
*Phase: 04-contribution-modes*
*Completed: 2026-04-01*
