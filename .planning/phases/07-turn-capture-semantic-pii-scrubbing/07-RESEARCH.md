# Phase 7: Turn Capture + Semantic PII Scrubbing - Research

**Researched:** 2026-06-05
**Domain:** Hermes v0.15.x lifecycle-hook turn/tool capture + GLiNER semantic PII detection
**Confidence:** HIGH (hook contract live-verified in 06-HOOK-KWARGS; GLiNER/ollama APIs verified against official model card + repos; package legitimacy clean)

## Summary

This phase promotes the Phase 6 debug-only hook stubs (`on_post_llm_call` / `on_post_tool_call`) into real `ConversationTurn` / `ToolCall` assembly, fixes the turn-scoped `on_session_end` correctness bug, captures model metadata via `ollama.show()` with graceful remote degradation, and replaces the `scrubber_llm.py` stub with a GLiNER (`nvidia/gliner-PII`) semantic PII layer gated behind the `[llm-scrub]` extra.

The single most important upstream input is `06-HOOK-KWARGS.md` — it is a **live-verified payload contract** (session `20260605_111446_5a978c`, Hermes v0.15.1). It settles every turn/tool kwarg question with `[VERIFIED]` data: `post_llm_call` carries BOTH `user_message` and `assistant_response` (so one call = a `human` + a `gpt` turn), `result` is a JSON string, `args` is already a dict, `turn_id`/`tool_call_id` are the correlation keys, and `on_session_end` fires **per `run_conversation` turn AND at CLI exit** — not once per session. The current `collector.on_session_end` saves-to-staging immediately, which would write N staging files; this is the headline correctness fix.

On the privacy side, the named model is **`nvidia/gliner-PII`** (capital `PII` — the lowercase `nvidia/gliner-pii` in REQUIREMENTS/CONTEXT is a casing error; HF repo is `nvidia/gliner-PII`). It is a 570M-param GLiNER model (base `urchade/gliner_large-v2.1`), loaded with `GLiNER.from_pretrained(...)` and queried with `predict_entities(text, labels, threshold=...)` returning span dicts with a float `score`. The locked confidence bands (≥0.7 redact / ≥0.4 flag / <0.4 ignore) map directly onto that float. GLiNER + torch + transformers are heavy (multi-GB) and are NOT in the dev env today — soft-import behind `[llm-scrub]` is mandatory.

**Primary recommendation:** Implement a per-`session_id` accumulating collector (hooks append turns/tools, finalize-once on CLI-exit / last `on_session_end`), map Hermes `status="ok"`→`ToolStatusType "success"`, and add a `kajiba.scrubber_semantic` module that wraps GLiNER with a within-CLI-run singleton cache, composed AFTER regex `scrub_record` (D-11), auto-redacting ≥0.7 only in `ConversationTurn.value` and flag-only everywhere in tool fields (D-07). Do NOT register `pre_llm_call` — `post_llm_call.user_message` already carries the user turn (recommendation in §Pattern 3).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Turn/tool capture (CAPT-02/03) | Plugin hooks (`hooks.py`) → Collector | — | Hooks are the only live data ingress; must stay fault-tolerant + cheap (no scrubbing in hooks). |
| Turn accumulation + finalize | Collector (`KajibaCollector`) | — | Session state lives here; finalize-once writes one staging file. |
| Model metadata enrichment (CAPT-04) | Collector (`_extract_model_metadata` + new ollama helper) | `ModelMetadata` schema | Metadata derived once at session start / finalize; `ollama.show()` is an optional local-service touch. |
| Regex PII scrub (Layer B) | CLI step (`scrubber.scrub_record`) | — | Carried hard rule: scrub at CLI, never in hooks. Unchanged. |
| Semantic PII scrub (Layer C) | CLI step (new `scrubber_semantic`) | GLiNER model | Heavy ML; runs once per CLI invocation, after regex, on a deep copy. |
| Flagged-entity surfacing (SC#5) | CLI (`_render_preview(flagged_items=...)`) | — | Reuse existing flagged channel; no new render surface. |

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Graceful degradation on ANY backend. Always populate `model_name`/`provider`/`platform`/`is_local` from hook kwargs. Call `ollama.show()` only when a local Ollama model is detected; on success fill `parameter_count`, `quantization`, `model_family`, `context_window`, `model_hash` (from Ollama digest). Soft-import Ollama; remote sessions must never error if Ollama is missing.
- **D-02:** At least one real local-Ollama capture run is REQUIRED (Hermes 3 8B Q4) so SC#3 is demonstrably TRUE on live data, not only mocked. Implementation must ALSO work end-to-end on the dev's normal remote backend (D-01 degradation path).
- **D-03:** Remote-model enrichment = light slug inference, no fabrication. Store `model_name` verbatim, `is_local=false`, parse slug for `provider` + `model_family`. Set `HardwareProfile.inference_backend`. Leave `parameter_count`/`quantization`/`model_hash` None for closed remote models.
- **D-04:** Entity label set = `person`, `company/organization`, `project`, `location`. Small set on purpose to limit code false positives; flag band absorbs ambiguity.
- **D-05:** Confidence bands (locked by PRIV-02 — DO NOT re-derive): ≥0.7 → auto-redact, ≥0.4 and <0.7 → flag, <0.4 → ignore.
- **D-06:** PRIV-03 calibration is a HARD GATE. Build a code-content fixture seeded with known-safe identifiers (variable/function names, `pandas`/`React`). Assert ZERO auto-redact at ≥0.7; flag-band (0.4–0.7) hits allowed. Record observed false-positive rate in the test/artifact.
- **D-07:** Asymmetric coverage. GLiNER auto-redacts (≥0.7) ONLY in conversation turn text (`ConversationTurn.value` user+assistant). In `tool_input`/`tool_output`, GLiNER NEVER auto-redacts regardless of confidence — FLAG only. Existing regex layer continues to scrub structured PII in tool fields.
- **D-08:** Add a Rich "⚠ Flagged for review (N)" panel to `kajiba preview` listing each flagged entity (snippet, suggested GLiNER label, confidence). Flagged text left VISIBLE. Auto-redacted items counted in `ScrubLog` (`potential_names_redacted` for names, `items_flagged` for flag count). REUSE the existing `_render_preview(..., flagged_items=...)` path.
- **D-09:** Stateless recompute. Semantic scrub recomputed each `kajiba preview` against the staged raw record — NO persisted scrubbed state, NO `pipeline_stage` in Phase 7. Within-run cache so GLiNER loads once per CLI invocation.
- **D-10:** Add `gliner` (+ torch/transformers) to the existing `[llm-scrub]` extra in `pyproject.toml` (currently `llm-scrub = []`), matching PRIV-04's literal `pip install kajiba[llm-scrub]`. Soft-import with graceful fallback; core stays import-clean and network-free.
- **D-11:** Regex first, then GLiNER. Layer B runs, then Layer C GLiNER runs on the regex-scrubbed text; GLiNER name redactions feed `ScrubLog.potential_names_redacted`. Scrubbing stays a CLI-step operation, never in hook callbacks.

### Claude's Discretion (resolved in this research — see §Architecture Patterns)

Turn-mapping mechanics, turn-scoped `on_session_end`, the `pre_llm_call` 5th-hook question, tool buffering, forward-compat `telemetry_schema_version`, and GLiNER device selection were delegated. Each is resolved with an evidence-backed recommendation below.

### Deferred Ideas (OUT OF SCOPE)

- Full resumable HITL review workflow (`kajiba preview --raw` / `kajiba inspect`, `pipeline_stage` field, resume-without-reprocessing) → **Phase 8** (VAL-01/VAL-02).
- `pip install kajiba[hermes]` auto-registration → **Phase 8** (PLUG-04).
- Cross-invocation caching/persistence of semantic scrub results → **Phase 8**.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CAPT-02 | User + assistant turns assembled into `ConversationTurn` objects | §Pattern 1 (turn mapping from `post_llm_call`), live-verified kwargs in 06-HOOK-KWARGS |
| CAPT-03 | Tool calls assembled into `ToolCall` and attached to correct turn via pending buffer | §Pattern 2 (tool buffering via `turn_id`/`tool_call_id`), Hermes→schema status mapping |
| CAPT-04 | Model metadata captured via `ollama.show()` into `ModelMetadata` | §Pattern 4 (ollama.show soft-import + response fields), D-01/D-03 degradation |
| PRIV-01 | `scrubber_llm.py` stub → GLiNER `nvidia/gliner-PII` | §Standard Stack, §Pattern 5 (GLiNER API) |
| PRIV-02 | Auto-redact ≥0.7, flag ≥0.4, ignore <0.4 | §Pattern 6 (band → float score mapping) — LOCKED, implement only |
| PRIV-03 | Calibrate against code-content fixtures | §Validation Architecture (calibration gate test), D-06 |
| PRIV-04 | `gliner` added as `[llm-scrub]` extra | §Standard Stack install, §Don't Hand-Roll, D-10 |

## Standard Stack

### Core (new in this phase)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `gliner` | 0.2.26 (verified PyPI 2026-06-05) | Span-tagging NER for semantic PII; loads `nvidia/gliner-PII` | The named PRIV-01 model is a GLiNER checkpoint; `gliner` is the canonical loader (`GLiNER.from_pretrained` / `predict_entities`). [VERIFIED: PyPI] [CITED: huggingface.co/nvidia/gliner-PII] |
| `torch` | 2.12.0 (verified PyPI) | GLiNER inference backend (GPU/CPU) | GLiNER is a PyTorch transformer; required transitively. [VERIFIED: PyPI] |
| `transformers` | 5.x (verified PyPI) | Tokenizer/backbone for GLiNER | GLiNER depends on it; pulled transitively by `gliner`. [VERIFIED: PyPI] |
| `ollama` | 0.6.2 (verified PyPI) | `ollama.show()` for local-model metadata (CAPT-04) | Official Ollama Python client; `show()` returns `details.parameter_size`/`quantization_level`/`family` + `model_info.*context_length` + `digest`. [VERIFIED: PyPI] [CITED: github.com/ollama/ollama-python, ollama.readthedocs.io/en/api] |

**Model:** `nvidia/gliner-PII` — 570M params, base `urchade/gliner_large-v2.1`, NVIDIA Open Model License, span output `{start, end, text, label, score}`. Strict-F1 0.64–0.87 on PII benchmarks at threshold 0.3. [CITED: huggingface.co/nvidia/gliner-PII]

> **Model-name correction (ACTION for planner):** REQUIREMENTS.md and 07-CONTEXT both write `nvidia/gliner-pii` (lowercase). The actual HF repo is **`nvidia/gliner-PII`** (uppercase `PII`). HF repo IDs are case-sensitive — `from_pretrained("nvidia/gliner-pii")` will 404. Use `nvidia/gliner-PII` in code; flag the doc typo for a one-line REQUIREMENTS fix. [VERIFIED: HF web fetch returned 404-free page only for capital `PII`]

### Supporting (already present, reused)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `psutil` / `pyyaml` | soft-dep | Template for GLiNER/Ollama soft-import pattern | Mirror their `try: import / except ImportError: fallback` shape. |
| `rich` | >=13.0 | Flagged panel rendering | Already wired in `_render_preview`. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `gliner` PyPI loader | onnxruntime export of GLiNER | gliner already optionally pulls `onnxruntime`; ONNX path avoids torch but loses GPU ease and is not the documented `from_pretrained` path. Stay with torch path; D-10 already accepts torch weight. |
| `nvidia/gliner-PII` | `knowledgator/gliner-pii-*` (small/base/large/edge) | Knowledgator variants are smaller/faster but PRIV-01 NAMES the NVIDIA model — locked, do not substitute. (Edge/small noted only as a fallback IF 570M proves too heavy for 8GB during the live run.) |
| `ollama` Python client | parse `~/.ollama` modelfiles directly | Client is the supported API; direct parsing is brittle. Use `ollama.show()`. |

**Installation:**
```bash
pip install kajiba[llm-scrub]    # pulls gliner -> torch, transformers; ollama for CAPT-04
```

**Version verification (run 2026-06-05):**
```
gliner   0.2.26   (PyPI)
ollama   0.6.2    (PyPI)
torch    2.12.0   (PyPI, cp313 win_amd64 wheel available)
transformers 5.x  (PyPI)
```
Dev env: Python 3.13.3, RTX 4070 Laptop 8GB, driver 595.97, CUDA-capable (Ada/Lovelace — on GLiNER's supported GPU list). None of gliner/torch/ollama/transformers currently installed (confirms soft-import necessity).

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `gliner` | PyPI | est. 2yr (0.1.0→0.2.26) | high | github.com/urchade/GLiNER | [OK] | Approved |
| `ollama` | PyPI | est. 1.5yr | very high | github.com/ollama/ollama-python | [OK] | Approved |
| `torch` | PyPI | mature | massive | github.com/pytorch/pytorch | [OK] | Approved |
| `transformers` | PyPI | mature | massive | github.com/huggingface/transformers | [OK] | Approved |

`slopcheck install` (v0.6.1) ran 2026-06-05: "scanned 4 packages — 4 OK". No postinstall-script risk (Python wheels). 
**Packages removed due to [SLOP]:** none. **Packages flagged [SUS]:** none.

> Note: `slopcheck install` proceeds to actually run `pip install` after the OK verdict. If a task wants verification WITHOUT installing, use `slopcheck scan` or `pip index versions <pkg>` instead.

## Architecture Patterns

### System Architecture Diagram

```
LIVE HERMES SESSION (v0.15.1)
        │
        ▼  (per turn)
  ┌─────────────────────────────────────────────────────────────┐
  │ plugin/hooks.py  (fault-tolerant, NO scrub, cheap)           │
  │                                                              │
  │ on_session_start ─ session_id, model, platform ─────┐        │
  │ post_llm_call    ─ user_message, assistant_response,│        │
  │                    turn_id, conversation_history ───┤        │
  │ post_tool_call   ─ tool_name, args(dict),           │        │
  │                    result(JSON str), tool_call_id,  │        │
  │                    turn_id, status/error_* ─────────┤        │
  │ on_session_end   ─ session_id, completed,           │        │
  │                    interrupted  (FIRES PER TURN!) ──┤        │
  └─────────────────────────────────────────────────────┼────────┘
                                                         ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ KajibaCollector  (accumulate-by-session_id, finalize-once)   │
  │  _conversations[]  ← human turn + gpt turn per post_llm_call │
  │  _pending_tools{turn_id: [ToolCall]} ← buffer, dedup by      │
  │                    tool_call_id, attach to that turn's gpt   │
  │  _model_metadata   ← hook kwargs + optional ollama.show()    │
  │  finalize() → _build_record() → ONE staging JSON             │
  └─────────────────────────────────────────────────────────────┘
                                                         │
        ════════════ CLI-time (kajiba preview) ═════════▼════════
  ┌─────────────────────────────────────────────────────────────┐
  │ load staged raw record (deep copy)                           │
  │   → Layer B  scrubber.scrub_record   (regex; structured PII) │
  │   → Layer C  scrubber_semantic       (GLiNER on scrubbed txt)│
  │        ConversationTurn.value : redact ≥0.7 + flag 0.4–0.7   │
  │        tool_input/tool_output : FLAG ONLY (never redact)     │
  │   → ScrubLog (potential_names_redacted, items_flagged)       │
  │   → _render_preview(flagged_items=[...])  ⚠ panel            │
  └─────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
src/kajiba/
├── plugin/hooks.py        # promote on_post_llm_call / on_post_tool_call; fix end dispatch
├── collector.py           # accumulate-by-session, finalize-once, ollama metadata helper
├── scrubber.py            # Layer B (unchanged)
├── scrubber_semantic.py   # NEW — GLiNER Layer C (replaces scrubber_llm.py stub role)
├── scrubber_llm.py        # keep file or re-point; new module is scrubber_semantic
└── cli.py                 # preview wires Layer C + flagged panel
tests/
├── fixtures/code_content_pii.json   # NEW — D-06 calibration fixture
├── test_collector.py      # extend: paired-turn mapping, tool buffer, turn-scoped end
├── test_scrubber_semantic.py        # NEW — band logic, asymmetric coverage, calibration gate
└── test_plugin.py         # extend: hooks call collector (not just debug-log)
```

### Pattern 1: One `post_llm_call` → a `human` turn + a `gpt` turn (CAPT-02)

**What:** Each `post_llm_call` carries BOTH `user_message` and `assistant_response` ([VERIFIED] in 06-HOOK-KWARGS). Emit two `ConversationTurn`s per call: `from="human"` (value=`user_message`) then `from="gpt"` (value=`assistant_response`).

**When:** On every `post_llm_call`. Use `conversation_history` (list of `{role, content}`) ONLY for ordering/dedup sanity — never re-ingest it as turns (that double-counts).

**Reconciliation with existing `on_turn_complete`:** the current `collector.on_turn_complete(turn: dict)` is single-role (`turn["role"]`/`turn["content"]`). Phase 7 adds a paired entry point (e.g. `on_llm_turn(user_message, assistant_response, turn_id, ...)`) that appends both turns, OR calls `on_turn_complete` twice. Keep `on_turn_complete` for back-compat (tests in `test_collector.py` use it) and add the paired method.

```python
# new collector method — append BOTH turns, scrub deferred to CLI
def on_llm_turn(self, *, user_message, assistant_response, turn_id=None, **_):
    if user_message:
        self._conversations.append(ConversationTurn(**{"from": "human"}, value=user_message))
    gpt = ConversationTurn(**{"from": "gpt"}, value=assistant_response or "")
    self._conversations.append(gpt)
    self._last_gpt_turn_id = turn_id          # so post_tool_call can attach
    # flush any tool calls already buffered for this turn_id:
    for tc in self._pending_tools.pop(turn_id, []):
        (gpt.tool_calls or gpt.__dict__.setdefault("tool_calls", [])).append(tc)
```

### Pattern 2: Tool buffering + Hermes→schema status mapping (CAPT-03)

**What:** Buffer each `ToolCall` keyed by `turn_id`; dedup on `tool_call_id`; parse `result` (JSON string) before storing; attach to the `gpt` turn for that `turn_id`. Tool calls may arrive before OR after the `post_llm_call` that owns the turn — buffer covers both orders.

**Critical mapping — `status="ok"` is NOT a `ToolStatusType`:** Hermes sends `status="ok"` on success; the schema's `ToolStatusType = Literal["success","failure","timeout","error"]`. Map `"ok" → "success"`; on `error_type`/`error_message` populated → `"error"` (or `"timeout"` if the error class/message indicates timeout). The existing `_build_record` counts `successful_tool_calls` by `tool_status == "success"`, so the mapping must produce `"success"` exactly.

```python
status = "success" if kw.get("status") == "ok" and not kw.get("error_type") else "error"
result_str = kw.get("result", "")
try:
    parsed = json.loads(result_str)            # result is a JSON STRING (finding 3)
    tool_output = json.dumps(parsed)[:2000]    # store normalized; keep <=2000 like on_turn_complete
except (json.JSONDecodeError, TypeError):
    tool_output = (result_str or "")[:2000]
tc = ToolCall(tool_name=kw["tool_name"],
              tool_input=json.dumps(kw.get("args") or {})[:2000],   # args is already a dict
              tool_output=tool_output,
              tool_status=status,
              latency_ms=kw.get("duration_ms"))
# dedup by tool_call_id, then buffer under turn_id
```

### Pattern 3: `pre_llm_call` — DO NOT register (recommendation)

**Recommendation:** Rely solely on `post_llm_call.user_message`; do NOT add a 5th `pre_llm_call` hook in Phase 7.

**Rationale:** 06-HOOK-KWARGS [VERIFIED] that `post_llm_call` carries `user_message` — the user turn is fully available without `pre_llm_call`. CAPT-02's wording names `pre_llm_call` historically (v0.6.0 assumption) but the live v0.15.x contract supersedes it. The only thing `pre_llm_call` would add is capturing an interrupted turn where the user typed but no `post_llm_call` fired; that edge is better handled by the `on_session_end.interrupted=True` signal (already available) plus the finalize-once design — an interrupted turn simply has no assistant response. Registering `pre_llm_call` would also collide with the deferred PLUG-05 (`pre_llm_call` context injection, Phase 8) — keep that hook unclaimed. **If** the live D-02 run reveals lost user turns on interruption, revisit; flag as the one open question.

### Pattern 4: Model metadata — ollama.show() with graceful degradation (CAPT-04)

**What:** At session start (or finalize), always set `model_name`/`provider`/`platform`/`is_local` from hook kwargs (D-01). If a LOCAL Ollama model is detected, soft-import `ollama` and call `ollama.show(model_name)`; map its response into `ModelMetadata`. On remote backends, do slug inference only (D-03) and leave param/quant/hash None.

**`ollama.show()` response fields** [CITED: ollama.readthedocs.io/en/api, github.com/ollama/ollama-python]:
- `details.parameter_size` (e.g. `"8.0B"`) → `ModelMetadata.parameter_count`
- `details.quantization_level` (e.g. `"Q4_0"`) → `quantization`
- `details.family` (e.g. `"llama"`) → `model_family`
- `model_info["<arch>.context_length"]` (e.g. `llama.context_length`) → `context_window`
- `digest` (SHA256, from `/api/tags` / show) → `model_hash`

```python
def _enrich_from_ollama(model_name: str) -> dict:
    try:
        import ollama                          # soft-dep (D-01); remote sessions skip this
    except ImportError:
        return {}
    try:
        resp = ollama.show(model_name)         # dict-like; ollama 0.6.x returns a model object
    except Exception:                          # ollama.ResponseError / httpx ConnectError if server down
        return {}
    d = resp.get("details", {}) if isinstance(resp, dict) else getattr(resp, "details", {})
    info = resp.get("model_info", {}) if isinstance(resp, dict) else getattr(resp, "modelinfo", {}) or {}
    ctx = next((v for k, v in (info or {}).items() if k.endswith(".context_length")), None)
    return {"parameter_count": d.get("parameter_size"),
            "quantization": d.get("quantization_level"),
            "model_family": d.get("family"),
            "context_window": ctx,
            "model_hash": (resp.get("digest") if isinstance(resp, dict) else getattr(resp, "digest", None))}
```

**`is_local` / "is this Ollama" detection:** `platform`/`provider` from hooks is `"cli"` for both local and remote in the captured session (06-HOOK-KWARGS) — `platform` alone does NOT distinguish local. Detect local by: provider already known to be `ollama`, OR `ollama.show()` succeeding for the model name. Recommendation: attempt `ollama.show()` only when `provider == "ollama"` OR the model slug has no provider prefix (bare name like `hermes3:8b`), to avoid a failing network call on every remote session.

**Schema confirmation:** `ModelMetadata` has `parameter_count` (str), `quantization`, `model_family`, `context_window`, `context_used`, `provider`, `is_local`, `model_hash` — all fields exist. `HardwareProfile.inference_backend` exists (set per D-03). NO schema change needed. `provider` is a `Literal["ollama","vllm","sglang","llamacpp","openrouter","custom"]` — slug inference for remote backends like Anthropic must map to `"custom"` or `"openrouter"` (Anthropic is not in the literal — use `"custom"` and record the real backend in `inference_backend` which is a free `str`).

### Pattern 5: GLiNER load + inference (PRIV-01)

```python
# scrubber_semantic.py — soft-import; module import stays clean without [llm-scrub]
def _get_model():
    global _MODEL
    if _MODEL is None:
        from gliner import GLiNER            # raises ImportError if extra not installed
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _MODEL = GLiNER.from_pretrained("nvidia/gliner-PII").to(device)  # capital PII
    return _MODEL

LABELS = ["person", "company", "organization", "project", "location"]  # D-04

def detect_entities(text: str, threshold: float = 0.4):
    if not text:
        return []
    model = _get_model()
    return model.predict_entities(text, LABELS, threshold=threshold)
    # each -> {"start","end","text","label","score": float}
```

**Device (discretionary, resolved):** Use CUDA when available (RTX 4070 8GB is on GLiNER's supported list; 570M model fits comfortably in 8GB — well under VRAM with Hermes-3-8B-Q4 NOT loaded simultaneously, since scrubbing is a CLI step, not in-session). Fall back to CPU automatically via `torch.cuda.is_available()`. First load downloads ~1.5–2.4GB of weights from HF (one-time; needs network at install/first-run only — acceptable because Layer C is the OPTIONAL extra, core stays offline).

**Threshold strategy:** call `predict_entities` ONCE at `threshold=0.4` (the flag floor) and bucket each span by its float `score`: `≥0.7 redact / 0.4–0.7 flag / <0.4 already excluded by threshold`. One inference pass, not two.

### Pattern 6: Asymmetric coverage composition (D-07, D-11)

**What:** Compose AFTER regex. For `ConversationTurn.value`: apply redaction for `score≥0.7`, flag for `0.4–0.7`. For `tool_input`/`tool_output`: collect spans as FLAGS only (any `score≥0.4`), NEVER mutate text.

**Composition with `scrub_record`:** the existing `scrub_record` returns `(scrubbed_record, ScrubLog)` and works on a `model_dump`→mutate→`model_validate` deep copy. Recommended shape: a new `scrub_record_semantic(scrubbed_record) -> (record, names_redacted_count, list[FlaggedItem])` that runs GLiNER on the already-regex-scrubbed text, mirroring the deep-copy discipline. Then in `cli.preview`:

```python
scrubbed, scrub_log = scrub_record(record)                 # Layer B (unchanged)
try:
    scrubbed, names_redacted, semantic_flags = scrub_record_semantic(scrubbed)  # Layer C
    scrub_log.potential_names_redacted = names_redacted
    scrub_log.items_flagged += len(semantic_flags)
except SemanticScrubUnavailable:                           # [llm-scrub] not installed
    semantic_flags = []
all_flagged = existing_org_domain_flags + semantic_flags   # extend the SAME channel (D-08)
```

**Replacement tag:** redacted names should use a tag consistent with regex placeholders, e.g. `[REDACTED_NAME]` / `[REDACTED_PERSON]`, so the existing `_build_highlighted_text` regex `\[REDACTED_\w+\]` highlights them in `--detail` mode for free.

### Pattern 7: `FlaggedItem` shape for the preview panel (D-08)

`_render_preview` iterates `flagged_items` reading `item.text` and `item.reason`. GLiNER flags must expose those attributes. Reuse `scrubber.FlaggedItem` (has `text`, `category`, `reason`, `start`, `end`). Build `reason=f"GLiNER {label} (confidence {score:.2f})"` so the panel shows snippet + suggested label + confidence per D-08. No new container needed.

### Anti-Patterns to Avoid

- **Re-ingesting `conversation_history` as turns** → double-counts every turn. Use it for ordering/dedup only.
- **Scrubbing inside hooks** → carried hard rule; GLiNER is heavy and would block/disrupt the Hermes session. CLI step only.
- **Treating first `on_session_end` as session-final** → it fires per turn. Finalize-once or you write N staging files (see Pattern below).
- **`from_pretrained("nvidia/gliner-pii")`** → 404. Repo is `nvidia/gliner-PII`.
- **Hard `import gliner` / `import ollama` at module top** → breaks core import-cleanliness (D-10/D-01). Soft-import inside functions.
- **Storing Hermes `status="ok"` directly** → fails `ToolStatusType` validation. Map to `"success"`.

### Turn-Scoped `on_session_end` Fix (correctness — the headline change)

**Problem ([VERIFIED] finding 2):** `on_session_end` fires after EVERY `run_conversation` turn AND at CLI exit. Current `collector.on_session_end` immediately `_save_to_staging()` (and in continuous mode builds+submits). Per-turn firing ⇒ N staging files / N submits per session.

**Recommended design — accumulate-across-turns + finalize-once, keyed by `session_id`:**
- Hooks APPEND turns/tools across all `post_llm_call`/`post_tool_call` events; they do NOT finalize.
- `on_session_end` becomes a turn-boundary marker: record `completed`/`interrupted` as candidate outcome signals; do NOT write staging here.
- Finalize-once trigger options (planner picks):
  1. **CLI-exit detection** — Hermes calls `on_session_end` at CLI exit; distinguish "last end" by an idle/teardown signal. 06-HOOK-KWARGS does not give a definitive "is-final" flag, so this is inference-based (LOW confidence) — needs the D-02 live run to confirm.
  2. **Idempotent write keyed by `session_id`** (RECOMMENDED, robust): every `on_session_end` rewrites the SAME staging file `session_{session_id}.json` (overwrite, not append). N firings ⇒ 1 file that grows with each turn. This is simple, needs no "is-final" detection, and matches the existing `_save_to_staging` filename (`session_{session_id}.json`) which already overwrites. The last write wins with the complete trajectory.
- **Continuous-mode caveat:** the current continuous path auto-submits inside `on_session_end`. Under per-turn firing that would submit repeatedly. Gate continuous auto-submit so it only runs once per session (e.g. a `_finalized` flag set on first submit, or move continuous submit to the idempotent-overwrite model and dedup downstream by `submission_hash`). Flag for the planner: the idempotent-overwrite staging design is safe; continuous auto-submit needs an explicit once-guard.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Semantic name/org/project detection | Regex name lists or LLM-prompt parsing | `gliner` + `nvidia/gliner-PII` | Span-tagging with calibrated float scores; the spec's old LLM-prompt approach (lines 312-336) is 20-50x slower and lower precision (REQUIREMENTS "Out of Scope"). |
| Local model metadata extraction | Parsing `~/.ollama` modelfiles | `ollama.show()` | Official client returns structured `details` + `model_info` + `digest`. |
| Tool result parsing | Custom string splitting | `json.loads(result)` | `result` is a JSON string (finding 3) — parse, don't regex. |
| "Is final session-end" detection | Timer/heuristic guesswork | Idempotent overwrite keyed by `session_id` | Avoids needing a definitive final-event signal Hermes doesn't expose. |
| Flagged-entity rendering | New Rich panel | `_render_preview(flagged_items=...)` | Channel already exists; just feed it `FlaggedItem`s. |

**Key insight:** GLiNER replaces the entire generative-LLM PII approach the spec originally sketched. The locked decisions exist precisely to keep GLiNER from corrupting code (asymmetric coverage + calibration gate). Build the plumbing, not new ML.

## Runtime State Inventory

> This is a code-promotion + new-module phase, not a rename/migration. Brief inventory for completeness.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Staging JSON at `<HERMES_HOME>/kajiba/staging/session_*.json` | None for existing records; new captures write here. D-09: no `pipeline_stage` persisted. |
| Live service config | Hermes plugin installed editable in Hermes venv (`%LOCALAPPDATA%\hermes\...\venv`, finding 8) | Re-copy/re-install plugin after promoting hooks (native-Windows COPY workflow, finding 7). |
| OS-registered state | None | None — verified: no scheduled tasks / services. |
| Secrets/env vars | `KAJIBA_DEBUG`, `HERMES_HOME` | Unchanged. |
| Build artifacts | `kajiba` editable install in Hermes venv (v0.2.0) | Reinstall after adding `[llm-scrub]` deps so the extra resolves; GLiNER weights download to HF cache on first run. |

## Common Pitfalls

### Pitfall 1: Per-turn `on_session_end` writes N staging files
**What goes wrong:** Naively promoting hooks while leaving `on_session_end` finalizing ⇒ a staging file (or submit) per turn.
**Why:** [VERIFIED] turn-scoped firing (finding 2).
**Avoid:** Idempotent overwrite keyed by `session_id` (Pattern above). **Warning sign:** multiple `session_*.json` for one session, or `turn_count` that resets.

### Pitfall 2: `status="ok"` ValidationError
**What goes wrong:** `ToolCall(tool_status="ok")` raises — not in the literal.
**Avoid:** Map `"ok"→"success"`. **Warning sign:** ToolCall construction throwing, swallowed by the fault-tolerant try/except (silent data loss).

### Pitfall 3: `nvidia/gliner-pii` 404
**What goes wrong:** Lowercase repo id returns 404 from HF.
**Avoid:** Use `nvidia/gliner-PII`. **Warning sign:** `from_pretrained` HTTP 404 / repo-not-found.

### Pitfall 4: GLiNER auto-redacting code identifiers
**What goes wrong:** GLiNER flags `pandas`/`React`/variable names as `company`/`project` at high confidence, corrupting training data.
**Why:** Generalist NER over-fires on capitalized tech terms.
**Avoid:** Asymmetric coverage (D-07: never redact in tool fields) + calibration gate (D-06: zero auto-redact on code fixture). **Warning sign:** code tokens replaced with `[REDACTED_*]` in conversation prose.

### Pitfall 5: GLiNER/torch import breaking core
**What goes wrong:** Top-level `import gliner` makes `kajiba` un-importable without the extra; breaks offline core constraint.
**Avoid:** Soft-import inside functions; `SemanticScrubUnavailable` fallback. **Warning sign:** `kajiba preview` raising `ModuleNotFoundError: gliner` instead of degrading gracefully.

### Pitfall 6: VRAM contention during the live D-02 run
**What goes wrong:** Running GLiNER (CUDA) while Hermes-3-8B-Q4 occupies the 8GB GPU could OOM.
**Avoid:** Scrubbing is a CLI step run AFTER the session — Ollama model need not be resident. If both load, fall GLiNER back to CPU. **Warning sign:** CUDA OOM on `preview` right after a live session.

## Code Examples

### Tool status mapping (verified literals)
```python
# ToolStatusType = Literal["success","failure","timeout","error"]  (schema.py:101)
# Hermes sends status="ok"; map it:
def _map_status(kw: dict) -> str:
    if kw.get("error_type") or kw.get("error_message"):
        et = (kw.get("error_type") or "").lower()
        return "timeout" if "timeout" in et else "error"
    return "success" if kw.get("status") == "ok" else "error"
```

### GLiNER band bucketing (one pass, D-05 locked)
```python
spans = model.predict_entities(text, LABELS, threshold=0.4)   # flag floor
redactions = [s for s in spans if s["score"] >= 0.7]          # auto-redact (turn.value only)
flags      = [s for s in spans if 0.4 <= s["score"] < 0.7]    # flag for review
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Spec Layer C: generative LLM prompt for PII (spec lines 312-336, string "high/medium/low" confidence) | GLiNER span-tagging with float scores | This phase (PRIV-01) | Faster, deterministic, calibratable. `scrubber_llm.py`'s `model_fn`/string-confidence interface is obsolete — replaced by float `score`. |
| `pre_llm_call` for user turn (v0.6.0 CAPT-02 wording) | `post_llm_call.user_message` carries it (v0.15.x) | Phase 6 live capture | No 5th hook needed (Pattern 3). |
| `on_session_end` = session-final | Turn-scoped (per `run_conversation` + CLI exit) | v0.15.x (finding 2) | Finalize-once redesign required. |

**Deprecated/outdated:**
- `scrubber_llm.py` `scrub_semantic(text, model_fn)` + `SemanticRedaction(confidence: str)` — replaced by float-score GLiNER. The new module is `scrubber_semantic.py`.
- REQUIREMENTS/CONTEXT `nvidia/gliner-pii` casing — should be `nvidia/gliner-PII`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=7.0 + pytest-cov (`[tool.pytest.ini_options]`, `testpaths=["tests"]`, `addopts="-v"`) |
| Config file | `pyproject.toml` |
| Quick run command | `python -m pytest tests/test_scrubber_semantic.py -x` |
| Full suite command | `python -m pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CAPT-02 | one `post_llm_call` → human+gpt turns; no double-count from history | unit | `python -m pytest tests/test_collector.py -k llm_turn -x` | ❌ Wave 0 (extend) |
| CAPT-03 | tool buffered by turn_id, dedup tool_call_id, result JSON parsed, status ok→success | unit | `python -m pytest tests/test_collector.py -k tool_buffer -x` | ❌ Wave 0 |
| CAPT-03 | turn-scoped on_session_end → exactly ONE staging file per session | unit | `python -m pytest tests/test_collector.py -k session_end_once -x` | ❌ Wave 0 |
| CAPT-04 | ollama.show() mapped into ModelMetadata (mocked) | unit | `python -m pytest tests/test_collector.py -k ollama_metadata -x` | ❌ Wave 0 |
| CAPT-04 | remote degradation: no ollama → slug inference, params None (D-03) | unit | `python -m pytest tests/test_collector.py -k remote_degrade -x` | ❌ Wave 0 |
| CAPT-04 | LIVE: real local-Ollama run (Hermes 3 8B Q4) populates real param/quant (D-02) | manual | documented walkthrough + captured staging JSON artifact | ❌ manual (D-02) |
| PRIV-01 | GLiNER loads `nvidia/gliner-PII`, detects person/company/project/location | integration | `python -m pytest tests/test_scrubber_semantic.py -k detect -x` (needs [llm-scrub]) | ❌ Wave 0 |
| PRIV-02 | band logic: ≥0.7 redact, 0.4–0.7 flag, <0.4 ignore (mock scores) | unit | `python -m pytest tests/test_scrubber_semantic.py -k bands -x` | ❌ Wave 0 |
| PRIV-03 | CALIBRATION GATE: zero auto-redact ≥0.7 on code fixture; record FP rate (D-06) | integration | `python -m pytest tests/test_scrubber_semantic.py -k calibration -x` | ❌ Wave 0 |
| PRIV-02/D-07 | asymmetric: tool fields FLAG-only, never redacted | unit | `python -m pytest tests/test_scrubber_semantic.py -k asymmetric -x` | ❌ Wave 0 |
| PRIV-04 | soft-import: core imports clean without [llm-scrub]; preview degrades | unit | `python -m pytest tests/test_scrubber_semantic.py -k soft_import -x` | ❌ Wave 0 |
| SC#5/D-08 | flagged entities surface in preview panel (text+label+confidence) | unit | `python -m pytest tests/test_cli.py -k flagged_panel -x` | ❌ Wave 0 (extend) |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_scrubber_semantic.py tests/test_collector.py -x`
- **Per wave merge:** `python -m pytest`
- **Phase gate:** full suite green + the D-02 live local-Ollama run produces a staging record with real `parameter_count`/`quantization` BEFORE `/gsd-verify-work`.

### Calibration-Gate Test Shape (D-06)
```python
# tests/fixtures/code_content_pii.json — known-safe identifiers seeded into turn text
#   e.g. "import pandas as pd", "const App = () => <React.Fragment/>",
#        "def compute_quality_score(record):", variable names, library names
def test_calibration_zero_redact_on_code(gliner_available):
    spans = detect_entities(CODE_TEXT, threshold=0.4)
    auto = [s for s in spans if s["score"] >= 0.7]
    assert auto == [], f"code identifiers auto-redacted: {auto}"   # HARD GATE
    flagged = [s for s in spans if 0.4 <= s["score"] < 0.7]
    fp_rate = len(flagged) / max(1, len(KNOWN_SAFE_TOKENS))
    record_artifact("gliner_code_fp_rate", fp_rate)               # observed FP rate (D-06)
```
Mark GLiNER-dependent tests with a skip-if-not-installed guard (`pytest.importorskip("gliner")`) so the core suite stays green without `[llm-scrub]`. The calibration + detect tests REQUIRE the extra and the model download — run them in a `[llm-scrub]`-installed CI lane / locally.

### Wave 0 Gaps
- [ ] `tests/fixtures/code_content_pii.json` — D-06 calibration fixture (code identifiers + a few real names to prove true-positive detection still works).
- [ ] `tests/test_scrubber_semantic.py` — bands, asymmetric coverage, calibration gate, soft-import fallback.
- [ ] `tests/test_collector.py` extensions — paired-turn mapping, tool buffer/dedup, turn-scoped session-end-once, ollama metadata (mocked) + remote degradation.
- [ ] `tests/test_cli.py` / `test_plugin.py` extensions — flagged panel surfacing; hooks invoke collector (not just debug-log).
- [ ] Install lane: `pip install kajiba[llm-scrub]` for the GLiNER-dependent tests + the D-02 Ollama install/pull (Hermes 3 8B Q4).

## Security Domain

> `security_enforcement` not set in config → treated as enabled. This phase IS a privacy/PII-control phase.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | Pydantic v2 models validate every captured turn/tool; `ToolStatusType` literal rejects bad status. |
| V6 Cryptography | no (hashing only) | SHA-256 content addressing already in schema; do not hand-roll. |
| V8 Data Protection / Privacy | yes (core) | Two-layer scrub (regex + GLiNER), asymmetric coverage, calibration gate, flag-band HITL, over-redact default (project constraint). |
| V12 Files/Resources | yes | GLiNER weights download to HF cache; staging files local-only under HERMES_HOME. |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| PII leak into community dataset (names in prose) | Information Disclosure | GLiNER ≥0.7 auto-redact in `ConversationTurn.value`; flag band for review. |
| Silent corruption of code training data | Tampering | D-07 asymmetric: never auto-redact tool/code fields; D-06 calibration gate. |
| PII in tool error messages | Information Disclosure | `error_message` may carry PII (06-HOOK-KWARGS) — runs through regex scrub; flag-only via GLiNER. |
| Hook handler crash disrupts Hermes session | Denial of Service | Fault-tolerant try/except in every handler (carried); finalize never raises. |
| Unverified heavy dependency (supply chain) | Tampering | slopcheck clean (4 OK); pinned to verified PyPI versions; gated behind opt-in extra. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ollama.show()` in client 0.6.x returns dict-or-object with `details.*` + `model_info.*context_length` + `digest` exactly as the REST API documents | Pattern 4 | Metadata fields land None; D-01 still degrades safely. Verify against installed `ollama._types` during impl. |
| A2 | GLiNER 570M weights are ~1.5–2.4GB and fit RTX 4070 8GB alongside no resident LLM | Pattern 5 | If too heavy, fall back to CPU or `knowledgator/gliner-pii-base` (but PRIV-01 names NVIDIA model — needs user OK to substitute). |
| A3 | Idempotent overwrite keyed by `session_id` correctly accumulates the full trajectory across per-turn `on_session_end` firings | Session-end fix | If Hermes resets `session_id` mid-session or `_conversations` is cleared, trajectory truncates. CONFIRM in D-02 live run. |
| A4 | No user turns are lost on interruption without `pre_llm_call` | Pattern 3 | Interrupted turns lack assistant response; if `post_llm_call` also skips `user_message` on interrupt, user turn is lost. CONFIRM in D-02 live run (the one open question). |
| A5 | GLiNER `predict_entities` labels `company`/`organization`/`project` behave as expected on the NVIDIA model's 55-label space | Pattern 5/6 | Model may not recognize `project` as a label; D-06 calibration + a true-positive test will reveal. May need label tuning within D-04's set. |

## Open Questions

1. **Interrupted-turn user capture (A4).**
   - Known: `post_llm_call` carries `user_message`; `on_session_end.interrupted` exists.
   - Unclear: whether `post_llm_call` fires at all (and carries `user_message`) when the user interrupts before a response.
   - Recommendation: rely on `post_llm_call` for now (Pattern 3); verify during the D-02 live run; only add `pre_llm_call` if the live run shows lost user turns.

2. **Final-vs-turn `on_session_end` disambiguation (A3).**
   - Known: fires per turn + at CLI exit; no explicit "is-final" flag in 06-HOOK-KWARGS.
   - Recommendation: idempotent overwrite keyed by `session_id` (no disambiguation needed); add a once-guard for continuous-mode auto-submit.

3. **`provider` literal gap for Anthropic.**
   - `ProviderType` lacks `anthropic`. Recommendation: map remote Anthropic to `provider="custom"`, record true backend in free-text `HardwareProfile.inference_backend` (D-03). Planner may optionally extend the literal — flag, don't assume.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | all | ✓ | 3.13.3 | — |
| RTX 4070 GPU + CUDA | GLiNER acceleration | ✓ | driver 595.97 (Ada/Lovelace, supported) | CPU via torch |
| `gliner` | PRIV-01 | ✗ | 0.2.26 on PyPI | install via `[llm-scrub]`; soft-import fallback |
| `torch` | GLiNER backend | ✗ | 2.12.0 (cp313 win wheel) | CPU wheel |
| `transformers` | GLiNER backbone | ✗ | 5.x | pulled transitively |
| `ollama` (client) | CAPT-04 metadata | ✗ | 0.6.2 on PyPI | D-01 degradation (remote path) |
| Ollama server + Hermes 3 8B Q4 | D-02 live run | ✗ (not installed) | — | REQUIRED for D-02 — install + pull before phase gate |
| Hermes Agent | live capture | ✓ | v0.15.1 native Windows | — |

**Missing dependencies with no fallback:**
- Ollama server + Hermes 3 8B Q4 model — REQUIRED for the D-02 live capture run that proves SC#3/CAPT-04 on real data. Must be installed/pulled (dev has no Ollama today). This is a phase-gate prerequisite, not a code fallback.

**Missing dependencies with fallback:**
- `gliner`/`torch`/`transformers`/`ollama` (client) — install via `[llm-scrub]`; core degrades gracefully (soft-import) when absent.

## Sources

### Primary (HIGH confidence)
- `.planning/phases/06-environment-plugin-foundation/06-HOOK-KWARGS.md` — live-verified v0.15.1 hook payload contract (all turn/tool kwargs, findings 1-8).
- `src/kajiba/{collector,scrubber,scrubber_llm,schema,cli}.py`, `src/kajiba/plugin/{__init__,hooks}.py` — current code (read in full / relevant sections).
- huggingface.co/nvidia/gliner-PII — model id, params (570M), base model, labels/usage, license, hardware.
- github.com/ollama/ollama-python + ollama.readthedocs.io/en/api — `ollama.show()` response fields, error handling.

### Secondary (MEDIUM confidence)
- PyPI version checks (`pip index versions`): gliner 0.2.26, ollama 0.6.2; slopcheck install scan → 4 OK.
- `docs/kajiba-project-spec.md` Layer C/D — original (now-superseded) PII design.

### Tertiary (LOW confidence)
- Exact `ollama` 0.6.x Python return-object shape (dict vs typed object) — verify against installed `ollama._types` during implementation (A1).

## Metadata

**Confidence breakdown:**
- Turn/tool capture (CAPT-02/03): HIGH — live-verified kwargs, existing code read.
- Session-end fix: HIGH on the problem, MEDIUM on the once-guard for continuous mode (needs live confirm).
- Model metadata (CAPT-04): HIGH on schema/degradation, MEDIUM on exact ollama return shape.
- GLiNER (PRIV-01/02): HIGH on API + model id correction, MEDIUM on `project` label efficacy + VRAM fit.
- Calibration/asymmetric (PRIV-03/D-06/D-07): HIGH on design, efficacy proven only by running the gate.

**Research date:** 2026-06-05
**Valid until:** 2026-07-05 (stable; re-verify gliner/ollama versions if planning slips a month).
