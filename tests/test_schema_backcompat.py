"""Back-compat + dispatch tests for the Phase 10 schema refactor.

Locks ESCH-01 (record_kind default), ESCH-02 (RecordBase inheritance),
ESCH-04 (golden record_id / submission_hash stability against the
pre-refactor baseline), and ESCH-05 (validate_record / load_record split).
"""

import json
from pathlib import Path

import pytest

from kajiba.schema import (
    ExperimentRecord,
    KajibaRecord,
    RecordBase,
    load_record,
    validate_record,
)

FIXTURES = Path(__file__).parent / "fixtures"

GOLDEN = json.loads((FIXTURES / "golden_ids.json").read_text(encoding="utf-8"))


def _load_fixture(name: str) -> dict:
    """Load a test fixture JSON file."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# ESCH-04 — golden-ID stability tripwire
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", list(GOLDEN.keys()))
def test_record_id_and_submission_hash_stable(name: str) -> None:
    """Post-refactor hashes are byte-identical to the committed baseline."""
    data = _load_fixture(name)
    rec = validate_record(data)
    assert rec.compute_record_id() == GOLDEN[name]["record_id"]
    assert rec.compute_submission_hash() == GOLDEN[name]["submission_hash"]


@pytest.mark.parametrize("name", list(GOLDEN.keys()))
def test_legacy_dicts_load(name: str) -> None:
    """Every legacy fixture dict loads via validate_record() without error."""
    data = _load_fixture(name)
    assert isinstance(validate_record(data), KajibaRecord)


# ---------------------------------------------------------------------------
# ESCH-01 — record_kind back-compat default
# ---------------------------------------------------------------------------


def test_record_kind_default() -> None:
    """A dict omitting record_kind defaults to 'coding_session' (ESCH-01)."""
    data = _load_fixture("minimal_trajectory.json")
    assert "record_kind" not in data
    assert validate_record(data).record_kind == "coding_session"


# ---------------------------------------------------------------------------
# ESCH-02 — shared RecordBase inheritance
# ---------------------------------------------------------------------------


def test_base_inheritance() -> None:
    """Both record kinds subclass RecordBase and carry inherited base attrs."""
    assert issubclass(KajibaRecord, RecordBase)
    assert issubclass(ExperimentRecord, RecordBase)
    rec = validate_record(_load_fixture("gold_trajectory.json"))
    for attr in (
        "model",
        "hardware",
        "submission",
        "record_id",
        "submission_hash",
        "created_at",
        "schema_version",
        "record_kind",
    ):
        assert hasattr(rec, attr)


# ---------------------------------------------------------------------------
# ESCH-05 — validate_record / load_record dispatch
# ---------------------------------------------------------------------------


def test_load_dispatch() -> None:
    """validate_record yields KajibaRecord; load_record dispatches by kind."""
    minimal_data = _load_fixture("minimal_trajectory.json")
    assert isinstance(validate_record(minimal_data), KajibaRecord)
    assert isinstance(load_record(minimal_data), KajibaRecord)

    exp_data = {
        "record_kind": "model_experiment",
        "experiment": {
            "experiment_id": "exp_001",
            "experiment_type": "model_evaluation",
            "local_model": {"model_name": "Hermes-3-Llama-3.1-8B"},
            "task_category": "coding",
            "task_description": "Write a binary search.",
            "started_at": "2026-06-03T12:00:00Z",
        },
        "outcome": {
            "local_model_output": "def bsearch(a, x): ...",
            "eval_score": 0.8,
        },
    }
    assert isinstance(load_record(exp_data), ExperimentRecord)
