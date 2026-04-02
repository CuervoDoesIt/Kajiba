---
phase: 01-privacy-foundation
plan: 01
subsystem: privacy
tags: [regex, pii-scrubbing, ip-detection, hex-tokens, domain-flagging, pydantic]

# Dependency graph
requires: []
provides:
  - Context-aware IP scrubbing that avoids version-string false positives
  - 40-char hex token scrubbing with context keywords (token=, key=, secret=, etc.)
  - Org domain flagging with safe-domain allowlist (FlaggedItem dataclass)
  - ScrubLog.items_flagged field for tracking flagged item count
  - ScrubResult.flagged list for review workflow integration
affects: [01-02, 01-03, phase-02-quality]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Context-aware regex scrubbing with prefix lookback to avoid false positives
    - Flagging pattern (FlaggedItem) for items needing human review vs auto-redaction
    - Safe-domain allowlist pattern (frozenset) for excluding known-good domains

key-files:
  created: []
  modified:
    - src/kajiba/schema.py
    - src/kajiba/scrubber.py
    - tests/test_scrubber.py

key-decisions:
  - "IP scrubbing uses 30-char prefix lookback with VERSION_PREFIX regex to skip version strings"
  - "Hex token detection requires context keyword prefix (token/key/secret/password/apikey/api_key/auth/credential) to avoid scrubbing git commit hashes"
  - "Org domains (.company/.org/.io) are flagged for review, not auto-redacted, with SAFE_DOMAINS frozenset for exclusions"
  - "hex_tokens category counts toward api_keys_redacted in ScrubLog (they are a type of secret)"

patterns-established:
  - "FlaggedItem dataclass: text/category/reason/start/end for items needing user review"
  - "Context-aware scrubbing: _scrub_ips_context_aware() runs after main pattern loop, not inside SCRUB_PATTERNS"
  - "flag_org_domains() runs after all redactions on final text, flagged items stored in ScrubResult.flagged"

requirements-completed: [PRIV-04, PRIV-05, PRIV-06]

# Metrics
duration: 4min
completed: 2026-03-31
---

# Phase 01 Plan 01: Scrubber Pattern Fixes Summary

**Context-aware IP regex eliminating version-string false positives, hex token scrubbing with keyword context, and org domain flagging with safe-domain allowlist**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-31T02:03:22Z
- **Completed:** 2026-03-31T02:07:47Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 3

## Accomplishments
- Fixed IP regex false positives: version strings like "Python 3.11.0.0" and "CUDA 12.1.0.0" no longer redacted, while real IPs still detected
- Added 40-char hex token scrubbing with context keywords (token=, key=, secret=, password=, apikey=, api_key=, auth=, credential=) -- preserves git commit hashes
- Added org domain flagging (.company, .org, .io TLDs) with safe-domain allowlist (github.io, python.org, crates.io, etc.) -- flags for review, never auto-redacts
- Extended ScrubLog with items_flagged counter and ScrubResult with flagged list for review workflow
- All 152 tests pass (23 new + 129 existing) with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for IP, hex tokens, org domains** - `c4b0bb9` (test)
2. **Task 1 GREEN: Implementation passing all tests** - `9486718` (feat)

_TDD cycle: RED (failing tests) then GREEN (implementation). No REFACTOR needed._

## Files Created/Modified
- `src/kajiba/schema.py` - Added `items_flagged: int = 0` field to ScrubLog model
- `src/kajiba/scrubber.py` - Added FlaggedItem dataclass, IP_CANDIDATE/VERSION_PREFIX regexes, _scrub_ips_context_aware(), ORG_DOMAIN_PATTERN/SAFE_DOMAINS, flag_org_domains(), hex_tokens SCRUB_PATTERNS entry, updated scrub_text()/scrub_record()
- `tests/test_scrubber.py` - Added TestIPFalsePositiveFix (8 tests), TestHexTokenScrubbing (6 tests), TestOrgDomainFlagging (6 tests), TestFlaggingSupport (3 tests)

## Decisions Made
- IP scrubbing uses 30-char prefix lookback with VERSION_PREFIX regex rather than negative lookbehind, because lookbehind requires fixed-width patterns and version prefixes are variable-length
- Hex token detection requires context keyword prefix to distinguish secrets from git SHA hashes -- "commit abc123..." is preserved, "token=abc123..." is scrubbed
- Org domains are flagged (FlaggedItem) rather than redacted because domain ownership can be ambiguous -- human review is the correct approach per the spec
- hex_tokens counts toward api_keys_redacted in ScrubLog since they are functionally API keys/secrets

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None - all functionality is fully wired and operational.

## Next Phase Readiness
- FlaggedItem and ScrubResult.flagged are ready for the `kajiba preview` redaction diff surface (noted as Phase 2 dependency in STATE.md blockers)
- ScrubLog.items_flagged integrates cleanly with existing scrub_record() pipeline
- The CATEGORY_TO_LOG_FIELD mapping includes hex_tokens for any future use of that mapping

---
## Self-Check: PASSED

- All 4 files verified present on disk
- Both commits (c4b0bb9, 9486718) verified in git log
- 152/152 tests passing

---
*Phase: 01-privacy-foundation*
*Completed: 2026-03-31*
