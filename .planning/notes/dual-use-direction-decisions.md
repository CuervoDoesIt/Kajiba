---
title: "Dual-Use Direction — Decisions & Rationale"
date: 2026-06-03
context: "/gsd-explore session deciding how to integrate docs/dual-use-roadmap.md"
related:
  - .planning/seeds/v1.2-experiment-logging.md
  - docs/dual-use-roadmap.md
---

# Dual-Use Direction — Decisions & Rationale

Records the *why* behind the four decisions made in the 2026-06-03 explore
session, so future-me doesn't re-litigate them. The decisions themselves and the
forward scope live in the seed (`.planning/seeds/v1.2-experiment-logging.md`).

## The two framing tensions surfaced at the start

1. **Mission reversal.** `REQUIREMENTS.md` explicitly listed *"Model
   evaluation/benchmarking — Out of scope entirely."* The dual-use roadmap is, at
   its core, a model-evaluation logging system. Integrating it isn't a bolt-on —
   it reverses a deliberate scope boundary, so it deserved a deliberate decision.
2. **v1.1 is a validation milestone.** Its whole purpose is to *prove* the
   coding pipeline works against real Hermes data and close the loop with a
   fine-tune. Folding dual-use in risked diluting that and churning the schema
   right when it most needs to hold still.

## Decision 1 — Parallel milestone (not sequential, not pivot, not fold-in)

**Chosen:** New v1.2 "Experiment Logging" milestone, run in parallel with v1.1.

**Why this over the alternatives:**
- User answered *need it soon* + *commit to it as first-class mission* + *full
  pipeline*. That combination kills "defer to v2" and kills "small slice into
  v1.1" (full pipeline is milestone-scale — would balloon v1.1 from 4 to ~9
  phases and erase its identity).
- **Sequential** (finish all v1.1 first) rejected: four phases of work before
  dual-use even starts — too slow for an operational need.
- **Pivot** (dual-use leapfrogs, trim v1.1) rejected: abandons v1.1's fine-tune
  gate mid-flight, leaving the coding pipeline unproven, and cuts against the
  standing "Hermes-centric, prove the loop" intent.
- **Parallel** wins because the two tracks only overlap at the schema/scrub
  core and diverge entirely on input (live hooks vs. deliberate logging) and
  output (community publish vs. private store). Most of dual-use can proceed
  without waiting on v1.1.

**Key enabling insight:** experiment logging is *"deliberate, review-heavy"* —
records are created on purpose, not scraped from live hooks. The deliberate path
has zero dependency on the v1.1 plugin work.

## Decision 2 — Separate ExperimentRecord with shared base

**Chosen:** Extract a common base from `KajibaRecord`; both record types extend
it; `record_kind` discriminator.

**Why:** `KajibaRecord` carries coding-specific validators (turn_count match,
tool_call_counts add up) that don't apply to experiments — extending it with
optional null-for-coding fields would create a god-object with conditional
validation. Full duplication was rejected as wasteful given shared model/hardware
metadata + scrub log. A discriminated union over a shared base is the idiomatic
Pydantic v2 answer. Migration cost of existing records is real → tracked as a
research question.

## Decision 3 — Shared core, divergent tail

**Chosen:** reuse schema base + scrub primitives; branch eval scorer + private
store + analysis export; skip community publish/HuggingFace.

**Why:** the *private/internal* answer is the simplifier — experiment data
informs the user's own routing/fine-tune decisions and never enters the shared
dataset, so the entire publish path is irrelevant to it. Scoring also diverges
because coding-trajectory quality signals don't measure eval quality.

## Decision 4 — v1.1 intact; Phases 6-7 are shared foundation

**Chosen:** leave v1.1 Phases 6-9 unchanged; treat 6 (plugin) + 7 (capture) as
shared capture infrastructure for both coding sessions and live experiments.

**Why:** the *mixed input* answer means the live-capture half of dual-use
genuinely needs the plugin/hooks v1.1 is already building. Rather than duplicate
that, dual-use's live-capture phase (P-E in the seed) gates on Phase 6-7. This
reframes Phase 6 not as "just the coding pipeline" but as foundation for both —
a reason to build it well, not a reason to change it. Phase 6 plan left untouched.

## Consequence for REQUIREMENTS.md

The out-of-scope entry for model evaluation is now wrong. Updated to point at
v1.2 (see the Reverse-out-of-scope edit made in the same session).
