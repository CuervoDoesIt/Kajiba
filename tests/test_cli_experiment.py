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
COMPLETE_FIXTURE = Path(__file__).parent / "fixtures" / "experiment_complete.json"
PII_FIXTURE = Path(__file__).parent / "fixtures" / "experiment_pii.json"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _isolate_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the CLI's experiment store at a tmp dir; return that dir.

    Also isolates ``kajiba.experiment_store.EXPERIMENTS_DIR`` (the store guard's
    default base, read at call time): the CLI calls
    ``log_experiment``/``update_experiment`` with NO ``expected_base``, so the
    EQUAL guard falls back to the store module's constant. Without this line
    every CLI write would compare the isolated ``tmp_path/"experiments"``
    store_dir against the real ``~/.hermes/.../experiments`` default base and
    raise ValueError.
    """
    store = tmp_path / "experiments"
    monkeypatch.setattr("kajiba.cli.EXPERIMENTS_DIR", store)
    monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)
    monkeypatch.setattr("kajiba.experiment_store.EXPERIMENTS_DIR", store, raising=False)
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


def _seed(
    runner: CliRunner, store: Path, fixture: Path,
) -> str:
    """Log a fixture into the isolated store; return its bare record_id."""
    log_result = runner.invoke(cli, ["experiment", "log", "--from", str(fixture)])
    assert log_result.exit_code == 0, log_result.output
    written = list(store.glob("exp_*.json"))
    assert len(written) == 1
    return json.loads(written[0].read_text(encoding="utf-8"))["record_id"]


def test_experiment_score(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`experiment score <id>` prints a confidence band + the Confidence surface."""
    store = _isolate_store(tmp_path, monkeypatch)
    record_id = _seed(runner, store, COMPLETE_FIXTURE)

    result = runner.invoke(cli, ["experiment", "score", record_id])

    assert result.exit_code == 0, result.output
    assert any(band in result.output for band in ("complete", "partial", "thin"))
    assert "Confidence" in result.output


def test_experiment_scrub(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`experiment scrub <id>` redacts PII to stdout and leaves the raw store unchanged (D-08)."""
    store = _isolate_store(tmp_path, monkeypatch)
    record_id = _seed(runner, store, PII_FIXTURE)

    raw_path = store / f"exp_{record_id}.json"
    before = raw_path.read_bytes()

    result = runner.invoke(cli, ["experiment", "scrub", record_id])

    assert result.exit_code == 0, result.output
    # Free-text PII from the fixture must not appear in the previewed output.
    # The email surfaces in BOTH task_description and lessons_learned, so its
    # absence proves the allowlist scrub fired across the experiment surfaces.
    assert "jane.doe@example.com" not in result.output
    # The scrubbed placeholder confirms the share-boundary transform ran.
    assert "[REDACTED_EMAIL]" in result.output

    # D-08 store-raw invariant: the on-disk raw file is byte-identical.
    after = raw_path.read_bytes()
    assert before == after


def test_experiment_scrub_out(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`experiment scrub <id> --out FILE` writes a scrubbed copy without touching the raw store."""
    store = _isolate_store(tmp_path, monkeypatch)
    record_id = _seed(runner, store, PII_FIXTURE)

    raw_path = store / f"exp_{record_id}.json"
    before = raw_path.read_bytes()
    out_file = tmp_path / "scrubbed.json"

    result = runner.invoke(
        cli, ["experiment", "scrub", record_id, "--out", str(out_file)],
    )

    assert result.exit_code == 0, result.output
    assert out_file.exists()
    scrubbed_text = out_file.read_text(encoding="utf-8")
    assert "jane.doe@example.com" not in scrubbed_text
    # Raw store untouched (D-08).
    assert raw_path.read_bytes() == before


def test_experiment_scrub_out_into_store_rejected(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`experiment scrub <id> --out <inside store>` is refused, leaving the raw file unchanged (WR-02)."""
    store = _isolate_store(tmp_path, monkeypatch)
    record_id = _seed(runner, store, PII_FIXTURE)

    raw_path = store / f"exp_{record_id}.json"
    before = raw_path.read_bytes()
    # An --out that points back into the experiment store would clobber the raw
    # copy and break the store-raw invariant (D-08).
    out_file = store / f"exp_{record_id}.json"

    result = runner.invoke(
        cli, ["experiment", "scrub", record_id, "--out", str(out_file)],
    )

    # The command must refuse (non-zero exit, no traceback) and leave the raw
    # store byte-identical.
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert raw_path.read_bytes() == before


def test_experiment_list_confidence(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`experiment list` renders a distinct Confidence column header (Pitfall 4)."""
    store = _isolate_store(tmp_path, monkeypatch)
    _seed(runner, store, COMPLETE_FIXTURE)

    result = runner.invoke(cli, ["experiment", "list"])

    assert result.exit_code == 0, result.output
    assert "Confidence" in result.output


def test_experiment_score_missing(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`experiment score <bad id>` exits non-zero with a clean message (no traceback)."""
    _isolate_store(tmp_path, monkeypatch)

    result = runner.invoke(cli, ["experiment", "score", "does_not_exist"])

    assert result.exit_code != 0
    assert "Traceback" not in result.output


# ===========================================================================
# Phase 13 RED scaffolds — review / lessons / drift + WR error paths +
# _parse_lesson. All fail until 13-04/13-05 add the subcommands and helpers.
# Every test routes through _isolate_store so no real ~/.hermes is touched.
# ===========================================================================


def _read_record(store: Path, record_id: str) -> dict:
    """Re-read a written exp_*.json from the isolated store as a dict."""
    return json.loads((store / f"exp_{record_id}.json").read_text(encoding="utf-8"))


def _drift_record(
    store: Path,
    *,
    experiment_id: str,
    eval_score: float,
    model_name: str = "Hermes-3-Llama-3.1-8B",
    task_category: str = "coding",
    started: str = "2026-06-03T12:00:00Z",
) -> str:
    """Write one experiment directly into the isolated store; return its record_id.

    Used to seed multi-run drift groups without depending on the (RED) review/
    lessons subcommands. Routes through log_experiment, so it exercises the
    same EQUAL guard the CLI uses (default base isolated by _isolate_store).
    """
    from kajiba.experiment_store import build_experiment_record, log_experiment

    rec = build_experiment_record(
        experiment_id=experiment_id,
        experiment_type="model_evaluation",
        task_category=task_category,
        task_description="Write a binary search function.",
        local_model_name=model_name,
        local_model_output=f"output-{experiment_id}",
        eval_score=eval_score,
        started_at=__import__("datetime").datetime.fromisoformat(
            started.replace("Z", "+00:00")
        ),
    )
    dest = log_experiment(rec, store)
    return json.loads(dest.read_text(encoding="utf-8"))["record_id"]


# --- REVIEW (EREV-01) ------------------------------------------------------


def test_review_sets_critique(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`experiment review <id> --critique` persists the critique to disk."""
    store = _isolate_store(tmp_path, monkeypatch)
    record_id = _seed(runner, store, FIXTURE)

    result = runner.invoke(
        cli, ["experiment", "review", record_id, "--critique", "Good but slow"],
    )

    assert result.exit_code == 0, result.output
    data = _read_record(store, record_id)
    assert data["outcome"]["reviewer_critique"] == "Good but slow"


def test_review_replaces_critique(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reviewing twice replaces the critique (single string, no append, D-07)."""
    store = _isolate_store(tmp_path, monkeypatch)
    record_id = _seed(runner, store, FIXTURE)

    runner.invoke(cli, ["experiment", "review", record_id, "--critique", "First take"])
    result = runner.invoke(
        cli, ["experiment", "review", record_id, "--critique", "Second take"],
    )

    assert result.exit_code == 0, result.output
    data = _read_record(store, record_id)
    assert data["outcome"]["reviewer_critique"] == "Second take"
    assert "First take" not in data["outcome"]["reviewer_critique"]


def test_review_reviewer_model_set_and_omitted(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--reviewer-model` sets reviewer identity; omitting it leaves it null (D-05)."""
    store = _isolate_store(tmp_path, monkeypatch)

    # With the flag.
    id_a = _seed(runner, store, FIXTURE)
    res_a = runner.invoke(
        cli,
        [
            "experiment", "review", id_a,
            "--critique", "ok",
            "--reviewer-model", "gpt-4o",
        ],
    )
    assert res_a.exit_code == 0, res_a.output
    data_a = _read_record(store, id_a)
    assert data_a["experiment"]["reviewer_model"]["model_name"] == "gpt-4o"

    # Without the flag, on a record whose reviewer_model starts null.
    id_b = _drift_record(store, experiment_id="exp_no_reviewer", eval_score=0.6)
    res_b = runner.invoke(
        cli, ["experiment", "review", id_b, "--critique", "ok"],
    )
    assert res_b.exit_code == 0, res_b.output
    data_b = _read_record(store, id_b)
    assert data_b["experiment"]["reviewer_model"] is None


def test_review_action_validated(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--action` accepts a valid Choice and rejects out-of-vocab without traceback (D-06)."""
    store = _isolate_store(tmp_path, monkeypatch)
    record_id = _seed(runner, store, FIXTURE)

    good = runner.invoke(
        cli,
        ["experiment", "review", record_id, "--critique", "ok", "--action", "use_as_is"],
    )
    assert good.exit_code == 0, good.output
    data = _read_record(store, record_id)
    assert data["outcome"]["recommended_action"] == "use_as_is"

    bad = runner.invoke(
        cli,
        ["experiment", "review", record_id, "--critique", "ok", "--action", "bogus"],
    )
    assert bad.exit_code != 0
    assert "Traceback" not in bad.output


def test_review_from_txt(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`review --from <.txt>` reads the raw file content as the critique (D-04)."""
    store = _isolate_store(tmp_path, monkeypatch)
    record_id = _seed(runner, store, FIXTURE)

    crit_file = tmp_path / "critique.txt"
    crit_file.write_text("Solid solution, minor style nits.", encoding="utf-8")

    result = runner.invoke(
        cli, ["experiment", "review", record_id, "--from", str(crit_file)],
    )

    assert result.exit_code == 0, result.output
    data = _read_record(store, record_id)
    assert "Solid solution" in data["outcome"]["reviewer_critique"]


def test_review_from_json(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`review --from <.json>` reads the reviewer_critique field of a fragment (D-04)."""
    store = _isolate_store(tmp_path, monkeypatch)
    record_id = _seed(runner, store, FIXTURE)

    crit_file = tmp_path / "critique.json"
    crit_file.write_text(
        json.dumps({"reviewer_critique": "Structured review from JSON."}),
        encoding="utf-8",
    )

    result = runner.invoke(
        cli, ["experiment", "review", record_id, "--from", str(crit_file)],
    )

    assert result.exit_code == 0, result.output
    data = _read_record(store, record_id)
    assert data["outcome"]["reviewer_critique"] == "Structured review from JSON."


def test_review_interactive_paste(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`review <id>` with no critique flags reads a multi-line paste (D-04)."""
    store = _isolate_store(tmp_path, monkeypatch)
    record_id = _seed(runner, store, FIXTURE)

    result = runner.invoke(
        cli, ["experiment", "review", record_id], input="line one\nline two\n",
    )

    assert result.exit_code == 0, result.output
    data = _read_record(store, record_id)
    critique = data["outcome"]["reviewer_critique"]
    assert "line one" in critique
    assert "line two" in critique


# --- LESSONS (EREV-02) -----------------------------------------------------


def test_lessons_add_with_category(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`lessons <id> --add --category` stores a 'category: lesson' entry."""
    store = _isolate_store(tmp_path, monkeypatch)
    record_id = _seed(runner, store, FIXTURE)

    result = runner.invoke(
        cli,
        [
            "experiment", "lessons", record_id,
            "--add", "needs explicit output format",
            "--category", "prompting",
        ],
    )

    assert result.exit_code == 0, result.output
    data = _read_record(store, record_id)
    assert "prompting: needs explicit output format" in data["outcome"]["lessons_learned"]


def test_lessons_read_mode(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`lessons <id>` with no --add prints the record's lessons."""
    store = _isolate_store(tmp_path, monkeypatch)
    record_id = _seed(runner, store, FIXTURE)
    runner.invoke(
        cli,
        ["experiment", "lessons", record_id, "--add", "be explicit", "--category", "prompting"],
    )

    result = runner.invoke(cli, ["experiment", "lessons", record_id])

    assert result.exit_code == 0, result.output
    assert "be explicit" in result.output


def test_lessons_filter_by_category(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`lessons <id> --category X` prints only lessons in category X."""
    store = _isolate_store(tmp_path, monkeypatch)
    record_id = _seed(runner, store, FIXTURE)
    runner.invoke(
        cli,
        ["experiment", "lessons", record_id, "--add", "set format", "--category", "prompting"],
    )
    runner.invoke(
        cli,
        ["experiment", "lessons", record_id, "--add", "retry on 5xx", "--category", "http"],
    )

    result = runner.invoke(
        cli, ["experiment", "lessons", record_id, "--category", "prompting"],
    )

    assert result.exit_code == 0, result.output
    assert "set format" in result.output
    assert "retry on 5xx" not in result.output


def test_lessons_crossrecord(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`lessons --category X` with no id aggregates lessons across records (D-11)."""
    store = _isolate_store(tmp_path, monkeypatch)
    id_a = _drift_record(store, experiment_id="exp_cross_a", eval_score=0.6)
    id_b = _drift_record(store, experiment_id="exp_cross_b", eval_score=0.7)

    runner.invoke(
        cli, ["experiment", "lessons", id_a, "--add", "lesson A", "--category", "prompting"],
    )
    runner.invoke(
        cli, ["experiment", "lessons", id_b, "--add", "lesson B", "--category", "prompting"],
    )

    result = runner.invoke(cli, ["experiment", "lessons", "--category", "prompting"])

    assert result.exit_code == 0, result.output
    assert id_a[:20] in result.output
    assert id_b[:20] in result.output


def test_parse_lesson_first_colon_split() -> None:
    """_parse_lesson splits on the first colon and lowercases the category (D-08)."""
    from kajiba.cli import _parse_lesson

    category, text = _parse_lesson("Prompting: be explicit")
    assert category == "prompting"
    assert text == "be explicit"


def test_parse_lesson_uncategorized_fallback() -> None:
    """A colon-less lesson falls back to the 'uncategorized' category (D-10)."""
    from kajiba.cli import _parse_lesson

    category, text = _parse_lesson("just a bare lesson")
    assert category == "uncategorized"
    assert text == "just a bare lesson"


def test_parse_lesson_preserves_colons_in_text() -> None:
    """Only the FIRST colon splits; colons in the lesson text are preserved (D-08)."""
    from kajiba.cli import _parse_lesson

    category, text = _parse_lesson("http: see https://x")
    assert category == "http"
    assert text == "see https://x"


# --- DRIFT (EREV-03 CLI half) ---------------------------------------------


def test_drift_idempotent_persists_and_clears(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`drift` sets drift_flag on an outlier, then clears it when it no longer drifts (D-15)."""
    store = _isolate_store(tmp_path, monkeypatch)
    a = _drift_record(store, experiment_id="d_a", eval_score=0.90,
                      started="2026-06-03T12:00:00Z")
    b = _drift_record(store, experiment_id="d_b", eval_score=0.90,
                      started="2026-06-03T12:01:00Z")
    outlier = _drift_record(store, experiment_id="d_c", eval_score=0.40,
                            started="2026-06-03T12:02:00Z")

    res1 = runner.invoke(cli, ["experiment", "drift"])
    assert res1.exit_code == 0, res1.output
    assert _read_record(store, outlier)["outcome"]["drift_flag"] is True

    # Add more consistent runs so the outlier's leave-one-out deviation shrinks
    # below threshold, then re-run drift — the flag must CLEAR (idempotent).
    _drift_record(store, experiment_id="d_d", eval_score=0.42,
                  started="2026-06-03T12:03:00Z")
    _drift_record(store, experiment_id="d_e", eval_score=0.41,
                  started="2026-06-03T12:04:00Z")
    _drift_record(store, experiment_id="d_f", eval_score=0.40,
                  started="2026-06-03T12:05:00Z")

    res2 = runner.invoke(cli, ["experiment", "drift"])
    assert res2.exit_code == 0, res2.output
    # 'a' and 'b' (0.90) are now the outliers; 'outlier' (0.40) sits with the
    # cluster, so its flag must have cleared.
    assert _read_record(store, outlier)["outcome"]["drift_flag"] is False


def test_drift_id_group_writes_whole_group(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`drift --id` writes/clears the WHOLE (model,task) group, not just --id (D-15, OQ2)."""
    store = _isolate_store(tmp_path, monkeypatch)
    # One group of 3 with a clear outlier.
    a = _drift_record(store, experiment_id="g_a", eval_score=0.90,
                      started="2026-06-03T12:00:00Z")
    b = _drift_record(store, experiment_id="g_b", eval_score=0.90,
                      started="2026-06-03T12:01:00Z")
    c = _drift_record(store, experiment_id="g_c", eval_score=0.40,
                      started="2026-06-03T12:02:00Z")
    # A record in a DIFFERENT group must remain untouched.
    other = _drift_record(store, experiment_id="o_a", eval_score=0.50,
                          model_name="modelY", task_category="writing",
                          started="2026-06-03T12:03:00Z")

    res = runner.invoke(cli, ["experiment", "drift", "--id", a])
    assert res.exit_code == 0, res.output

    # Whole-group write: outlier true, consistent runs false — all written.
    assert _read_record(store, c)["outcome"]["drift_flag"] is True
    assert _read_record(store, a)["outcome"]["drift_flag"] is False
    assert _read_record(store, b)["outcome"]["drift_flag"] is False
    # Other group untouched (still its seeded default False).
    assert _read_record(store, other)["outcome"]["drift_flag"] is False

    # Normalize the outlier, re-run drift --id — whole group clears.
    runner.invoke(
        cli, ["experiment", "review", c, "--critique", "n/a"],
    )
    # Bring the outlier into the cluster by adding consistent runs.
    _drift_record(store, experiment_id="g_d", eval_score=0.40,
                  started="2026-06-03T12:04:00Z")
    _drift_record(store, experiment_id="g_e", eval_score=0.41,
                  started="2026-06-03T12:05:00Z")
    _drift_record(store, experiment_id="g_f", eval_score=0.90,
                  started="2026-06-03T12:06:00Z")
    _drift_record(store, experiment_id="g_g", eval_score=0.90,
                  started="2026-06-03T12:07:00Z")

    res2 = runner.invoke(cli, ["experiment", "drift", "--id", c])
    assert res2.exit_code == 0, res2.output
    assert _read_record(store, c)["outcome"]["drift_flag"] is False


# --- WR error paths --------------------------------------------------------


def test_partial_flags_error(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`log --score` alone (no --from, missing --type/--task-category) errors (WR-01)."""
    _isolate_store(tmp_path, monkeypatch)

    result = runner.invoke(cli, ["experiment", "log", "--score", "0.5"])

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    # The message should name the missing flags rather than silently prompting.
    lowered = result.output.lower()
    assert "type" in lowered or "task" in lowered or "required" in lowered


def test_missing_record_kind_friendly(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`log --from` a fragment missing record_kind / required fields errors cleanly (WR-02)."""
    _isolate_store(tmp_path, monkeypatch)

    # (1) Otherwise-valid fragment that only omits record_kind.
    no_kind = json.loads(FIXTURE.read_text(encoding="utf-8"))
    no_kind.pop("record_kind", None)
    f1 = tmp_path / "no_kind.json"
    f1.write_text(json.dumps(no_kind), encoding="utf-8")

    res1 = runner.invoke(cli, ["experiment", "log", "--from", str(f1)])
    assert res1.exit_code != 0
    assert "Traceback" not in res1.output
    assert "ValidationError" not in res1.output
    # WR-02: a friendly user-facing message must be SHOWN (today the load
    # crashes with an unhandled ValidationError → empty output, RED).
    assert res1.output.strip() != ""
    assert res1.exception is None or isinstance(res1.exception, SystemExit)

    # (2) Fragment missing record_kind AND other required fields — default
    # injection of record_kind alone is insufficient; must still be friendly.
    f2 = tmp_path / "very_incomplete.json"
    f2.write_text(json.dumps({"experiment": {}}), encoding="utf-8")

    res2 = runner.invoke(cli, ["experiment", "log", "--from", str(f2)])
    assert res2.exit_code != 0
    assert "Traceback" not in res2.output
    assert "ValidationError" not in res2.output
    assert res2.output.strip() != ""
    assert res2.exception is None or isinstance(res2.exception, SystemExit)


def test_malformed_json_friendly(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`log --from` invalid JSON yields a 'Malformed JSON' message (WR-03)."""
    _isolate_store(tmp_path, monkeypatch)

    bad = tmp_path / "broken.json"
    bad.write_text("{ not valid json ", encoding="utf-8")

    result = runner.invoke(cli, ["experiment", "log", "--from", str(bad)])

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "Malformed JSON" in result.output
