# Phase 1: Privacy Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-30
**Phase:** 1-Privacy Foundation
**Areas discussed:** Consent stripping, Hardware anonymization, Org domain flagging, Regex fix strategy

---

## Consent Stripping

### When should consent-level field stripping happen?

| Option | Description | Selected |
|--------|-------------|----------|
| At submit time | Strip fields when record enters the outbox. Local outbox only contains what you consented to share. Simpler but can't change consent later. | |
| At publish time | Outbox keeps full record; stripping happens when pushing to the dataset repo. Allows changing consent before publishing, but full data sits locally longer. | |
| Both layers | Strip at submit (outbox is consent-safe), verify again at publish. Belt and suspenders. | ✓ |

**User's choice:** Both layers
**Notes:** Belt and suspenders approach — strip at submit time so the outbox is consent-safe, verify again at publish for defense in depth.

### If a user changes their consent level after records are already in the outbox, what happens to existing records?

| Option | Description | Selected |
|--------|-------------|----------|
| Retroactive | Re-process existing outbox records to match new consent level | |
| Forward only | New consent applies to future records only; existing ones stay as-is | |
| You decide | Claude picks the best approach based on implementation complexity | ✓ |

**User's choice:** You decide (Claude's discretion)
**Notes:** None

---

## Hardware Anonymization

### How should GPU names be generalized?

| Option | Description | Selected |
|--------|-------------|----------|
| Family tier | "NVIDIA GeForce RTX 4090" → "NVIDIA RTX 40xx" (series-level, hides specific model) | ✓ |
| Vendor only | "NVIDIA GeForce RTX 4090" → "NVIDIA GPU" (maximum anonymity, loses useful context for consumers) | |
| You decide | Claude picks a reasonable generalization strategy | |

**User's choice:** Family tier
**Notes:** Series-level generalization preserves useful context for consumers filtering by GPU class while hiding the specific model.

### What standard RAM/VRAM tiers should values be rounded to?

| Option | Description | Selected |
|--------|-------------|----------|
| Power-of-2 tiers | 4, 8, 16, 32, 64, 128 GB — standard hardware boundaries | ✓ |
| Coarser buckets | "8-16 GB", "16-32 GB", "32-64 GB" — range labels, more anonymous | |
| You decide | Claude picks appropriate tiers | |

**User's choice:** Power-of-2 tiers
**Notes:** Standard hardware boundaries (4, 8, 16, 32, 64, 128 GB) round to nearest.

---

## Org Domain Flagging

### How should flagged items (org domains) be surfaced to the contributor?

| Option | Description | Selected |
|--------|-------------|----------|
| Preview warnings | Show flagged items as warnings in `kajiba preview` — contributor decides to redact or keep each one before submit | ✓ |
| Auto-flag in record | Flag items are noted in the ScrubLog metadata but not shown interactively — just recorded for transparency | |
| Interactive prompt | At submit time, prompt the contributor for each flagged item: "acme.io detected — redact or keep?" | |

**User's choice:** Preview warnings
**Notes:** Non-blocking — flagged items appear as warnings in preview, contributor can decide.

### What gets the flagging treatment (review, not auto-redact)?

| Option | Description | Selected |
|--------|-------------|----------|
| Org domains only | Just .company, .org, .io patterns per spec — keep it narrow for v1 | |
| Org + medium-confidence | Org domains + any future medium-confidence matches (extensible category) | ✓ |
| You decide | Claude designs the flagging mechanism for extensibility | |

**User's choice:** Org + medium-confidence
**Notes:** Extensible flagging mechanism that org domains use now and future scrubber layers (LLM semantic in v2) can also populate.

---

## Regex Fix Strategy

### How should the IP regex avoid matching version strings?

| Option | Description | Selected |
|--------|-------------|----------|
| Context guards | Negative lookbehind for version-like contexts and validate octet ranges (0-255) | |
| Allowlist approach | Maintain an allowlist of known non-IP patterns and skip matches | |
| You decide | Claude picks the most robust approach for reducing false positives | ✓ |

**User's choice:** You decide (Claude's discretion)
**Notes:** None

### How strict should the 40-char hex token pattern be?

| Option | Description | Selected |
|--------|-------------|----------|
| Context-required | Only match when preceded by key=, token=, secret=, password= | |
| Broad + exclusions | Match any 40-char hex string but exclude known patterns | |
| You decide | Claude picks the right balance of recall vs precision | ✓ |

**User's choice:** You decide (Claude's discretion)
**Notes:** None

---

## Claude's Discretion

- Consent change handling (retroactive vs forward-only)
- IP regex fix approach
- 40-char hex token pattern strictness

## Deferred Ideas

None — discussion stayed within phase scope.
