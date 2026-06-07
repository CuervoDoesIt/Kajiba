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
- ✓ `ExperimentRecord` type on a shared `RecordBase` + `record_kind` discriminator and `load_record()` factory, back-compatible with existing records (byte-identical record/submission IDs, SCHEMA_VERSION 0.2.0) — v1.2 Phase 10
- ✓ `kajiba experiment` CLI (`log` --from/flags/interactive + `list`) and programmatic `log_experiment`/`build_experiment_record` entry points writing to a private `~/.hermes/kajiba/experiments/` store, structurally separated from staging/outbox and actively excluded from publish/submit (D-13 write guard + raw-dict `record_kind` publish skip) — v1.2 Phase 11 (ELOG-01/02/03)
- ✓ Eval-specific completeness/confidence scorer (`eval_scorer.compute_eval_confidence`, `complete`/`partial`/`thin` bands distinct from gold/silver/bronze, experiment-only guard) + experiment-aware PII scrub (`experiment_scrub.scrub_experiment` — five free-text surfaces redacted via the shared engine while model identity & full hardware stay byte-identical) + `kajiba experiment score`/`scrub` CLI and Confidence column — v1.2 Phase 12 (EEVAL-01/02)
- ✓ Reviewer critique attachment, queryable lessons, and quality-drift detection — `kajiba experiment review` (human or reviewer-model, re-review replaces, 3 input modes), `kajiba experiment lessons` (category+text via `_parse_lesson`, `--category` filter, cross-record query), and `kajiba experiment drift` (`experiment_drift.compute_drift` nearest-in-group-neighbor baseline + idempotent `drift_flag` persist/clear) — all writes funnel through `update_experiment` in-place overwrite (CR-01 closed, EQUAL store guard, identity byte-stable); Phase 10 schema untouched — v1.2 Phase 13 (EREV-01/02/03)
- ✓ Live experiment capture via shared Hermes hooks — `KAJIBA_EXPERIMENT*` env opt-in read at `on_session_start`, `_build_experiment_record` mapping buffered turns through the same `build_experiment_record` constructor (structural parity by construction), and a Design-B self-cleaning `_finalize_experiment` that emits exactly ONE `exp_*.json` per opted-in session despite turn-scoped `on_session_end` firings; an experiment branch returns before the contribution-mode read so staging/outbox are never touched (D-08); schema frozen — v1.2 Phase 14 (ECAP-01). *Automated coverage complete (6/6 ECAP-01 tests); end-to-end live-Hermes SC#1 proof tracked as a pending UAT (`14-HUMAN-UAT.md`).*

### Active

<!-- Current milestone: v1.1 Hermes Pipeline Validation -->

- [ ] Kajiba rewritten as a real Hermes plugin matching the actual plugin API (register(ctx), hook events, plugin.yaml manifest)
- [ ] Turn capture from Hermes's separate event streams (pre/post_llm_call, post_tool_call) into KajibaCollector
- [ ] LLM-based semantic PII scrubbing — catch personal names, company names, project names that regex misses
- [ ] HITL session collection workflow with manual review at each pipeline step
- [ ] End-to-end pipeline validation: collect → scrub → score → publish → download → fine-tune a local 3B model

<!-- Parallel milestone: v1.2 Experiment Logging (Dual-Use) -->

- [x] `kajiba experiment` CLI + programmatic deliberate logging into a private local store (no community publish) — validated in Phase 11
- [x] Eval-specific scorer and experiment-aware scrub tuning (preserve model/hardware fields) — validated in Phase 12 (EEVAL-01/02)
- [x] Reviewer-model critique attachment, queryable `lessons_learned`, and quality-drift detection — validated in Phase 13 (EREV-01/02/03)
- [x] Live experiment capture via shared Hermes hooks (depends on v1.1 Phase 6–7) — validated in Phase 14 (ECAP-01); live-Hermes SC#1 proof pending as UAT
- [ ] Analysis-oriented export + Nemotron/Qwen/Gemma practice-project integration

### Out of Scope

- Fine-tuning tooling — Kajiba is the pipeline only; consumers bring their own training frameworks
- Hosted service / API — everything runs locally on the contributor's machine
- HuggingFace integration — deferred to a future milestone after the pipeline is validated on GitHub
- Real-time streaming — batch processing, not live telemetry
- ~~Model evaluation / benchmarking~~ — **reversed 2026-06-03**; now in scope as the parallel v1.2 Experiment Logging (dual-use) milestone

## Current Milestone: v1.1 Hermes Pipeline Validation

**Goal:** Prove the end-to-end pipeline works with the real Hermes Agent — collect actual session data, walk it through scrub/score/publish, and fine-tune a local model with the result.

**Target features:**
- WSL2 + Hermes Agent + Ollama environment setup (documented, reproducible)
- Kajiba rewritten as a real Hermes plugin (matching the actual plugin API)
- Turn capture from Hermes's separate event streams (pre/post_llm_call, post_tool_call)
- HITL session collection with manual review at each pipeline step
- LLM-based semantic PII scrubbing (using real session data to test against)
- QLoRA fine-tune experiment with Llama 3.2 3B on collected Kajiba data

## Parallel Milestone: v1.2 Experiment Logging (Dual-Use)

**Runs alongside v1.1 — does not replace it.** v1.1 remains the active execution milestone; v1.2 phases (10–15) are appended to the same roadmap and execute by dependency, not strict order.

**Goal:** Add a first-class, private experiment/eval-logging capability — capture local-model outputs, reviewer-model critiques, eval scoring, and quality drift — without disturbing the coding-session pipeline.

**Target features:**
- Separate `ExperimentRecord` on a base extracted from `KajibaRecord` + `record_kind` discriminator
- `kajiba experiment` CLI + programmatic logging → private local store (no community publish path)
- Eval-specific scorer + experiment-aware scrub tuning
- Reviewer critique attachment, `lessons_learned`, drift detection
- Live experiment capture via shared Hermes hooks (depends on v1.1 Phase 6–7)
- Analysis export + Nemotron/Qwen/Gemma practice-project integration

**Architecture stance:** *shared core, divergent tail* — reuse the schema base + scrub primitives; branch into an eval scorer, private store, and analysis export; skip community publish/HuggingFace entirely. See `.planning/seeds/v1.2-experiment-logging.md` and `.planning/notes/dual-use-direction-decisions.md`.

## Context

- **Shipped**: v1.0 MVP on 2026-04-02
- **Codebase**: 10 Python modules, 10,478 LOC, 356 tests passing
- **Tech stack**: Python 3.11+, Pydantic v2, Click, Rich, pytest
- **CLI commands**: preview, submit, export, history, stats, config (set/get/show), rate, report, review, publish, delete, browse, download — 13 commands total
- **Hermes Agent**: v0.6.0 (NousResearch/hermes-agent), MIT license, plugin-based architecture with hook events
- **Integration gap**: Current `hermes_integration.py` was built against an assumed API. Real Hermes plugin system uses `ctx.register_hook()` inside a plugin directory, not Protocol-based injection.
- **Hardware**: Dev machine has RTX 4070 8GB VRAM — Hermes 3 8B Q4 for collection, 3B model for fine-tuning
- **API access**: OpenAI subscription, Anthropic API key available as collection fallbacks
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
| Dual-use: add experiment/eval logging as parallel v1.2 milestone | Operational eval need + first-class mission commitment; reverses prior "model eval out of scope"; runs parallel to v1.1 since input/output diverge | — Pending (decided 2026-06-03 via /gsd-explore) |
| Separate `ExperimentRecord` over a shared base (not extend `KajibaRecord`) | Coding-specific validators don't apply to experiments; avoids god-object and full duplication | — Pending |
| Experiment data private/internal — no community publish | Eval data informs the user's own routing/fine-tune decisions; never enters the shared dataset | — Pending |

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
*Last updated: 2026-06-07 after Phase 14 (Live Experiment Capture) complete — env-driven experiment opt-in + `_build_experiment_record` (structural parity) + Design-B self-cleaning `_finalize_experiment` (one `exp_*.json`/session, D-08 staging/outbox bypass); schema frozen (ECAP-01). Live-Hermes SC#1 proof pending as UAT.*
