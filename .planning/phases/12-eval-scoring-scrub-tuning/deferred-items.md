# Deferred Items — Phase 12

Out-of-scope discoveries logged during execution. Do NOT fix in this phase.

## 12-04: scrubber.py api_keys pattern misses `sk-live-` style keys

- **Found during:** 12-04 Task 2 (experiment scrub integration test)
- **Where:** `src/kajiba/scrubber.py` SCRUB_PATTERNS["api_keys"] — `re.compile(r"sk-[a-zA-Z0-9]{32,}")`
- **Issue:** API keys with an internal hyphen after the `sk-` prefix (e.g.
  `sk-live-AbCdEf1234567890XyZqrStUvWx`, used by some providers) are NOT redacted
  because `[a-zA-Z0-9]` stops at the first hyphen and the remaining run is below
  the `{32,}` minimum. The fixture `tests/fixtures/experiment_pii.json`
  `task_description` carries such a key and it survives scrubbing
  (`api_keys_redacted=0`).
- **Why deferred:** Pre-existing gap in the SHARED community regex layer
  (`scrubber.py`), finalized in earlier phases. Plan 12-04 is the integration
  layer and per D-09 reuses the shared scrub engine verbatim — it must NOT fork
  or modify the regex denylist. Out of scope (scope boundary: only auto-fix
  issues directly caused by this task's changes).
- **Suggested owner:** A scrubber-hardening pass (regex tuning is exactly Phase
  12's "scrub-tuning" theme but in the COMMUNITY scrubber, a separate concern
  from the experiment divergent tail). Widen the `sk-` pattern to tolerate
  internal hyphens/underscores, e.g. `sk-[a-zA-Z0-9_-]{20,}`, with regression
  tests in `tests/test_scrubber.py`.
