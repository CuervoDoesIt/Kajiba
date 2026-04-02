# Feature Research

**Domain:** Hermes Agent Plugin Integration, LLM PII Scrubbing, HITL Data Collection, Fine-Tuning Pipeline Validation
**Researched:** 2026-04-02
**Confidence:** HIGH for Hermes plugin API (official docs verified); HIGH for GLiNER PII (official HuggingFace model card verified); MEDIUM for HITL patterns (cross-validated community sources); MEDIUM for QLoRA/Unsloth specifics (multiple practitioner guides, official Unsloth docs partially unavailable)

---

## Context: What Already Exists (v1.0)

The following features are **already built and validated** in v1.0. They are listed to clarify scope — this document covers ONLY new v1.1 features and how they interact with what exists.

| Existing Feature | Module | Status |
|-----------------|--------|--------|
| Pydantic v2 schema, full record/turn/tool-call models | `schema.py` | Shipped |
| Regex PII scrubbing (7 categories, 40-char hex, org domains) | `scrubber.py` | Shipped |
| Quality scoring (5 sub-scores, gold/silver/bronze tiers) | `scorer.py` | Shipped |
| CLI (preview, submit, export, history, stats, config, rate, report, review, publish, delete, browse, download) | `cli.py` | Shipped |
| Hermes integration via assumed Protocol/event API | `hermes_integration.py` | **Needs rewrite** |
| Hardware profile auto-detection, timestamp jitter, anonymization | `collector.py`, `privacy.py` | Shipped |
| PR-based publishing, sharded JSONL, catalog.json | `publisher.py` | Shipped |
| LLM scrubber stub (raises NotImplementedError) | `scrubber_llm.py` | **Stub to implement** |

---

## Feature Landscape

### Table Stakes (v1.1 Must-Haves)

Features whose absence makes the v1.1 milestone goals unreachable. These are the minimum required to achieve "collect real Hermes session data, walk it through the pipeline, fine-tune a model."

---

#### 1. Kajiba rewritten as a real Hermes plugin

**Why expected:** The current `hermes_integration.py` was built against an assumed `agent.on(event, callback)` Protocol API. The real Hermes plugin system (v0.5.0+, confirmed in official docs) uses a completely different mechanism: a `~/.hermes/plugins/kajiba/` directory containing `plugin.yaml` + `__init__.py` with a `register(ctx)` function. Without this rewrite, Kajiba cannot collect any data from a live Hermes session.

**What the real API looks like (HIGH confidence — verified against official Hermes docs):**

- Plugin lives at `~/.hermes/plugins/kajiba/` (dropped directory, auto-discovered at startup)
- `plugin.yaml` declares: `name`, `version`, `description`, `provides_tools` (list), `provides_hooks` (list)
- `__init__.py` exports `register(ctx)` — called once at startup
- `ctx.register_hook(event_name, callback)` — subscribes to lifecycle events
- `ctx.register_tool(name, toolset, schema, handler, check_fn)` — registers tools
- Tool handlers: `def handler(args: dict, **kwargs) -> str` — always return JSON string, never raise
- If `register(ctx)` crashes, the plugin disables gracefully without crashing Hermes

**Available hook events (HIGH confidence — verified in Hermes v0.5.0 release notes):**

| Hook | Timing | Fire-and-forget? | Notes |
|------|--------|-----------------|-------|
| `on_session_start` | New session begins | Yes | Initialization |
| `on_session_end` | Session concludes | Yes | Cleanup, trigger export |
| `pre_llm_call` | Before LLM inference | No — can inject context | Returns `{"context": str}` to inject into ephemeral system prompt |
| `post_llm_call` | After LLM response | Yes | Capture assistant turn, tool_calls |
| `pre_tool_call` | Before tool execution | Yes | Pre-processing |
| `post_tool_call` | After tool completion | Yes | Capture tool name, args, result, task_id |

**Note on payload structure:** Official docs confirm the hook events and their purpose but do not publish a formal payload schema. The `post_tool_call` hook is confirmed to receive `tool_name`, `args`, `result`, `task_id`, and additional `**kwargs`. The `post_llm_call` hook carries the assistant message including content and tool_calls. Exact field names require empirical verification against live Hermes v0.6.0 — this is the first task of Phase 1.

**Complexity:** Medium. The logic in `KajibaCollector` largely stays the same; what changes is the registration wiring and the directory structure. The collector methods (`on_session_start`, `on_turn_complete`, `on_session_end`) map directly to the hook events. The main risk is hook payload shape differences from the assumed API.

**Dependency:** Everything else in v1.1 depends on this. No real data can be collected without it.

---

#### 2. Turn capture from separate pre/post_llm_call and post_tool_call streams

**Why expected:** The original `hermes_integration.py` assumed a single `turn_complete` event that bundled everything together. Hermes's real hook system fires separately: one hook for the LLM call (with the assistant response), another for each tool invocation. Kajiba must merge these into `ConversationTurn` + `ToolCall` objects that match the existing schema.

**What this requires:**
- `post_llm_call` → captures assistant role, content, tool_calls list, token counts, latency
- `post_tool_call` → captures individual tool invocations (name, args, result, status)
- `pre_llm_call` → can capture the user turn (the prompt going in)
- Session-scoped state in the collector to accumulate turns across hook fires before assembly

**Complexity:** Medium. The `KajibaCollector` in-memory state already accumulates turns in `_conversations`. The new challenge is assembling a complete `ConversationTurn` from multiple hook fires (user turn from `pre_llm_call`, assistant content from `post_llm_call`, tool results from `post_tool_call`) before committing the turn. Requires a "pending turn buffer" in the collector.

**Dependency on existing:** `ConversationTurn`, `ToolCall` schema models are already defined and validated. `KajibaCollector` already has `on_turn_complete(turn_dict)`. The main work is adapting the input assembly, not the downstream processing.

---

#### 3. WSL2 + Hermes + Ollama development environment (documented, reproducible)

**Why expected:** The pipeline validation goal requires a live Hermes Agent session collecting real data. Without a working dev environment that matches the target runtime (WSL2, GPU passthrough, Hermes v0.6.0, Ollama with Hermes 3 8B Q4), no real data can be collected and the fine-tuning experiment cannot run.

**What this requires:**
- WSL2 with NVIDIA GPU passthrough (CUDA via Windows driver stub — do NOT install Linux NVIDIA driver inside WSL2)
- Ollama installed in WSL2 (auto-detects GPU via CUDA stub)
- Hermes Agent v0.6.0 installed in WSL2
- Kajiba plugin directory symlinked or copied to `~/.hermes/plugins/kajiba/`
- Verified end-to-end: Hermes starts, Kajiba plugin loads, hooks fire, collector captures a turn

**Hardware context (from PROJECT.md):** RTX 4070 8GB VRAM. Hermes 3 8B Q4 is ~4.5GB VRAM — fits with headroom. Llama 3.2 3B Q4 for fine-tuning is ~2GB VRAM.

**Complexity:** Medium. WSL2 GPU passthrough is well-documented and well-understood in 2025 (insiderllm.com guide, official NVIDIA WSL docs). The main risk is version-specific Hermes plugin loading behavior. Requires careful documentation so the setup is reproducible.

**Not a code feature per se** — but is a prerequisite gate for all other v1.1 features. Goes in Phase 1 of the roadmap.

---

#### 4. LLM-based semantic PII scrubbing (GLiNER-based)

**Why expected:** The `scrubber_llm.py` stub has existed since the beginning. Real Hermes session data will contain personal names ("Fix the issue John reported"), company/project names ("Deploy to AcmeCorp's staging"), and geographic identifiers that regex cannot catch. Without semantic scrubbing, the pipeline cannot credibly claim it protects contributor privacy at the level needed for community trust.

**Recommended approach: GLiNER (not generative LLM prompting)**

Based on research, GLiNER is the correct choice over Ollama-based prompt-and-parse for this use case:

| Criterion | GLiNER (recommended) | Ollama prompt-and-parse |
|-----------|---------------------|------------------------|
| Speed | ~75ms per text chunk on CPU | 1-5s per text chunk |
| Accuracy (PII-specific) | Strict F1 0.87 (Nemotron-PII benchmark) | Varies by model, prompt |
| Output format | Structured spans with confidence scores | Needs JSON parsing, error-prone |
| Local deployment | Pure Python, `pip install gliner` | Requires Ollama running |
| Dependencies | `gliner` package, ~570M model | External process dependency |
| False positive control | `threshold` parameter (tune recall vs precision) | Prompt engineering |
| Entity categories | 55+ PII types including person, company, project, location | Depends on prompt |

**Specific models (HIGH confidence — HuggingFace model cards verified):**
- `nvidia/gliner-pii` — 570M params, 55+ entity categories, Strict F1 0.87, recommended
- `knowledgator/gliner-pii-small-v1.0` — lighter weight option if VRAM matters
- Usage: `model.predict_entities(text, labels, threshold=0.5)` returns `[{text, label, start, end, score}]`

**Integration approach:**
- Replace `scrubber_llm.py`'s `NotImplementedError` with GLiNER-based implementation
- `scrub_semantic(text, model_fn)` signature stays compatible; `model_fn` becomes optional (GLiNER handles inference internally)
- Auto-redact entities with `score >= high_threshold` (0.7+), flag entities with `score >= low_threshold` (0.4+) for review
- `SemanticRedaction` dataclass already defined in stub — keep it, populate from GLiNER output
- Replace span text in original string, log to `ScrubLog`

**New extra required:** `pip install kajiba[llm-scrub]` should install `gliner` (not `ollama` — GLiNER is self-contained)

**Complexity:** Medium. GLiNER's Python API is simple. The main work is: confidence threshold tuning, integrating span-based replacement into the existing string scrubbing flow, adding model download/caching on first use, and wiring into the `scrub_record()` pipeline as Layer C.

**Dependency on existing:** Runs after Layer B (regex scrubber) in `scrub_record()`. Uses existing `ScrubLog` fields. `SemanticRedaction` dataclass already defined.

---

#### 5. HITL session collection with manual review at each pipeline step

**Why expected:** The v1.1 goal is "pipeline validation" — meaning a human (the developer) explicitly reviews what the pipeline captures at each stage to verify correctness. This is not a permanent user-facing feature; it is a validation harness for the milestone. The stages are: collect → scrub → score → review → publish.

**What this requires:**
- After each Hermes session ends, `kajiba preview` shows the raw captured record before scrubbing
- After scrubbing, `kajiba preview` shows the diff (already supported) — confirm scrub quality against real session data
- After scoring, `kajiba review` (already implemented) shows tier assignment — confirm scoring accuracy
- Manual `kajiba submit` decision (already ad-hoc mode) — gate before publish
- After publish, verify the record appears in the catalog and is downloadable

**What this is NOT:** A new workflow engine. The existing CLI commands already cover most of this. The "HITL" here is the developer running the commands manually and checking the output.

**What might be missing:** A `kajiba capture --session <id>` command that shows the raw collector output (before scrubbing) for a specific session, to validate that hook capture worked correctly. This is the gap between what the existing `preview` command does (shows staged/scrubbed record) and what HITL validation needs (shows raw captured record pre-scrub for comparison).

**Complexity:** Low-Medium. Mostly CLI UX polish — a `--raw` or `--pre-scrub` flag on `preview`, or a new `kajiba inspect` command that shows the raw collector output from staging before scrubbing is applied. The collector output already goes to staging; the gap is a view command for it.

---

#### 6. End-to-end pipeline smoke test (collect → publish → download → fine-tune)

**Why expected:** The milestone goal explicitly states "end-to-end pipeline validation." This means verifying that the complete chain works: collect real session data, scrub it, score it, publish it to GitHub, download it back, convert to training format, run one QLoRA epoch on Llama 3.2 3B.

**This is not a persistent feature — it is a milestone gate.** However, the artifacts from this process feed back as:
- Documentation of the setup (reproducible by others)
- A small real-world dataset in the community repo
- Evidence that `to_sharegpt()` and `to_dpo_candidate()` produce training-ready output

**QLoRA fine-tune specifics (MEDIUM confidence — practitioner guides, not verified against official Unsloth docs directly):**
- Recommended framework: Unsloth (30-70% faster than standard HuggingFace training on same GPU)
- Model: Llama 3.2 3B Instruct Q4_K_M via Unsloth's pre-quantized weights
- Format: ShareGPT (matches Kajiba's `to_sharegpt()` output); use `standardize_sharegpt()` in Unsloth if needed
- Hardware: RTX 4070 8GB VRAM — 3B Q4 model fits with ~4GB to spare for activations/optimizer state
- Minimum dataset size: Quality dominates over quantity for QLoRA. Even 50-100 high-quality real-world sessions can produce observable behavior change (original QLoRA paper; practitioners confirm). Pipeline validation does not require a large dataset.
- Expected training time: 1-2 hours for a single epoch on 100 records on RTX 4070 (rough estimate based on similar hardware reports)

**Complexity:** High for the first run (environment setup, format debugging, training configuration). Low complexity to repeat once the pipeline is working.

**Dependency on existing:** `to_sharegpt()` and `to_dpo_candidate()` methods already exist on `KajibaRecord`. The JSONL export from `kajiba download` already produces the right format. The gap is running the training step, which is out of scope for Kajiba itself (consumers bring their own training tools) — but the milestone requires running it once to validate the output format.

---

### Differentiators (v1.1 Additions)

Features specific to v1.1 that go beyond what any other pipeline offers, even in basic form.

---

#### 1. pre_llm_call context injection (optional Kajiba intelligence)

**What it is:** The `pre_llm_call` hook is the only Hermes hook that can return a value — specifically `{"context": str}` — to inject text into the ephemeral system prompt for that turn. Kajiba can use this to inject session metadata or quality hints. For example: notifying the assistant that it is being recorded for a dataset, or injecting current session quality signals.

**Value proposition:** No other data collection plugin would use this hook for collection purposes. Most plugins use it for memory injection (like Hindsight's integration). Kajiba could optionally use it to inform the model that it is in a "dataset collection session," potentially improving response quality and coherence (the model knows its responses will be evaluated).

**Complexity:** Low. A one-line addition to the `register(ctx)` function. The implementation is trivial; the prompt engineering for the injection is the interesting part.

**Caution:** Injecting context changes the session's behavior. This must be optional (off by default) so it does not confound the collected data. A session where the model was told "you are being recorded" is different from a natural session.

---

#### 2. Plugin installable as a Python package entry point

**What it is:** Hermes supports plugin distribution via `pyproject.toml` entry points under `[project.entry-points."hermes_agent.plugins"]`. This means `pip install kajiba` (with the Hermes plugin extra) can auto-register the Kajiba plugin without the user manually copying files to `~/.hermes/plugins/`.

**Value proposition:** Reduces setup friction from "copy this directory" to "pip install kajiba[hermes]". This is the distribution model for a community plugin.

**Complexity:** Low. Requires adding an entry point to `pyproject.toml` and ensuring the plugin's `register(ctx)` is importable. The directory-drop method still works for development.

**Dependency:** Plugin directory structure must be finalized first. The entry point just points to the `register` function.

---

### Anti-Features (v1.1 Scope Constraints)

#### 1. Generative LLM prompting for PII detection

**Why avoid:** Using Ollama-prompt-and-parse for PII detection (calling `ollama.chat(model, pii_detection_prompt + text)` and parsing JSON output) is 20-50x slower than GLiNER, produces unstructured output that requires brittle JSON parsing, depends on an external process, and shows lower precision than a model trained specifically for span-tagging PII. The `model_fn: Callable` parameter in the existing `scrubber_llm.py` stub suggests this approach, but research shows GLiNER is strictly better for this use case.

**What to do instead:** GLiNER with `nvidia/gliner-pii` or `knowledgator/gliner-pii`. The `model_fn` parameter in the stub signature can either be removed or made optional with GLiNER as the default.

---

#### 2. Full fine-tuning tooling inside Kajiba

**Why avoid:** Kajiba is the pipeline only. Including training scripts creates framework-specific maintenance burden (Unsloth, Axolotl, LLaMA-Factory all evolve fast), scope explosion, and contradicts the core design. The milestone requires running one fine-tuning experiment for validation, but this is documented as a consumer-side operation, not a Kajiba feature.

**What to do instead:** Provide training-ready JSONL exports. Document the Unsloth + ShareGPT workflow in a `docs/fine-tuning-guide.md`. The experiment lives outside the Kajiba codebase.

---

#### 3. Ollama as a hard dependency for core scrubbing

**Why avoid:** If GLiNER-based scrubbing requires Ollama running, the `[llm-scrub]` extra becomes a system-level dependency (an external process) rather than a Python package dependency. This breaks the "works with pip install" guarantee and the "no external services for core" constraint.

**What to do instead:** GLiNER runs entirely in Python (`pip install gliner`). It downloads its model weights on first use to a local cache directory. No external process required.

---

#### 4. Rewriting KajibaCollector's core logic

**Why avoid:** The collector's data capture, assembly, and export logic is tested and working (356 tests passing). The v1.1 integration work is purely about the registration wiring and hook payload mapping, not about replacing the collector's internal logic.

**What to do instead:** Keep `KajibaCollector` intact. Write a new `register(ctx)` in a proper plugin directory structure that calls the existing collector methods. The collector methods may need minor signature adjustments to match actual Hermes hook payloads, but the logic stays.

---

## Feature Dependencies

```
[WSL2 + Hermes + Ollama environment setup]
    └──gates──> [Hermes plugin rewrite (register(ctx), plugin.yaml)]
                    └──enables──> [Turn capture from pre/post_llm_call + post_tool_call]
                                      └──enables──> [HITL session collection workflow]
                                                        └──enables──> [LLM semantic PII scrubbing (GLiNER)]
                                                                          └──enables──> [End-to-end pipeline validation]
                                                                                            └──enables──> [QLoRA fine-tune experiment]

[LLM semantic PII scrubbing (GLiNER)]
    └──enhances──> [existing regex scrubber Layer B]
    └──populates──> [existing ScrubLog schema]
    └──requires──> [gliner extra in pyproject.toml]

[Turn capture from separate hook streams]
    └──requires──> [existing ConversationTurn + ToolCall schema models]
    └──requires──> [KajibaCollector "pending turn buffer" for multi-hook assembly]
    └──feeds into──> [existing export_record() → scrub_record() → compute_quality_score() chain]

[Plugin installable via entry point]
    └──requires──> [plugin directory structure finalized]
    └──enhances──> [Hermes plugin rewrite]
```

### Dependency Notes

- **Environment setup gates everything:** No live Hermes session = no real data = pipeline validation impossible. This must be Phase 1.
- **Plugin rewrite gates data collection:** Without `register(ctx)`, hooks never fire. Phase 1 alongside environment.
- **Turn capture depends on payload shapes:** Hook payload field names must be confirmed empirically before the turn assembly logic can be written. This is a discovery task, not an assumption.
- **GLiNER is independent of Hermes:** The semantic scrubber can be developed and tested with synthetic text or existing staged records. It does not require live Hermes sessions.
- **HITL workflow depends on working plugin:** Manual review only makes sense once real session data is flowing through the pipeline.
- **Fine-tuning experiment is the last step:** Requires real data collected, scrubbed, scored, published, and downloaded first.

---

## MVP Definition (v1.1)

### Phase 1: Environment + Plugin Foundation (Must complete first)

- [ ] WSL2 + Hermes v0.6.0 + Ollama environment — working and documented
- [ ] Kajiba plugin directory (`~/.hermes/plugins/kajiba/`) with `plugin.yaml` + `register(ctx)` — hooks registered
- [ ] Empirically confirm hook payload field names for `post_llm_call` and `post_tool_call` against live Hermes
- [ ] Verify at least one turn captured and stored in staging

### Phase 2: Turn Capture + Semantic Scrubbing (Core new features)

- [ ] Turn assembly from separate hook streams — `ConversationTurn` objects assembled correctly
- [ ] GLiNER-based `scrubber_llm.py` implementation — `scrub_semantic()` working with `nvidia/gliner-pii`
- [ ] `gliner` dependency added to `pyproject.toml` under `[llm-scrub]` extra
- [ ] Semantic scrubbing integrated into `scrub_record()` as Layer C after regex Layer B

### Phase 3: HITL Validation + Pipeline Gate

- [ ] `kajiba preview --raw` or equivalent — shows pre-scrub captured record for verification
- [ ] Manual walkthrough: collect → preview → scrub → score → review → submit
- [ ] Verify `to_sharegpt()` output matches expected training format

### Phase 4: Publish + Fine-Tune Experiment (Milestone gate)

- [ ] Collected records published to GitHub dataset repo
- [ ] Records downloadable via `kajiba download`
- [ ] QLoRA fine-tune experiment run with Unsloth + Llama 3.2 3B on downloaded data
- [ ] Training completes without error — any behavioral change is a bonus, not the goal

### Add After Validation (v1.1.x or v2)

- [ ] Plugin installable via `pip install kajiba[hermes]` entry point
- [ ] `pre_llm_call` context injection (optional, off by default)
- [ ] HuggingFace dataset upload (`huggingface_hub` extra) — already in PROJECT.md as deferred

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Phase | Priority |
|---------|------------|---------------------|-------|----------|
| WSL2 + Hermes + Ollama environment | CRITICAL (gate) | Medium | 1 | P0 |
| Hermes plugin rewrite (register(ctx), plugin.yaml) | CRITICAL (gate) | Medium | 1 | P0 |
| Hook payload shape discovery | CRITICAL (gate) | Low (empirical) | 1 | P0 |
| Turn capture from pre/post_llm_call + post_tool_call | HIGH | Medium | 2 | P0 |
| GLiNER semantic PII scrubbing | HIGH | Medium | 2 | P0 |
| HITL collection workflow (preview --raw) | MEDIUM | Low | 3 | P1 |
| End-to-end pipeline smoke test | HIGH (milestone gate) | Low (given others) | 3-4 | P1 |
| QLoRA fine-tune experiment | HIGH (milestone gate) | Low (consumer-side) | 4 | P1 |
| Plugin entry point distribution | MEDIUM | Low | post-v1.1 | P2 |
| pre_llm_call context injection | LOW | Low | post-v1.1 | P3 |

**Priority key:** P0 = milestone blocked without it; P1 = milestone incomplete without it; P2 = quality improvement; P3 = future enhancement

---

## Competitor Feature Analysis

### Other Hermes Plugins (42-evey/hermes-plugins)

The 42-evey/hermes-plugins repo (23 community plugins) shows what real Hermes plugin development looks like. Key observations:
- `evey-telemetry` and `evey-session-guard` are the closest analogs to Kajiba — they observe session data via hooks
- Plugins use shared utilities (`evey_utils.py`) for retry logic and HTTP helpers
- The pattern of using `post_llm_call` to capture user/assistant exchanges is established (Hindsight integration uses it this way)
- **Lesson:** Kajiba's plugin implementation is following established patterns, not pioneering unknown territory

### Hindsight Memory Integration

The Hindsight integration uses `post_llm_call` to "auto-retain the user/assistant exchange." This is exactly what Kajiba needs for turn capture. The difference is Kajiba stores locally and applies PII scrubbing first.

- **Lesson:** The `post_llm_call` capture pattern is confirmed working in production. Kajiba's assembly logic (merging with tool calls from `post_tool_call`) is more complex but the foundation is proven.

### Microsoft Presidio

Presidio is a full PII detection + anonymization framework. It now ships a `GLiNERRecognizer` that uses GLiNER internally. The full Presidio framework adds orchestration, service architecture, and DevOps overhead that Kajiba does not need.

- **Lesson:** Use GLiNER directly, not Presidio. Presidio is overkill for Kajiba's single-model use case. The `gliner` package is a direct dependency; no service orchestration needed.

---

## Sources

**Hermes Agent Plugin API:**
- [Build a Hermes Plugin — official Hermes Agent docs](https://hermes-agent.nousresearch.com/docs/guides/build-a-hermes-plugin/) — HIGH confidence. Official documentation confirming plugin.yaml schema, register(ctx) API, hook events.
- [Hermes Agent v0.5.0 Release Notes](https://github.com/NousResearch/hermes-agent/blob/main/RELEASE_v0.5.0.md) — HIGH confidence. Confirms pre_llm_call, post_llm_call, on_session_start, on_session_end hooks activated in v0.5.0.
- [42-evey/hermes-plugins community plugins](https://github.com/42-evey/hermes-plugins) — MEDIUM confidence. Real-world plugin examples confirming plugin directory structure and hook usage patterns.
- [Hindsight Hermes integration](https://hindsight.vectorize.io/sdks/integrations/hermes) — MEDIUM confidence. Confirms post_llm_call used for user/assistant exchange capture.

**GLiNER PII Scrubbing:**
- [nvidia/gliner-PII — HuggingFace model card](https://huggingface.co/nvidia/gliner-PII) — HIGH confidence. Official model card confirming 570M params, 55+ entity types, threshold=0.3/0.5, Python usage example.
- [knowledgator/gliner-pii-base-v1.0 — HuggingFace](https://huggingface.co/knowledgator/gliner-pii-base-v1.0) — HIGH confidence. Alternative smaller model confirmed.
- [Using GLiNER as external PII model — Microsoft Presidio docs](https://microsoft.github.io/presidio/samples/python/gliner/) — HIGH confidence. Official Presidio documentation confirming GLiNER integration pattern.
- [The Next Generation of Privacy: Docling and GLiNER — DEV Community](https://dev.to/aairom/the-next-generation-of-privacy-using-docling-gliners-advanced-ner-to-masterfully-detect-and-75p) — MEDIUM confidence. Practitioner guide confirming GLiNER local deployment approach.

**QLoRA Fine-Tuning:**
- [QLoRA: Efficient Finetuning of Quantized LLMs (original paper)](https://arxiv.org/abs/2305.14314) — HIGH confidence. Dataset quality dominates quantity; small high-quality datasets produce state-of-the-art results.
- [Fine-tuning Llama 3.2 3B — Analytics Vidhya](https://www.analyticsvidhya.com/blog/2024/12/fine-tuning-llama-3-2-3b-for-rag/) — MEDIUM confidence. Practical guide for Llama 3.2 3B fine-tuning.
- [Fine-tune Llama 3.1 Ultra-Efficiently with Unsloth — HuggingFace blog](https://huggingface.co/blog/mlabonne/sft-llama3) — MEDIUM confidence. ShareGPT + Unsloth workflow documented.

**WSL2 + GPU Setup:**
- [WSL2 + Ollama on Windows: Complete Setup Guide — InsiderLLM](https://insiderllm.com/guides/wsl2-ollama-windows-setup-guide/) — MEDIUM confidence. Confirms GPU passthrough approach, critical warning about not installing Linux NVIDIA driver inside WSL2.
- [CUDA on WSL User Guide — NVIDIA official docs](https://docs.nvidia.com/cuda/wsl-user-guide/index.html) — HIGH confidence. Official NVIDIA guidance on WSL2 CUDA.

---
*Feature research for: Kajiba v1.1 Hermes Pipeline Validation milestone*
*Researched: 2026-04-02*
*Supersedes: previous FEATURES.md which covered v1.0 features. The v1.0 feature landscape is preserved below in the archived section.*

---

## Archive: v1.0 Feature Landscape (Reference Only)

The following content was the original FEATURES.md covering the v1.0 dataset pipeline features. Preserved for reference when working on phases that build on or modify these existing features.

> See v1.0 features: PII preview/diff, consent enforcement, metadata anonymization, opt-out/deletion, dataset card, quality tier filtering, model metadata filtering, license clarity, deduplication, transparent scrubbing log, runtime context as dataset dimension, two-pass PII scrubbing, contribution modes, user annotation refinement, scrub strictness levels, dataset catalog CLI, contribution statistics, model-agnostic adapter protocol, and anti-features (fine-tuning tooling, hosted API, model evaluation, automatic submission without review, personal identity tracking, real-time streaming, synthetic data generation).
> The feature dependency graph, MVP definition, and competitor analysis for v1.0 features remain valid for understanding the existing system.
