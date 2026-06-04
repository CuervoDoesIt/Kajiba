"""Private persistence for model-experiment records (the dual-use store).

This module owns the single write path for the v1.2 experiment-logging
milestone. Both the ``kajiba experiment`` CLI surface (11-02) and external
eval scripts funnel through :func:`log_experiment`, so there is exactly one
place that serializes an :class:`~kajiba.schema.ExperimentRecord` to disk.

Design decisions realized here:

* **D-01** — one flat JSON file per run, ``exp_<record_id>.json``.
* **D-02** — experiment records land directly in the store on log; there is
  no staging -> outbox promotion gate (those belong to the community pipeline).
* **D-05** — persistence is a single-responsibility module, separate from the
  schema and the CLI.
* **D-08** — records are validated on construction (Pydantic), so this module
  trusts the record it is handed and does not re-validate.
* **D-13** — a structural guard refuses to write into any directory not named
  ``experiments``, so an experiment can never leak into the community
  ``staging``/``outbox`` namespaces.

The module is deliberately Click-free: it imports nothing from
:mod:`kajiba.cli` so that programmatic ELOG-02 callers can use it without
pulling in the CLI. The store directory (``EXPERIMENTS_DIR``) is owned by
``cli.py`` per D-03 and passed in as the ``store_dir`` argument.
"""

import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from kajiba.config import get_hermes_home
from kajiba.schema import (
    ExperimentMetadata,
    ExperimentOutcome,
    ExperimentRecord,
    ModelMetadata,
)

logger = logging.getLogger(__name__)

# The canonical experiment store base, derived via get_hermes_home() so it
# follows the active Hermes profile (HERMES_HOME). The store module stays
# Click-free (it never imports ``kajiba.cli``); parity with ``cli.py``'s
# EXPERIMENTS_DIR is maintained because both derive from the same
# get_hermes_home() helper. The literal-parity test
# (test_experiments_dir_matches_cli) guards against drift between the two.
EXPERIMENTS_DIR = get_hermes_home() / "kajiba" / "experiments"

# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------


def log_experiment(
    record: ExperimentRecord,
    store_dir: Path,
    *,
    expected_base: Optional[Path] = None,
) -> Path:
    """Persist a validated ExperimentRecord to the private experiment store.

    Computes the record's content-addressable identity via the frozen schema
    methods, then writes a single ``exp_<record_id>.json`` file into
    ``store_dir`` using an atomic temp-file-plus-replace. If an identical
    record was already logged, the existing file is left untouched and its
    path is returned (skip-with-notice dedup).

    Args:
        record: An already-validated ExperimentRecord (D-08). Its
            ``record_id`` and ``submission_hash`` are computed and set here.
        store_dir: The experiments store directory. Must resolve EQUAL to
            ``expected_base`` (WR-04 guard, D-13).
        expected_base: The canonical experiments base the ``store_dir`` must
            EQUAL. Defaults to ``None`` → the module's :data:`EXPERIMENTS_DIR`
            resolved AT CALL TIME (never bound at def-time), so ``cli.py``
            callers passing the real ``EXPERIMENTS_DIR`` are accepted without
            passing it, while tests pass ``tmp_path/'experiments'`` (or
            monkeypatch ``experiment_store.EXPERIMENTS_DIR``) to stay isolated
            and Click-free.

    Returns:
        Path to the written — or pre-existing identical — JSON file.

    Raises:
        ValueError: If ``store_dir`` does not resolve EQUAL to
            ``expected_base`` (structural privacy guard, WR-04 / D-13).
    """
    # WR-04 / D-13 structural guard: refuse to write anywhere but the canonical
    # experiment store. Resolve the default base at CALL TIME so a monkeypatch
    # of EXPERIMENTS_DIR is honored (never bind it as a def-time default).
    if expected_base is None:
        expected_base = EXPERIMENTS_DIR
    resolved = store_dir.resolve()
    if resolved != expected_base.resolve():
        raise ValueError(
            f"store_dir {resolved} is not the expected experiment store {expected_base}"
        )

    store_dir.mkdir(parents=True, exist_ok=True)

    # Identity comes from the frozen Phase 10 schema methods — never hand-rolled.
    record.compute_record_id()
    record.compute_submission_hash()
    dest = store_dir / f"exp_{record.record_id}.json"

    # Content-addressable dedup: identical content was already logged (D-02).
    if dest.exists():
        logger.info("Experiment already logged (identical content): %s", dest)
        return dest

    data = record.model_dump(mode="json", by_alias=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"

    # Atomic write: temp file in the same dir, then os.replace (atomic and
    # overwrite-safe on both POSIX and Windows).
    fd, tmp_name = tempfile.mkstemp(dir=store_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp_name, dest)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise

    logger.info("Experiment logged to %s", dest)
    return dest


def update_experiment(
    record: ExperimentRecord,
    store_dir: Path,
    *,
    expected_base: Optional[Path] = None,
) -> Path:
    """Overwrite an existing experiment in place — the corrective write path.

    This is the single in-place overwrite write path that all three Phase 13
    commands funnel through (D-03). It closes CR-01 (the ``log_experiment``
    dedup-skip data-loss bug) by INTENTIONALLY overwriting ``exp_<id>.json``
    rather than early-returning on ``dest.exists()``: logging then updating the
    same identity with a corrected ``eval_score`` leaves exactly one file whose
    on-disk score is the corrected value.

    In-place overwrite is safe because the record's content-addressable identity
    excludes the outcome/metadata fields a correction mutates: ``compute_record_id``
    / ``compute_submission_hash`` (schema.py:445-467) hash only the experiment
    identity payload, so ``record_id`` — and therefore the on-disk filename —
    stays byte-stable across any outcome/metadata mutation (D-01).

    The record is re-validated before writing (the models lack
    ``validate_assignment``, so re-validation is the project rule, Pitfall 3):
    an out-of-range value forced into the dict is rejected by Pydantic, not
    persisted.

    Args:
        record: The ExperimentRecord to overwrite in place. Its ``record_id``
            and ``submission_hash`` are (re)computed here.
        store_dir: The experiments store directory. Must resolve EQUAL to
            ``expected_base`` (WR-04 guard, D-13).
        expected_base: The canonical experiments base the ``store_dir`` must
            EQUAL. Defaults to ``None`` → the module's :data:`EXPERIMENTS_DIR`
            resolved AT CALL TIME (never bound at def-time), so ``cli.py``
            callers passing the real ``EXPERIMENTS_DIR`` are accepted without
            passing it, while tests pass ``tmp_path/'experiments'`` (or
            monkeypatch ``experiment_store.EXPERIMENTS_DIR``) to stay isolated
            and Click-free.

    Returns:
        Path to the overwritten JSON file.

    Raises:
        ValueError: If ``store_dir`` does not resolve EQUAL to
            ``expected_base`` (structural privacy guard, WR-04 / D-13).
        pydantic.ValidationError: If the re-validated record fails validation.
    """
    # WR-04 / D-13 structural guard: refuse to write anywhere but the canonical
    # experiment store. Resolve the default base at CALL TIME so a monkeypatch
    # of EXPERIMENTS_DIR is honored (never bind it as a def-time default).
    if expected_base is None:
        expected_base = EXPERIMENTS_DIR
    resolved = store_dir.resolve()
    if resolved != expected_base.resolve():
        raise ValueError(
            f"store_dir {resolved} is not the expected experiment store {expected_base}"
        )

    store_dir.mkdir(parents=True, exist_ok=True)

    # Re-validate after mutation: the models lack validate_assignment, so a
    # mutated record must be re-validated before it crosses into storage
    # (Pitfall 3). An out-of-range value is rejected here, not persisted.
    record = ExperimentRecord.model_validate(
        record.model_dump(mode="json", by_alias=True)
    )

    # Identity comes from the frozen Phase 10 schema methods — never hand-rolled.
    # Identity excludes outcome/metadata, so the filename is stable across
    # corrections (CR-01 / D-01).
    record.compute_record_id()
    record.compute_submission_hash()
    dest = store_dir / f"exp_{record.record_id}.json"

    # NO dest.exists() early-return: update_experiment ALWAYS overwrites (CR-01).
    data = record.model_dump(mode="json", by_alias=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"

    # Atomic write: temp file in the same dir, then os.replace (atomic and
    # overwrite-safe on both POSIX and Windows).
    fd, tmp_name = tempfile.mkstemp(dir=store_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp_name, dest)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise

    logger.info("Experiment updated in place: %s", dest)
    return dest


# ---------------------------------------------------------------------------
# Convenience constructor
# ---------------------------------------------------------------------------


def build_experiment_record(
    *,
    experiment_id: str,
    experiment_type: str,
    task_category: str,
    task_description: str,
    local_model_name: str,
    local_model_output: str,
    eval_score: float,
    started_at: Optional[datetime] = None,
    **extra,
) -> ExperimentRecord:
    """Assemble and validate an ExperimentRecord from flat keyword fields.

    A thin convenience over the nested schema models (D-06): callers pass
    scalar fields and this assembles the ``ExperimentMetadata`` /
    ``ExperimentOutcome`` / ``ModelMetadata`` tree. Pydantic validates on
    construction (D-08), so an out-of-vocab ``experiment_type`` or an
    out-of-range ``eval_score`` raises immediately.

    Args:
        experiment_id: Caller-chosen identifier for the run.
        experiment_type: One of the controlled EXPERIMENT_TYPES values.
        task_category: Free-form task category (e.g. "coding").
        task_description: Human-readable description of the task.
        local_model_name: Name of the local model under evaluation.
        local_model_output: The local model's produced output.
        eval_score: Quality score in the inclusive range 0.0-1.0.
        started_at: When the run started; defaults to ``datetime.now(UTC)``.
        **extra: Additional top-level ExperimentRecord fields (e.g. model,
            hardware, trajectory) passed through to the constructor.

    Returns:
        A validated ExperimentRecord with ``record_kind == "model_experiment"``.

    Raises:
        pydantic.ValidationError: If any assembled field fails validation.
    """
    started = started_at or datetime.now(UTC)
    return ExperimentRecord(
        experiment=ExperimentMetadata(
            experiment_id=experiment_id,
            experiment_type=experiment_type,
            local_model=ModelMetadata(model_name=local_model_name),
            task_category=task_category,
            task_description=task_description,
            started_at=started,
        ),
        outcome=ExperimentOutcome(
            local_model_output=local_model_output,
            eval_score=eval_score,
        ),
        **extra,
    )
