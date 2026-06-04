"""Persistence tests for the private experiment store (ELOG-02 + ELOG-03).

Covers the single atomic write path in ``kajiba.experiment_store``:
``build_experiment_record`` (the convenience constructor) and
``log_experiment`` (the direct-to-store write). These tests own the
six behaviors required of the store module — record construction, file
write + path return, atomic write, content-addressable dedup, the
package-level re-exports (D-07), and the D-13 structural write guard.

Store isolation uses ``tmp_path / "experiments"`` passed straight to
``log_experiment`` as ``store_dir``; the store module is Click-free, so
no monkeypatch of CLI constants is needed (RESEARCH Pitfall 2).
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from kajiba.schema import (
    ExperimentMetadata,
    ExperimentOutcome,
    ExperimentRecord,
    ModelMetadata,
)


def _make_record(**overrides) -> ExperimentRecord:
    """Build a fully populated ExperimentRecord mirroring test_schema_experiment."""
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


def test_build_record() -> None:
    """build_experiment_record(**fields) returns a valid model_experiment record."""
    from kajiba.experiment_store import build_experiment_record

    rec = build_experiment_record(
        experiment_id="exp_001",
        experiment_type="model_evaluation",
        task_category="coding",
        task_description="Write a binary search function.",
        local_model_name="Hermes-3-Llama-3.1-8B",
        local_model_output="def bsearch(a, x): ...",
        eval_score=0.82,
    )
    assert isinstance(rec, ExperimentRecord)
    assert rec.record_kind == "model_experiment"
    assert rec.outcome.eval_score == 0.82
    assert rec.experiment.experiment_type == "model_evaluation"


def test_log_writes_file(tmp_path: Path) -> None:
    """log_experiment writes exp_<record_id>.json and returns its path."""
    from kajiba.experiment_store import log_experiment

    store = tmp_path / "experiments"
    rec = _make_record()
    dest = log_experiment(rec, store)

    assert dest.exists()
    assert dest.parent == store
    assert rec.record_id is not None
    assert rec.record_id.startswith("kajiba_exp_")
    assert dest.name == f"exp_{rec.record_id}.json"


def test_atomic_write(tmp_path: Path) -> None:
    """No .tmp file is left behind and the written file is valid JSON."""
    from kajiba.experiment_store import log_experiment

    store = tmp_path / "experiments"
    dest = log_experiment(_make_record(), store)

    leftover = list(store.glob("*.tmp"))
    assert leftover == [], f"temp files left behind: {leftover}"
    data = json.loads(dest.read_text(encoding="utf-8"))
    assert data["record_kind"] == "model_experiment"


def test_dedup_skip(tmp_path: Path) -> None:
    """Re-logging identical content returns the same path; one file remains."""
    from kajiba.experiment_store import log_experiment

    store = tmp_path / "experiments"
    first = log_experiment(_make_record(), store)
    second = log_experiment(_make_record(), store)

    assert first == second
    assert len(list(store.glob("exp_*.json"))) == 1


def test_public_exports() -> None:
    """The two store functions are importable from the top-level kajiba package."""
    from kajiba import build_experiment_record, log_experiment

    assert callable(build_experiment_record)
    assert callable(log_experiment)


def test_refuses_outbox_dir(tmp_path: Path) -> None:
    """log_experiment refuses any directory not named 'experiments' (D-13)."""
    import pytest

    from kajiba.experiment_store import log_experiment

    with pytest.raises(ValueError):
        log_experiment(_make_record(), tmp_path / "outbox")
