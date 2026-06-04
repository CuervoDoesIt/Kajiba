"""ELOG-03 exclusion tests: experiments never reach any community path.

Two guarantees are proven here without any real network access:

* ``test_publish_skips_experiment`` — the active backstop. A misplaced
  ``model_experiment`` record dropped into the outbox is skipped by the
  ``publish`` Step 4 consent loop (raw-dict ``record_kind`` discriminator,
  RESEARCH Pattern 4 / D-13), printing a skip notice and never appearing in
  output. ``kajiba.cli.GitHubOps`` is monkeypatched so the auth check passes
  but no PR is ever opened (RESEARCH line 535 — no real network).
* ``test_experiment_absent_from_community_paths`` — the D-14 regression. A real
  experiment written through ``kajiba.experiment_store.log_experiment`` is
  proven to be structurally absent from the outbox glob, left untouched on
  disk, and never present in ``publish`` output.

All directory constants (``OUTBOX_DIR``, ``EXPERIMENTS_DIR``, ``KAJIBA_BASE``)
are monkeypatched to ``tmp_path`` subdirs so the real ``~/.hermes`` is never
touched (RESEARCH Pitfall 2).
"""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from kajiba.cli import cli
from kajiba.experiment_store import build_experiment_record, log_experiment


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _isolate_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Point outbox + experiment store at tmp dirs; return (outbox, experiments)."""
    outbox = tmp_path / "outbox"
    experiments = tmp_path / "experiments"
    outbox.mkdir(parents=True, exist_ok=True)
    experiments.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("kajiba.cli.OUTBOX_DIR", outbox)
    monkeypatch.setattr("kajiba.cli.EXPERIMENTS_DIR", experiments)
    monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)
    # 13-02 tightened the store guard to an EQUAL expected_base check whose
    # default base is experiment_store.EXPERIMENTS_DIR read at call time. This
    # test calls log_experiment without expected_base (production semantics), so
    # the store-module constant must also point at the tmp store to stay isolated.
    monkeypatch.setattr("kajiba.experiment_store.EXPERIMENTS_DIR", experiments)
    return outbox, experiments


class _StubGhResult:
    """Minimal stand-in for publisher.GhResult used by the publish flow."""

    def __init__(self, success: bool, stdout: str = "", returncode: int = 0) -> None:
        self.success = success
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


class _StubGitHubOps:
    """Network-free GitHubOps stub: auth passes so Step 4 (the guard) is reached.

    No PR is ever opened — the publish run exits before any push because the
    only outbox record (an experiment) is skipped, leaving no valid records.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def check_auth(self) -> _StubGhResult:
        return _StubGhResult(success=True, returncode=0)

    def get_username(self) -> _StubGhResult:  # pragma: no cover - never reached
        return _StubGhResult(success=True, stdout="stub-user")

    def fork_repo(self) -> _StubGhResult:  # pragma: no cover - never reached
        return _StubGhResult(success=True)


def _write_experiment_to_outbox(outbox: Path) -> str:
    """Deliberately misplace a model_experiment .jsonl line into the outbox.

    Returns the experiment's record_id so the test can assert its absence.
    """
    record = build_experiment_record(
        experiment_id="exp_misplaced_1",
        experiment_type="model_evaluation",
        task_category="coding",
        task_description="Misplaced experiment that must never publish.",
        eval_score=0.9,
        local_model_name="Hermes-3-Llama-3.1-8B",
        local_model_output="def f(): ...",
    )
    record.compute_record_id()
    record.compute_submission_hash()
    data = record.model_dump(mode="json", by_alias=True)
    record_id = data["record_id"]
    (outbox / "record_misplaced.jsonl").write_text(
        json.dumps(data, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return record_id


def test_publish_skips_experiment(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A misplaced model_experiment in the outbox is skipped by publish, not published."""
    outbox, _experiments = _isolate_dirs(tmp_path, monkeypatch)
    monkeypatch.setattr("kajiba.cli.GitHubOps", _StubGitHubOps)

    record_id = _write_experiment_to_outbox(outbox)

    result = runner.invoke(cli, ["publish", "--dry-run"])

    # The experiment record_id never appears in publish output.
    assert record_id not in result.output
    # The active skip notice is printed (defense in depth on top of the dir split).
    assert "Skipping experiment record" in result.output
    # No PR opened: the run ends because no valid records remain after the skip.
    assert "No valid records" in result.output


def test_experiment_absent_from_community_paths(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-14: an experiment logged to the private store never crosses into a community path."""
    outbox, experiments = _isolate_dirs(tmp_path, monkeypatch)
    monkeypatch.setattr("kajiba.cli.GitHubOps", _StubGitHubOps)

    record = build_experiment_record(
        experiment_id="exp_private_1",
        experiment_type="model_evaluation",
        task_category="coding",
        task_description="A private experiment.",
        eval_score=0.75,
        local_model_name="Hermes-3-Llama-3.1-8B",
        local_model_output="def g(): ...",
    )
    written_path = log_experiment(record, experiments)
    record_id = json.loads(written_path.read_text(encoding="utf-8"))["record_id"]
    contents_before = written_path.read_bytes()

    # (a) the experiment file is not part of the outbox glob.
    outbox_files = list(outbox.glob("*.jsonl"))
    assert written_path not in outbox_files
    assert all(f.parent == outbox for f in outbox_files)
    assert written_path.parent == experiments

    # (c) the experiment record_id never appears in publish output.
    result = runner.invoke(cli, ["publish", "--dry-run"])
    assert record_id not in result.output

    # (b) the experiment file on disk is untouched by the publish run.
    assert written_path.exists()
    assert written_path.read_bytes() == contents_before
