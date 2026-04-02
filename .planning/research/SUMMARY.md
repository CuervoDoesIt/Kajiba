# Project Research Summary

**Project:** Kajiba
**Domain:** Community AI Training Data Pipeline -- Hermes Plugin Integration + Local Fine-Tuning Validation
**Researched:** 2026-04-02
**Confidence:** HIGH

## Executive Summary

Kajiba v1.1 is a milestone that transforms Kajiba from a standalone data pipeline into a live Hermes Agent plugin that collects real coding session data, scrubs it for PII, and validates the end-to-end flow by fine-tuning a local LLM on the output. The existing v1.0 codebase (schema, regex scrubber, quality scorer, CLI, publisher) is solid and largely unchanged. The v1.1 work concentrates on three vertical additions at the pipeline's edges: a new Plugin Entry Layer replacing the incorrect Protocol-based integration with Hermes's real `register(ctx)` plugin API, a semantic PII scrubbing layer that fills the `scrubber_llm.py` stub, and a fine-tuning validation experiment that proves the exported data actually trains a model. The core data flow (collect, scrub, score, publish) is architecturally unchanged.

The recommended approach is a strict four-phase build ordered by dependencies. Phase 1 establishes the WSL2 + Hermes + Ollama development environment and the plugin scaffold -- nothing else can proceed without confirmed hook firing. Phase 2 implements turn capture from Hermes's separate hook streams and the semantic PII scrubber (using GLiNER, not generative LLM prompting). Phase 3 validates the pipeline end-to-end via HITL manual review. Phase 4 runs the QLoRA fine-tuning experiment as the milestone gate. The two researchers (FEATURES and ARCHITECTURE) independently arrived at essentially the same phase structure, which is a strong signal that the ordering is correct.

The key risks are: (1) the Hermes plugin API uses a completely different wiring model than the current code assumes -- this is not a refactor, it is a greenfield rewrite of the integration layer; (2) LLM-based PII scrubbing has a high false positive rate on code content if thresholds are too aggressive, corrupting the training data; and (3) the WSL2 + CUDA environment has several silent failure modes (CUDA driver stub overwrite, Ollama context truncation, network binding) that waste days if not caught on day one. All three risks are well-documented and have clear prevention strategies identified in the research.

## Key Findings

### Recommended Stack

The existing core stack (Python 3.11+, Pydantic v2, Click, Rich) is unchanged. The v1.1 additions are narrowly scoped.

**Core new technologies:**
- **Hermes Agent v0.6.0** -- plugin host. Kajiba rewrites as a real plugin using `register(ctx)` and `ctx.register_hook()`. The current Protocol-based `hermes_integration.py` is wrong and must be replaced entirely.
- **GLiNER (`nvidia/gliner-pii`)** -- semantic PII detection. 570M parameter span-tagging model, ~75ms per text chunk on CPU, Strict F1 0.87. Replaces the original plan of Ollama-based generative prompting, which is 20-50x slower and lower precision. Self-contained Python package, no external process required.
- **Ollama Python client (>=0.6.1)** -- model metadata capture via `ollama.show()` and optional LLM scrubbing fallback. Not used for primary PII detection (GLiNER handles that).
- **pydantic-settings (>=2.13.1)** -- typed configuration management replacing ad-hoc YAML reads. Supports TOML, env vars, and `.env` files with `KAJIBA_` prefix.
- **filelock (>=3.25.2)** -- cross-platform lock preventing concurrent plugin instances.

**QLoRA experiment stack (external to Kajiba, NOT shipped):**
- Unsloth + TRL + PEFT + bitsandbytes for QLoRA fine-tuning of Llama 3.2 3B on RTX 4070 8GB. Documented as a consumer-side operation, not a Kajiba feature.

**Critical version note:** Hermes v0.6.0 introduced HERMES_HOME profile isolation. All hardcoded `~/.hermes` paths in Kajiba must be replaced with `get_hermes_home()` (plugin context) or `HERMES_HOME` env var (CLI context).

**Stack divergence between researchers:** STACK.md recommended Presidio + spaCy for NER-based PII detection (Pass 2) with Ollama as optional Pass 3. FEATURES.md recommended GLiNER as the primary semantic PII approach, noting it is faster, more accurate, and self-contained. The FEATURES.md recommendation is stronger -- GLiNER is purpose-built for PII span detection with structured output, while Presidio adds orchestration overhead Kajiba does not need. **Recommendation: Use GLiNER as the semantic PII layer. Drop Presidio and spaCy from the dependency list.** The regex scrubber (existing) handles structured PII; GLiNER handles named entities. This is a two-pass pipeline, not three.

### Expected Features

**Must have (table stakes -- milestone blocked without these):**
- Kajiba rewritten as real Hermes plugin (`register(ctx)`, `plugin.yaml`, `~/.hermes/plugins/kajiba/`)
- Turn capture from separate `post_llm_call` and `post_tool_call` hook streams, assembled into `ConversationTurn` + `ToolCall` objects
- WSL2 + Hermes + Ollama development environment (documented, reproducible, GPU-verified)
- Semantic PII scrubbing via GLiNER replacing the `scrubber_llm.py` stub
- HITL session collection with manual review at each pipeline step
- End-to-end pipeline validation: collect real data, scrub, score, publish, download, fine-tune

**Should have (differentiators):**
- Plugin installable via `pip install kajiba[hermes]` entry point (reduces setup friction)
- `pre_llm_call` context injection for optional dataset quality hints (off by default)

**Defer (v2+):**
- Full fine-tuning tooling inside Kajiba (Kajiba is the pipeline, not the training framework)
- HuggingFace dataset upload (already planned as deferred)
- Ollama as a hard core dependency (GLiNER is self-contained)

### Architecture Approach

The v1.1 architecture adds three vertical concerns to the existing pipeline without restructuring the core data flow. A new Plugin Entry Layer (`~/.hermes/plugins/kajiba/`) replaces the Protocol stub, a new Semantic Scrub Layer is inserted between regex scrub and quality scoring, and the existing export format layer serves fine-tuning consumers as-is. The plugin directory is a separate artifact from the Python package -- it imports from the installed `kajiba` library via `from kajiba.collector import KajibaCollector`. This separation keeps the collector testable independently of Hermes.

**Major components:**
1. **Plugin directory** (`~/.hermes/plugins/kajiba/`) -- `register(ctx)` entry point, hook handlers that map Hermes kwargs to `KajibaCollector` methods. Module-level singleton collector instance.
2. **KajibaCollector** (modified) -- accepts new `model_name` + `platform` kwargs alongside existing `model_config` for backwards compatibility. Pending turn buffer for assembling turns from multiple hook fires.
3. **Semantic scrubber** (`scrubber_llm.py`) -- GLiNER-based PII detection with confidence thresholds. Auto-redact high confidence (>=0.7), flag medium (>=0.4) for HITL review, ignore low. Called per-turn, not per-record, to stay within model attention range.
4. **HITL state machine** -- `pipeline_stage` field on staging records (`captured`, `regex_scrubbed`, `llm_reviewed`, `scored`, `approved`) enabling resumable review workflows.

### Critical Pitfalls

1. **Protocol vs Plugin API mismatch (MP-1)** -- The existing `hermes_integration.py` uses `agent.on(event, cb)` which does not exist in the real Hermes API. The plugin appears to load but captures zero turns. Treat the rewrite as greenfield, not a refactor. Verify `on_session_start` fires before writing any capture logic.

2. **HERMES_HOME profile isolation (MP-4)** -- Kajiba hardcodes `~/.hermes/kajiba/` but Hermes v0.6.0 profiles use isolated directories. Data goes to the wrong location and `kajiba preview` finds nothing. Use `get_hermes_home()` in plugin code, `HERMES_HOME` env var in CLI.

3. **LLM scrubber false positives on code content (MP-6)** -- Small models flag `user`, `admin`, `UserService` as PII. Corrupts training data. Use GLiNER's confidence threshold (>=0.7 for auto-redact), test against code fixtures, and route medium-confidence to HITL review.

4. **Synchronous Ollama in hook callbacks (MP-7)** -- Calling inference from `post_llm_call` blocks the Hermes event loop 2-15 seconds per turn. Collect raw data in hooks (fast), defer all scrubbing to CLI review step.

5. **WSL2 CUDA driver stub overwrite (MP-8)** -- Installing `cuda` or `cuda-drivers` meta-package inside WSL2 overwrites the GPU stub. Ollama falls back to CPU at 60x slower speed with no visible error. Install only `cuda-toolkit-12-x`. Verify GPU acceleration on day one.

## Implications for Roadmap

Based on combined research, the following four-phase structure is recommended. Both FEATURES.md and ARCHITECTURE.md independently converged on this ordering, driven by hard dependencies: nothing works without the environment and plugin scaffold, turn capture and scrubbing depend on the plugin, validation depends on working capture and scrubbing, and fine-tuning depends on validated data.

### Phase 1: Environment + Plugin Foundation
**Rationale:** Every other phase depends on a working Hermes plugin that actually receives hook events. The WSL2 + Ollama environment must be validated with GPU acceleration before any real data collection. This is the gate.
**Delivers:** Working dev environment (WSL2, Hermes v0.6.0, Ollama, GPU-verified); plugin directory with `plugin.yaml` + `register(ctx)` that Hermes discovers and loads; confirmed hook firing for `on_session_start` and `post_llm_call`; HERMES_HOME-aware path resolution; IP regex false positive fix (CP-5).
**Addresses features:** WSL2 environment setup, Hermes plugin rewrite, hook payload shape discovery.
**Avoids pitfalls:** MP-1 (Protocol vs plugin mismatch), MP-2 (hook argument `**kwargs`), MP-3 (`pre_llm_call` safety), MP-4 (HERMES_HOME paths), MP-8 (CUDA stub overwrite), MP-9 (Ollama network binding), CP-5 (IP regex false positives).

### Phase 2: Turn Capture + Semantic PII Scrubbing
**Rationale:** With hooks firing, implement the actual data capture logic (assembling turns from separate hook streams) and the semantic scrubber (the largest privacy gap). These two features are independent of each other and can be developed in parallel, but both must complete before HITL validation makes sense.
**Delivers:** Turn assembly from `post_llm_call` + `post_tool_call` into `ConversationTurn` + `ToolCall` objects; GLiNER-based `scrubber_llm.py` implementation with confidence thresholds; `[llm-scrub]` extra in `pyproject.toml`; semantic scrub integrated into `scrub_record()` as Layer C; consent level enforcement (CP-2).
**Addresses features:** Turn capture from separate hook streams, GLiNER semantic PII scrubbing.
**Avoids pitfalls:** MP-5 (context window -- chunk long sessions for GLiNER), MP-6 (false positives -- confidence thresholds + code fixture tests), MP-7 (blocking hooks -- scrubbing only in CLI, never in hooks), CP-1 (regex-only scrubbing gap), CP-2 (consent enforcement).

### Phase 3: HITL Validation + Pipeline Smoke Test
**Rationale:** With data flowing through the pipeline, manually validate every step: collect a real Hermes session, preview the raw capture, compare pre/post scrub, verify quality scoring, approve via review, submit, publish. This is the integration test for all prior phases.
**Delivers:** `kajiba preview --raw` or `kajiba inspect` for pre-scrub verification; `pipeline_stage` state machine for resumable HITL review; manual walkthrough of full pipeline on real session data; verification that `to_sharegpt()` output matches training format expectations.
**Addresses features:** HITL session collection workflow, end-to-end pipeline smoke test.
**Avoids pitfalls:** MP-10 (format incompatibility -- verify before fine-tuning), MP-13 (HITL fragility -- state machine with resume).

### Phase 4: QLoRA Fine-Tune Experiment (Milestone Gate)
**Rationale:** The milestone's success criterion is proving the full loop: Kajiba-collected data can train a model. This phase uses validated, scrubbed data from Phase 3. It is a consumer-side operation documented outside the Kajiba codebase.
**Delivers:** Collected records published to GitHub dataset repo; records downloadable via `kajiba download`; QLoRA fine-tune of Llama 3.2 3B on Kajiba data using Unsloth; documented training configuration for RTX 4070 8GB; `docs/fine-tuning-guide.md`.
**Addresses features:** End-to-end pipeline validation, QLoRA fine-tune experiment.
**Avoids pitfalls:** MP-10 (format conversion via `to_sharegpt()` + `standardize_sharegpt()`), MP-11 (OOM -- batch_size=1, paged_adamw_8bit, max_seq_length=2048), MP-12 (chat template -- verify `<|start_header_id|>` markers in tokenized output).

### Phase Ordering Rationale

- **Phase 1 before everything:** Hard gate. Without confirmed hook firing, no data enters the pipeline. Without GPU-verified WSL2, inference is 60x slower and the fine-tuning experiment is impossible.
- **Phase 2 parallelizable internally:** Turn capture (hooks.py + collector changes) and GLiNER scrubber (scrubber_llm.py) have no mutual dependency. Both can be developed simultaneously.
- **Phase 3 after Phase 2:** HITL review only makes sense with real data flowing through both scrub layers. Running it earlier would validate the wrong thing.
- **Phase 4 last:** Depends on real published data. The fine-tuning experiment is the milestone's exit criterion, not a development dependency.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1:** Hermes hook payload field names need empirical verification against a live Hermes v0.6.0 session. Official docs confirm hook names and purposes but do not publish a formal payload schema. The first task of Phase 1 is running Hermes with a logging-only plugin stub to capture actual kwargs.
- **Phase 2 (GLiNER):** FEATURES.md recommends GLiNER over the Ollama-based approach from STACK.md. This pivot needs validation: confirm `nvidia/gliner-pii` model download works, confirm Python API matches documented usage, confirm threshold tuning produces acceptable false positive rates on code content. Budget a spike task at the start of Phase 2.
- **Phase 4:** QLoRA configuration for RTX 4070 8GB is documented in practitioner guides but not verified on this specific hardware. The training configuration (batch_size=1, paged_adamw_8bit, max_seq_length=2048) needs empirical validation. Budget a setup/debug day.

Phases with standard patterns (skip deep research):
- **Phase 3:** HITL review is CLI UX work using existing commands. The `pipeline_stage` state machine is a straightforward addition. No novel patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core technologies verified via official docs and PyPI. Hermes plugin API confirmed against official NousResearch documentation. Version compatibility matrix is clean. |
| Features | HIGH | Hermes plugin API verified against official docs. GLiNER PII model verified against HuggingFace model card. Feature dependency graph independently corroborated by architecture research. |
| Architecture | HIGH | Plugin wiring pattern confirmed by multiple real-world Hermes plugins (42-evey/hermes-plugins, Hindsight integration). Data flow changes are additive, not restructuring. |
| Pitfalls | HIGH | Hermes-specific pitfalls sourced from official docs and release notes. WSL2/CUDA pitfalls corroborated by NVIDIA and Microsoft official documentation. QLoRA pitfalls from Unsloth official docs and practitioner reports. |

**Overall confidence:** HIGH

### Gaps to Address

- **Hermes hook payload schema:** Official docs confirm hook names and purpose but do not publish formal kwargs schemas. Field names (`user_message`, `assistant_response`, `conversation_history`) are inferred from docs and community plugins. Must be empirically confirmed in Phase 1 with a logging stub.
- **GLiNER vs Presidio+spaCy decision:** STACK.md and FEATURES.md diverge on the semantic PII approach. This summary recommends GLiNER. The STACK.md Presidio recommendation should be considered deprecated unless GLiNER validation in Phase 2 reveals unexpected issues, in which case Presidio is the fallback.
- **`post_tool_call` result type:** PITFALLS.md notes that `result` may be a JSON string, not a Python dict. Must verify empirically and add `json.loads()` if needed.
- **Consent level enforcement (CP-2):** Declared in schema but never enforced at export time. Must be implemented before any real contributor data is accepted. Slotted for Phase 2.
- **Metadata fingerprinting (CP-3):** Hardware profile anonymization (VRAM rounding, timestamp jitter, GPU generalization) -- existing code in `privacy.py` may already handle this. Verify coverage before Phase 3.

## Sources

### Primary (HIGH confidence)
- [Hermes Agent Plugin Guide](https://hermes-agent.nousresearch.com/docs/guides/build-a-hermes-plugin/) -- plugin.yaml format, register(ctx) signature, hook event table
- [Hermes Agent v0.5.0 Release Notes](https://github.com/NousResearch/hermes-agent/blob/main/RELEASE_v0.5.0.md) -- pre/post_llm_call hooks added
- [Hermes Agent v0.6.0 Release Notes](https://github.com/NousResearch/hermes-agent/blob/main/RELEASE_v0.6.0.md) -- HERMES_HOME, profiles, plugin enable/disable
- [nvidia/gliner-PII HuggingFace model card](https://huggingface.co/nvidia/gliner-PII) -- 570M params, 55+ entity types, F1 0.87
- [NVIDIA CUDA on WSL User Guide](https://docs.nvidia.com/cuda/wsl-user-guide/index.html) -- driver stub architecture
- [Ollama Python client](https://github.com/ollama/ollama-python) -- official SDK, ollama.show() API
- [Ollama Context Length docs](https://docs.ollama.com/context-length) -- num_ctx vs reported context length
- [Unsloth Fine-tuning Guide](https://unsloth.ai/docs/get-started/fine-tuning-llms-guide) -- QLoRA config, VRAM requirements
- [Unsloth Chat Templates](https://docs.unsloth.ai/basics/chat-templates) -- Llama 3 template requirements

### Secondary (MEDIUM confidence)
- [42-evey/hermes-plugins](https://github.com/42-evey/hermes-plugins) -- real-world plugin directory structure examples
- [Hindsight Hermes integration](https://hindsight.vectorize.io/sdks/integrations/hermes) -- post_llm_call capture pattern confirmed
- [InsiderLLM WSL2 + Ollama guide](https://insiderllm.com/guides/wsl2-ollama-windows-setup-guide/) -- file system performance, network binding
- [QLoRA original paper](https://arxiv.org/abs/2305.14314) -- quality over quantity for small dataset fine-tuning
- [HuggingFace Cookbook PII detection](https://huggingface.co/learn/cookbook/llm_gateway_pii_detection) -- false positive/negative analysis

### Tertiary (LOW confidence)
- Hermes hook payload field names (documented purpose but not formal schema -- requires empirical validation)

---
*Research completed: 2026-04-02*
*Ready for roadmap: yes*
