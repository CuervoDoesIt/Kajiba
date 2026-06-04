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
within each group of >=2 runs, measures every run's distance to its NEAREST
neighbor in the same group. A run drifts when that nearest-neighbor distance
exceeds the threshold — both directions, regressions AND improvements (D-14):
an isolated run with no close peer is anomalous regardless of which side of the
cluster it falls on. Groups with fewer than two runs never flag and never crash
on an empty baseline (the ``<2``-run guard precedes any neighbor lookup). This
module reads record fields only; it never mutates or writes and imports nothing
from Click, the CLI, or the store.

Baseline note (Assumption A1, Discretion #4): RESEARCH Pattern 3 sketched a
leave-one-out baseline, and 13-03 first shipped a whole-group MEAN, but both are
contaminated by an outlier — in a 0.90/0.90/0.40 group the mean (0.73) sits
between the clusters and flags the two consistent 0.90 runs too, and when the
group later splits into two balanced clusters (e.g. four 0.90s and three ~0.40s)
the mean/median cannot clear a run that has close peers. The locked 13-01 CLI
tests (``test_drift_id_group_writes_whole_group``,
``test_drift_idempotent_persists_and_clears``) pin the contract that a run is
NOT drift when it has a neighbor within threshold; the nearest-neighbor distance
is the robust baseline that satisfies every locked unit AND CLI test. Discretion
 #4 / A1 explicitly delegate the baseline choice.
"""

import logging

from kajiba.schema import ExperimentRecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Drift threshold
# ---------------------------------------------------------------------------

# Default absolute eval_score distance to a run's NEAREST in-group neighbor that
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
    run's distance to its NEAREST in-group neighbor (the smallest absolute
    ``outcome.eval_score`` gap to any other run in the group) is measured; the
    run drifts when that nearest-neighbor distance exceeds ``threshold`` (both
    directions, D-14 — an isolated run is anomalous whether it is higher or
    lower than the cluster). A run that has any peer within ``threshold`` is not
    drift, so a balanced two-cluster group clears every member. Groups with
    fewer than two runs are never flagged and never trigger an empty-baseline
    lookup (the ``<2``-run guard runs before any neighbor comparison). This is a
    pure read-only function: it mutates and writes nothing.

    Args:
        records: The experiment records to evaluate.
        threshold: Maximum absolute ``eval_score`` distance to a run's nearest
            in-group neighbor before the run counts as drift. Defaults to
            ``DRIFT_THRESHOLD`` (0.15).

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
            # <2-run guard BEFORE any neighbor lookup (no empty-baseline path).
            for r in group:
                verdict[r.record_id] = False
            continue

        scores = [r.outcome.eval_score for r in group]
        for idx, r in enumerate(group):
            nearest = min(
                abs(scores[idx] - other)
                for j, other in enumerate(scores)
                if j != idx
            )
            verdict[r.record_id] = nearest > threshold

    return verdict
