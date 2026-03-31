# Feature Research

**Domain:** Community AI Training Data Pipeline
**Researched:** 2026-03-30
**Confidence:** MEDIUM-HIGH — Core platform features verified against BigCode/The Stack, HuggingFace Hub, MLCommons Croissant, Mozilla Foundation best practices, and Open Future governance frameworks. Specific UX/workflow patterns are MEDIUM (community norms, cross-validated across multiple sources). A few future differentiators are LOW (speculative extrapolation from trends).

---

## Feature Landscape

### Table Stakes

Features whose absence causes potential contributors or consumers to distrust or abandon the platform. These are "must have or users leave."

---

#### 1. Pre-submission PII preview with redaction diff
**Why expected:** Contributors sharing real AI session data are not going to trust a black-box pipeline. Seeing exactly what was redacted — and what was not — before data leaves the machine is the minimum bar for informed consent. BigCode's community noted that opaque scrubbing was a top trust concern. Kajiba's existing `preview` command is the skeleton; it must surface the scrub diff clearly.
**Complexity:** Low (skeleton exists — `preview` command + `ScrubLog` already there; UX polish needed)
**Current state:** Partial. `preview` command exists but the scrub diff display is minimal; `ScrubLog` contains per-category counts only, not inline diffs.

---

#### 2. Consent level selection with enforceable field stripping
**Why expected:** Contributors expect to choose how much they share. "I just want to share the code conversation, not my hardware fingerprint" is a reasonable request. Without enforcement, consent levels are theater. GDPR frameworks, the Mozilla open dataset best practices, and BigCode's governance model all treat configurable data minimization as baseline. Kajiba already has `consent_level` in its schema — but does not enforce it.
**Complexity:** Low-Medium (enforcement logic is a filter function; the schema fields and consent levels are defined; the main work is wiring `apply_consent_level()` into export/submit paths)
**Current state:** Schema field exists; enforcement is entirely unimplemented (confirmed in CONCERNS.md).

---

#### 3. Metadata anonymization before export
**Why expected:** Hardware profile + timestamp + precise RAM/VRAM combination can be a unique fingerprint even without any explicit PII. Rare GPU models (e.g., "NVIDIA A100 80GB SXM") narrow the contributor pool to dozens of people. Contributors who read their record output and see their exact GPU model + precise timestamp will not submit again. GPU generalization, timestamp jitter, and RAM/VRAM rounding to standard tiers are table stakes for a privacy-first pipeline.
**Complexity:** Low-Medium (a pure function; no dependencies outside schema/scrubber)
**Current state:** Entirely unimplemented (confirmed in CONCERNS.md as Layer D missing).

---

#### 4. Explicit opt-out / record deletion request mechanism
**Why expected:** After BigCode's experience and growing GDPR awareness, any community data platform without a "remove my contribution" path will face community rejection. Consumers who discover they want data removed must have a documented process. Even if technical deletion from trained weights is hard, dataset-level removal is achievable and expected.
**Complexity:** Medium (requires a record deletion index in the dataset repo; CLI command to flag a record ID for removal; a documented process; does not require retraining anything)
**Current state:** Not implemented. No deletion path exists.

---

#### 5. Dataset card / README with provenance and usage documentation
**Why expected:** HuggingFace, Kaggle, OpenML, and the MLCommons Croissant standard all treat dataset documentation as mandatory. Consumers downloading training subsets need to know: what is the license, what scrubbing was applied, what quality tiers are represented, what models contributed the data, what the known biases are. Without this, the dataset is unusable in a responsible workflow. The MLCommons Croissant standard (adopted by HuggingFace, Kaggle, Google Dataset Search) encodes this in machine-readable JSON-LD.
**Complexity:** Low (mostly documentation; auto-generation from dataset stats is Medium)
**Current state:** Not implemented. No dataset card or catalog metadata exists.

---

#### 6. Quality tier filtering for consumers (gold / silver / bronze / review_needed)
**Why expected:** Consumers fine-tuning local models need to control the quality floor of the data they train on. Downloading everything and filtering manually is unworkable at scale. The existing quality tier system (gold/silver/bronze) exists in the scorer — but it must be surfaced in the dataset structure so consumers can download subsets by tier without custom scripts.
**Complexity:** Low (quality tiers already computed; need to be stored in record and reflected in dataset directory structure)
**Current state:** Quality tiers are computed but not stored in outbox records (confirmed performance bottleneck in CONCERNS.md); not reflected in any dataset organization structure.

---

#### 7. Model metadata filtering for consumers (model family, quantization, context window)
**Why expected:** A consumer fine-tuning Mistral-7B Q4_K_M on a 16GB GPU needs data generated by similar models in similar runtime contexts. Data from GPT-4 with 128K context is actively harmful to their use case. Filtering by model name, quantization type, VRAM tier, and context window size is the minimum viable catalog feature. The Open Trusted Data Initiative and Croissant both mandate machine-readable model/runtime context metadata.
**Complexity:** Medium (requires model metadata stored in structured, queryable form in the dataset repo; a catalog index file)
**Current state:** Model metadata is captured in `ModelMetadata` schema but is not indexed or surfaced for filtering.

---

#### 8. License clarity (Apache 2.0 or CDLA Permissive 2.0)
**Why expected:** Community datasets without explicit permissive licenses are unusable in most fine-tuning workflows. The Open Trusted Data Initiative mandates CDLA Permissive 2.0 for contributed data. Mozilla's best practices require recorded license per data point. Without license metadata, consumers cannot use the data in commercially-viable models or share derivatives. This is not a feature request — it is a prerequisite for adoption.
**Complexity:** Low (metadata field; policy decision already made — Apache 2.0 in PROJECT.md)
**Current state:** Apache 2.0 declared in project. Not attached to individual records or the dataset card.

---

#### 9. Deduplication with visible record ID
**Why expected:** Contributors submitting the same session twice — accidentally or intentionally — will pollute the dataset and skew quality statistics. Consumers will encounter duplicate training examples which harm fine-tuning convergence. Content-addressable IDs and submission hash dedup are the established solution (already partially implemented via SHA-256 in Kajiba).
**Complexity:** Low (already implemented; needs enforcement at the repo/submission layer)
**Current state:** `compute_record_id()` and `compute_submission_hash()` exist; dedup enforcement on the dataset repo side is not implemented.

---

#### 10. Transparent scrubbing log surfaced in record
**Why expected:** Consumers need to know what was redacted in a record and with what confidence. A record that has had 50 regex redactions is less useful than one with zero. A record where the LLM scrubber flagged potential personal names is different from one it cleared. The `ScrubLog` already tracks counts per category — this must be included in the exported record so consumers can filter by scrub confidence.
**Complexity:** Low (ScrubLog exists in schema; needs to be serialized into the outbox record)
**Current state:** ScrubLog is computed but not persisted in the outbox record.

---

### Differentiators

Features that set Kajiba apart from generic dataset hosting. Not universally expected, but create strong community loyalty and competitive advantage.

---

#### 1. Runtime context as first-class dataset dimension
**What it is:** Every record carries structured, queryable runtime context: model name + version + parameter count + quantization type + context window + LoRA config + system prompt fingerprint + hardware tier + inference settings (temperature, top_p, etc.). No other community dataset captures this combination for coding AI sessions.
**Value proposition:** Enables consumers to find data generated under conditions that match their own runtime — dramatically increasing fine-tuning relevance. A developer training a 7B Q4 model on 8GB VRAM can filter for exactly that profile.
**Complexity:** Medium (schema fields exist; needs structured indexing and catalog query support)
**Sources:** No existing community dataset for coding AI sessions indexes the full runtime stack this way. This is a genuine gap.

---

#### 2. Two-pass PII scrubbing with LLM semantic layer
**What it is:** Regex pass (Layer B, already partially built) + local LLM semantic pass (Layer C, stub) that catches personal names, company names, project names, and context-dependent identifiers that regex cannot detect. Auto-redact high-confidence semantic PII; flag medium-confidence for user review.
**Value proposition:** "Tell John at Acme Corp to deploy Whisperforge" slips through regex. Semantic scrubbing is what separates a trustworthy community dataset from one that leaks contributors' professional identities. This is the primary privacy differentiator.
**Complexity:** High (requires local LLM via Ollama/llama.cpp; prompt engineering; confidence scoring; UI for flagged items)
**Dependencies:** Table stake #1 (preview/diff), Table stake #3 (metadata anonymization); requires local inference runtime

---

#### 3. Ad-hoc vs. continuous contribution modes
**What it is:** Ad-hoc mode: user reviews and approves every record before submission. Continuous mode: user sets parameters once; records meeting quality threshold are submitted automatically.
**Value proposition:** Different users have radically different comfort levels. Power users who want to maximize contribution velocity use continuous mode. Privacy-cautious users use ad-hoc with full review. Both audiences are underserved by existing dataset tooling. The choice itself signals respect for contributor autonomy.
**Complexity:** Medium (ad-hoc flow exists in the CLI skeleton; continuous mode requires a background daemon or session-end auto-submit; approval queue management)
**Dependencies:** Table stake #2 (consent enforcement), Table stake #1 (preview)

---

#### 4. User annotation refinement post-auto-score
**What it is:** After auto-scoring, the contributor can tag/adjust quality signals: mark turns as pain points, flag what worked, override quality tier reasoning, add free-text notes about the session context.
**Value proposition:** Heuristic scoring misses subjective quality signals. A session with syntactically valid but semantically wrong tool calls scores silver but the contributor knows it was a failure. User annotations on top of auto-scores create a richer quality signal than either alone. This is what separates community-curated from machine-curated data.
**Complexity:** Medium (CLI rate/report commands are collector methods only; need CLI surface for post-hoc annotation on staged records)
**Current state:** Collector methods exist (`on_rate`, `on_report`); no standalone CLI commands (confirmed gap in CONCERNS.md).

---

#### 5. Configurable scrub strictness levels
**What it is:** Users can choose their scrub strictness: aggressive (maximum redaction, may sacrifice coherence), balanced (default), permissive (regex only, no LLM pass). Strictness level is recorded in the `ScrubLog` and included in the record.
**Value proposition:** Different contributors have different privacy postures. Developers working on internal enterprise projects need aggressive scrubbing; developers on fully public OSS projects may prefer permissive to preserve technical content quality. Recording the strictness level lets consumers filter for higher-quality unredacted records.
**Complexity:** Low-Medium (config key exists; needs to be wired through the scrubbing pipeline as a policy parameter)

---

#### 6. Dataset catalog with CLI browsing and subset download
**What it is:** A structured dataset catalog (index file + per-model subdirectories) that consumers can browse with `kajiba browse`, filter by model/tier/hardware/date, and download a filtered JSONL subset.
**Value proposition:** Consumers should not need to clone the entire dataset repo and write custom scripts to get training-ready data. A first-class CLI consumer experience with filtering is table stakes for developer adoption, but rare in current community dataset tooling.
**Complexity:** High (requires catalog index schema; dataset repo structure design; `kajiba browse` and `kajiba download` CLI commands; incremental download support)
**Dependencies:** Table stakes #6 and #7 (tier and model filtering must be in catalog index)

---

#### 7. Contribution statistics and community leaderboard
**What it is:** Aggregate stats surfaced in CLI (`kajiba stats --global`) and in the dataset README: total records by tier, by model, by contributor count (anonymized), trend over time. Optionally a public leaderboard of contributor count (not identity).
**Value proposition:** Community data projects live or die by visible momentum. Contributors want to know the project is active. The Kaggle progression system (Novice → Grandmaster) shows gamification of contribution drives engagement. Kajiba's version: anonymized contribution counts, tier distribution, dataset growth over time.
**Complexity:** Medium (local stats already work; global stats require periodic aggregation in the dataset repo; leaderboard requires pseudonym/token system)

---

#### 8. Model-agnostic adapter protocol
**What it is:** A documented protocol (Python abstract base class or minimal interface spec) that any AI-assisted coding tool can implement to become a Kajiba data source — not just Hermes Agent.
**Value proposition:** The current Hermes-only coupling caps the total addressable contributor pool. Model-agnostic collection multiplies community size. Continue.dev, Aider, Cursor, any tool using LLM APIs can integrate. This is the network effect play.
**Complexity:** Medium (the HermesAgent Protocol class already uses structural typing; the main work is documentation, example adapters, and decoupling the hardcoded `~/.hermes/kajiba` path)
**Dependencies:** Resolving the hardcoded path issue (CONCERNS.md fragile areas)

---

### Anti-Features

Features to deliberately NOT build. Including them would add complexity, scope creep, or undermine core trust.

---

#### 1. Fine-tuning tooling
**Why avoid:** Kajiba is the pipeline, not the trainer. Including fine-tuning scripts invites scope explosion, framework-specific maintenance burden (Unsloth, Axolotl, LLaMA-Factory all evolve fast), and distracts from the pipeline's core quality. Consumers bring their own frameworks.
**What to do instead:** Provide training-ready JSONL exports in ShareGPT and Alpaca formats. Document how to load the output with popular frameworks. Link to Unsloth, LLaMA-Factory, and Axolotl in the README.

---

#### 2. Hosted API or cloud service
**Why avoid:** A hosted service requires infrastructure, authentication, rate limiting, SLAs, and legal liability for data hosted. It contradicts the local-first, privacy-first design philosophy. It also creates a central failure point and a monetization pressure that corrupts the community-commons governance model.
**What to do instead:** Everything runs locally. Distribution through GitHub repo (then HuggingFace). The value of Kajiba is precisely that it is not a service.

---

#### 3. Model evaluation or benchmarking
**Why avoid:** Evaluation is a completely separate problem domain. Adding benchmarking creates scope confusion ("Is this a data pipeline or a model eval framework?"), introduces complex statistical methodology, and already has excellent dedicated tools (lm-evaluation-harness, HELM, Eleuther eval harness).
**What to do instead:** Export records in DPO-candidate format so consumers can use them in evaluation frameworks. Leave the evaluation to those frameworks.

---

#### 4. Automatic submission without user review (in ad-hoc mode)
**Why avoid:** Contributors who submit data they haven't seen lose trust when they later discover what was shared. Even with excellent PII scrubbing, surprising contributors erodes the community. The ad-hoc mode must require explicit approval per record. Only continuous mode (an explicit opt-in) should submit without per-record review.
**What to do instead:** Default to ad-hoc with mandatory preview. Make continuous mode an explicit configuration choice with clear consent language.

---

#### 5. Personal identity tracking or contributor accounts
**Why avoid:** A login system means storing identity, which creates GDPR obligations and a privacy attack surface. It also creates inclusion friction (users don't want another account). Pseudonymous contribution tokens (optional) are sufficient for the leaderboard differentiator.
**What to do instead:** Use hardware-derived or user-set pseudonym tokens stored locally. Never associate identity with records in the shared dataset.

---

#### 6. Real-time streaming or live telemetry
**Why avoid:** Streaming data out of a coding session in real time creates privacy risk (data leaves before scrubbing completes), network dependency, and latency pressure. Batch processing at session end is safer, more reliable, and already the design.
**What to do instead:** Batch process at session end. The session-end hook already exists.

---

#### 7. Synthetic data generation
**Why avoid:** Synthetic data pipelines (generating artificial coding sessions via LLM) are a fundamentally different product with different quality properties, different governance implications, and a different value proposition. Mixing synthetic and real data in the same pipeline without clear separation will confuse consumers and undermine the "real-world session data" core value.
**What to do instead:** If synthetic data is ever desired, it should be a clearly separate dataset partition with explicit metadata flags. Not in scope for this pipeline.

---

## Feature Dependencies

```
Table stake #1 (PII preview/diff)
  └── Differentiator #2 (LLM semantic scrubbing)
      └── Differentiator #5 (scrub strictness levels)

Table stake #2 (consent enforcement)
  └── Table stake #3 (metadata anonymization) [both in scrub/export path]
  └── Differentiator #3 (ad-hoc vs continuous modes)

Table stake #6 (quality tier filtering for consumers)
  └── Table stake #7 (model metadata filtering)
  └── Differentiator #6 (CLI catalog browsing)
      └── Differentiator #7 (contribution statistics)

Table stake #5 (dataset card / provenance documentation)
  └── Table stake #8 (license clarity per record)
  └── Differentiator #6 (CLI catalog browsing)

Table stake #9 (deduplication)
  └── Must be enforced before Table stake #6 and #7 (catalog integrity)

Differentiator #4 (user annotation refinement)
  └── Table stake #1 (preview must exist for annotation to make sense)
  └── Table stake #6 (annotations feed into quality tier)

Differentiator #8 (model-agnostic adapter protocol)
  └── Table stake #2, #3 (consent and anonymization must apply regardless of source agent)
  └── Requires path decoupling (CONCERNS.md: hardcoded ~/.hermes/kajiba path)
```

---

## MVP Definition

### Launch With (v1)

These are the features without which the first public dataset push fails.

| Feature | Rationale | Source |
|---------|-----------|--------|
| Consent enforcement (table stake #2) | Silent consent violations are a launch-stopper | CONCERNS.md gap |
| Metadata anonymization (table stake #3) | Hardware fingerprinting breaks contributor trust | CONCERNS.md gap |
| Quality tier stored in outbox record (table stake #6, partial) | Required for dataset organization; currently re-computed every time | CONCERNS.md performance |
| Dataset card auto-generated from stats (table stake #5) | Without this the dataset repo is unusable | Not implemented |
| Model metadata in catalog index (table stake #7, partial) | Consumers need model-based filtering on day one | Not implemented |
| License field per record (table stake #8) | Required for consumer legal use | Not implemented |
| ScrubLog in outbox record (table stake #10) | Consumers need scrub transparency | Not implemented |
| Record deletion index + CLI flag (table stake #4) | Needed before first public push; cannot add later without breaking trust | Not implemented |
| Scrub regex gap fixes (40-char hex, org domain flagging) | Known PII leak vectors; must be closed before launch | CONCERNS.md |

### Add After Validation (v1.x)

Features that improve the experience once the pipeline is live and basic trust is established.

| Feature | Rationale |
|---------|-----------|
| CLI rate/report commands (differentiator #4) | Contributor experience improvement; not blocking launch |
| Configurable scrub strictness (differentiator #5) | Config key exists; wire-up work |
| Model-agnostic adapter protocol (differentiator #8) | Expands contributor pool; not required for initial GitHub dataset |
| Ad-hoc vs continuous modes (differentiator #3) | Continuous mode is a comfort-level enhancement; ad-hoc already exists |
| Dataset catalog CLI browsing (differentiator #6, partial) | `kajiba browse` and `kajiba download` commands |
| Contribution statistics (differentiator #7, local) | `kajiba stats` with global dataset stats |
| Path decoupling / KAJIBA_DATA_DIR env var | Needed before adapter protocol; low effort |

### Future Consideration (v2+)

Features requiring significant architecture work or external dependencies not yet in scope.

| Feature | Rationale | Blocker |
|---------|-----------|---------|
| LLM semantic PII scrubbing (differentiator #2) | High privacy value; requires local inference runtime (Ollama/llama.cpp) | Dependency on external runtime; stub exists |
| HuggingFace upload command | Already in PROJECT.md as deferred | Waiting for GitHub validation |
| Full catalog CLI with subset download | Requires catalog index design to stabilize first | Catalog index schema must be validated |
| Contribution leaderboard (differentiator #7, global) | Requires pseudonym token system design | Token system not designed |
| Croissant JSON-LD dataset metadata | MLCommons standard for maximum discoverability | Overkill for GitHub-first phase |

---

## Feature Prioritization Matrix

| Feature | User Impact | Build Effort | Risk if Skipped | Priority |
|---------|-------------|--------------|-----------------|----------|
| Consent enforcement | HIGH | Low-Med | LAUNCH BLOCKER | P0 |
| Metadata anonymization | HIGH | Low-Med | LAUNCH BLOCKER | P0 |
| ScrubLog in outbox record | HIGH | Low | Quality loss | P0 |
| Quality tier stored in record | Med | Low | Re-score perf + catalog broken | P0 |
| Dataset card generation | HIGH | Med | Dataset unusable | P0 |
| Record deletion index | HIGH | Med | Trust-breaking if absent at launch | P0 |
| Regex scrubber gap fixes | HIGH | Low | PII leak at launch | P0 |
| License per record | Med | Low | Consumer legal risk | P0 |
| Model metadata catalog index | HIGH | Med | Consumer can't filter | P1 |
| CLI rate/report commands | Med | Low | Annotation quality | P1 |
| Scrub strictness config | Med | Low | Contributor flexibility | P1 |
| Model-agnostic adapter | HIGH | Med | Locked to Hermes only | P1 |
| Ad-hoc vs continuous modes | Med | Med | Power user friction | P1 |
| Dataset catalog CLI browse | HIGH | High | Consumer DX only via raw files | P2 |
| LLM semantic scrubbing | HIGH | High | Best privacy scrubbing | P2 |
| Contribution statistics | Low | Med | Community momentum visibility | P2 |
| HuggingFace upload | HIGH | Med | Broader distribution | P2 (post-GitHub) |
| Leaderboard / tokens | Low | High | Community gamification | P3 |
| Croissant JSON-LD metadata | Med | High | Google Dataset Search index | P3 |

---

## Competitor Feature Analysis

### HuggingFace Hub (dataset hosting)
**What they do well:** Dataset cards with rich YAML metadata, dataset viewer (in-browser data exploration), license filtering, task category filters, download stats, Croissant JSON-LD export, discussion threads per dataset, private/public toggle.
**What they don't do:** Contributor-side PII scrubbing, runtime context metadata, consent level enforcement, session-level quality scoring, model-specific filtering (they have model metadata for model repos, not for the data records themselves).
**Lesson for Kajiba:** HuggingFace is the distribution layer; Kajiba's value is everything that happens before data reaches that layer. Kajiba should aim to be HuggingFace-compatible (JSONL + dataset card), not to replicate it.

### BigCode / The Stack
**What they do well:** Permissive license selection, "Am I in the Stack" opt-out tool, automated PII redaction (F1-score ~90%), formal governance card, tiered data access (public processed vs. restricted raw), quarterly removal updates.
**What they don't do:** Real-time contributor-side review, consent levels, runtime context metadata, quality scoring by the contributor.
**Lesson for Kajiba:** BigCode's opt-out model and governance card are the trust foundations Kajiba needs to replicate. The "Am I in the dataset" lookup is a v1.x feature worth adding.

### Kaggle Datasets
**What they do well:** Contributor progression system (Novice → Grandmaster), voting, discussion, public download counts, notebook integration, usability tags.
**What they don't do:** Privacy-first workflows, PII scrubbing, session-level quality scoring, runtime context.
**Lesson for Kajiba:** Contribution stats and progression signals build community momentum. The quality is simpler here (Kajiba's auto-scoring + user annotation is more rigorous).

### OpenML
**What they do well:** Uniform dataset formatting, rich metadata for automated processing, 21,000+ datasets, API for programmatic access.
**What they don't do:** LLM-specific metadata, runtime context, privacy scrubbing.
**Lesson for Kajiba:** API-first access matters for consumers who want to automate dataset integration into training pipelines.

### ShareGPT / WizardLM / Alpaca community datasets
**What they do well:** Standardized conversation formats that training frameworks consume directly.
**What they don't do:** PII scrubbing, runtime context, quality scoring, consent management.
**Lesson for Kajiba:** The to_sharegpt() and to_dpo_candidate() export methods in KajibaRecord are the right direction. Kajiba's output should be drop-in for any tool that accepts ShareGPT format.

---

## Sources

- [HuggingFace Dataset Cards Documentation](https://huggingface.co/docs/hub/en/datasets-cards) — HIGH confidence. Official HuggingFace metadata schema and card requirements.
- [HuggingFace Datasets Overview](https://huggingface.co/docs/hub/en/datasets-overview) — HIGH confidence. Official feature documentation.
- [MLCommons Croissant Metadata Format Announcement](https://mlcommons.org/2024/03/croissant_metadata_announce/) — HIGH confidence. Official MLCommons announcement; adopted by HuggingFace, Kaggle, Google Dataset Search.
- [Croissant Format Specification](https://docs.mlcommons.org/croissant/docs/croissant-spec.html) — HIGH confidence. Official specification.
- [Mozilla Foundation: Towards Best Practices for Open Datasets for LLM Training](https://www.mozillafoundation.org/en/research/library/towards-best-practices-for-open-datasets-for-llm-training/) — HIGH confidence. Practitioner-validated best practices document from 2024 dataset convening.
- [BigCode Data Governance Case Study - The Turing Way](https://book.the-turing-way.org/project-design/data-security/data-governance/bigcode-casestudy/) — HIGH confidence. Authoritative case study of The Stack governance model.
- [BigCode Governance Card](https://arxiv.org/html/2312.03872v1) — HIGH confidence. Formal governance documentation.
- [Open Future: Commons-Based Data Set Governance for AI](https://openfuture.eu/publication/commons-based-data-set-governance-for-ai/) — MEDIUM confidence. Policy framework from established digital rights organization.
- [Open Trusted Data Initiative Dataset Specification](https://the-ai-alliance.github.io/open-trusted-data-initiative/dataset-requirements/) — MEDIUM confidence. AI Alliance governance requirements; cross-validates HuggingFace metadata standards.
- [LLM DataHub: Awesome Datasets for LLM Training](https://github.com/Zjh-819/LLMDataHub) — MEDIUM confidence. Community-curated list; reveals format conventions in practice.
- [Unsloth Dataset Formats Guide](https://unsloth.ai/docs/get-started/fine-tuning-llms-guide/datasets-guide) — MEDIUM confidence. ShareGPT vs Alpaca format usage in fine-tuning workflows.
- [Analyzing Dataset Annotation Quality Management (MIT Press / Computational Linguistics)](https://direct.mit.edu/coli/article/50/3/817/120233/Analyzing-Dataset-Annotation-Quality-Management-in) — MEDIUM confidence. Academic survey of annotation quality patterns.
- [BigCode / The Stack v2 on HuggingFace](https://huggingface.co/datasets/bigcode/the-stack-v2) — HIGH confidence. Primary reference for community coding dataset patterns.
- [OSI: Data Governance in Open Source AI](https://opensource.org/wp-content/uploads/2025/02/2025-OSI-DataGovernanceOSAI-final-v5.pdf) — MEDIUM confidence. Policy framework from Open Source Initiative.
