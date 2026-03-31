"""Privacy transformation functions for Kajiba records.

Implements consent-level field stripping (Layer E), hardware profile
anonymization (Layer D), and timestamp jittering. All functions are
pure -- they return new records without mutating their inputs.
"""

import hashlib
import json
import logging
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from kajiba.schema import ConsentLevelType, KajibaRecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# GPU family mapping -- ordered list of (regex, family_label) pairs.
# Per D-04: series-level generalization.
GPU_FAMILY_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"NVIDIA\s+(?:GeForce\s+)?RTX\s+50\d{2}(?:\s+(?:Ti|SUPER))?", re.IGNORECASE), "NVIDIA RTX 50xx"),
    (re.compile(r"NVIDIA\s+(?:GeForce\s+)?RTX\s+40\d{2}(?:\s+(?:Ti|SUPER))?", re.IGNORECASE), "NVIDIA RTX 40xx"),
    (re.compile(r"NVIDIA\s+(?:GeForce\s+)?RTX\s+30\d{2}(?:\s+(?:Ti|SUPER))?", re.IGNORECASE), "NVIDIA RTX 30xx"),
    (re.compile(r"NVIDIA\s+(?:GeForce\s+)?RTX\s+20\d{2}(?:\s+(?:Ti|SUPER))?", re.IGNORECASE), "NVIDIA RTX 20xx"),
    (re.compile(r"NVIDIA\s+(?:GeForce\s+)?GTX\s+16\d{2}(?:\s+(?:Ti|SUPER))?", re.IGNORECASE), "NVIDIA GTX 16xx"),
    (re.compile(r"NVIDIA\s+(?:GeForce\s+)?GTX\s+10\d{2}(?:\s+(?:Ti))?", re.IGNORECASE), "NVIDIA GTX 10xx"),
    (re.compile(r"NVIDIA\s+A100", re.IGNORECASE), "NVIDIA A100"),
    (re.compile(r"NVIDIA\s+A[46]000", re.IGNORECASE), "NVIDIA Axxxx"),
    (re.compile(r"NVIDIA\s+H100", re.IGNORECASE), "NVIDIA H100"),
    (re.compile(r"NVIDIA\s+L40", re.IGNORECASE), "NVIDIA L40"),
    (re.compile(r"AMD\s+(?:Radeon\s+)?RX\s+7\d{3}", re.IGNORECASE), "AMD RX 7000"),
    (re.compile(r"AMD\s+(?:Radeon\s+)?RX\s+6\d{3}", re.IGNORECASE), "AMD RX 6000"),
    (re.compile(r"AMD\s+Instinct\s+MI\d+", re.IGNORECASE), "AMD Instinct"),
    (re.compile(r"Apple\s+M[1-9]", re.IGNORECASE), "Apple Silicon"),
    (re.compile(r"Intel\s+Arc\s+A\d+", re.IGNORECASE), "Intel Arc"),
]

# RAM/VRAM rounding tiers (power-of-2 per D-05).
STANDARD_RAM_TIERS = [4, 8, 16, 32, 64, 128, 256, 512]

# Consent stripping rules per spec Section 2.2 Layer E and decisions D-01
# through D-03.
CONSENT_STRIP_MAP: dict[str, dict] = {
    "anonymous": {
        "remove_top_level": ["model", "hardware", "outcome", "pain_points"],
        "remove_submission_fields": ["contributor_id", "hermes_version"],
        "strip_timing": True,
    },
    "trajectory_only": {
        "remove_top_level": ["hardware"],
        "remove_submission_fields": ["contributor_id"],
        "keep_model_fields_only": ["model_name"],
        "strip_timing": True,
    },
    "metadata_only": {
        "strip_trajectory_text": True,
    },
    "full": {},
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def generalize_gpu_name(name: str) -> str:
    """Generalize a GPU name to its family-level designator.

    Args:
        name: The full GPU name (e.g., "NVIDIA GeForce RTX 4090").

    Returns:
        Family-level name (e.g., "NVIDIA RTX 40xx"), or "Other GPU" if
        unrecognized.
    """
    for pattern, family in GPU_FAMILY_MAP:
        if pattern.search(name):
            return family
    return "Other GPU"


def round_to_tier(value: int) -> int:
    """Round a RAM/VRAM value UP to the next power-of-2 standard tier.

    Always rounds up (ceiling) to err on the side of privacy -- reporting
    a higher bucket is less fingerprinting than a lower one.

    Args:
        value: The raw GB value.

    Returns:
        The smallest standard tier >= value, or the largest tier if value
        exceeds all.
    """
    if value <= 0:
        return STANDARD_RAM_TIERS[0]
    for tier in STANDARD_RAM_TIERS:
        if tier >= value:
            return tier
    return STANDARD_RAM_TIERS[-1]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def anonymize_hardware(record: KajibaRecord) -> KajibaRecord:
    """Apply all hardware anonymization steps per D-04, D-05, D-06, D-08.

    Generalizes GPU name to family, rounds RAM/VRAM to power-of-2 tiers,
    strips OS to family-only label, and removes cuda_version.

    Args:
        record: The KajibaRecord to anonymize.

    Returns:
        New KajibaRecord with anonymized hardware. Input is not mutated.
    """
    data = record.model_dump(mode="json", by_alias=True)
    hw = data.get("hardware")
    if not hw:
        return record

    if hw.get("gpu_name"):
        hw["gpu_name"] = generalize_gpu_name(hw["gpu_name"])
    if hw.get("gpu_vram_gb") is not None:
        hw["gpu_vram_gb"] = round_to_tier(hw["gpu_vram_gb"])
    if hw.get("ram_gb") is not None:
        hw["ram_gb"] = round_to_tier(hw["ram_gb"])

    # Strip OS to family label only (D-06)
    if hw.get("os"):
        os_val = hw["os"].lower()
        if "darwin" in os_val or "macos" in os_val or "mac" in os_val:
            hw["os"] = "macos"
        elif "linux" in os_val:
            hw["os"] = "linux"
        elif "windows" in os_val or "win" in os_val:
            hw["os"] = "windows"
        # else: keep as-is (already family-level or unknown)

    # Strip cuda_version -- fingerprinting surface, no fine-tuning utility
    hw.pop("cuda_version", None)

    return KajibaRecord.model_validate(data)


def jitter_timestamp(record: KajibaRecord) -> KajibaRecord:
    """Jitter the record's created_at timestamp by +/-0-30 minutes.

    Uses a deterministic seed derived from the trajectory content so the
    same record always gets the same jitter. Per D-07.

    Args:
        record: The KajibaRecord to jitter.

    Returns:
        New KajibaRecord with jittered created_at. Input is not mutated.
    """
    # Deterministic seed from trajectory content
    content = json.dumps(
        [{"from": t.from_, "value": t.value} for t in record.trajectory.conversations],
        sort_keys=True,
        ensure_ascii=True,
    )
    seed = hashlib.sha256(content.encode("utf-8")).hexdigest()
    rng = random.Random(seed)

    # Offset in seconds: -1800 to +1800 (30 minutes)
    offset_seconds = rng.randint(-1800, 1800)

    data = record.model_dump(mode="json", by_alias=True)
    # created_at is serialized as ISO string in JSON mode
    original_dt = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
    jittered_dt = original_dt + timedelta(seconds=offset_seconds)
    data["created_at"] = jittered_dt.isoformat()

    return KajibaRecord.model_validate(data)


def apply_consent_level(
    record: KajibaRecord,
    level: ConsentLevelType,
) -> KajibaRecord:
    """Strip fields from a record based on the consent level.

    Pure function per D-02: returns a new record, does not mutate input.
    Consent level rules follow the spec Section 2.2 Layer E table.

    Args:
        record: The KajibaRecord to strip.
        level: The consent level to enforce.

    Returns:
        New KajibaRecord with fields stripped per consent level.
    """
    rules = CONSENT_STRIP_MAP.get(level, {})
    if not rules:
        return record  # "full" -- nothing to strip

    data = record.model_dump(mode="json", by_alias=True)

    # Remove top-level fields
    for field_name in rules.get("remove_top_level", []):
        data.pop(field_name, None)

    # Remove submission sub-fields
    sub = data.get("submission")
    if sub:
        for field_name in rules.get("remove_submission_fields", []):
            sub.pop(field_name, None)

    # Keep only specified model fields (trajectory_only: keep model_name only)
    keep_model = rules.get("keep_model_fields_only")
    if keep_model is not None and data.get("model"):
        model_data = data["model"]
        kept = {k: model_data[k] for k in keep_model if k in model_data}
        data["model"] = kept

    # Strip timing (anonymous, trajectory_only)
    if rules.get("strip_timing"):
        data.pop("created_at", None)

    # Strip trajectory text (metadata_only)
    if rules.get("strip_trajectory_text"):
        for turn in data.get("trajectory", {}).get("conversations", []):
            turn["value"] = "[REDACTED_CONTENT]"
            if turn.get("tool_calls"):
                for tc in turn["tool_calls"]:
                    tc["tool_input"] = "[REDACTED_CONTENT]"
                    tc["tool_output"] = "[REDACTED_CONTENT]"

    return KajibaRecord.model_validate(data)
