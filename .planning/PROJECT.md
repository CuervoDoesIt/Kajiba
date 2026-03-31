# Kajiba

## What This Is

Kajiba is an open-source, model-agnostic data pipeline that lets developers contribute their AI-assisted coding session data — prompts, responses, tool calls, model configurations, and hardware profiles — to a community dataset. Other developers browse and download subsets of this dataset to fine-tune their local LLMs, filtered by model type, quality tier, or runtime context. The pipeline handles collection, PII scrubbing, quality scoring, and publishing.

## Core Value

Real-world AI session data, tagged with full runtime context (model identity, config, hardware), flowing into a community dataset that accelerates local model fine-tuning for everyone.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ Pydantic v2 schema with validation for records, trajectories, turns, tool calls, model metadata, hardware profiles — existing
- ✓ Regex-based PII scrubbing across 7 pattern categories (paths, keys, network, emails, phone, crypto, connection strings) — existing
- ✓ Quality scoring with 5 weighted sub-scores (coherence, tool validity, outcome quality, info density, metadata completeness) and tier assignment (gold/silver/bronze) — existing
- ✓ CLI with preview, submit, export, history, stats, config commands via Click + Rich — existing
- ✓ Hermes Agent integration via event hooks (session lifecycle, turn capture, rate/report) — existing
- ✓ Hardware profile auto-detection (GPU via nvidia-smi, CPU, RAM, OS) — existing
- ✓ Content-addressable record IDs and dedup via SHA-256 submission hash — existing
- ✓ Local-first processing with no network calls required for core pipeline — existing
- ✓ Fault-tolerant collector that never disrupts the host agent — existing

### Active

<!-- Current scope. Building toward these. -->

- [ ] Model-agnostic data collection — decouple from Hermes-specific paths and support any LLM-powered tool as a data source
- [ ] Full runtime context in data packages — model name, version, parameter count, quantization, hyperparams, LoRA config, system prompts, tool definitions, hardware specs, inference settings, context window size
- [ ] LLM-based semantic PII scrubbing — catch personal names, company names, project names that regex misses
- [ ] Metadata anonymization — GPU generalization, timestamp jitter, RAM/VRAM rounding, OS version stripping
- [ ] Consent level enforcement — strip fields based on user's chosen consent level (anonymous, trajectory_only, metadata_only, full)
- [ ] Configurable contribution modes — ad-hoc with user review/approval before submit, or continuous with pre-set parameters
- [ ] GitHub repository as dataset destination — structured repo that contributors push scrubbed records to
- [ ] Browsable dataset catalog — structured organization so consumers can browse by model, quality tier, or runtime context and download subsets
- [ ] User annotation refinement — auto-score first, then let users tag/adjust quality signals (pain points, what worked)
- [ ] Complete regex scrubber coverage — add generic 40-char hex token pattern and org domain flagging per spec

### Out of Scope

- Fine-tuning tooling — Kajiba is the pipeline only; consumers bring their own training frameworks
- Hosted service / API — everything runs locally on the contributor's machine
- HuggingFace integration — deferred to a future milestone after the pipeline is validated on GitHub
- Real-time streaming — batch processing, not live telemetry
- Model evaluation / benchmarking — out of scope entirely

## Context

- **Existing codebase**: ~8 Python modules implementing the core pipeline (schema, collector, scrubber, scorer, CLI, Hermes integration). See `.planning/codebase/` for full analysis.
- **Current state**: Early MVP (v0.1.0). End-to-end flow partially works but several spec features are stubs or missing (LLM scrubber, metadata anonymization, consent enforcement, HuggingFace upload).
- **Key gap**: Currently tightly coupled to Hermes Agent. The vision is model-agnostic — any AI-assisted coding tool should be able to contribute data.
- **Privacy is paramount**: Contributors are sharing real session data. Maximum scrubbing by default. The pipeline must earn trust before community adoption.
- **Phased rollout**: GitHub repo first to validate the pipeline, then transition to HuggingFace for broader community access.

## Constraints

- **Tech stack**: Python 3.11+, Pydantic v2, Click, Rich — already established, no reason to change
- **Privacy**: Maximum scrubbing by default — err on the side of over-redacting
- **Local-first**: All processing happens on the contributor's machine before any data leaves
- **Open source**: Apache 2.0 license, community-friendly contribution flow
- **No external services for core**: Core pipeline must work without API keys or network access

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| GitHub repo as initial dataset destination | Validate pipeline before attempting community-scale distribution via HuggingFace | — Pending |
| Model-agnostic (not Hermes-specific) | Maximize community value — any LLM tool's data is useful | — Pending |
| Maximum PII scrubbing by default | Trust must be earned before community adoption; over-redact rather than leak | — Pending |
| Auto-score + user refinement for quality signals | Automated scoring provides baseline; user annotations capture what heuristics miss | — Pending |
| Configurable contribution modes (ad-hoc vs continuous) | Different users have different comfort levels and workflows | — Pending |
| Pipeline only, no fine-tuning tooling | Sharp scope boundary — do one thing well | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-30 after initialization*
