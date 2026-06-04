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
    # Pass expected_base=store so the EQUAL guard (13-02) accepts this
    # tmp_path store dir instead of comparing against the real ~/.hermes
    # default base.
    dest = log_experiment(rec, store, expected_base=store)

    assert dest.exists()
    assert dest.parent == store
    assert rec.record_id is not None
    assert rec.record_id.startswith("kajiba_exp_")
    assert dest.name == f"exp_{rec.record_id}.json"


def test_atomic_write(tmp_path: Path) -> None:
    """No .tmp file is left behind and the written file is valid JSON."""
    from kajiba.experiment_store import log_experiment

    store = tmp_path / "experiments"
    dest = log_experiment(_make_record(), store, expected_base=store)

    leftover = list(store.glob("*.tmp"))
    assert leftover == [], f"temp files left behind: {leftover}"
    data = json.loads(dest.read_text(encoding="utf-8"))
    assert data["record_kind"] == "model_experiment"


def test_dedup_skip(tmp_path: Path) -> None:
    """Re-logging identical content returns the same path; one file remains."""
    from kajiba.experiment_store import log_experiment

    store = tmp_path / "experiments"
    first = log_experiment(_make_record(), store, expected_base=store)
    second = log_experiment(_make_record(), store, expected_base=store)

    assert first == second
    assert len(list(store.glob("exp_*.json"))) == 1


def test_public_exports() -> None:
    """The two store functions are importable from the top-level kajiba package."""
    from kajiba import build_experiment_record, log_experiment

    assert callable(build_experiment_record)
    assert callable(log_experiment)


def test_refuses_outbox_dir(tmp_path: Path) -> None:
    """log_experiment refuses a store_dir != expected base (WR-04 / EQUAL guard).

    With NO ``expected_base`` the guard falls back to the module default base
    (the real ``experiments`` dir), which is not ``tmp_path/"outbox"`` →
    rejected. Passing ``expected_base=tmp_path/"experiments"`` asserts the
    same reject intent explicitly under the EQUAL predicate.
    """
    import pytest

    from kajiba.experiment_store import log_experiment

    with pytest.raises(ValueError):
        log_experiment(_make_record(), tmp_path / "outbox")

    with pytest.raises(ValueError):
        log_experiment(
            _make_record(),
            tmp_path / "outbox",
            expected_base=tmp_path / "experiments",
        )


# ---------------------------------------------------------------------------
# Phase 13 RED scaffolds — update_experiment (CR-01 / WR-04) + EXPERIMENTS_DIR
# parity. All five fail until 13-02 lands `update_experiment` and the
# `experiment_store.EXPERIMENTS_DIR` constant. The store-guard tests use the
# EQUAL predicate: accept store_dir == expected_base; reject store_dir !=
# expected_base. Jointly satisfiable by 13-02's single predicate.
# ---------------------------------------------------------------------------


def test_update_overwrites_in_place(tmp_path: Path) -> None:
    """update_experiment overwrites the same identity in place (CR-01, T-13-CR01).

    The dedup-skip bug in log_experiment would leave the first (0.50) score on
    disk; update_experiment must replace it with the corrected 0.90, leaving
    exactly one file.
    """
    from kajiba.experiment_store import update_experiment

    store = tmp_path / "experiments"

    rec_lo = _make_record(
        outcome=ExperimentOutcome(
            local_model_output="def bsearch(a, x): ...",
            eval_score=0.50,
        ),
    )
    update_experiment(rec_lo, store, expected_base=store)

    # Same identity (experiment_id / task_description / local_model_name /
    # local_model_output / started_at unchanged), corrected score.
    rec_hi = _make_record(
        outcome=ExperimentOutcome(
            local_model_output="def bsearch(a, x): ...",
            eval_score=0.90,
        ),
    )
    dest = update_experiment(rec_hi, store, expected_base=store)

    files = list(store.glob("exp_*.json"))
    assert len(files) == 1
    data = json.loads(dest.read_text(encoding="utf-8"))
    # Bug-closure: dedup-skip would have left 0.50 here.
    assert data["outcome"]["eval_score"] == 0.90


def test_identity_stable_across_mutation(tmp_path: Path) -> None:
    """Mutating non-identity fields keeps record_id and filename byte-stable (CR-01)."""
    from kajiba.experiment_store import update_experiment

    store = tmp_path / "experiments"

    rec = _make_record()
    first = update_experiment(rec, store, expected_base=store)
    first_id = rec.record_id
    first_name = first.name

    # Mutate only NON-identity fields (identity excludes outcome metadata).
    rec.outcome.reviewer_critique = "Now reviewed in depth."
    rec.outcome.lessons_learned = ["added more lessons", "and another"]
    rec.outcome.drift_flag = True

    second = update_experiment(rec, store, expected_base=store)

    assert rec.record_id == first_id
    assert second.name == first_name


def test_update_guard_rejects_dir_outside_base(tmp_path: Path) -> None:
    """update_experiment rejects store_dir != expected_base (WR-04, T-13-ERR).

    EQUAL predicate: bad_dir.resolve() != base.resolve() → ValueError. The
    accept tests pass store_dir == expected_base and are accepted by the SAME
    predicate, so all cases are jointly satisfiable.
    """
    import pytest

    from kajiba.experiment_store import update_experiment

    base = tmp_path / "experiments"
    bad_dir = tmp_path / "elsewhere" / "experiments"

    with pytest.raises(ValueError):
        update_experiment(_make_record(), bad_dir, expected_base=base)


def test_update_default_base_guard(
    tmp_path: Path, monkeypatch,
) -> None:
    """Default expected_base reads experiment_store.EXPERIMENTS_DIR at call time.

    Proves the PRODUCTION default path (update_experiment(rec, EXPERIMENTS_DIR)
    with no expected_base) is accepted exactly as production uses it, and pins
    the default-binding-at-call-time rule so the parent-vs-equal regression
    cannot recur silently.
    """
    import pytest

    import kajiba.experiment_store as store_mod

    base = tmp_path / "experiments"
    monkeypatch.setattr(store_mod, "EXPERIMENTS_DIR", base)

    # ACCEPT: default base == store_dir (monkeypatched), no expected_base.
    store_mod.update_experiment(_make_record(), base)
    assert len(list(base.glob("exp_*.json"))) == 1

    # REJECT: default base (tmp_path/"experiments") != tmp_path/"elsewhere".
    with pytest.raises(ValueError):
        store_mod.update_experiment(_make_record(), tmp_path / "elsewhere")


def test_experiments_dir_matches_cli() -> None:
    """cli.EXPERIMENTS_DIR and experiment_store.EXPERIMENTS_DIR stay equal (T-13-DRIFT-CFG).

    After 13-02 lands the constant in experiment_store.py, the two literals must
    match (both resolved) so the store guard's default base equals the directory
    the CLI actually writes to. Literal drift fails fast in CI rather than only
    fail-closing at production runtime. RED now on the missing
    experiment_store.EXPERIMENTS_DIR.
    """
    import kajiba.cli
    import kajiba.experiment_store

    assert (
        kajiba.cli.EXPERIMENTS_DIR.resolve()
        == kajiba.experiment_store.EXPERIMENTS_DIR.resolve()
    )
