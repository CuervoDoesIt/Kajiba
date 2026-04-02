---
phase: 01-privacy-foundation
plan: 03
subsystem: privacy
tags: [privacy, consent, anonymization, cli, collector, pii, flagging]

# Dependency graph
requires:
  - phase: 01-privacy-foundation plan 01
    provides: FlaggedItem dataclass, flag_org_domains(), ScrubLog.items_flagged
  - phase: 01-privacy-foundation plan 02
    provides: apply_consent_level(), anonymize_hardware(), jitter_timestamp()
provides:
  - Full privacy pipeline wired into collector.export_record()
  - Full privacy pipeline wired into CLI submit, export, preview commands
  - Flagged org domain warnings in CLI preview output
  - Consent enforcement at write time in submit and export
  - Integration tests for CLI privacy pipeline
affects: [phase-02-quality, phase-03-publishing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Privacy pipeline order: scrub -> anonymize -> jitter -> consent strip"
    - "Flagged items shown as warnings in CLI preview, not auto-redacted"
    - "Consent level read from original record submission metadata"

key-files:
  created:
    - tests/test_cli.py (TestPreviewFlaggedWarnings, TestSubmitConsentEnforcement, TestExportPrivacyPipeline)
  modified:
    - src/kajiba/collector.py (export_record with full privacy pipeline)
    - src/kajiba/cli.py (preview/submit/export with privacy pipeline, _render_preview with flagged_items)

key-decisions:
  - "Preview shows anonymized hardware but does not apply consent stripping (user sees full context)"
  - "Flagged items collected from original record turns, not scrubbed turns, for accurate domain detection"
  - "Consent level read from original record, not scrubbed record, to avoid scrubbing altering metadata"

patterns-established:
  - "Privacy pipeline integration: always scrub -> anonymize -> jitter -> consent strip in that order"
  - "CLI flagged warnings: collect via flag_org_domains, pass to _render_preview as flagged_items"

requirements-completed: [PRIV-01, PRIV-02, PRIV-03, PRIV-04, PRIV-05, PRIV-06]

# Metrics
duration: 5min
completed: 2026-03-31
---

# Phase 1 Plan 3: Privacy Pipeline Wiring Summary

**Full privacy pipeline (scrub -> anonymize -> jitter -> consent strip) wired into collector.export_record() and all CLI commands with flagged org domain warnings in preview**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-31T02:10:38Z
- **Completed:** 2026-03-31T02:15:38Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Wired the complete privacy pipeline (scrub -> anonymize -> jitter -> consent strip) into collector.export_record() with try/except fault-tolerance wrapper
- Updated all three CLI commands (preview, submit, export) to apply the full privacy pipeline before output
- Added flagged org domain warnings in preview and submit commands, showing specific domains for user review
- Created integration tests verifying consent enforcement, hardware anonymization, and flagged warning display

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire privacy pipeline into collector.export_record() and CLI commands** - `110905c` (feat)
2. **Task 2: Add integration tests for CLI privacy pipeline and flagged warnings** - `2dbd250` (test)

## Files Created/Modified
- `src/kajiba/collector.py` - export_record() now applies full privacy pipeline: scrub, anonymize_hardware, jitter_timestamp, apply_consent_level
- `src/kajiba/cli.py` - preview/submit/export commands wire privacy pipeline; _render_preview accepts flagged_items; imports from kajiba.privacy and kajiba.scrubber.flag_org_domains
- `tests/test_cli.py` - TestPreviewFlaggedWarnings (3 tests), TestSubmitConsentEnforcement (2 tests), TestExportPrivacyPipeline (1 test)

## Decisions Made
- Preview shows anonymized hardware but does NOT apply consent stripping -- user should see the full context to make informed decisions before submitting
- Flagged items are collected from the original (pre-scrub) record turns so domain detection happens on raw text, not scrubbed text
- Consent level is read from the original record's submission metadata, not the scrubbed record, to prevent scrubbing from altering consent metadata

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 1 (privacy-foundation) is fully complete: all three plans executed
- Scrubber patterns fixed (Plan 01), privacy module created (Plan 02), pipeline wired (Plan 03)
- All 158 tests pass across the full suite
- Phase 2 (quality) can proceed -- quality scoring now operates on privacy-processed records
- The flagged-for-review mechanism (FlaggedItem) is ready for Phase 2 to use in redaction diff surfaces

---
*Phase: 01-privacy-foundation*
*Completed: 2026-03-31*
