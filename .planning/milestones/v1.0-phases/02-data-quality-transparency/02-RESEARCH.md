# Phase 2: Data Quality & Transparency - Research

**Researched:** 2026-03-30
**Domain:** Quality scoring persistence, CLI annotation commands, redaction diff display (Python/Pydantic/Click/Rich)
**Confidence:** HIGH

## Summary

Phase 2 extends the existing quality scoring system and CLI to make quality transparent and interactive. The work divides into four areas: (1) adding a `QualityMetadata` Pydantic model to `KajibaRecord` and persisting scores at submit time, (2) enhancing `kajiba preview` with inline redaction highlighting and a summary/detail toggle, (3) adding `kajiba rate` and `kajiba report` CLI commands for contributor annotations, and (4) wiring annotations into the preview and export pipeline.

All building blocks already exist. The scorer produces `QualityResult` with the exact fields needed. The scrubber returns `ScrubResult` with `redactions` (list of `Redaction` with original/replacement/category/start/end) and `flagged` (list of `FlaggedItem`). Rich is already imported in cli.py with Console, Table, Panel, and Text. The `PainPoint` model and `OutcomeSignals` model already define the data shapes. The `KajibaCollector` already has `on_rate()` and `on_report()` methods -- this phase surfaces equivalent functionality through the CLI.

**Primary recommendation:** Build from the inside out -- schema extension first (QualityMetadata model), then scorer/submit wiring, then CLI commands (rate, report), then preview enhancement. Each layer is independently testable.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Preview shows scrubbed text with redacted spans highlighted inline (e.g., `[REDACTED:email]` in red). Compact, single-pass through text. Not side-by-side or before/after.
- **D-02:** Flagged items (org domains from Phase 1) appear as yellow warning lines below the scrubbed text. Visually distinct from red redactions. Builds on Phase 1's existing partial implementation.
- **D-03:** Summary + detail toggle: `kajiba preview` shows a summary table by default (category | count), with a `--detail` flag to see full inline-highlighted text. Good for large records.
- **D-04:** Quality data stored in a new nested `QualityMetadata` Pydantic model on `KajibaRecord`. Field: `record.quality`. Contains `quality_tier`, `composite_score`, `sub_scores` dict (all 5 dimensions), and `scored_at` timestamp.
- **D-05:** All sub-scores (coherence, tool_validity, outcome_quality, information_density, metadata_completeness) are stored alongside the composite score. Enables consumers to filter by specific quality dimensions.
- **D-06:** Quality computed and stored at submit time. Preview also computes and displays the score (but doesn't persist until submit). User sees quality before committing.
- **D-07:** `kajiba rate` uses interactive Rich prompts by default (score 1-5, optional tags). CLI flags (`--score`, `--tags`) override for non-interactive/scripting use.
- **D-08:** Both `kajiba rate` and `kajiba report` use an interactive picker to select which staged record to annotate (when multiple exist). No implicit "latest" default.
- **D-09:** `kajiba report` uses the existing `PainPoint` schema: interactive Rich picker for category (from `PAIN_POINT_CATEGORIES`), free-text description, severity selection. Structured but guided.
- **D-10:** Preview shows a merged quality panel: auto-score, sub-scores, AND user rating/tags/pain points together in one Rich panel. Single place to see everything about quality.
- **D-11:** `kajiba history` list shows tier and score only. Annotations visible when drilling into a specific record's detail view. Keeps the list clean.

### Claude's Discretion
- Rich formatting details (colors, padding, panel borders) for the redaction diff display
- Exact layout of the merged quality panel (table vs key-value pairs vs hybrid)
- Whether `--detail` flag applies to quality panel too or just redaction diff
- Tag vocabulary for `kajiba rate` -- use existing `OUTCOME_TAGS` or define a separate quality-tag vocabulary

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| QUAL-01 | Quality tier and composite score stored in outbox record at submit time | QualityMetadata Pydantic model on KajibaRecord; scorer already produces QualityResult with exact fields needed; wired at submit/export commands |
| QUAL-02 | Preview shows inline redaction diff with highlighted redactions | ScrubResult.redactions list provides start/end/category for each redaction; Rich Text markup supports per-span styling; summary table from ScrubResult.stats |
| QUAL-03 | User can rate staged record via `kajiba rate` with score and tags | OutcomeSignals model already defines user_rating (1-5) and outcome_tags; Click command + Rich prompts for interactive flow; `--score`/`--tags` flags for scripting |
| QUAL-04 | User can report pain points via `kajiba report` with category/description/severity | PainPoint model already defines all fields; PAIN_POINT_CATEGORIES tuple provides picker vocabulary; staged record load + save-back pattern |
| QUAL-05 | User annotations included in exported record alongside auto-scores | Annotations stored on staged record (JSON file); submit pipeline reads them and persists to outbox; preview displays merged quality panel |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Tech stack**: Python 3.11+, Pydantic v2, Click, Rich -- no deviations
- **Privacy**: Maximum scrubbing by default; quality scoring happens BEFORE privacy transforms
- **Local-first**: All processing on contributor's machine
- **No external services**: Core pipeline works without API keys or network access
- **Naming**: snake_case for modules/functions, PascalCase for classes, UPPER_SNAKE_CASE for constants
- **Type annotations**: Full annotations on all public functions, use `Optional[X]` not `X | None`
- **Logging**: `logger = logging.getLogger(__name__)` per module; `%s` formatting; no `print()`
- **Docstrings**: Google-style with Args/Returns/Raises sections
- **Serialization**: `model_dump(mode="json", by_alias=True)` for JSON; `model_validate()` for input
- **Section dividers**: `# ---------------------------------------------------------------------------` with label comments
- **Testing**: pytest with Click's CliRunner; fixtures in `tests/fixtures/`; `_make_record()` / `_load_fixture()` helpers

## Standard Stack

### Core (already installed -- no new dependencies)

| Library | Version (verified) | Purpose | Why Standard |
|---------|-------------------|---------|--------------|
| pydantic | 2.12.5 | QualityMetadata model, schema validation | Already used for all schema models |
| click | 8.3.1 | `rate` and `report` CLI commands | Already used for all CLI commands |
| rich | 14.3.3 | Interactive prompts, inline text highlighting, panels | Already used for all CLI output |
| pytest | 9.0.2 | Test new commands and schema changes | Already used for all tests |

### Supporting (already available -- no new imports)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `datetime` (stdlib) | 3.13.3 | `scored_at` timestamp in QualityMetadata | When computing quality at submit time |
| `json` (stdlib) | 3.13.3 | Staged record save-back after annotation | When `rate`/`report` write updated staging files |

### No New Dependencies Required

This phase uses only existing project dependencies. No `pip install` needed. The Rich library (14.3.3) already supports all features needed: `Prompt`, `IntPrompt`, `Confirm`, `Text` with spans, `Table`, and `Panel`.

## Architecture Patterns

### Recommended Changes to Project Structure

No new modules required. All changes fit within existing files:

```
src/kajiba/
  schema.py       # ADD: QualityMetadata model, quality field on KajibaRecord
  scorer.py       # NO CHANGE (QualityResult stays as-is; new model derives from it)
  cli.py          # ADD: rate command, report command, preview --detail, load_all_staging()
                  # MODIFY: _render_preview(), submit (persist quality), history (read stored)
  scrubber.py     # NO CHANGE (ScrubResult already has what preview needs)
  privacy.py      # NO CHANGE
  collector.py    # NO CHANGE
```

### Pattern 1: QualityMetadata Schema Extension

**What:** Add a nested Pydantic model to KajibaRecord for persistent quality data.
**When to use:** When quality scores need to survive the submit -> outbox -> publish pipeline.
**Example:**

```python
# In src/kajiba/schema.py — follows existing nested model pattern
class QualityMetadata(BaseModel):
    """Stored quality assessment for a record."""

    quality_tier: str  # "gold", "silver", "bronze", "review_needed"
    composite_score: float = Field(ge=0.0, le=1.0)
    sub_scores: dict[str, float]
    scored_at: datetime


# On KajibaRecord:
class KajibaRecord(BaseModel):
    # ... existing fields ...
    quality: Optional[QualityMetadata] = None
```

**Key detail:** `quality` field must be `Optional` with default `None` so that existing staged records without quality data still validate. Quality is populated at submit time, not at record creation.

### Pattern 2: Staged Record Load-All + Picker

**What:** Load all staged records (not just latest) and present an interactive picker.
**When to use:** For `rate` and `report` commands that need to target a specific record (per D-08).
**Example:**

```python
# In src/kajiba/cli.py — new helper
def _load_all_staging() -> list[tuple[Path, KajibaRecord]]:
    """Load all sessions from the staging directory.

    Returns:
        List of (file_path, KajibaRecord) tuples sorted by modification time.
    """
    _ensure_dirs()
    files = sorted(
        list(STAGING_DIR.glob("*.json")) + list(STAGING_DIR.glob("*.jsonl")),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    results = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append((f, validate_record(data)))
        except Exception as exc:
            logger.error("Failed to load staging file %s: %s", f, exc)
    return results
```

The picker uses Rich's `Prompt.ask()` with choices. When only one record exists, it auto-selects with confirmation.

### Pattern 3: Staged Record Save-Back

**What:** After `rate` or `report` modifies a staged record, write it back to the same staging file.
**When to use:** Annotations modify the staging file in-place so `preview` and `submit` see the updates.
**Example:**

```python
# After attaching outcome/pain_point to record:
updated_data = record.model_dump(mode="json", by_alias=True)
staging_path.write_text(
    json.dumps(updated_data, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
```

**Key detail:** Use `indent=2` for human-readability (staging files are local-only). Use `by_alias=True` because `ConversationTurn.from_` has alias `"from"`.

### Pattern 4: Inline Redaction Highlighting with Rich Text

**What:** Build a Rich `Text` object with styled spans marking where redactions occurred.
**When to use:** For the `--detail` view of `kajiba preview` (per D-01, D-03).
**Example:**

```python
from rich.text import Text

def _highlight_redactions(scrubbed_text: str, redactions: list) -> Text:
    """Build Rich Text with redaction placeholders highlighted in red."""
    text = Text(scrubbed_text)
    # Find all placeholder markers in the scrubbed text and style them
    import re
    for match in re.finditer(r"\[REDACTED_\w+\]", scrubbed_text):
        text.stylize("bold red", match.start(), match.end())
    return text
```

**Note:** The `Redaction` dataclass tracks start/end positions in the ORIGINAL text. Since scrubbing changes text length, the planner must use placeholder positions in the SCRUBBED text (regex match on `[REDACTED_*]` patterns), not the original positions.

### Pattern 5: Quality Persistence at Submit Time

**What:** Compute quality score and store it in `record.quality` before writing to outbox.
**When to use:** In the `submit` and `export` commands (per D-06).
**Example:**

```python
# In submit command, after privacy pipeline but before writing:
quality_result = compute_quality_score(final)
final.quality = QualityMetadata(
    quality_tier=quality_result.quality_tier,
    composite_score=quality_result.composite_score,
    sub_scores=quality_result.sub_scores,
    scored_at=datetime.now(UTC),
)
```

### Anti-Patterns to Avoid

- **Storing quality on the staged record:** Quality is computed fresh at preview/submit time, not stored in staging. The staged record evolves (annotations added) so pre-computing quality on it would be stale.
- **Re-computing quality in `history`/`stats`:** The current code at cli.py:349-353 does `compute_quality_score(rec)` for every outbox record. After this phase, `history` reads `record.quality.quality_tier` directly. Fallback to recompute only if `quality` field is None (backward compatibility with old records).
- **Mutating staged records in-place without deep copy:** Always use `model_dump()` -> modify -> `model_validate()` or write JSON. Never mutate the Pydantic model attributes directly on a loaded record.
- **Building a parallel redaction mechanism:** The redaction diff display MUST use `ScrubResult.redactions` and `ScrubResult.flagged` from Phase 1's scrubber, not a new mechanism (per STATE.md blocker note).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Interactive CLI prompts | Custom input() loops | `rich.prompt.Prompt`, `rich.prompt.IntPrompt`, `rich.prompt.Confirm` | Rich prompts handle validation, colors, defaults, retry |
| Numbered choice picker | String parsing of user input | `rich.prompt.Prompt.ask(choices=...)` with numbered display | Built-in choice validation, auto-complete |
| Inline text highlighting | ANSI escape codes | `rich.text.Text` with `.stylize()` method | Handles terminal compatibility, nesting, overflow |
| Quality tier coloring | Manual color mapping | Rich markup `[yellow]gold[/yellow]` etc. | Already established pattern in `_render_preview()` at cli.py:121-123 |
| Timestamp generation | Manual string formatting | `datetime.now(UTC)` (already used throughout) | Consistent with existing codebase pattern |

## Common Pitfalls

### Pitfall 1: Redaction Position Drift After Scrubbing
**What goes wrong:** Using `Redaction.start`/`Redaction.end` positions from `ScrubResult` to highlight in the scrubbed text. These positions reference the ORIGINAL text, not the scrubbed text where placeholders have different lengths.
**Why it happens:** Regex replacements change string length. A 40-character API key becomes `[REDACTED_KEY]` (14 chars), shifting all subsequent positions.
**How to avoid:** For inline highlighting in the scrubbed text, search for `[REDACTED_*]` placeholder patterns using regex on the scrubbed text itself. The `Redaction` objects are useful for the summary table (category counts) but not for positional highlighting.
**Warning signs:** Highlights appear at wrong positions or extend beyond text boundaries.

### Pitfall 2: Schema Migration for Existing Outbox Records
**What goes wrong:** Adding `quality: Optional[QualityMetadata]` to KajibaRecord works for new records, but existing outbox records lack this field. If `history` or `stats` assumes `record.quality` is always present, it will crash on old records.
**Why it happens:** No database migration -- outbox is flat files.
**How to avoid:** Always check `if record.quality:` before accessing sub-fields. Fallback to `compute_quality_score()` for records without stored quality. The field defaults to `None`, so Pydantic validation will pass.
**Warning signs:** `AttributeError` or `TypeError` when running `history` after upgrade.

### Pitfall 3: Click Command Registration Order
**What goes wrong:** New `rate` and `report` commands conflict with existing command names or fail to register.
**Why it happens:** Click uses the function name as the command name by default. If a function is named `report` but there is already an attribute or import named `report`, it shadows.
**How to avoid:** Use `@cli.command()` decorator (already established pattern). Verify that `rate` and `report` are not reserved names in Click (they are not). Add to the help text test at test_cli.py:30-35 to verify both commands appear.
**Warning signs:** `click.exceptions.UsageError` or command missing from `--help` output.

### Pitfall 4: Staged Record Save-Back Loses Validation
**What goes wrong:** After attaching an outcome or pain point to a record, saving the modified dict without re-validation could produce an invalid record.
**Why it happens:** Directly modifying the dict from `model_dump()` bypasses Pydantic validators (turn_count, tool_call_counts, outcome_tags vocabulary).
**How to avoid:** After modifying the dict, call `KajibaRecord.model_validate(data)` to verify. If validation fails, report the error to the user and do not overwrite the staging file.
**Warning signs:** `ValidationError` on next load of the staging file.

### Pitfall 5: Interactive Prompts in Test Environment
**What goes wrong:** Tests hang waiting for user input from Rich prompts or Click prompts.
**Why it happens:** Interactive prompts require stdin input. Click's `CliRunner` supports `input=` parameter, but Rich prompts bypass Click's input mechanism.
**How to avoid:** For `rate` and `report` commands, use Click flags (`--score`, `--tags`, `--category`, etc.) as the primary interface, with Rich interactive prompts only when flags are not provided. Tests use the CLI flags path exclusively. Alternatively, use `monkeypatch` to mock Rich prompt calls.
**Warning signs:** Test suite hangs indefinitely or times out.

### Pitfall 6: by_alias Serialization for ConversationTurn
**What goes wrong:** Saving a record with `model_dump()` instead of `model_dump(by_alias=True)` produces `"from_"` in JSON instead of `"from"`. The record cannot be re-loaded because `model_validate()` expects `"from"` (the alias).
**Why it happens:** `ConversationTurn.from_` uses `Field(alias="from")` because `from` is a Python keyword. `populate_by_name=True` allows both `from_` and `from` on input, but output must use alias for round-trip compatibility.
**How to avoid:** Always use `model_dump(mode="json", by_alias=True)` for serialization. This is the established pattern (scrubber.py:327, cli.py:281).
**Warning signs:** `ValidationError: conversations -> 0 -> from: field required` on re-load.

## Code Examples

### Creating QualityMetadata from QualityResult

```python
# Source: Derived from existing scorer.py QualityResult and D-04/D-05 decisions
from datetime import UTC, datetime
from kajiba.scorer import compute_quality_score

quality_result = compute_quality_score(record)
quality_meta = QualityMetadata(
    quality_tier=quality_result.quality_tier,
    composite_score=quality_result.composite_score,
    sub_scores=quality_result.sub_scores,
    scored_at=datetime.now(UTC),
)
record.quality = quality_meta
```

### Interactive Record Picker Pattern

```python
# Source: Derived from D-08 decision + Rich prompt patterns
from rich.prompt import IntPrompt

staged = _load_all_staging()
if not staged:
    console.print("[yellow]No sessions found in staging directory.[/yellow]")
    return
if len(staged) == 1:
    filepath, record = staged[0]
    console.print(f"[dim]One staged record found: {filepath.name}[/dim]")
else:
    for i, (fp, rec) in enumerate(staged, 1):
        turns = rec.trajectory.turn_count
        model = rec.model.model_name if rec.model else "unknown"
        console.print(f"  {i}. {fp.name} — {turns} turns, model: {model}")
    choice = IntPrompt.ask(
        "Select record",
        choices=[str(i) for i in range(1, len(staged) + 1)],
    )
    filepath, record = staged[choice - 1]
```

### Inline Redaction Highlighting

```python
# Source: Derived from D-01 decision + Rich Text API
import re
from rich.text import Text

def _build_highlighted_text(scrubbed_text: str) -> Text:
    """Build Rich Text with REDACTED placeholders styled red."""
    text = Text(scrubbed_text)
    for match in re.finditer(r"\[REDACTED_\w+\]", scrubbed_text):
        text.stylize("bold red", match.start(), match.end())
    return text
```

### Summary Table for Redaction Counts

```python
# Source: Derived from D-03 decision + existing scrub_stats pattern
from rich.table import Table

def _build_scrub_summary_table(scrub_stats: dict, flagged_count: int) -> Table:
    """Build a compact summary table of scrubbing results."""
    table = Table(title="Scrubbing Summary", show_header=True)
    table.add_column("Category", style="bold")
    table.add_column("Redacted", justify="right")
    for category, count in scrub_stats.items():
        if count > 0:
            table.add_row(category.replace("_", " ").title(), str(count))
    if flagged_count > 0:
        table.add_row("[yellow]Flagged for Review[/yellow]", str(flagged_count))
    return table
```

### Rate Command with Dual Interface (Interactive + Flags)

```python
# Source: Derived from D-07 decision + Click/Rich patterns
@cli.command()
@click.option("--score", type=click.IntRange(1, 5), help="Quality rating 1-5.")
@click.option("--tags", help="Comma-separated outcome tags.")
@click.option("--comment", help="Optional free-text comment.")
def rate(score: Optional[int], tags: Optional[str], comment: Optional[str]) -> None:
    """Rate a staged record's quality."""
    # If --score not provided, use interactive Rich prompt
    if score is None:
        score = IntPrompt.ask("Rating (1-5)", choices=["1", "2", "3", "4", "5"])
    # ... tag selection, save-back to staging file
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Quality re-computed every time (cli.py history/stats) | Quality stored at submit time, read from record | This phase | Eliminates O(n * scoring_cost) on history/stats |
| No annotation CLI commands | `rate` and `report` as standalone CLI commands | This phase | Standalone users can annotate without Hermes Agent running |
| Scrubbing results shown as aggregate counts only | Inline highlighted redactions with summary/detail toggle | This phase | Contributors see exactly what was removed, building trust |

**No deprecated APIs used:** All Rich, Click, and Pydantic APIs in scope are current as of verified installed versions (Rich 14.3.3, Click 8.3.1, Pydantic 2.12.5).

## Open Questions

1. **Tag vocabulary for `kajiba rate`**
   - What we know: `OUTCOME_TAGS` (18 tags) already exists and covers most quality-related annotations. The `OutcomeSignals` model uses `OutcomeTagType` for validation.
   - What's unclear: Whether a separate, smaller tag vocabulary would be more user-friendly for the interactive picker (18 choices is a lot for a Rich prompt).
   - Recommendation: Use `OUTCOME_TAGS` as-is. The existing vocabulary is well-defined and used throughout the codebase. A separate vocabulary would create maintenance burden and confusion. The interactive picker can group tags by theme (completion, quality, tools, behavior) to make selection easier.

2. **Whether `--detail` flag should apply to quality panel too**
   - What we know: D-03 specifies `--detail` for the redaction diff. D-10 specifies a merged quality panel.
   - What's unclear: Should `--detail` expand the quality panel to show per-sub-score breakdown, or should sub-scores always be shown?
   - Recommendation: Always show sub-scores in the quality panel (they are compact -- 5 lines). Apply `--detail` only to the redaction diff section. The quality panel is already small; hiding sub-scores behind a flag reduces transparency for no space savings.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v --tb=short` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QUAL-01 | Quality tier/score stored in outbox at submit | integration | `python -m pytest tests/test_cli.py::TestSubmitQualityPersistence -x` | No -- Wave 0 |
| QUAL-01 | QualityMetadata model validates correctly | unit | `python -m pytest tests/test_schema.py::TestQualityMetadata -x` | No -- Wave 0 |
| QUAL-01 | history reads stored quality instead of recomputing | integration | `python -m pytest tests/test_cli.py::TestHistoryStoredQuality -x` | No -- Wave 0 |
| QUAL-02 | Preview shows redaction summary by default | integration | `python -m pytest tests/test_cli.py::TestPreviewRedactionSummary -x` | No -- Wave 0 |
| QUAL-02 | Preview --detail shows inline highlighted text | integration | `python -m pytest tests/test_cli.py::TestPreviewRedactionDetail -x` | No -- Wave 0 |
| QUAL-03 | rate command with --score/--tags flags | integration | `python -m pytest tests/test_cli.py::TestRateCommand -x` | No -- Wave 0 |
| QUAL-03 | rate saves outcome to staging file | integration | `python -m pytest tests/test_cli.py::TestRateCommand::test_rate_saves_to_staging -x` | No -- Wave 0 |
| QUAL-04 | report command with --category/--description/--severity flags | integration | `python -m pytest tests/test_cli.py::TestReportCommand -x` | No -- Wave 0 |
| QUAL-04 | report appends pain point to staging file | integration | `python -m pytest tests/test_cli.py::TestReportCommand::test_report_saves_to_staging -x` | No -- Wave 0 |
| QUAL-05 | Exported record contains both auto-scores and annotations | integration | `python -m pytest tests/test_cli.py::TestExportAnnotations -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x -q` (full suite, ~2.5s)
- **Per wave merge:** `python -m pytest tests/ -v --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_schema.py::TestQualityMetadata` -- covers QUAL-01 schema validation
- [ ] `tests/test_cli.py::TestSubmitQualityPersistence` -- covers QUAL-01 submit persistence
- [ ] `tests/test_cli.py::TestHistoryStoredQuality` -- covers QUAL-01 history reads stored quality
- [ ] `tests/test_cli.py::TestPreviewRedactionSummary` -- covers QUAL-02 default summary view
- [ ] `tests/test_cli.py::TestPreviewRedactionDetail` -- covers QUAL-02 --detail flag
- [ ] `tests/test_cli.py::TestRateCommand` -- covers QUAL-03
- [ ] `tests/test_cli.py::TestReportCommand` -- covers QUAL-04
- [ ] `tests/test_cli.py::TestExportAnnotations` -- covers QUAL-05

Existing test helpers (`_minimal_record_data()` in test_cli.py, `_make_record()` and `_load_fixture()` in test_scorer.py, monkeypatch pattern for STAGING_DIR/OUTBOX_DIR) are sufficient. No new conftest.py fixtures needed.

## Sources

### Primary (HIGH confidence)
- `src/kajiba/schema.py` -- Full schema with all Pydantic models, controlled vocabularies, field validators
- `src/kajiba/scorer.py` -- Quality scoring system, QualityResult dataclass, sub-score functions, tier thresholds
- `src/kajiba/cli.py` -- All CLI commands, `_render_preview()`, `_load_latest_staging()`, submit/export pipeline
- `src/kajiba/scrubber.py` -- ScrubResult, Redaction, FlaggedItem dataclasses; `scrub_text()`, `scrub_record()`
- `src/kajiba/privacy.py` -- Privacy pipeline (anonymize_hardware, jitter_timestamp, apply_consent_level)
- `docs/kajiba-project-spec.md` -- Quality scoring spec (Section 3), controlled vocabularies (Section 1.3)
- `tests/test_cli.py` -- CLI test patterns with CliRunner, monkeypatching, staging/outbox fixtures
- `tests/test_scorer.py` -- Scorer test patterns with fixture loading and `_make_record()` helper
- `.planning/phases/02-data-quality-transparency/02-CONTEXT.md` -- All locked decisions (D-01 through D-11)
- `.planning/STATE.md` -- Phase 2 blocker: "redaction diff MUST use the new mechanism, not the old ScrubResult shape" (verified: Phase 1 ScrubResult already has `redactions` and `flagged` lists)

### Secondary (MEDIUM confidence)
- `.planning/codebase/CONCERNS.md` -- Gap analysis confirming quality storage gap and rate/report CLI gap
- Rich library documentation -- `Text.stylize()`, `Prompt.ask()`, `IntPrompt.ask()` APIs (verified available in Rich 14.3.3 via installed version check)

### Tertiary (LOW confidence)
- None -- all findings verified against actual source code

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies; all libraries verified installed with current versions
- Architecture: HIGH -- all patterns derived from existing codebase; schema extension follows established Pydantic model pattern
- Pitfalls: HIGH -- all pitfalls identified from reading actual code (position drift, alias serialization, schema migration) and established test patterns

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable -- no fast-moving dependencies)
