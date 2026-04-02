# Kajiba

## What This Is

Kajiba is an open-source, model-agnostic data pipeline that lets developers contribute their AI-assisted coding session data — prompts, responses, tool calls, model configurations, and hardware profiles — to a community dataset. Other developers browse and download subsets of this dataset to fine-tune their local LLMs, filtered by model type, quality tier, or runtime context. The pipeline handles collection, PII scrubbing, quality scoring, publishing, and consumer access.

## Core Value

Real-world AI session data, tagged with full runtime context (model identity, config, hardware), flowing into a community dataset that accelerates local model fine-tuning for everyone.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ Pydantic v2 schema with validation for records, trajectories, turns, tool calls, model metadata, hardware profiles — existing
- ✓ Regex-based PII scrubbing across 7 pattern categories (paths, keys, network, emails, phone, crypto, connection strings) — existing
- ✓ Quality scoring with 5 weighted sub-scores (coherence, tool validity, outcome quality, info density, metadata completeness) and tier assignment (gold/silver/bronze) — existing
- ✓ CLI with preview, submit, export, history, stats, config, rate, report, review, publish, delete, browse, download commands via Click + Rich — v1.0
- ✓ Hermes Agent integration via event hooks (session lifecycle, turn capture, rate/report) — existing
- ✓ Hardware profile auto-detection (GPU via nvidia-smi, CPU, RAM, OS) — existing
- ✓ Content-addressable record IDs and dedup via SHA-256 submission hash — existing
- ✓ Local-first processing with no network calls required for core pipeline — existing
- ✓ Fault-tolerant collector that never disrupts the host agent — existing
- ✓ Consent level enforcement — fields stripped based on user's chosen consent level (anonymous, trajectory_only, metadata_only, full) — v1.0
- ✓ Metadata anonymization — GPU generalization to family tier, timestamp jitter ±30min, RAM/VRAM power-of-2 rounding, OS version stripping — v1.0
- ✓ Complete regex scrubber coverage — 40-char hex token scrubbing with context keywords, org domain flagging with safe-domain allowlist, IP false positive fix — v1.0
- ✓ Quality score persistence — QualityMetadata model with tier, composite score, all 5 sub-scores stored in record at submit time — v1.0
- ✓ Redaction transparency — preview shows summary table by default, --detail flag for inline-highlighted scrubbed text — v1.0
- ✓ User annotation refinement — `kajiba rate` and `kajiba report` commands with interactive picker — v1.0
- ✓ Dataset publishing — `kajiba publish` with fork+PR workflow, sharded JSONL, catalog.json, README.md — v1.0
- ✓ Deletion mechanism — `kajiba delete <record_id>` via PR with soft delete index — v1.0
- ✓ Configurable contribution modes — ad-hoc review gate and continuous auto-submit with quality threshold — v1.0
- ✓ Browsable dataset catalog — `kajiba browse` with model drill-down and `kajiba download` with filtered subsets — v1.0

### Active

<!-- Next milestone scope. -->

- [ ] Model-agnostic data collection — decouple from Hermes-specific paths and support any LLM-powered tool as a data source
- [ ] Full runtime context in data packages — model name, version, parameter count, quantization, hyperparams, LoRA config, system prompts, tool definitions, hardware specs, inference settings, context window size
- [ ] LLM-based semantic PII scrubbing — catch personal names, company names, project names that regex misses

### Out of Scope

- Fine-tuning tooling — Kajiba is the pipeline only; consumers bring their own training frameworks
- Hosted service / API — everything runs locally on the contributor's machine
- HuggingFace integration — deferred to a future milestone after the pipeline is validated on GitHub
- Real-time streaming — batch processing, not live telemetry
- Model evaluation / benchmarking — out of scope entirely

## Context

- **Shipped**: v1.0 MVP on 2026-04-02
- **Codebase**: 10 Python modules, 10,478 LOC, 356 tests passing
- **Tech stack**: Python 3.11+, Pydantic v2, Click, Rich, pytest
- **CLI commands**: preview, submit, export, history, stats, config (set/get/show), rate, report, review, publish, delete, browse, download — 13 commands total
- **Key gap**: Currently tightly coupled to Hermes Agent. The vision is model-agnostic — any AI-assisted coding tool should be able to contribute data.
- **Privacy**: Maximum scrubbing by default. Full pipeline: regex scrub → hardware anonymize → timestamp jitter → consent enforce. Org domains flagged for review.
- **Remaining stubs**: LLM scrubber (`scrubber_llm.py`), HuggingFace upload (`huggingface_hub` extra)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| GitHub repo as initial dataset destination | Validate pipeline before attempting community-scale distribution via HuggingFace | ✓ Good — `kajiba publish` and `kajiba browse/download` work against GitHub repos |
| Maximum PII scrubbing by default | Trust must be earned before community adoption; over-redact rather than leak | ✓ Good — 7 regex categories + org domain flagging + consent enforcement |
| Auto-score + user refinement for quality signals | Automated scoring provides baseline; user annotations capture what heuristics miss | ✓ Good — QualityMetadata stored alongside OutcomeSignals and PainPoints |
| Configurable contribution modes (ad-hoc vs continuous) | Different users have different comfort levels and workflows | ✓ Good — runtime config switching with quality threshold |
| Pipeline only, no fine-tuning tooling | Sharp scope boundary — do one thing well | ✓ Good — clear scope, consumers use their own training tools |
| PR-based publishing (not direct push) | Review layer prevents data poisoning, maintains contributor trust | ✓ Good — fork+branch+PR workflow with consent re-verification |
| Consent re-verification at publish time | Belt-and-suspenders: even if submit missed it, publish catches it | ✓ Good — confirmed by Nyquist validation tests |
| Privacy pipeline order: scrub → anonymize → jitter → consent | Each step depends on prior step's output being complete | ✓ Good — consistent across all 4 export paths |

## Constraints

- **Tech stack**: Python 3.11+, Pydantic v2, Click, Rich — established, no reason to change
- **Privacy**: Maximum scrubbing by default — err on the side of over-redacting
- **Local-first**: All processing happens on the contributor's machine before any data leaves
- **Open source**: Apache 2.0 license, community-friendly contribution flow
- **No external services for core**: Core pipeline must work without API keys or network access

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone:**
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-02 after v1.0 milestone completion*
