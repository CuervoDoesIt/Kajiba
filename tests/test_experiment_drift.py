"""RED test scaffold for the experiment drift detector (Plan 03, EREV-03).

These tests intentionally fail until ``kajiba.experiment_drift`` is
implemented in Wave 2. The failing import is the RED signal — do NOT add
``@pytest.mark.skip`` or stub the production module to make them pass.

``compute_drift(records, threshold=DRIFT_THRESHOLD) -> dict[str, bool]`` is a
PURE function: no store, no CLI, no file I/O. It groups records by
``(experiment.local_model.model_name, experiment.task_category)`` and, within
each group, compares every run's ``outcome.eval_score`` to the leave-one-out
mean of the OTHER runs in its group (RESEARCH Pattern 3). A run drifts when the
absolute deviation exceeds ``threshold`` (both directions, D-14). Groups with
fewer than two runs never flag (<2-run guard, no ``mean([])`` crash). The
returned dict has an entry for EVERY input record_id so callers can SET and
CLEAR idempotently (D-15).
"""

from datetime import UTC, datetime

from kajiba.experiment_drift import DRIFT_THRESHOLD, compute_drift
from kajiba.schema import (
    ExperimentMetadata,
    ExperimentOutcome,
    ExperimentRecord,
    ModelMetadata,
)


def _make_record(
    *,
    experiment_id: str,
    eval_score: float,
    model_name: str = "Hermes-3-Llama-3.1-8B",
    task_category: str = "coding",
    started_minute: int = 0,
) -> ExperimentRecord:
    """Build an ExperimentRecord varying the fields compute_drift groups/reads.

    A distinct experiment_id + started_at per run guarantees a distinct
    record_id (identity is content-addressable over those fields).
    """
    rec = ExperimentRecord(
        experiment=ExperimentMetadata(
            experiment_id=experiment_id,
            experiment_type="model_evaluation",
            local_model=ModelMetadata(model_name=model_name),
            task_category=task_category,
            task_description="Write a binary search function.",
            started_at=datetime(2026, 6, 3, 12, started_minute, 0, tzinfo=UTC),
        ),
        outcome=ExperimentOutcome(
            local_model_output=f"output-{experiment_id}",
            eval_score=eval_score,
        ),
    )
    rec.compute_record_id()
    return rec


def test_flags_regression() -> None:
    """A run whose score drops below the leave-one-out mean by > threshold flags."""
    a = _make_record(experiment_id="a", eval_score=0.90, started_minute=0)
    b = _make_record(experiment_id="b", eval_score=0.90, started_minute=1)
    # Leave-one-out mean for c = mean(0.90, 0.90) = 0.90; deviation 0.40 > 0.15.
    c = _make_record(experiment_id="c", eval_score=0.50, started_minute=2)

    verdict = compute_drift([a, b, c])

    assert verdict[c.record_id] is True
    assert verdict[a.record_id] is False
    assert verdict[b.record_id] is False


def test_flags_improvement() -> None:
    """A run whose score rises above the leave-one-out mean by > threshold flags (D-14)."""
    a = _make_record(experiment_id="a", eval_score=0.50, started_minute=0)
    b = _make_record(experiment_id="b", eval_score=0.50, started_minute=1)
    # Leave-one-out mean for c = 0.50; deviation 0.40 upward > 0.15.
    c = _make_record(experiment_id="c", eval_score=0.90, started_minute=2)

    verdict = compute_drift([a, b, c])

    assert verdict[c.record_id] is True
    assert verdict[a.record_id] is False
    assert verdict[b.record_id] is False


def test_under_threshold_not_flagged() -> None:
    """Runs that all sit within threshold of each other never flag."""
    a = _make_record(experiment_id="a", eval_score=0.80, started_minute=0)
    b = _make_record(experiment_id="b", eval_score=0.82, started_minute=1)
    c = _make_record(experiment_id="c", eval_score=0.84, started_minute=2)

    verdict = compute_drift([a, b, c])

    assert verdict[a.record_id] is False
    assert verdict[b.record_id] is False
    assert verdict[c.record_id] is False


def test_group_of_one_never_flagged() -> None:
    """A single-run group returns False and never raises (mean([]) guard)."""
    a = _make_record(experiment_id="a", eval_score=0.99, started_minute=0)

    verdict = compute_drift([a])

    assert verdict[a.record_id] is False


def test_threshold_override() -> None:
    """A tighter threshold flags runs the default 0.15 leaves alone."""
    a = _make_record(experiment_id="a", eval_score=0.80, started_minute=0)
    b = _make_record(experiment_id="b", eval_score=0.80, started_minute=1)
    # Leave-one-out mean for c = 0.80; deviation 0.10: under default 0.15,
    # over a tight 0.05.
    c = _make_record(experiment_id="c", eval_score=0.70, started_minute=2)

    default_verdict = compute_drift([a, b, c])
    tight_verdict = compute_drift([a, b, c], threshold=0.05)

    assert default_verdict[c.record_id] is False
    assert tight_verdict[c.record_id] is True


def test_verdict_covers_all_records() -> None:
    """The returned dict has an entry for every input record_id (D-15)."""
    recs = [
        _make_record(experiment_id="a", eval_score=0.90, started_minute=0),
        _make_record(experiment_id="b", eval_score=0.50, started_minute=1),
        _make_record(experiment_id="c", eval_score=0.92, started_minute=2),
    ]

    verdict = compute_drift(recs)

    assert set(verdict.keys()) == {r.record_id for r in recs}


def test_groups_isolated() -> None:
    """Drift in one (model, task) group never flags records in another group."""
    # Group 1: coding on model X — one clear outlier.
    g1a = _make_record(
        experiment_id="g1a", eval_score=0.90, model_name="modelX",
        task_category="coding", started_minute=0,
    )
    g1b = _make_record(
        experiment_id="g1b", eval_score=0.90, model_name="modelX",
        task_category="coding", started_minute=1,
    )
    g1c = _make_record(
        experiment_id="g1c", eval_score=0.40, model_name="modelX",
        task_category="coding", started_minute=2,
    )
    # Group 2: writing on model Y — perfectly consistent.
    g2a = _make_record(
        experiment_id="g2a", eval_score=0.70, model_name="modelY",
        task_category="writing", started_minute=3,
    )
    g2b = _make_record(
        experiment_id="g2b", eval_score=0.70, model_name="modelY",
        task_category="writing", started_minute=4,
    )

    verdict = compute_drift([g1a, g1b, g1c, g2a, g2b])

    assert verdict[g1c.record_id] is True
    assert verdict[g2a.record_id] is False
    assert verdict[g2b.record_id] is False
