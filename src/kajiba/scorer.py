"""Quality scoring system for Kajiba records.

Implements the five-sub-score quality system from Section 3 of the spec.
Each record receives a composite score (0.0-1.0) and a quality tier
(gold/silver/bronze/review_needed).
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from kajiba.schema import KajibaRecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Quality tier thresholds
# ---------------------------------------------------------------------------

GOLD_THRESHOLD = 0.85
SILVER_THRESHOLD = 0.65
BRONZE_THRESHOLD = 0.45

# Sub-score weights
WEIGHTS = {
    "coherence": 0.30,
    "tool_validity": 0.25,
    "outcome_quality": 0.20,
    "information_density": 0.15,
    "metadata_completeness": 0.10,
}


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class QualityResult:
    """Result of quality scoring a record."""

    composite_score: float
    sub_scores: dict[str, float]
    quality_tier: str  # "gold", "silver", "bronze", "review_needed"


# ---------------------------------------------------------------------------
# Sub-score functions
# ---------------------------------------------------------------------------


def score_coherence(record: KajibaRecord) -> float:
    """Score trajectory coherence (weight: 0.30).

    Checks:
    - Alternating human/gpt turns (no double-human or double-gpt)
    - Tool calls appear only in gpt turns
    - No empty turns (value is non-empty string)
    - Conversation has at least 2 turns
    - Final turn is from gpt (task was attempted)
    """
    turns = record.trajectory.conversations

    if len(turns) < 2:
        return 0.0

    score = 1.0

    for i, turn in enumerate(turns):
        expected_role = "human" if i % 2 == 0 else "gpt"
        if turn.from_ != expected_role:
            score -= 0.15

        if not turn.value.strip():
            score -= 0.10

        if turn.tool_calls:
            if turn.from_ != "gpt":
                score -= 0.20
            for tc in turn.tool_calls:
                if not tc.tool_name or not tc.tool_status:
                    score -= 0.05

    if turns[-1].from_ != "gpt":
        score -= 0.10

    return max(0.0, score)


def score_tool_validity(record: KajibaRecord) -> float:
    """Score tool call validity (weight: 0.25).

    Checks:
    - Tool calls have all required fields
    - Success/failure counts match the actual tool_status values
    - No tool calls with status "success" but empty output
    - No tool calls with unreasonable latency (>300s = suspicious)
    """
    trajectory = record.trajectory
    tool_calls = []
    for turn in trajectory.conversations:
        if turn.tool_calls:
            tool_calls.extend(turn.tool_calls)

    if not tool_calls:
        return 1.0

    score = 1.0
    actual_success = sum(1 for tc in tool_calls if tc.tool_status == "success")
    actual_failure = sum(1 for tc in tool_calls if tc.tool_status != "success")

    if trajectory.successful_tool_calls != actual_success:
        score -= 0.15
    if trajectory.failed_tool_calls != actual_failure:
        score -= 0.15

    for tc in tool_calls:
        if tc.tool_status == "success" and not (tc.tool_output or "").strip():
            score -= 0.10
        if tc.latency_ms is not None and tc.latency_ms > 300_000:
            score -= 0.05

    return max(0.0, score)


def score_outcome_quality(record: KajibaRecord) -> float:
    """Score outcome signal quality (weight: 0.20).

    Checks:
    - If rating is 5 and tags include 'task_failed' -> inconsistent
    - If rating is 1 and tags include 'perfect' -> inconsistent
    - Presence of user_comment adds value
    """
    outcome = record.outcome
    if not outcome:
        return 0.5

    score = 1.0
    rating = outcome.user_rating
    tags = outcome.outcome_tags

    if rating >= 4 and "task_failed" in tags:
        score -= 0.30
    if rating <= 2 and "perfect" in tags:
        score -= 0.30
    if rating >= 4 and "hallucination" in tags and "minor_hallucination" not in tags:
        score -= 0.15

    if outcome.user_comment and len(outcome.user_comment) > 20:
        score = min(1.0, score + 0.10)

    return max(0.0, score)


def score_information_density(record: KajibaRecord) -> float:
    """Score information density (weight: 0.15).

    Checks:
    - Total token count across all turns
    - Ratio of gpt tokens to human tokens
    - Presence of tool calls adds value
    - Multi-turn interactions score higher
    """
    turns = record.trajectory.conversations
    total_tokens = sum(
        t.token_count if t.token_count is not None else len(t.value.split())
        for t in turns
    )
    gpt_tokens = sum(
        t.token_count if t.token_count is not None else len(t.value.split())
        for t in turns
        if t.from_ == "gpt"
    )
    human_tokens = total_tokens - gpt_tokens

    if total_tokens < 100:
        return 0.2
    if total_tokens < 300:
        return 0.5

    score = 0.7

    if record.trajectory.total_tool_calls > 0:
        score += 0.15

    if record.trajectory.turn_count >= 4:
        score += 0.10

    if human_tokens > 0 and gpt_tokens / human_tokens < 0.5:
        score -= 0.15

    return min(1.0, max(0.0, score))


def score_metadata_completeness(record: KajibaRecord) -> float:
    """Score metadata completeness (weight: 0.10).

    Simply counts how many optional sections are present and populated.
    """
    score = 0.0
    if record.model and record.model.model_name:
        score += 0.30
    if record.model and record.model.quantization:
        score += 0.15
    if record.model and record.model.provider:
        score += 0.10
    if record.hardware and record.hardware.gpu_name:
        score += 0.20
    if record.outcome and record.outcome.user_rating:
        score += 0.15
    if record.pain_points:
        score += 0.10
    return min(1.0, score)


# ---------------------------------------------------------------------------
# Composite scorer
# ---------------------------------------------------------------------------


def compute_quality_score(record: KajibaRecord) -> QualityResult:
    """Compute the composite quality score and tier for a record.

    Combines five weighted sub-scores into a single composite score
    and assigns a quality tier.

    Args:
        record: The KajibaRecord to score.

    Returns:
        QualityResult with composite_score, sub_scores dict, and quality_tier.
    """
    sub_scores = {
        "coherence": score_coherence(record),
        "tool_validity": score_tool_validity(record),
        "outcome_quality": score_outcome_quality(record),
        "information_density": score_information_density(record),
        "metadata_completeness": score_metadata_completeness(record),
    }

    composite = sum(sub_scores[k] * WEIGHTS[k] for k in WEIGHTS)

    if composite >= GOLD_THRESHOLD:
        tier = "gold"
    elif composite >= SILVER_THRESHOLD:
        tier = "silver"
    elif composite >= BRONZE_THRESHOLD:
        tier = "bronze"
    else:
        tier = "review_needed"

    return QualityResult(
        composite_score=round(composite, 3),
        sub_scores={k: round(v, 3) for k, v in sub_scores.items()},
        quality_tier=tier,
    )
