"""RED test scaffold for the experiment eval-confidence scorer (Plan 02).

These tests intentionally fail at collection time with ModuleNotFoundError
until ``kajiba.eval_scorer`` is implemented in Wave 2. The failing import is
the RED signal — do NOT add ``@pytest.mark.skip``.
"""

import json
from pathlib import Path

import pytest

from kajiba.eval_scorer import EvalConfidenceResult, compute_eval_confidence
from kajiba.schema import KajibaRecord, load_record

FIXTURES = Path(__file__).parent / "fixtures"

EXPERIMENT_BANDS = {"complete", "partial", "thin"}
COMMUNITY_TIERS = {"gold", "silver", "bronze", "review_needed"}


def _load_fixture(name: str) -> dict:
    """Load a JSON fixture from the fixtures directory."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_complete_experiment_scores_complete() -> None:
    """A fully-populated experiment lands in the complete band with a high score."""
    record = load_record(_load_fixture("experiment_complete.json"))
    result = compute_eval_confidence(record)
    assert result.confidence_band == "complete"
    assert result.composite_score >= 0.80


def test_thin_experiment_scores_thin() -> None:
    """A required-fields-only experiment lands in the thin band below the partial threshold."""
    record = load_record(_load_fixture("experiment_thin.json"))
    result = compute_eval_confidence(record)
    assert result.confidence_band == "thin"
    assert result.composite_score < 0.50


def test_band_vocabulary_distinct() -> None:
    """Every confidence band is experiment-vocabulary, never a community quality tier."""
    for name in ("experiment_complete.json", "experiment_thin.json", "experiment_pii.json"):
        record = load_record(_load_fixture(name))
        result = compute_eval_confidence(record)
        assert result.confidence_band in EXPERIMENT_BANDS
        assert result.confidence_band not in COMMUNITY_TIERS


def test_experiment_only() -> None:
    """The scorer rejects a non-experiment (coding-session) record."""
    record = load_record(_load_fixture("gold_trajectory.json"))
    assert isinstance(record, KajibaRecord)
    with pytest.raises((TypeError, ValueError)):
        compute_eval_confidence(record)
