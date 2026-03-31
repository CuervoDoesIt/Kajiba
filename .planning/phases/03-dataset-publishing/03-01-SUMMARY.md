---
phase: 03-dataset-publishing
plan: 01
subsystem: publishing
tags: [jsonl, sharding, catalog, github-ops, subprocess, hashlib, readme-generation]

# Dependency graph
requires:
  - phase: 01-privacy-foundation
    provides: apply_consent_level for re-verification at publish time
  - phase: 02-data-quality
    provides: QualityMetadata with quality_tier for directory organization
provides:
  - publisher.py module with all file layout, sharding, catalog, README, deletion, GitHubOps logic
  - Pure functions for dataset structure computation (normalize, shard, path, catalog, readme)
  - GitHubOps class wrapping gh/git CLI behind mockable interface
  - PR template functions for publish and deletion workflows
  - GhResult dataclass for structured CLI operation results
affects: [03-02-PLAN, phase-05-consumer-commands]

# Tech tracking
tech-stack:
  added: []
  patterns: [GitHubOps wrapper for subprocess isolation, hash-based deterministic sharding, forward-slash paths for cross-platform]

key-files:
  created:
    - src/kajiba/publisher.py
    - tests/test_publisher.py
  modified: []

key-decisions:
  - "SHA-256 first 2 hex chars mod 256 for deterministic shard assignment -- uniform distribution, simple, deterministic"
  - "Forward slashes in compute_record_path (string concat, not pathlib) for cross-platform dataset paths"
  - "Special chars stripped (not replaced with hyphens) in normalize_model_name to avoid spurious hyphens"
  - "GitHubOps._run_gh and _run_git use identical error handling pattern (FileNotFoundError -> -1, TimeoutExpired -> -2)"

patterns-established:
  - "GitHubOps pattern: wrap all external CLI calls in a class with _run_gh/_run_git methods returning GhResult dataclass"
  - "Hash-based sharding: compute_shard_key uses SHA-256 mod num_shards for deterministic file assignment"
  - "Forward-slash paths: dataset-relative paths always use / not pathlib to avoid Windows backslash issues"

requirements-completed: [PUB-01, PUB-02, PUB-03, PUB-04, PRIV-08]

# Metrics
duration: 5min
completed: 2026-03-31
---

# Phase 3 Plan 1: Publisher Module Summary

**Publisher module with SHA-256 sharded JSONL layout, catalog indexing, README generation, deletion tracking, and GitHubOps gh/git CLI wrapper**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-31T15:13:41Z
- **Completed:** 2026-03-31T15:19:22Z
- **Tasks:** 1 (TDD: RED + GREEN + REFACTOR)
- **Files modified:** 2

## Accomplishments
- Created publisher.py (875 lines) with 10 public functions/classes covering all dataset publishing logic
- Created test_publisher.py (695 lines) with 63 unit tests across 9 test classes
- All 251 tests pass (188 existing + 63 new) with zero regressions
- GitHubOps class isolates all gh/git subprocess calls behind mockable interface with structured GhResult returns

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for publisher module** - `ef025bc` (test)
2. **Task 1 GREEN: Implement publisher module** - `a91cfce` (feat)

## Files Created/Modified
- `src/kajiba/publisher.py` - File layout (normalize_model_name, compute_shard_key, compute_record_path), sharding (write_records_to_shards), catalog generation (generate_catalog), README generation (generate_readme), deletion tracking (create_deletion_entry), GitHubOps class (check_auth, fork_repo, clone_fork, pull_latest, create_branch, commit_all, push_branch, create_pr, get_username), PR templates (build_publish_pr_title, build_publish_pr_body, build_deletion_pr_title, build_deletion_pr_body)
- `tests/test_publisher.py` - 63 unit tests: TestNormalizeModelName (8), TestComputeShardKey (5), TestComputeRecordPath (6), TestWriteRecordsToShards (8), TestGenerateCatalog (7), TestGenerateReadme (6), TestCreateDeletionEntry (5), TestGitHubOps (12), TestPRTemplates (6)

## Decisions Made
- SHA-256 first 2 hex chars mod 256 for deterministic shard assignment -- provides uniform distribution across 256 shards, simple implementation, and deterministic results
- Forward slashes in compute_record_path via string concatenation (not pathlib) to avoid Windows backslash issues in dataset-relative paths
- Special characters (!, @, etc.) are stripped rather than replaced with hyphens in normalize_model_name -- this avoids spurious hyphens like "a-b-c" from "a!!b@@c" while spaces/dots/underscores still become hyphens
- GitHubOps uses identical error handling for both _run_gh and _run_git: FileNotFoundError returns returncode -1, TimeoutExpired returns returncode -2

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed normalize_model_name special character handling**
- **Found during:** Task 1 GREEN (implementation)
- **Issue:** Initial implementation replaced all non-alphanumeric chars with hyphens, causing "a!!b@@c" to become "a-b-c" instead of "abc" as specified in behavior
- **Fix:** Changed to two-step regex: first replace whitespace/dots/underscores with hyphens, then strip remaining special chars
- **Files modified:** src/kajiba/publisher.py
- **Verification:** All normalize_model_name tests pass
- **Committed in:** a91cfce (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Minor implementation correction. No scope creep.

## Issues Encountered
None

## Known Stubs
None - all functions are fully implemented.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Publisher module is complete and ready for Plan 02 (CLI commands: `kajiba publish` and `kajiba delete`)
- GitHubOps class provides the mockable interface Plan 02 will call from CLI commands
- All pure functions (catalog, readme, sharding) are tested and ready for integration

---
*Phase: 03-dataset-publishing*
*Completed: 2026-03-31*
