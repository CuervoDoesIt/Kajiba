# Phase 7: Turn Capture + Semantic PII Scrubbing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-05
**Phase:** 07-turn-capture-semantic-pii-scrubbing
**Areas discussed:** Model-metadata (remote vs local), GLiNER entity scope, Flagged-entity display in preview, GLiNER scrub coverage

---

## Model-metadata: remote vs local

### Q1 — How to satisfy model-metadata capture given remote-only live sessions?

| Option | Description | Selected |
|--------|-------------|----------|
| Both (degrade + 1 local run) | Graceful degradation for any backend + at least one local-Ollama (Hermes 3 8B) capture run so SC#3 is demonstrably TRUE | ✓ |
| Graceful degradation only | Store what's available; prove SC#3 via mocked ollama.show(); real local run waits for Phase 9 | |
| Local Ollama required | Make local Ollama the Phase 7 capture path; remote captures name/provider only | |

**User's choice:** Both (degrade + 1 local run)
**Notes:** Aligns with the v1.1 milestone goal of fine-tuning a local model on collected data; implementation must still work end-to-end on the dev's normal remote backend.

### Q2 — How much to infer for REMOTE models vs leave blank?

| Option | Description | Selected |
|--------|-------------|----------|
| Light inference + backend tag | model_name verbatim, is_local=false, parse slug for provider+model_family, set inference_backend; leave param/quant/hash None | ✓ |
| Minimal / honest only | Only model_name + provider + is_local; no slug parsing | |
| You decide | Defer enrichment depth to researcher/planner | |

**User's choice:** Light inference + backend tag
**Notes:** Maximizes useful runtime-context tags without fabricating unknown numbers for closed remote models.

---

## GLiNER entity scope

### Q1 — Which GLiNER entity label set by default?

| Option | Description | Selected |
|--------|-------------|----------|
| SC#4 core + location | person, company/organization, project, location | ✓ |
| SC#4 minimum only | person, company/organization, project | |
| Broad PII set | adds username/handle, job_title, etc. — max redaction, max code false positives | |

**User's choice:** SC#4 core + location
**Notes:** Small label set limits code false positives; the flag band absorbs ambiguity.

### Q2 — What should PRIV-03 code-FP calibration produce as an acceptance gate?

| Option | Description | Selected |
|--------|-------------|----------|
| Bounded: zero false auto-redacts | Code fixture with known-safe identifiers; assert NONE auto-redact at ≥0.7; flag-band allowed; document FP rate | ✓ |
| + code-term allowlist | Bounded option plus a maintained suppression allowlist | |
| Measure & document only | Record FP rate as baseline, no hard gate | |

**User's choice:** Bounded: zero false auto-redacts
**Notes:** Protects training-data utility (no silent code corruption) while privacy-max still wins on real PII via the flag band.

---

## Flagged-entity display in preview

### Q1 — How should 0.4–0.7 flagged entities appear in `kajiba preview` (minimal, no Phase 8 UI)?

| Option | Description | Selected |
|--------|-------------|----------|
| Summary panel + counts | Rich "⚠ Flagged for review (N)" panel: text + suggested label + confidence; flagged text left visible | ✓ |
| Counts only | Just "Flagged: N" in the scrub summary line | |
| Inline markers | Wrap flagged spans inline in previewed text | |

**User's choice:** Summary panel + counts
**Notes:** Reuses the existing `_render_preview(..., flagged_items=...)` channel; no new persisted state — Phase 8 owns pipeline_stage/resumability.

### Q2 — Recompute each preview, or persist semantic result?

| Option | Description | Selected |
|--------|-------------|----------|
| Recompute, stateless | GLiNER runs fresh each preview against staged raw record; within-run cache; Phase 8 owns persistence | ✓ |
| Persist to staging now | Write GLiNER redactions+flags into staged record on first scrub | |
| You decide | Defer to researcher/planner based on measured load time | |

**User's choice:** Recompute, stateless
**Notes:** Keeps the Phase 7/8 boundary clean and honors "scrubbing at CLI step."

---

## GLiNER scrub coverage

### Q1 — Which fields should the GLiNER semantic layer scan?

| Option | Description | Selected |
|--------|-------------|----------|
| Turns + tools, flag-only in tools | Auto-redact (≥0.7) in turn text; in tool_input/tool_output ONLY flag (never auto-redact) | ✓ |
| Conversation text only | GLiNER on turn values only; tool fields stay regex-only | |
| Turns + tools, auto-redact both | Auto-redact ≥0.7 everywhere including tool fields | |

**User's choice:** Turns + tools, flag-only in tools
**Notes:** Catches real names in file contents/commit headers (privacy-max) while never silently corrupting code in training data — directly resolves the PRIV-03 tension.

---

## Claude's Discretion

Delegated to researcher/planner (recorded in CONTEXT.md → Claude's Discretion):
- Turn-mapping mechanics (one `post_llm_call` → human + gpt turns; `conversation_history` for ordering/dedup only).
- Turn-scoped `on_session_end` save fix (fires per turn, not once per session — must accumulate and finalize once).
- Whether to register `pre_llm_call` as a 5th hook for interrupted-turn robustness.
- Tool buffering details (`turn_id` correlation, `result` JSON-string parse, `tool_call_id` dedup, status→tool_status).
- Recording `telemetry_schema_version` for forward-compat.
- GLiNER device (GPU vs CPU) loading/runtime.
- Exact regex→GLiNER ordering interaction with the `scrub_record` envelope.

## Deferred Ideas

- Full resumable HITL review workflow (`preview --raw`/`inspect`, `pipeline_stage`) → Phase 8.
- `pip install kajiba[hermes]` auto-registration → Phase 8.
- Cross-invocation caching/persistence of semantic scrub results → revisit in Phase 8.
- Reviewed-not-folded todo: `2026-06-04-fix-experiment-relog-dedup-cr01.md` (v1.2 experiment-store work, unrelated).
