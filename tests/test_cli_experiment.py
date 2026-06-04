"""CLI behavior tests for the `kajiba experiment` group (ELOG-01).

Covers the `log` subcommand (file-first `--from`, scalar override flags, and
the interactive Rich fallback) plus the `list` read-back subcommand. The store
is isolated per-test by monkeypatching ``kajiba.cli.EXPERIMENTS_DIR`` (and
``KAJIBA_BASE`` for ``_ensure_dirs``) to a ``tmp_path`` subdirectory so tests
never touch the real ``~/.hermes`` (RESEARCH Pitfall 2).
"""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from kajiba.cli import cli

FIXTURE = Path(__file__).parent / "fixtures" / "experiment_run.example.json"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _isolate_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the CLI's experiment store at a tmp dir; return that dir."""
    store = tmp_path / "experiments"
    monkeypatch.setattr("kajiba.cli.EXPERIMENTS_DIR", store)
    monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)
    return store


def test_log_from_file(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`experiment log --from <fixture>` writes one exp_*.json and prints its path."""
    store = _isolate_store(tmp_path, monkeypatch)

    result = runner.invoke(cli, ["experiment", "log", "--from", str(FIXTURE)])

    assert result.exit_code == 0, result.output
    assert "exp_" in result.output
    assert ".json" in result.output

    written = list(store.glob("exp_*.json"))
    assert len(written) == 1
    # Written into the experiment store, not staging/outbox.
    assert written[0].parent == store


def test_log_scalar_overrides(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--score` overrides outcome.eval_score on top of --from before validation."""
    store = _isolate_store(tmp_path, monkeypatch)

    result = runner.invoke(
        cli, ["experiment", "log", "--from", str(FIXTURE), "--score", "0.5"],
    )

    assert result.exit_code == 0, result.output
    written = list(store.glob("exp_*.json"))
    assert len(written) == 1
    data = json.loads(written[0].read_text(encoding="utf-8"))
    assert data["outcome"]["eval_score"] == 0.5


def test_log_interactive(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`experiment log` with no flags persists via the scripted interactive fallback."""
    store = _isolate_store(tmp_path, monkeypatch)

    # Prompt order: experiment_id, task_category, task_description,
    # eval_score, experiment_type, local_model.model_name, local_model_output.
    scripted = "\n".join(
        [
            "exp_interactive_1",
            "coding",
            "Write a quicksort.",
            "0.7",
            "model_evaluation",
            "Hermes-3-Llama-3.1-8B",
            "def quicksort(a): ...",
        ]
    ) + "\n"

    result = runner.invoke(cli, ["experiment", "log"], input=scripted)

    assert result.exit_code == 0, result.output
    written = list(store.glob("exp_*.json"))
    assert len(written) == 1
    data = json.loads(written[0].read_text(encoding="utf-8"))
    assert data["record_kind"] == "model_experiment"
    assert data["experiment"]["experiment_id"] == "exp_interactive_1"


def test_list(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After logging a record, `experiment list` shows it (read-back)."""
    store = _isolate_store(tmp_path, monkeypatch)

    log_result = runner.invoke(cli, ["experiment", "log", "--from", str(FIXTURE)])
    assert log_result.exit_code == 0, log_result.output

    written = list(store.glob("exp_*.json"))
    assert len(written) == 1
    record_id = json.loads(written[0].read_text(encoding="utf-8"))["record_id"]

    list_result = runner.invoke(cli, ["experiment", "list"])
    assert list_result.exit_code == 0, list_result.output
    # The record_id (or a recognizable prefix) appears in the read-back table.
    assert record_id[:20] in list_result.output or "exp_" in list_result.output
