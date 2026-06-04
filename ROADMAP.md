# Kajiba Roadmap

> Community data pipeline for open-source local model improvement.
> Target integration: Hermes Agent by NousResearch.

This document tracks the phased development plan, milestones, and checkpoints for Kajiba. Each phase builds on the previous one and has clear deliverables that gate progression to the next.

---

## Phase 1 — MVP (Weeks 1-6)

**Goal:** Prove the core concept works end-to-end on a single machine. A user can run Hermes Agent, capture a session, scrub PII, score quality, and export a Kajiba-format record.

### Milestones

- [ ] **M1.1 — Schema v0.1 finalized**
  - Define top-level record schema (JSON) with required and optional fields
  - Implement controlled vocabularies (outcome tags, pain point categories)
  - Schema versioning strategy documented
  - ShareGPT export compatibility verified

- [ ] **M1.2 — Collector plugin skeleton**
  - `KajibaCollector` class with session lifecycle hooks (`on_session_start`, `on_turn_complete`, `on_session_end`)
  - Model metadata extraction from Hermes Agent config
  - Hardware profile auto-detection (GPU, CPU, RAM, OS)
  - Turn capture with tool call enrichment (name, input, output, status, latency)

- [ ] **M1.3 — Slash commands: `/rate` and `/report`**
  - `/rate [1-5] [tags...]` — attach user rating and outcome tags to current session
  - `/report [category] [text]` — submit structured pain point reports
  - Input validation against controlled vocabularies

- [ ] **M1.4 — PII scrubber (regex layer)**
  - Pattern matching for: file paths, API keys, network identifiers, emails, phone numbers, SSH keys, connection strings
  - Type-tagged placeholder replacement (`[REDACTED_PATH]`, `[REDACTED_KEY]`, etc.)
  - Scrub log generation (counts of each redaction type)

- [ ] **M1.5 — Local quality scorer**
  - Sub-scores: trajectory coherence, tool call validity, outcome signal quality, information density, metadata completeness
  - Weighted composite score (0.0 - 1.0)
  - Quality tier assignment (gold / silver / bronze / review_needed)

- [ ] **M1.6 — JSONL export + manual HF upload**
  - `/kajiba preview` — show submission preview with PII scrub results
  - `/kajiba submit` — write finalized record to `~/.hermes/kajiba/outbox/`
  - `kajiba-upload` helper script using `huggingface_hub` to create dataset PRs

### Phase 1 Checkpoint

- [ ] End-to-end test: capture a real Hermes Agent session, scrub, score, export, and upload to a test HF dataset
- [ ] All unit tests passing for schema validation, scrubber, and scorer
- [ ] Internal documentation complete for plugin installation and usage

---

## Phase 2 — Pipeline (Weeks 7-14)

**Goal:** Replace manual upload with an automated ingestion pipeline. Add the LLM-based PII scrubber and dedup layer.

### Milestones

- [ ] **M2.1 — Ingestion API (FastAPI)**
  - POST endpoint for record submission with schema validation
  - Rate limiting per contributor
  - Schema version negotiation (accept older versions, normalize to latest)

- [ ] **M2.2 — LLM-based semantic PII scrubber**
  - Local model prompt for detecting semantic PII (names, company names, project names, locations)
  - Confidence-based redaction (high = auto, medium = flagged for user review)
  - Integration with regex scrubber as a two-pass pipeline

- [ ] **M2.3 — Deduplication layer**
  - Content-addressable hashing (`submission_hash`) for exact dedup
  - Near-duplicate detection for trivially varied resubmissions

- [ ] **M2.4 — Schema validator service**
  - Validate incoming records against all supported schema versions
  - Normalize older schema versions to latest before storage
  - Rejection with actionable error messages for malformed records

- [ ] **M2.5 — Direct submission from Hermes Agent**
  - `hermes kajiba submit` command (replaces manual upload workflow)
  - Authentication via pseudonymous contributor ID

- [ ] **M2.6 — First public HF dataset release**
  - `CuervoDoesIt/kajiba-community` dataset published on HuggingFace
  - Dataset card with schema docs, usage examples, and contribution guide

### Phase 2 Checkpoint

- [ ] Ingestion API deployed and accepting submissions
- [ ] LLM + regex PII scrubbing pipeline validated against test trajectories containing known PII
- [ ] Dedup correctly rejects identical and near-duplicate submissions
- [ ] At least 50 records in public HF dataset

---

## Phase 3 — Curation (Weeks 15-22)

**Goal:** Build community quality control and produce the first training-ready datasets. Generate the first Atropos RL environment from community data.

### Milestones

- [ ] **M3.1 — Quality tier system (production)**
  - Gold / Silver / Bronze / Review-needed tiers enforced on all records
  - Tier-based access controls for curated dataset downloads

- [ ] **M3.2 — Community voting system**
  - Upvote/downvote on individual records via dataset browser
  - Weighted votes based on contributor history (1.0x base, up to 2.0x for prolific contributors)
  - Auto-quarantine for records with community score below -0.5

- [ ] **M3.3 — DPO pair generator**
  - Match records with same task prompt but divergent ratings
  - Generate chosen/rejected pairs for Direct Preference Optimization training
  - Export in standard DPO format compatible with Axolotl / LLaMA-Factory

- [ ] **M3.4 — Adversarial submission detection**
  - Detect bulk bot-generated submissions (uniform quality scores)
  - Prompt injection detection in trajectory text
  - Circular/vacuous trajectory detection
  - Semantic dedup for padded submissions

- [ ] **M3.5 — Dataset browser (HF Spaces)**
  - Searchable, filterable UI for browsing community records
  - Quality tier and community score visualizations
  - Direct voting integration

- [ ] **M3.6 — First Atropos environment from community data**
  - Task clustering by category, tool signature, and difficulty
  - Environment scaffolding with reward function derivation
  - Validation suite with test rollouts
  - Published as pip-installable package and Hermes skill

### Phase 3 Checkpoint

- [ ] At least 500 curated records across multiple task categories
- [ ] At least 1 Atropos environment generated, validated, and published
- [ ] DPO pairs generated and tested in a fine-tuning run
- [ ] Community voting active with at least 10 participating voters

---

## Phase 4 — Flywheel (Weeks 23-30)

**Goal:** Close the loop. Community data improves models, better models generate better data. Prepare for upstream proposal to NousResearch.

### Milestones

- [ ] **M4.1 — Environment refresh pipeline**
  - Monthly re-clustering of all gold/silver records
  - Automated diffing against previous environment versions
  - Publish new minor version when >20% new tasks or >10% changed references
  - Old versions preserved for reproducibility

- [ ] **M4.2 — Benchmark suite**
  - Standardized evaluation tasks derived from community data
  - Reproducible scoring across model versions
  - Regression detection for model updates

- [ ] **M4.3 — Contributor leaderboard**
  - Top contributors by volume and quality tier on HF dataset page
  - Attribution system for model cards of models trained on Kajiba data

- [ ] **M4.4 — Contribution incentive system**
  - Environment naming credits for nucleus contributors
  - Governance participation rights for active contributors
  - Voting rights on schema changes and curation policies

- [ ] **M4.5 — Upstream proposal to NousResearch**
  - Compile evidence: dataset size, quality distribution, community engagement
  - Prepare integration RFC: collector as built-in Hermes skill, `/rate` and `/report` in core
  - Engage NousResearch team on Discord

### Phase 4 Checkpoint

- [ ] At least 1 model fine-tuned on Kajiba data with measurable improvement
- [ ] Environment refresh pipeline running on schedule
- [ ] Leaderboard and incentive system live
- [ ] Upstream proposal drafted and shared with NousResearch

---

## Phase 5 — Scale (Ongoing)

**Goal:** Expand beyond the initial scope. Support multiple model harnesses, federated collection, and training partnerships.

### Milestones

- [ ] **M5.1 — Multi-model benchmarking**
  - Compare performance across model families using standardized Kajiba tasks
  - Cross-model trajectory analysis (which models excel at which task categories)

- [ ] **M5.2 — Cross-harness schema support**
  - Extend schema to accept trajectories from agent harnesses beyond Hermes
  - Adapter plugins for popular harnesses (e.g., OpenHands, SWE-agent)

- [ ] **M5.3 — Federated collection**
  - Privacy-preserving collection for enterprise/sensitive deployments
  - Aggregated statistics without raw trajectory sharing
  - Differential privacy guarantees for contributed metadata

- [ ] **M5.4 — Model training partnerships**
  - Collaborate with model labs using Kajiba data for training runs
  - Publish training reports and model cards with Kajiba data provenance

---

## Key Dates and Gates

| Gate | Criteria | Blocks |
|------|----------|--------|
| **Phase 1 exit** | Schema finalized, collector works e2e, export + upload functional | Phase 2 |
| **Phase 2 exit** | Ingestion API live, LLM scrubber validated, public HF dataset exists | Phase 3 |
| **Phase 3 exit** | 500+ records, 1+ Atropos env published, community voting active | Phase 4 |
| **Phase 4 exit** | Flywheel demonstrated (data -> model -> better data), upstream proposal sent | Phase 5 |
| **Phase 5** | Ongoing — no exit gate, continuous expansion | — |

## How to Use This Roadmap

- Check off milestones as they are completed
- Each phase has a **Checkpoint** section — all checkpoint items must pass before moving to the next phase
- Milestones within a phase can be worked on in parallel where dependencies allow
- Update this file as scope evolves or timelines shift
