"""Eval completeness/confidence scorer for ExperimentRecord (EEVAL-01).

This module is a *completeness/confidence lens on the eval RECORD* — it answers
"is this logged experiment complete enough to analyze and trust?" — NOT a
re-judgment of the model's answer (D-01). The existing ``eval_score`` field on
``ExperimentOutcome`` remains the answer-quality signal; this scorer deliberately
excludes it from completeness credit (Pitfall 4).

It mirrors ``scorer.py``'s structure (WEIGHTS dict, threshold constants, a
frozen-shape result dataclass, a ``compute_*`` entrypoint, private ``_score_*``
sub-checks) but is a NEW single-responsibility module (D-09, mirrors
``experiment_store.py``) and uses eval-native band vocabulary —
``complete`` / ``partial`` / ``thin`` — which is DISTINCT from the coding
scorer's community quality tiers (D-02). Bands here are advisory/analysis-only
(D-04); nothing is persisted and the schema stays frozen (compute-on-read, D-03).
"""

import logging
from dataclasses import dataclass

from kajiba.schema import ExperimentRecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Confidence band thresholds (LOCKED — see plan <scoring_contract>)
# ---------------------------------------------------------------------------

COMPLETE_THRESHOLD = 0.80
PARTIAL_THRESHOLD = 0.50

# Minimum non-trivial length for local_model_output to count as present.
_MIN_OUTPUT_LEN = 20

# Sub-check weights (LOCKED, sum == 1.0)
WEIGHTS = {
    "output_present": 0.30,
    "reviewer_critique": 0.20,
    "model_metadata": 0.20,
    "hardware_present": 0.10,
    "lessons_learned": 0.10,
    "outcome_signals": 0.10,
}


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class EvalConfidenceResult:
    """Result of scoring the completeness/confidence of an ExperimentRecord."""

    composite_score: float
    sub_scores: dict[str, float]
    confidence_band: str  # "complete", "partial", "thin"


# ---------------------------------------------------------------------------
# Sub-score functions (each returns a float in [0.0, 1.0])
# ---------------------------------------------------------------------------


def _score_output_present(record: ExperimentRecord) -> float:
    """Score presence of the model output (weight: 0.30).

    Returns:
        1.0 if ``outcome.local_model_output`` is present and non-trivial
        (length >= _MIN_OUTPUT_LEN), else 0.0.
    """
    output = record.outcome.local_model_output
    if output and len(output.strip()) >= _MIN_OUTPUT_LEN:
        return 1.0
    return 0.0


def _score_reviewer_critique(record: ExperimentRecord) -> float:
    """Score presence of a reviewer critique (weight: 0.20).

    The field is Optional; an absent critique scores 0.0, never an error
    (Pitfall 2).

    Returns:
        1.0 if ``outcome.reviewer_critique`` is a non-empty string, else 0.0.
    """
    critique = record.outcome.reviewer_critique
    if critique and critique.strip():
        return 1.0
    return 0.0


def _score_model_metadata(record: ExperimentRecord) -> float:
    """Score local-model identity completeness (weight: 0.20).

    Additive fraction of the three identity fields populated, mirroring
    ``score_metadata_completeness``'s additive idiom.

    Returns:
        Fraction in [0.0, 1.0] of {model_name, quantization, provider} present.
    """
    local_model = record.experiment.local_model
    present = 0
    if local_model.model_name:
        present += 1
    if local_model.quantization:
        present += 1
    if local_model.provider:
        present += 1
    return present / 3.0


def _score_hardware_present(record: ExperimentRecord) -> float:
    """Score presence of hardware metadata (weight: 0.10).

    Returns:
        1.0 if ``record.hardware`` is populated (gpu_name present), else 0.0.
    """
    if record.hardware and record.hardware.gpu_name:
        return 1.0
    return 0.0


def _score_lessons_learned(record: ExperimentRecord) -> float:
    """Score presence of lessons learned (weight: 0.10).

    Returns:
        1.0 if ``outcome.lessons_learned`` is a non-empty list, else 0.0.
    """
    if record.outcome.lessons_learned:
        return 1.0
    return 0.0


def _score_outcome_signals(record: ExperimentRecord) -> float:
    """Score completeness of outcome signals (weight: 0.10).

    Scores ONLY ``recommended_action`` and ``completed_at`` (each contributes
    0.5). It deliberately does NOT credit ``eval_score`` being in range — a sane
    eval_score is the schema's job and is the *answer-quality* signal, not a
    completeness signal (Pitfall 4). This guarantees a required-fields-only
    record (only eval_score present) scores 0.0 here, keeping the thin fixture
    below PARTIAL_THRESHOLD.

    Returns:
        Fraction in {0.0, 0.5, 1.0} of {recommended_action, completed_at} present.
    """
    score = 0.0
    if record.outcome.recommended_action:
        score += 0.5
    if record.experiment.completed_at:
        score += 0.5
    return score


# ---------------------------------------------------------------------------
# Composite scorer
# ---------------------------------------------------------------------------


def compute_eval_confidence(record: ExperimentRecord) -> EvalConfidenceResult:
    """Compute the completeness/confidence composite and band for an experiment.

    Combines six weighted eval-native sub-checks into a single composite score
    in [0.0, 1.0] and assigns a confidence band (complete/partial/thin). This is
    a trust lens on the eval RECORD's completeness (D-01), never a re-judgment of
    the model's answer.

    Args:
        record: The ExperimentRecord to score. A non-experiment record (e.g. a
            coding-session KajibaRecord) is rejected — the completeness lens
            applies to experiments only (D-01).

    Returns:
        EvalConfidenceResult with composite_score, sub_scores dict, and
        confidence_band.

    Raises:
        TypeError: If ``record`` is not an ExperimentRecord.
    """
    if not isinstance(record, ExperimentRecord):
        raise TypeError(
            "compute_eval_confidence requires an ExperimentRecord; got "
            f"{type(record).__name__}. The eval-confidence lens applies to "
            "model-experiment records only."
        )

    sub_scores = {
        "output_present": _score_output_present(record),
        "reviewer_critique": _score_reviewer_critique(record),
        "model_metadata": _score_model_metadata(record),
        "hardware_present": _score_hardware_present(record),
        "lessons_learned": _score_lessons_learned(record),
        "outcome_signals": _score_outcome_signals(record),
    }

    composite = sum(sub_scores[k] * WEIGHTS[k] for k in WEIGHTS)

    if composite >= COMPLETE_THRESHOLD:
        band = "complete"
    elif composite >= PARTIAL_THRESHOLD:
        band = "partial"
    else:
        band = "thin"

    return EvalConfidenceResult(
        composite_score=round(composite, 3),
        sub_scores={k: round(v, 3) for k, v in sub_scores.items()},
        confidence_band=band,
    )
