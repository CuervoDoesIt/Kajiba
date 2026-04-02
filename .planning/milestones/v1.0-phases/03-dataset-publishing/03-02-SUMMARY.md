---
phase: 03-dataset-publishing
plan: 02
subsystem: cli
tags: [click, rich, gh-cli, publish, delete, pr-workflow, consent-reverification]

# Dependency graph
requires:
  - phase: 03-dataset-publishing/01
    provides: publisher.py with GitHubOps, write_records_to_shards, generate_catalog, generate_readme, create_deletion_entry, PR builders
  - phase: 01-privacy-foundation
    provides: apply_consent_level for consent re-verification at publish time
provides:
  - "kajiba publish CLI command implementing full D-04 workflow (auth, outbox, consent, fork, clone, shards, catalog, readme, PR)"
  - "kajiba delete CLI command implementing D-09 deletion via index file and D-10 any-record-by-ID"
  - "Integration tests for both commands covering error cases and dry-run mode"
affects: [04-model-agnostic, 05-consumer-browse]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "GitHubOps mock pattern: monkeypatch GitHubOps constructor to return MagicMock with GhResult returns"
    - "_load_config_value helper for reading config keys from ~/.hermes/config.yaml"

key-files:
  created: []
  modified:
    - src/kajiba/cli.py
    - tests/test_cli.py

key-decisions:
  - "publish command re-verifies consent on every record before writing to shards (belt-and-suspenders per D-03)"
  - "delete branch name uses first 12 chars of record_id for readability"
  - "dry-run mode writes shards/catalog/readme to clone but does not commit/push/PR"

patterns-established:
  - "CLI commands that require gh CLI: check auth first, fail fast with clear install URL"
  - "Mock GitHubOps in tests via monkeypatch on kajiba.cli.GitHubOps constructor"

requirements-completed: [PUB-05, PRIV-07]

# Metrics
duration: 4min
completed: 2026-03-31
---

# Phase 3 Plan 2: Publish and Delete CLI Commands Summary

**`kajiba publish` and `kajiba delete` CLI commands wiring publisher.py into Click with full D-04 workflow, consent re-verification, dry-run mode, and deletion-via-PR**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-31T15:21:37Z
- **Completed:** 2026-03-31T15:25:28Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added `kajiba publish` command implementing the full 10-step D-04 workflow: auth check, outbox load, consent re-verification, fork/clone, branch, shard writing, catalog/readme regeneration, commit, push, PR creation
- Added `kajiba delete` command implementing D-09 deletion via index file and D-10 any-record-by-ID via PR
- Added 8 integration tests covering error cases (no gh, no auth, no records, missing argument) and dry-run mode
- All 259 tests pass (251 existing + 8 new)
- CLI now has 10 commands: config, delete, export, history, preview, publish, rate, report, stats, submit

## Task Commits

Each task was committed atomically:

1. **Task 1: Add kajiba publish command with full D-04 workflow** - `b65d2da` (feat)
2. **Task 2: Add kajiba delete command and integration tests** - `8eba0a5` (feat)

## Files Created/Modified
- `src/kajiba/cli.py` - Added publisher imports, _load_config_value helper, publish command (D-04 workflow with dry-run), delete command (D-09/D-10 deletion via PR)
- `tests/test_cli.py` - Added _make_outbox_record helper, TestPublishCommand (5 tests), TestDeleteCommand (3 tests)

## Decisions Made
- Publish command re-verifies consent level on each record before writing to shards, implementing belt-and-suspenders approach from Phase 1 D-03
- Delete branch name uses first 12 characters of record_id for human readability (e.g., `kajiba/delete-abc123456789`)
- Dry-run mode writes shards, catalog, and readme to the local clone directory but stops before commit/push/PR -- this lets users inspect what would be published
- Partial success handling: if push succeeds but PR creation fails, user gets a message with manual PR creation URL instead of a hard failure

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. The `gh` CLI is checked at runtime with clear install instructions if missing.

## Next Phase Readiness
- Phase 3 (dataset-publishing) is now complete with both plans executed
- All publishing infrastructure in place: publisher.py (Plan 01) + CLI commands (Plan 02)
- Ready for Phase 4 (model-agnostic) or Phase 5 (consumer-browse) which will use catalog.json for browse/download

## Self-Check: PASSED

- FOUND: src/kajiba/cli.py
- FOUND: tests/test_cli.py
- FOUND: .planning/phases/03-dataset-publishing/03-02-SUMMARY.md
- FOUND: b65d2da (Task 1 commit)
- FOUND: 8eba0a5 (Task 2 commit)

---
*Phase: 03-dataset-publishing*
*Completed: 2026-03-31*
