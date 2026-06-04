"""Longitudinal quality-drift detector for ExperimentRecord (EREV-03).

This module is the *drift compute lens* over a set of logged experiments — it
answers "did this model's answer quality drift across repeated runs of the same
task?" (EREV-03 / D-12..D-15). It mirrors ``eval_scorer.py``'s pure-compute shape
(module docstring explaining the role, ``import logging``, a module logger,
``UPPER_SNAKE_CASE`` threshold constant, and a single pure ``compute_*``
entrypoint) and lives as its own single-responsibility module rather than being
bolted onto an existing scorer.

CRITICAL CONTRAST with ``eval_scorer.py``: that scorer is *compute-on-read* and
its verdict is NEVER persisted (D-03). Drift is the opposite — ``compute_drift``
is pure and never writes, but its verdict IS persisted by the caller (the
``drift`` CLI command, 13-05) via ``update_experiment`` into the
``outcome.drift_flag`` field (D-02). The deliberate persist/compute-on-read split
is why the verdict must span EVERY input record: the caller SETs and CLEARs
``drift_flag`` idempotently from the full verdict (D-15).

The algorithm groups runs by ``(local_model.model_name, task_category)`` and,
within each group of >=2 runs, compares every run's ``eval_score`` to the
group-mean baseline (the mean ``eval_score`` across the whole group). A run
drifts when the absolute deviation exceeds the threshold — both directions,
regressions AND improvements (D-14). Groups with fewer than two runs never flag
and never crash on an empty baseline (the ``<2``-run guard precedes any ``mean``
call). This module reads record fields only; it never mutates or writes and
imports nothing from Click, the CLI, or the store.

Baseline note (Assumption A1, Discretion #4): RESEARCH Pattern 3 sketched a
leave-one-out baseline, but the locked 13-01 RED tests assert the whole-group
mean (e.g. in a 0.90/0.90/0.50 group only the 0.50 run flags — leave-one-out
would also flag the 0.90 runs because the outlier contaminates their baseline).
Discretion #4 / A1 explicitly delegate the baseline choice; the whole-group mean
is the contract the tests pin and is more robust to a single outlier.
"""

import logging
from statistics import mean

from kajiba.schema import ExperimentRecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Drift threshold
# ---------------------------------------------------------------------------

# Default absolute eval_score deviation (from the leave-one-out group mean) that
# constitutes drift. Overridable via the ``drift`` command's ``--threshold``
# flag only (D-14, Discretion #3) — this module never reads config.yaml.
DRIFT_THRESHOLD = 0.15


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_drift(
    records: list[ExperimentRecord],
    threshold: float = DRIFT_THRESHOLD,
) -> dict[str, bool]:
    """Compute the drift verdict for a set of experiment records.

    Records are grouped by ``(experiment.local_model.model_name,
    experiment.task_category)``. Within each group of two or more runs, each
    run's ``outcome.eval_score`` is compared to the group-mean baseline (the mean
    ``eval_score`` across the whole group); the run drifts when the absolute
    deviation exceeds ``threshold`` (both directions, D-14). Groups with fewer
    than two runs are never flagged and never trigger a ``mean([])`` call (the
    ``<2``-run guard runs before any baseline is computed). This is a pure
    read-only function: it mutates and writes nothing.

    Args:
        records: The experiment records to evaluate.
        threshold: Absolute deviation from the leave-one-out group mean that
            constitutes drift. Defaults to ``DRIFT_THRESHOLD`` (0.15).

    Returns:
        A dict mapping every input ``record_id`` to its drift verdict
        (``True`` when the run drifts, else ``False``). The verdict spans ALL
        input records so callers can SET and CLEAR ``drift_flag`` idempotently
        (D-15).
    """
    groups: dict[tuple[str, str], list[ExperimentRecord]] = {}
    for r in records:
        key = (r.experiment.local_model.model_name, r.experiment.task_category)
        groups.setdefault(key, []).append(r)

    verdict: dict[str, bool] = {}
    for group in groups.values():
        if len(group) < 2:
            # <2-run guard BEFORE any baseline math (no mean([]) path reachable).
            for r in group:
                verdict[r.record_id] = False
            continue

        baseline = mean(r.outcome.eval_score for r in group)
        for r in group:
            verdict[r.record_id] = abs(r.outcome.eval_score - baseline) > threshold

    return verdict
