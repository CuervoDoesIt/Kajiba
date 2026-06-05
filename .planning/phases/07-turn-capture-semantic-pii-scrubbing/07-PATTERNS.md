# Phase 7: Turn Capture + Semantic PII Scrubbing - Pattern Map

**Mapped:** 2026-06-05
**Files analyzed:** 9 (4 modified source, 1 new source, 1 packaging, 3 test/fixture)
**Analogs found:** 9 / 9 (all in-repo — this is a code-promotion + mirror phase, not a greenfield phase)

> Every new/modified file has a strong in-repo analog. No file falls back to RESEARCH.md
> abstract patterns. The dominant move is **mirror an existing shape**, not invent one.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/kajiba/plugin/hooks.py` | plugin/hooks (event handlers) | event-driven | itself — `on_session_start`/`on_session_end` (working handlers) vs the `on_post_*` stubs | exact (same file, promote stubs) |
| `src/kajiba/collector.py` | collector (session state) | event-driven → batch finalize | itself — `on_turn_complete` + `_extract_model_metadata` + `_detect_hardware` (psutil soft-import) + `_save_to_staging` | exact (same file, extend) |
| `src/kajiba/scrubber_semantic.py` (NEW) | service (PII detector) | transform | `src/kajiba/scrubber.py` (`scrub_text`/`scrub_record` + `Redaction`/`FlaggedItem`/`ScrubResult`); soft-import from `_detect_hardware` psutil block | role-match (mirror containers + deep-copy) |
| `src/kajiba/scrubber_llm.py` | service (stub to retire) | transform | `src/kajiba/scrubber.py` dataclasses (replace string-confidence shapes) | exact (same role, replace) |
| `src/kajiba/scrubber.py` | service (Layer B regex) | transform | itself — unchanged; the composition target (D-11) | n/a (compose-with, not modify) |
| `src/kajiba/cli.py` | controller (CLI commands) | request-response | itself — `preview` + `_render_preview(..., flagged_items=...)` (already renders flagged) | exact (extend `all_flagged`) |
| `src/kajiba/schema.py` | model (Pydantic) | n/a | itself — fields already exist; **no change expected** | n/a (confirm-only) |
| `pyproject.toml` | config (packaging) | n/a | itself — `[project.optional-dependencies] upload`/`dev` blocks | exact (fill `llm-scrub = []`) |
| `tests/*` + `tests/fixtures/code_content_pii.json` (NEW) | test | n/a | `tests/test_collector.py`, `tests/test_scrubber*.py`, existing `tests/fixtures/*.json` | role-match |

## Pattern Assignments

### `src/kajiba/plugin/hooks.py` (plugin/hooks, event-driven)

**Analog:** itself — promote the `on_post_llm_call`/`on_post_tool_call` debug stubs (lines 87-114) to real dispatch, matching the already-working `on_session_start` (lines 64-84) and `on_session_end` (lines 117-129) shape.

**Fault-tolerant dispatch pattern to COPY** (`on_session_start`, lines 73-84) — every promoted handler keeps this exact try/except + `if _collector is not None` shell (carried hard rule, CONTEXT "Established Patterns"):
```python
try:
    _log_kwargs("on_session_start", {"session_id": session_id, "model": model, "platform": platform}, kwargs)
    if _collector is not None:
        _collector.on_session_start(session_id=session_id, model_name=model, platform=platform)
except Exception:
    logger.exception("Error in on_session_start hook")
```

**Stub to REPLACE** (lines 87-99) — currently `_log_kwargs(...)` only; promote to extract the live kwargs (`user_message`, `assistant_response`, `turn_id`, `conversation_history` per 06-HOOK-KWARGS) and call a new collector method, keeping the same `**kwargs`-tolerant signature + try/except:
```python
def on_post_llm_call(**kwargs) -> None:
    try:
        _log_kwargs("on_post_llm_call", {}, kwargs)   # keep debug log
    except Exception:
        logger.exception("Error in on_post_llm_call hook")
```

**`on_session_end` turn-scoped fix** (lines 117-129): handler dispatch shell is unchanged; the correctness fix (per-turn firing → finalize-once) lives in the collector method it calls, not here. Keep `_log_kwargs` + `if _collector is not None` + try/except.

---

### `src/kajiba/collector.py` (collector, event-driven → batch finalize)

**Analog:** itself — three established patterns in this file are the templates for the new work.

**1. Soft-import + graceful degradation (Ollama metadata, D-01)** — COPY the psutil block in `_detect_hardware` (lines 104-117). It is the canonical soft-dep shape for the new `_enrich_from_ollama` helper:
```python
ram_gb: Optional[int] = None
try:
    import psutil
    ram_gb = round(psutil.virtual_memory().total / (1024 ** 3))
except ImportError:
    ...   # fall back, never raise
```
New `ollama` helper mirrors this: `try: import ollama / except ImportError: return {}`, then a second `try/except Exception` around `ollama.show()` (the network/service touch). Remote sessions must never error (D-01).

**2. Turn assembly (CAPT-02/03)** — `on_turn_complete` (lines 221-252) is the analog for the new paired-turn method. It already shows the `ConversationTurn(**{"from": role}, value=..., tool_calls=[ToolCall(...)])` construction and the `[:2000]` truncation convention:
```python
tool_calls = [ToolCall(
    tool_name=tc["name"],
    tool_input=tc.get("input", "")[:2000],
    tool_output=tc.get("output", "")[:2000],
    tool_status=tc.get("status", "success"),   # CAUTION: Hermes sends "ok" → must map to "success"
    latency_ms=tc.get("latency_ms"),
) for tc in turn["tool_calls"]]
conversation_turn = ConversationTurn(**{"from": turn["role"]}, value=turn["content"], tool_calls=tool_calls, ...)
self._conversations.append(conversation_turn)
```
New work: add a paired `on_llm_turn(...)` that appends a `human` then a `gpt` turn (RESEARCH Pattern 1), keep `on_turn_complete` for test back-compat. Add `_pending_tools: dict[str, list[ToolCall]]` buffer keyed by `turn_id` (init alongside `_conversations` in `__init__` lines 172-180 and reset in `on_session_start` lines 210-213). **`tool_status` mapping `"ok"→"success"` is mandatory** — `_build_record` (lines 393-395) counts `successful_tool_calls` by `tool_status == "success"`.

**3. Metadata extraction (CAPT-04)** — `_extract_model_metadata` (lines 136-154) is extended: it currently maps a flat config dict into `ModelMetadata`. Layer the Ollama enrichment (D-01) and remote slug inference (D-03) on top, populating `HardwareProfile.inference_backend`. All `ModelMetadata`/`HardwareProfile` fields already exist (see schema confirm below).

**4. Session-end finalize-once (headline correctness fix)** — `on_session_end` (lines 254-336) currently calls `_save_to_staging()` immediately. `_save_to_staging` (lines 419-435) already writes an **overwriting** file `session_{session_id}.json`:
```python
filename = f"session_{self._session_id or 'unknown'}.json"
staging_file = STAGING_DIR / filename
staging_file.write_text(json.dumps(record_json, ...))   # overwrite — last write wins
```
RESEARCH recommends idempotent-overwrite keyed by `session_id`: per-turn `on_session_end` firings rewrite the same file (N firings → 1 file). The continuous-mode auto-submit branch (lines 286-333) needs an explicit once-guard (`_finalized` flag) so it does not submit per turn.

---

### `src/kajiba/scrubber_semantic.py` (NEW — service, transform)

**Analog:** `src/kajiba/scrubber.py` — mirror its containers and deep-copy discipline; do NOT invent new shapes (CONTEXT "Reusable Assets").

**Reuse `FlaggedItem` verbatim** (`scrubber.py` lines 150-159) — GLiNER flags feed the SAME preview channel (D-08). `_render_preview` reads `item.text` and `item.reason` (cli.py line 496), so build:
```python
@dataclass
class FlaggedItem:        # already exists in scrubber.py — import it, don't redefine
    text: str
    category: str
    reason: str           # set: f"GLiNER {label} (confidence {score:.2f})"
    start: int
    end: int
```

**Replace the string-confidence stub** — `scrubber_llm.py`'s `SemanticRedaction(confidence: str)` is obsolete; GLiNER gives `score: float`. The band bucketing (D-05, locked) is a single inference pass:
```python
spans = model.predict_entities(text, LABELS, threshold=0.4)   # flag floor
redactions = [s for s in spans if s["score"] >= 0.7]          # auto-redact (turn.value ONLY)
flags      = [s for s in spans if 0.4 <= s["score"] < 0.7]    # flag for review
```

**Soft-import pattern** — mirror `_detect_hardware`'s psutil block (collector.py lines 104-117): `from gliner import GLiNER` inside a function, raise `SemanticScrubUnavailable` (not `ModuleNotFoundError`) when `[llm-scrub]` absent. Within-run singleton cache (`global _MODEL`) so GLiNER loads once per CLI invocation (D-09).

**Replacement tag** — use `[REDACTED_NAME]` / `[REDACTED_PERSON]` to match the regex placeholder convention (`scrubber.py` lines 20-28, `PLACEHOLDER_PATH = "[REDACTED_PATH]"`) so the existing `_build_highlighted_text` regex highlights them for free.

**Asymmetric coverage (D-07)** — for `ConversationTurn.value`: redact ≥0.7 + flag 0.4–0.7. For `tool_input`/`tool_output`: collect FLAGS only, never mutate. Compose on the already-regex-scrubbed record (D-11), mirroring `scrub_record`'s deep-copy: `record.model_dump(by_alias=True)` → mutate → `KajibaRecord.model_validate(data)` (`scrubber.py` lines 327, 369).

---

### `src/kajiba/scrubber_llm.py` (service, transform — retire)

**Analog:** itself + `scrubber_semantic.py`. The `NotImplementedError` stub (lines 66-72) and the string-confidence `SemanticRedaction`/`ScrubResult` dataclasses (lines 22-38) are replaced. RESEARCH directs the new module name to be `scrubber_semantic.py`; planner decides whether to delete `scrubber_llm.py`, re-point it, or leave it raising. The `Callable`-based `model_fn` interface (line 41) is dead — GLiNER is span-tagging, not generative.

---

### `src/kajiba/scrubber.py` (service, Layer B regex — compose-with, unchanged)

**Analog:** itself. **No modification expected** — Layer B runs first (D-11). The composition surface for Layer C:
- `scrub_record(record) -> tuple[KajibaRecord, ScrubLog]` (lines 314-370) — Layer C runs on its output.
- `ScrubLog` assembly (lines 357-366) — Layer C adds `potential_names_redacted` and increments `items_flagged`.
- `flag_org_domains` (lines 201-221) — the existing flag producer that Layer C flags get appended alongside (extend the SAME list, D-08).
- Deep-copy discipline (`model_dump` → mutate → `model_validate`, lines 327/369) — the pattern `scrubber_semantic` mirrors.

---

### `src/kajiba/cli.py` (controller, request-response)

**Analog:** itself — `preview` (lines 593-629) already collects `all_flagged` and passes it to `_render_preview(..., flagged_items=all_flagged)`. Extend the SAME channel; no new render surface (D-08).

**Flag-collection pattern to EXTEND** (lines 601-610):
```python
scrubbed, scrub_log = scrub_record(record)          # Layer B (unchanged)
all_flagged = []
for turn in record.trajectory.conversations:
    all_flagged.extend(flag_org_domains(turn.value))
    if turn.tool_calls:
        for tc in turn.tool_calls:
            all_flagged.extend(flag_org_domains(tc.tool_input))
            all_flagged.extend(flag_org_domains(tc.tool_output))
```
Insert Layer C after Layer B (RESEARCH Pattern 6): call `scrub_record_semantic(scrubbed)` inside try/except `SemanticScrubUnavailable`, set `scrub_log.potential_names_redacted`, `scrub_log.items_flagged += len(semantic_flags)`, and `all_flagged.extend(semantic_flags)`.

**Rendering — already done** (`_render_preview`, lines 487-496): iterates `flagged_items` reading `item.text` and `item.reason`:
```python
if flagged_items:
    console.print(f"{len(flagged_items)} item(s) flagged for review (not auto-redacted):")
    for item in flagged_items:
        console.print(f"  [yellow]* {item.text}[/yellow] — {item.reason}")
```
GLiNER `FlaggedItem`s plug straight in. **Note:** there are 4+ `scrub_record` call sites that build `all_flagged` (lines 601, 649, 694, 1761) — the planner must apply Layer C consistently or factor a shared helper.

---

### `src/kajiba/schema.py` (model — confirm-only, NO change)

**Analog:** itself. All required fields verified present:
- `ToolStatusType = Literal["success","failure","timeout","error"]` (line 101) — `"ok"` is NOT valid; collector must map.
- `ToolCall` (lines 125-132): `tool_name`, `tool_input`, `tool_output`, `tool_status`, `latency_ms`.
- `ConversationTurn` (lines 135-144): `from_` (alias `"from"`), `value`, `tool_calls`, `token_count`, `generation_latency_ms`. `model_config = {"populate_by_name": True}`.
- `ModelMetadata` (lines 166-177): `parameter_count` (str), `quantization`, `model_family`, `context_window`, `context_used`, `provider` (Literal — **lacks `anthropic`; map remote to `"custom"`**), `is_local`, `model_hash` — all present.
- `HardwareProfile.inference_backend` (line 189): free `str`, exists.
- `ScrubLog.potential_names_redacted` (226) + `items_flagged` (233): exist.

No schema edit required. (If planner extends `ProviderType` for Anthropic, that is the one optional change — flag, don't assume.)

---

### `pyproject.toml` (config — packaging)

**Analog:** itself — the `upload` / `dev` optional-dependency blocks (lines 32-37) are the shape for filling the empty `llm-scrub = []` (line 33):
```toml
[project.optional-dependencies]
upload = ["huggingface_hub>=0.19"]
llm-scrub = []          # ← fill: gliner, torch, transformers, ollama (D-10)
dev = ["pytest>=7.0", "pytest-cov>=4.0"]
```
Add `gliner`, `torch`, `transformers`, `ollama` (verified versions in RESEARCH §Standard Stack). Project version is `0.2.0` (line 7).

---

### Tests + fixture (test)

**Analogs:** `tests/test_collector.py` (extend: paired-turn, tool buffer/dedup, session-end-once, ollama-metadata mocked + remote degrade), `tests/test_cli.py` (extend: flagged panel), and existing `tests/fixtures/*.json` (`gold_trajectory.json`, `pii_trajectory.json`) for the NEW `tests/fixtures/code_content_pii.json`.

**New `tests/test_scrubber_semantic.py`** — bands, asymmetric coverage, calibration gate (D-06 HARD GATE: zero auto-redact ≥0.7 on code identifiers), soft-import fallback. Gate GLiNER-dependent tests with `pytest.importorskip("gliner")` so the core suite stays green without the extra (RESEARCH Validation Architecture).

## Shared Patterns

### Fault-tolerant event handler shell
**Source:** `src/kajiba/plugin/hooks.py` lines 73-84 (`on_session_start`); collector methods all wrap bodies in `try: ... except Exception: logger.exception(...)`.
**Apply to:** every promoted hook (`on_post_llm_call`, `on_post_tool_call`) and every new/extended collector method. Never propagate to Hermes (carried hard rule).

### Soft-dependency import with graceful fallback
**Source:** `src/kajiba/collector.py` lines 104-117 (psutil in `_detect_hardware`).
**Apply to:** `scrubber_semantic._get_model` (gliner/torch) and `collector._enrich_from_ollama` (ollama). `try: import X / except ImportError: <degrade>`. Core stays import-clean and offline (D-01, D-10).

### Deep-copy scrub discipline
**Source:** `src/kajiba/scrubber.py` lines 327, 369 (`model_dump(by_alias=True)` → mutate → `KajibaRecord.model_validate(data)`).
**Apply to:** `scrubber_semantic.scrub_record_semantic` — never mutate the raw staged record.

### Flagged-item channel (single render surface)
**Source:** `scrubber.FlaggedItem` (`scrubber.py` lines 150-159) + `_render_preview` consumption (`cli.py` lines 487-496, reads `item.text`/`item.reason`).
**Apply to:** all GLiNER flags — reuse `FlaggedItem`, set `reason=f"GLiNER {label} (confidence {score:.2f})"`, append to the existing `all_flagged` list (D-08).

### `[REDACTED_*]` placeholder convention
**Source:** `scrubber.py` lines 20-28 (`PLACEHOLDER_PATH = "[REDACTED_PATH]"` etc.).
**Apply to:** GLiNER name redactions — use `[REDACTED_NAME]`/`[REDACTED_PERSON]` so existing highlight regex (`\[REDACTED_\w+\]`) catches them.

### `[:2000]` field truncation
**Source:** `collector.on_turn_complete` lines 235-236.
**Apply to:** new tool buffering (`tool_input`/`tool_output` from `args`/`result`).

## No Analog Found

None. Every file maps to an in-repo analog. This phase mirrors and promotes existing shapes rather than introducing novel architecture — the only genuinely new mechanics (GLiNER inference, `ollama.show()` calls, the tool-buffer dict) all reuse established soft-import / dataclass / deep-copy patterns above.

## Metadata

**Analog search scope:** `src/kajiba/` (plugin, collector, scrubber, scrubber_llm, schema, cli), `pyproject.toml`, `tests/`.
**Files scanned (read):** hooks.py, scrubber_llm.py, scrubber.py, collector.py, pyproject.toml, schema.py (targeted), cli.py (targeted).
**Pattern extraction date:** 2026-06-05
