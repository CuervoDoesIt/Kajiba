# Roadmap: Kajiba

## Overview

Kajiba moves from a working but trust-incomplete MVP to a community-ready data pipeline in five phases. The first two phases close active privacy violations and build the quality transparency layer that earns contributor trust. The third phase creates the publishing infrastructure that gives trustworthy records somewhere to go. The fourth phase adds configurable contribution modes that match different contributors' workflows. The fifth phase delivers the consumer-facing catalog experience that closes the loop between contributors and fine-tuners.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Privacy Foundation** - Close active consent and fingerprinting violations before any data leaves the machine
- [ ] **Phase 2: Data Quality & Transparency** - Store quality scores in records, surface scrub diffs, add annotation commands
- [ ] **Phase 3: Dataset Publishing** - Build the GitHub dataset repo, catalog, PR workflow, deletion mechanism, and publish command
- [ ] **Phase 4: Contribution Modes** - Add ad-hoc review gate and continuous auto-submit with configurable parameters
- [ ] **Phase 5: Consumer Experience** - Deliver catalog browse and download commands for fine-tuners

## Phase Details

### Phase 1: Privacy Foundation
**Goal**: Contributors can export records knowing their consent choice is actually enforced and their hardware profile cannot fingerprint them
**Depends on**: Nothing (first phase)
**Requirements**: PRIV-01, PRIV-02, PRIV-03, PRIV-04, PRIV-05, PRIV-06
**Success Criteria** (what must be TRUE):
  1. A user who sets consent level to `anonymous` gets a record with trajectory-only fields — all hardware, model, and metadata fields are absent from the exported file
  2. A user running `kajiba preview` sees redacted hardware shown as GPU family (e.g., "NVIDIA RTX 30xx") not exact model, rounded RAM tiers, and no OS version
  3. A user running `kajiba preview` on a record containing a version string like `Python 3.11.0.0` sees it preserved — not redacted as an IP address
  4. A record containing `token=abc123def456...` (40 hex chars with context keyword) has the token scrubbed before export
  5. A record containing an org domain like `acme.io` shows a flagged-for-review warning rather than being silently auto-redacted or silently passed through
**Plans:** 3 plans

Plans:
- [x] 01-01-PLAN.md — Fix IP regex, add hex token scrubbing, add org domain flagging with safe-domain allowlist
- [x] 01-02-PLAN.md — Create privacy module with consent enforcement, hardware anonymization, and timestamp jitter
- [x] 01-03-PLAN.md — Wire privacy pipeline into CLI commands and collector, add flagged warning display

### Phase 2: Data Quality & Transparency
**Goal**: Contributors can see exactly what gets redacted and annotate quality signals before records enter the outbox
**Depends on**: Phase 1
**Requirements**: QUAL-01, QUAL-02, QUAL-03, QUAL-04, QUAL-05
**Success Criteria** (what must be TRUE):
  1. A record written to the outbox contains `quality_tier` and `composite_score` fields — `kajiba history` reads the stored value instead of recomputing it
  2. Running `kajiba preview` shows original text alongside scrubbed output with redactions highlighted, so the contributor can see what was removed
  3. A user can run `kajiba rate` on a staged record, provide a numeric score and optional tags, and those values appear in the exported record's annotation fields
  4. A user can run `kajiba report` on a staged record to attach a pain point with category, description, and severity, and those values appear in the exported record
  5. When a record is exported, user ratings and pain points appear alongside the auto-computed quality scores
**Plans:** 3 plans

Plans:
- [x] 02-01-PLAN.md — Add QualityMetadata model, persist quality at submit/export, update history/stats to read stored quality
- [x] 02-02-PLAN.md — Enhance preview with redaction summary table and --detail inline highlighting
- [x] 02-03-PLAN.md — Add rate and report CLI commands, merged quality panel, annotation visibility

### Phase 3: Dataset Publishing
**Goal**: Contributors can publish scrubbed records to a structured GitHub dataset repository via a safe PR-based workflow, and can request deletion of records they previously contributed
**Depends on**: Phase 1
**Requirements**: PRIV-07, PRIV-08, PUB-01, PUB-02, PUB-03, PUB-04, PUB-05
**Success Criteria** (what must be TRUE):
  1. Running `kajiba publish` pushes scrubbed outbox records to the dataset repository as sharded JSONL files organized under `{model}/{tier}/` directories via a pull request (not direct push)
  2. After publishing, `catalog.json` in the dataset repository is updated with current models, tiers, record counts, and metadata
  3. The dataset repository contains an auto-generated `README.md` that describes the dataset's license, scrubbing methods, quality distribution, and model coverage
  4. Running `kajiba delete <record_id>` creates or updates a deletion index file in the dataset repository recording the deletion request
  5. A contributor reviewing a PR to the dataset repository can confirm that no record was pushed without consent-enforcement having been applied
**Plans:** 2 plans

Plans:
- [x] 03-01-PLAN.md — Create publisher.py module with file layout, sharding, catalog, README, deletion, and GitHubOps wrapper
- [x] 03-02-PLAN.md — Add publish and delete CLI commands with full PR workflow and integration tests

### Phase 4: Contribution Modes
**Goal**: Contributors can choose between reviewing each record manually or running a background mode that auto-submits records above a quality threshold
**Depends on**: Phase 3
**Requirements**: CONT-01, CONT-02, CONT-03, CONT-04
**Success Criteria** (what must be TRUE):
  1. In ad-hoc mode, each record captured requires explicit user review and approval in the CLI before it is submitted to the outbox
  2. In continuous mode, records that meet the configured quality threshold are automatically submitted to the outbox without per-record interaction
  3. A user can switch between ad-hoc and continuous modes by running `kajiba config` with no restart required
  4. Continuous mode minimum quality tier, consent level, and auto-submit interval are all configurable via `kajiba config`
**Plans:** 3 plans

Plans:
- [x] 04-01-PLAN.md — Create config.py module with shared helpers, restructure config command to set/get/show subcommands
- [x] 04-02-PLAN.md — Add kajiba review command with one-at-a-time approve/reject/skip flow and activity notifications
- [x] 04-03-PLAN.md — Extend collector on_session_end for continuous mode auto-submit with quality threshold

### Phase 5: Consumer Experience
**Goal**: Fine-tuners can browse the published dataset catalog and download filtered subsets without leaving the CLI
**Depends on**: Phase 3
**Requirements**: CONS-01, CONS-02, CONS-03, CONS-04
**Success Criteria** (what must be TRUE):
  1. The dataset repository is organized by quality tier so a consumer can download only gold or silver records without downloading the full dataset
  2. The catalog index includes model family, parameter count, quantization type, and context window for each record set, enabling informed subset selection
  3. Running `kajiba browse` shows available models, tiers, and hardware profiles with filter options
  4. Running `kajiba download --model llama3 --tier gold` fetches only the matching subset to a local directory
**Plans:** 2 plans

Plans:
- [ ] 05-01-PLAN.md — Extend generate_catalog() with model metadata enrichment, add GitHubOps read methods and filter_catalog() function
- [ ] 05-02-PLAN.md — Add kajiba browse and kajiba download CLI commands with Rich rendering and progress bar

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Privacy Foundation | 3/3 | Complete | 2026-03-31 |
| 2. Data Quality & Transparency | 0/3 | Planning complete | - |
| 3. Dataset Publishing | 0/2 | Planning complete | - |
| 4. Contribution Modes | 0/3 | Planning complete | - |
| 5. Consumer Experience | 0/2 | Planning complete | - |
