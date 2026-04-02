# Stack Research

**Domain:** Community AI Training Data Pipeline — Hermes Plugin + Local Fine-tuning
**Researched:** 2026-04-02
**Confidence:** HIGH (core technologies verified via official docs, PyPI, and Hermes official docs)

---

## Context: Existing Stack (Do Not Change)

The following are already established and in production. This document covers only **new additions** needed for the active milestone.

| Technology | Version | Role |
|---|---|---|
| Python | 3.11+ | Primary language |
| Pydantic | >=2.0 | Schema and validation |
| Click | >=8.0 | CLI framework |
| Rich | >=13.0 | Terminal output |
| pytest + pytest-cov | >=7.0 / >=4.0 | Testing |
| setuptools + wheel | >=68.0 | Build backend |

---

## Recommended Stack

### New Core Technologies

| Technology | Recommended Version | Purpose | Why |
|---|---|---|---|
| Hermes Agent | v0.6.0 (v2026.3.30) | Plugin host — Kajiba rewrites `hermes_integration.py` as a real plugin | The current `hermes_integration.py` uses a Protocol-based injection model built against an assumed API. Real Hermes plugins live in `~/.hermes/plugins/<name>/`, expose a `register(ctx)` entry point, and use `ctx.register_hook()` for lifecycle events. v0.6.0 is the current stable release. No pip install — installed via the Hermes install script. |
| `ollama` (Python client) | `>=0.6.1` | LLM backend for semantic PII scrubbing (Pass 3) and model metadata capture | Official first-party client (0.6.1, Nov 2025). AsyncClient available for non-blocking calls. `ollama.show(model_name)` returns `details.parameter_size`, `details.quantization_level`, `details.family`, and `model_info` context length — solves model config capture alongside scrubbing. |
| `presidio-analyzer` | `>=2.2.362` | Structured NER-based PII detection (Pass 2) | Microsoft-maintained, actively updated (2.2.362, Mar 2026). Combines spaCy NER with rule-based recognizers. Detects PERSON, ORG, LOCATION entities that regex misses. Fully local — no network required. Use as primary NER layer; Ollama LLM as optional semantic fallback for ambiguous cases. |
| `presidio-anonymizer` | `>=2.2.362` | Replace/redact detected PII spans | Paired with presidio-analyzer. Handles span replacement with typed placeholders (`<PERSON>`, `<ORG>`). Ships at the same version as analyzer. |
| `spacy` | `>=3.8.14` | NLP engine backing Presidio | Required by presidio-analyzer as its default NER engine (3.8.14, Mar 2026). Requires post-install model download: `python -m spacy download en_core_web_lg`. Use the large model (`en_core_web_lg`) not `en_core_web_sm` — larger recall matters more than speed for PII work. |
| `pydantic-settings` | `>=2.13.1` | Typed, validated configuration management | Already using Pydantic v2. pydantic-settings (2.13.1, Feb 2026) replaces the current ad-hoc `~/.hermes/config.yaml` read. Supports TOML (via stdlib `tomllib`), YAML, env vars, and `.env` files. Add `KAJIBA_` prefix support for env var overrides. |

### Supporting Libraries

| Library | Recommended Version | Purpose | When to Use |
|---|---|---|---|
| `psutil` | `>=7.2.2` | RAM detection in hardware profiler | Already conditionally imported — promote to declared optional dependency. Needed for accurate RAM reporting on non-Linux systems. |
| `pyyaml` | `>=6.0` | Read existing Hermes `~/.hermes/config.yaml` | Already conditionally imported. Keep as optional dep until pydantic-settings replaces it fully. |
| `filelock` | `>=3.25.2` | Prevent concurrent Kajiba plugin instances | Lightweight cross-platform lock. Create `~/.hermes/kajiba/kajiba.lock` on collector start; release on `on_session_end`. 3.25.2, Mar 2026. |

### QLoRA Fine-tuning Experiment (External Tooling — NOT shipped in Kajiba)

These libraries are needed for the end-to-end pipeline validation experiment (fine-tuning a 3B model on Kajiba-collected data). They are NOT added to Kajiba's `pyproject.toml`. Document in `docs/fine-tuning-experiment.md` as a separate setup guide.

| Library | Recommended Version | Purpose | Why |
|---|---|---|---|
| `unsloth` | `>=2026.3.18` | QLoRA fine-tuning engine | Current version 2026.3.18 (Mar 2026). 2x faster training and up to 70% less VRAM than vanilla HuggingFace. RTX 4070 (Ampere, 8GB VRAM) is explicitly supported. Install via `pip install unsloth` with PyTorch pre-installed, or use `curl -fsSL https://unsloth.ai/install.sh | sh` in WSL2. |
| `trl` | `>=1.0.0` | SFTTrainer for supervised fine-tuning | Current version 1.0.0 (Mar 2026). Built on HuggingFace Transformers. `SFTTrainer` handles dataset batching, gradient accumulation, and PEFT integration in one API. Required by Unsloth. |
| `peft` | `>=0.18.1` | LoRA / QLoRA adapter management | Current version 0.18.1 (Jan 2026). `LoraConfig` specifies `r`, `lora_alpha`, `target_modules`. Directly integrated with `transformers` and `trl`. |
| `bitsandbytes` | `>=0.49.2` | 4-bit NF4 quantization for QLoRA | Current version 0.49.2 (Feb 2026). Enables loading Llama 3.2 3B in ~2GB VRAM (NF4 format), leaving headroom for activations and gradients. Requires PyTorch >=2.3. RTX 4070 Compute Capability 8.6 is well within supported range (CC 6.0+). |
| `transformers` | `>=4.47.0` | Model loading, tokenizer, trainer base | Underpins trl and peft. Version 4.47.0 confirmed compatible with trl 0.12.0 in published guides. TRL 1.0.0 is built on top — use latest transformers. |
| `datasets` | `>=3.0.0` | Load Kajiba JSONL as HuggingFace Dataset | Standard HuggingFace datasets library. `load_dataset("json", data_files=...)` reads JSONL shards directly. Required for SFTTrainer's `dataset` argument. |
| `accelerate` | `>=0.30.1` | Multi-GPU / mixed-precision training coordinator | Required by transformers Trainer. Handles device placement and bf16/fp16 mixed precision. Even for single-GPU RTX 4070 this is needed. |

### Development Tools (No Change Needed)

The existing pytest + pytest-cov setup is adequate. No new dev tools are required for this milestone.

---

## Hermes Plugin API Reference

This section documents the real Hermes plugin API that Kajiba must implement. The current `hermes_integration.py` used a Protocol-based injection model that does not match this API.

### Plugin Directory Layout

```
~/.hermes/plugins/kajiba/
├── plugin.yaml        # Manifest — Hermes reads this at startup
├── __init__.py        # Entry point — must define register(ctx)
├── hooks.py           # Hook callback implementations
└── tools.py           # Any Kajiba-provided tools (optional)
```

### plugin.yaml Format

```yaml
name: kajiba
version: 1.1.0
description: Collect AI session data for community fine-tuning dataset
provides_tools: []          # Kajiba provides no tools, only hooks
provides_hooks:
  - on_session_start
  - pre_llm_call
  - post_llm_call
  - post_tool_call
  - on_session_end
# requires_env:             # Uncomment if needed
#   - KAJIBA_OLLAMA_HOST
```

### register(ctx) Entry Point

```python
# ~/.hermes/plugins/kajiba/__init__.py
def register(ctx):
    """Called once at startup. Wire hook callbacks into Hermes."""
    from .hooks import (
        on_session_start,
        on_pre_llm_call,
        on_post_llm_call,
        on_post_tool_call,
        on_session_end,
    )
    ctx.register_hook("on_session_start", on_session_start)
    ctx.register_hook("pre_llm_call",     on_pre_llm_call)
    ctx.register_hook("post_llm_call",    on_post_llm_call)
    ctx.register_hook("post_tool_call",   on_post_tool_call)
    ctx.register_hook("on_session_end",   on_session_end)
```

### Hook Event Signatures

| Hook | Arguments Received | Return Value | Notes |
|---|---|---|---|
| `on_session_start` | `session_id`, `model`, `platform` | None | First turn only. Map `model` + `platform` → `KajibaCollector.on_session_start()`. |
| `pre_llm_call` | `session_id`, `user_message`, `conversation_history`, `is_first_turn`, `model`, `platform` | Optional `{"context": "..."}` | If returns dict with `"context"` key, value is appended to ephemeral system prompt. Kajiba should return `None` — it's an observer only, not a context injector. |
| `post_llm_call` | `session_id`, `user_message`, `assistant_response`, `conversation_history`, `model`, `platform` | None | Primary turn capture hook. Contains full turn data needed for `ConversationTurn` records. |
| `post_tool_call` | `tool_name`, `args`, `result`, `task_id` | None | Fires for ALL tool calls, not just plugin-registered ones. Use to capture `ToolCall` records. |
| `on_session_end` | `session_id`, `completed`, `interrupted`, `model`, `platform` | None | `completed=True` for normal exit; `interrupted=True` for ctrl-C. Trigger `KajibaCollector.on_session_end()`. |

### Key Differences From Current `hermes_integration.py`

| Current (Wrong) | Required (Correct) |
|---|---|
| Protocol class `HermesAgent` with `agent.on(event, cb)` | `register(ctx)` function with `ctx.register_hook(event, cb)` |
| Import-and-inject pattern: caller passes agent object | Auto-discovery: Hermes loads plugin from `~/.hermes/plugins/kajiba/` at startup |
| No `plugin.yaml` manifest | `plugin.yaml` manifest required for discovery |
| `on_session_start(session_id, model_config)` | `on_session_start(session_id, model, platform)` |
| No `pre_llm_call` hook | `pre_llm_call` fires once per turn before LLM (available since v0.5.0) |
| No distinction between LLM and tool events | Separate `post_llm_call` and `post_tool_call` streams |
| `register_hooks(agent)` returns `KajibaCollector` | No return value from `register(ctx)`; collector held in module state |

### Ollama as Hermes Provider

Hermes v0.6.0 treats Ollama as a custom OpenAI-compatible endpoint — not a first-class provider. Configure via `hermes model`, select "Custom endpoint":

```yaml
# ~/.hermes/config.yaml (Hermes config, not Kajiba config)
provider: custom
base_url: "http://localhost:11434/v1"
api_key: "ollama"
model: "hermes3:8b-llama3.1-q4_K_M"
```

The `platform` argument received in hook callbacks will be `"custom"` when Ollama is the provider. `model` will be the exact model string (e.g., `"hermes3:8b-llama3.1-q4_K_M"`). Kajiba can use this to populate `ModelMetadata.provider = "ollama"` and pass the model string to `ollama.show()` for full metadata retrieval.

---

## Installation

### Kajiba Dependencies (add to pyproject.toml)

```bash
# Core new deps
pip install "ollama>=0.6.1"
pip install "presidio-analyzer>=2.2.362" "presidio-anonymizer>=2.2.362"
pip install "spacy>=3.8.14"
pip install "pydantic-settings>=2.13.1"

# spaCy model (post-install step — document in README)
python -m spacy download en_core_web_lg

# Supporting optional deps
pip install "filelock>=3.25.2" "psutil>=7.2.2" "pyyaml>=6.0"
```

Suggested `pyproject.toml` extras structure:

```toml
[project.optional-dependencies]
llm-scrub = [
    "ollama>=0.6.1",
    "presidio-analyzer>=2.2.362",
    "presidio-anonymizer>=2.2.362",
    "spacy>=3.8.14",
]
config = [
    "pydantic-settings>=2.13.1",
    "pyyaml>=6.0",
]
upload = ["huggingface_hub>=0.19"]   # existing, unchanged
dev = ["pytest>=7.0", "pytest-cov>=4.0"]  # existing, unchanged
all = [
    "kajiba[llm-scrub]",
    "kajiba[config]",
    "kajiba[upload]",
    "kajiba[dev]",
    "filelock>=3.25.2",
    "psutil>=7.2.2",
]
```

### QLoRA Experiment (separate WSL2 environment — NOT in Kajiba)

```bash
# In WSL2 with CUDA 12.x and PyTorch pre-installed
pip install "torch>=2.3.0" --index-url https://download.pytorch.org/whl/cu124
pip install "unsloth>=2026.3.18"
pip install "trl>=1.0.0"
pip install "peft>=0.18.1"
pip install "bitsandbytes>=0.49.2"
pip install "transformers>=4.47.0"
pip install "datasets>=3.0.0"
pip install "accelerate>=0.30.1"
```

Or use Unsloth's installer (handles PyTorch + CUDA detection automatically):

```bash
curl -fsSL https://unsloth.ai/install.sh | sh
pip install "trl>=1.0.0" "datasets>=3.0.0"
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|---|---|---|---|
| Fine-tuning engine | `unsloth` | `transformers` Trainer directly | Unsloth is 2x faster, 70% less VRAM, and drop-in compatible with TRL. On RTX 4070 (8GB), vanilla transformers may OOM on a 3B model with QLoRA — Unsloth's custom CUDA kernels prevent this. No reason to use vanilla Trainer when Unsloth wraps it transparently. |
| Fine-tuning engine | `unsloth` | `axolotl` | Axolotl is a higher-level wrapper with more config options but adds complexity and is YAML-driven. For a one-shot fine-tuning experiment in a Jupyter notebook, Unsloth's Python API is more transparent and easier to debug. |
| LLM PII scrubbing backend | `ollama` Python client | `transformers` + `torch` locally | Transformers requires 2GB+ PyTorch install and CUDA configuration. Breaks the "no heavy dependencies for core pipeline" constraint. Contributors should not need CUDA to run Kajiba. Use Ollama to abstract the model runtime — contributors just run `ollama pull qwen2.5:3b`. |
| NER/PII detection | `presidio-analyzer` + `spacy` | Pure Ollama LLM for all PII | LLM inference for every record is slow (~500ms-2s per call vs. <50ms for spaCy NER). Use spaCy/Presidio for structural entities (PERSON, ORG, LOCATION) and Ollama only as optional Pass 3 for ambiguous semantic PII. |
| NER/PII detection | `presidio-analyzer` + `spacy` | `spacy` alone | Presidio adds regex recognizers on top of spaCy NER — covers emails, phone numbers, credit cards, SSNs, crypto wallets out of the box. No reason not to use it when it wraps spaCy anyway. |
| Config management | `pydantic-settings` | Plain `pyyaml` + dict | Current approach. Untyped, no validation, no env var support. pydantic-settings costs almost nothing (Pydantic v2 already present) and eliminates runtime config errors. |
| 4-bit quantization | `bitsandbytes` | `llama-cpp-python` | llama-cpp-python requires compiling from source with correct CUDA flags. Bitsandbytes works inside the PyTorch/HuggingFace ecosystem directly and is required by Unsloth anyway. Use bitsandbytes for the experiment. |

---

## What NOT to Use

| Library / Approach | Reason | Use Instead |
|---|---|---|
| `langchain` or `llama-index` for PII scrubbing | Massive dependency trees (40+ transitive packages) for a feature that needs 20 lines of ollama client code. | `ollama` client + `presidio-analyzer` |
| Cloud-based PII services (AWS Comprehend, Azure Text Analytics) | Sending user session data to cloud APIs for PII detection violates Kajiba's core privacy contract. | `presidio-analyzer` + `spacy` (fully local) |
| `presidio-analyzer` with `stanza` NLP engine | Stanza is significantly slower than spaCy for comparable English NER accuracy. | `spacy` `en_core_web_lg` |
| `presidio-analyzer` with `en_core_web_trf` transformer model | The trf model requires `spacy-transformers` and GPU for practical speed. On CPU it is 10x slower than `en_core_web_lg`. Accuracy gain is marginal for PII entity types. | `en_core_web_lg` (CNN-based, fast, accurate enough) |
| `DVC` for dataset versioning | Full ML experiment tracking system. Kajiba's publishing needs are simple: organize by `model/tier/`, commit JSONL, push. GitPython is sufficient. DVC creates a parallel versioning system that confuses contributors. | GitPython or subprocess |
| `celery` / `dramatiq` for background collection | Message queue brokers (Redis/RabbitMQ) required. Kajiba is a local CLI tool — background scheduling is not needed for the current milestone. | Not needed yet; if needed later, use APScheduler |
| APScheduler 4.x | In alpha as of early 2026, significantly different API from 3.x. Not stable. | `APScheduler>=3.11.2,<4.0` if background mode is added |
| HuggingFace inference API for LLM scrubbing | Network call — violates local-first constraint and is a privacy hazard when processing user session data. | `ollama` + local model |

---

## Stack Patterns by Variant

### Pattern 1: Semantic PII Scrubbing (Three-Pass)

Fastest and most reliable approach for semantic PII detection on session records:

1. **Pass 1 — Regex** (existing `scrubber.py`): Catches paths, tokens, keys, IPs, emails, phones, hex tokens. Fast, zero-overhead.
2. **Pass 2 — Presidio + spaCy NER** (new `scrubber_ner.py`): Catches PERSON, ORG, LOCATION entities. ~20-50ms per record. Fully local.
3. **Pass 3 — Ollama LLM** (existing stub `scrubber_llm.py`, now implemented): Sends Pass-1+2 output to a small local model (e.g., `qwen2.5:3b`) with a structured prompt asking it to identify remaining personal identifiers. ~500ms-2s per record. Only runs when `llm_pii_scrub: true` AND Ollama is available. Gracefully skipped if Ollama is unreachable.

Pass 3 should never block or fail hard — wrap in `try/except` and log if Ollama is unavailable.

### Pattern 2: Hermes Plugin Hook Mapping

Map Hermes hooks to existing KajibaCollector methods:

| Hermes Hook | KajibaCollector Method | Data Mapping |
|---|---|---|
| `on_session_start(session_id, model, platform)` | `on_session_start(session_id, model_config)` | Build `model_config` dict from `model` + `platform` + `ollama.show()` |
| `post_llm_call(session_id, user_message, assistant_response, ...)` | `on_turn_complete(turn_dict)` | Build `turn_dict` as `{"from": "human", "value": user_message}` + `{"from": "gpt", "value": assistant_response}` |
| `post_tool_call(tool_name, args, result, task_id)` | Append to current turn's `tool_calls` list | Build `ToolCall` dict from `tool_name`, `args`, `result` |
| `on_session_end(session_id, completed, interrupted, ...)` | `on_session_end(session_id)` | Pass through; `completed`/`interrupted` → `OutcomeSignals.outcome` |

### Pattern 3: Model Metadata from Ollama

Use `ollama.show(model_name)` to populate `ModelMetadata` at session start:

```python
import ollama

info = ollama.show(model_name)
model_config = {
    "model_name": model_name,
    "provider": "ollama",
    "parameter_size": info.details.parameter_size,       # "8.0B"
    "quantization": info.details.quantization_level,    # "Q4_K_M"
    "family": info.details.family,                       # "llama"
    "context_length": info.model_info.get("llama.context_length"),
}
```

For non-Ollama providers (OpenAI, Anthropic via API), the `platform` argument in hooks identifies the provider; `model` gives the model string. Fall back to user-provided config for metadata.

### Pattern 4: QLoRA Experiment Data Flow

```
kajiba download --model hermes3-8b --tier gold --format sharegpt \
    --output ./kajiba-dataset/

# Convert to Unsloth-compatible format
# (Unsloth accepts ShareGPT format natively via TRL's SFTTrainer)

unsloth fine-tune:
  FastLanguageModel.from_pretrained("unsloth/Llama-3.2-3B-Instruct-bnb-4bit")
  + LoraConfig(r=16, target_modules=["q_proj","k_proj","v_proj","o_proj",...])
  + SFTTrainer(dataset=load_dataset("json", data_files="./kajiba-dataset/*.jsonl"))
  → saved adapter at ./kajiba-lora/
  → merged model → ollama create kajiba-3b-v1
```

The ShareGPT format output from `kajiba download` feeds directly into Unsloth's SFTTrainer without reformatting.

### Pattern 5: Configuration with pydantic-settings

Replace ad-hoc YAML read in `cli.py` with a `KajibaConfig` class:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class KajibaConfig(BaseSettings):
    model_config = SettingsConfigDict(
        toml_file="~/.hermes/kajiba/config.toml",
        env_prefix="KAJIBA_",
    )
    consent_level: str = "full"
    auto_submit: bool = False
    llm_pii_scrub: bool = True
    scrub_strictness: str = "high"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    dataset_repo_path: Optional[str] = None
```

Env var overrides work out of the box: `KAJIBA_OLLAMA_MODEL=hermes3:8b` at the shell level.

---

## Version Compatibility

| Library | Min Python | Notes |
|---|---|---|
| `ollama` 0.6.1 | 3.8+ | AsyncClient available; `ollama.show()` returns `ModelInfo` with details |
| `presidio-analyzer` 2.2.362 | 3.10+ | spaCy 3.x required as NLP engine |
| `presidio-anonymizer` 2.2.362 | 3.10+ | Paired with analyzer — same version |
| `spacy` 3.8.14 | 3.9+ | Kajiba requires 3.11+, no conflict |
| `pydantic-settings` 2.13.1 | 3.8+ | Requires pydantic v2 (already present) |
| `filelock` 3.25.2 | 3.8+ | Cross-platform, no deps |
| `psutil` 7.2.2 | 3.6+ | Already soft-dep in codebase |
| `unsloth` 2026.3.18 | 3.9+ | QLoRA experiment only — not in Kajiba package |
| `trl` 1.0.0 | 3.10+ | QLoRA experiment only |
| `peft` 0.18.1 | 3.10+ | QLoRA experiment only |
| `bitsandbytes` 0.49.2 | 3.10+ | Requires PyTorch >=2.3; CUDA 11.8–13.0 |

All Kajiba package libraries are compatible with Python 3.11+. No conflicts with existing dependencies.

**Hermes Agent note:** v0.6.0 requires Python 3.11 (installed by Hermes's own installer via `uv`). The `pre_llm_call` and `post_llm_call` hooks are available since v0.5.0 (released v2026.3.28). The current integration target is v0.6.0 (v2026.3.30).

**presidio-analyzer Python note:** Requires Python >=3.10. Kajiba's 3.11+ baseline satisfies this with headroom.

**QLoRA VRAM budget on RTX 4070 (8GB):** Llama 3.2 3B in NF4 (bitsandbytes) uses ~1.8GB. LoRA adapters add ~0.3GB. Gradient checkpointing (enabled by Unsloth by default) trades compute for memory. Effective batch size 8 (per_device_train_batch_size=2 + gradient_accumulation_steps=4) fits within 8GB. Confirmed by Unsloth documentation: RTX 40-series explicitly supported.

---

## Sources

- [Hermes Agent Plugin Guide](https://hermes-agent.nousresearch.com/docs/guides/build-a-hermes-plugin/) — plugin.yaml format, register(ctx) signature, hook event table (HIGH confidence)
- [Hermes Agent v0.6.0 release notes](https://github.com/NousResearch/hermes-agent/blob/main/RELEASE_v0.6.0.md) — current stable version, plugin enable/disable, ctx.inject_message() (HIGH confidence)
- [Hermes Agent v0.5.0 release notes](https://github.com/NousResearch/hermes-agent/blob/main/RELEASE_v0.5.0.md) — pre_llm_call, post_llm_call, on_session_start, on_session_end added to agent loop (HIGH confidence)
- [Hermes Agent Configuration docs](https://hermes-agent.nousresearch.com/docs/user-guide/configuration/) — Ollama as custom OpenAI-compatible endpoint via base_url (HIGH confidence)
- [hermes-opencode-plugin GitHub](https://github.com/zaycruz/hermes-opencode-plugin) — real-world plugin directory structure example confirming layout (MEDIUM confidence)
- [ollama PyPI page](https://pypi.org/project/ollama/) — version 0.6.1, released Nov 13, 2025 (HIGH confidence)
- [ollama/ollama-python GitHub](https://github.com/ollama/ollama-python) — official first-party client, httpx-based, async support confirmed (HIGH confidence)
- [presidio-analyzer PyPI page](https://pypi.org/project/presidio-analyzer/) — version 2.2.362, released Mar 15, 2026; Python >=3.10 (HIGH confidence)
- [presidio-anonymizer PyPI page](https://pypi.org/project/presidio-anonymizer/) — version 2.2.362, released Mar 15, 2026 (HIGH confidence)
- [Microsoft Presidio installation docs](https://microsoft.github.io/presidio/installation/) — `pip install presidio_analyzer presidio_anonymizer` + `python -m spacy download en_core_web_lg`; Python 3.10–3.13 support confirmed (HIGH confidence)
- [spaCy PyPI page](https://pypi.org/project/spacy/) — version 3.8.14, released Mar 29, 2026 (HIGH confidence)
- [pydantic-settings PyPI page](https://pypi.org/project/pydantic-settings/) — version 2.13.1, released Feb 19, 2026; TOML/YAML/env support confirmed (HIGH confidence)
- [unsloth PyPI page](https://pypi.org/project/unsloth/) — version 2026.3.18, released Mar 31, 2026; Python <3.15 >=3.9; RTX 40-series supported (HIGH confidence)
- [Unsloth installation docs](https://unsloth.ai/docs/get-started/install/pip-install) — WSL2 install via curl script; CUDA 12.x support (HIGH confidence)
- [trl PyPI page](https://pypi.org/project/trl/) — version 1.0.0, released Mar 30, 2026; Python >=3.10 (HIGH confidence)
- [peft PyPI page](https://pypi.org/project/peft/) — version 0.18.1, released Jan 9, 2026; Python >=3.10 (HIGH confidence)
- [bitsandbytes PyPI page](https://pypi.org/project/bitsandbytes/) — version 0.49.2, released Feb 16, 2026; Python >=3.10; CUDA 11.8–13.0; PyTorch >=2.3 (HIGH confidence)
- [filelock PyPI page](https://pypi.org/project/filelock/) — version 3.25.2, released Mar 11, 2026 (HIGH confidence)

---
*Stack research for: Kajiba v1.1 — Hermes Plugin Integration + Local Fine-tuning Experiment*
*Researched: 2026-04-02*
