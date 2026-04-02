# Requirements: Kajiba

**Defined:** 2026-04-02
**Core Value:** Real-world AI session data, tagged with full runtime context, flowing into a community dataset that accelerates local model fine-tuning for everyone.

## v1.1 Requirements

Requirements for Hermes Pipeline Validation milestone. Each maps to roadmap phases.

### Plugin Integration

- [ ] **PLUG-01**: Kajiba plugin scaffold created at `~/.hermes/plugins/kajiba/` with `plugin.yaml` manifest and `register(ctx)` entry point
- [ ] **PLUG-02**: Plugin registers hooks for `on_session_start`, `post_llm_call`, `post_tool_call`, and `on_session_end` via `ctx.register_hook()`
- [ ] **PLUG-03**: All `~/.hermes` paths replaced with HERMES_HOME-aware resolution for v0.6.0 profile isolation
- [ ] **PLUG-04**: Plugin installable via `pip install kajiba[hermes]` entry point (auto-registers without manual file copy)
- [ ] **PLUG-05**: Optional `pre_llm_call` context injection into ephemeral system prompt (off by default, configurable)

### Data Capture

- [ ] **CAPT-01**: Logging-only plugin stub deployed to empirically confirm hook kwargs against live Hermes v0.6.0
- [ ] **CAPT-02**: User turns captured from `pre_llm_call` and assistant responses from `post_llm_call`, assembled into `ConversationTurn` objects
- [ ] **CAPT-03**: Tool calls captured from `post_tool_call` events and attached to the correct assistant turn via pending turn buffer
- [ ] **CAPT-04**: Full model metadata captured via `ollama.show()` (parameter count, quantization, family, context length) and stored in `ModelMetadata`

### Privacy

- [ ] **PRIV-01**: `scrubber_llm.py` stub replaced with GLiNER-based semantic PII detection using `nvidia/gliner-pii` model
- [ ] **PRIV-02**: Auto-redact entities with confidence >= 0.7, flag entities with confidence >= 0.4 for HITL review, ignore below 0.4
- [ ] **PRIV-03**: GLiNER tested against code content fixtures to calibrate false positive rates on programming identifiers
- [ ] **PRIV-04**: `gliner` added to `pyproject.toml` as `pip install kajiba[llm-scrub]` optional extra

### Environment

- [ ] **ENV-01**: Documented WSL2 + NVIDIA GPU passthrough + Hermes Agent v0.6.0 + Ollama setup guide with verification steps
- [ ] **ENV-02**: Documented Ollama configuration (num_ctx override, Hermes 3 8B model pull, Hermes custom endpoint setup)
- [ ] **ENV-03**: Dev symlink script/instructions linking Kajiba plugin directory into `~/.hermes/plugins/` for development workflow

### Validation

- [ ] **VAL-01**: `kajiba preview --raw` or `kajiba inspect` shows pre-scrub captured record for comparison
- [ ] **VAL-02**: `pipeline_stage` field on staging records (captured/scrubbed/reviewed/scored/approved) enabling resumable HITL review
- [ ] **VAL-03**: Manual end-to-end walkthrough completed: collect real Hermes session → scrub → score → review → publish → download
- [ ] **VAL-04**: QLoRA fine-tune of Llama 3.2 3B on collected Kajiba data completed, with documented training guide (`docs/fine-tuning-guide.md`)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Model-Agnostic Collection

- **AGNO-01**: Decouple data collection from Hermes-specific paths to support any LLM-powered tool as a data source
- **AGNO-02**: Generic adapter protocol for non-Hermes agents (VS Code extensions, other CLI tools)

### Distribution

- **DIST-01**: HuggingFace dataset upload via `huggingface_hub` extra
- **DIST-02**: Dataset card generation for HuggingFace compliance

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Fine-tuning tooling in Kajiba | Pipeline only — consumers bring their own training frameworks |
| Presidio/spaCy for PII | GLiNER is faster, more accurate, self-contained — Presidio is overkill |
| Ollama as core dependency | GLiNER handles PII locally; Ollama only for inference/metadata capture |
| Real-time streaming | Batch processing, not live telemetry |
| Generative LLM prompting for PII | 20-50x slower and lower precision than GLiNER span-tagging |
| Model evaluation/benchmarking | Out of scope entirely |
| Hosted service / API | Everything runs locally on contributor's machine |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PLUG-01 | — | Pending |
| PLUG-02 | — | Pending |
| PLUG-03 | — | Pending |
| PLUG-04 | — | Pending |
| PLUG-05 | — | Pending |
| CAPT-01 | — | Pending |
| CAPT-02 | — | Pending |
| CAPT-03 | — | Pending |
| CAPT-04 | — | Pending |
| PRIV-01 | — | Pending |
| PRIV-02 | — | Pending |
| PRIV-03 | — | Pending |
| PRIV-04 | — | Pending |
| ENV-01 | — | Pending |
| ENV-02 | — | Pending |
| ENV-03 | — | Pending |
| VAL-01 | — | Pending |
| VAL-02 | — | Pending |
| VAL-03 | — | Pending |
| VAL-04 | — | Pending |

**Coverage:**
- v1.1 requirements: 20 total
- Mapped to phases: 0
- Unmapped: 20

---
*Requirements defined: 2026-04-02*
*Last updated: 2026-04-02 after initial definition*
