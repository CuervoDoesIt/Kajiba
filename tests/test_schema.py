"""Tests for the Kajiba record schema."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from kajiba.schema import (
    OUTCOME_TAGS,
    SCHEMA_VERSION,
    ConversationTurn,
    KajibaRecord,
    OutcomeSignals,
    QualityMetadata,
    Trajectory,
    validate_record,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    """Load a test fixture JSON file."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Valid record tests
# ---------------------------------------------------------------------------


class TestValidRecords:
    """Test that valid records parse without error."""

    def test_gold_tier_record(self) -> None:
        """A fully-populated gold-tier record validates successfully."""
        data = _load_fixture("gold_trajectory.json")
        record = validate_record(data)
        assert record.schema_version == SCHEMA_VERSION
        assert record.record_type == "task_trajectory"
        assert record.trajectory.turn_count == 10
        assert record.trajectory.total_tool_calls == 4
        assert record.trajectory.successful_tool_calls == 4
        assert record.trajectory.failed_tool_calls == 0
        assert record.model is not None
        assert record.model.model_name == "Hermes-3-Llama-3.1-8B"
        assert record.outcome is not None
        assert record.outcome.user_rating == 5
        assert "perfect" in record.outcome.outcome_tags
        assert record.hardware is not None
        assert record.hardware.gpu_name == "NVIDIA RTX 4090"

    def test_minimal_record(self) -> None:
        """A minimal record (trajectory only, no optional sections) validates."""
        data = _load_fixture("minimal_trajectory.json")
        record = validate_record(data)
        assert record.trajectory.turn_count == 2
        assert record.model is None
        assert record.hardware is None
        assert record.outcome is None
        assert record.pain_points is None
        assert record.submission is None

    def test_silver_record_with_all_sections(self) -> None:
        """A record with all optional sections validates."""
        data = _load_fixture("silver_trajectory.json")
        record = validate_record(data)
        assert record.model is not None
        assert record.outcome is not None
        assert record.outcome.user_rating == 3
        assert record.submission is not None

    def test_pii_record(self) -> None:
        """PII-laden record validates (PII is content, not schema issue)."""
        data = _load_fixture("pii_trajectory.json")
        record = validate_record(data)
        assert record.pain_points is not None
        assert len(record.pain_points) == 1
        assert record.pain_points[0].category == "safety_concern"


# ---------------------------------------------------------------------------
# Validation failure tests
# ---------------------------------------------------------------------------


class TestValidationFailures:
    """Test that invalid records raise ValidationError."""

    def test_bad_rating_too_high(self) -> None:
        """Rating > 5 must fail."""
        data = _load_fixture("minimal_trajectory.json")
        data["outcome"] = {"user_rating": 6, "outcome_tags": []}
        with pytest.raises(ValidationError):
            validate_record(data)

    def test_bad_rating_too_low(self) -> None:
        """Rating < 1 must fail."""
        data = _load_fixture("minimal_trajectory.json")
        data["outcome"] = {"user_rating": 0, "outcome_tags": []}
        with pytest.raises(ValidationError):
            validate_record(data)

    def test_unknown_outcome_tag(self) -> None:
        """An unknown outcome tag must fail validation."""
        data = _load_fixture("minimal_trajectory.json")
        data["outcome"] = {
            "user_rating": 3,
            "outcome_tags": ["totally_made_up_tag"],
        }
        with pytest.raises(ValidationError):
            validate_record(data)

    def test_inconsistent_tool_counts(self) -> None:
        """Tool counts that don't add up must fail."""
        data = _load_fixture("minimal_trajectory.json")
        data["trajectory"]["total_tool_calls"] = 5
        data["trajectory"]["successful_tool_calls"] = 2
        data["trajectory"]["failed_tool_calls"] = 1
        with pytest.raises(ValidationError):
            validate_record(data)

    def test_turn_count_mismatch(self) -> None:
        """turn_count != len(conversations) must fail."""
        data = _load_fixture("minimal_trajectory.json")
        data["trajectory"]["turn_count"] = 99
        with pytest.raises(ValidationError):
            validate_record(data)

    def test_empty_conversations(self) -> None:
        """Empty conversations list must fail."""
        data = _load_fixture("minimal_trajectory.json")
        data["trajectory"]["conversations"] = []
        data["trajectory"]["turn_count"] = 0
        with pytest.raises(ValidationError):
            validate_record(data)

    def test_invalid_record_type(self) -> None:
        """Unknown record type must fail."""
        data = _load_fixture("minimal_trajectory.json")
        data["record_type"] = "unknown_type"
        with pytest.raises(ValidationError):
            validate_record(data)


# ---------------------------------------------------------------------------
# Export method tests
# ---------------------------------------------------------------------------


class TestExportMethods:
    """Test ShareGPT and DPO export methods."""

    def test_sharegpt_export(self) -> None:
        """to_sharegpt() produces valid ShareGPT format."""
        data = _load_fixture("gold_trajectory.json")
        record = validate_record(data)
        sharegpt = record.to_sharegpt()

        assert "conversations" in sharegpt
        for turn in sharegpt["conversations"]:
            assert set(turn.keys()) == {"from", "value"}
            assert turn["from"] in ("human", "gpt")
            assert isinstance(turn["value"], str)

    def test_sharegpt_roundtrip(self) -> None:
        """ShareGPT export preserves turn count and content."""
        data = _load_fixture("gold_trajectory.json")
        record = validate_record(data)
        sharegpt = record.to_sharegpt()
        assert len(sharegpt["conversations"]) == record.trajectory.turn_count

        # Content should be preserved
        for i, turn in enumerate(sharegpt["conversations"]):
            assert turn["value"] == record.trajectory.conversations[i].value

    def test_dpo_candidate(self) -> None:
        """to_dpo_candidate() extracts prompt and response."""
        data = _load_fixture("gold_trajectory.json")
        record = validate_record(data)
        dpo = record.to_dpo_candidate()

        assert "prompt" in dpo
        assert "response" in dpo
        assert len(dpo["prompt"]) > 0
        assert len(dpo["response"]) > 0
        # Prompt should be the first human turn
        assert dpo["prompt"] == record.trajectory.conversations[0].value


# ---------------------------------------------------------------------------
# Record ID determinism tests
# ---------------------------------------------------------------------------


class TestRecordIdDeterminism:
    """Test that record IDs are deterministic."""

    def test_same_content_same_hash(self) -> None:
        """Same trajectory content must produce the same record_id."""
        data = _load_fixture("gold_trajectory.json")
        record1 = validate_record(data)
        record2 = validate_record(data)

        id1 = record1.compute_record_id()
        id2 = record2.compute_record_id()
        assert id1 == id2

    def test_different_content_different_hash(self) -> None:
        """Different trajectory content must produce different record_ids."""
        data1 = _load_fixture("gold_trajectory.json")
        data2 = _load_fixture("minimal_trajectory.json")
        record1 = validate_record(data1)
        record2 = validate_record(data2)

        id1 = record1.compute_record_id()
        id2 = record2.compute_record_id()
        assert id1 != id2

    def test_record_id_format(self) -> None:
        """Record IDs should have the kajiba_ prefix."""
        data = _load_fixture("gold_trajectory.json")
        record = validate_record(data)
        record_id = record.compute_record_id()
        assert record_id.startswith("kajiba_")
        assert len(record_id) == len("kajiba_") + 12  # 12 hex chars

    def test_submission_hash_format(self) -> None:
        """Submission hashes should have the sha256: prefix."""
        data = _load_fixture("gold_trajectory.json")
        record = validate_record(data)
        sub_hash = record.compute_submission_hash()
        assert sub_hash.startswith("sha256:")
        assert len(sub_hash) > len("sha256:") + 10


# ---------------------------------------------------------------------------
# Controlled vocabulary tests
# ---------------------------------------------------------------------------


class TestControlledVocabulary:
    """Test that controlled vocabularies are properly defined."""

    def test_outcome_tags_tuple(self) -> None:
        """OUTCOME_TAGS tuple should have all expected tags."""
        assert "task_completed" in OUTCOME_TAGS
        assert "perfect" in OUTCOME_TAGS
        assert "hallucination" in OUTCOME_TAGS
        assert "loop_detected" in OUTCOME_TAGS
        assert len(OUTCOME_TAGS) == 18

    def test_all_outcome_tags_valid_in_model(self) -> None:
        """Every tag in OUTCOME_TAGS should be accepted by the model."""
        data = _load_fixture("minimal_trajectory.json")
        for tag in OUTCOME_TAGS:
            test_data = {**data, "outcome": {"user_rating": 3, "outcome_tags": [tag]}}
            record = validate_record(test_data)
            assert tag in record.outcome.outcome_tags


# ---------------------------------------------------------------------------
# QualityMetadata tests
# ---------------------------------------------------------------------------


class TestQualityMetadata:
    """Test QualityMetadata model validation and KajibaRecord integration."""

    def test_valid_quality_metadata(self) -> None:
        """QualityMetadata with valid data validates successfully."""
        from datetime import UTC, datetime

        qm = QualityMetadata(
            quality_tier="gold",
            composite_score=0.9,
            sub_scores={
                "coherence": 0.95,
                "tool_validity": 1.0,
                "outcome_quality": 0.85,
                "information_density": 0.8,
                "metadata_completeness": 0.7,
            },
            scored_at=datetime.now(UTC),
        )
        assert qm.quality_tier == "gold"
        assert qm.composite_score == 0.9
        assert len(qm.sub_scores) == 5

    def test_composite_score_too_high(self) -> None:
        """composite_score > 1.0 must raise ValidationError."""
        from datetime import UTC, datetime

        with pytest.raises(ValidationError):
            QualityMetadata(
                quality_tier="gold",
                composite_score=1.5,
                sub_scores={"coherence": 0.9},
                scored_at=datetime.now(UTC),
            )

    def test_composite_score_too_low(self) -> None:
        """composite_score < 0.0 must raise ValidationError."""
        from datetime import UTC, datetime

        with pytest.raises(ValidationError):
            QualityMetadata(
                quality_tier="gold",
                composite_score=-0.1,
                sub_scores={"coherence": 0.9},
                scored_at=datetime.now(UTC),
            )

    def test_record_quality_none_backward_compat(self) -> None:
        """KajibaRecord with quality=None validates (backward compat)."""
        data = _load_fixture("minimal_trajectory.json")
        record = validate_record(data)
        assert record.quality is None

    def test_record_quality_roundtrip(self) -> None:
        """KajibaRecord with QualityMetadata round-trips through dump/validate."""
        from datetime import UTC, datetime

        data = _load_fixture("minimal_trajectory.json")
        record = validate_record(data)
        record.quality = QualityMetadata(
            quality_tier="silver",
            composite_score=0.72,
            sub_scores={
                "coherence": 0.8,
                "tool_validity": 1.0,
                "outcome_quality": 0.5,
                "information_density": 0.5,
                "metadata_completeness": 0.3,
            },
            scored_at=datetime.now(UTC),
        )

        dumped = record.model_dump(mode="json", by_alias=True)
        restored = validate_record(dumped)
        assert restored.quality is not None
        assert restored.quality.quality_tier == "silver"
        assert restored.quality.composite_score == 0.72
        assert "coherence" in restored.quality.sub_scores
