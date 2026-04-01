# Phase 5: Consumer Experience - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md --- this log preserves the alternatives considered.

**Date:** 2026-04-01
**Phase:** 05-consumer-experience
**Areas discussed:** Browse display format, Download mechanics, Missing metadata handling, Filter composition

---

## Browse Display Format

### Top-level presentation

| Option | Description | Selected |
|--------|-------------|----------|
| Summary table | Rich table with one row per model: name, tier counts, total records, avg quality. Consistent with existing stats/history tables. | ✓ |
| Tree drill-down | Hierarchical view: models -> tiers -> shard details. More verbose. | |
| Compact one-liner | Model name + record count per line. Low info density. | |

**User's choice:** Summary table
**Notes:** Selected with preview showing Rich table format with tier columns and footer hint.

### Model detail level

| Option | Description | Selected |
|--------|-------------|----------|
| Tier breakdown + metadata | Show tier table plus model metadata (parameter_count, quantization, context_window) when available. | ✓ |
| Tier counts only | Just tier table, no model metadata. | |
| Full shard listing | Every shard file with sizes. Too verbose for typical use. | |

**User's choice:** Tier breakdown + metadata
**Notes:** Matches CONS-02 requirement to surface runtime context in catalog.

### Filter flags on browse

| Option | Description | Selected |
|--------|-------------|----------|
| Browse accepts filters | Same --model, --tier flags work on both browse and download. | ✓ |
| Browse is unfiltered | Browse always shows everything, filters download-only. | |
| You decide | Claude picks. | |

**User's choice:** Browse accepts filters
**Notes:** Consistent flag surface between browse and download.

### Empty/error states

| Option | Description | Selected |
|--------|-------------|----------|
| Helpful empty message | Clear message with next action suggestion. Error states suggest gh auth status. | ✓ |
| Silent exit | No output, exit code 0. | |
| You decide | Claude picks. | |

**User's choice:** Helpful empty message

---

## Download Mechanics

### Fetch source

| Option | Description | Selected |
|--------|-------------|----------|
| Upstream repo via gh | Fetch catalog.json and shards from upstream using gh api. No fork needed for read-only. | ✓ |
| Git clone + sparse checkout | Clone with sparse checkout for matched paths. More bandwidth-efficient. | |
| Direct raw.githubusercontent.com | Raw GitHub URLs without gh. Works without auth for public repos. | |

**User's choice:** Upstream repo via gh
**Notes:** Consistent with Phase 3's gh-only approach.

### Output path

| Option | Description | Selected |
|--------|-------------|----------|
| Default dir + optional flag | Default: ~/.hermes/kajiba/downloads/{model}/{tier}/. Allow --output override. | ✓ |
| Current directory | Write to ./{model}/{tier}/ in working directory. | |
| Always require --output | No default, explicit path required. | |

**User's choice:** Default dir + optional flag

### Progress display

| Option | Description | Selected |
|--------|-------------|----------|
| Rich progress bar | Rich progress bar with shard count and bytes. Completion summary. | ✓ |
| Simple line-per-shard | One line per shard downloaded. | |
| You decide | Claude picks. | |

**User's choice:** Rich progress bar

---

## Missing Metadata Handling

### Display strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Show available, dim missing | Display what exists, dim dash for missing. Aggregate across all records for model. | ✓ |
| Require all fields | Only show metadata panel when ALL fields populated. | |
| Best-effort aggregate | Show all unique values as comma-separated lists. | |

**User's choice:** Show available, dim missing
**Notes:** If ANY record for a model has parameter_count, it shows in browse.

### Enrichment timing

| Option | Description | Selected |
|--------|-------------|----------|
| At publish time | Extend generate_catalog() to extract model metadata. Browse reads pre-computed catalog. | ✓ |
| At browse time | Browse samples records on-the-fly for metadata. Slower. | |
| You decide | Claude picks. | |

**User's choice:** At publish time
**Notes:** No extra network calls during browse.

---

## Filter Composition

### Composition logic

| Option | Description | Selected |
|--------|-------------|----------|
| AND between flags, exact match | --model X --tier Y = both. Single value per flag. | ✓ |
| AND between flags, OR within repeats | --model X --model Y = either model. More powerful but complex. | |
| Glob/wildcard support | --model 'llama*' matches variants. | |

**User's choice:** AND between flags, exact match

### No-match behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Show what's available | Show which filter failed and list available options. | ✓ |
| Silent empty exit | No output, exit code 0. | |
| You decide | Claude picks. | |

**User's choice:** Show what's available

### Unfiltered download guard

| Option | Description | Selected |
|--------|-------------|----------|
| Confirm with size estimate | Show totals, prompt "Continue? [y/N]". | ✓ |
| Just download everything | No guard. | |
| Require at least one filter | Error without --model or --tier. | |

**User's choice:** Confirm with size estimate

---

## Claude's Discretion

- Rich table styling and column widths
- Download caching/skip-if-exists behavior
- Whether --hardware filter flag is worthwhile
- Deletion filtering during download
- Dry-run mode for download
- Dataset repo URL configuration

## Deferred Ideas

None --- discussion stayed within phase scope.
