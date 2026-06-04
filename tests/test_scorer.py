"""Tests for the quality scoring system."""

import json
from pathlib import Path

import pytest

from kajiba.schema import (
    ConversationTurn,
    HardwareProfile,
    KajibaRecord,
    ModelMetadata,
    OutcomeSignals,
    PainPoint,
    Trajectory,
    validate_record,
)
from kajiba.scorer import (
    BRONZE_THRESHOLD,
    GOLD_THRESHOLD,
    SILVER_THRESHOLD,
    compute_quality_score,
    score_coherence,
    score_information_density,
    score_metadata_completeness,
    score_outcome_quality,
    score_tool_validity,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _make_record(**kwargs) -> KajibaRecord:
    """Build a KajibaRecord from keyword arguments with sensible defaults."""
    conversations = kwargs.pop("conversations", [
        ConversationTurn(**{"from": "human"}, value="Hello"),
        ConversationTurn(**{"from": "gpt"}, value="Hi there! How can I help you today?"),
    ])
    turn_count = kwargs.pop("turn_count", len(conversations))
    total_tc = kwargs.pop("total_tool_calls", 0)
    success_tc = kwargs.pop("successful_tool_calls", 0)
    fail_tc = kwargs.pop("failed_tool_calls", 0)

    trajectory = Trajectory(
        conversations=conversations,
        turn_count=turn_count,
        total_tool_calls=total_tc,
        successful_tool_calls=success_tc,
        failed_tool_calls=fail_tc,
    )
    return KajibaRecord(trajectory=trajectory, **kwargs)


# ---------------------------------------------------------------------------
# Tier tests with fixtures
# ---------------------------------------------------------------------------


class TestQualityTiers:
    """Test that fixture records hit their expected quality tiers."""

    def test_gold_fixture(self) -> None:
        """Gold fixture should score gold tier."""
        data = _load_fixture("gold_trajectory.json")
        record = validate_record(data)
        result = compute_quality_score(record)
        assert result.quality_tier == "gold"
        assert result.composite_score >= GOLD_THRESHOLD

    def test_silver_fixture(self) -> None:
        """Silver fixture should score silver tier."""
        data = _load_fixture("silver_trajectory.json")
        record = validate_record(data)
        result = compute_quality_score(record)
        assert result.quality_tier == "silver"
        assert result.composite_score >= SILVER_THRESHOLD
        assert result.composite_score < GOLD_THRESHOLD

    def test_minimal_fixture_bronze_or_below(self) -> None:
        """Minimal fixture (no metadata) should score bronze or below."""
        data = _load_fixture("minimal_trajectory.json")
        record = validate_record(data)
        result = compute_quality_score(record)
        # Minimal record: no metadata, no tools, only 2 turns, no outcome
        assert result.composite_score < GOLD_THRESHOLD

    def test_adversarial_fixture_review_needed(self) -> None:
        """Adversarial fixture should score review_needed."""
        data = _load_fixture("adversarial_trajectory.json")
        record = validate_record(data)
        result = compute_quality_score(record)
        assert result.quality_tier == "review_needed"
        assert result.composite_score < BRONZE_THRESHOLD


# ---------------------------------------------------------------------------
# Sub-score tests
# ---------------------------------------------------------------------------


class TestCoherenceScore:
    """Test the coherence sub-score."""

    def test_perfect_alternation(self) -> None:
        """Perfectly alternating turns should score high."""
        data = _load_fixture("gold_trajectory.json")
        record = validate_record(data)
        score = score_coherence(record)
        assert score >= 0.9

    def test_single_turn(self) -> None:
        """Single turn should score 0.0."""
        record = _make_record(
            conversations=[
                ConversationTurn(**{"from": "human"}, value="Hello"),
            ],
            turn_count=1,
        )
        score = score_coherence(record)
        assert score == 0.0

    def test_empty_turn_penalty(self) -> None:
        """Empty turn values should incur a penalty."""
        record = _make_record(
            conversations=[
                ConversationTurn(**{"from": "human"}, value="Hello"),
                ConversationTurn(**{"from": "gpt"}, value=""),
            ],
        )
        score = score_coherence(record)
        assert score < 1.0


class TestToolValidityScore:
    """Test the tool validity sub-score."""

    def test_no_tool_calls(self) -> None:
        """No tool calls should return 1.0 (not applicable)."""
        data = _load_fixture("minimal_trajectory.json")
        record = validate_record(data)
        score = score_tool_validity(record)
        assert score == 1.0

    def test_correct_tool_counts(self) -> None:
        """Correct tool counts should score high."""
        data = _load_fixture("gold_trajectory.json")
        record = validate_record(data)
        score = score_tool_validity(record)
        assert score >= 0.8

    def test_mismatched_tool_counts(self) -> None:
        """Mismatched tool counts should be penalized."""
        data = _load_fixture("adversarial_trajectory.json")
        record = validate_record(data)
        score = score_tool_validity(record)
        assert score < 1.0


class TestOutcomeQualityScore:
    """Test the outcome quality sub-score."""

    def test_no_outcome(self) -> None:
        """No outcome should return 0.5 (neutral)."""
        data = _load_fixture("minimal_trajectory.json")
        record = validate_record(data)
        score = score_outcome_quality(record)
        assert score == 0.5

    def test_consistent_high_rating(self) -> None:
        """High rating with consistent tags should score high."""
        data = _load_fixture("gold_trajectory.json")
        record = validate_record(data)
        score = score_outcome_quality(record)
        assert score >= 0.9

    def test_inconsistent_rating_tags(self) -> None:
        """Rating 5 with task_failed tag should be penalized."""
        data = _load_fixture("adversarial_trajectory.json")
        record = validate_record(data)
        score = score_outcome_quality(record)
        assert score < 0.7

    def test_comment_bonus(self) -> None:
        """User comment > 20 chars should add bonus."""
        # Use a scenario where base score < 1.0 so bonus is visible
        record = _make_record(
            outcome=OutcomeSignals(
                user_rating=4,
                outcome_tags=["task_completed", "hallucination"],
                user_comment="This interaction had a hallucination but still completed the task.",
            ),
        )
        score_with_comment = score_outcome_quality(record)

        record_no_comment = _make_record(
            outcome=OutcomeSignals(
                user_rating=4,
                outcome_tags=["task_completed", "hallucination"],
            ),
        )
        score_without = score_outcome_quality(record_no_comment)
        assert score_with_comment > score_without


class TestInformationDensityScore:
    """Test the information density sub-score."""

    def test_minimal_record_low_density(self) -> None:
        """Very short conversations should score low."""
        record = _make_record(
            conversations=[
                ConversationTurn(**{"from": "human"}, value="Hi"),
                ConversationTurn(**{"from": "gpt"}, value="Hello"),
            ],
        )
        score = score_information_density(record)
        assert score <= 0.5

    def test_rich_record_high_density(self) -> None:
        """Rich conversations with tool calls should score high."""
        data = _load_fixture("gold_trajectory.json")
        record = validate_record(data)
        score = score_information_density(record)
        assert score >= 0.7


class TestMetadataCompletenessScore:
    """Test the metadata completeness sub-score."""

    def test_no_metadata(self) -> None:
        """Record with no optional metadata should score 0.0."""
        data = _load_fixture("minimal_trajectory.json")
        record = validate_record(data)
        score = score_metadata_completeness(record)
        assert score == 0.0

    def test_full_metadata(self) -> None:
        """Record with all metadata should score high."""
        data = _load_fixture("gold_trajectory.json")
        record = validate_record(data)
        score = score_metadata_completeness(record)
        assert score >= 0.8


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test edge cases in scoring."""

    def test_only_one_turn_coherence(self) -> None:
        """Record with 1 turn should get 0 coherence."""
        record = _make_record(
            conversations=[
                ConversationTurn(**{"from": "human"}, value="Hello"),
            ],
            turn_count=1,
        )
        assert score_coherence(record) == 0.0

    def test_sub_scores_in_result(self) -> None:
        """QualityResult should contain all five sub-scores."""
        data = _load_fixture("gold_trajectory.json")
        record = validate_record(data)
        result = compute_quality_score(record)
        assert set(result.sub_scores.keys()) == {
            "coherence",
            "tool_validity",
            "outcome_quality",
            "information_density",
            "metadata_completeness",
        }

    def test_composite_score_range(self) -> None:
        """Composite score should always be between 0 and 1."""
        for fixture_name in [
            "gold_trajectory.json",
            "silver_trajectory.json",
            "minimal_trajectory.json",
            "adversarial_trajectory.json",
        ]:
            data = _load_fixture(fixture_name)
            record = validate_record(data)
            result = compute_quality_score(record)
            assert 0.0 <= result.composite_score <= 1.0
