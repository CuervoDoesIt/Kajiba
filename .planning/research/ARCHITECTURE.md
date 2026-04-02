# Architecture Research

**Domain:** Hermes Plugin Integration + LLM PII Scrubbing + Fine-tuning Data Export
**Researched:** 2026-04-02
**Confidence:** HIGH (Hermes plugin API verified against official docs; LLM scrubbing patterns verified via multiple sources; fine-tuning export verified via Unsloth/PEFT official docs)

---

## Standard Architecture

### System Overview

The v1.1 milestone adds three vertical concerns to the existing pipeline. None of them require restructuring the core data flow (collect → scrub → score → publish). They sit at the edges: a new **Plugin Entry Layer** replacing the Protocol stub, a new **Semantic Scrub Layer** inserted between regex scrub and quality scoring, and a new **Export Format Layer** appended after quality scoring.

```
~/.hermes/plugins/kajiba/
├── plugin.yaml          ← NEW: Hermes plugin manifest
├── __init__.py          ← NEW: register(ctx) entry point
└── hooks.py             ← NEW: on_session_start/end, pre/post_llm_call handlers

         │  ctx.register_hook("on_session_start", ...)
         │  ctx.register_hook("post_llm_call", ...)
         │  ctx.register_hook("on_session_end", ...)
         ▼

src/kajiba/
├── collector.py         ← CHANGED: new hook signatures from Hermes plugin API
├── hermes_integration.py ← REPLACED: old Protocol stub → thin dispatcher
├── scrubber.py          ← UNCHANGED: regex Layer B
├── scrubber_llm.py      ← IMPLEMENTED: semantic Layer C (was stub)
├── scorer.py            ← UNCHANGED
├── cli.py               ← MINOR CHANGE: llm-scrub toggle in preview/submit
└── schema.py            ← UNCHANGED

Data Flow (updated for v1.1):

Session turn arrives via post_llm_call hook
     │
     ▼
collector.on_turn_complete(turn_dict)        ← mapped from hook kwargs
     │
     ▼
scrubber.scrub_record(record)                ← Layer B: regex PII (existing)
     │ scrubbed KajibaRecord + ScrubLog
     ▼
scrubber_llm.scrub_semantic(text, model_fn)  ← Layer C: semantic PII (NEW)
     │ merged ScrubResult with all redactions
     ▼
scorer.compute_quality_score(record)         ← unchanged
     │ QualityResult
     ▼
~/.hermes/kajiba/staging/session_{id}.json   ← HITL review gate
     │ user: kajiba review → approve
     ▼
record.to_sharegpt() / to_dpo_candidate()   ← existing methods, no changes
     │ sharegpt or DPO dict
     ▼
export as JSONL for fine-tuning              ← no new code required
```

### Component Responsibilities After v1.1

| Component | Status | Responsibility | Changes |
|-----------|--------|---------------|---------|
| `~/.hermes/plugins/kajiba/__init__.py` | NEW | `register(ctx)` entry point; wire all hooks | New file |
| `~/.hermes/plugins/kajiba/plugin.yaml` | NEW | Plugin manifest declaring hook subscriptions | New file |
| `hermes_integration.py` | REPLACED | Dispatch Hermes hook kwargs to `KajibaCollector` methods | Full rewrite of 95 LOC |
| `collector.py` | CHANGED | Accept `model` (str) + `platform` (str) from Hermes hooks instead of `model_config` (dict) | `on_session_start`, `on_session_end` signatures update |
| `scrubber_llm.py` | IMPLEMENTED | Semantic PII detection via local Ollama model; structured JSON output | Stub → real implementation |
| `scrubber.py` | UNCHANGED | Regex-based Layer B scrubbing | No changes |
| `scorer.py` | UNCHANGED | Quality scoring | No changes |
| `cli.py` | MINOR CHANGE | Add `--llm-scrub` flag to `preview` and `submit` | ~20 LOC change |
| `schema.py` | UNCHANGED | Data model | No changes |

---

## Recommended Project Structure

The v1.1 changes require two filesystem locations, not just `src/kajiba/`:

```
D:/Kajiba/                               (or wherever the dev machine has this)
├── src/kajiba/
│   ├── hermes_integration.py            ← REPLACED (thin dispatcher to collector)
│   ├── collector.py                     ← CHANGED (hook signature updates)
│   ├── scrubber_llm.py                  ← IMPLEMENTED (LLM semantic scrub)
│   ├── scrubber.py                      ← unchanged
│   ├── scorer.py                        ← unchanged
│   ├── schema.py                        ← unchanged
│   └── cli.py                           ← minor change (llm-scrub flag)
│
└── .planning/
    └── research/                        ← this document lives here

~/.hermes/plugins/kajiba/                ← PLUGIN INSTALL LOCATION (new dir)
├── plugin.yaml
├── __init__.py                          ← register(ctx) entry point
└── hooks.py                             ← hook handler functions

~/.hermes/kajiba/
├── staging/                             ← unchanged
└── outbox/                              ← unchanged
```

**Structure rationale:**

- The plugin lives at `~/.hermes/plugins/kajiba/` because that is where Hermes discovers plugins. It is NOT inside `src/kajiba/` — it is a consumer of the Kajiba library, not part of the library itself.
- `hermes_integration.py` remains in the library so the collector can be used standalone (without Hermes) in tests and the CLI. The plugin directory imports from it.
- `scrubber_llm.py` stays in `src/kajiba/` (same as the regex scrubber) because it is part of the library's scrubbing pipeline, not plugin-specific.

---

## Architectural Patterns

### Pattern 1: Plugin Register Function Wiring ctx Hooks to Existing Collector

The Hermes plugin API contract is: define `register(ctx)`, call `ctx.register_hook(event, handler)` inside it. The handlers must accept `**kwargs` for forward compatibility.

The hook signatures from Hermes v0.5.0+ (confirmed via official docs) are:

```python
# on_session_start kwargs: session_id (str), model (str), platform (str)
# on_session_end kwargs:   session_id (str), completed (bool), interrupted (bool),
#                          model (str), platform (str)
# pre_llm_call kwargs:     session_id (str), user_message (str),
#                          conversation_history (list), is_first_turn (bool),
#                          model (str), platform (str)
# post_llm_call kwargs:    session_id (str), user_message (str),
#                          assistant_response (str), conversation_history (list),
#                          model (str), platform (str)
# post_tool_call kwargs:   tool_name (str), args (dict), result (str), task_id (str)
```

The adapter pattern: wrap hook kwargs into the dict shape `KajibaCollector` already accepts. This means the collector's method signatures must also change to accept the new kwarg names.

```python
# ~/.hermes/plugins/kajiba/__init__.py
from kajiba.collector import KajibaCollector

_collector: KajibaCollector | None = None

def register(ctx) -> None:
    global _collector
    _collector = KajibaCollector()

    ctx.register_hook("on_session_start", _on_session_start)
    ctx.register_hook("post_llm_call", _on_post_llm_call)
    ctx.register_hook("post_tool_call", _on_post_tool_call)
    ctx.register_hook("on_session_end", _on_session_end)
```

```python
# ~/.hermes/plugins/kajiba/hooks.py
def _on_session_start(session_id: str, model: str, platform: str, **kwargs) -> None:
    if _collector is None:
        return
    _collector.on_session_start(
        session_id=session_id,
        model_name=model,
        platform=platform,
    )

def _on_post_llm_call(
    session_id: str,
    user_message: str,
    assistant_response: str,
    conversation_history: list,
    model: str,
    platform: str,
    **kwargs,
) -> None:
    if _collector is None:
        return
    # Build turn dict that collector.on_turn_complete already accepts
    _collector.on_turn_complete({
        "role": "gpt",
        "content": assistant_response,
    })

def _on_session_end(
    session_id: str,
    completed: bool,
    interrupted: bool,
    model: str,
    platform: str,
    **kwargs,
) -> None:
    if _collector is None:
        return
    _collector.on_session_end(session_id=session_id)
```

**Why this pattern:** The `_collector` module-level singleton is correct here because Hermes fires `on_session_start` before any turn hooks, establishing session context. The singleton is reset on each `on_session_start` call inside the collector (existing behavior).

**Trade-off:** Module-level state is not thread-safe. For Hermes's single-session CLI use case this is fine. If Hermes ever runs concurrent sessions per process, this needs a `session_id → collector` dict.

### Pattern 2: KajibaCollector Signature Adaptation (Minimal Breaking Change)

`collector.py` currently has `on_session_start(self, session_id: str, model_config: dict)`. The Hermes plugin API does not pass `model_config` as a dict — it passes `model: str` (the model name string) and `platform: str`.

The minimal change: add `model_name` and `platform` as keyword arguments to `on_session_start`, keep `model_config` as an optional parameter for backwards compatibility (used in tests and standalone CLI):

```python
def on_session_start(
    self,
    session_id: str,
    model_config: Optional[dict] = None,   # kept for backwards compat
    *,
    model_name: Optional[str] = None,       # new: from Hermes hook
    platform: Optional[str] = None,         # new: from Hermes hook
) -> None:
    # If called from plugin, construct minimal model_config from kwargs
    if model_config is None and model_name is not None:
        model_config = {"model_name": model_name, "provider": platform}
    ...
```

This preserves all existing tests that call `on_session_start(session_id="x", model_config={...})` while enabling the plugin path.

### Pattern 3: LLM Semantic Scrubber — Structured Output via Ollama

The LLM scrubber calls a local model (Hermes 3 8B Q4 via Ollama) with a focused PII detection prompt. The model returns a JSON array of detected entities. This must be robust to model output variance.

**Recommended approach:** Use Ollama's `format="json"` parameter + Pydantic validation + retry on parse failure. This resolves >95% of structured output issues per community benchmarks.

```python
# src/kajiba/scrubber_llm.py

import json
import logging
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)

PII_DETECTION_PROMPT = """\
You are a privacy auditor. Identify ALL personally identifiable information in the text below.

Return ONLY a JSON array. Each item must have exactly these fields:
- "text": the exact string found in the input (verbatim match required)
- "category": one of: person_name, company_name, project_name, location, username, other
- "confidence": one of: high, medium, low

Text to analyze:
<<<
{text}
>>>

Rules:
- Public figures in their public capacity are NOT PII (e.g., "Linus Torvalds" in a Linux commit context)
- Generic company names from docs (GitHub, Microsoft) are NOT PII
- Internal project codenames, employer names, real usernames ARE PII
- Return [] if no PII found
"""

@dataclass
class SemanticRedaction:
    original_text: str
    replacement_tag: str
    confidence: str      # "high", "medium", "low"
    category: str        # "person_name", "company_name", "project_name", ...

@dataclass
class ScrubResult:
    scrubbed_text: str
    redactions: list[SemanticRedaction] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)

def scrub_semantic(text: str, model_fn: Callable[[str], str]) -> ScrubResult:
    prompt = PII_DETECTION_PROMPT.format(text=text)
    raw = model_fn(prompt)
    try:
        detections = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("LLM scrubber returned non-JSON; skipping semantic scrub")
        return ScrubResult(scrubbed_text=text)

    redactions = []
    scrubbed = text
    for item in detections:
        if item.get("confidence") in ("high", "medium"):
            tag = f"[REDACTED_{item['category'].upper()}]"
            scrubbed = scrubbed.replace(item["text"], tag)
            redactions.append(SemanticRedaction(
                original_text=item["text"],
                replacement_tag=tag,
                confidence=item["confidence"],
                category=item["category"],
            ))
    return ScrubResult(
        scrubbed_text=scrubbed,
        redactions=redactions,
        stats={"total": len(redactions)},
    )
```

**model_fn contract:** The caller (collector or CLI) provides `model_fn`. For Ollama: `lambda prompt: ollama.generate(model="hermes3:8b-q4", prompt=prompt, format="json")["response"]`. This keeps the scrubber decoupled from any specific inference backend.

**When to call:** After `scrubber.scrub_record()` (regex pass) and before `scorer.compute_quality_score()`. The LLM scrubber operates on individual string fields (turn content), not the full `KajibaRecord` at once — same pattern as the regex scrubber's `scrub_text()`.

**Confidence threshold policy:** Auto-redact `high` and `medium` confidence. Flag `low` confidence items in the `ScrubLog` for HITL review. Do NOT auto-redact low confidence (too many false positives with local 8B models).

### Pattern 4: Fine-tuning Export via Existing KajibaRecord Methods

No new export code is required for the fine-tuning experiment. `KajibaRecord.to_sharegpt()` and `KajibaRecord.to_dpo_candidate()` already exist and produce the correct formats.

The export workflow is purely operational (CLI commands + a shell script), not an architectural change:

```
# Step 1: Export approved records as JSONL
kajiba export --format sharegpt ./fine_tune_data.jsonl

# Step 2: Fine-tune with Unsloth (outside Kajiba — consumer-side)
python train.py \
    --model unsloth/Llama-3.2-3B-Instruct-bnb-4bit \
    --dataset ./fine_tune_data.jsonl \
    --r 16 --lora-alpha 32 --max-seq-len 2048
```

The only Kajiba-side change needed: the `kajiba export` CLI command needs a `--format sharegpt|dpo|raw` flag if it does not already have one. Confirm against `cli.py` before implementing.

---

## Data Flow

### Session Collection Flow (v1.1 Plugin Path)

```
Hermes Agent session starts
     │
     ▼ on_session_start(session_id, model, platform)
~/.hermes/plugins/kajiba/hooks.py
     │ maps to: collector.on_session_start(session_id, model_name, platform)
     ▼
KajibaCollector._session_id set, hardware detected, ModelMetadata built
     │
     ▼ pre_llm_call fires (optional: memory plugins inject context)
     │ Kajiba does NOT subscribe to pre_llm_call — no action needed here
     │
     ▼ post_llm_call(session_id, user_message, assistant_response, ...)
~/.hermes/plugins/kajiba/hooks.py
     │ maps user_message → "human" turn, assistant_response → "gpt" turn
     │ calls collector.on_turn_complete() twice (once per role)
     ▼
KajibaCollector._conversations list grows
     │
     ▼ post_tool_call(tool_name, args, result, task_id)
~/.hermes/plugins/kajiba/hooks.py
     │ appends ToolCall to last "gpt" turn's tool_calls list
     ▼
KajibaCollector._conversations updated with tool call
     │
     ▼ on_session_end(session_id, completed, interrupted, ...)
~/.hermes/plugins/kajiba/hooks.py
     │ maps to: collector.on_session_end(session_id)
     ▼
KajibaCollector._save_to_staging() → ~/.hermes/kajiba/staging/session_{id}.json
```

### HITL Review Flow (post-collection)

```
~/.hermes/kajiba/staging/session_{id}.json
     │
     ▼ kajiba preview
CLI loads record, runs scrubber.scrub_record() (regex pass)
     │
     ▼ if --llm-scrub flag:
scrubber_llm.scrub_semantic(turn_content, model_fn) for each turn
     │ merged redaction log
     ▼
Rich table: redaction summary, quality tier, flagged org domains
     │
     ▼ kajiba review → user approves/edits/rejects
     │
     ▼ kajiba submit
Full privacy pipeline: scrub → anonymize → jitter → consent
Record written to ~/.hermes/kajiba/outbox/record_{id}.jsonl
```

### LLM Scrub Integration Into Privacy Pipeline

```
Existing pipeline (Layer B only):
  raw record → scrub_record() → scrubbed record → scorer

v1.1 pipeline (Layer B + Layer C):
  raw record
      → scrub_record()          ← regex, always runs
      → scrub_semantic_record() ← LLM, runs when llm_pii_scrub=true in config
      → scorer
```

`scrub_semantic_record()` is a new thin wrapper in `scrubber_llm.py` that iterates over `KajibaRecord` conversation turns and calls `scrub_semantic()` per turn. This mirrors the pattern in `scrubber.py`'s `scrub_record()` function. It appends any new redactions to the existing `ScrubLog`.

---

## Scaling Considerations

This is a local-first, single-user pipeline. Scaling is not a concern for v1.1. The relevant considerations are latency and reliability:

| Concern | Impact | Mitigation |
|---------|--------|------------|
| LLM scrub adds latency | ~2–5s per turn on 8B Q4 model | Gate behind config flag `llm_pii_scrub`; off by default |
| Ollama not running | LLM scrub call fails | Catch `ConnectionError`; log warning; fall back to regex-only |
| Long turns exceed model context | Truncation artifacts | Truncate input to 2000 chars (matches existing `tool_input[:2000]` pattern); log when truncated |
| Model returns invalid JSON | Parse failure | Catch `JSONDecodeError`; return no-op `ScrubResult`; log warning (no exception raised) |
| Plugin crashes | Hermes logs and skips | Already Hermes's default behavior for hook failures — no extra handling needed |

---

## Anti-Patterns

### Anti-Pattern 1: Calling `register_hooks(agent)` Pattern on the Real Plugin API

**What people do:** Try to adapt the old `hermes_integration.py`'s `register_hooks(agent)` style — where you call `agent.on("event", callback)` — to the real Hermes plugin system.
**Why wrong:** The real Hermes plugin API does not expose an `agent` object with an `.on()` method. The plugin receives a `ctx` context object. There is no `agent.on()`. Keeping the old Protocol-based adapter means Kajiba will never actually connect to a real Hermes session.
**Do instead:** Delete the old `HermesAgent` Protocol class and `register_hooks(agent)` function. Replace with a `register(ctx)` function that calls `ctx.register_hook()`. Keep `KajibaCollector` as the stateful data accumulator — it does not change structurally, only its input signatures need updating.

### Anti-Pattern 2: Wiring the User Turn from pre_llm_call Instead of post_llm_call

**What people do:** Subscribe to `pre_llm_call` to capture the user message (since it's in the payload), avoiding a second hook subscription.
**Why wrong:** `pre_llm_call` fires before the model responds. If you capture the user message there, you have no pairing with the assistant response. You end up with turns in the wrong order or missing the assistant side. Additionally, `pre_llm_call` can return a value (context injection) — returning accidentally could corrupt the agent's system prompt.
**Do instead:** Subscribe only to `post_llm_call`. Its payload includes both `user_message` and `assistant_response`. Build two `ConversationTurn` objects from a single hook call.

### Anti-Pattern 3: Calling scrub_semantic on the Full Record at Once

**What people do:** Pass the serialized JSON of the entire `KajibaRecord` to the LLM scrubber in one call.
**Why wrong:** A full record serialized to JSON can be 10–50KB. Local 8B models lose coherence on long inputs; the PII detection accuracy degrades significantly beyond ~2000 tokens. The model also "hallucinates" PII in field names (e.g., flags "record_id" as a person name).
**Do instead:** Call `scrub_semantic()` per turn content string, not per record. This matches the existing `scrub_text()` pattern in `scrubber.py` and keeps inputs within reliable model attention range.

### Anti-Pattern 4: Storing the Ollama model_fn as a Module-Level Callable

**What people do:** `import ollama; MODEL_FN = lambda p: ollama.generate(...)` at module level in `scrubber_llm.py`.
**Why wrong:** This creates a hard dependency on `ollama` being installed and running at import time. The module becomes un-importable on machines without Ollama — breaking all tests and the regex-scrub-only path.
**Do instead:** `scrub_semantic(text, model_fn)` accepts `model_fn` as an argument (already the existing stub signature). The caller (CLI or collector) constructs and passes `model_fn`. Gate the Ollama import inside the caller with a try/except. `scrubber_llm.py` itself imports nothing from Ollama.

### Anti-Pattern 5: Separate plugin.yaml and __init__.py Copies Inside src/kajiba/

**What people do:** Keep the plugin files inside `src/kajiba/` and try to symlink or copy them to `~/.hermes/plugins/kajiba/` at install time.
**Why wrong:** Creates two sources of truth. The `register(ctx)` function and `plugin.yaml` that Hermes reads must live at `~/.hermes/plugins/kajiba/`. Having them inside the Python package confuses both Hermes's plugin discovery and developers reading the codebase.
**Do instead:** The plugin directory `~/.hermes/plugins/kajiba/` is a separate artifact from the Python package. `__init__.py` there imports from the installed `kajiba` package (`from kajiba.collector import KajibaCollector`). Development setup: `pip install -e .` installs the library; a `make install-plugin` target copies/symlinks the plugin directory.

---

## Integration Points

### New Integration: Hermes Plugin API

| Boundary | Protocol | Direction | Notes |
|----------|----------|-----------|-------|
| `~/.hermes/plugins/kajiba/__init__.py` → Hermes | `register(ctx)` function | Hermes calls Kajiba | Called once at Hermes startup |
| Hermes → `hooks.py` handlers | `ctx.register_hook(event, fn)` | Hermes calls Kajiba | Per-session, per-turn events |
| `hooks.py` → `collector.py` | Direct Python import | Kajiba internal | `from kajiba.collector import KajibaCollector` |

**Confirmed hook names (Hermes v0.5.0+, HIGH confidence):**
- `on_session_start` — fires when session begins; kwargs: `session_id`, `model`, `platform`
- `post_llm_call` — fires after each LLM response; kwargs: `session_id`, `user_message`, `assistant_response`, `conversation_history`, `model`, `platform`
- `post_tool_call` — fires after each tool call; kwargs: `tool_name`, `args`, `result`, `task_id`
- `on_session_end` — fires when session ends; kwargs: `session_id`, `completed`, `interrupted`, `model`, `platform`

**Not using:**
- `pre_llm_call` — not needed; we capture from `post_llm_call` which has both sides of the exchange
- `pre_tool_call` — not needed; `post_tool_call` has the result which is what matters for training data

### Modified Integration: KajibaCollector ← scrubber_llm

| Boundary | Protocol | Notes |
|----------|----------|-------|
| `collector.export_record()` → `scrubber_llm.scrub_semantic_record()` | Direct call with `model_fn` kwarg | Only when `llm_pii_scrub=true` in config |
| `cli.py preview/submit` → `scrubber_llm.scrub_semantic_record()` | Direct call with `model_fn` kwarg | Only when `--llm-scrub` flag passed |

### Unchanged Integrations

| Boundary | Status |
|----------|--------|
| `collector.py` → `scrubber.scrub_record()` | Unchanged |
| `collector.py` → `scorer.compute_quality_score()` | Unchanged |
| `cli.py` → `publisher.py` | Unchanged |
| JSONL outbox → `kajiba export` | Unchanged |
| `KajibaRecord.to_sharegpt()` | Unchanged — works for fine-tuning export as-is |

---

## Suggested Build Order

Dependencies drive the ordering. Each item can be started only after all items it depends on are complete.

```
1. plugin.yaml + __init__.py skeleton (plugin dir)
   └── No dependencies. Establishes plugin directory.
       Verifies Hermes discovers and loads the plugin without errors.

2. collector.py: update on_session_start signature
   └── Depends on: confirmed Hermes hook kwarg names (verified above).
       Change: add model_name, platform kwargs; keep model_config for compat.
       Risk: MEDIUM — touches working code with 356 tests.

3. hooks.py (full hook handlers)
   └── Depends on: (1) plugin dir, (2) updated collector.
       Wire all four hooks: on_session_start, post_llm_call,
       post_tool_call, on_session_end.

4. hermes_integration.py rewrite
   └── Depends on: (2) updated collector signatures.
       Replace Protocol stub with thin dispatcher used by hooks.py.
       Keep register_hooks() as a deprecated no-op with a deprecation warning
       so any downstream code that calls it doesn't hard-break.

5. scrubber_llm.py implementation
   └── No dependencies on (1)-(4). Can be built in parallel.
       Implement scrub_semantic() + scrub_semantic_record().
       Unit test against a mock model_fn that returns known JSON.

6. cli.py: --llm-scrub flag on preview and submit
   └── Depends on: (5) implemented scrubber_llm.
       ~20 LOC change. Add Ollama import gating.

7. End-to-end HITL session collection test
   └── Depends on: (1)-(4) complete, real Hermes Agent running.
       Collect a real session, verify staging file created.
       This is the integration validation for the plugin rewrite.

8. End-to-end LLM scrub test
   └── Depends on: (5)-(6), Ollama running with Hermes 3 8B Q4.
       Run preview --llm-scrub on a staging file with known content.

9. Fine-tuning data export validation
   └── Depends on: (7) — at least one real session collected.
       kajiba export --format sharegpt → verify JSONL schema matches
       Unsloth's expected format.
       No code changes expected at this step.
```

**Highest risk item:** Step 2 (collector signature change). It touches `on_session_start` which is called by the existing 356-test suite. The change must be backwards-compatible (optional kwargs with defaults) or tests must be updated. Budget time for test updates.

**Lowest risk item:** Step 5 (scrubber_llm implementation). The interface is already defined in the stub. Only the body changes. Tests can use a mock `model_fn` — no real Ollama required for unit tests.

**Parallelizable:** Steps 1+5 can be started simultaneously with step 2. The plugin skeleton and the LLM scrubber have no mutual dependency.

---

## Sources

- [Hermes Agent — Build a Hermes Plugin](https://hermes-agent.nousresearch.com/docs/guides/build-a-hermes-plugin/) — PRIMARY SOURCE for hook names, callback signatures, plugin.yaml format, ctx API. HIGH confidence — official NousResearch documentation verified 2026-04-02.
- [NousResearch/hermes-agent RELEASE_v0.5.0.md](https://github.com/NousResearch/hermes-agent/blob/main/RELEASE_v0.5.0.md) — Confirms four lifecycle hooks activated in v0.5.0: pre/post_llm_call, on_session_start, on_session_end. HIGH confidence — official release notes.
- [NousResearch/hermes-agent RELEASE_v0.6.0.md](https://github.com/NousResearch/hermes-agent/blob/main/RELEASE_v0.6.0.md) — v0.6.0 adds profiles, MCP server mode; no breaking plugin API changes identified. HIGH confidence — official release notes.
- [Ollama Python library](https://github.com/ollama/ollama) — OpenAI-compatible API, `format="json"` parameter for structured output. HIGH confidence — official Ollama project.
- [DZone — Local SLMs for PII Scrubbing](https://dzone.com/articles/the-ai-firewall-using-local-small-language-models) — Pattern of using local 3B-8B models for PII detection with structured JSON output. MEDIUM confidence — practitioner article, approach corroborated by multiple sources.
- [Markaicode — Reliable Structured Output from Local LLMs](https://markaicode.com/ollama-structured-output-pipeline/) — format="json" + Pydantic validation + retry resolves >95% of structured output issues. MEDIUM confidence — community guide, consistent with Ollama official docs.
- [Unsloth Fine-tuning Guide](https://unsloth.ai/docs/get-started/fine-tuning-llms-guide) — Llama 3.2 3B fits in 8GB VRAM with 4-bit QLoRA; ShareGPT format directly supported. HIGH confidence — official Unsloth documentation.

---
*Architecture research for: Kajiba v1.1 Hermes Plugin Integration + LLM PII Scrubbing*
*Researched: 2026-04-02*
