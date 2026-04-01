# Phase 5: Consumer Experience - Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver `kajiba browse` and `kajiba download` CLI commands that let fine-tuners discover and fetch filtered subsets of the published dataset catalog. Enrich `catalog.json` with model metadata (parameter count, quantization, context window) at publish time so consumers can make informed subset selections. After this phase, the full contributor-to-consumer loop is closed.

</domain>

<decisions>
## Implementation Decisions

### Browse Display
- **D-01:** Summary table at top level. Rich table with one row per model showing name, per-tier record counts, total records, and average quality score. Footer shows total models and records with hint to use `--model <name>` for details.
- **D-02:** Drill-down via `--model` flag. `kajiba browse --model llama-3` shows model metadata panel (parameter count, quantization, context window) plus tier breakdown table with records, avg score, and size. Hardware distribution shown as a summary line.
- **D-03:** Browse accepts same filter flags as download (`--model`, `--tier`). Filtered browse narrows the table to matching entries. Consistent flag surface between browse and download.
- **D-04:** Helpful empty/error states. Empty catalog: "No records published yet. Run `kajiba publish` to contribute." Network error: show error message + suggest checking `gh auth status`. No filter matches: list available models and tiers.

### Download Mechanics
- **D-05:** Fetch from upstream repo via `gh api`. Read `catalog.json` from the configured dataset repo (default: CuervoDoesIt/kajiba-dataset), apply filters, then download matching shard files. No fork needed for read-only consumer access. Consistent with Phase 3's gh-only approach.
- **D-06:** Default output to `~/.hermes/kajiba/downloads/{model}/{tier}/`. Allow `--output <path>` flag to override. Preserves model/tier directory structure in output.
- **D-07:** Rich progress bar during download. Show shard count and bytes fetched. Completion summary with shard count, record count, and total size.

### Missing Metadata Handling
- **D-08:** Show available metadata, dim missing fields with "---". Catalog aggregates what's available across ALL records for a model --- if ANY record has parameter_count, show it. Missing fields displayed as dim dash in browse output.
- **D-09:** Catalog enrichment at publish time. Extend `generate_catalog()` in publisher.py to extract `parameter_count`, `quantization`, and `context_window` from records and aggregate as lists of unique values per model. Browse reads pre-computed catalog --- no extra network calls.

### Filter Composition
- **D-10:** AND between flags, single value per flag. `--model llama-3 --tier gold` = records matching BOTH. Simple, predictable, consistent with typical CLI patterns.
- **D-11:** No-match feedback. When filters match nothing, show which filter failed and list available options (models, tiers). Same pattern as `config set` validation.
- **D-12:** Unfiltered download requires confirmation. Show total records and estimated size from catalog, prompt "Continue? [y/N]". Prevents accidental full-dataset downloads.

### Claude's Discretion
- Exact Rich table styling and column widths for browse output
- Download caching or skip-if-exists behavior for re-downloads
- Whether `--hardware` filter flag is worth adding (hardware distribution is in catalog but not in requirements)
- Deletion filtering during download (whether to auto-exclude deleted record IDs)
- Dry-run mode for download (`--dry-run` to show what would be fetched without downloading)
- Dataset repo URL configuration (hardcoded default vs `kajiba config set dataset_repo`)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Implementation
- `src/kajiba/publisher.py` --- `generate_catalog()` at line 426 produces catalog.json with models, tiers, record counts, hardware distribution, shard lists. Extension point for CONS-02 metadata enrichment.
- `src/kajiba/publisher.py` --- `generate_readme()` at line 577 already references browse and download commands in usage examples.
- `src/kajiba/cli.py` --- Current CLI commands. Extension point for `browse` and `download` commands. Contains `console = Console()` Rich rendering and all Click command patterns.
- `src/kajiba/schema.py` --- `ModelMetadata` model with `parameter_count`, `quantization`, `context_window` Optional fields (line 160-164). Source for catalog enrichment.
- `src/kajiba/config.py` --- `VALID_CONFIG_KEYS` includes `dataset_repo` key with default `CuervoDoesIt/kajiba-dataset`. Source for download target.

### Publishing Infrastructure (Phase 3 outputs)
- `.planning/phases/03-dataset-publishing/03-CONTEXT.md` --- D-02: GitHub via `gh` CLI only. D-05: sharded JSONL under `data/{model}/{tier}/`. D-07: Rich catalog metadata designed for Phase 5 consumption.
- `src/kajiba/publisher.py` --- `GhResult` dataclass and `_gh_run()` helper for `gh` CLI calls. Reuse for browse/download GitHub operations.

### Spec
- `docs/kajiba-project-spec.md` --- Full project specification including schema definitions.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `generate_catalog()` in `publisher.py` --- Already produces the data structure browse needs. Extend with model metadata fields for CONS-02.
- `_gh_run()` / `GhResult` in `publisher.py` --- Wrapper for `gh` CLI subprocess calls with error handling. Reuse for `gh api` calls in browse/download.
- `VALID_CONFIG_KEYS["dataset_repo"]` in `config.py` --- Already configured with default repo URL.
- `_load_config_value()` in `config.py` --- Read dataset_repo from user config.
- Rich `Table`, `Panel`, `Progress` from `rich` --- Already imported and used extensively in cli.py.
- `_ensure_dirs()` in `cli.py` --- Creates Kajiba base directories. Extend for downloads directory.

### Established Patterns
- Click commands with Rich output registered under `@cli.command()` / `@cli.group()`.
- `subprocess.run()` for external CLI calls (nvidia-smi, gh).
- `json.loads()` / `json.dumps()` for record serialization throughout.
- Helpful error messages with available options (config set validation pattern from Phase 4).

### Integration Points
- New `browse` and `download` commands register under existing Click group in `cli.py`.
- `generate_catalog()` in `publisher.py` needs extension for model metadata aggregation.
- Downloads directory `~/.hermes/kajiba/downloads/` is new --- needs creation logic.
- `catalog.json` is the bridge: published by contributor, consumed by fine-tuner.

</code_context>

<specifics>
## Specific Ideas

- The browse-then-download workflow mirrors `browse` as preview and `download` as action --- same pattern as `preview` then `submit`.
- `dataset_repo` config key already exists in VALID_CONFIG_KEYS, so users can point browse/download at any compatible dataset repo.
- Progress bar during download is important for UX since network operations are the first time Kajiba makes users wait (core pipeline is local-first).
- Confirmation before unfiltered download prevents surprises as the dataset grows.

</specifics>

<deferred>
## Deferred Ideas

None --- discussion stayed within phase scope.

</deferred>

---

*Phase: 05-consumer-experience*
*Context gathered: 2026-04-01*
