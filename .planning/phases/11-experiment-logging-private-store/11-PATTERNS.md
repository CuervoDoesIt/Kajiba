# Phase 11: Experiment Logging & Private Store - Pattern Map

**Mapped:** 2026-06-03
**Files analyzed:** 7 (2 new source, 2 modified source, 3 new tests, 1 new fixture)
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/kajiba/experiment_store.py` (NEW) | service / persistence | file-I/O (write) | `cli.py::_submit_record()` + `os.replace` | role-match (write idiom) |
| `src/kajiba/cli.py` (MOD: `experiment` group + `log`/`list`) | controller / CLI | request-response | `cli.py::config` group (line 677), `config_show` table | exact |
| `src/kajiba/cli.py` (MOD: `EXPERIMENTS_DIR` + `_ensure_dirs()`) | config / constants | file-I/O | `KAJIBA_BASE`/`STAGING_DIR`/`OUTBOX_DIR` + `_ensure_dirs()` (lines 64-74) | exact |
| `src/kajiba/cli.py` (MOD: `publish` guard) | controller | transform / filter | `publish` Step 4 loop (line 1476) | exact (in-place edit) |
| `src/kajiba/__init__.py` (MOD: re-exports) | package surface | n/a | current `__version__` export | exact |
| `tests/test_experiment_store.py` (NEW) | test | unit | `tests/test_cli.py` monkeypatch idiom | role-match |
| `tests/test_cli_experiment.py` (NEW) | test | integration | `tests/test_cli.py` CliRunner+`input=` | exact |
| `tests/test_experiment_exclusion.py` (NEW) | test | integration | `tests/test_cli.py::test_*_consent_*` (publish-style flow) | role-match |
| `tests/fixtures/experiment_run.example.json` (NEW) | fixture | data | `model_dump(mode="json", by_alias=True)` of `ExperimentRecord` | derived |

## Pattern Assignments

### `src/kajiba/experiment_store.py` (NEW — service, file-I/O write)

**Analog:** `src/kajiba/cli.py::_submit_record()` (lines 406-416) for the ID-compute → `model_dump` → write sequence. The new module uses atomic `tempfile.mkstemp` + `os.replace` rather than direct `write_text` (greenfield + cross-platform; see RESEARCH Pitfall 4).

**Module header / import + logger pattern** (copy convention from `cli.py:1-17,57` and `schema.py` module-logger idiom):
```python
"""Experiment store — persistence for private model-experiment records.

Owns the single write path for ExperimentRecord (ELOG-02). The CLI
experiment group and external eval scripts both route through here.
"""

import json
import logging
import os
import tempfile
from pathlib import Path

from kajiba.schema import ExperimentRecord

logger = logging.getLogger(__name__)
```

**ID-compute + serialize + write core** — model the sequence on `_submit_record` lines 406-415, swapping the direct write for atomic temp-then-replace:
```python
# Analog: cli.py:406-415 (_submit_record)
final.compute_record_id()
final.compute_submission_hash()
_ensure_dirs()
outbox_file = OUTBOX_DIR / f"record_{final.record_id}.jsonl"
record_json = final.model_dump(mode="json", by_alias=True)
outbox_file.write_text(
    json.dumps(record_json, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
```
New module mirrors this but: filename `exp_{record.record_id}.json` (D-01), `indent=2` for inspectability (D-04), `mode="json", by_alias=True` (project convention), atomic write via `os.replace`. Full reference implementation is in RESEARCH.md Pattern 1 (lines 194-235). Re-export typing/style: `Optional[X]`, double quotes, Google docstrings.

**Structural guard (D-13):** before writing, assert the destination dir's `.name == "experiments"` and raise `ValueError` otherwise (RESEARCH Pattern 1 lines 207-210). This is the only genuinely new logic — no existing analog; it enforces the privacy boundary.

**Dedup skip-with-notice:** `if dest.exists(): logger.info(...); return dest` (Claude's discretion, RESEARCH lines 217-219). Mirrors the `logger.info("...%s", path)` lazy-`%s` logging convention used throughout (`_submit_record`, collector).

---

### `src/kajiba/cli.py` — `EXPERIMENTS_DIR` constant + `_ensure_dirs()` (MOD, config)

**Analog:** lines 64-74 (exact template).
```python
KAJIBA_BASE = Path.home() / ".hermes" / "kajiba"
STAGING_DIR = KAJIBA_BASE / "staging"
OUTBOX_DIR = KAJIBA_BASE / "outbox"
DOWNLOADS_DIR = Path.home() / ".hermes" / "kajiba" / "downloads"


def _ensure_dirs() -> None:
    """Create Kajiba directories if they don't exist."""
    KAJIBA_BASE.mkdir(parents=True, exist_ok=True)
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
```
**Apply:** add `EXPERIMENTS_DIR = KAJIBA_BASE / "experiments"` next to the other dir constants (D-03 — derive from `KAJIBA_BASE`, no second `~/.hermes` literal), and add `EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)` inside `_ensure_dirs()`. Pass `EXPERIMENTS_DIR` into `log_experiment(record, store_dir)` so the store module stays Click-free (Open Question 1 resolution).

---

### `src/kajiba/cli.py` — `experiment` group + `log` / `list` (MOD, controller, request-response)

**Analog:** `config` group (lines 677-719).

**Group declaration pattern** (lines 677-682):
```python
@cli.group(invoke_without_command=True)
@click.pass_context
def config(ctx: click.Context) -> None:
    """Manage Kajiba configuration."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(config_show)
```
**Apply:** declare `@cli.group()` `def experiment()` (group docstring "Log and inspect private model-experiment runs."). Subcommands `@experiment.command("log")` and `@experiment.command("list")`. Option declarations and the `log` body skeleton are in RESEARCH Pattern 3 (lines 288-308). Import `EXPERIMENT_TYPES` (schema.py:114) for `--type` `click.Choice`, and `load_record` / `ExperimentRecord` (schema.py:515, 432) for `--from`.

**`--from` load + override pattern (D-10/D-11):** use `load_record(json.loads(...))` NOT `validate_record()` (Pitfall 1 — `validate_record` is hardwired to `KajibaRecord`, schema.py:512). Validate `isinstance(rec, ExperimentRecord)` and raise `click.ClickException` otherwise (RESEARCH lines 397-402). Apply scalar overrides to the raw dict **before** `load_record()` so Pydantic validators catch bad values (RESEARCH note lines 404-408 — no `validate_assignment` on these models).

**Interactive Rich fallback (D-12):** prompt only for the single required `local_model.model_name` plus essential scalars; accept `--local-model model.json` for the full nested `ModelMetadata` (Pitfall 3). `console = Console()` is already module-level (cli.py:58); use `click.prompt` / Rich as elsewhere.

**`list` table pattern** — model on `config_show` table (lines 703-719):
```python
table = Table(title="Kajiba Configuration")
table.add_column("Setting", style="bold")
table.add_column("Value")
...
console.print(table)
```
Glob `EXPERIMENTS_DIR.glob("exp_*.json")` sorted by mtime; full read-back example in RESEARCH lines 412-429.

---

### `src/kajiba/cli.py` — `publish` active guard (MOD, transform/filter)

**Analog & insertion point:** the `for path, data in outbox_records:` loop at line 1476 (Step 4 consent re-verification).
```python
for path, data in outbox_records:
    try:
        record = validate_record(data)
        ...
```
**Apply (D-13 active guard):** as the first statement inside the loop, before `validate_record(data)`, check the raw dict discriminator:
```python
for path, data in outbox_records:
    if data.get("record_kind") == "model_experiment":
        logger.warning("Refusing to publish experiment record: %s", path)
        console.print(f"[yellow]  Skipping experiment record (never published): {path.name}[/yellow]")
        continue
    try:
        record = validate_record(data)
        ...
```
Reading `record_kind` on the raw dict (matches how `_load_outbox_records` returns raw dicts, line 113) avoids feeding an experiment into the `KajibaRecord` validator. The existing `logger.warning(...); console.print("[yellow]  Skipping...")` skip-style at lines 1496-1497 is the exact phrasing/style to mirror. `submit` (line 477) reads only `STAGING_DIR` via `_load_latest_staging`, so it needs only a defensive assertion, not dead code (Assumption A2).

---

### `src/kajiba/__init__.py` (MOD, package surface)

**Current state (entire file):**
```python
"""Kajiba (鍛冶場) — Community data pipeline for open-source local model improvement."""

__version__ = "0.1.0"
```
**Apply (D-07):** add `from kajiba.experiment_store import build_experiment_record, log_experiment` so `from kajiba import log_experiment, build_experiment_record` works. (Project has no `__all__` convention — non-underscore names are public; keep that, but the import itself is the export.)

---

### `tests/test_experiment_store.py` / `tests/test_cli_experiment.py` / `tests/test_experiment_exclusion.py` (NEW, tests)

**Analog:** `tests/test_cli.py`.

**Runner fixture** (test_cli.py:13-14):
```python
@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()
```

**Dir-isolation monkeypatch idiom** (test_cli.py:147, 212-214) — the critical pattern for Pitfall 2:
```python
monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
monkeypatch.setattr("kajiba.cli.OUTBOX_DIR", outbox)
monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)
```
**Apply:** `monkeypatch.setattr("kajiba.cli.EXPERIMENTS_DIR", tmp_path / "experiments")` for CLI tests; for `test_experiment_store.py` pass `tmp_path` directly as `store_dir` (cleaner, store module is Click-free).

**Scripted interactive input** (test_cli.py:216):
```python
result = runner.invoke(cli, ["submit"], input="y\n")
```
**Apply:** test `--from` and flag-driven paths primarily (no `input=`); cover one interactive path with scripted `input="...\n...\n"` (Pitfall 5). Assert via `result.exit_code == 0` and `result.output` substring checks, as test_cli.py does throughout.

**Exclusion regression (D-14):** write via `log_experiment` to monkeypatched `EXPERIMENTS_DIR`, then assert (a) `OUTBOX_DIR.glob("*.jsonl")` excludes it, (b) the `publish` guard skips a misplaced `model_experiment` dict, (c) the experiment file is untouched and its `record_id` never appears in command output. Monkeypatch `GitHubOps`/catalog fetch to avoid network (RESEARCH line 535).

---

### `tests/fixtures/experiment_run.example.json` (NEW, fixture)

**Source:** the exact shape of `ExperimentRecord.model_dump(mode="json", by_alias=True)`, omitting `record_id`/`submission_hash` (computed by `log_experiment`). Canonical content in RESEARCH lines 433-461. Doubles as the documented `--from` example referenced from `experiment log --help`. Round-trip already proven by `test_schema_experiment.py::test_round_trip`.

## Shared Patterns

### Serialization
**Source:** `cli.py:411` (`_submit_record`), `schema.py` convention.
**Apply to:** `experiment_store.py` write, fixture shape.
```python
record_json = final.model_dump(mode="json", by_alias=True)
```
`by_alias=True` is mandatory project-wide (the `from_`→`"from"` alias on nested `ConversationTurn`).

### Record load/dispatch
**Source:** `schema.py:515` (`load_record`).
**Apply to:** CLI `--from`, all places parsing a possibly-experiment JSON.
```python
kind = data.get("record_kind", "coding_session")
if kind == "model_experiment":
    return ExperimentRecord.model_validate(data)
return KajibaRecord.model_validate(data)
```
Never use `validate_record()` (KajibaRecord-only) on experiment data — Pitfall 1.

### Content-addressable identity
**Source:** `schema.py:445,469` (`ExperimentRecord.compute_record_id` / `compute_submission_hash`).
**Apply to:** `log_experiment` (call both before writing). Format locked `kajiba_exp_<12hex>`; do not hand-roll hashing.

### Logging
**Source:** module-level `logger = logging.getLogger(__name__)`; lazy `%s` (`_submit_record`, publish line 1496).
**Apply to:** `experiment_store.py` (dedup notice, write confirm), CLI guard. Never `print()` for logging.

### CLI rendering / prompts
**Source:** module-level `console = Console()` (cli.py:58); `Table` usage `config_show` (lines 703-719); `console.print("[yellow]...[/yellow]")` status style.
**Apply to:** `experiment list` table, `log` success panel, publish skip notice.

### Test isolation
**Source:** `tests/test_cli.py` `monkeypatch.setattr("kajiba.cli.<DIR>", tmp_path/...)` + `CliRunner` + scripted `input=`.
**Apply to:** all three new test files. Prevents writes to the real `~/.hermes` store (Pitfall 2).

## No Analog Found

| Concern | Role | Reason | Guidance |
|---------|------|--------|----------|
| Atomic write-temp-then-`os.replace` helper | persistence | Existing code uses direct `write_text` (`_submit_record:412`, `export`); no atomic-write precedent | Use stdlib `tempfile.mkstemp` + `os.replace` per RESEARCH Pattern 1 (six lines, cross-platform). Acceptable to match existing direct `write_text` if planner prefers minimalism. |
| Structural dir guard (`store_dir.name == "experiments"`) | persistence security | No prior "refuse-to-write-outside-X" guard exists | New logic; enforces D-13 privacy boundary. Raise `ValueError`. |
| `build_experiment_record(**fields)` kwargs constructor | schema convenience | No flat-kwargs builder for nested models exists (collector assembles models imperatively) | Thin wrapper assembling `ExperimentMetadata`/`ExperimentOutcome`/`ModelMetadata`; validates on construction (D-08). Skeleton in RESEARCH Pattern 2 (lines 252-280). |

## Metadata

**Analog search scope:** `src/kajiba/` (cli.py, schema.py, __init__.py), `tests/`
**Files scanned:** cli.py (targeted: constants/`_submit_record`/`config` group/publish loop), schema.py (ExperimentRecord family + `load_record`), __init__.py (full), test_cli.py (idioms)
**Pattern extraction date:** 2026-06-03
