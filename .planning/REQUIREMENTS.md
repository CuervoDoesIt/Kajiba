# Requirements: Kajiba

**Defined:** 2026-03-30
**Core Value:** Real-world AI session data, tagged with full runtime context, flowing into a community dataset that accelerates local model fine-tuning for everyone.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Privacy & Trust

- [x] **PRIV-01**: User's consent level choice is enforced at export time — fields are stripped based on selected level (anonymous, trajectory_only, metadata_only, full)
- [x] **PRIV-02**: Hardware profiles are anonymized before export — GPU names generalized to families, RAM/VRAM rounded to standard tiers, OS version stripped
- [x] **PRIV-03**: Timestamps are jittered (±0-30 min) before export to prevent session correlation
- [ ] **PRIV-04**: Generic 40-character hex tokens are scrubbed when preceded by context keywords (key=, token=, secret=)
- [ ] **PRIV-05**: Organizational domain names (.company, .org, .io) are flagged for user review (not auto-redacted)
- [ ] **PRIV-06**: IP address regex no longer false-positives on version strings (e.g., Python 3.11.0.0)
- [ ] **PRIV-07**: User can request deletion of a contributed record via `kajiba delete <record_id>`
- [ ] **PRIV-08**: Deletion requests are tracked in a deletion index file in the dataset repository

### Data Quality

- [ ] **QUAL-01**: Quality tier (gold/silver/bronze/review_needed) and composite score are stored in the outbox record at submit time
- [ ] **QUAL-02**: Preview command shows inline redaction diff — original text with highlighted redactions side by side with scrubbed output
- [ ] **QUAL-03**: User can rate a staged record's quality via `kajiba rate` with a numeric score and optional tags
- [ ] **QUAL-04**: User can report pain points on a staged record via `kajiba report` with category, description, and severity
- [ ] **QUAL-05**: User annotations (ratings, pain points) are included in the exported record alongside auto-scores

### Dataset Publishing

- [ ] **PUB-01**: Scrubbed records are organized in the dataset repository as sharded JSONL files under `{model}/{tier}/` directories
- [ ] **PUB-02**: A catalog index file (catalog.json) is generated/updated on each publish, listing available models, tiers, record counts, and metadata
- [ ] **PUB-03**: Contributions to the dataset repository use a PR-based workflow (not direct push) for review and poisoning defense
- [ ] **PUB-04**: A dataset card (README.md) is auto-generated from dataset statistics including license, scrubbing methods, quality distribution, and model coverage
- [ ] **PUB-05**: User can publish scrubbed records to the dataset repository via `kajiba publish`

### Consumer Experience

- [ ] **CONS-01**: Dataset repository is organized by quality tier so consumers can download subsets by tier
- [ ] **CONS-02**: Catalog index includes model family, parameter count, quantization type, and context window for each record set
- [ ] **CONS-03**: User can browse the dataset catalog via `kajiba browse` with filters for model, tier, and hardware
- [ ] **CONS-04**: User can download a filtered subset of the dataset via `kajiba download` with model/tier/hardware filters

### Contribution Modes

- [ ] **CONT-01**: User can contribute in ad-hoc mode — review and approve each record before submission
- [ ] **CONT-02**: User can contribute in continuous mode — records meeting configured quality threshold are auto-submitted
- [ ] **CONT-03**: User can switch between ad-hoc and continuous modes via `kajiba config`
- [ ] **CONT-04**: Continuous mode parameters are configurable: minimum quality tier, consent level, auto-submit interval

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Advanced Privacy

- **ADVP-01**: LLM-based semantic PII scrubbing via local model (Ollama) catches personal names, company names, project names
- **ADVP-02**: Configurable scrub strictness levels (aggressive, balanced, permissive) with strictness recorded in ScrubLog
- **ADVP-03**: ScrubLog with per-category redaction counts persisted in exported records for consumer transparency

### Model Agnostic

- **AGNO-01**: Documented adapter protocol (Python ABC) allowing any AI tool to become a Kajiba data source
- **AGNO-02**: Generic adapter for non-Hermes AI tools that can ingest raw session JSON
- **AGNO-03**: Path decoupling — KAJIBA_DATA_DIR environment variable replaces hardcoded ~/.hermes/kajiba

### Community Scale

- **COMM-01**: Contribution statistics displayed via `kajiba stats --global` with total records, tier distribution, model coverage
- **COMM-02**: HuggingFace upload command for transitioning dataset to HuggingFace Hub
- **COMM-03**: Pseudonymous contribution tokens for optional leaderboard participation
- **COMM-04**: Croissant JSON-LD metadata for Google Dataset Search discoverability

## Out of Scope

| Feature | Reason |
|---------|--------|
| Fine-tuning tooling | Pipeline only — consumers bring their own training frameworks |
| Hosted API / cloud service | Local-first design; no central infrastructure |
| Model evaluation / benchmarking | Separate problem domain with dedicated tools (lm-eval-harness, HELM) |
| Automatic submission without review (ad-hoc mode) | Erodes contributor trust; only continuous mode auto-submits |
| Personal identity tracking / accounts | Creates GDPR obligations and privacy attack surface |
| Real-time streaming / live telemetry | Batch processing at session end is safer and more reliable |
| Synthetic data generation | Different product with different quality/governance properties |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PRIV-01 | Phase 1 | Complete |
| PRIV-02 | Phase 1 | Complete |
| PRIV-03 | Phase 1 | Complete |
| PRIV-04 | Phase 1 | Pending |
| PRIV-05 | Phase 1 | Pending |
| PRIV-06 | Phase 1 | Pending |
| PRIV-07 | Phase 3 | Pending |
| PRIV-08 | Phase 3 | Pending |
| QUAL-01 | Phase 2 | Pending |
| QUAL-02 | Phase 2 | Pending |
| QUAL-03 | Phase 2 | Pending |
| QUAL-04 | Phase 2 | Pending |
| QUAL-05 | Phase 2 | Pending |
| PUB-01 | Phase 3 | Pending |
| PUB-02 | Phase 3 | Pending |
| PUB-03 | Phase 3 | Pending |
| PUB-04 | Phase 3 | Pending |
| PUB-05 | Phase 3 | Pending |
| CONS-01 | Phase 5 | Pending |
| CONS-02 | Phase 5 | Pending |
| CONS-03 | Phase 5 | Pending |
| CONS-04 | Phase 5 | Pending |
| CONT-01 | Phase 4 | Pending |
| CONT-02 | Phase 4 | Pending |
| CONT-03 | Phase 4 | Pending |
| CONT-04 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 26 total
- Mapped to phases: 26
- Unmapped: 0

---
*Requirements defined: 2026-03-30*
*Last updated: 2026-03-30 after roadmap creation*
