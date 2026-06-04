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

from kajiba.schema import (
    ExperimentMetadata,
    ExperimentOutcome,
    ExperimentRecord,
    ModelMetadata,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------


def log_experiment(record: ExperimentRecord, store_dir: Path) -> Path:
    """Persist a validated ExperimentRecord to the private experiment store.

    Computes the record's content-addressable identity via the frozen schema
    methods, then writes a single ``exp_<record_id>.json`` file into
    ``store_dir`` using an atomic temp-file-plus-replace. If an identical
    record was already logged, the existing file is left untouched and its
    path is returned (skip-with-notice dedup).

    Args:
        record: An already-validated ExperimentRecord (D-08). Its
            ``record_id`` and ``submission_hash`` are computed and set here.
        store_dir: The experiments store directory (``EXPERIMENTS_DIR``).
            Must resolve to a directory named ``experiments`` (D-13).

    Returns:
        Path to the written — or pre-existing identical — JSON file.

    Raises:
        ValueError: If ``store_dir`` does not resolve to an ``experiments``
            directory (structural privacy guard, D-13).
    """
    # D-13 structural guard: refuse to write anywhere but the experiment store.
    resolved = store_dir.resolve()
    if resolved.name != "experiments":
        raise ValueError(
            f"Experiment store must be the 'experiments' directory, got {resolved}"
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
