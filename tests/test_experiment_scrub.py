"""RED test scaffold for the experiment PII scrubber (Plan 03).

These tests intentionally fail at collection time with ModuleNotFoundError
until ``kajiba.experiment_scrub`` is implemented in Wave 2. The failing import
is the RED signal — do NOT add ``@pytest.mark.skip``.
"""

import json
from pathlib import Path

import pytest

from kajiba.experiment_scrub import scrub_experiment
from kajiba.schema import ExperimentRecord, ScrubLog, load_record

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    """Load a JSON fixture from the fixtures directory."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _load_pii_record() -> ExperimentRecord:
    """Load the PII experiment fixture as an ExperimentRecord."""
    record = load_record(_load_fixture("experiment_pii.json"))
    assert isinstance(record, ExperimentRecord)
    return record


def test_free_text_redacted() -> None:
    """Email/path PII is removed from local_model_output, task_description, and lessons_learned."""
    record = _load_pii_record()
    scrubbed, _scrub_log = scrub_experiment(record)
    output = scrubbed.outcome.local_model_output
    description = scrubbed.experiment.task_description
    lessons = " ".join(scrubbed.outcome.lessons_learned)
    assert "admin@internal.corp" not in output
    assert "/home/jdoe/projects/kajiba/logs/auth.log" not in output
    assert "jane.doe@example.com" not in description
    assert "jane.doe@example.com" not in lessons


def test_task_category_redacted() -> None:
    """PII placed in the free-text task_category is removed by the allowlist scrub (CR-01)."""
    record = _load_pii_record()
    # Sanity-check the fixture actually carries PII in task_category.
    assert "jane.doe@example.com" in record.experiment.task_category
    scrubbed, _scrub_log = scrub_experiment(record)
    assert "jane.doe@example.com" not in scrubbed.experiment.task_category
    assert "@" not in scrubbed.experiment.task_category


def test_model_and_hardware_preserved() -> None:
    """Model hash/name, hardware, reviewer_model, and experiment_id are byte-identical after scrubbing."""
    record = _load_pii_record()
    before_hash = record.experiment.local_model.model_hash
    before_name = record.experiment.local_model.model_name
    before_hardware = record.hardware.model_dump()
    before_reviewer = record.experiment.reviewer_model.model_dump()
    before_experiment_id = record.experiment.experiment_id
    scrubbed, _scrub_log = scrub_experiment(record)
    assert scrubbed.experiment.local_model.model_hash == before_hash
    assert scrubbed.experiment.local_model.model_name == before_name
    assert scrubbed.hardware.model_dump() == before_hardware
    assert scrubbed.experiment.reviewer_model.model_dump() == before_reviewer
    # experiment_id is load-bearing identity — must stay byte-identical (CR-01).
    assert scrubbed.experiment.experiment_id == before_experiment_id


def test_scrublog_and_outcome_fields() -> None:
    """ScrubLog reports non-zero redactions; non-text outcome fields are unchanged."""
    record = _load_pii_record()
    before_score = record.outcome.eval_score
    before_drift = record.outcome.drift_flag
    before_action = record.outcome.recommended_action
    scrubbed, scrub_log = scrub_experiment(record)
    assert isinstance(scrub_log, ScrubLog)
    assert scrub_log.emails_redacted > 0
    assert scrub_log.file_paths_redacted > 0
    assert scrubbed.outcome.eval_score == before_score
    assert scrubbed.outcome.drift_flag == before_drift
    assert scrubbed.outcome.recommended_action == before_action


def test_lessons_list_shape() -> None:
    """lessons_learned stays a list of the same length (not stringified)."""
    record = _load_pii_record()
    before_len = len(record.outcome.lessons_learned)
    scrubbed, _scrub_log = scrub_experiment(record)
    assert isinstance(scrubbed.outcome.lessons_learned, list)
    assert len(scrubbed.outcome.lessons_learned) == before_len
