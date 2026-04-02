"""Kajiba CLI — click-based command interface.

Provides commands for previewing, submitting, exporting, and managing
Kajiba session data.
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from kajiba import __version__
from kajiba.config import (
    _load_config_value,
    _save_config_value,
    _show_pending_notifications,
    VALID_CONFIG_KEYS,
)
from kajiba.privacy import anonymize_hardware, apply_consent_level, jitter_timestamp
from kajiba.publisher import (
    CLONE_DIR,
    DEFAULT_DATASET_REPO,
    GitHubOps,
    build_deletion_pr_body,
    build_deletion_pr_title,
    build_publish_pr_body,
    build_publish_pr_title,
    create_deletion_entry,
    filter_catalog,
    generate_catalog,
    generate_readme,
    write_records_to_shards,
)
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)
from kajiba.schema import (
    OUTCOME_TAGS, PAIN_POINT_CATEGORIES, SCHEMA_VERSION,
    KajibaRecord, OutcomeSignals, PainPoint, QualityMetadata,
    SubmissionMetadata, validate_record,
)
from kajiba.scorer import compute_quality_score
from kajiba.scrubber import flag_org_domains, scrub_record

logger = logging.getLogger(__name__)
console = Console()

# ---------------------------------------------------------------------------
# Directory management
# ---------------------------------------------------------------------------

KAJIBA_BASE = Path.home() / ".hermes" / "kajiba"
STAGING_DIR = KAJIBA_BASE / "staging"
OUTBOX_DIR = KAJIBA_BASE / "outbox"
DOWNLOADS_DIR = Path.home() / ".hermes" / "kajiba" / "downloads"


def _ensure_dirs() -> None:
    """Create Kajiba directories if they don't exist."""
    KAJIBA_BASE.mkdir(parents=True, exist_ok=True)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)


def _load_latest_staging() -> Optional[KajibaRecord]:
    """Load the most recent session from the staging directory.

    Returns:
        The most recent KajibaRecord, or None if staging is empty.
    """
    _ensure_dirs()
    files = sorted(STAGING_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        jsonl_files = sorted(STAGING_DIR.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
        files = jsonl_files

    if not files:
        return None

    latest = files[0]
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
        return validate_record(data)
    except Exception as exc:
        logger.error("Failed to load staging file %s: %s", latest, exc)
        return None


def _load_outbox_records() -> list[tuple[Path, dict]]:
    """Load all records from the outbox.

    Returns:
        List of (file_path, record_data) tuples.
    """
    _ensure_dirs()
    records = []
    for f in sorted(OUTBOX_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            for line in f.read_text(encoding="utf-8").strip().split("\n"):
                if line.strip():
                    records.append((f, json.loads(line)))
        except Exception as exc:
            logger.error("Failed to load outbox file %s: %s", f, exc)
    return records


def _load_all_staging() -> list[tuple[Path, KajibaRecord]]:
    """Load all sessions from the staging directory.

    Returns:
        List of (file_path, KajibaRecord) tuples sorted by
        modification time (newest first).
    """
    _ensure_dirs()
    files = sorted(
        list(STAGING_DIR.glob("*.json")) + list(STAGING_DIR.glob("*.jsonl")),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    results: list[tuple[Path, KajibaRecord]] = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append((f, validate_record(data)))
        except Exception as exc:
            logger.error("Failed to load staging file %s: %s", f, exc)
    return results


def _pick_staged_record() -> Optional[tuple[Path, KajibaRecord]]:
    """Load staged records and let user pick one.

    Per D-08: Interactive picker when multiple exist. No implicit latest.

    Returns:
        (file_path, record) tuple, or None if no records or user cancels.
    """
    staged = _load_all_staging()
    if not staged:
        console.print("[yellow]No sessions found in staging directory.[/yellow]")
        console.print(f"  Staging path: {STAGING_DIR}")
        return None

    if len(staged) == 1:
        filepath, record = staged[0]
        console.print(f"[dim]One staged record found: {filepath.name}[/dim]")
        return filepath, record

    console.print("[bold]Staged records:[/bold]")
    for i, (fp, rec) in enumerate(staged, 1):
        turns = len(rec.trajectory.conversations)
        model = rec.model.model_name if rec.model else "unknown"
        console.print(f"  {i}. {fp.name} — {turns} turns, model: {model}")

    choice_str = click.prompt(
        "Select record number",
        type=click.IntRange(1, len(staged)),
    )
    return staged[int(choice_str) - 1]


def _save_staged_record(filepath: Path, record: KajibaRecord) -> None:
    """Save a modified record back to its staging file.

    Uses model_dump(mode="json", by_alias=True) for round-trip
    compatibility (from_ -> "from" alias). Re-validates before saving.

    Args:
        filepath: Path to the staging JSON file.
        record: The modified KajibaRecord to save.
    """
    data = record.model_dump(mode="json", by_alias=True)
    # Re-validate to catch any corruption
    validate_record(data)
    filepath.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _build_scrub_summary_table(scrub_stats: dict, flagged_count: int) -> Table:
    """Build a compact summary table of scrubbing results.

    Args:
        scrub_stats: Dict of category -> redaction count from ScrubLog.
        flagged_count: Number of items flagged for review.

    Returns:
        Rich Table with category and count columns.
    """
    table = Table(title="Scrubbing Summary", show_header=True)
    table.add_column("Category", style="bold")
    table.add_column("Redacted", justify="right")
    for category, count in scrub_stats.items():
        if count > 0:
            label = category.replace("_redacted", "").replace("_", " ").title()
            table.add_row(label, str(count))
    if flagged_count > 0:
        table.add_row("[yellow]Flagged for Review[/yellow]", str(flagged_count))
    return table


def _build_highlighted_text(scrubbed_text: str) -> Text:
    """Build Rich Text with REDACTED placeholders styled red.

    Searches the scrubbed text for [REDACTED_*] markers and applies
    bold red styling. Uses placeholder positions in the SCRUBBED text
    (not original text positions from Redaction objects).

    Args:
        scrubbed_text: Text with REDACTED placeholder markers.

    Returns:
        Rich Text object with styled redaction markers.
    """
    import re as _re
    text = Text(scrubbed_text)
    for match in _re.finditer(r"\[REDACTED_\w+\]", scrubbed_text):
        text.stylize("bold red", match.start(), match.end())
    return text


def _render_preview(
    record: KajibaRecord,
    quality_result: dict,
    scrub_stats: dict,
    flagged_items: Optional[list] = None,
    detail: bool = False,
    scrubbed_record: Optional[KajibaRecord] = None,
) -> None:
    """Render a rich preview of a record."""
    # Header table
    table = Table(title="Kajiba — Submission Preview", show_header=False, expand=True)
    table.add_column("Field", style="bold cyan", width=24)
    table.add_column("Value")

    table.add_row("Record type", record.record_type)
    table.add_row("Schema version", record.schema_version)
    table.add_row("Turns", str(record.trajectory.turn_count))
    table.add_row(
        "Tool calls",
        f"{record.trajectory.total_tool_calls} total "
        f"({record.trajectory.successful_tool_calls} success, "
        f"{record.trajectory.failed_tool_calls} failed)",
    )

    if record.model:
        model_str = record.model.model_name
        if record.model.quantization:
            model_str += f" ({record.model.quantization})"
        table.add_row("Model", model_str)

    console.print(table)

    # Merged quality panel (per D-10)
    quality_panel_rows = []

    # Auto-computed scores
    tier = quality_result.get("quality_tier", "unknown")
    tier_colors = {"gold": "yellow", "silver": "white", "bronze": "dark_orange", "review_needed": "red"}
    tier_color = tier_colors.get(tier, "white")
    quality_panel_rows.append(f"[bold]Quality Tier:[/bold] [{tier_color}]{tier}[/{tier_color}]")
    quality_panel_rows.append(
        f"[bold]Composite Score:[/bold] {quality_result.get('composite_score', 0):.3f}"
    )

    for name, value in quality_result.get("sub_scores", {}).items():
        label = name.replace("_", " ").title()
        quality_panel_rows.append(f"  {label}: {value:.3f}")

    # User annotations (per D-10: merged in same panel)
    if record.outcome:
        quality_panel_rows.append("")
        quality_panel_rows.append(f"[bold]User Rating:[/bold] {record.outcome.user_rating}/5")
        if record.outcome.outcome_tags:
            quality_panel_rows.append(f"[bold]Tags:[/bold] {', '.join(record.outcome.outcome_tags)}")
        if record.outcome.user_comment:
            quality_panel_rows.append(f"[bold]Comment:[/bold] {record.outcome.user_comment}")

    if record.pain_points:
        quality_panel_rows.append("")
        quality_panel_rows.append(f"[bold]Pain Points:[/bold] ({len(record.pain_points)})")
        for pp in record.pain_points:
            quality_panel_rows.append(f"  [{pp.severity}] {pp.category}: {pp.description}")

    console.print(Panel("\n".join(quality_panel_rows), title="Quality & Annotations"))

    # Scrubbing transparency (per D-01, D-02, D-03)
    has_redactions = any(v > 0 for v in scrub_stats.values())
    flagged_count = len(flagged_items) if flagged_items else 0

    if has_redactions or flagged_count > 0:
        # Always show summary table (D-03: default view)
        summary_table = _build_scrub_summary_table(scrub_stats, flagged_count)
        console.print(summary_table)

        # Detail mode: show inline highlighted scrubbed text (D-01, D-03)
        if detail and scrubbed_record:
            console.print()
            console.print("[bold]Inline Redactions:[/bold]")
            for turn in scrubbed_record.trajectory.conversations:
                role_label = f"[bold]{turn.from_}:[/bold] "
                highlighted = _build_highlighted_text(turn.value)
                console.print(Text.assemble(role_label, highlighted))
                if turn.tool_calls:
                    for tc in turn.tool_calls:
                        if tc.tool_input:
                            console.print(Text.assemble(
                                "  [tool_input] ",
                                _build_highlighted_text(tc.tool_input),
                            ))
                        if tc.tool_output:
                            console.print(Text.assemble(
                                "  [tool_output] ",
                                _build_highlighted_text(tc.tool_output),
                            ))

        # Show flagged items as yellow warnings (D-02)
        if flagged_items:
            console.print()
            flagged_text = Text()
            flagged_text.append("WARNING: ", style="bold yellow")
            flagged_text.append(
                f"{len(flagged_items)} item(s) flagged for review (not auto-redacted):",
            )
            console.print(flagged_text)
            for item in flagged_items:
                console.print(f"  [yellow]* {item.text}[/yellow] — {item.reason}")
            console.print(
                "[dim]Flagged items will pass through if you submit"
                " without addressing them.[/dim]"
            )
    else:
        console.print("[green]No PII detected.[/green]")

    # First and last turn preview
    turns = record.trajectory.conversations
    if turns:
        first_turn = turns[0]
        first_value = first_turn.value[:200] + ("..." if len(first_turn.value) > 200 else "")
        console.print(Panel(
            f"[bold]{first_turn.from_}:[/bold] {first_value}",
            title="First turn",
        ))
        if len(turns) > 1:
            last_turn = turns[-1]
            last_value = last_turn.value[:200] + ("..." if len(last_turn.value) > 200 else "")
            console.print(Panel(
                f"[bold]{last_turn.from_}:[/bold] {last_value}",
                title="Last turn",
            ))


# ---------------------------------------------------------------------------
# Submit pipeline helper
# ---------------------------------------------------------------------------


def _submit_record(
    record: KajibaRecord,
    scrubbed: KajibaRecord,
    scrub_log: "object",
) -> tuple[Path, "object"]:
    """Apply full privacy pipeline and write record to outbox.

    Args:
        record: Original record (for reading consent level).
        scrubbed: Pre-scrubbed record.
        scrub_log: Scrub log from scrub_record().

    Returns:
        Tuple of (outbox_file_path, quality_result).
    """
    anonymized = anonymize_hardware(scrubbed)
    jittered = jitter_timestamp(anonymized)

    consent_level = "full"
    if record.submission and record.submission.consent_level:
        consent_level = record.submission.consent_level
    final = apply_consent_level(jittered, consent_level)

    if final.submission is None:
        final.submission = SubmissionMetadata()
    final.submission.scrub_log = scrub_log

    quality_result = compute_quality_score(final)
    final.quality = QualityMetadata(
        quality_tier=quality_result.quality_tier,
        composite_score=quality_result.composite_score,
        sub_scores=quality_result.sub_scores,
        scored_at=datetime.now(UTC),
    )

    final.compute_record_id()
    final.compute_submission_hash()

    _ensure_dirs()
    outbox_file = OUTBOX_DIR / f"record_{final.record_id}.jsonl"
    record_json = final.model_dump(mode="json", by_alias=True)
    outbox_file.write_text(
        json.dumps(record_json, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return outbox_file, quality_result


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(version=SCHEMA_VERSION, prog_name="kajiba")
def cli() -> None:
    """Kajiba — Community data pipeline for open-source local model improvement."""
    logging.basicConfig(level=logging.WARNING)
    # D-10: Show pending activity notifications before any command output
    notification = _show_pending_notifications()
    if notification:
        console.print(f"[dim]{notification}[/dim]")


@cli.command()
@click.option("--detail", is_flag=True, default=False, help="Show full inline-highlighted redactions instead of summary.")
def preview(detail: bool) -> None:
    """Preview the most recent session from staging."""
    record = _load_latest_staging()
    if record is None:
        console.print("[yellow]No sessions found in staging directory.[/yellow]")
        console.print(f"  Staging path: {STAGING_DIR}")
        return

    scrubbed, scrub_log = scrub_record(record)

    # Collect flagged items from all conversation turns
    all_flagged = []
    for turn in record.trajectory.conversations:
        all_flagged.extend(flag_org_domains(turn.value))
        if turn.tool_calls:
            for tc in turn.tool_calls:
                all_flagged.extend(flag_org_domains(tc.tool_input))
                all_flagged.extend(flag_org_domains(tc.tool_output))

    # Apply hardware anonymization for preview (show what export would look like)
    preview_record = anonymize_hardware(scrubbed)

    quality = compute_quality_score(preview_record)

    scrub_stats = scrub_log.model_dump()
    quality_dict = {
        "composite_score": quality.composite_score,
        "sub_scores": quality.sub_scores,
        "quality_tier": quality.quality_tier,
    }

    _render_preview(
        preview_record, quality_dict, scrub_stats,
        flagged_items=all_flagged,
        detail=detail,
        scrubbed_record=scrubbed if detail else None,
    )


@cli.command()
def submit() -> None:
    """Submit the most recent session after preview and confirmation."""
    record = _load_latest_staging()
    if record is None:
        console.print("[yellow]No sessions found in staging directory.[/yellow]")
        return

    scrubbed, scrub_log = scrub_record(record)

    # Collect flagged items from all conversation turns
    all_flagged = []
    for turn in record.trajectory.conversations:
        all_flagged.extend(flag_org_domains(turn.value))
        if turn.tool_calls:
            for tc in turn.tool_calls:
                all_flagged.extend(flag_org_domains(tc.tool_input))
                all_flagged.extend(flag_org_domains(tc.tool_output))

    # Apply hardware anonymization for preview display
    preview_record = anonymize_hardware(scrubbed)

    quality = compute_quality_score(preview_record)

    scrub_stats = scrub_log.model_dump()
    quality_dict = {
        "composite_score": quality.composite_score,
        "sub_scores": quality.sub_scores,
        "quality_tier": quality.quality_tier,
    }

    _render_preview(preview_record, quality_dict, scrub_stats, flagged_items=all_flagged)

    if not click.confirm("\nSubmit this record?"):
        console.print("[yellow]Submission cancelled.[/yellow]")
        return

    outbox_file, quality_result = _submit_record(record, scrubbed, scrub_log)
    console.print(f"[green]Record submitted to {outbox_file}[/green]")
    console.print(f"  Record ID: {outbox_file.stem.replace('record_', '')}")
    console.print(f"  Quality tier: {quality_result.quality_tier}")


@cli.command()
@click.argument("path", type=click.Path())
def export(path: str) -> None:
    """Export the most recent session to a local JSONL file."""
    record = _load_latest_staging()
    if record is None:
        console.print("[yellow]No sessions found in staging directory.[/yellow]")
        return

    # Apply full privacy pipeline: scrub -> anonymize -> jitter -> consent strip
    scrubbed, scrub_log = scrub_record(record)
    anonymized = anonymize_hardware(scrubbed)
    jittered = jitter_timestamp(anonymized)

    consent_level = "full"
    if record.submission and record.submission.consent_level:
        consent_level = record.submission.consent_level
    final = apply_consent_level(jittered, consent_level)

    # Attach scrub log
    if final.submission is None:
        final.submission = SubmissionMetadata()
    final.submission.scrub_log = scrub_log

    # Persist quality score in record (per D-04/D-06)
    quality_result_obj = compute_quality_score(final)
    final.quality = QualityMetadata(
        quality_tier=quality_result_obj.quality_tier,
        composite_score=quality_result_obj.composite_score,
        sub_scores=quality_result_obj.sub_scores,
        scored_at=datetime.now(UTC),
    )

    # Compute IDs
    final.compute_record_id()
    final.compute_submission_hash()

    export_path = Path(path)
    export_path.parent.mkdir(parents=True, exist_ok=True)
    record_json = final.model_dump(mode="json", by_alias=True)
    export_path.write_text(json.dumps(record_json, ensure_ascii=False) + "\n", encoding="utf-8")

    console.print(f"[green]Record exported to {export_path}[/green]")


@cli.command()
def history() -> None:
    """List past submissions from the outbox."""
    records = _load_outbox_records()
    if not records:
        console.print("[yellow]No submissions found in outbox.[/yellow]")
        console.print(f"  Outbox path: {OUTBOX_DIR}")
        return

    table = Table(title="Submission History")
    table.add_column("File", style="dim")
    table.add_column("Record ID")
    table.add_column("Type")
    table.add_column("Turns", justify="right")
    table.add_column("Created At")
    table.add_column("Quality Tier")
    table.add_column("Score", justify="right")

    for filepath, data in records:
        record_id = data.get("record_id", "—")
        record_type = data.get("record_type", "—")
        turn_count = str(data.get("trajectory", {}).get("turn_count", "—"))
        created = data.get("created_at", "—")
        if isinstance(created, str) and len(created) > 19:
            created = created[:19]

        # Read stored quality, fallback to recompute for old records (per D-11)
        quality_data = data.get("quality")
        if quality_data and "quality_tier" in quality_data:
            tier = quality_data["quality_tier"]
        else:
            try:
                rec = validate_record(data)
                tier = compute_quality_score(rec).quality_tier
            except Exception:
                tier = "?"

        score_str = (
            f"{quality_data['composite_score']:.3f}"
            if quality_data and "composite_score" in quality_data
            else "\u2014"
        )

        table.add_row(
            filepath.name, str(record_id), record_type,
            turn_count, str(created), tier, score_str,
        )

    console.print(table)


@cli.command()
def stats() -> None:
    """Show aggregate statistics from all outbox records."""
    records = _load_outbox_records()
    if not records:
        console.print("[yellow]No submissions found.[/yellow]")
        return

    total = len(records)
    tier_counts: dict[str, int] = {}
    tag_counts: dict[str, int] = {}
    pp_counts: dict[str, int] = {}

    for _, data in records:
        try:
            # Read stored quality, fallback to recompute for old records
            quality_data = data.get("quality")
            if quality_data and "quality_tier" in quality_data:
                tier = quality_data["quality_tier"]
            else:
                rec = validate_record(data)
                tier = compute_quality_score(rec).quality_tier
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

            rec = validate_record(data)
            if rec.outcome:
                for tag in rec.outcome.outcome_tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

            for pp in rec.pain_points or []:
                pp_counts[pp.category] = pp_counts.get(pp.category, 0) + 1
        except Exception:
            tier_counts["error"] = tier_counts.get("error", 0) + 1

    console.print(Panel(f"[bold]Total submissions:[/bold] {total}", title="Kajiba Stats"))

    if tier_counts:
        tier_table = Table(title="Quality Tier Distribution")
        tier_table.add_column("Tier")
        tier_table.add_column("Count", justify="right")
        for tier in ["gold", "silver", "bronze", "review_needed", "error"]:
            if tier in tier_counts:
                tier_table.add_row(tier, str(tier_counts[tier]))
        console.print(tier_table)

    if tag_counts:
        tag_table = Table(title="Most Common Outcome Tags")
        tag_table.add_column("Tag")
        tag_table.add_column("Count", justify="right")
        for tag, count in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            tag_table.add_row(tag, str(count))
        console.print(tag_table)

    if pp_counts:
        pp_table = Table(title="Most Common Pain Point Categories")
        pp_table.add_column("Category")
        pp_table.add_column("Count", justify="right")
        for cat, count in sorted(pp_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            pp_table.add_row(cat, str(count))
        console.print(pp_table)


@cli.group(invoke_without_command=True)
@click.pass_context
def config(ctx: click.Context) -> None:
    """Manage Kajiba configuration."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(config_show)


@config.command("show")
def config_show() -> None:
    """Show all configuration values."""
    config_path = Path.home() / ".hermes" / "config.yaml"

    # Build merged config: defaults + file overrides
    file_config: dict = {}
    if config_path.exists():
        try:
            import yaml  # type: ignore[import-untyped]
            with config_path.open() as f:
                full_config = yaml.safe_load(f) or {}
            file_config = full_config.get("kajiba", {})
        except ImportError:
            console.print("[dim]PyYAML not installed; showing defaults only.[/dim]")
        except Exception as exc:
            console.print(f"[yellow]Error reading config: {exc}[/yellow]")

    table = Table(title="Kajiba Configuration")
    table.add_column("Setting", style="bold")
    table.add_column("Value")
    table.add_column("Source", style="dim")

    for key, schema in VALID_CONFIG_KEYS.items():
        if key in file_config:
            table.add_row(key, str(file_config[key]), "config")
        else:
            table.add_row(key, str(schema["default"]), "default")

    table.add_row("config_path", str(config_path), "")
    table.add_row("staging_dir", str(STAGING_DIR), "")
    table.add_row("outbox_dir", str(OUTBOX_DIR), "")
    table.add_row("schema_version", SCHEMA_VERSION, "")

    console.print(table)


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """Set a configuration value."""
    if key not in VALID_CONFIG_KEYS:
        console.print(f"[red]Unknown config key: {key}[/red]")
        valid_keys = ", ".join(VALID_CONFIG_KEYS.keys())
        console.print(f"[dim]Valid keys: {valid_keys}[/dim]")
        return

    schema = VALID_CONFIG_KEYS[key]
    if schema["type"] == "choice":
        if value not in schema["choices"]:
            console.print(f"[red]Invalid value for {key}: {value}[/red]")
            console.print(f"[dim]Valid options: {', '.join(schema['choices'])}[/dim]")
            return
    elif schema["type"] == "int":
        if not value.lstrip("-").isdigit():
            console.print(f"[red]Invalid value for {key}: {value} (must be an integer)[/red]")
            return
        if "min" in schema and int(value) < schema["min"]:
            console.print(f"[red]Invalid value for {key}: {value} (minimum: {schema['min']})[/red]")
            return
    elif schema["type"] == "bool":
        if value.lower() not in ("true", "false"):
            console.print(f"[red]Invalid value for {key}: {value} (must be true or false)[/red]")
            return

    _save_config_value(key, value)
    console.print(f"[green]Set {key} = {value}[/green]")


@config.command("get")
@click.argument("key")
def config_get(key: str) -> None:
    """Get a configuration value."""
    if key not in VALID_CONFIG_KEYS:
        console.print(f"[red]Unknown config key: {key}[/red]")
        return

    default = str(VALID_CONFIG_KEYS[key]["default"])
    value = _load_config_value(key, default)

    if value == default:
        # Check if the value actually comes from config file or is just the default
        config_path = Path.home() / ".hermes" / "config.yaml"
        from_file = False
        if config_path.exists():
            try:
                import yaml  # type: ignore[import-untyped]
                with config_path.open() as f:
                    full_config = yaml.safe_load(f) or {}
                from_file = key in full_config.get("kajiba", {})
            except Exception:
                pass
        if from_file:
            console.print(f"{key} = {value}")
        else:
            console.print(f"{key} = {value} [dim](default)[/dim]")
    else:
        console.print(f"{key} = {value}")


@cli.command()
@click.option("--score", type=click.IntRange(1, 5), default=None, help="Quality rating 1-5.")
@click.option("--tags", default=None, help="Comma-separated outcome tags.")
@click.option("--comment", default=None, help="Optional free-text comment.")
def rate(score: Optional[int], tags: Optional[str], comment: Optional[str]) -> None:
    """Rate a staged record's quality.

    Attaches a user rating (1-5), optional outcome tags, and optional
    comment to a staged record. Uses interactive prompts when flags
    are not provided.
    """
    picked = _pick_staged_record()
    if picked is None:
        return
    filepath, record = picked

    # Detect interactive mode: no flags passed at all
    interactive = score is None and tags is None and comment is None

    # Interactive prompts when flags not provided (per D-07)
    if score is None:
        score = click.prompt("Rating (1-5)", type=click.IntRange(1, 5))

    tag_list: list[str] = []
    if tags is not None:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        # Validate tags against vocabulary
        for tag in tag_list:
            if tag not in OUTCOME_TAGS:
                console.print(f"[red]Unknown tag: {tag!r}[/red]")
                console.print(f"[dim]Valid tags: {', '.join(OUTCOME_TAGS)}[/dim]")
                return
    elif interactive:
        # Interactive tag selection only in fully interactive mode
        tag_input = click.prompt(
            "Outcome tags (comma-separated, or press Enter to skip)",
            default="",
            show_default=False,
        )
        if tag_input.strip():
            tag_list = [t.strip() for t in tag_input.split(",") if t.strip()]
            for tag in tag_list:
                if tag not in OUTCOME_TAGS:
                    console.print(f"[red]Unknown tag: {tag!r}[/red]")
                    return

    user_comment = comment
    if user_comment is None and interactive:
        user_comment_input = click.prompt(
            "Comment (or press Enter to skip)",
            default="",
            show_default=False,
        )
        if user_comment_input.strip():
            user_comment = user_comment_input.strip()

    # Attach or update outcome
    record.outcome = OutcomeSignals(
        user_rating=score,
        outcome_tags=tag_list,
        user_comment=user_comment if user_comment else None,
    )

    _save_staged_record(filepath, record)
    console.print(f"[green]Rating saved: {score}/5[/green]")
    if tag_list:
        console.print(f"  Tags: {', '.join(tag_list)}")
    if user_comment:
        console.print(f"  Comment: {user_comment}")


@cli.command()
@click.option(
    "--category",
    type=click.Choice([c for c in PAIN_POINT_CATEGORIES], case_sensitive=False),
    default=None,
    help="Pain point category.",
)
@click.option("--description", default=None, help="Description of the pain point.")
@click.option(
    "--severity",
    type=click.Choice(["low", "medium", "high", "critical"], case_sensitive=False),
    default=None,
    help="Severity level.",
)
def report(category: Optional[str], description: Optional[str], severity: Optional[str]) -> None:
    """Report a pain point on a staged record.

    Attaches a structured pain point (category, description, severity)
    to a staged record. Uses interactive prompts when flags are not provided.
    """
    picked = _pick_staged_record()
    if picked is None:
        return
    filepath, record = picked

    # Interactive prompts when flags not provided (per D-09)
    if category is None:
        console.print("[bold]Pain point categories:[/bold]")
        for i, cat in enumerate(PAIN_POINT_CATEGORIES, 1):
            console.print(f"  {i}. {cat}")
        cat_idx = click.prompt(
            "Select category number",
            type=click.IntRange(1, len(PAIN_POINT_CATEGORIES)),
        )
        category = PAIN_POINT_CATEGORIES[int(cat_idx) - 1]

    if description is None:
        description = click.prompt("Description")

    if severity is None:
        severity = click.prompt(
            "Severity",
            type=click.Choice(["low", "medium", "high", "critical"]),
            default="medium",
        )

    pain_point = PainPoint(
        category=category,
        severity=severity,
        description=description,
    )

    # Append to existing pain points (do not overwrite)
    if record.pain_points is None:
        record.pain_points = []
    record.pain_points.append(pain_point)

    _save_staged_record(filepath, record)
    console.print(f"[green]Pain point reported: {category} ({severity})[/green]")
    console.print(f"  {description}")


# ---------------------------------------------------------------------------
# Review command (ad-hoc contribution mode)
# ---------------------------------------------------------------------------


@cli.command()
def review() -> None:
    """Review and approve staged records one at a time.

    Shows each pending staged record with a full preview (quality scores,
    scrubbing summary, flagged items), then prompts for action:
    approve (submit to outbox), reject (remove from staging), skip, or quit.
    """
    staged = _load_all_staging()
    if not staged:
        console.print("[yellow]No records in staging to review.[/yellow]")
        return

    approved = 0
    rejected = 0
    skipped = 0

    for filepath, record in staged:
        console.print(f"\n[bold]Reviewing:[/bold] {filepath.name}")

        # Reuse existing preview infrastructure (per D-01)
        scrubbed, scrub_log = scrub_record(record)

        # Collect flagged items from all conversation turns
        all_flagged: list = []
        for turn in record.trajectory.conversations:
            all_flagged.extend(flag_org_domains(turn.value))
            if turn.tool_calls:
                for tc in turn.tool_calls:
                    all_flagged.extend(flag_org_domains(tc.tool_input))
                    all_flagged.extend(flag_org_domains(tc.tool_output))

        preview_record = anonymize_hardware(scrubbed)
        quality = compute_quality_score(preview_record)
        scrub_stats = scrub_log.model_dump()
        quality_dict = {
            "composite_score": quality.composite_score,
            "sub_scores": quality.sub_scores,
            "quality_tier": quality.quality_tier,
        }

        _render_preview(
            preview_record, quality_dict, scrub_stats,
            flagged_items=all_flagged,
        )

        # Prompt: approve / reject / skip / quit (per D-03, UI-SPEC)
        action = click.prompt(
            "Action",
            type=click.Choice(
                ["approve", "reject", "skip", "quit"],
                case_sensitive=False,
            ),
            default="skip",
        )

        if action == "approve":
            try:
                outbox_file, _qr = _submit_record(record, scrubbed, scrub_log)
                filepath.unlink()  # Only remove staging after successful submit
                console.print(
                    f"[green]Approved and submitted: {outbox_file.name}[/green]"
                )
                approved += 1
            except Exception as exc:
                console.print(
                    f"[red]Error submitting record: {exc}[/red]"
                )
                console.print(
                    "[yellow]Record kept in staging for retry.[/yellow]"
                )
        elif action == "reject":
            filepath.unlink()
            console.print(
                "[red]Record rejected and removed from staging.[/red]"
            )
            rejected += 1
        elif action == "skip":
            console.print("[dim]Skipped.[/dim]")
            skipped += 1
        elif action == "quit":
            break

    console.print(
        f"\n[bold]Review complete:[/bold] {approved} approved, "
        f"{rejected} rejected, {skipped} skipped"
    )


# ---------------------------------------------------------------------------
# Consumer commands: shared filter options
# ---------------------------------------------------------------------------


def _filter_options(func):
    """Shared filter options for browse and download commands (D-03)."""
    func = click.option(
        "--tier", default=None,
        type=click.Choice(["gold", "silver", "bronze", "review_needed"]),
        help="Filter by quality tier.",
    )(func)
    func = click.option(
        "--model", default=None,
        help="Filter by model name (case-insensitive substring match).",
    )(func)
    return func


def _fetch_catalog(gh_ops: GitHubOps, dataset_repo: str) -> Optional[dict]:
    """Fetch and parse catalog.json from the dataset repo.

    Handles error states per D-04: gh not found, auth failure, catalog
    not found (404), network error. Prints appropriate Rich messages
    and returns None on failure.

    Args:
        gh_ops: Initialized GitHubOps instance.
        dataset_repo: Repository string for error messages.

    Returns:
        Parsed catalog dict, or None on any failure.
    """
    result = gh_ops.get_file_contents("catalog.json", raw=True)
    if result.returncode == -1:
        console.print(
            "[red]Error:[/red] gh CLI not found. "
            "Install from https://cli.github.com/"
        )
        return None
    if not result.success:
        if "404" in result.stderr or "Not Found" in result.stderr:
            console.print(
                "[yellow]No records published yet.[/yellow] "
                "Run `kajiba publish` to contribute."
            )
        else:
            console.print(
                f"[red]Error:[/red] Could not fetch catalog from {dataset_repo}. "
                f"{result.stderr.strip()}"
            )
            console.print(
                "[dim]Check `gh auth status` for authentication.[/dim]"
            )
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        console.print(
            f"[red]Error:[/red] Invalid catalog.json from {dataset_repo}."
        )
        return None


def _render_no_match(catalog: dict, model: Optional[str], tier: Optional[str]) -> None:
    """Show no-match feedback with available options (D-11)."""
    all_models = catalog.get("models", {})
    filter_parts = []
    if model:
        filter_parts.append(f'--model "{model}"')
    if tier:
        filter_parts.append(f'--tier "{tier}"')
    console.print(
        f"[yellow]No records match {' '.join(filter_parts)}.[/yellow]"
    )
    if all_models:
        model_names = sorted(all_models.keys())
        console.print(f"Available models: {', '.join(model_names)}")
    all_tiers: set[str] = set()
    for m_info in all_models.values():
        all_tiers.update(m_info.get("tiers", {}).keys())
    if all_tiers:
        console.print(f"Available tiers: {', '.join(sorted(all_tiers))}")


def _render_browse_summary(catalog: dict) -> None:
    """Render top-level browse summary table (D-01)."""
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

        scores = []
        for t_info in tiers.values():
            avg = t_info.get("avg_quality_score", 0)
            if avg > 0:
                scores.append(avg)
        avg_str = f"{sum(scores) / len(scores):.2f}" if scores else "---"

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


def _render_browse_model(model_slug: str, model_info: dict) -> None:
    """Render drill-down view for a single model (D-02)."""
    display = model_info.get("display_name", model_slug)
    params = model_info.get("parameter_counts", [])
    quants = model_info.get("quantizations", [])
    ctx_wins = model_info.get("context_windows", [])

    meta_lines = [f"[bold]Model:[/bold] {display}"]
    meta_lines.append(
        f"[bold]Parameters:[/bold] {', '.join(str(p) for p in params)}"
        if params else "[bold]Parameters:[/bold] [dim]---[/dim]"
    )
    meta_lines.append(
        f"[bold]Quantization:[/bold] {', '.join(str(q) for q in quants)}"
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

    # Hardware distribution summary line
    hw = model_info.get("hardware_distribution", {})
    if hw:
        hw_items = sorted(hw.items(), key=lambda x: x[1], reverse=True)[:5]
        hw_str = ", ".join(f"{name} ({count})" for name, count in hw_items)
        console.print(f"[dim]Hardware: {hw_str}[/dim]")


@cli.command()
@_filter_options
@click.option("--repo", default=None, help="Dataset repo (owner/repo).")
def browse(model: Optional[str], tier: Optional[str], repo: Optional[str]) -> None:
    """Browse the dataset catalog.

    Shows available models, quality tiers, and record counts.
    Use --model <name> for detailed model metadata.
    """
    # Resolve repo
    dataset_repo = repo if repo else _load_config_value(
        "dataset_repo", DEFAULT_DATASET_REPO,
    )

    # Fetch catalog
    gh_ops = GitHubOps(upstream_repo=dataset_repo)
    catalog = _fetch_catalog(gh_ops, dataset_repo)
    if catalog is None:
        raise SystemExit(1)

    # Check empty catalog
    if not catalog.get("models"):
        console.print(
            "[yellow]No records published yet.[/yellow] "
            "Run `kajiba publish` to contribute."
        )
        return

    # Apply filters
    filtered = filter_catalog(catalog, model=model, tier=tier)

    # Check no matches
    if not filtered.get("models"):
        _render_no_match(catalog, model, tier)
        return

    # Drill-down if --model specified and exactly one model matches
    if model and len(filtered["models"]) == 1:
        slug = next(iter(filtered["models"]))
        _render_browse_model(slug, filtered["models"][slug])
    else:
        _render_browse_summary(filtered)


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------


def _collect_download_shards(
    catalog: dict,
    model: Optional[str] = None,
    tier: Optional[str] = None,
) -> list[dict]:
    """Collect shard file paths and metadata from filtered catalog.

    Args:
        catalog: Full catalog dict.
        model: Model filter (passed to filter_catalog).
        tier: Tier filter (passed to filter_catalog).

    Returns:
        List of dicts with 'path', 'model', 'tier' keys.
    """
    filtered = filter_catalog(catalog, model=model, tier=tier)
    shards: list[dict] = []
    for slug, info in filtered.get("models", {}).items():
        for tier_name, tier_info in info.get("tiers", {}).items():
            for shard_name in tier_info.get("shards", []):
                shards.append({
                    "path": f"data/{slug}/{tier_name}/{shard_name}",
                    "model": slug,
                    "tier": tier_name,
                })
    return shards


def _format_size(size_bytes: int) -> str:
    """Format byte count as human-readable size string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def _download_shards(
    gh_ops: GitHubOps,
    shards: list[dict],
    output_dir: Path,
) -> tuple[int, int, int, int]:
    """Download shard files with Rich progress tracking.

    Skips files that already exist at the destination.

    Args:
        gh_ops: GitHubOps instance for file fetching.
        shards: List of shard dicts with 'path', 'model', 'tier' keys.
        output_dir: Base output directory.

    Returns:
        Tuple of (downloaded_count, skipped_count, total_records, total_bytes).
    """
    downloaded = 0
    skipped = 0
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
            # Build destination using forward-slash split for cross-platform (Pitfall 7)
            dest = output_dir / Path(*shard_path.split("/"))

            # Skip if exists
            if dest.exists():
                console.print(
                    f"  [dim]Skipped (already exists): {shard_path}[/dim]"
                )
                skipped += 1
                progress.update(task, advance=1)
                continue

            result = gh_ops.get_file_contents(shard_path, raw=True)
            if result.success:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(result.stdout, encoding="utf-8")
                file_bytes = len(result.stdout.encode("utf-8"))
                total_bytes += file_bytes
                # Count non-empty lines as records
                total_records += sum(
                    1 for line in result.stdout.split("\n") if line.strip()
                )
                downloaded += 1
            else:
                console.print(
                    f"  [red]Failed to download: {shard_path}[/red]"
                )

            progress.update(task, advance=1)

    return downloaded, skipped, total_records, total_bytes


@cli.command()
@_filter_options
@click.option("--output", "output_path", default=None, type=click.Path(),
              help="Output directory. Default: ~/.hermes/kajiba/downloads/")
@click.option("--repo", default=None, help="Dataset repo (owner/repo).")
def download(
    model: Optional[str],
    tier: Optional[str],
    output_path: Optional[str],
    repo: Optional[str],
) -> None:
    """Download a filtered subset of the dataset.

    Fetches matching JSONL shard files from the dataset repository
    to a local directory. Use --model and --tier to filter.
    """
    # Resolve repo
    dataset_repo = repo if repo else _load_config_value(
        "dataset_repo", DEFAULT_DATASET_REPO,
    )

    # Fetch catalog
    gh_ops = GitHubOps(upstream_repo=dataset_repo)
    catalog = _fetch_catalog(gh_ops, dataset_repo)
    if catalog is None:
        raise SystemExit(1)

    # Check empty catalog
    if not catalog.get("models"):
        console.print(
            "[yellow]No records published yet.[/yellow] "
            "Run `kajiba publish` to contribute."
        )
        return

    # Collect matching shards
    shards = _collect_download_shards(catalog, model=model, tier=tier)

    if not shards:
        _render_no_match(catalog, model, tier)
        return

    # Unfiltered confirmation (D-12)
    if not model and not tier:
        total_recs = catalog.get("total_records", 0)
        total_size = _format_size(catalog.get("total_size_bytes", 0))
        if not click.confirm(
            f"This will download all {total_recs} record(s) ({total_size}). Continue?",
            default=False,
        ):
            return

    # Resolve output directory (D-06)
    output_dir = Path(output_path) if output_path else DOWNLOADS_DIR

    # Download shards with progress (D-07)
    downloaded, skipped, total_records, total_bytes = _download_shards(
        gh_ops, shards, output_dir,
    )

    # Completion summary
    size_str = _format_size(total_bytes)
    if downloaded > 0:
        console.print(
            f"[green]Downloaded {downloaded} shard(s), "
            f"{total_records} record(s), {size_str}.[/green]"
        )
    if skipped > 0:
        console.print(
            f"[dim]Skipped {skipped} shard(s) (already exist).[/dim]"
        )
    if downloaded > 0:
        console.print(f"[dim]Saved to {output_dir}[/dim]")


# ---------------------------------------------------------------------------
# Publishing commands
# ---------------------------------------------------------------------------



@cli.command()
@click.option("--repo", default=None, help="Dataset repository (owner/repo). Default: config or CuervoDoesIt/kajiba-dataset")
@click.option("--dry-run", is_flag=True, help="Show what would be published without actually pushing")
def publish(repo: Optional[str], dry_run: bool) -> None:
    """Publish outbox records to the dataset repository via PR.

    Implements the full D-04 workflow: auth check, outbox load, consent
    re-verification, fork/clone, branch, write shards, catalog, readme,
    commit, push, PR creation.
    """
    # Step 1: Resolve dataset repo
    if repo is None:
        dataset_repo = _load_config_value("dataset_repo", DEFAULT_DATASET_REPO)
    else:
        dataset_repo = repo
    repo_name = dataset_repo.split("/")[-1]

    console.print(f"[bold]Publishing to:[/bold] {dataset_repo}")

    # Step 2: Check gh auth
    gh_ops = GitHubOps(upstream_repo=dataset_repo)
    auth_result = gh_ops.check_auth()
    if auth_result.returncode == -1:
        console.print(
            "[red]Error:[/red] gh CLI not found. "
            "Install from https://cli.github.com/"
        )
        raise SystemExit(1)
    if not auth_result.success:
        console.print(
            "[red]Error:[/red] Not authenticated. "
            "Run `gh auth login` first."
        )
        raise SystemExit(1)
    console.print("[green]  Auth check passed[/green]")

    # Step 3: Load outbox records
    outbox_records = _load_outbox_records()
    if not outbox_records:
        console.print(
            "[yellow]No records to publish.[/yellow] "
            "Submit records first with `kajiba submit`."
        )
        raise SystemExit(1)
    console.print(f"[green]  Loaded {len(outbox_records)} outbox record(s)[/green]")

    # Step 4: Re-verify consent (D-03)
    verified_records: list[dict] = []
    model_names: list[str] = []
    tier_names: list[str] = []
    for path, data in outbox_records:
        try:
            record = validate_record(data)
            consent_level = "full"
            if record.submission and record.submission.consent_level:
                consent_level = record.submission.consent_level
            stripped = apply_consent_level(record, consent_level)
            rec_dict = stripped.model_dump(mode="json", by_alias=True)
            verified_records.append(rec_dict)

            # Collect model and tier info for PR metadata
            if record.model and record.model.model_name:
                model_names.append(record.model.model_name)
            else:
                model_names.append("unknown")
            if record.quality and record.quality.quality_tier:
                tier_names.append(record.quality.quality_tier)
            else:
                tier_names.append("review_needed")
        except Exception as exc:
            logger.warning("Skipping invalid record from %s: %s", path, exc)
            console.print(f"[yellow]  Skipping invalid record: {path.name}[/yellow]")

    if not verified_records:
        console.print("[red]Error:[/red] No valid records after consent verification.")
        raise SystemExit(1)
    console.print(f"[green]  Consent verified: {len(verified_records)} record(s)[/green]")

    # Step 5: Get username and fork
    username_result = gh_ops.get_username()
    if not username_result.success:
        console.print(f"[red]Error:[/red] Could not get GitHub username: {username_result.stderr}")
        raise SystemExit(1)
    username = username_result.stdout.strip()
    console.print(f"[green]  GitHub user: {username}[/green]")

    fork_result = gh_ops.fork_repo()
    if not fork_result.success:
        console.print(f"[red]Error:[/red] Failed to fork repository: {fork_result.stderr}")
        raise SystemExit(1)
    console.print("[green]  Fork ready[/green]")

    # Step 6: Clone or update fork
    clone_dir = CLONE_DIR
    if clone_dir.exists() and (clone_dir / ".git").is_dir():
        pull_result = gh_ops.pull_latest(str(clone_dir))
        if not pull_result.success:
            console.print(f"[red]Error:[/red] Failed to update clone: {pull_result.stderr}")
            raise SystemExit(1)
        console.print("[green]  Clone updated[/green]")
    else:
        fork_url = f"https://github.com/{username}/{repo_name}.git"
        clone_result = gh_ops.clone_fork(str(clone_dir), fork_url)
        if not clone_result.success:
            console.print(f"[red]Error:[/red] Failed to clone fork: {clone_result.stderr}")
            raise SystemExit(1)
        console.print("[green]  Fork cloned[/green]")

    # Step 7: Create branch
    branch_name = f"kajiba/publish-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    branch_result = gh_ops.create_branch(str(clone_dir), branch_name)
    if not branch_result.success:
        console.print(f"[red]Error:[/red] Failed to create branch: {branch_result.stderr}")
        raise SystemExit(1)
    console.print(f"[green]  Branch created: {branch_name}[/green]")

    # Step 8: Write records
    written_count = write_records_to_shards(clone_dir, verified_records)
    console.print(f"[green]  Wrote {written_count} record(s) to shards[/green]")

    # Step 9: Generate catalog and README
    catalog = generate_catalog(clone_dir)
    catalog_path = clone_dir / "catalog.json"
    catalog_path.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    readme_content = generate_readme(catalog)
    readme_path = clone_dir / "README.md"
    readme_path.write_text(readme_content, encoding="utf-8")
    console.print("[green]  Catalog and README regenerated[/green]")

    # Step 10: Dry run check
    if dry_run:
        console.print()
        console.print(Panel(
            f"[bold]Dry run summary[/bold]\n"
            f"Records: {written_count}\n"
            f"Models: {', '.join(sorted(set(model_names)))}\n"
            f"Tiers: {', '.join(sorted(set(tier_names)))}\n"
            f"Branch: {branch_name}\n"
            f"No changes pushed.",
            title="Publish Dry Run",
        ))
        return

    # Step 11: Commit, push, PR
    commit_result = gh_ops.commit_all(
        str(clone_dir),
        f"kajiba: add {written_count} record(s)",
    )
    if not commit_result.success:
        console.print(f"[red]Error:[/red] Failed to commit: {commit_result.stderr}")
        raise SystemExit(1)
    console.print("[green]  Changes committed[/green]")

    push_result = gh_ops.push_branch(str(clone_dir), branch_name)
    if not push_result.success:
        console.print(f"[red]Error:[/red] Failed to push: {push_result.stderr}")
        raise SystemExit(1)
    console.print("[green]  Branch pushed[/green]")

    pr_title = build_publish_pr_title(written_count, model_names)
    pr_body = build_publish_pr_body(
        written_count, model_names, tier_names, __version__,
    )
    head = f"{username}:{branch_name}"
    pr_result = gh_ops.create_pr(pr_title, pr_body, head)

    if not pr_result.success:
        console.print(
            f"[yellow]Warning:[/yellow] Records pushed to fork but PR creation failed.\n"
            f"  {pr_result.stderr}\n"
            f"  Create PR manually at https://github.com/{username}/{repo_name}"
        )
        return

    pr_url = pr_result.stdout.strip()
    console.print()
    console.print(Panel(
        f"[bold green]Published successfully![/bold green]\n"
        f"Records: {written_count}\n"
        f"Models: {', '.join(sorted(set(model_names)))}\n"
        f"Tiers: {', '.join(sorted(set(tier_names)))}\n"
        f"PR: {pr_url}",
        title="Publish Complete",
    ))


@cli.command()
@click.argument("record_id")
@click.option("--repo", default=None, help="Dataset repository (owner/repo)")
@click.option("--reason", default="contributor_request", help="Reason for deletion")
def delete(record_id: str, repo: Optional[str], reason: str) -> None:
    """Request deletion of a record from the dataset repository via PR.

    Implements D-09 deletion via index file (not physical removal) and
    D-10 any record by ID (no identity verification).

    RECORD_ID is the unique identifier of the record to delete.
    """
    # Step 1: Resolve dataset repo
    if repo is None:
        dataset_repo = _load_config_value("dataset_repo", DEFAULT_DATASET_REPO)
    else:
        dataset_repo = repo
    repo_name = dataset_repo.split("/")[-1]

    console.print(f"[bold]Requesting deletion from:[/bold] {dataset_repo}")
    console.print(f"  Record ID: {record_id}")
    console.print(f"  Reason: {reason}")

    # Step 2: Check gh auth
    gh_ops = GitHubOps(upstream_repo=dataset_repo)
    auth_result = gh_ops.check_auth()
    if auth_result.returncode == -1:
        console.print(
            "[red]Error:[/red] gh CLI not found. "
            "Install from https://cli.github.com/"
        )
        raise SystemExit(1)
    if not auth_result.success:
        console.print(
            "[red]Error:[/red] Not authenticated. "
            "Run `gh auth login` first."
        )
        raise SystemExit(1)
    console.print("[green]  Auth check passed[/green]")

    # Step 3: Get username and ensure fork
    username_result = gh_ops.get_username()
    if not username_result.success:
        console.print(f"[red]Error:[/red] Could not get GitHub username: {username_result.stderr}")
        raise SystemExit(1)
    username = username_result.stdout.strip()

    fork_result = gh_ops.fork_repo()
    if not fork_result.success:
        console.print(f"[red]Error:[/red] Failed to fork repository: {fork_result.stderr}")
        raise SystemExit(1)
    console.print("[green]  Fork ready[/green]")

    # Step 4: Clone or update
    clone_dir = CLONE_DIR
    if clone_dir.exists() and (clone_dir / ".git").is_dir():
        pull_result = gh_ops.pull_latest(str(clone_dir))
        if not pull_result.success:
            console.print(f"[red]Error:[/red] Failed to update clone: {pull_result.stderr}")
            raise SystemExit(1)
        console.print("[green]  Clone updated[/green]")
    else:
        fork_url = f"https://github.com/{username}/{repo_name}.git"
        clone_result = gh_ops.clone_fork(str(clone_dir), fork_url)
        if not clone_result.success:
            console.print(f"[red]Error:[/red] Failed to clone fork: {clone_result.stderr}")
            raise SystemExit(1)
        console.print("[green]  Fork cloned[/green]")

    # Step 5: Create branch
    branch_name = f"kajiba/delete-{record_id[:12]}"
    branch_result = gh_ops.create_branch(str(clone_dir), branch_name)
    if not branch_result.success:
        console.print(f"[red]Error:[/red] Failed to create branch: {branch_result.stderr}")
        raise SystemExit(1)
    console.print(f"[green]  Branch created: {branch_name}[/green]")

    # Step 6: Append deletion entry
    deletion_entry = create_deletion_entry(record_id, reason)
    deletions_path = clone_dir / "deletions.jsonl"
    with open(deletions_path, "a", encoding="utf-8") as f:
        f.write(deletion_entry + "\n")
    console.print("[green]  Deletion entry appended to deletions.jsonl[/green]")

    # Step 7: Commit, push, PR
    commit_result = gh_ops.commit_all(
        str(clone_dir),
        f"kajiba: request deletion of {record_id}",
    )
    if not commit_result.success:
        console.print(f"[red]Error:[/red] Failed to commit: {commit_result.stderr}")
        raise SystemExit(1)
    console.print("[green]  Changes committed[/green]")

    push_result = gh_ops.push_branch(str(clone_dir), branch_name)
    if not push_result.success:
        console.print(f"[red]Error:[/red] Failed to push: {push_result.stderr}")
        raise SystemExit(1)
    console.print("[green]  Branch pushed[/green]")

    pr_title = build_deletion_pr_title(record_id)
    pr_body = build_deletion_pr_body(record_id, __version__)
    head = f"{username}:{branch_name}"
    pr_result = gh_ops.create_pr(pr_title, pr_body, head)

    if not pr_result.success:
        console.print(
            f"[yellow]Warning:[/yellow] Deletion pushed to fork but PR creation failed.\n"
            f"  {pr_result.stderr}\n"
            f"  Create PR manually at https://github.com/{username}/{repo_name}"
        )
        return

    pr_url = pr_result.stdout.strip()
    console.print()
    console.print(Panel(
        f"[bold green]Deletion request submitted![/bold green]\n"
        f"Record ID: {record_id}\n"
        f"PR: {pr_url}",
        title="Deletion Complete",
    ))
