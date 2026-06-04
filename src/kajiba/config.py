"""Configuration management for Kajiba.

Provides config read/write, validation schema, quality tier comparison,
and activity logging for contribution modes.
"""

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

import click

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TIER_ORDER: dict[str, int] = {
    "gold": 4,
    "silver": 3,
    "bronze": 2,
    "review_needed": 1,
}


def get_hermes_home() -> Path:
    """Resolve the active Hermes home directory.

    Checks the ``HERMES_HOME`` environment variable first (Hermes v0.6.0
    profile isolation); falls back to ``~/.hermes`` when unset or empty.
    Read on every call (never cached) so a later-set HERMES_HOME is honored.

    Returns:
        Path to the active Hermes home directory.
    """
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    return Path.home() / ".hermes"


KAJIBA_BASE = get_hermes_home() / "kajiba"
ACTIVITY_LOG = KAJIBA_BASE / "activity.jsonl"

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


# ---------------------------------------------------------------------------
# Config read/write
# ---------------------------------------------------------------------------


def _load_config_value(key: str, default: str) -> str:
    """Read a single value from the active Hermes config.yaml under the kajiba section.

    Args:
        key: The config key to look up (e.g. "dataset_repo").
        default: Fallback value if key is absent or yaml unavailable.

    Returns:
        The config value as a string, or the default.
    """
    config_path = get_hermes_home() / "config.yaml"
    if not config_path.exists():
        return default
    try:
        import yaml  # type: ignore[import-untyped]
        with config_path.open() as f:
            full_config = yaml.safe_load(f) or {}
        kajiba_section = full_config.get("kajiba", {})
        return str(kajiba_section.get(key, default))
    except ImportError:
        return default
    except Exception:
        return default


def _save_config_value(key: str, value: str) -> None:
    """Write a single value to the active Hermes config.yaml under the kajiba section.

    Type coercion: "true"/"false" -> bool, digit strings -> int, else string.

    Args:
        key: The config key to set.
        value: The string value from the CLI.

    Raises:
        click.ClickException: If PyYAML is not installed.
    """
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        raise click.ClickException(
            "PyYAML is required for config set. Install it: pip install pyyaml"
        )

    config_path = get_hermes_home() / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    full_config: dict = {}
    if config_path.exists():
        try:
            with config_path.open() as f:
                full_config = yaml.safe_load(f) or {}
        except Exception:
            full_config = {}

    kajiba_section = full_config.get("kajiba", {})

    # Type coercion
    coerced: object
    if value.lower() == "true":
        coerced = True
    elif value.lower() == "false":
        coerced = False
    elif value.lstrip("-").isdigit():
        coerced = int(value)
    else:
        coerced = value

    kajiba_section[key] = coerced
    full_config["kajiba"] = kajiba_section

    with config_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(full_config, f, default_flow_style=False)


# ---------------------------------------------------------------------------
# Tier comparison
# ---------------------------------------------------------------------------


def tier_meets_threshold(record_tier: str, min_tier: str) -> bool:
    """Check if a quality tier meets or exceeds a minimum threshold.

    Args:
        record_tier: The tier of the record (e.g. "gold").
        min_tier: The minimum acceptable tier (e.g. "silver").

    Returns:
        True if record_tier >= min_tier in the tier ordering.
    """
    return TIER_ORDER.get(record_tier, 0) >= TIER_ORDER.get(min_tier, 0)


# ---------------------------------------------------------------------------
# Activity logging
# ---------------------------------------------------------------------------


def _log_activity(action: str, record_id: str, quality_tier: str) -> None:
    """Append an activity entry to the activity log.

    Args:
        action: The action type (e.g. "auto_submitted", "queued_for_review").
        record_id: The record's unique ID.
        quality_tier: The record's quality tier.
    """
    try:
        ACTIVITY_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "action": action,
            "record_id": record_id,
            "quality_tier": quality_tier,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        with ACTIVITY_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        logger.exception("Failed to log activity: %s %s", action, record_id)


def _show_pending_notifications() -> Optional[str]:
    """Read and clear the activity log, returning a summary string.

    Counts entries by action type and returns a human-readable summary.
    Deletes the activity log file after reading.

    Returns:
        Formatted summary string, or None if no entries or on error.
    """
    try:
        if not ACTIVITY_LOG.exists():
            return None

        counts: dict[str, int] = {}
        for line in ACTIVITY_LOG.read_text(encoding="utf-8").strip().split("\n"):
            if not line.strip():
                continue
            entry = json.loads(line)
            action = entry.get("action", "unknown")
            counts[action] = counts.get(action, 0) + 1

        # Clean up
        ACTIVITY_LOG.unlink(missing_ok=True)

        if not counts:
            return None

        parts: list[str] = []
        if counts.get("auto_submitted"):
            parts.append(f"{counts['auto_submitted']} record(s) auto-submitted")
        if counts.get("queued_for_review"):
            parts.append(f"{counts['queued_for_review']} queued for review")

        return ", ".join(parts) if parts else None
    except Exception:
        logger.exception("Failed to show pending notifications")
        return None
