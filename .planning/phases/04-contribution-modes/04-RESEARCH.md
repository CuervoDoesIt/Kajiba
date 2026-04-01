# Phase 4: Contribution Modes - Research

**Researched:** 2026-04-01
**Domain:** CLI command architecture, config management, session lifecycle hooks, quality-gated auto-submission
**Confidence:** HIGH

## Summary

Phase 4 adds two contribution modes (ad-hoc and continuous) to the Kajiba pipeline. The implementation touches three primary areas: (1) a new `kajiba review` CLI command for one-at-a-time manual review of staged records, (2) restructuring the existing `config` command into a group with `set`, `get`, and `show` subcommands, and (3) extending `KajibaCollector.on_session_end()` to optionally auto-submit records that meet a quality threshold in continuous mode.

The codebase is well-prepared for this work. The `_load_config_value()` helper already reads from `~/.hermes/config.yaml`, the `_render_preview()` function provides reusable record display, `_load_all_staging()` returns all staged records, and the full submit pipeline (scrub -> anonymize -> jitter -> consent strip -> quality score -> IDs -> write) is established in the `submit` command. The `auto_submit: False` config default confirms the project anticipated this feature.

**Primary recommendation:** Extract the submit pipeline into a reusable `_submit_record()` helper function, then call it from both the `review` approve flow and the continuous mode auto-submit path. This avoids duplicating the 15-line privacy+quality+write sequence.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Preview-then-approve flow. New `kajiba review` command shows each pending staged record with full preview (reuses existing preview infrastructure), then prompts approve/reject/skip.
- **D-02:** User-initiated review. Records land in staging silently after session end. User explicitly runs `kajiba review` when ready. Does not auto-prompt or block the agent session. Consistent with fault-tolerant collector pattern.
- **D-03:** One record at a time. `kajiba review` shows the most recent staged record, user decides, then moves to next. Focused attention per record rather than batch overview.
- **D-04:** Inline at session end. `KajibaCollector.on_session_end` checks if mode is continuous, computes quality score, and if the record meets the threshold, calls the submit pipeline directly. No separate background process or daemon. Extends existing fault-tolerant collector pattern.
- **D-05:** Auto-submit to local outbox only. Continuous mode moves qualifying records from staging to outbox. Publishing to GitHub still requires explicit `kajiba publish`. Keeps network operations user-initiated (local-first principle).
- **D-06:** Subcommand pattern: `kajiba config set <key> <value>` and `kajiba config get <key>`. Existing `kajiba config` display becomes `kajiba config show`. Familiar CLI pattern (like `git config`).
- **D-07:** Immediate effect -- config read from `~/.hermes/config.yaml` at each command invocation. Mode switch is just `kajiba config set contribution_mode continuous`; next session uses the new value. Consistent with existing `_load_config_value()` pattern.
- **D-08:** Configurable keys for this phase: `contribution_mode` (ad-hoc/continuous), `min_quality_tier` (gold/silver/bronze), `consent_level`, `auto_submit_interval` (reserved for future -- not used in inline trigger but stored for potential background mode later).
- **D-09:** Queue for manual review. In continuous mode, records scoring below the configured threshold stay in staging. User can review them later via `kajiba review`. Nothing is lost, nothing is auto-discarded.
- **D-10:** Silent with summary on next CLI use. Auto-submit activity happens silently during sessions. Next time user runs any kajiba command, a brief summary appears: "2 records auto-submitted, 1 queued for review". Non-intrusive notification.

### Claude's Discretion
- Rich formatting for the review command (panel layout, approve/reject prompt style)
- Exact summary notification format and placement in CLI output
- Config validation (e.g., rejecting invalid tier names, showing available options)
- How `auto_submit_interval` config key is stored and documented (placeholder for future use)
- Activity log format for continuous mode events

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CONT-01 | User can contribute in ad-hoc mode -- review and approve each record before submission | `kajiba review` command using `_load_all_staging()`, `_render_preview()`, and the extracted submit helper. One-at-a-time flow per D-03. |
| CONT-02 | User can contribute in continuous mode -- records meeting configured quality threshold are auto-submitted | `on_session_end()` extension reads `contribution_mode` config, calls `compute_quality_score()`, compares tier, calls submit pipeline inline. Fault-tolerant wrapper. |
| CONT-03 | User can switch between ad-hoc and continuous modes via `kajiba config` | `kajiba config set contribution_mode <value>` writes to `~/.hermes/config.yaml`. Read at each invocation via `_load_config_value()`. |
| CONT-04 | Continuous mode parameters are configurable: minimum quality tier, consent level, auto-submit interval | `kajiba config set` supports `min_quality_tier`, `consent_level`, `auto_submit_interval` keys with validation. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Click | 8.3.1 (installed) | CLI framework, command groups | Already established in project; `@cli.group()` with `invoke_without_command` for config subcommands |
| Rich | 13.0+ (installed) | Terminal rendering for review command | Already established; `Console`, `Panel`, `Table` used throughout CLI |
| Pydantic | 2.12.5 (installed) | Schema validation, model_dump/model_validate | Already established; all records are Pydantic models |
| PyYAML | soft dependency | Config read/write to `~/.hermes/config.yaml` | Already used (lazy import) for config reading; needed for writing |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.2 (installed) | Test runner | All tests |
| click.testing.CliRunner | (bundled with Click) | CLI command testing | Testing review, config set/get/show commands |

No new dependencies required. Everything needed is already installed or available as soft dependency.

## Architecture Patterns

### Recommended Changes to Existing Structure
```
src/kajiba/
  cli.py              # MODIFY: add review command, restructure config -> group
  collector.py        # MODIFY: extend on_session_end() for continuous mode
  (no new files)      # All changes fit within existing modules
```

### Pattern 1: Extract Submit Pipeline Helper
**What:** Extract the 15-line submit pipeline (scrub -> anonymize -> jitter -> consent -> quality -> IDs -> write) from the `submit` command into a reusable `_submit_record()` function.
**When to use:** Called by `kajiba review` approve flow, continuous mode auto-submit, and the existing `submit` command.
**Why:** The submit pipeline is currently inlined in the `submit` command (cli.py lines 440-475). Both new code paths need the same sequence. Duplication would create divergence risk.
**Example:**
```python
def _submit_record(
    record: KajibaRecord,
    scrubbed: KajibaRecord,
    scrub_log: ScrubLog,
) -> tuple[Path, QualityResult]:
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
```

### Pattern 2: Click Group with invoke_without_command
**What:** Convert `config` from `@cli.command()` to `@cli.group(invoke_without_command=True)` with `set`, `get`, `show` subcommands. When invoked without a subcommand, falls through to `show` behavior for backward compatibility.
**When to use:** D-06 requirement.
**Example:**
```python
@cli.group(invoke_without_command=True)
@click.pass_context
def config(ctx: click.Context) -> None:
    """Manage Kajiba configuration."""
    if ctx.invoked_subcommand is None:
        # Backward compat: bare `kajiba config` acts like `kajiba config show`
        ctx.invoke(config_show)


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """Set a configuration value."""
    ...


@config.command("get")
@click.argument("key")
def config_get(key: str) -> None:
    """Get a configuration value."""
    ...


@config.command("show")
def config_show() -> None:
    """Show all configuration values."""
    # Move existing config command body here
    ...
```

### Pattern 3: Tier Comparison for Quality Threshold
**What:** Ordinal comparison of quality tiers for continuous mode threshold check.
**When to use:** In `on_session_end()` when checking if a record meets the minimum quality tier.
**Example:**
```python
TIER_ORDER: dict[str, int] = {
    "gold": 4,
    "silver": 3,
    "bronze": 2,
    "review_needed": 1,
}


def tier_meets_threshold(record_tier: str, min_tier: str) -> bool:
    """Check if a record's quality tier meets or exceeds the minimum.

    Args:
        record_tier: The record's computed quality tier.
        min_tier: The minimum acceptable tier from config.

    Returns:
        True if record_tier >= min_tier in the ordinal ranking.
    """
    return TIER_ORDER.get(record_tier, 0) >= TIER_ORDER.get(min_tier, 0)
```

### Pattern 4: Activity Log for D-10 Notification
**What:** A simple JSONL activity log at `~/.hermes/kajiba/activity.jsonl` that continuous mode appends to. The CLI group callback reads and displays pending notifications, then clears them.
**When to use:** D-10 requires non-intrusive summary on next CLI use after auto-submit events.
**Example:**
```python
ACTIVITY_LOG = KAJIBA_BASE / "activity.jsonl"

def _log_activity(action: str, record_id: str, quality_tier: str) -> None:
    """Append an activity entry to the log."""
    entry = {
        "action": action,  # "auto_submitted" or "queued_for_review"
        "record_id": record_id,
        "quality_tier": quality_tier,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    ACTIVITY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with ACTIVITY_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _show_pending_notifications() -> None:
    """Show and clear any pending activity notifications."""
    if not ACTIVITY_LOG.exists():
        return
    try:
        lines = ACTIVITY_LOG.read_text(encoding="utf-8").strip().split("\n")
        entries = [json.loads(line) for line in lines if line.strip()]
    except Exception:
        return

    if not entries:
        return

    auto_submitted = sum(1 for e in entries if e["action"] == "auto_submitted")
    queued = sum(1 for e in entries if e["action"] == "queued_for_review")

    parts = []
    if auto_submitted:
        parts.append(f"{auto_submitted} record(s) auto-submitted")
    if queued:
        parts.append(f"{queued} queued for review")

    if parts:
        console.print(f"[dim]{', '.join(parts)}[/dim]")

    # Clear the log
    ACTIVITY_LOG.unlink(missing_ok=True)
```

### Pattern 5: Config Write with PyYAML
**What:** A `_save_config_value()` function that reads the existing YAML config, updates a single key under the `kajiba` section, and writes back. Requires PyYAML.
**When to use:** `kajiba config set <key> <value>`.
**Example:**
```python
def _save_config_value(key: str, value: str) -> None:
    """Write a single config value to ~/.hermes/config.yaml.

    Args:
        key: The config key (e.g., "contribution_mode").
        value: The value to set.

    Raises:
        click.ClickException: If PyYAML is not installed.
    """
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        raise click.ClickException(
            "PyYAML is required for config set. Install it: pip install pyyaml"
        )

    config_path = Path.home() / ".hermes" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    full_config: dict = {}
    if config_path.exists():
        try:
            with config_path.open() as f:
                full_config = yaml.safe_load(f) or {}
        except Exception:
            pass

    if "kajiba" not in full_config:
        full_config["kajiba"] = {}

    # Type coercion for known boolean/int keys
    if value.lower() in ("true", "false"):
        full_config["kajiba"][key] = value.lower() == "true"
    elif value.isdigit():
        full_config["kajiba"][key] = int(value)
    else:
        full_config["kajiba"][key] = value

    with config_path.open("w") as f:
        yaml.safe_dump(full_config, f, default_flow_style=False)
```

### Anti-Patterns to Avoid
- **Duplicating the submit pipeline:** Do not copy the scrub-anonymize-jitter-consent-quality-write sequence into `review` or `on_session_end`. Extract it once.
- **Background daemon for continuous mode:** D-04 explicitly chose inline at session end. Do not create a separate process, thread, or scheduled task.
- **Auto-publishing in continuous mode:** D-05 is clear: continuous mode writes to local outbox only. Network operations remain user-initiated.
- **Breaking `kajiba config` backward compatibility:** Bare `kajiba config` (no subcommand) must still work, showing config like before. Use `invoke_without_command=True`.
- **Mutating the activity log from the collector without fault tolerance:** The collector's auto-submit path must be wrapped in try/except per the established pattern. A failed activity log write must not crash the session.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI subcommand groups | Custom argument parsing | Click `@cli.group(invoke_without_command=True)` | Click handles subcommand routing, help text, argument parsing |
| YAML config read/write | Custom YAML parser | PyYAML `safe_load` / `safe_dump` | YAML has edge cases (multiline strings, type coercion); PyYAML handles them |
| Record preview rendering | New rendering code | Existing `_render_preview()` | Already handles Rich panels, quality display, scrub stats, flagged items |
| Submit pipeline | Inline copy-paste | Extracted `_submit_record()` helper | 15 lines of privacy+quality+ID+write logic that must stay consistent |
| Interactive prompts | Raw `input()` calls | Click `click.confirm()`, `click.prompt()` | Consistent with existing CLI patterns, works with CliRunner in tests |

**Key insight:** This phase is primarily about wiring together existing components in new control-flow patterns. Almost no new algorithmic code is needed.

## Common Pitfalls

### Pitfall 1: Config Command Backward Compatibility
**What goes wrong:** Changing `config` from `@cli.command()` to `@cli.group()` breaks `kajiba config` (no subcommand) for existing users.
**Why it happens:** Click groups require a subcommand by default.
**How to avoid:** Use `invoke_without_command=True` on the group, check `ctx.invoked_subcommand is None`, and invoke `config_show` as fallback.
**Warning signs:** Test `test_config_shows_defaults` fails after restructuring.

### Pitfall 2: PyYAML Not Installed for Config Set
**What goes wrong:** `kajiba config set` crashes with ImportError because PyYAML is a soft dependency.
**Why it happens:** PyYAML is not in `pyproject.toml` dependencies; it is conditionally imported.
**How to avoid:** Catch `ImportError` in `_save_config_value()` and raise a user-friendly `click.ClickException` with install instructions. Config reading already handles this gracefully.
**Warning signs:** Works in dev (PyYAML installed) but fails in fresh install.

### Pitfall 3: Collector Auto-Submit Lacks Access to CLI Imports
**What goes wrong:** `on_session_end()` in `collector.py` needs the submit pipeline (scrub, anonymize, jitter, consent, quality, write to outbox) but the pipeline is currently only in `cli.py`.
**Why it happens:** The collector module already imports `scrubber`, `scorer`, and `privacy` but does not know about outbox paths or the full pipeline sequence.
**How to avoid:** The submit pipeline helper should live in a location importable by `collector.py`. Two approaches: (a) put `_submit_record()` in `collector.py` alongside `export_record()`, or (b) create a small `submission.py` module. Approach (a) is simpler since `collector.py` already imports all the needed modules.
**Warning signs:** Circular import if helper is left in `cli.py` and collector tries to import it.

### Pitfall 4: Config Validation Missing for Invalid Values
**What goes wrong:** User sets `kajiba config set min_quality_tier platinum` and gets a confusing failure later when continuous mode tries to compare tiers.
**Why it happens:** Config set stores any string value without validating against known options.
**How to avoid:** Validate known keys against allowed values at `config set` time. Define a `CONFIG_SCHEMA` dict mapping key names to allowed values or types. Show the valid options in the error message.
**Warning signs:** Silent bad config that only manifests at session end.

### Pitfall 5: Review Command Removes Staging File Before Submit Completes
**What goes wrong:** If the review command deletes the staging file immediately after the user approves, but the submit pipeline fails, the record is lost.
**Why it happens:** Eager cleanup.
**How to avoid:** Only remove the staging file after the outbox write succeeds. Use a try/except around the submit call, and only unlink the staging file in the success path.
**Warning signs:** Intermittent data loss during review.

### Pitfall 6: Activity Log Concurrency
**What goes wrong:** Two simultaneous sessions could write to `activity.jsonl` at the same time, producing malformed JSON.
**Why it happens:** File append without locking.
**How to avoid:** This is low-risk for the expected usage pattern (single user, sequential sessions). Each write is a single `json.dumps()` + newline, which is atomic on most filesystems for small writes. If needed later, use file locking, but for now this is acceptable.
**Warning signs:** Corrupted activity log.

## Code Examples

### Review Command Core Logic
```python
@cli.command()
def review() -> None:
    """Review and approve staged records one at a time."""
    _show_pending_notifications()  # D-10: show auto-submit summary

    staged = _load_all_staging()
    if not staged:
        console.print("[yellow]No records in staging to review.[/yellow]")
        return

    reviewed = 0
    approved = 0
    rejected = 0
    skipped = 0

    for filepath, record in staged:
        console.print(f"\n[bold]Reviewing:[/bold] {filepath.name}")

        # Reuse existing preview infrastructure
        scrubbed, scrub_log = scrub_record(record)
        all_flagged = []
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

        _render_preview(preview_record, quality_dict, scrub_stats, flagged_items=all_flagged)

        # Prompt: approve / reject / skip / quit
        action = click.prompt(
            "Action",
            type=click.Choice(["approve", "reject", "skip", "quit"], case_sensitive=False),
            default="skip",
        )

        if action == "approve":
            outbox_file, qr = _submit_record(record, scrubbed, scrub_log)
            filepath.unlink()  # Remove from staging after successful submit
            console.print(f"[green]Approved and submitted: {outbox_file.name}[/green]")
            approved += 1
        elif action == "reject":
            filepath.unlink()
            console.print("[red]Record rejected and removed from staging.[/red]")
            rejected += 1
        elif action == "skip":
            console.print("[dim]Skipped.[/dim]")
            skipped += 1
        elif action == "quit":
            break

        reviewed += 1

    console.print(f"\n[bold]Review complete:[/bold] {approved} approved, {rejected} rejected, {skipped} skipped")
```

### Continuous Mode in on_session_end
```python
def on_session_end(self, session_id: str) -> None:
    """Finalize record and optionally auto-submit in continuous mode."""
    try:
        if self._session_id != session_id:
            logger.warning(
                "Session ID mismatch: expected %s, got %s",
                self._session_id, session_id,
            )
        logger.info(
            "Kajiba collector ended for session %s (%d turns)",
            session_id, len(self._conversations),
        )

        # --- Continuous mode auto-submit (D-04) ---
        contribution_mode = _load_config_value("contribution_mode", "ad-hoc")
        if contribution_mode != "continuous":
            # Ad-hoc mode: record stays in staging for manual review
            self._save_to_staging()
            return

        # Build and process record
        record = self._build_record()
        scrubbed, scrub_log = scrub_record(record)
        anonymized = anonymize_hardware(scrubbed)
        quality = compute_quality_score(anonymized)

        min_tier = _load_config_value("min_quality_tier", "silver")
        if tier_meets_threshold(quality.quality_tier, min_tier):
            # Auto-submit: full pipeline
            outbox_path, _ = _submit_record(record, scrubbed, scrub_log)
            _log_activity("auto_submitted", "...", quality.quality_tier)
            logger.info("Auto-submitted record (tier: %s)", quality.quality_tier)
        else:
            # Below threshold: save to staging for manual review
            self._save_to_staging()
            _log_activity("queued_for_review", "...", quality.quality_tier)
            logger.info("Record queued for review (tier: %s, min: %s)",
                        quality.quality_tier, min_tier)

    except Exception:
        logger.exception("Error in on_session_end")
```

### Config Set with Validation
```python
VALID_CONFIG_KEYS: dict[str, dict] = {
    "contribution_mode": {
        "type": "choice",
        "choices": ["ad-hoc", "continuous"],
        "default": "ad-hoc",
    },
    "min_quality_tier": {
        "type": "choice",
        "choices": ["gold", "silver", "bronze"],
        "default": "silver",
    },
    "consent_level": {
        "type": "choice",
        "choices": ["anonymous", "trajectory_only", "metadata_only", "full"],
        "default": "full",
    },
    "auto_submit_interval": {
        "type": "int",
        "min": 0,
        "default": 0,
        "description": "Reserved for future background mode (minutes). Currently unused.",
    },
    "auto_submit": {
        "type": "bool",
        "default": False,
        "description": "Legacy key. Use contribution_mode instead.",
    },
    "llm_pii_scrub": {
        "type": "bool",
        "default": True,
    },
    "scrub_strictness": {
        "type": "choice",
        "choices": ["low", "medium", "high"],
        "default": "high",
    },
    "dataset_repo": {
        "type": "string",
        "default": "CuervoDoesIt/kajiba-dataset",
    },
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `kajiba config` (read-only display) | `kajiba config show/set/get` (subcommand group) | This phase | Backward compat via `invoke_without_command` |
| `auto_submit: False` config key | `contribution_mode: ad-hoc/continuous` config key | This phase | More descriptive; `auto_submit` becomes legacy |
| Submit only via `kajiba submit` | Submit via `review approve` or auto at session end | This phase | Two new code paths call same submit pipeline |

## Open Questions

1. **Should `collector.py` save to staging directly?**
   - What we know: Currently `export_record()` returns a record in-memory; CLI handles file I/O. For continuous mode, `on_session_end()` needs to both save to staging (ad-hoc) and submit to outbox (continuous).
   - What's unclear: Whether the collector should take on file I/O responsibility or delegate to a helper.
   - Recommendation: Add a `_save_to_staging()` method to the collector that mirrors the existing staging write pattern. The collector already imports all needed modules. Keep the submit pipeline helper importable by collector (place it in `collector.py` or a shared `submission.py`).

2. **Should PyYAML become a required dependency?**
   - What we know: Config reading gracefully falls back when PyYAML is absent. Config writing requires PyYAML (no pure-Python YAML writer in stdlib).
   - What's unclear: Whether to keep it optional (with error message on `config set`) or add to `pyproject.toml` dependencies.
   - Recommendation: Keep PyYAML optional per existing pattern. `config set` raises a clear error with install instructions if PyYAML is missing. This maintains the "no external services for core" constraint -- core pipeline still works without it.

3. **Where to place `_submit_record()` and `_load_config_value()` for collector access?**
   - What we know: `collector.py` imports from `schema`, `scorer`, `scrubber`, and `privacy`. It does not import from `cli.py`. `_load_config_value()` and the submit pipeline are currently in `cli.py`.
   - What's unclear: Best module boundary.
   - Recommendation: Move `_load_config_value()` and `_save_config_value()` to a new thin `config.py` module (or keep in cli.py and have collector use its own inline reader). Move `_submit_record()` logic into `collector.py` alongside `export_record()` since it already has all the right imports. This avoids circular imports.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/test_cli.py tests/test_collector.py -x -v` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONT-01 | `kajiba review` shows staged records, approve moves to outbox, reject removes, skip continues | unit (CLI) | `python -m pytest tests/test_cli.py::TestReviewCommand -x` | Wave 0 |
| CONT-02 | Continuous mode auto-submits qualifying records at session end | unit (collector) | `python -m pytest tests/test_collector.py::TestContinuousMode -x` | Wave 0 |
| CONT-03 | `kajiba config set contribution_mode continuous` persists and is read on next invocation | unit (CLI) | `python -m pytest tests/test_cli.py::TestConfigSubcommands -x` | Wave 0 |
| CONT-04 | `min_quality_tier`, `consent_level`, `auto_submit_interval` configurable via `kajiba config set` | unit (CLI) | `python -m pytest tests/test_cli.py::TestConfigSetValidation -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_cli.py tests/test_collector.py -x -v`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_cli.py::TestReviewCommand` -- covers CONT-01 (review approve/reject/skip flow, staging cleanup)
- [ ] `tests/test_cli.py::TestConfigSubcommands` -- covers CONT-03, CONT-04 (set/get/show, validation, backward compat)
- [ ] `tests/test_cli.py::TestConfigSetValidation` -- covers CONT-04 (invalid values rejected, valid options shown)
- [ ] `tests/test_collector.py::TestContinuousMode` -- covers CONT-02 (auto-submit on session end, below-threshold stays in staging)
- [ ] `tests/test_cli.py::TestActivityNotification` -- covers D-10 (summary shown on next CLI use)

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | Yes | 3.13.3 | -- |
| Click | CLI commands | Yes | 8.3.1 | -- |
| Rich | Terminal rendering | Yes | installed | -- |
| Pydantic | Schema validation | Yes | 2.12.5 | -- |
| pytest | Testing | Yes | 9.0.2 | -- |
| PyYAML | Config set/get | No (not installed in venv) | -- | Error message with install instructions; config read falls back to defaults |

**Missing dependencies with no fallback:**
- None -- all critical dependencies are available.

**Missing dependencies with fallback:**
- PyYAML: Not installed but is a soft dependency. `config set` will require it and provide a clear install instruction. Config reading already handles absence gracefully.

## Project Constraints (from CLAUDE.md)

- **Tech stack**: Python 3.11+, Pydantic v2, Click, Rich -- no changes needed
- **Privacy**: Maximum scrubbing by default -- auto-submit must run full privacy pipeline
- **Local-first**: All processing on contributor's machine -- continuous mode writes to local outbox only (D-05)
- **No external services for core**: Core pipeline works without API keys -- config read/write is local file only
- **Naming**: snake_case functions, PascalCase classes, UPPER_SNAKE_CASE constants
- **Logging**: `logger = logging.getLogger(__name__)`, `%s` formatting, no `print()`
- **Error handling**: Collector methods wrapped in try/except, log exceptions
- **Docstrings**: Google-style with Args/Returns/Raises
- **Type annotations**: All public functions, `Optional[X]` not `X | None`
- **Import style**: `from X import Y` for specific names
- **Config path**: `~/.hermes/config.yaml` under `kajiba` section
- **Data paths**: `~/.hermes/kajiba/staging/`, `~/.hermes/kajiba/outbox/`
- **Serialization**: `model_dump(mode="json", by_alias=True)` for JSON output

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection of `src/kajiba/cli.py`, `src/kajiba/collector.py`, `src/kajiba/scorer.py`, `src/kajiba/privacy.py`, `src/kajiba/schema.py`, `src/kajiba/hermes_integration.py`
- Direct codebase inspection of `tests/test_cli.py`, `tests/test_collector.py`
- `pyproject.toml` for dependency versions and test configuration
- Runtime verification: Click 8.3.1, Pydantic 2.12.5, pytest 9.0.2, Python 3.13.3

### Secondary (MEDIUM confidence)
- [Click Documentation - Commands and Groups](https://click.palletsprojects.com/en/stable/commands-and-groups/) -- `invoke_without_command` pattern for group backward compatibility
- [Click Documentation - Complex Applications](https://click.palletsprojects.com/en/stable/complex/) -- context passing and subcommand patterns

### Tertiary (LOW confidence)
- None -- all findings verified against codebase.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already installed and in use; no new dependencies
- Architecture: HIGH - patterns derived from direct inspection of existing code; submit pipeline, config helpers, and collector hooks are well-understood
- Pitfalls: HIGH - pitfalls identified from actual code structure (circular imports, PyYAML absence, backward compat)

**Research date:** 2026-04-01
**Valid until:** 2026-05-01 (stable codebase, no fast-moving external dependencies)
