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

from kajiba.privacy import anonymize_hardware, apply_consent_level, jitter_timestamp
from kajiba.schema import SCHEMA_VERSION, KajibaRecord, SubmissionMetadata, validate_record
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


def _render_preview(
    record: KajibaRecord,
    quality_result: dict,
    scrub_stats: dict,
    flagged_items: Optional[list] = None,
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

    if record.outcome:
        rating_str = f"{record.outcome.user_rating}/5"
        if record.outcome.outcome_tags:
            rating_str += f" — {', '.join(record.outcome.outcome_tags)}"
        table.add_row("Rating", rating_str)

    # Quality
    tier = quality_result.get("quality_tier", "unknown")
    tier_colors = {"gold": "yellow", "silver": "white", "bronze": "dark_orange", "review_needed": "red"}
    tier_color = tier_colors.get(tier, "white")
    score_str = f"{quality_result.get('composite_score', 0):.3f} [{tier_color}]({tier})[/{tier_color}]"
    table.add_row("Quality score", score_str)

    # Sub-scores
    for name, value in quality_result.get("sub_scores", {}).items():
        table.add_row(f"  {name}", f"{value:.3f}")

    console.print(table)

    # PII scrub results
    if any(v > 0 for v in scrub_stats.values()):
        scrub_table = Table(title="PII Scrubbing Results", show_header=False)
        scrub_table.add_column("Category", style="bold")
        scrub_table.add_column("Count")
        for cat, count in scrub_stats.items():
            if count > 0:
                scrub_table.add_row(cat, str(count))
        console.print(scrub_table)
    else:
        console.print("[green]No PII detected.[/green]")

    # Show flagged items (per D-09)
    if flagged_items:
        console.print()
        flagged_text = Text()
        flagged_text.append("WARNING: ", style="bold yellow")
        flagged_text.append(f"{len(flagged_items)} item(s) flagged for review (not auto-redacted):")
        console.print(flagged_text)
        for item in flagged_items:
            console.print(f"  [yellow]* {item.text}[/yellow] — {item.reason}")
        console.print(
            "[dim]Flagged items will pass through if you submit"
            " without addressing them (per D-11).[/dim]"
        )

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
# CLI commands
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(version=SCHEMA_VERSION, prog_name="kajiba")
def cli() -> None:
    """Kajiba — Community data pipeline for open-source local model improvement."""
    logging.basicConfig(level=logging.WARNING)


@cli.command()
def preview() -> None:
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

    _render_preview(preview_record, quality_dict, scrub_stats, flagged_items=all_flagged)


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

    # Apply full privacy pipeline: scrub -> anonymize -> jitter -> consent strip
    anonymized = anonymize_hardware(scrubbed)
    jittered = jitter_timestamp(anonymized)

    # Read consent level from record's submission metadata (per D-03)
    consent_level = "full"
    if record.submission and record.submission.consent_level:
        consent_level = record.submission.consent_level
    final = apply_consent_level(jittered, consent_level)

    # Attach scrub log to final record
    if final.submission is None:
        final.submission = SubmissionMetadata()
    final.submission.scrub_log = scrub_log

    # Compute IDs and write to outbox
    final.compute_record_id()
    final.compute_submission_hash()

    _ensure_dirs()
    outbox_file = OUTBOX_DIR / f"record_{final.record_id}.jsonl"
    record_json = final.model_dump(mode="json", by_alias=True)
    outbox_file.write_text(json.dumps(record_json, ensure_ascii=False) + "\n", encoding="utf-8")

    console.print(f"[green]Record submitted to {outbox_file}[/green]")
    console.print(f"  Record ID: {final.record_id}")
    console.print(f"  Quality tier: {quality.quality_tier}")


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

    for filepath, data in records:
        record_id = data.get("record_id", "—")
        record_type = data.get("record_type", "—")
        turn_count = str(data.get("trajectory", {}).get("turn_count", "—"))
        created = data.get("created_at", "—")
        if isinstance(created, str) and len(created) > 19:
            created = created[:19]
        # Re-score for tier display
        try:
            rec = validate_record(data)
            tier = compute_quality_score(rec).quality_tier
        except Exception:
            tier = "?"

        table.add_row(filepath.name, str(record_id), record_type, turn_count, str(created), tier)

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
            rec = validate_record(data)
            tier = compute_quality_score(rec).quality_tier
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

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


@cli.command()
def config() -> None:
    """Show current Kajiba configuration."""
    config_path = Path.home() / ".hermes" / "config.yaml"

    kajiba_config = {
        "consent_level": "full",
        "auto_submit": False,
        "llm_pii_scrub": True,
        "scrub_strictness": "high",
    }

    if config_path.exists():
        try:
            import yaml  # type: ignore[import-untyped]
            with config_path.open() as f:
                full_config = yaml.safe_load(f) or {}
            if "kajiba" in full_config:
                kajiba_config.update(full_config["kajiba"])
        except ImportError:
            console.print("[dim]PyYAML not installed; showing defaults only.[/dim]")
        except Exception as exc:
            console.print(f"[yellow]Error reading config: {exc}[/yellow]")

    table = Table(title="Kajiba Configuration")
    table.add_column("Setting", style="bold")
    table.add_column("Value")

    for key, value in kajiba_config.items():
        table.add_row(key, str(value))

    table.add_row("config_path", str(config_path))
    table.add_row("staging_dir", str(STAGING_DIR))
    table.add_row("outbox_dir", str(OUTBOX_DIR))
    table.add_row("schema_version", SCHEMA_VERSION)

    console.print(table)
