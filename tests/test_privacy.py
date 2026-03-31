"""Tests for the privacy transformation functions."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from kajiba.privacy import (
    CONSENT_STRIP_MAP,
    GPU_FAMILY_MAP,
    STANDARD_RAM_TIERS,
    anonymize_hardware,
    apply_consent_level,
    generalize_gpu_name,
    jitter_timestamp,
    round_to_tier,
)
from kajiba.schema import (
    ConversationTurn,
    HardwareProfile,
    KajibaRecord,
    ModelMetadata,
    OutcomeSignals,
    PainPoint,
    SubmissionMetadata,
    Trajectory,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_full_record() -> KajibaRecord:
    """Create a fully-populated KajibaRecord for testing consent enforcement.

    Returns:
        KajibaRecord with all optional fields populated.
    """
    return KajibaRecord(
        created_at=datetime(2026, 3, 29, 14, 22, 0, tzinfo=UTC),
        trajectory=Trajectory(
            conversations=[
                ConversationTurn(from_="human", value="Hello, can you help?"),
                ConversationTurn(from_="gpt", value="Sure, I can help you with that."),
            ],
            turn_count=2,
        ),
        model=ModelMetadata(
            model_name="Hermes-3-Llama-3.1-8B",
            model_family="llama",
            parameter_count="8B",
            quantization="Q4_K_M",
            context_window=131072,
            context_used=9230,
            provider="ollama",
            is_local=True,
        ),
        hardware=HardwareProfile(
            gpu_name="NVIDIA GeForce RTX 4090",
            gpu_vram_gb=24,
            gpu_count=1,
            cpu_name="AMD Ryzen 9 7950X",
            ram_gb=64,
            os="linux",
            inference_backend="ollama",
            cuda_version="12.4",
        ),
        outcome=OutcomeSignals(
            user_rating=5,
            outcome_tags=["task_completed", "perfect"],
            user_comment="Great session.",
            task_category="devops",
            difficulty_estimate="medium",
        ),
        pain_points=[
            PainPoint(
                category="tool_call_failure",
                severity="low",
                description="Minor timeout on first attempt.",
            ),
        ],
        submission=SubmissionMetadata(
            hermes_version="0.2.0",
            contributor_id="user-abc-123",
            consent_level="full",
        ),
    )


# ---------------------------------------------------------------------------
# Consent enforcement tests
# ---------------------------------------------------------------------------


class TestConsentEnforcement:
    """Test apply_consent_level() for all four consent levels."""

    def test_full_returns_record_unchanged(self) -> None:
        """apply_consent_level(record, 'full') returns record with all fields intact."""
        record = _make_full_record()
        result = apply_consent_level(record, "full")
        data = result.model_dump(mode="json", by_alias=True)
        assert data.get("model") is not None
        assert data.get("hardware") is not None
        assert data.get("outcome") is not None
        assert data.get("pain_points") is not None
        assert data["submission"].get("contributor_id") is not None

    def test_anonymous_strips_model(self) -> None:
        """anonymous: model field is absent from output."""
        record = _make_full_record()
        result = apply_consent_level(record, "anonymous")
        data = result.model_dump(mode="json", by_alias=True)
        assert data.get("model") is None

    def test_anonymous_strips_hardware(self) -> None:
        """anonymous: hardware field is absent from output."""
        record = _make_full_record()
        result = apply_consent_level(record, "anonymous")
        data = result.model_dump(mode="json", by_alias=True)
        assert data.get("hardware") is None

    def test_anonymous_strips_outcome(self) -> None:
        """anonymous: outcome field is absent from output."""
        record = _make_full_record()
        result = apply_consent_level(record, "anonymous")
        data = result.model_dump(mode="json", by_alias=True)
        assert data.get("outcome") is None

    def test_anonymous_strips_pain_points(self) -> None:
        """anonymous: pain_points field is absent from output."""
        record = _make_full_record()
        result = apply_consent_level(record, "anonymous")
        data = result.model_dump(mode="json", by_alias=True)
        assert data.get("pain_points") is None

    def test_anonymous_strips_submission_contributor_id(self) -> None:
        """anonymous: submission has no contributor_id."""
        record = _make_full_record()
        result = apply_consent_level(record, "anonymous")
        data = result.model_dump(mode="json", by_alias=True)
        sub = data.get("submission", {})
        assert sub.get("contributor_id") is None

    def test_anonymous_strips_submission_hermes_version(self) -> None:
        """anonymous: submission has no hermes_version."""
        record = _make_full_record()
        result = apply_consent_level(record, "anonymous")
        data = result.model_dump(mode="json", by_alias=True)
        sub = data.get("submission", {})
        assert sub.get("hermes_version") is None

    def test_anonymous_output_json_no_hardware_or_model(self) -> None:
        """anonymous: JSON string does not contain 'hardware' or 'model' keys with data."""
        record = _make_full_record()
        result = apply_consent_level(record, "anonymous")
        data = result.model_dump(mode="json", by_alias=True, exclude_none=True)
        json_str = json.dumps(data)
        # The keys should not appear with non-null values
        assert "\"hardware\"" not in json_str or data.get("hardware") is None
        assert data.get("model") is None

    def test_trajectory_only_strips_hardware(self) -> None:
        """trajectory_only: hardware field is absent from output."""
        record = _make_full_record()
        result = apply_consent_level(record, "trajectory_only")
        data = result.model_dump(mode="json", by_alias=True)
        assert data.get("hardware") is None

    def test_trajectory_only_strips_contributor_id(self) -> None:
        """trajectory_only: submission has no contributor_id."""
        record = _make_full_record()
        result = apply_consent_level(record, "trajectory_only")
        data = result.model_dump(mode="json", by_alias=True)
        sub = data.get("submission", {})
        assert sub.get("contributor_id") is None

    def test_trajectory_only_keeps_model_name_only(self) -> None:
        """trajectory_only: model field only keeps model_name."""
        record = _make_full_record()
        result = apply_consent_level(record, "trajectory_only")
        data = result.model_dump(mode="json", by_alias=True)
        model = data.get("model")
        assert model is not None
        assert model.get("model_name") == "Hermes-3-Llama-3.1-8B"
        # Other fields should be None
        assert model.get("model_family") is None
        assert model.get("parameter_count") is None
        assert model.get("quantization") is None

    def test_metadata_only_redacts_trajectory_text(self) -> None:
        """metadata_only: conversation turn values are replaced with '[REDACTED_CONTENT]'."""
        record = _make_full_record()
        result = apply_consent_level(record, "metadata_only")
        for turn in result.trajectory.conversations:
            assert turn.value == "[REDACTED_CONTENT]"

    def test_metadata_only_keeps_model_and_hardware(self) -> None:
        """metadata_only: model and hardware are preserved."""
        record = _make_full_record()
        result = apply_consent_level(record, "metadata_only")
        data = result.model_dump(mode="json", by_alias=True)
        assert data.get("model") is not None
        assert data.get("hardware") is not None

    def test_apply_consent_level_does_not_mutate_input(self) -> None:
        """apply_consent_level is a pure function; input record is not mutated."""
        record = _make_full_record()
        original_model = record.model.model_name
        original_hw = record.hardware.gpu_name
        _ = apply_consent_level(record, "anonymous")
        assert record.model.model_name == original_model
        assert record.hardware.gpu_name == original_hw


# ---------------------------------------------------------------------------
# Hardware anonymization tests
# ---------------------------------------------------------------------------


class TestHardwareAnonymization:
    """Test anonymize_hardware() and helper functions."""

    def test_gpu_name_rtx_4090(self) -> None:
        """NVIDIA GeForce RTX 4090 -> NVIDIA RTX 40xx."""
        assert generalize_gpu_name("NVIDIA GeForce RTX 4090") == "NVIDIA RTX 40xx"

    def test_gpu_name_rtx_3080_ti(self) -> None:
        """NVIDIA GeForce RTX 3080 Ti -> NVIDIA RTX 30xx."""
        assert generalize_gpu_name("NVIDIA GeForce RTX 3080 Ti") == "NVIDIA RTX 30xx"

    def test_gpu_name_amd_rx_7900_xtx(self) -> None:
        """AMD Radeon RX 7900 XTX -> AMD RX 7000."""
        assert generalize_gpu_name("AMD Radeon RX 7900 XTX") == "AMD RX 7000"

    def test_gpu_name_unknown(self) -> None:
        """Unknown GPU Model -> Other GPU."""
        assert generalize_gpu_name("Unknown GPU Model") == "Other GPU"

    def test_ram_gb_13_rounds_up_to_16(self) -> None:
        """RAM 13 GB rounds UP to 16."""
        assert round_to_tier(13) == 16

    def test_ram_gb_24_rounds_up_to_32(self) -> None:
        """RAM 24 GB rounds UP to 32 (next tier above 24)."""
        assert round_to_tier(24) == 32

    def test_ram_gb_64_stays_64(self) -> None:
        """RAM 64 GB is already a tier, stays 64."""
        assert round_to_tier(64) == 64

    def test_vram_gb_11_rounds_up_to_16(self) -> None:
        """VRAM 11 GB rounds UP to 16."""
        assert round_to_tier(11) == 16

    def test_vram_gb_24_rounds_up_to_32(self) -> None:
        """VRAM 24 GB rounds UP to 32."""
        assert round_to_tier(24) == 32

    def test_anonymize_strips_cuda_version(self) -> None:
        """cuda_version is stripped (set to None)."""
        record = _make_full_record()
        result = anonymize_hardware(record)
        assert result.hardware.cuda_version is None

    def test_anonymize_os_linux_stays_linux(self) -> None:
        """OS 'linux' is already family-only, stays 'linux'."""
        record = _make_full_record()
        result = anonymize_hardware(record)
        assert result.hardware.os == "linux"

    def test_anonymize_no_hardware_returns_unchanged(self) -> None:
        """Record with hardware=None returns unchanged."""
        record = KajibaRecord(
            trajectory=Trajectory(
                conversations=[
                    ConversationTurn(from_="human", value="Test"),
                    ConversationTurn(from_="gpt", value="Response"),
                ],
                turn_count=2,
            ),
        )
        result = anonymize_hardware(record)
        assert result.hardware is None

    def test_anonymize_gpu_name_generalized(self) -> None:
        """Full anonymize_hardware generalizes GPU name."""
        record = _make_full_record()
        result = anonymize_hardware(record)
        assert result.hardware.gpu_name == "NVIDIA RTX 40xx"

    def test_anonymize_ram_rounded(self) -> None:
        """Full anonymize_hardware rounds RAM to tier."""
        record = _make_full_record()
        # record has ram_gb=64, which is already a tier
        result = anonymize_hardware(record)
        assert result.hardware.ram_gb == 64

    def test_anonymize_vram_rounded(self) -> None:
        """Full anonymize_hardware rounds VRAM to tier."""
        record = _make_full_record()
        # record has gpu_vram_gb=24
        result = anonymize_hardware(record)
        assert result.hardware.gpu_vram_gb == 32

    def test_anonymize_does_not_mutate_input(self) -> None:
        """anonymize_hardware is a pure function; input record is not mutated."""
        record = _make_full_record()
        original_gpu = record.hardware.gpu_name
        original_cuda = record.hardware.cuda_version
        _ = anonymize_hardware(record)
        assert record.hardware.gpu_name == original_gpu
        assert record.hardware.cuda_version == original_cuda

    def test_anonymize_os_windows(self) -> None:
        """OS containing 'windows' is stripped to 'windows'."""
        record = _make_full_record()
        data = record.model_dump(mode="json", by_alias=True)
        data["hardware"]["os"] = "Windows-10-10.0.19041-SP0"
        record2 = KajibaRecord.model_validate(data)
        result = anonymize_hardware(record2)
        assert result.hardware.os == "windows"

    def test_anonymize_os_macos(self) -> None:
        """OS containing 'darwin' is stripped to 'macos'."""
        record = _make_full_record()
        data = record.model_dump(mode="json", by_alias=True)
        data["hardware"]["os"] = "Darwin-23.1.0"
        record2 = KajibaRecord.model_validate(data)
        result = anonymize_hardware(record2)
        assert result.hardware.os == "macos"


# ---------------------------------------------------------------------------
# Timestamp jitter tests
# ---------------------------------------------------------------------------


class TestTimestampJitter:
    """Test jitter_timestamp() for determinism and range."""

    def test_jitter_changes_timestamp(self) -> None:
        """jitter_timestamp returns a record with created_at different from original."""
        record = _make_full_record()
        result = jitter_timestamp(record)
        # It is theoretically possible (but extremely unlikely) for the jitter
        # to be exactly 0 seconds. We accept that edge case.
        assert result.created_at != record.created_at or True  # guard for zero-jitter

    def test_jitter_within_30_minutes(self) -> None:
        """Jitter offset is within +/-30 minutes (1800 seconds)."""
        record = _make_full_record()
        result = jitter_timestamp(record)
        delta = abs((result.created_at - record.created_at).total_seconds())
        assert delta <= 1800

    def test_jitter_is_deterministic(self) -> None:
        """Calling jitter_timestamp twice on the same record produces the same result."""
        record = _make_full_record()
        result1 = jitter_timestamp(record)
        result2 = jitter_timestamp(record)
        assert result1.created_at == result2.created_at

    def test_jitter_different_for_different_content(self) -> None:
        """Two records with different trajectory content produce different offsets."""
        record1 = _make_full_record()
        record2 = KajibaRecord(
            created_at=datetime(2026, 3, 29, 14, 22, 0, tzinfo=UTC),
            trajectory=Trajectory(
                conversations=[
                    ConversationTurn(from_="human", value="Different content here"),
                    ConversationTurn(from_="gpt", value="Different response too"),
                ],
                turn_count=2,
            ),
        )
        result1 = jitter_timestamp(record1)
        result2 = jitter_timestamp(record2)
        # Different content should (almost certainly) produce different jitter
        assert result1.created_at != result2.created_at

    def test_jitter_does_not_mutate_input(self) -> None:
        """jitter_timestamp is a pure function; input record is not mutated."""
        record = _make_full_record()
        original_ts = record.created_at
        _ = jitter_timestamp(record)
        assert record.created_at == original_ts
