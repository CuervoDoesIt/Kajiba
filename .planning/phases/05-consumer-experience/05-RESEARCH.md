# Phase 5: Consumer Experience - Research

**Researched:** 2026-04-01
**Domain:** CLI commands for dataset browsing and downloading via GitHub API
**Confidence:** HIGH

## Summary

Phase 5 closes the contributor-to-consumer loop by adding `kajiba browse` and `kajiba download` CLI commands. The consumer reads `catalog.json` from the configured dataset repository via `gh api`, applies filters (model, tier), and either displays a Rich table (browse) or fetches matching JSONL shard files to a local directory (download). The catalog must be enriched at publish time with `parameter_count`, `quantization`, and `context_window` from `ModelMetadata`.

All infrastructure for this phase already exists. The `GitHubOps` class in `publisher.py` wraps `gh` CLI calls behind a `GhResult` interface. The `generate_catalog()` function already produces per-model/per-tier statistics. The `config.py` module already has `dataset_repo` as a valid config key. The `cli.py` module already uses Rich `Table`, `Panel`, and `Console` for output. The work is (1) extend `generate_catalog()` to include model metadata, (2) add read-only `gh api` methods to `GitHubOps`, (3) build `browse` and `download` Click commands, and (4) add the `~/.hermes/kajiba/downloads/` directory to the filesystem layout.

**Primary recommendation:** Build a `DatasetClient` helper (or extend `GitHubOps`) with `fetch_catalog()` and `download_shard()` methods that use `gh api` for read-only access. The browse command formats catalog data with Rich tables. The download command iterates matching shards and writes them to disk with a Rich progress bar. No new dependencies required.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Summary table at top level. Rich table with one row per model showing name, per-tier record counts, total records, and average quality score. Footer shows total models and records with hint to use `--model <name>` for details.
- **D-02:** Drill-down via `--model` flag. `kajiba browse --model llama-3` shows model metadata panel (parameter count, quantization, context window) plus tier breakdown table with records, avg score, and size. Hardware distribution shown as a summary line.
- **D-03:** Browse accepts same filter flags as download (`--model`, `--tier`). Filtered browse narrows the table to matching entries. Consistent flag surface between browse and download.
- **D-04:** Helpful empty/error states. Empty catalog: "No records published yet. Run `kajiba publish` to contribute." Network error: show error message + suggest checking `gh auth status`. No filter matches: list available models and tiers.
- **D-05:** Fetch from upstream repo via `gh api`. Read `catalog.json` from the configured dataset repo (default: CuervoDoesIt/kajiba-dataset), apply filters, then download matching shard files. No fork needed for read-only consumer access. Consistent with Phase 3's gh-only approach.
- **D-06:** Default output to `~/.hermes/kajiba/downloads/{model}/{tier}/`. Allow `--output <path>` flag to override. Preserves model/tier directory structure in output.
- **D-07:** Rich progress bar during download. Show shard count and bytes fetched. Completion summary with shard count, record count, and total size.
- **D-08:** Show available metadata, dim missing fields with "---". Catalog aggregates what's available across ALL records for a model -- if ANY record has parameter_count, show it. Missing fields displayed as dim dash in browse output.
- **D-09:** Catalog enrichment at publish time. Extend `generate_catalog()` in publisher.py to extract `parameter_count`, `quantization`, and `context_window` from records and aggregate as lists of unique values per model. Browse reads pre-computed catalog -- no extra network calls.
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

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CONS-01 | Dataset repository is organized by quality tier so consumers can download subsets by tier | Already done by Phase 3 (`data/{model}/{tier}/` structure). Catalog `tiers` dict provides the index. Download filters on `tier` key. |
| CONS-02 | Catalog index includes model family, parameter count, quantization type, and context window for each record set | Extend `generate_catalog()` to aggregate `parameter_count`, `quantization`, `context_window` from `ModelMetadata` in records. Schema already has these Optional fields. |
| CONS-03 | User can browse the dataset catalog via `kajiba browse` with filters for model, tier, and hardware | New Click command reads catalog.json via `gh api`, applies filters, renders Rich tables per D-01/D-02/D-03. |
| CONS-04 | User can download a filtered subset of the dataset via `kajiba download` with model/tier/hardware filters | New Click command reads catalog for shard list, downloads each matching shard via `gh api` raw content, writes to `~/.hermes/kajiba/downloads/`. |

</phase_requirements>

## Standard Stack

### Core

No new dependencies. All required libraries are already in the project.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| click | 8.3.1 (installed) | CLI command framework | Already used for all existing commands |
| rich | 14.3.3 (installed) | Table, Panel, Progress bar rendering | Already used for all CLI output |
| subprocess | stdlib | `gh api` calls via GitHubOps wrapper | Already established pattern in publisher.py |
| json | stdlib | Parse catalog.json, JSONL shard files | Used throughout the codebase |
| pathlib | stdlib | File system operations for downloads directory | Used throughout the codebase |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| rich.progress (Progress, DownloadColumn, BarColumn, etc.) | 14.3.3 | Download progress tracking | During `kajiba download` shard fetching |
| rich.text (Text) | 14.3.3 | Dim styling for missing metadata fields | Browse output when metadata is "---" |

### Alternatives Considered

None -- no new dependencies needed. The existing stack covers all requirements.

## Architecture Patterns

### Recommended Project Structure

No new files needed beyond extending existing ones:

```
src/kajiba/
    cli.py           # Add browse and download commands
    publisher.py     # Extend generate_catalog() for model metadata; add read-only gh api methods to GitHubOps
    config.py        # Already has dataset_repo key -- no changes needed
tests/
    test_cli.py      # Add browse and download command tests
    test_publisher.py # Add catalog enrichment and GitHubOps read method tests
```

### Pattern 1: Read-Only GitHubOps Methods

**What:** Add `get_file_contents()` and `get_directory_listing()` methods to the existing `GitHubOps` class in publisher.py. These use `gh api` with appropriate Accept headers for read-only access to the dataset repo. No fork required (reads from upstream directly per D-05).

**When to use:** Browse (read catalog.json) and download (read shard files).

**Example:**
```python
# In publisher.py GitHubOps class

def get_file_contents(self, path: str, raw: bool = False) -> GhResult:
    """Fetch a file's contents from the upstream repo.

    Args:
        path: File path within the repo (e.g. "catalog.json").
        raw: If True, return raw file content instead of JSON.

    Returns:
        GhResult with file contents in stdout.
    """
    args = ["api", f"repos/{self._upstream}/contents/{path}"]
    if raw:
        args = [
            "api",
            "-H", "Accept: application/vnd.github.raw+text",
            f"repos/{self._upstream}/contents/{path}",
        ]
    return self._run_gh(args)
```

**Why this pattern:** Consistent with existing GitHubOps wrapper. Testable via GhResult mocking (same pattern as test_publisher.py). Reuses `_run_gh()` subprocess isolation.

### Pattern 2: Shared Filter Options via Decorator

**What:** Define a `filter_options` decorator that applies `--model`, `--tier` Click options to both `browse` and `download` commands. Per D-03, both commands share the same filter surface.

**When to use:** When registering browse and download commands.

**Example:**
```python
# In cli.py

def filter_options(func):
    """Shared filter options for browse and download commands."""
    func = click.option(
        "--model", default=None,
        help="Filter by model name (e.g. llama-3, gpt-4o).",
    )(func)
    func = click.option(
        "--tier", default=None,
        type=click.Choice(["gold", "silver", "bronze", "review_needed"]),
        help="Filter by quality tier.",
    )(func)
    return func

@cli.command()
@filter_options
@click.option("--repo", default=None, help="Dataset repo (owner/repo).")
def browse(model, tier, repo):
    """Browse the dataset catalog."""
    ...

@cli.command()
@filter_options
@click.option("--output", default=None, type=click.Path(), help="Output directory.")
@click.option("--repo", default=None, help="Dataset repo (owner/repo).")
def download(model, tier, output, repo):
    """Download a filtered subset of the dataset."""
    ...
```

**Why this pattern:** Enforces D-03 (consistent flag surface). Uses standard Click option reuse pattern. Avoids duplicating option definitions.

### Pattern 3: Catalog Filter + Match Function

**What:** Pure function that takes catalog dict and filter criteria, returns matching models/tiers/shards. Separates filtering logic from I/O and rendering.

**When to use:** Both browse (to filter what is displayed) and download (to determine which shards to fetch).

**Example:**
```python
def filter_catalog(
    catalog: dict,
    model: Optional[str] = None,
    tier: Optional[str] = None,
) -> dict:
    """Filter catalog to matching models and tiers.

    Args:
        catalog: Full catalog dict from catalog.json.
        model: Model slug to match (case-insensitive partial match).
        tier: Tier name to match exactly.

    Returns:
        Filtered catalog dict with same structure but only matching entries.
    """
    models = catalog.get("models", {})
    filtered_models = {}
    for slug, info in models.items():
        # Model filter: match slug or display_name (case-insensitive)
        if model:
            model_lower = model.lower()
            if model_lower not in slug and model_lower not in info.get("display_name", "").lower():
                continue
        # Tier filter: only include matching tier
        if tier:
            tiers = info.get("tiers", {})
            if tier not in tiers:
                continue
            info = {**info, "tiers": {tier: tiers[tier]}}
        filtered_models[slug] = info
    return {**catalog, "models": filtered_models}
```

**Why this pattern:** Testable without network I/O. Same function serves browse and download. Easy to extend with additional filters.

### Pattern 4: Rich Progress for Shard Downloads

**What:** Use `rich.progress.Progress` context manager with `DownloadColumn` for tracking shard downloads. Each shard gets a task. Total task tracks overall progress.

**When to use:** `kajiba download` shard fetching loop.

**Example:**
```python
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)

def _download_shards(
    gh_ops: GitHubOps,
    shards: list[dict],
    output_dir: Path,
) -> tuple[int, int, int]:
    """Download shard files with progress tracking.

    Returns:
        Tuple of (shards_downloaded, records_count, total_bytes).
    """
    total_bytes = 0
    total_records = 0

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.0f}%",
        DownloadColumn(),
        TimeRemainingColumn(),
    )

    with progress:
        task = progress.add_task("Downloading...", total=len(shards))
        for shard_info in shards:
            shard_path = shard_info["path"]
            result = gh_ops.get_file_contents(shard_path, raw=True)
            if result.success:
                dest = output_dir / Path(*shard_path.split("/"))
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(result.stdout, encoding="utf-8")
                total_bytes += len(result.stdout.encode("utf-8"))
                total_records += result.stdout.count("\n")
            progress.update(task, advance=1)

    return len(shards), total_records, total_bytes
```

### Pattern 5: Catalog Enrichment at Publish Time

**What:** Extend `generate_catalog()` in publisher.py to extract `parameter_count`, `quantization`, and `context_window` from `ModelMetadata` in each record and aggregate unique values per model.

**When to use:** When `kajiba publish` regenerates catalog.json.

**Example:**
```python
# Inside generate_catalog(), within the per-record loop:

# Model metadata for CONS-02
m = rec.get("model")
if m and isinstance(m, dict):
    pc = m.get("parameter_count")
    if pc:
        model_info.setdefault("parameter_counts", [])
        if pc not in model_info["parameter_counts"]:
            model_info["parameter_counts"].append(pc)
    qt = m.get("quantization")
    if qt:
        model_info.setdefault("quantizations", [])
        if qt not in model_info["quantizations"]:
            model_info["quantizations"].append(qt)
    cw = m.get("context_window")
    if cw:
        model_info.setdefault("context_windows", [])
        if cw not in model_info["context_windows"]:
            model_info["context_windows"].append(cw)
```

**Catalog enrichment output:**
```json
{
  "models": {
    "llama-3": {
      "display_name": "Llama 3",
      "parameter_counts": ["8B", "70B"],
      "quantizations": ["Q4_K_M", "Q8_0"],
      "context_windows": [8192, 131072],
      "tiers": { ... },
      "total_records": 42,
      "hardware_distribution": { ... }
    }
  }
}
```

### Anti-Patterns to Avoid

- **Cloning the dataset repo for browse:** Never clone or fetch git history for read-only operations. Use `gh api` to read individual files. The dataset repo could grow very large; consumers should not need a local clone.
- **Hardcoding the dataset repo URL:** Use `_load_config_value("dataset_repo", DEFAULT_DATASET_REPO)` so users can point at alternative dataset repos.
- **Parsing JSONL during browse:** Browse should only read catalog.json. Never download shard files just to display metadata. The catalog is the pre-computed index.
- **Using `urllib` or `requests` for downloads:** The project uses `gh` CLI exclusively for GitHub operations. Do not introduce HTTP libraries. The `gh` CLI handles authentication automatically.
- **Putting download logic in cli.py:** Keep network I/O and file writing in publisher.py (or a new dedicated module). CLI module should only handle Click commands and Rich rendering.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| GitHub API authentication | Token management, OAuth flow | `gh` CLI (already authenticated) | gh handles auth, tokens, 2FA transparently |
| Progress bar rendering | Custom terminal progress output | `rich.progress.Progress` with `DownloadColumn` | Rich already imported, handles terminal width, colors, cleanup |
| CLI option parsing | Manual argparse for filter flags | Click `@click.option` with shared decorator | Consistent with all existing commands |
| Table rendering | Custom ASCII tables for browse | `rich.table.Table` | Already used by history, stats, config commands |
| Config value lookup | Hardcoded defaults | `_load_config_value("dataset_repo", DEFAULT_DATASET_REPO)` | Already implemented in config.py |
| Model name matching | Regex model matching | Case-insensitive substring match on slug + display_name | Simple, predictable, covers 95% of use cases |

## Common Pitfalls

### Pitfall 1: GitHub API File Size Limit

**What goes wrong:** The GitHub Contents API returns empty content for files larger than 1 MB when using the default JSON response. JSONL shard files can exceed this.
**Why it happens:** GitHub API spec limits JSON-encoded content to 1 MB. Raw content works up to 100 MB.
**How to avoid:** Always use `Accept: application/vnd.github.raw+text` header for downloading shard files. The `get_file_contents(raw=True)` method must set this header.
**Warning signs:** Downloaded file content is empty or base64-encoded instead of raw JSONL.

### Pitfall 2: Catalog JSON vs Raw Content Header

**What goes wrong:** Using the raw Accept header for catalog.json returns a string that needs `json.loads()`. Using the default JSON header returns a GitHub API wrapper object with the content base64-encoded.
**How to avoid:** For catalog.json: use raw Accept header and `json.loads(result.stdout)`. For directory listings (if needed): use default Accept header. Be explicit about which header each method needs.
**Warning signs:** `json.loads()` fails on GitHub API metadata object, or catalog content is base64-encoded.

### Pitfall 3: gh CLI Not Installed

**What goes wrong:** Browse and download fail with unhelpful error if `gh` is not installed.
**Why it happens:** Unlike publish (which also needs gh), consumers may not have gh installed since they didn't contribute.
**How to avoid:** Check for gh availability as the first step in both commands. Show clear install instructions: "Install from https://cli.github.com/". This is already handled by `GhResult.returncode == -1` pattern from publisher.py.
**Warning signs:** `FileNotFoundError` exception on `subprocess.run(["gh", ...])`.

### Pitfall 4: Empty or Missing Catalog

**What goes wrong:** Browse/download fail when the dataset repo has no catalog.json (new repo, or catalog hasn't been generated yet).
**Why it happens:** Catalog is generated during `kajiba publish`. A brand-new dataset repo won't have one.
**How to avoid:** Check `GhResult.success` after fetching catalog.json. On failure, show D-04 message: "No records published yet. Run `kajiba publish` to contribute." Distinguish between "catalog not found" (404) and "network error" (other failures).
**Warning signs:** `gh api` returns non-zero exit code.

### Pitfall 5: Unfiltered Download Size Surprise

**What goes wrong:** User runs `kajiba download` without filters and downloads the entire dataset unexpectedly.
**Why it happens:** No safety check before starting a potentially large download.
**How to avoid:** D-12 requires confirmation for unfiltered downloads. Show total records and estimated size from catalog, prompt "Continue? [y/N]". Only skip confirmation when at least one filter is applied.
**Warning signs:** Large downloads without user awareness.

### Pitfall 6: subprocess.run Captures Entire Shard in Memory

**What goes wrong:** Very large shard files (tens of MB) are loaded entirely into `GhResult.stdout` string, consuming excessive memory.
**Why it happens:** `subprocess.run(capture_output=True)` reads all stdout into memory.
**How to avoid:** For Phase 5 v1, this is acceptable since individual JSONL shards are bounded by the sharding strategy (256 shards distributes records; no single shard should exceed several MB). If future scaling becomes an issue, switch to `subprocess.Popen` with streaming. Document this as a known limitation.
**Warning signs:** Memory usage spikes during download of large datasets.

### Pitfall 7: Cross-Platform Path Handling

**What goes wrong:** Shard paths from catalog use forward slashes (e.g., `data/gpt-4o/gold/shard_a3.jsonl`) but pathlib on Windows may not split correctly.
**Why it happens:** Phase 3 uses forward-slash paths for cross-platform compatibility in the repo, but download writes to local filesystem.
**How to avoid:** Use `Path(*path.split("/"))` to split the forward-slash path into platform-appropriate path components. This pattern is already used in `write_records_to_shards()` in publisher.py.
**Warning signs:** Files written to wrong directories or `FileNotFoundError` on Windows.

## Code Examples

### Browse Command -- Top-Level Summary Table (D-01)

```python
# Source: Derived from existing cli.py Table patterns

def _render_browse_summary(catalog: dict) -> None:
    """Render top-level browse summary table."""
    models = catalog.get("models", {})
    table = Table(title="Kajiba Dataset Catalog")
    table.add_column("Model", style="bold")
    table.add_column("Gold", justify="right")
    table.add_column("Silver", justify="right")
    table.add_column("Bronze", justify="right")
    table.add_column("Total", justify="right", style="bold")
    table.add_column("Avg Score", justify="right")

    total_records = 0
    for slug, info in sorted(models.items()):
        tiers = info.get("tiers", {})
        gold = tiers.get("gold", {}).get("record_count", 0)
        silver = tiers.get("silver", {}).get("record_count", 0)
        bronze = tiers.get("bronze", {}).get("record_count", 0)
        model_total = info.get("total_records", 0)
        total_records += model_total

        # Compute weighted avg score across tiers
        scores = []
        for t_info in tiers.values():
            avg = t_info.get("avg_quality_score", 0)
            if avg > 0:
                scores.append(avg)
        avg_str = f"{sum(scores)/len(scores):.2f}" if scores else "---"

        table.add_row(
            info.get("display_name", slug),
            str(gold) if gold else "---",
            str(silver) if silver else "---",
            str(bronze) if bronze else "---",
            str(model_total),
            avg_str,
        )

    console.print(table)
    console.print(
        f"[dim]{len(models)} model(s), {total_records} record(s) total. "
        f"Use --model <name> for details.[/dim]"
    )
```

### Browse Command -- Model Drill-Down (D-02)

```python
# Source: Derived from existing cli.py Panel + Table patterns

def _render_browse_model(model_slug: str, model_info: dict) -> None:
    """Render drill-down view for a single model."""
    # Metadata panel
    display = model_info.get("display_name", model_slug)
    params = model_info.get("parameter_counts", [])
    quants = model_info.get("quantizations", [])
    ctx_wins = model_info.get("context_windows", [])

    meta_lines = [f"[bold]Model:[/bold] {display}"]
    meta_lines.append(
        f"[bold]Parameters:[/bold] {', '.join(params)}"
        if params else "[bold]Parameters:[/bold] [dim]---[/dim]"
    )
    meta_lines.append(
        f"[bold]Quantization:[/bold] {', '.join(quants)}"
        if quants else "[bold]Quantization:[/bold] [dim]---[/dim]"
    )
    meta_lines.append(
        f"[bold]Context Window:[/bold] {', '.join(str(w) for w in ctx_wins)}"
        if ctx_wins else "[bold]Context Window:[/bold] [dim]---[/dim]"
    )
    console.print(Panel("\n".join(meta_lines), title="Model Metadata"))

    # Tier breakdown table
    table = Table(title="Tier Breakdown")
    table.add_column("Tier", style="bold")
    table.add_column("Records", justify="right")
    table.add_column("Avg Score", justify="right")
    table.add_column("Size", justify="right")

    for tier_name in ["gold", "silver", "bronze", "review_needed"]:
        tier_info = model_info.get("tiers", {}).get(tier_name)
        if tier_info:
            size_mb = tier_info.get("total_size_bytes", 0) / (1024 * 1024)
            table.add_row(
                tier_name,
                str(tier_info.get("record_count", 0)),
                f"{tier_info.get('avg_quality_score', 0):.2f}",
                f"{size_mb:.1f} MB",
            )
    console.print(table)

    # Hardware distribution summary
    hw = model_info.get("hardware_distribution", {})
    if hw:
        hw_items = sorted(hw.items(), key=lambda x: x[1], reverse=True)[:5]
        hw_str = ", ".join(f"{name} ({count})" for name, count in hw_items)
        console.print(f"[dim]Hardware: {hw_str}[/dim]")
```

### Collecting Shard Paths for Download

```python
def _collect_download_shards(
    catalog: dict,
    model: Optional[str] = None,
    tier: Optional[str] = None,
) -> list[dict]:
    """Collect shard file paths and metadata from filtered catalog.

    Returns:
        List of dicts with 'path', 'model', 'tier', 'size_bytes' keys.
    """
    filtered = filter_catalog(catalog, model=model, tier=tier)
    shards = []
    for slug, info in filtered.get("models", {}).items():
        for tier_name, tier_info in info.get("tiers", {}).items():
            for shard_name in tier_info.get("shards", []):
                shards.append({
                    "path": f"data/{slug}/{tier_name}/{shard_name}",
                    "model": slug,
                    "tier": tier_name,
                    "size_bytes": tier_info.get("total_size_bytes", 0) // max(len(tier_info.get("shards", [1])), 1),
                })
    return shards
```

### gh api Call Pattern for Raw Content

```python
# Critical: Must use raw Accept header to avoid 1MB JSON limit
# Source: GitHub REST API docs - repos/contents

# For catalog.json (small, needs JSON parsing):
result = gh_ops.get_file_contents("catalog.json", raw=True)
if result.success:
    catalog = json.loads(result.stdout)

# For shard files (potentially large, write to disk):
result = gh_ops.get_file_contents(
    "data/gpt-4o/gold/shard_a3.jsonl", raw=True,
)
if result.success:
    dest_path.write_text(result.stdout, encoding="utf-8")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `git clone --sparse` for subset download | `gh api` for targeted file fetching | Phase 5 decision D-05 | No local clone needed; direct API access |
| Manual catalog inspection via JSON | Rich CLI tables with filter flags | Phase 5 | Consumer-friendly browsing experience |
| Catalog without model metadata | Enriched catalog with params/quant/context | Phase 5 CONS-02 | Informed subset selection for fine-tuners |

**Deprecated/outdated:**
- The README.md `How to Use` section in `generate_readme()` currently shows `git clone --sparse` as the download method. After Phase 5, this should be updated to recommend `kajiba browse` and `kajiba download` instead.

## Open Questions

1. **Should `--hardware` filter be added?**
   - What we know: Hardware distribution data exists in catalog. D-03 mentions "filters for model, tier, and hardware" in CONS-03 text.
   - What's unclear: The CONTEXT.md lists hardware filter as Claude's discretion. No explicit requirement for it.
   - Recommendation: Skip `--hardware` filter in initial implementation. Hardware filtering requires per-record inspection (not just catalog metadata), which contradicts the "no extra network calls" design. Hardware distribution is visible in browse drill-down. Can be added later if needed.

2. **Download caching / skip-if-exists behavior**
   - What we know: Users may re-run download. D-06 specifies a stable output directory structure.
   - What's unclear: Whether to overwrite, skip, or prompt on existing files.
   - Recommendation: Implement skip-if-exists by default. If the destination shard file already exists and has the same size, skip it. Show "[dim]Skipped (already exists)[/dim]" in progress. This is safe, fast, and expected CLI behavior. No `--force` flag needed for v1 -- users can delete the directory manually.

3. **Deletion filtering during download**
   - What we know: `deletions.jsonl` lists deleted record IDs. Consumers should exclude these.
   - What's unclear: Whether to auto-filter during download or leave it to the consumer's training pipeline.
   - Recommendation: Download shard files as-is but show a note: "N records in deletions.jsonl -- filter these when loading data." Optionally, if `deletions.jsonl` exists, download it too. Post-download filtering is the consumer's responsibility (consistent with README.md documentation).

4. **Dataset repo configuration source**
   - What we know: `VALID_CONFIG_KEYS["dataset_repo"]` already exists with default `CuervoDoesIt/kajiba-dataset`.
   - What's unclear: Whether browse/download should use `--repo` flag, config value, or both.
   - Recommendation: Use both (same as publish command). `--repo` flag overrides config value. Config value overrides default. Pattern: `repo = repo_arg or _load_config_value("dataset_repo", DEFAULT_DATASET_REPO)`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | Yes | 3.13.3 | -- |
| pytest | Testing | Yes | 9.0.2 | -- |
| rich | Browse/download rendering | Yes | 14.3.3 | -- |
| click | CLI commands | Yes | 8.3.1 | -- |
| gh CLI | Browse/download data access | No (not on dev machine) | -- | Commands fail gracefully with GhResult error handling. Tests mock GitHubOps. |

**Missing dependencies with no fallback:**
- `gh` CLI is not installed on this dev machine. However, all `gh` interactions are wrapped behind `GitHubOps` and return `GhResult`, so the code handles absence gracefully. Tests use mocked `GitHubOps` instances (already established pattern in test_publisher.py). The `gh` CLI is a runtime dependency for end users, not a build/test dependency.

**Missing dependencies with fallback:**
- None.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_cli.py tests/test_publisher.py -x -v` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONS-01 | Catalog tiers enable subset download | unit | `pytest tests/test_publisher.py::TestGenerateCatalogEnriched -x` | No -- Wave 0 |
| CONS-02 | Catalog includes model metadata (params, quant, context) | unit | `pytest tests/test_publisher.py::TestGenerateCatalogEnriched -x` | No -- Wave 0 |
| CONS-03 | `kajiba browse` with filter options | unit + integration | `pytest tests/test_cli.py::TestBrowseCommand -x` | No -- Wave 0 |
| CONS-04 | `kajiba download` with filter options | unit + integration | `pytest tests/test_cli.py::TestDownloadCommand -x` | No -- Wave 0 |

### Supporting Test Cases

| Behavior | Test Type | Automated Command | File Exists? |
|----------|-----------|-------------------|-------------|
| `filter_catalog()` pure function | unit | `pytest tests/test_publisher.py::TestFilterCatalog -x` | No -- Wave 0 |
| `GitHubOps.get_file_contents()` | unit (mocked) | `pytest tests/test_publisher.py::TestGitHubOpsRead -x` | No -- Wave 0 |
| Browse empty catalog message (D-04) | unit | `pytest tests/test_cli.py::TestBrowseCommand::test_empty_catalog -x` | No -- Wave 0 |
| Browse no-match feedback (D-11) | unit | `pytest tests/test_cli.py::TestBrowseCommand::test_no_match -x` | No -- Wave 0 |
| Download unfiltered confirmation (D-12) | unit | `pytest tests/test_cli.py::TestDownloadCommand::test_unfiltered_confirmation -x` | No -- Wave 0 |
| Download skip-if-exists | unit | `pytest tests/test_cli.py::TestDownloadCommand::test_skip_existing -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_cli.py tests/test_publisher.py -x -v`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_publisher.py::TestGenerateCatalogEnriched` -- catalog enrichment with model metadata
- [ ] `tests/test_publisher.py::TestFilterCatalog` -- catalog filtering pure function
- [ ] `tests/test_publisher.py::TestGitHubOpsRead` -- read-only gh api methods (mocked)
- [ ] `tests/test_cli.py::TestBrowseCommand` -- browse command with CliRunner (mocked GitHubOps)
- [ ] `tests/test_cli.py::TestDownloadCommand` -- download command with CliRunner (mocked GitHubOps, tmp_path)
- [ ] Test fixtures: sample `catalog.json` with enriched model metadata for test assertions

## Sources

### Primary (HIGH confidence)
- `src/kajiba/publisher.py` -- existing GitHubOps class, generate_catalog(), GhResult pattern
- `src/kajiba/cli.py` -- existing Click command patterns, Rich Table/Panel/Console usage
- `src/kajiba/config.py` -- VALID_CONFIG_KEYS with dataset_repo, _load_config_value()
- `src/kajiba/schema.py` -- ModelMetadata model with Optional parameter_count/quantization/context_window fields
- [GitHub REST API: Repository Contents](https://docs.github.com/en/rest/repos/contents) -- API endpoint, size limits, Accept headers
- [gh api manual](https://cli.github.com/manual/gh_api) -- CLI flags, no --output flag, -H header syntax

### Secondary (MEDIUM confidence)
- [Rich Progress documentation](https://rich.readthedocs.io/en/stable/progress.html) -- Progress columns, DownloadColumn, example patterns
- [Rich downloader.py example](https://github.com/Textualize/rich/blob/master/examples/downloader.py) -- Progress bar with download tracking pattern
- [Click option reuse patterns](https://github.com/pallets/click/issues/108) -- Shared decorator for common options
- [gh file download notes](https://notes.billmill.org/computer_usage/git/downloading_a_single_file_from_github_with_gh.html) -- raw Accept header for file content

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all libraries verified installed and in use
- Architecture: HIGH -- patterns directly extend existing codebase (GitHubOps, Click commands, Rich rendering)
- Pitfalls: HIGH -- GitHub API limits verified against official docs, cross-platform path pattern already solved in publisher.py
- Catalog enrichment: HIGH -- ModelMetadata schema fields already exist, generate_catalog() extension is straightforward
- Download progress: MEDIUM -- Rich Progress pattern verified from official example, but subprocess-based download (not HTTP streaming) is a less common pattern

**Research date:** 2026-04-01
**Valid until:** 2026-05-01 (stable -- no external dependency changes expected)
