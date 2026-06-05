# Phase 7: Turn Capture + Semantic PII Scrubbing - Context

**Gathered:** 2026-06-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Promote the Phase 6 debug-only hook stubs into **real capture**, and replace the
`scrubber_llm.py` stub with a **GLiNER semantic PII layer**. Concretely:

- **CAPT-02** — `post_llm_call` is wired into `ConversationTurn` assembly (user +
  assistant turns) instead of debug-logging only.
- **CAPT-03** — `post_tool_call` events are assembled into `ToolCall` objects and
  attached to the correct assistant turn via a pending-turn buffer (correlated by
  `turn_id` / `tool_call_id`).
- **CAPT-04** — model metadata (param count, quantization, family, context length)
  captured via `ollama.show()` for local models, with graceful degradation for
  remote backends; stored in `ModelMetadata`.
- **PRIV-01/02/03/04** — `scrubber_llm.py` becomes a GLiNER (`nvidia/gliner-pii`)
  semantic detector with locked confidence bands (≥0.7 auto-redact / ≥0.4 flag /
  <0.4 ignore), calibrated against code fixtures, gated behind the `[llm-scrub]`
  extra.

**Explicitly NOT in Phase 7 (belongs to Phase 8):** the full resumable HITL review
workflow (`kajiba preview --raw` / `kajiba inspect`, `pipeline_stage` persistence),
and `pip install kajiba[hermes]` packaging. Phase 7 only needs flagged entities to
*surface* in preview; it does not build the review/resume machinery.

</domain>

<decisions>
## Implementation Decisions

### Model Metadata Capture (CAPT-04)
- **D-01:** **Graceful degradation on ANY backend.** Always populate
  `model_name` / `provider` / `platform` / `is_local` from the hook kwargs.
  Call `ollama.show()` **only when a local Ollama model is detected**; when it
  succeeds, fill `parameter_count`, `quantization`, `model_family`,
  `context_window`, and `model_hash` (from the Ollama digest). Soft-import Ollama
  / handle its absence gracefully (psutil/pyyaml soft-dep pattern) — remote
  sessions must never error because Ollama is missing.
- **D-02:** **At least one real local-Ollama capture run is required** (Hermes 3 8B
  Q4) so SC#3 ("metadata captured from Ollama") is *demonstrably* TRUE on live data,
  not only proven against a mocked `ollama.show()`. The implementation must ALSO
  work end-to-end on the dev's normal remote backend (degradation path, D-01).
- **D-03:** **Remote-model enrichment = light slug inference, no fabrication.**
  Store `model_name` verbatim, set `is_local=false`, and parse the slug for
  `provider` + `model_family` (e.g. `anthropic`/`claude`,
  `openrouter`/`nemotron`). Set `HardwareProfile.inference_backend`
  (`ollama` | `openrouter` | `anthropic` | …). Leave `parameter_count` /
  `quantization` / `model_hash` **None** for closed remote models — do not guess.

### Semantic PII — GLiNER (PRIV-01/02/03/04)
- **D-04:** **Entity label set = `person`, `company/organization`, `project`,
  `location`** (SC#4 core + location as a common re-identifier). Small set on
  purpose to limit code false positives; the flag band absorbs ambiguity.
- **D-05:** **Confidence bands (carried, locked by PRIV-02 — do not re-derive):**
  ≥0.7 → auto-redact, ≥0.4 and <0.7 → flag for human review, <0.4 → ignore.
- **D-06:** **PRIV-03 calibration is a hard gate, not just a measurement.** Build a
  code-content fixture seeded with known-safe identifiers (variable/function names,
  library names like `pandas`/`React`). The test asserts **zero** of them
  auto-redact at ≥0.7 confidence; flag-band (0.4–0.7) hits are *allowed* (they're
  reviewable, not destructive). The observed false-positive rate is recorded in the
  test/artifact.
- **D-07:** **Asymmetric coverage (resolves the PRIV-03 tension).** GLiNER
  **auto-redacts (≥0.7) ONLY in conversation turn text** (`ConversationTurn.value`
  for user + assistant). In **`tool_input` / `tool_output`, GLiNER NEVER
  auto-redacts regardless of confidence — it only FLAGS.** The existing regex layer
  continues to scrub structured PII (paths/emails/keys) in tool fields as today.
  Rationale: catch real names in file contents/commit headers without ever silently
  corrupting code in training data.

### Flagged-Entity Surfacing in `kajiba preview` (SC#5)
- **D-08:** Add a Rich **"⚠ Flagged for review (N)"** panel to `kajiba preview`
  listing each flagged entity (text snippet, suggested GLiNER label, confidence).
  Flagged text is **left visible** (reviewer needs context). Auto-redacted (≥0.7)
  items are counted in `ScrubLog` (`potential_names_redacted` for names,
  `items_flagged` for the flag count). **Reuse the existing
  `_render_preview(..., flagged_items=...)` path in `cli.py`** — it already renders
  a flagged list (today fed by `flag_org_domains`); GLiNER flags extend the same
  channel.
- **D-09:** **Stateless recompute.** The semantic scrub (redactions + flags) is
  recomputed on each `kajiba preview` against the staged raw record — **no persisted
  scrubbed state and no `pipeline_stage` in Phase 7** (that is Phase 8). Use a
  within-run cache so GLiNER loads once per CLI invocation.

### Packaging (PRIV-04)
- **D-10:** Add `gliner` (and its torch/transformers deps) to the **existing
  `[llm-scrub]` extra** in `pyproject.toml` (currently `llm-scrub = []`), matching
  PRIV-04's literal `pip install kajiba[llm-scrub]`. Soft-import with graceful
  fallback when the extra is not installed (core pipeline stays import-clean and
  network-free per project constraints).

### Pipeline Composition
- **D-11:** **Regex first, then GLiNER.** Layer B (`scrubber.py`) runs, then the
  Layer C GLiNER detector runs on the regex-scrubbed text; GLiNER name redactions
  feed `ScrubLog.potential_names_redacted`. Scrubbing stays a **CLI-step** operation
  (never in hook callbacks — carried decision). Planner to confirm exact
  interaction/ordering with the existing `scrub_record` envelope.

### Claude's Discretion (delegated — not user decisions)
These were explicitly handed to the researcher/planner; capture them as **research
questions**, not gray areas already answered:

- **Turn-mapping mechanics:** one `post_llm_call` → a `human` turn (`user_message`)
  + a `gpt` turn (`assistant_response`); use `conversation_history` only for
  ordering/dedup so turns are not double-counted. Confirm against live shapes in
  `06-HOOK-KWARGS.md`.
- **Turn-scoped `on_session_end` (correctness fix):** per `06-HOOK-KWARGS.md`
  finding 2, `on_session_end` fires **after every `run_conversation` turn AND at CLI
  exit**, NOT once per session. The current `collector.on_session_end` immediately
  saves-to-staging — firing per turn would write N staging files. Planner MUST design
  accumulate-across-turns + finalize-once (on last end / CLI exit), keyed by
  `session_id`.
- **`pre_llm_call` (5th hook?):** decide whether to register `pre_llm_call` for
  robust user-turn capture when a turn is interrupted (no `post_llm_call` fires) vs.
  rely solely on `post_llm_call.user_message`. CAPT-02's wording names `pre_llm_call`,
  but `post_llm_call` already carries `user_message` — reconcile.
- **Tool buffering:** correlate tool calls to their assistant turn via `turn_id`;
  `result` is a **JSON string** (parse before storing structured output);
  `tool_call_id` is the dedup key; map `status` / `error_type` / `error_message` →
  `ToolCall.tool_status`.
- **Forward-compat:** record `telemetry_schema_version` (`"hermes.observer.v1"`,
  finding 1) so capture can detect an observer-schema bump (storage location is
  discretionary).
- **GLiNER device:** GPU (RTX 4070 8GB) vs CPU loading/runtime — planner's call.

### Folded Todos
None folded.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Hook Payload Contract (READ FIRST)
- `.planning/phases/06-environment-plugin-foundation/06-HOOK-KWARGS.md` — **THE
  authoritative live payload contract** for all four v0.15.x hooks (kwarg tables,
  8 cross-cutting findings, and the explicit Phase 7 CAPT-02/CAPT-03 mapping
  tables). Settles result-is-JSON-string, turn-scoped session-end, and the
  `turn_id`/`tool_call_id` correlation keys.
- `.planning/phases/06-environment-plugin-foundation/06-CONTEXT.md` — carried Phase
  6 decisions (HERMES_HOME resolution, plugin package layout, fault-tolerant hooks).

### Requirements & Scope
- `.planning/REQUIREMENTS.md` — CAPT-02/03/04, PRIV-01/02/03/04 (the locked bands
  and `nvidia/gliner-pii` model name live here).
- `.planning/ROADMAP.md` §"Phase 7" — the five success criteria this phase must make TRUE.

### Project Spec
- `docs/kajiba-project-spec.md` — full pipeline design: Layer B (regex) / Layer C
  (semantic) scrubbing model, the record schema, and controlled vocabularies.

### Existing Code (the integration surface)
- `src/kajiba/plugin/hooks.py` — `on_post_llm_call` / `on_post_tool_call` are
  debug-only stubs to promote to real capture; `on_session_end` dispatch needs the
  turn-scoped fix.
- `src/kajiba/collector.py` — `KajibaCollector`: `on_turn_complete` (single-role,
  needs adapting to the user+assistant pair shape), `_extract_model_metadata`,
  `_detect_hardware`, `_save_to_staging`, `_build_record`.
- `src/kajiba/scrubber_llm.py` — the stub to REPLACE with GLiNER. Note: current stub
  is generative/`model_fn`-shaped with string confidences; GLiNER is span-tagging
  with float scores — the interface changes (`confidence: float`, label set D-04).
- `src/kajiba/scrubber.py` — Layer B regex scrubber + `Redaction` / `FlaggedItem` /
  `ScrubResult` dataclasses + `ScrubLog` assembly to compose with (D-11).
- `src/kajiba/cli.py` — `preview` / `_render_preview(..., flagged_items=...)` (the
  reuse target for D-08), `scrub_record` call sites.
- `src/kajiba/schema.py` — `ConversationTurn`, `ToolCall`, `ModelMetadata`
  (`context_used` field exists), `HardwareProfile` (`inference_backend` field
  exists), `ScrubLog` (`potential_names_redacted`, `items_flagged` exist).

### External
- GLiNER PII model: `nvidia/gliner-pii` (Hugging Face) — the named PRIV-01 model;
  custom label set applied at inference (D-04).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`_render_preview(..., flagged_items=...)` (`cli.py`)** already renders a flagged
  list (today from `flag_org_domains`). GLiNER flags plug straight into this channel
  — no new rendering surface needed for D-08.
- **`FlaggedItem` / `Redaction` / `ScrubResult` (`scrubber.py`)** — established
  shapes for "redacted vs flagged"; the semantic layer should mirror them (float
  confidence instead of regex match) rather than invent new containers.
- **`ScrubLog.potential_names_redacted` / `items_flagged` (`schema.py`)** — already
  reserved for exactly this semantic output; no schema change needed to log counts.
- **`HardwareProfile.inference_backend` and `ModelMetadata.context_used`
  (`schema.py`)** — already exist; D-03 just needs to populate `inference_backend`.
- **`collector.on_session_start(session_id, model_config=None, *, model_name=None,
  platform=None)`** — already maps hook `model`→`model_name`, `platform`→`provider`.
- **Soft-dependency pattern** (`psutil`, `pyyaml`) — the template for the GLiNER /
  Ollama soft-imports (D-01, D-10).

### Established Patterns
- **Fault-tolerant hooks:** every handler wraps its body in try/except and never
  propagates to Hermes — keep this when promoting the stubs.
- **Scrub at CLI step, never in hooks** — carried hard rule; GLiNER (heavy) must not
  run in a hook callback.
- **Scrub on a deep copy** (`model_dump` → mutate → `model_validate`) so the raw
  staged record is never mutated.

### Integration Points
- `post_llm_call` / `post_tool_call` hook handlers → collector turn/tool buffer →
  `ConversationTurn` / `ToolCall` → `_build_record` → staging JSON.
- `kajiba preview` → load staged record → regex scrub (Layer B) → GLiNER scrub
  (Layer C) → `_render_preview` (redaction counts + flagged panel).
- Local Ollama (`ollama.show()`) is the only optional network/local-service touch —
  gated and soft (D-01); core stays offline.

</code_context>

<specifics>
## Specific Ideas

- **Dev machine reality (drives the metadata decision):** Hermes v0.15.1 native
  Windows, RTX 4070 8GB, remote OpenAI sub + Anthropic key, **no Ollama currently
  installed** (per `06-CONTEXT.md`). The "both" path (D-02) means installing Ollama +
  pulling Hermes 3 8B Q4 for the one local capture run that proves CAPT-04/SC#3.
- **The asymmetric-coverage idea (D-07)** is the user's preferred resolution to the
  privacy-max-vs-code-false-positive tension — auto-redact in prose, flag-only in
  tool/code fields. Treat it as a firm design constraint, not a suggestion.
- **Keep the Phase 7/8 line bright:** flagged entities just need to *appear* in
  preview (panel + counts). No persistence, no `pipeline_stage`, no resumable review
  — those are Phase 8.

</specifics>

<deferred>
## Deferred Ideas

- **Full resumable HITL review workflow** (`kajiba preview --raw` / `kajiba inspect`,
  `pipeline_stage` field, resume-without-reprocessing) → **Phase 8** (VAL-01/VAL-02).
- **`pip install kajiba[hermes]` auto-registration** → **Phase 8** (PLUG-04).
- **Cross-invocation caching/persistence of semantic scrub results** (raised under
  D-09) → revisit in Phase 8 alongside `pipeline_stage`.

### Reviewed Todos (not folded)
- **`2026-06-04-fix-experiment-relog-dedup-cr01.md`** — "Fix experiment re-log dedup
  data loss (CR-01) + Phase 11 review warnings." Matched at 0.6 on generic keyword
  overlap only (`data`, `phase`, `review`, `kajiba`). It is **v1.2 experiment-store /
  CLI** work, unrelated to v1.1 turn-capture/PII. Same disposition as Phase 6:
  deferred to its own task / Phase 11 follow-up.

</deferred>

---

*Phase: 07-turn-capture-semantic-pii-scrubbing*
*Context gathered: 2026-06-05*
