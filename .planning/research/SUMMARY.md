# Project Research Summary

**Project:** Kajiba
**Domain:** Community AI Training Data Pipeline
**Researched:** 2026-03-30
**Confidence:** MEDIUM-HIGH

## Executive Summary

Kajiba is a local-first, privacy-first CLI pipeline that collects real-world AI-assisted coding sessions, scrubs PII, scores quality, and publishes structured JSONL records to a community Git-based dataset. The research consensus is clear: build this as a layered pipeline (Source → Scrub → Score → Contribute → Publish) where each stage has a single, testable responsibility. The existing codebase has a solid foundation — Pydantic v2 schemas, regex scrubbing, quality scoring, and a Click/Rich CLI — but is missing several launch-blocking features: consent enforcement, metadata anonymization, LLM-based semantic scrubbing, and the dataset publishing infrastructure itself.

The recommended approach is to ship in three tightly-scoped phases before any community-facing release. Phase 1 closes the privacy and trust gap: consent enforcement, metadata anonymization, regex hardening, and scrub transparency. Phase 2 builds the dataset publishing infrastructure: model-agnostic source adapters, the dataset repository structure, the catalog index, and the contribution mode gate. Phase 3 adds the features that drive community growth: LLM semantic scrubbing, the consumer-facing CLI catalog, contribution stats, and the adapter protocol for non-Hermes tools. Attempting to publish the dataset before Phase 1 is complete is explicitly identified as a launch blocker by the pitfalls research — consent unenforcement and hardware fingerprinting are active privacy violations, not hypothetical risks.

The three critical risks to manage throughout are: (1) PII leakage through the regex-only scrubber and unenforced consent levels — both confirmed gaps in the current codebase; (2) dataset poisoning via unvalidated community contributions — requires a PR-based submission model before the repository goes live; (3) Git repository size — plan to migrate to HuggingFace once the dataset exceeds 2 GB, which can happen faster than expected with rich metadata records. All three risks have well-understood mitigations; none require exotic technology.

---

## Key Findings

### Recommended Stack

The existing stack (Python 3.11+, Pydantic v2, Click, Rich, pytest) is the right foundation and should not change. Six new libraries are needed for the active milestone, all verified on PyPI at current versions. The technology selections are conservative and justified: Ollama Python client over llama-cpp-python (contributor setup simplicity wins over raw control), Presidio + spaCy over LLM-only PII detection (structured NER is 20-50ms vs 500ms-2s per record — use both, in order), APScheduler over the `schedule` library (daemon mode requires thread-safe, configurable intervals with graceful shutdown), pydantic-settings over raw YAML (already have Pydantic v2, zero-cost upgrade with type safety), GitPython over subprocess git wrapping (shell injection safety for paths with spaces).

The two-pass scrubbing architecture is the central stack pattern: Pass 1 is the existing regex layer, Pass 2 is Presidio + spaCy NER for structured entities (names, orgs, locations), Pass 3 is an optional Ollama LLM semantic pass for ambiguous context-dependent identifiers. The Ollama `/api/show` endpoint also doubles as the model metadata capture mechanism — it returns parameter count, quantization level, family, context length, and architecture for any locally-pulled model.

**Core new technologies:**
- `ollama >=0.6.1`: Local LLM backend for semantic PII scrubbing and model metadata — first-party client, simplest contributor setup
- `presidio-analyzer + presidio-anonymizer >=2.2.362`: Structured PII detection (NER + regex) — Microsoft-maintained, catches names/orgs/locations that regex misses
- `spacy >=3.8.14` with `en_core_web_lg`: NLP engine backing Presidio — large model required for adequate recall on PII
- `GitPython >=3.1.46`: Git operations for dataset repo management — maintenance-mode but complete and safe
- `APScheduler >=3.11.2,<4.0`: Background daemon scheduler for continuous contribution mode — pin to 3.x API, 4.x is alpha
- `pydantic-settings >=2.13.1`: Structured config management replacing ad-hoc YAML reads — natural companion to existing Pydantic v2
- `filelock >=3.25.2`: Single-instance lock for daemon mode — prevents concurrent background collectors

### Expected Features

The features research makes a sharp distinction between what blocks the first dataset push (P0) and what improves the experience afterward. Nine features are launch blockers — not "nice to have" but "the dataset is unsafe or unusable without them."

**Must have before any community-facing release (P0):**
- Consent level enforcement (field stripping at export) — currently schema-only, unimplemented; active privacy violation
- Metadata anonymization (GPU generalization, timestamp jitter, RAM/VRAM rounding, OS stripping) — hardware profiles uniquely fingerprint contributors
- ScrubLog serialized into outbox record — consumers must know what was redacted
- Quality tier persisted in record at submit time — currently recomputed on every read, breaks catalog integrity
- Dataset card / README auto-generated from stats — without this the repo is undiscoverable and unusable
- Record deletion request mechanism (deletion index + CLI flag) — cannot add trust retroactively; must exist at launch
- Regex scrubber gap fixes (40-char hex token, org domain flagging) — confirmed PII leak vectors
- License field per record (Apache 2.0) — legal requirement for consumer use

**Should have after initial validation (P1):**
- CLI `rate` and `report` commands for post-hoc annotation
- Configurable scrub strictness levels wired through the pipeline
- Model-agnostic adapter protocol (expands contributor pool beyond Hermes)
- Ad-hoc vs continuous contribution modes
- Model metadata catalog index for consumer filtering
- `KAJIBA_DATA_DIR` env var and path decoupling

**Defer to v2+:**
- LLM semantic PII scrubbing (high value but requires external runtime dependency)
- Full CLI catalog browser (`kajiba browse`, `kajiba download`)
- Contribution leaderboard and pseudonym tokens
- HuggingFace upload command (after GitHub validation)
- Croissant JSON-LD dataset metadata

**Explicit anti-features — do not build:**
Fine-tuning tooling, hosted API, model evaluation/benchmarking, real-time streaming, personal identity tracking, synthetic data generation.

### Architecture Approach

The recommended architecture extends the existing linear pipeline with three new vertical concerns: a Source Layer (pluggable adapters behind a `SourceAdapter` ABC), a Contribution Mode Layer (`ContributionManager` strategy object governing ad-hoc vs continuous flow), and a Dataset Repository Layer (separate Git repo with `Publisher`, `CatalogBuilder`, and a `catalog.json` index). The existing Capture → Scrub → Score → Outbox pipeline is preserved and made source-agnostic by replacing Hermes-specific method signatures with a neutral `SessionData` dataclass as the pipeline's entry point.

**Major components:**
1. `SourceAdapter` ABC + `SourceRegistry` — pluggable per-tool normalization; `HermesAdapter` refactored from existing `hermes_integration.py`; `GenericAdapter` for file-drop ingestion
2. `ConsentEnforcer` — pure function that strips fields by consent level; must run before any write to disk, not only at display time
3. `ContributionManager` — strategy object holding ad-hoc queue vs continuous auto-submit behavior; single authority on mode logic, not scattered across CLI commands
4. `Publisher` + `CatalogBuilder` — writes sharded JSONL to `data/by-model/{slug}/{tier}/shard-NNNN.jsonl`; regenerates `catalog.json` once per batch, not per record
5. Separate `kajiba-dataset` Git repo — append-only; records in `revoked.json` rather than deleted; `catalog.json` is the consumer entry point

**The build order matters.** The architecture research provides a concrete 10-step dependency sequence: `SourceAdapter` ABC first (unblocks everything), then `HermesAdapter` refactor (highest-risk step, touches working code), then `CollectorRefactor` (accepts `SessionData`), then `ConsentEnforcer` (pure function, testable in isolation), then `ContributionManager`, then `CatalogBuilder`, then `Publisher`, then CLI extensions, then dataset repo scaffolding.

**Key patterns to follow:**
- ABC for in-package adapters, Protocol for community-contributed adapters (structural subtyping without inheritance dependency)
- Simple dict registry for adapter discovery now; entry_points only when adapters distribute as separate packages
- Strategy pattern for contribution modes, not inheritance and not scattered conditionals
- Append-only dataset with `revoked.json` for post-publish corrections (never rewrite git history)
- Shard files at 50 MB / 10K records per shard — not one file per record (git degrades above ~10K files)

### Critical Pitfalls

1. **Regex-only scrubbing passes semantic PII (CP-1, CRITICAL)** — Names, employer names, and project names are invisible to regex. Research shows regex-only approaches achieve ~65% PII recall. The `scrubber_llm.py` stub currently raises `NotImplementedError`. Must implement two-pass (Presidio NER + optional Ollama semantic) before accepting any real contributor data. Also fix the `ScrubResult` name collision between `scrubber.py` and `scrubber_llm.py` before assembling the two-pass pipeline.

2. **Consent level declared but never enforced (CP-2, CRITICAL)** — `consent_level` is in the schema; `apply_consent_level()` does not exist; `export_record()` and `submit` ignore the field entirely. Contributors who set `consent_level: anonymous` are not protected. CONCERNS.md confirms this. Implement `ConsentEnforcer.apply()` as a hard gate before any write to disk, run in both ad-hoc and continuous modes. Add tests asserting specific fields are absent per consent level.

3. **Hardware metadata fingerprinting (CP-3, HIGH)** — Exact GPU model + precise timestamp + exact RAM/VRAM is a unique fingerprint. Rare hardware (A100, H100) narrows the contributor pool to dozens of people globally. Implement all four Layer D anonymization steps (GPU generalization, timestamp jitter ±30 min, VRAM/RAM rounding to standard tiers, OS version stripping) as a required pipeline stage, not optional.

4. **Dataset poisoning via community contributions (CP-4, HIGH)** — As few as 250 malicious documents can backdoor an LLM fine-tune (demonstrated in practice, not theory). Defense: PR-based submission model (no direct push to dataset repo), submission rate limiting per contributor fingerprint, suspicious pattern detection across submissions. This must be in place before the repository goes live.

5. **IP regex false positives corrupt technical content (CP-5, HIGH)** — The existing `\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b` pattern matches Python version strings (`3.11.0.0`), CUDA versions (`12.2.1.0`), and library versions. An already-present regression that actively degrades training data quality. Fix with negative lookbehind/lookahead for version-string contexts; add false-positive test cases for version numbers.

---

## Implications for Roadmap

Based on combined research, three phases are recommended before community launch, with a fourth phase for growth features.

### Phase 1: Privacy Foundation

**Rationale:** Three of the four CRITICAL pitfalls (CP-1 partial, CP-2, CP-3) are in the scrubbing and consent path. The research is unambiguous: no external contributor data should be accepted while consent enforcement is absent and metadata anonymization is unimplemented. These are active privacy violations in the current codebase, not future risks. This phase has zero external dependencies and can be built and tested entirely with fixture data.

**Delivers:** A scrubber you can trust. Every record exported from this phase will have enforced consent stripping, anonymized metadata, and a transparent scrub log. Contributors can see what was redacted. No PII leaks through regex false positives.

**Addresses:**
- Consent level enforcement (P0 feature, CP-2 pitfall)
- Metadata anonymization — all 4 Layer D steps (P0 feature, CP-3 pitfall)
- ScrubLog serialized into outbox record (P0 feature)
- Quality tier persisted in record at submit time (P0 feature, TD-4)
- Regex scrubber gap fixes: 40-char hex token, org domain flagging, IP false positive fix (P0 feature, CP-5, SM-3)
- PII preview diff surfaced in `kajiba preview` (UP-1)
- Consent level explained in CLI (UP-2)
- `ScrubResult` name collision resolved (TD-1)
- Redaction objects stop storing original PII text (SM-1)
- Hermes integration test coverage with `MockHermesAgent` (IG-2)

**Avoids:** CP-2 (silent consent breach), CP-3 (hardware fingerprinting), CP-5 (IP regex corruption), SM-1 (PII in logs)

### Phase 2: Dataset Publishing Infrastructure

**Rationale:** Phase 1 produces trustworthy records. Phase 2 gives those records somewhere to go. The source adapter refactor, consent enforcement wiring, and catalog infrastructure all have hard interdependencies (see ARCHITECTURE.md build order steps 1-10). This phase also decouples from Hermes (IG-1), which is required before the dataset can accept contributions from other tools. Dataset poisoning defense (CP-4) must be in place before the repo goes live.

**Delivers:** A working `kajiba publish` command that writes scrubbed, consent-stripped records into a structured dataset repo, generates a `catalog.json` index, and pushes to GitHub via a PR-based contribution model. Contributors can submit in ad-hoc mode with explicit per-record review.

**Uses:**
- `GitPython >=3.1.46` for git operations
- `pydantic-settings >=2.13.1` for config management
- `filelock >=3.25.2` for daemon single-instance safety

**Addresses:**
- Source adapter ABC + `HermesAdapter` refactor (architecture foundation)
- Collector refactored to accept `SessionData` (model-agnostic)
- `GenericAdapter` for file-drop ingestion
- `KAJIBA_DATA_DIR` env var, path decoupling (IG-1)
- `ContributionManager` with ad-hoc mode queue and review gate
- `Publisher` with sharded JSONL output (`shard-NNNN.jsonl`)
- `CatalogBuilder` regenerating `catalog.json` once per batch
- Dataset repo scaffolding with `README.md`, `schemas/v1/`, directory skeleton
- Dataset card auto-generated from stats (P0 feature)
- License field per record (P0 feature)
- Record deletion index + `kajiba delete` CLI command (P0 feature)
- Deduplication enforced at publish layer (dedup hash already implemented)
- PR-based contribution model in dataset repo (CP-4 defense)
- psutil and pyyaml promoted to declared dependencies with warnings (IG-3)

**Avoids:** CP-4 (dataset poisoning), IG-1 (hardcoded Hermes path), Anti-Pattern 2 (mode logic in CLI), Anti-Pattern 3 (one file per record), Anti-Pattern 5 (consent only at display time)

### Phase 3: Contributor Experience

**Rationale:** With a working, safe pipeline, Phase 3 focuses on the features that reduce friction and expand the contributor base. Continuous mode, annotation refinement, and scrub strictness configuration all build on the contribution mode infrastructure from Phase 2. Model-agnostic adapter protocol documentation expands the community beyond Hermes users. This phase also improves the consumer experience with model metadata indexing.

**Delivers:** Power users can enable continuous mode. Contributors can annotate quality signals and choose scrub strictness. Non-Hermes tools can integrate. Consumers can filter the catalog by model metadata. The outbox handles high volume without performance degradation.

**Uses:**
- `APScheduler >=3.11.2,<4.0` for continuous mode background scheduling
- `watchdog >=6.0.0` (optional) for real-time staging directory monitoring

**Addresses:**
- Continuous mode via `APScheduler BackgroundScheduler` (differentiator #3)
- `kajiba rate` and `kajiba report` CLI annotation commands (differentiator #4)
- Configurable scrub strictness levels wired through pipeline (differentiator #5)
- Model-agnostic adapter protocol — ABC documentation, example `GenericAdapter`, entry_points spec (differentiator #8)
- Model metadata catalog index for consumer filtering (P1 feature, table stake #7)
- Outbox index / SQLite manifest to replace full-directory glob (TD-3)
- Contribution summary log for continuous mode (UP-3)
- `kajiba history` pagination

**Avoids:** UP-3 (silent continuous mode submissions), TD-3 (unbounded outbox directory)

### Phase 4: LLM Scrubbing + Community Scale

**Rationale:** LLM semantic scrubbing is the highest privacy value feature but requires an external runtime (Ollama) and significant prompt engineering. Deferring it until the pipeline is validated on real contributor data means the LLM pass can be tuned against actual session content rather than synthetic fixtures. Contribution stats, catalog browsing, and the HuggingFace migration belong here as they require a functioning dataset with meaningful record counts to be useful.

**Delivers:** Semantic PII detection catches names, project names, and company names that the Presidio NER layer misses. Consumers have a first-class CLI catalog experience. The dataset is accessible via HuggingFace for broader distribution.

**Uses:**
- `ollama >=0.6.1` for LLM-based semantic scrubbing
- `presidio-analyzer` Pass 2 already in place from Phase 1; Pass 3 (Ollama) added here
- `huggingface_hub >=0.19` for HuggingFace upload (already in pyproject.toml extras)

**Addresses:**
- LLM semantic PII scrubbing — Ollama Pass 3, structured prompt, auto-redact + flag for review (differentiator #2, CP-1 full resolution)
- Model metadata via Ollama `/api/show` at session capture time
- `kajiba browse` and `kajiba download` CLI catalog commands (differentiator #6)
- Contribution statistics (`kajiba stats --global`) (differentiator #7)
- HuggingFace upload command
- Git repo size migration trigger at 2 GB
- Croissant JSON-LD dataset metadata (v2+ consideration)

**Avoids:** CP-1 (regex-only scrubbing passes semantic PII — full resolution)

---

### Phase Ordering Rationale

- **Privacy before publishing:** Phases 1 and 2 are strictly ordered. The pitfalls research identifies three CRITICAL privacy violations in the current codebase that must be resolved before any record is published. Reversing the order means publishing data that has known consent and fingerprinting issues — a trust breach that is very difficult to recover from.
- **Infrastructure before experience:** Phase 2 before Phase 3 because continuous mode, annotation, and the model-agnostic protocol all require the publishing infrastructure (ContributionManager, Publisher, catalog) to be in place first.
- **Validate on real data before LLM scrubbing:** Phase 3 before Phase 4 because the LLM scrubber prompt engineering is best tuned against real contributor sessions, not fixtures. Also, Ollama dependency is optional — the pipeline should be fully functional without it.
- **Feature groupings follow architectural dependencies:** Phase 1 is all pure pipeline transforms (no new external dependencies). Phase 2 introduces GitPython, pydantic-settings, filelock. Phase 3 introduces APScheduler. Phase 4 introduces Ollama. Dependency introduction is staged to keep each phase testable in isolation.
- **Anti-features are enforced throughout:** Fine-tuning tooling, hosted services, and model evaluation are out of scope at all phases per the features research. No phase should expand toward these.

### Research Flags

Phases likely needing deeper `/gsd:research-phase` during planning:

- **Phase 2 (Dataset Repo):** The PR-based contribution model design (how contributors submit — fork + PR vs direct push + review queue) needs a concrete workflow decision. The catalog conflict resolution strategy (when two contributors push simultaneously) needs design. The sharding threshold (50 MB vs 10K records) should be validated against expected JSONL record sizes.
- **Phase 4 (LLM Scrubbing):** Prompt engineering for the Ollama semantic PII pass needs iteration against real session data. The confidence threshold design (what triggers auto-redact vs flag-for-review) is not specified in the research and needs empirical tuning. Presidio false positive rate on non-name entities (Anonym.legal reports 22.7% precision on person names) may require custom recognizer tuning.

Phases with standard patterns (skip research-phase):

- **Phase 1 (Privacy Foundation):** All patterns are well-documented. Presidio + spaCy usage, pydantic-settings configuration, consent field stripping logic — all established. The work is implementation of specified behavior, not research.
- **Phase 3 (Contributor Experience):** APScheduler BackgroundScheduler pattern is well-documented and the STACK.md provides the exact implementation pattern. CLI annotation commands follow the existing Click command structure.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All core libraries verified on PyPI at specific versions. Version compatibility confirmed. APScheduler 4.x alpha warning is a concrete, verified concern. |
| Features | MEDIUM-HIGH | Table stakes and P0 features derived from real community dataset precedents (BigCode, HuggingFace, MLCommons Croissant). Differentiators are well-reasoned extrapolations from community dataset gaps. A few future features (leaderboard, Croissant JSON-LD) are speculative. |
| Architecture | MEDIUM-HIGH | Component boundaries and data flow patterns are consistent with real-world data pipeline architecture (LLaMA-Factory, HuggingFace dataset structure). The 10-step build order is derived from hard dependency analysis. Anti-patterns are drawn from documented failure modes in comparable projects. |
| Pitfalls | HIGH | Critical pitfalls are corroborated by both external research (USENIX, ICLR, NIST) and CONCERNS.md codebase evidence. CP-2 and CP-3 are confirmed present in the current codebase, not theoretical. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **Contribution submission UX design:** The exact user-facing flow for the PR-based contribution model is not specified. Does `kajiba publish` open a PR automatically? Does it require the contributor to have forked the dataset repo? This workflow needs a concrete decision before Phase 2 planning.
- **Presidio false positive tuning:** The research cites a 22.7% false positive rate for Presidio on person names in general text. For technical coding sessions (where many "names" are identifiers, library names, or function names), this may be higher. Empirical testing against real session data is needed before the Presidio pass is wired into the default pipeline.
- **Outbox → dataset repo record lifecycle:** The exact moment consent stripping occurs (at `kajiba submit` vs at `kajiba publish`) has implications for what is stored locally in the outbox. The architecture shows `ConsentEnforcer.apply()` running before Publisher, which means stripped records in the dataset repo but potentially full records in the local outbox. Whether full records are retained locally after publish is a policy decision that needs explicit documentation.
- **Ollama availability detection:** Phase 3 and 4 features (continuous mode optional watchdog, LLM scrubbing) depend on Ollama being locally installed and running. The graceful degradation path when Ollama is absent needs explicit design — the pipeline must not silently degrade in ways that mislead contributors about their privacy protection level.

---

## Sources

### Primary (HIGH confidence)
- `D:/Kajiba/.planning/research/STACK.md` — full technology selection with version verification
- `D:/Kajiba/.planning/research/FEATURES.md` — feature landscape, MVP definition, prioritization matrix
- `D:/Kajiba/.planning/research/ARCHITECTURE.md` — component design, patterns, build order, anti-patterns
- `D:/Kajiba/.planning/research/PITFALLS.md` — critical/moderate/minor pitfall analysis with codebase evidence
- `D:/Kajiba/.planning/PROJECT.md` — requirements, constraints, and key decisions
- [Microsoft Presidio documentation](https://microsoft.github.io/presidio/) — PII detection architecture
- [ollama/ollama-python GitHub](https://github.com/ollama/ollama-python) — official first-party client API
- [APScheduler PyPI](https://pypi.org/project/APScheduler/) — version 3.11.2 confirmed
- [pydantic-settings PyPI](https://pypi.org/project/pydantic-settings/) — version 2.13.1 confirmed
- [BigCode Governance Card](https://arxiv.org/html/2312.03872v1) — community dataset trust patterns
- [HuggingFace Dataset Cards Documentation](https://huggingface.co/docs/hub/en/datasets-cards) — dataset metadata standards
- ICLR 2025: Persistent Pre-Training Poisoning of LLMs — dataset poisoning attack surface
- NIST AI 100-2e 2025: Adversarial Machine Learning Taxonomy — adversarial ML threat taxonomy
- D:/Kajiba/.planning/codebase/CONCERNS.md — codebase-specific pitfall evidence (consent, metadata, regex gaps)

### Secondary (MEDIUM confidence)
- [Mozilla Foundation: Best Practices for Open Datasets for LLM Training](https://www.mozillafoundation.org/en/research/library/towards-best-practices-for-open-datasets-for-llm-training/) — contributor consent governance norms
- [MLCommons Croissant Specification](https://docs.mlcommons.org/croissant/docs/croissant-spec.html) — dataset metadata standard
- [LLaMA-Factory data/README.md](https://raw.githubusercontent.com/hiyouga/LLaMA-Factory/main/data/README.md) — real-world dataset catalog format
- [Python Packaging: Creating and discovering plugins](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/) — entry_points vs dict registry tradeoffs
- [DataFlow: LLM-Driven Framework](https://arxiv.org/html/2512.16676v1) — multi-source data pipeline architecture patterns
- [Anonym.legal: Presidio false positive rate on person names](https://anonym.legal/blog/presidio-false-positive-legal-healthcare-cost-2024) — Presidio precision limitations
- [Lakera: Introduction to Data Poisoning](https://www.lakera.ai/blog/training-data-poisoning) — dataset poisoning mechanics
- [Open Trusted Data Initiative Dataset Specification](https://the-ai-alliance.github.io/open-trusted-data-initiative/dataset-requirements/) — governance and license requirements

### Tertiary (LOW confidence)
- [Datasets Should Behave Like Git Repositories](https://towardsdatascience.com/datasets-should-behave-like-git-repositories-9acb83a0dae5/) — append-only dataset discipline principles (opinion article, sound principles)
- [APScheduler vs schedule comparison](https://leapcell.io/blog/scheduling-tasks-in-python-apscheduler-versus-schedule) — scheduler selection rationale
- [llama.cpp vs Ollama tradeoffs (2026)](https://www.openxcell.com/blog/llama-cpp-vs-ollama/) — LLM runtime selection tradeoffs

---
*Research completed: 2026-03-30*
*Ready for roadmap: yes*
