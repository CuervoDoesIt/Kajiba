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

## v1.2 Requirements

Requirements for the Experiment Logging (Dual-Use) milestone. Runs **in parallel** with v1.1 — phases numbered 10+. Most are v1.1-independent; live capture (ECAP) depends on v1.1 Phase 6–7. See `.planning/seeds/v1.2-experiment-logging.md`.

### Experiment Schema

- [x] **ESCH-01**: Records carry a `record_kind` discriminator (`coding_session` | `model_experiment`) defaulting to `coding_session` when absent, so existing records stay valid
- [x] **ESCH-02**: A shared base model holds fields common to both kinds (model metadata, hardware profile, scrub log, record/submission IDs); `KajibaRecord` and `ExperimentRecord` both extend it
- [x] **ESCH-03**: An `ExperimentRecord` captures experiment metadata (id, type, local model, optional reviewer model, task category/description, timestamps) and outcome (local output, reviewer critique, eval score, drift flag, lessons_learned, recommended action)
- [x] **ESCH-04**: Existing staged/outbox `KajibaRecord` JSON loads unchanged after the refactor, with previously computed record/submission IDs unaffected

### Experiment Logging & Storage

- [x] **ELOG-01**: User can deliberately record an eval run via a `kajiba experiment` CLI command group, without a live Hermes session
- [x] **ELOG-02**: A programmatic logging entry point lets an external script (the practice project) write `ExperimentRecord`s directly
- [x] **ELOG-03**: Experiment records persist in a private local namespace, separate from coding-session staging/outbox, and are excluded from any community publish path

### Experiment Evaluation & Privacy

- [x] **EEVAL-01**: An eval-specific scorer produces quality signals suited to model-output evaluation, independent of the coding-trajectory scorer
- [x] **EEVAL-02**: Scrubbing on experiment records retains model-identity and hardware fields needed for analysis while still redacting personal/PII data

### Experiment Review & Drift

- [x] **EREV-01**: User (or a reviewer model such as Grok) can attach a critique to an existing experiment record via `kajiba experiment review`
- [x] **EREV-02**: User can capture `lessons_learned` on a record in a queryable form (structured categories and/or free text)
- [x] **EREV-03**: Quality drift across repeated runs of the same model+task is computed and flagged on the record

### Experiment Live Capture

- [ ] **ECAP-01**: An eval run performed inside a live Hermes session is captured into an `ExperimentRecord` through the shared plugin hooks *(depends on v1.1 Phase 6–7)*

### Experiment Export & Integration

- [ ] **EEXP-01**: User can export experiment records in an analysis-oriented format (comparison/routing/drift), distinct from the community fine-tuning export
- [ ] **EEXP-02**: The Nemotron/Qwen/Gemma practice-project workflow writes its eval runs directly into Kajiba experiment records end-to-end

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
| Fine-tuning tooling in Kajiba | Pipeline only -- consumers bring their own training frameworks |
| Presidio/spaCy for PII | GLiNER is faster, more accurate, self-contained -- Presidio is overkill |
| Ollama as core dependency | GLiNER handles PII locally; Ollama only for inference/metadata capture |
| Real-time streaming | Batch processing, not live telemetry |
| Generative LLM prompting for PII | 20-50x slower and lower precision than GLiNER span-tagging |
| ~~Model evaluation/benchmarking~~ | **Reversed 2026-06-03 → moved to v1.2 "Experiment Logging" (dual-use).** Was "out of scope entirely"; now a first-class second purpose. See `.planning/seeds/v1.2-experiment-logging.md`. |
| Hosted service / API | Everything runs locally on contributor's machine |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PLUG-01 | Phase 6 | Pending |
| PLUG-02 | Phase 6 | Pending |
| PLUG-03 | Phase 6 | Pending |
| PLUG-04 | Phase 8 | Pending |
| PLUG-05 | Phase 8 | Pending |
| CAPT-01 | Phase 6 | Pending |
| CAPT-02 | Phase 7 | Pending |
| CAPT-03 | Phase 7 | Pending |
| CAPT-04 | Phase 7 | Pending |
| PRIV-01 | Phase 7 | Pending |
| PRIV-02 | Phase 7 | Pending |
| PRIV-03 | Phase 7 | Pending |
| PRIV-04 | Phase 7 | Pending |
| ENV-01 | Phase 6 | Pending |
| ENV-02 | Phase 6 | Pending |
| ENV-03 | Phase 6 | Pending |
| VAL-01 | Phase 8 | Pending |
| VAL-02 | Phase 8 | Pending |
| VAL-03 | Phase 8 | Pending |
| VAL-04 | Phase 9 | Pending |
| ESCH-01 | Phase 10 | Complete (10-02) |
| ESCH-02 | Phase 10 | Complete (10-02) |
| ESCH-03 | Phase 10 | Complete (10-02) |
| ESCH-04 | Phase 10 | Complete (10-03 — golden tripwire green for all 5 fixtures) |
| ELOG-01 | Phase 11 | Complete (11-02) |
| ELOG-02 | Phase 11 | Complete (11-01) |
| ELOG-03 | Phase 11 | Complete |
| EEVAL-01 | Phase 12 | Complete |
| EEVAL-02 | Phase 12 | Complete |
| EREV-01 | Phase 13 | Complete |
| EREV-02 | Phase 13 | Complete |
| EREV-03 | Phase 13 | Complete |
| ECAP-01 | Phase 14 | Pending |
| EEXP-01 | Phase 15 | Pending |
| EEXP-02 | Phase 15 | Pending |

**Coverage:**

- v1.1 requirements: 20 total — mapped to phases: 20, unmapped: 0
- v1.2 requirements: 15 total — mapped to phases: 15, unmapped: 0

---
*Requirements defined: 2026-04-02*
*Last updated: 2026-06-03 — added v1.2 Experiment Logging requirements (parallel milestone)*
