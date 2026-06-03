"""ExperimentRecord tests for the Phase 10 dual-use schema (ESCH-03).

Covers JSON round-trip equality, controlled-vocabulary rejection for
experiment_type and recommended_action, the recommended_action=None
default, the lessons_learned empty default, and eval_score bounds.
"""

from datetime import UTC, datetime

import pydantic
import pytest

from kajiba.schema import (
    ExperimentMetadata,
    ExperimentOutcome,
    ExperimentRecord,
    ModelMetadata,
)


def _make_experiment_record(**overrides) -> ExperimentRecord:
    """Build a fully populated ExperimentRecord with overridable fields."""
    experiment = overrides.pop(
        "experiment",
        ExperimentMetadata(
            experiment_id="exp_001",
            experiment_type="model_evaluation",
            local_model=ModelMetadata(model_name="Hermes-3-Llama-3.1-8B"),
            reviewer_model=ModelMetadata(model_name="gpt-4o"),
            task_category="coding",
            task_description="Write a binary search function.",
            started_at=datetime(2026, 6, 3, 12, 0, 0, tzinfo=UTC),
            completed_at=datetime(2026, 6, 3, 12, 5, 0, tzinfo=UTC),
        ),
    )
    outcome = overrides.pop(
        "outcome",
        ExperimentOutcome(
            local_model_output="def bsearch(a, x): ...",
            reviewer_critique="Correct but missing edge cases.",
            eval_score=0.82,
            drift_flag=False,
            lessons_learned=["handle empty input"],
            recommended_action="needs_fine_tune",
        ),
    )
    return ExperimentRecord(experiment=experiment, outcome=outcome, **overrides)


class TestExperimentRecord:
    """Validate ExperimentRecord behaviors required by ESCH-03."""

    def test_round_trip(self) -> None:
        """A fully populated record round-trips dump -> validate to equality."""
        rec = _make_experiment_record()
        dumped = rec.model_dump(mode="json", by_alias=True)
        rebuilt = ExperimentRecord.model_validate(dumped)
        assert rebuilt == rec

    def test_record_kind_is_model_experiment(self) -> None:
        """record_kind defaults to 'model_experiment' for ExperimentRecord."""
        assert _make_experiment_record().record_kind == "model_experiment"

    def test_experiment_type_rejects_out_of_vocab(self) -> None:
        """An out-of-vocab experiment_type raises ValidationError."""
        with pytest.raises(pydantic.ValidationError):
            ExperimentMetadata(
                experiment_id="exp_002",
                experiment_type="bogus",
                local_model=ModelMetadata(model_name="m"),
                task_category="coding",
                task_description="desc",
                started_at=datetime(2026, 6, 3, tzinfo=UTC),
            )

    def test_recommended_action_rejects_out_of_vocab(self) -> None:
        """An out-of-vocab recommended_action raises ValidationError."""
        with pytest.raises(pydantic.ValidationError):
            ExperimentOutcome(
                local_model_output="out",
                eval_score=0.5,
                recommended_action="nope",
            )

    def test_recommended_action_none_accepted(self) -> None:
        """recommended_action defaults to None and accepts None explicitly."""
        outcome = ExperimentOutcome(local_model_output="out", eval_score=0.5)
        assert outcome.recommended_action is None
        explicit = ExperimentOutcome(
            local_model_output="out", eval_score=0.5, recommended_action=None
        )
        assert explicit.recommended_action is None

    def test_lessons_learned_defaults_empty(self) -> None:
        """lessons_learned defaults to [] and accepts a list[str]."""
        outcome = ExperimentOutcome(local_model_output="out", eval_score=0.5)
        assert outcome.lessons_learned == []
        populated = ExperimentOutcome(
            local_model_output="out",
            eval_score=0.5,
            lessons_learned=["a", "b"],
        )
        assert populated.lessons_learned == ["a", "b"]

    def test_eval_score_bounds(self) -> None:
        """eval_score outside the 0.0-1.0 range raises ValidationError."""
        with pytest.raises(pydantic.ValidationError):
            ExperimentOutcome(local_model_output="out", eval_score=1.5)
        with pytest.raises(pydantic.ValidationError):
            ExperimentOutcome(local_model_output="out", eval_score=-0.1)
