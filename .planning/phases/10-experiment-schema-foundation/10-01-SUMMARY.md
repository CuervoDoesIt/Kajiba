---
phase: 10-experiment-schema-foundation
plan: 01
subsystem: testing
tags: [pydantic, content-hash, golden-baseline, back-compat, sha256]

# Dependency graph
requires:
  - phase: existing v1.0 schema
    provides: KajibaRecord, validate_record, compute_record_id, compute_submission_hash
provides:
  - Reproducible golden-baseline capture script (tests/capture_golden_ids.py)
  - Committed pre-refactor record_id + submission_hash baseline for the 5 *_trajectory.json fixtures (ESCH-04 tripwire)
affects: [10-02 schema refactor, 10-03 back-compat tests]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Golden-baseline pinning: snapshot content hashes from pre-refactor schema, commit before any edit, assert byte-identical after"

key-files:
  created:
    - tests/capture_golden_ids.py
    - tests/fixtures/golden_ids.json
  modified: []

key-decisions:
  - "Golden corpus = the five *_trajectory.json fixtures via glob; enriched_catalog.json excluded (no trajectory, not a KajibaRecord)"
  - "Baseline stored as committed JSON (not hardcoded test constants) so the downstream parametrized test reads it as ground truth"
  - "Capture script includes a defensive trajectory-key guard as belt-and-suspenders against non-KajibaRecord fixtures"

patterns-established:
  - "Pre-refactor baseline capture: generate-then-commit before touching the schema so the back-compat guarantee stays falsifiable"

requirements-completed: [ESCH-04]

# Metrics
duration: 8min
completed: 2026-06-03
---

# Phase 10 Plan 01: Golden Baseline Capture Summary

**Captured the ESCH-04 back-compat tripwire — a reproducible script plus committed pre-refactor record_id/submission_hash baseline for the five *_trajectory.json fixtures, generated before any schema edit.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-06-03
- **Completed:** 2026-06-03
- **Tasks:** 2
- **Files modified:** 2 (both created)

## Accomplishments
- Wrote `tests/capture_golden_ids.py`: a standalone, runnable script that imports the pre-refactor `validate_record`, globs `*_trajectory.json`, guards on the `trajectory` key, and writes `golden_ids.json` deterministically (`json.dumps(..., indent=2, sort_keys=True)`).
- Generated and committed `tests/fixtures/golden_ids.json` with exactly the five fixture keys, captured from the current (pre-refactor) `schema.py`.
- Verified `minimal_trajectory.json` → `kajiba_c2eac32fcdc4`, matching the value RESEARCH proved survives the later refactor.
- Confirmed the capture is byte-identical reproducible (re-run produces an identical file hash).
- Confirmed `src/kajiba/schema.py` is byte-for-byte unchanged (`git diff --quiet` exits 0) — the critical constraint of this plan.

## Captured Baseline

| Fixture | record_id | submission_hash |
|---------|-----------|-----------------|
| adversarial_trajectory.json | kajiba_c9a682a0f395 | sha256:5c6461622fb433aeaa5b3229a2c365c530e324d44a0d988040d2db2036210b4b |
| gold_trajectory.json | kajiba_40f6331f7ff1 | sha256:da289eeb670aae6408b9fc78ffab487de4df92e966103377e3954e06bd4f654c |
| minimal_trajectory.json | kajiba_c2eac32fcdc4 | sha256:52b1ed267d5bd84577839c5d4018c7fb46b1d75555480fd23e0aff5e91e87bfa |
| pii_trajectory.json | kajiba_6ce9ef1a3c39 | sha256:9e7f5ba0e75c9ab5cf1092f8603f6ec528d174f89b6487cd08d9f44e4f9b63df |
| silver_trajectory.json | kajiba_5fcc0553f6e8 | sha256:29fbd75602f6b8d8b688cf5c136147bae0ecae861cab9710e83177ebfe63181f |

`enriched_catalog.json` is intentionally absent — it is a publisher catalog fixture with no `trajectory`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write the golden-baseline capture script** - `723a37e` (test)
2. **Task 2: Run the script and commit the pre-refactor golden baseline** - `85b3866` (test)

**Plan metadata:** (final docs commit)

## Files Created/Modified
- `tests/capture_golden_ids.py` - Reproducible capture script for the pre-refactor record_id/submission_hash baseline.
- `tests/fixtures/golden_ids.json` - Committed golden baseline for the 5 *_trajectory.json fixtures (ESCH-04 ground truth).

## Decisions Made
None beyond the locked plan/Claude's-discretion choices. The plan specified glob-based selection, the `trajectory` guard, deterministic JSON serialization, and the committed-JSON baseline approach — all followed exactly.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- The repository runs on Windows; PowerShell-syntax reproducibility check failed under the Bash tool (bash shell). Re-ran the same check with POSIX `sha256sum` — confirmed byte-identical reproducibility. No impact on artifacts.
- Git emitted a benign `LF will be replaced by CRLF` warning on commit of the Python script. Expected on Windows; no impact.

## User Setup Required
None - no external service configuration required. This phase adds zero dependencies.

## Next Phase Readiness
- The ESCH-04 tripwire is committed before any schema edit, so plan 10-02 (the `RecordBase`/`ExperimentRecord` refactor) can proceed and have its back-compat guarantee verified against this baseline.
- Plan 10-03 can wire a parametrized test that reads `tests/fixtures/golden_ids.json` and asserts byte-identical `record_id`/`submission_hash` post-refactor.
- `schema.py` remains untouched, as required.

## Self-Check: PASSED

- FOUND: tests/capture_golden_ids.py
- FOUND: tests/fixtures/golden_ids.json
- FOUND commit: 723a37e (Task 1)
- FOUND commit: 85b3866 (Task 2)

---
*Phase: 10-experiment-schema-foundation*
*Completed: 2026-06-03*
