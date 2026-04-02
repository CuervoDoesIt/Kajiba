# Phase 1: Privacy Foundation - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Close active consent and fingerprinting violations. After this phase, contributors can export records knowing their consent choice is enforced, their hardware profile cannot fingerprint them, regex false positives are fixed, and org domains are flagged for review. No data publishing or quality changes — purely making the scrub/export path trustworthy.

</domain>

<decisions>
## Implementation Decisions

### Consent Enforcement
- **D-01:** Consent stripping happens at BOTH submit time and publish time (belt and suspenders). The outbox only contains consent-safe data, and publish verifies again before pushing.
- **D-02:** `apply_consent_level(record, level)` is a pure function that strips fields based on the consent table in the spec (Section 2.2 Layer E). Called in the CLI submit/export paths and in export_record().
- **D-03:** Consent level is read from the record's `submission.consent_level` field, which is set from the user's config at capture time.

### Hardware Anonymization
- **D-04:** GPU names are generalized to family tier: "NVIDIA GeForce RTX 4090" → "NVIDIA RTX 40xx" (series-level, hides specific model). Map common GPU families to their series designator.
- **D-05:** RAM and VRAM are rounded to nearest power-of-2 standard tier: 4, 8, 16, 32, 64, 128 GB.
- **D-06:** OS version is stripped entirely — only the OS family label remains (linux, macos, windows).
- **D-07:** Timestamps are jittered ±0-30 minutes (random offset per record) to prevent session correlation.
- **D-08:** `anonymize_metadata(record)` is a function that applies all hardware anonymization. Called after PII scrubbing in the scrub pipeline.

### Org Domain Flagging
- **D-09:** Org domains (.company, .org, .io patterns) are FLAGGED for review, not auto-redacted. Flagged items appear as warnings in `kajiba preview` so the contributor can decide to redact or keep each one before submit.
- **D-10:** The flagging mechanism is extensible — designed as a "medium-confidence" category that future scrubber layers (e.g., LLM semantic scrubbing in v2) can also use. ScrubResult gets a new `flagged` list alongside `redactions`.
- **D-11:** If a contributor submits without addressing flagged items, they pass through as-is (flagged items are noted in the ScrubLog but not blocked).

### Regex Fixes
- **D-12:** IP address regex fix and 40-char hex token pattern are Claude's discretion. Goal: minimize false positives on version strings while catching real IPs, and catch hex tokens only when context keywords are present.

### Claude's Discretion
- Consent change handling (retroactive vs forward-only for existing outbox records) — Claude picks the best approach based on implementation complexity.
- IP regex fix approach — context guards, octet validation, or hybrid.
- 40-char hex token pattern strictness — context-required vs broad+exclusions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Privacy Spec
- `docs/kajiba-project-spec.md` §2.2 — PII scrubbing layers (B, C, D, E) and consent level table. Primary source for what each consent level strips.

### Existing Implementation
- `src/kajiba/scrubber.py` — Current regex scrubber (Layer B). Extension point for new patterns and flagging mechanism.
- `src/kajiba/schema.py` lines 210-234 — ScrubLog model and SubmissionMetadata with consent_level field.
- `src/kajiba/collector.py` lines 40-110 — `_detect_hardware()` function that captures raw GPU/RAM/OS data. Anonymization wraps around this output.
- `src/kajiba/cli.py` lines 191-225 — Submit command where consent enforcement must be wired.

### Codebase Analysis
- `.planning/codebase/CONCERNS.md` — Full gap analysis including spec vs implementation table.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scrub_text()` / `scrub_record()` in `scrubber.py` — well-structured scrubbing pipeline. New patterns (40-char hex, org domain) add to `SCRUB_PATTERNS` dict.
- `ScrubLog` Pydantic model in `schema.py` — already tracks per-category counts. Extend for flagged items.
- `ConsentLevelType` Literal in `schema.py` — consent levels already defined as a type.
- `_detect_hardware()` in `collector.py` — already captures GPU name, VRAM, RAM, OS. Anonymization function operates on this output.

### Established Patterns
- Scrubbing operates on deep copy via `model_dump(by_alias=True)` → mutate → `model_validate()`. Same pattern for consent stripping and metadata anonymization.
- Per-category counting in ScrubLog via `CATEGORY_TO_LOG_FIELD` mapping.
- Pure function pattern: `scrub_record()` returns new record + log, doesn't mutate input.

### Integration Points
- `scrub_record()` is called from CLI submit/export paths — consent enforcement and metadata anonymization should compose with this.
- `_detect_hardware()` output flows into `KajibaRecord.hardware` via `collector.export_record()`.
- CLI `preview` command (`_render_preview()`) is where flagged items surface to the user.

</code_context>

<specifics>
## Specific Ideas

- Contributor mentioned privacy is paramount — err on the side of over-redacting. Maximum scrubbing by default.
- Consent stripping is called out as a "silent breach" in CONCERNS.md — treat as a blocking bug fix, not a new feature.
- STATE.md notes: "Phase 2 plan must confirm the diff surface uses the new mechanism, not the old ScrubResult shape" — the flagging mechanism built here must be stable for Phase 2 to build on.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-privacy-foundation*
*Context gathered: 2026-03-30*
