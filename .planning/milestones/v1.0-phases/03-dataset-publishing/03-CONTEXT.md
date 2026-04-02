# Phase 3: Dataset Publishing - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the GitHub dataset repository infrastructure: PR-based contribution workflow via fork, structured JSONL storage organized by model/tier, catalog index, auto-generated dataset card, and deletion mechanism. First phase with external network operations (GitHub API via gh CLI). After this phase, contributors can publish scrubbed records and request deletions.

</domain>

<decisions>
## Implementation Decisions

### PR Workflow Mechanics
- **D-01:** Fork + PR model. User forks the dataset repo. `kajiba publish` clones their fork, adds records, pushes to fork, opens PR to upstream via `gh pr create`. Standard open-source contribution flow.
- **D-02:** GitHub authentication via `gh` CLI only. Require `gh` installed and authenticated (`gh auth login`). No token management in Kajiba. All GitHub operations use `gh api` / `gh pr create`.
- **D-03:** Consent re-verification at publish time. Before writing records to the PR, re-run `apply_consent_level()` on each record. Belt-and-suspenders per Phase 1 D-01. Even manually-placed outbox records get stripped.
- **D-04:** `kajiba publish` workflow: check gh auth → clone/update fork → re-verify consent → write records to `{model}/{tier}/` directories → update catalog.json → regenerate README.md → commit → push → open PR.

### Repository Structure
- **D-05:** Records stored as sharded JSONL files under `data/{model}/{tier}/` directories. Model names normalized to lowercase + hyphens (e.g., "GPT-4o" → "gpt-4o", "Claude 3.5 Sonnet" → "claude-3-5-sonnet").
- **D-06:** Sharding strategy is Claude's discretion. Goal: keep files manageable for git (avoid single files > 50MB), deterministic shard assignment, easy merge of new data with existing shards.

### Catalog & Dataset Card
- **D-07:** Rich metadata in `catalog.json`: model name, tier, record count, average quality score, hardware distribution, file sizes, shard list, last updated timestamp. Enough for Phase 5 consumer browse/download commands.
- **D-08:** Dataset README.md uses a static template with dynamic stats sections. Template includes License (Apache 2.0), Scrubbing Methods, How to Use prose. Dynamic sections include model coverage table, quality distribution chart, total record counts. Regenerated on each publish.

### Deletion Mechanism
- **D-09:** Deletion via index file, not physical removal. `kajiba delete <record_id>` appends the ID to `deletions.jsonl` in the dataset repo via PR. Records are NOT physically removed from data shards. Consumers filter out deleted IDs when loading.
- **D-10:** Deletion scope is Claude's discretion. Goal: privacy-friendly, minimal abuse surface. Recommend allowing any record by ID (no identity tracking required).

### Claude's Discretion
- Sharding strategy details (date-based, size-based, or hybrid)
- Deletion scope (any record by ID vs contributor-verified)
- Fork detection and setup flow (what if user hasn't forked yet?)
- PR title/body template content
- Catalog.json schema details (exact field names and types)
- Error handling for network failures during publish

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Implementation
- `src/kajiba/cli.py` — Current CLI commands. Extension point for `publish` and `delete` commands. Contains `_load_all_staging()`, `_save_staged_record()` helpers from Phase 2.
- `src/kajiba/schema.py` — `KajibaRecord` model with `QualityMetadata`, `SubmissionMetadata` (consent_level field), `ModelMetadata` (model_name field for directory naming).
- `src/kajiba/privacy.py` — `apply_consent_level()` for re-verification at publish time.
- `src/kajiba/scrubber.py` — `scrub_record()` for the scrub pipeline.

### Privacy (Phase 1 outputs)
- `.planning/phases/01-privacy-foundation/01-CONTEXT.md` — D-01: consent at both submit and publish. The publish command MUST re-verify.

### Quality (Phase 2 outputs)
- `src/kajiba/schema.py` — `QualityMetadata` model with `quality_tier` field used for directory organization.

### Spec
- `docs/kajiba-project-spec.md` — Dataset publishing spec sections if present.

### Codebase Analysis
- `.planning/codebase/CONCERNS.md` — Gap analysis.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `huggingface_hub>=0.19` declared as `[upload]` extra in `pyproject.toml` — not used yet but shows the path for future HuggingFace integration.
- `KajibaRecord.model_dump(mode="json", by_alias=True)` — standard serialization for JSONL output.
- `_load_all_staging()` and outbox loading patterns in `cli.py` — patterns for loading records from disk.
- `QualityMetadata.quality_tier` — already stored, ready for directory organization.
- `ModelMetadata.model_name` — source for directory naming.
- `SubmissionMetadata.consent_level` — source for consent re-verification.

### Established Patterns
- Click CLI commands with Rich output. New `publish` and `delete` commands follow same pattern.
- `subprocess.run()` already used in `collector.py` for `nvidia-smi` — same pattern for `gh` CLI calls.
- Pure function pattern: functions take data in, return data out, don't mutate input.

### Integration Points
- New commands register under the existing Click group in `cli.py`.
- Outbox records at `~/.hermes/kajiba/outbox/` are the source for publishing.
- No existing GitHub integration code — this is new infrastructure.

</code_context>

<specifics>
## Specific Ideas

- The `gh` CLI dependency keeps Kajiba's core dependency-free while enabling GitHub operations. Users who don't want to publish can use Kajiba without `gh`.
- Re-verification at publish is critical — it's the last checkpoint before data leaves the contributor's machine.
- The fork + PR model means Kajiba never needs write access to the upstream dataset repo. Only the fork needs push access (which `gh` handles automatically).
- Catalog.json serves double duty: Phase 5 consumer commands will read it for browse/download, and it's human-readable for anyone exploring the repo.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-dataset-publishing*
*Context gathered: 2026-03-31*
