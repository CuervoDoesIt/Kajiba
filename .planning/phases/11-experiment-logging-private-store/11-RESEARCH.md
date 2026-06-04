# Phase 11: Experiment Logging & Private Store - Research

**Researched:** 2026-06-03
**Domain:** Local-first persistence + Click CLI surface (Python 3.11+, Pydantic v2, Click, Rich)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Private Store Layout**
- **D-01:** Single flat store at `~/.hermes/kajiba/experiments/`, **one JSON file per run** named `exp_<record_id>.json` (e.g. `exp_kajiba_exp_<12hex>.json` — mirror the existing `record_{record_id}` naming idiom; exact filename prefix is planner's discretion as long as it is one file per run and clearly an experiment).
- **D-02:** **No staging→outbox promotion gate.** Records land directly in the store on log.
- **D-03:** The store base path derives from the **same base constant as `STAGING_DIR`/`OUTBOX_DIR`** (`KAJIBA_BASE` in `cli.py`). Do not hardcode a second `~/.hermes` literal — add `EXPERIMENTS_DIR = KAJIBA_BASE / "experiments"` and include it in `_ensure_dirs()`.
- **D-04:** Format is one-JSON-per-run (not append-only JSONL).

**Programmatic API (ELOG-02)**
- **D-05:** New module `src/kajiba/experiment_store.py` owns persistence.
- **D-06:** Two public functions:
  - `log_experiment(record: ExperimentRecord) -> Path` — computes IDs (`compute_record_id()` / `compute_submission_hash()`), writes the JSON to the store, returns the written path.
  - `build_experiment_record(**fields) -> ExperimentRecord` — convenience constructor.
- **D-07:** Both functions are **re-exported from `kajiba/__init__.py`**.
- **D-08:** Validation stays at the Pydantic boundary. `log_experiment` accepts an already-validated `ExperimentRecord`; `build_experiment_record` validates on construction. `log_experiment` is the single write path the CLI also calls.

**CLI Input Model (ELOG-01)**
- **D-09:** Add a `kajiba experiment` **Click group** (new `@cli.group()`, same pattern as `config`). Primary subcommand: `kajiba experiment log`.
- **D-10:** **File-first input:** `kajiba experiment log --from run.json` loads a JSON, validates it into an `ExperimentRecord` (reuse `load_record()` / `ExperimentRecord.model_validate`), then calls `log_experiment()`.
- **D-11:** A few **scalar convenience flags** (`--score`, `--type`, `--task-category`, similar top-level scalars) override or fill fields on top of `--from`.
- **D-12:** **Interactive fallback:** when neither `--from` nor required flags are supplied, prompt for essential fields via Rich. Nested `ModelMetadata` may be supplied via a `--model-from`/`--local-model` JSON snippet or reuse hardware/model auto-detection; capture the cleanest path.

**Publish Exclusion (ELOG-03)**
- **D-13:** **Structural + active guard (defense in depth).**
  - *Structural:* experiments live only in `EXPERIMENTS_DIR`; the experiment store **must never** write into `STAGING_DIR`/`OUTBOX_DIR` (assert/guard this).
  - *Active:* `publish` (and `submit`, if a path could reach it) explicitly **skip or refuse any record where `record_kind == "model_experiment"`**.
- **D-14:** A regression test must assert that an `ExperimentRecord` written by `log_experiment()` does **not** appear in `publish`/`browse`/`download` output.

### Claude's Discretion
- **Read-back command:** lean toward a minimal `kajiba experiment list`. Richer `show`/query is Phase 13/15.
- **Exact `run.json` schema/example:** document the canonical example file (a serialized `ExperimentRecord`).
- **Duplicate / overwrite handling:** content-addressable IDs mean re-logging the same experiment yields the same `exp_<id>.json`; decide overwrite vs skip-with-notice (suggested: skip + inform).
- **Interactive-mode field coverage** and how nested `ModelMetadata` is gathered (see D-12).
- Filename prefix exact spelling (D-01) and where the store dir constant lives.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope. Read-back beyond a minimal `experiment list`, querying `lessons_learned`, drift detection, scrubbing, and eval scoring are all Phase 12/13/15 scope. **No scrubbing happens at log time in this phase — records are stored raw.**
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ELOG-01 | User can deliberately record an eval run via a `kajiba experiment` CLI command group, without a live Hermes session | `config` `@cli.group()` pattern (cli.py:677) is the exact structural template; Rich `console`/`click.prompt` already used throughout cli.py for interactive fallback; `load_record()` (schema.py:515) parses `--from` JSON into an `ExperimentRecord` |
| ELOG-02 | A programmatic logging entry point lets an external script write `ExperimentRecord`s directly | New `experiment_store.py` with `log_experiment()` / `build_experiment_record()`, re-exported from `__init__.py`; `_submit_record()` (cli.py:371) is the reference write pattern (`compute_record_id()` → `model_dump(mode="json", by_alias=True)` → `write_text`) |
| ELOG-03 | Experiment records persist in a private namespace, separate from staging/outbox, excluded from any community publish path | `publish` loads only `OUTBOX_DIR` via `_load_outbox_records()` (cli.py:101); `browse`/`download` hit the remote dataset only — structural separation is automatic. Active guard: `record_kind == "model_experiment"` skip in `publish` Step 4 loop (cli.py:1476). Regression test via `CliRunner` + monkeypatch (D-14) |
</phase_requirements>

## Summary

Phase 11 is a **pure integration phase** built entirely on code that already exists in the repository. The `ExperimentRecord` family and its content-addressable identity methods (`kajiba_exp_<12hex>`) were frozen in Phase 10. There are no new external dependencies, no new libraries, and no network access. The entire phase is: (1) a new single-responsibility persistence module, (2) a new Click command group mirroring the existing `config` group, (3) two re-exported functions, and (4) a `record_kind` guard plus regression test on the existing publish path.

Because everything is local stdlib + already-pinned project deps (Pydantic v2, Click ≥8, Rich ≥13), confidence is HIGH across the board — the findings come from direct reads of `schema.py`, `cli.py`, `__init__.py`, and the existing test suite, not from training data. The only genuinely external technical question — how to write a single JSON file atomically and cross-platform on Windows + POSIX — resolves cleanly to the Python stdlib `os.replace()` (write-temp-then-replace), confirmed against the official Python docs.

**Primary recommendation:** Add `EXPERIMENTS_DIR = KAJIBA_BASE / "experiments"` to `cli.py` and `_ensure_dirs()`; create `experiment_store.py` owning `log_experiment()` (atomic write-temp-then-`os.replace`, skip-with-notice on identical content) and `build_experiment_record()`; add a `@cli.group() experiment` with `log` (+ minimal `list`); re-export the two functions from `__init__.py`; and add a `record_kind == "model_experiment"` skip in the `publish` consent-verification loop, proven by a `CliRunner` regression test.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Persist `ExperimentRecord` to disk | Persistence (`experiment_store.py`) | — | Single-responsibility module per project convention; CLI and programmatic callers both route through it (D-05/D-08) |
| Compute content-addressable IDs | Schema (`schema.py`, already built) | Persistence | `compute_record_id()`/`compute_submission_hash()` are frozen Phase 10 methods on `ExperimentRecord`; persistence calls them |
| Construct record from kwargs / file | Schema boundary | Persistence (`build_experiment_record`) | Pydantic validates on construction (D-08); `build_experiment_record` is a thin convenience wrapper |
| CLI input parsing & prompts | CLI (`cli.py` experiment group) | — | Click + Rich; mirrors existing `config` group and `rate`/`report` interactive patterns |
| Community-path exclusion | CLI (`publish` guard) + Persistence (dir separation) | — | Defense in depth (D-13): structural dir separation is primary, `record_kind` refusal is the backstop |
| Re-export public API | Package surface (`__init__.py`) | — | `from kajiba import log_experiment, build_experiment_record` (D-07) |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pydantic` | >=2.0 (pinned) `[VERIFIED: pyproject.toml]` | `ExperimentRecord` construction/validation/serialization | Already the schema layer's single source of truth; no alternative |
| `click` | >=8.0 (pinned) `[VERIFIED: pyproject.toml]` | `experiment` command group + options | Every existing CLI command is Click; `config` group is the template |
| `rich` | >=13.0 (pinned) `[VERIFIED: pyproject.toml]` | Interactive prompts / `list` table / success panels | Used throughout cli.py |
| stdlib `os` / `pathlib` / `json` | Python 3.11+ | Atomic single-file writes, path handling, serialization | Local-first, no third-party I/O lib needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `tempfile` (stdlib) | 3.11+ | Create temp file in the same directory before `os.replace` | Atomic-write helper (write-temp-then-replace) |
| `pytest` / `click.testing.CliRunner` | pytest >=7.0 `[VERIFIED: pyproject.toml]` | Regression + behavior tests | All CLI tests already use `CliRunner` + `monkeypatch` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `os.replace()` write-temp-then-rename | Direct `path.write_text()` | Direct write is what `_submit_record`/`export` currently do (cli.py:412, 559). For a single content-addressable file the atomicity benefit is marginal, but `os.replace` is strictly safer (no torn write on crash) and still cross-platform. **Recommend the temp-then-replace pattern** for the new module since it is greenfield and the project is local-first/cross-platform; matching existing direct-write is acceptable if the planner prefers minimalism. |
| New persistence module | Adding functions to `cli.py` | Violates one-module-per-responsibility convention (D-05); persistence must be importable without Click for ELOG-02 |
| `--local-model` JSON snippet for nested `ModelMetadata` | Field-by-field Rich prompts | JSON snippet is far cleaner than prompting ~9 nested fields; see Pitfall 3 |

**Installation:** None. No new packages. `[VERIFIED: pyproject.toml]` dependencies already satisfy the phase.

## Package Legitimacy Audit

> Not applicable — Phase 11 installs **no external packages**. All code uses already-pinned project dependencies (pydantic, click, rich) and the Python standard library (`os`, `pathlib`, `json`, `tempfile`, `hashlib`). No registry lookups or slopcheck run required.

## Architecture Patterns

### System Architecture Diagram

```
                 ELOG-01 (CLI)                         ELOG-02 (programmatic)
                      │                                        │
        kajiba experiment log [--from run.json]      from kajiba import
        [--score --type --task-category ...]           build_experiment_record,
        [interactive Rich fallback]                     log_experiment
                      │                                        │
                      ▼                                        ▼
        ┌──────────────────────────────┐         ┌──────────────────────────┐
        │ cli.py: experiment_log()      │         │ caller assembles fields  │
        │  - load_record(json) OR       │         │  build_experiment_record │
        │    build_experiment_record()  │         │   (validates on ctor)    │
        │  - apply scalar overrides     │         └────────────┬─────────────┘
        └───────────────┬──────────────┘                      │
                        │  ExperimentRecord (validated)        │
                        └──────────────┬───────────────────────┘
                                       ▼
                    ┌───────────────────────────────────────┐
                    │ experiment_store.log_experiment(rec)   │
                    │  1. assert dest is EXPERIMENTS_DIR only │ ◄── D-13 structural guard
                    │  2. rec.compute_record_id()            │
                    │  3. rec.compute_submission_hash()      │
                    │  4. dedup: if exp_<id>.json exists →    │ ◄── skip-with-notice
                    │     return existing path (Claude disc.) │
                    │  5. write temp → os.replace(dest)       │ ◄── atomic write
                    └────────────────────┬───────────────────┘
                                         ▼
                    ~/.hermes/kajiba/experiments/exp_<id>.json
                                         │
                                         │ (NEVER reaches the lines below)
                                         ▼
        ┌────────────────────────────────────────────────────────────┐
        │ Community path — structurally separate + actively guarded    │
        │  publish  → _load_outbox_records() globs OUTBOX_DIR only      │
        │             + skip any record_kind == "model_experiment" ◄────┼── D-13 active guard
        │  browse / download → remote dataset only (never touch disk    │
        │             experiment store)                                 │
        └────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| `EXPERIMENTS_DIR` constant + `_ensure_dirs()` extension | `src/kajiba/cli.py` (near line 64–75) | Derive store path from `KAJIBA_BASE` (D-03); create on demand |
| `log_experiment()` / `build_experiment_record()` | `src/kajiba/experiment_store.py` (new) | Persistence + convenience construction (D-05/D-06/D-08) |
| `experiment` group + `log` / `list` subcommands | `src/kajiba/cli.py` (new group, mirror `config` at line 677) | ELOG-01 input surface (D-09..D-12) |
| `record_kind` skip guard | `src/kajiba/cli.py` `publish` Step 4 loop (line ~1476) | ELOG-03 active backstop (D-13) |
| Re-exports | `src/kajiba/__init__.py` | `log_experiment`, `build_experiment_record` (D-07) |

### Recommended Project Structure
```
src/kajiba/
├── schema.py             # (existing, frozen) ExperimentRecord + identity methods
├── cli.py                # + EXPERIMENTS_DIR, _ensure_dirs() line, experiment group, publish guard
├── experiment_store.py   # NEW — log_experiment(), build_experiment_record()
└── __init__.py           # + re-exports
tests/
├── test_experiment_store.py   # NEW — programmatic API (ELOG-02), atomic write, dedup
├── test_cli_experiment.py     # NEW — experiment log/list CLI (ELOG-01)
└── test_experiment_exclusion.py  # NEW — ELOG-03 / D-14 regression
docs/ or tests/fixtures/
└── experiment_run.example.json   # NEW — canonical run.json (Claude's discretion)
```

### Pattern 1: Single Atomic Write Path (the shared write — D-08)
**What:** Both CLI and programmatic callers funnel through `log_experiment()`; no duplicate persistence logic.
**When to use:** Always — it is the single write path.
**Example:**
```python
# Source: pattern derived from cli.py:371-416 (_submit_record) + os.replace docs
# src/kajiba/experiment_store.py
import json
import logging
import os
import tempfile
from pathlib import Path

from kajiba.schema import ExperimentRecord

logger = logging.getLogger(__name__)


def log_experiment(record: ExperimentRecord, store_dir: Path) -> Path:
    """Persist a validated ExperimentRecord to the private store.

    Args:
        record: An already-validated ExperimentRecord (D-08).
        store_dir: The experiments store directory (EXPERIMENTS_DIR).

    Returns:
        Path to the written (or pre-existing identical) JSON file.

    Raises:
        ValueError: If store_dir resolves into the community staging/outbox.
    """
    # D-13 structural guard: refuse to write anywhere but the experiment store.
    resolved = store_dir.resolve()
    if resolved.name != "experiments":
        raise ValueError(f"Experiment store must be the experiments dir, got {resolved}")

    store_dir.mkdir(parents=True, exist_ok=True)
    record.compute_record_id()
    record.compute_submission_hash()
    dest = store_dir / f"exp_{record.record_id}.json"

    # Content-addressable dedup (Claude's discretion: skip-with-notice).
    if dest.exists():
        logger.info("Experiment already logged (identical content): %s", dest)
        return dest

    data = record.model_dump(mode="json", by_alias=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"

    # Atomic write: temp file in same dir, then os.replace (atomic on POSIX + Windows).
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
```
> Note: the CLI owns `EXPERIMENTS_DIR` (D-03 says it derives from `KAJIBA_BASE` in `cli.py`). Passing `store_dir` into `log_experiment` keeps the store module free of a hardcoded `~/.hermes` literal and keeps it monkeypatch-friendly for tests. The planner may alternatively define the constant in `experiment_store.py` and import it into `cli.py` — either satisfies D-03 as long as there is exactly one base literal (`KAJIBA_BASE`). Decide and document.

### Pattern 2: `build_experiment_record` convenience constructor (D-06)
**What:** kwargs → nested `ExperimentRecord`, validating on construction.
**Example:**
```python
# src/kajiba/experiment_store.py
from datetime import UTC, datetime
from typing import Optional

from kajiba.schema import (
    ExperimentMetadata, ExperimentOutcome, ExperimentRecord, ModelMetadata,
)


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
    """Assemble and validate an ExperimentRecord from flat kwargs (D-06)."""
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
```

### Pattern 3: New Click group mirroring `config` (D-09)
**What:** `@cli.group()` + subcommands, exactly like `config` (cli.py:677–783).
**Example:**
```python
# Source: cli.py:677-682 (config group template)
@cli.group()
def experiment() -> None:
    """Log and inspect private model-experiment runs."""


@experiment.command("log")
@click.option("--from", "from_path", type=click.Path(exists=True), default=None,
              help="Load an ExperimentRecord from a JSON file.")
@click.option("--score", "eval_score", type=click.FloatRange(0.0, 1.0), default=None)
@click.option("--type", "experiment_type",
              type=click.Choice(list(EXPERIMENT_TYPES)), default=None)
@click.option("--task-category", default=None)
@click.option("--local-model", "model_json", type=click.Path(exists=True), default=None,
              help="JSON snippet for nested ModelMetadata (D-12).")
def experiment_log(from_path, eval_score, experiment_type, task_category, model_json):
    """Record an eval run as a private ExperimentRecord (ELOG-01)."""
    # 1. file-first: load_record(json.loads(...)) -> ExperimentRecord
    # 2. apply scalar overrides on top (D-11)
    # 3. interactive Rich fallback if neither --from nor required flags (D-12)
    # 4. path = log_experiment(record, EXPERIMENTS_DIR); console.print success
```
> `load_record()` (schema.py:515) already dispatches `record_kind == "model_experiment"` → `ExperimentRecord`. For `--from`, prefer `load_record(data)` over `ExperimentRecord.model_validate(data)` so a malformed `record_kind` is caught consistently. Validate that the result is an `ExperimentRecord` and error clearly if a caller passes a coding-session file.

### Pattern 4: ELOG-03 active guard in `publish` (D-13)
**What:** Skip experiment-kind records inside the existing consent-verification loop.
**Where:** `publish` Step 4, the `for path, data in outbox_records:` loop (cli.py:1476).
**Example:**
```python
# Inside publish() Step 4 loop (cli.py ~1476)
for path, data in outbox_records:
    if data.get("record_kind") == "model_experiment":
        logger.warning("Refusing to publish experiment record: %s", path)
        console.print(f"[yellow]  Skipping experiment record (never published): {path.name}[/yellow]")
        continue
    # ... existing consent verification ...
```
> Reading `data.get("record_kind")` on the raw dict (before `validate_record`) is correct and robust: `_load_outbox_records()` returns raw dicts, and `validate_record()` only builds `KajibaRecord`, so checking the discriminator first also avoids feeding an experiment dict into the coding-session validator. Apply the same guard in `submit`/`_submit_record` only if a code path can route an experiment record there — currently `submit` only reads `STAGING_DIR`, so the structural separation already covers it; add a defensive assertion rather than dead code.

### Anti-Patterns to Avoid
- **Hardcoding a second `~/.hermes` literal** for the store — violates D-03. Derive from `KAJIBA_BASE` only.
- **Scrubbing at log time** — explicitly out of scope this phase; store records raw (CONTEXT domain note).
- **Field-by-field prompting for nested `ModelMetadata`** — awkward and error-prone; prefer a `--local-model` JSON snippet (D-12, Pitfall 3).
- **Duplicating persistence logic in the CLI** — the CLI must call `log_experiment()` (D-08), not write files itself.
- **Validating an experiment file with `validate_record()`** — that builds a `KajibaRecord` and will reject/ misparse experiment data; use `load_record()` or `ExperimentRecord.model_validate()`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Content-addressable IDs | Custom hash logic | `record.compute_record_id()` / `compute_submission_hash()` (schema.py:445) | Already frozen in Phase 10; format locked `kajiba_exp_<12hex>` |
| record_kind dispatch on load | `if data["record_kind"] == ...` everywhere | `load_record()` (schema.py:515) | Single dispatch point, legacy-safe default |
| Atomic cross-platform file replace | Custom lock/flush dance | `tempfile.mkstemp` + `os.replace()` | `os.replace` is atomic on POSIX and Windows and overwrites the destination (unlike `os.rename` on Windows) `[CITED: docs.python.org/3/library/os.html#os.replace]` |
| Serialization with `from` alias | Manual dict building | `model_dump(mode="json", by_alias=True)` | Project convention; handles the `from_`→`"from"` alias on nested `ConversationTurn` |
| CLI testing harness | subprocess | `click.testing.CliRunner` + `monkeypatch` | Every existing CLI test uses this (test_cli.py) |

**Key insight:** Phase 11 is assembly, not invention. Every hard part (identity, validation, serialization, dispatch) was solved in Phase 10. The only new primitive is one atomic-write helper, which is six lines of stdlib.

## Runtime State Inventory

> This is not a rename/refactor/migration phase — it is additive (new module, new command, new dir). No existing stored data, service config, OS-registered state, secrets, or build artifacts are renamed or migrated.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — `EXPERIMENTS_DIR` is a brand-new namespace; no existing records change. Verified: `experiments/` does not appear in cli.py and is not in `_ensure_dirs()`. | None |
| Live service config | None — no external services touched (core is offline; publish only runs on explicit user action). | None |
| OS-registered state | None — no scheduled tasks, daemons, or registrations. | None |
| Secrets/env vars | None — no API keys or env vars; core pipeline is offline by constraint. | None |
| Build artifacts | New module `experiment_store.py` is picked up by `setuptools.packages.find` automatically (`where=["src"]`, pyproject.toml:52). After adding it, an editable reinstall (`pip install -e .`) refreshes the entry-point/console script if needed, but the new module imports without reinstall. | Reinstall not strictly required for module import; recommended if console script behavior changes (it does not). |

## Common Pitfalls

### Pitfall 1: `validate_record()` cannot parse an experiment file
**What goes wrong:** Reusing `validate_record()` (which calls `KajibaRecord.model_validate`) on a `--from run.json` experiment file will fail or mis-parse.
**Why it happens:** `validate_record()` is hardwired to `KajibaRecord` (schema.py:512); experiments need `ExperimentRecord`.
**How to avoid:** Use `load_record()` (dispatches by `record_kind`) or `ExperimentRecord.model_validate()` directly.
**Warning signs:** `ValidationError` about missing `trajectory`/`outcome.user_rating` when loading an experiment.

### Pitfall 2: Tests pollute the real `~/.hermes/kajiba/experiments/`
**What goes wrong:** CLI/programmatic tests write to the user's real home store.
**Why it happens:** `KAJIBA_BASE`/`EXPERIMENTS_DIR` are module-level constants resolved at import.
**How to avoid:** Follow the existing test idiom — `monkeypatch.setattr("kajiba.cli.EXPERIMENTS_DIR", tmp_path / "experiments")` (and `KAJIBA_BASE` where `_ensure_dirs` is exercised), exactly as test_cli.py monkeypatches `STAGING_DIR`/`OUTBOX_DIR`/`KAJIBA_BASE` (test_cli.py:147, 212–214). If `log_experiment` takes `store_dir` as an argument, tests pass `tmp_path` directly — cleaner.
**Warning signs:** Files appearing in your actual home dir during `pytest`.

### Pitfall 3: Nested `ModelMetadata` is painful to prompt for (D-12)
**What goes wrong:** Interactive mode tries to prompt 9 optional nested fields (`model_family`, `quantization`, `context_window`, ...).
**Why it happens:** `ExperimentMetadata.local_model` is a required nested `ModelMetadata` (schema.py:413), and only `model_name` is required.
**How to avoid:** **Recommended path:** interactive mode prompts only for `local_model.model_name` (the one required field) and accepts an optional `--local-model model.json` snippet for the full nested object. Field-by-field prompting of all nine is worse UX and harder to test. Auto-detection (reusing collector hardware/model detection) is out of scope here (collector targets live Hermes sessions) — note it as a Phase 14 enhancement, do not build it now.
**Warning signs:** A prompt avalanche; brittle prompt-order tests.

### Pitfall 4: `os.rename` instead of `os.replace` breaks dedup-overwrite on Windows
**What goes wrong:** If the planner later chooses overwrite semantics, `os.rename` raises `FileExistsError` on Windows when the destination exists.
**Why it happens:** Windows `rename` does not overwrite; `replace` does `[CITED: docs.python.org/3/library/os.html#os.replace]`.
**How to avoid:** Always use `os.replace` for the temp→final move. (With skip-with-notice dedup the dest never exists at replace time anyway, but `os.replace` is the correct default regardless.)
**Warning signs:** `FileExistsError` only on Windows CI.

### Pitfall 5: Interactive prompts hang `CliRunner` tests
**What goes wrong:** A test that doesn't supply `input=` to an interactive path blocks/errors.
**Why it happens:** `click.prompt` reads stdin.
**How to avoid:** Mirror the existing pattern — pass `runner.invoke(cli, [...], input="...\n...\n")` (test_cli.py:216 uses `input="y\n"`). Test the `--from` and flag-driven (non-interactive) paths primarily; cover one interactive path with scripted `input=`.
**Warning signs:** Tests hang or exit with `Aborted!`.

## Code Examples

### Reading `--from` and applying scalar overrides (D-10/D-11)
```python
# Source: composed from schema.load_record (515) + cli option patterns
import json
from kajiba.schema import load_record, ExperimentRecord

def _load_from_file(from_path: str) -> ExperimentRecord:
    data = json.loads(Path(from_path).read_text(encoding="utf-8"))
    rec = load_record(data)
    if not isinstance(rec, ExperimentRecord):
        raise click.ClickException("--from file is not a model_experiment record.")
    return rec

# Scalar overrides (D-11): mutate validated fields, then re-validate via model_validate
if eval_score is not None:
    rec.outcome.eval_score = eval_score          # Pydantic re-checks bound on assignment? See note.
```
> Note: Pydantic v2 does **not** validate on attribute assignment unless `model_config = {"validate_assignment": True}` is set, and `ExperimentRecord`/`ExperimentOutcome` do not set it. To keep overrides safe, prefer rebuilding via `model_copy(update=...)` then `ExperimentRecord.model_validate(rec.model_dump(...))`, or apply overrides to the dict **before** `load_record()`. Recommend: apply scalar overrides to the raw dict pre-validation so the existing validators (eval_score bound, vocab) catch bad values. Document this in the plan.

### Minimal `experiment list` (Claude's discretion read-back)
```python
@experiment.command("list")
def experiment_list() -> None:
    """List logged experiment runs (confirms they are absent from browse)."""
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(EXPERIMENTS_DIR.glob("exp_*.json"),
                   key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        console.print("[yellow]No experiments logged.[/yellow]")
        return
    table = Table(title="Logged Experiments")
    table.add_column("Record ID"); table.add_column("Type")
    table.add_column("Task"); table.add_column("Score", justify="right")
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        exp = d.get("experiment", {}); out = d.get("outcome", {})
        table.add_row(d.get("record_id", "—"), exp.get("experiment_type", "—"),
                      exp.get("task_category", "—"), str(out.get("eval_score", "—")))
    console.print(table)
```

### Canonical `run.json` example (Claude's discretion — document this)
```json
{
  "schema_version": "0.2.0",
  "record_kind": "model_experiment",
  "experiment": {
    "experiment_id": "exp_001",
    "experiment_type": "model_evaluation",
    "local_model": {
      "model_name": "Hermes-3-Llama-3.1-8B",
      "quantization": "Q4_K_M",
      "provider": "ollama",
      "is_local": true
    },
    "reviewer_model": { "model_name": "gpt-4o" },
    "task_category": "coding",
    "task_description": "Write a binary search function.",
    "started_at": "2026-06-03T12:00:00Z",
    "completed_at": "2026-06-03T12:05:00Z"
  },
  "outcome": {
    "local_model_output": "def bsearch(a, x): ...",
    "reviewer_critique": "Correct but missing edge cases.",
    "eval_score": 0.82,
    "drift_flag": false,
    "lessons_learned": ["handle empty input"],
    "recommended_action": "needs_fine_tune"
  }
}
```
> This shape is exactly what `model_dump(mode="json", by_alias=True)` produces and what `load_record()` consumes — so `--from run.json` and the ELOG-02 script path are interchangeable (a verified round-trip is already proven by `test_schema_experiment.py::test_round_trip`). `record_id`/`submission_hash` are omitted in the input example because `log_experiment` computes them. Store the example at `tests/fixtures/experiment_run.example.json` (or `docs/`) and reference it from the `experiment log` `--help`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `os.rename` for "move into place" | `os.replace` (atomic + overwrites on Windows) | stdlib (3.3+) | Cross-platform atomic single-file writes without conditional logic `[CITED: docs.python.org]` |
| Discriminated-union models | Manual `load_record()` factory by `record_kind` | Phase 10 (10-02) | Phase 11 must call `load_record()`, not a union validator |

**Deprecated/outdated:** None relevant. No deprecated APIs in scope.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Pydantic v2 does not validate on attribute assignment for these models (no `validate_assignment` config) | Code Examples / scalar overrides | LOW — verified by reading schema.py (no `validate_assignment` in any model_config); risk is only that an override of an invalid scalar wouldn't be caught at assignment time. Mitigation (apply overrides pre-validation) documented. `[VERIFIED: schema.py read]` |
| A2 | `submit` cannot currently route an experiment record (it only reads `STAGING_DIR`, and only `log_experiment` writes experiments, only to `EXPERIMENTS_DIR`) | Pattern 4 | LOW — structural separation makes the active `submit` guard defensive-only; if a future path writes experiments to staging this assumption breaks. Recommend a defensive assertion, not dead code. `[VERIFIED: cli.py read — submit() uses _load_latest_staging only]` |
| A3 | Adding `experiment_store.py` requires no reinstall for import (only the package is already installed editable) | Runtime State Inventory | LOW — standard setuptools `find` behavior; module is importable in dev once on path. `[VERIFIED: pyproject.toml packages.find]` |

**Note:** A1–A3 are all verified by direct repository reads; none require user confirmation. There are **no `[ASSUMED]`-from-training claims** that affect a locked decision.

## Open Questions

1. **Where does `EXPERIMENTS_DIR` live — `cli.py` or `experiment_store.py`?**
   - What we know: D-03 says "add `EXPERIMENTS_DIR = KAJIBA_BASE / "experiments"` … include it in `_ensure_dirs()`" — that strongly implies `cli.py`.
   - What's unclear: ELOG-02 callers import from `kajiba` directly and may want the path without importing `cli` (which pulls in Click). Defining the base in `cli.py` and passing `store_dir` into `log_experiment` (as in Pattern 1) resolves this cleanly.
   - Recommendation: define `EXPERIMENTS_DIR` in `cli.py` (satisfies D-03 literally); have `log_experiment(record, store_dir)` take the dir as a parameter so the store module stays Click-free and test-friendly. Document the single-base-literal rule.

2. **Overwrite vs skip on identical content.**
   - What we know: content-addressable IDs mean re-logging identical content targets the same file.
   - Recommendation: **skip-with-notice** (CONTEXT suggested it; content is byte-identical so overwrite is wasted I/O). Detect via `dest.exists()` before write. Implemented in Pattern 1.

## Environment Availability

> Phase 11 is code/config-only with no external runtime dependencies (offline core pipeline). All needed tooling is already present.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | everything | ✓ | 3.13.3 on dev machine (req ≥3.11) | — |
| pydantic | record models | ✓ (pinned dep) | >=2.0 | — |
| click | CLI group | ✓ (pinned dep) | >=8.0 | — |
| rich | prompts/tables | ✓ (pinned dep) | >=13.0 | — |
| pytest / CliRunner | tests | ✓ (dev extra) | >=7.0 | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None. (`gh` CLI is only needed to *exercise* `publish` end-to-end, but the ELOG-03 regression test asserts the guard via `CliRunner` without network/`gh` — see Validation Architecture.)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=7.0 + `click.testing.CliRunner` `[VERIFIED: pyproject.toml, test_cli.py]` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `addopts="-v"`) |
| Quick run command | `python -m pytest tests/test_experiment_store.py tests/test_cli_experiment.py tests/test_experiment_exclusion.py -x` |
| Full suite command | `python -m pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ELOG-01 | `kajiba experiment log --from run.json` writes `exp_<id>.json` and prints success | integration | `python -m pytest tests/test_cli_experiment.py::test_log_from_file -x` | ❌ Wave 0 |
| ELOG-01 | scalar flags (`--score`/`--type`/`--task-category`) override/fill (D-11) | integration | `python -m pytest tests/test_cli_experiment.py::test_log_scalar_overrides -x` | ❌ Wave 0 |
| ELOG-01 | interactive fallback persists with scripted `input=` (D-12) | integration | `python -m pytest tests/test_cli_experiment.py::test_log_interactive -x` | ❌ Wave 0 |
| ELOG-01 | `kajiba experiment list` shows logged runs (read-back) | integration | `python -m pytest tests/test_cli_experiment.py::test_list -x` | ❌ Wave 0 |
| ELOG-02 | `build_experiment_record(**fields)` returns a valid `ExperimentRecord` | unit | `python -m pytest tests/test_experiment_store.py::test_build_record -x` | ❌ Wave 0 |
| ELOG-02 | `log_experiment(record, dir)` writes file, returns path, computes IDs | unit | `python -m pytest tests/test_experiment_store.py::test_log_writes_file -x` | ❌ Wave 0 |
| ELOG-02 | re-logging identical content is skipped with same path (dedup) | unit | `python -m pytest tests/test_experiment_store.py::test_dedup_skip -x` | ❌ Wave 0 |
| ELOG-02 | write is atomic (no `.tmp` left behind; valid JSON) | unit | `python -m pytest tests/test_experiment_store.py::test_atomic_write -x` | ❌ Wave 0 |
| ELOG-02 | `from kajiba import log_experiment, build_experiment_record` works (D-07) | unit | `python -m pytest tests/test_experiment_store.py::test_public_exports -x` | ❌ Wave 0 |
| ELOG-03 | `log_experiment` refuses a non-`experiments` dir (structural guard, D-13) | unit | `python -m pytest tests/test_experiment_store.py::test_refuses_outbox_dir -x` | ❌ Wave 0 |
| ELOG-03 | `publish` skips `record_kind == "model_experiment"` (active guard, D-13) | integration | `python -m pytest tests/test_experiment_exclusion.py::test_publish_skips_experiment -x` | ❌ Wave 0 |
| ELOG-03 | a logged experiment never appears in publish/browse/download output (D-14 regression) | integration | `python -m pytest tests/test_experiment_exclusion.py::test_experiment_absent_from_community_paths -x` | ❌ Wave 0 |

> D-14 regression detail: write an experiment via `log_experiment` to a monkeypatched `EXPERIMENTS_DIR`; assert (a) `OUTBOX_DIR` glob does not contain it, (b) `publish --dry-run` (with `gh` calls monkeypatched or with an empty outbox) never includes the experiment record_id in output, and (c) `browse`/`download` read only the remote catalog (no disk read of `EXPERIMENTS_DIR`) — assert by confirming the experiment file is untouched and its id never appears in command output. Avoid real network: monkeypatch `GitHubOps`/`_fetch_catalog` or assert on the structural path (outbox glob excludes it) which needs no network.

### Sampling Rate
- **Per task commit:** the relevant new test file's quick run (`pytest tests/test_experiment_store.py -x`).
- **Per wave merge:** all three new test files.
- **Phase gate:** full suite green (`python -m pytest`) before `/gsd-verify-work`. Baseline is currently 264 passed, 2 pre-existing skips (yaml soft-dep) — new tests add to passed count; the 2 skips remain expected.

### Wave 0 Gaps
- [ ] `tests/test_experiment_store.py` — covers ELOG-02 + ELOG-03 structural guard
- [ ] `tests/test_cli_experiment.py` — covers ELOG-01 (log + list, file/flags/interactive)
- [ ] `tests/test_experiment_exclusion.py` — covers ELOG-03 active guard + D-14 regression
- [ ] `tests/fixtures/experiment_run.example.json` — canonical `--from` fixture (doubles as the documented example)
- [ ] Framework install: none needed (pytest + CliRunner already present)

## Security Domain

> `security_enforcement` not present in `.planning/config.json` → treat as enabled. Scope is narrow: a local, offline, additive persistence feature with no auth, sessions, network, or crypto.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth surface; local CLI only |
| V3 Session Management | no | No sessions |
| V4 Access Control | partial | OS filesystem perms only; store under user home (`~/.hermes/kajiba/experiments/`). The **privacy boundary** (experiments never published) is the security-relevant control — enforced by D-13 dir separation + `record_kind` guard + D-14 test |
| V5 Input Validation | yes | Pydantic v2 validates every field on construction/`model_validate`; controlled vocabularies (`EXPERIMENT_TYPES`, `RECOMMENDED_ACTIONS`) reject out-of-vocab; `eval_score` bound `[0,1]` |
| V6 Cryptography | no | `hashlib.sha256` is used for content-addressable IDs only (not security crypto); never hand-roll — already in schema.py |
| V12 Files & Resources | yes | `--from` reads a user-supplied JSON path; use `json.loads` (no `eval`), validate via `load_record`, write only inside `EXPERIMENTS_DIR` (structural guard refuses other dirs) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Experiment data leaking into community publish | Information Disclosure | Defense in depth: structural dir separation (primary) + `record_kind == "model_experiment"` refusal in `publish` (backstop) + D-14 regression test |
| Malformed/hostile `--from` JSON | Tampering | `json.loads` + Pydantic validation via `load_record`; reject non-experiment records with a clear `ClickException` |
| Path traversal via store dir / record_id | Tampering | `record_id` is a hash-derived `kajiba_exp_<12hex>` (no user-controlled path chars); filename is constructed, not user-supplied; structural guard asserts the parent dir is `experiments` |
| Torn write on crash leaves corrupt JSON | Denial / integrity | Atomic write-temp-then-`os.replace`; clean up temp on exception |
| Raw PII stored at log time (no scrub this phase) | Information Disclosure | By design out of scope (Phase 12 adds experiment-aware scrub); store is **private/no-publish** so PII never leaves the machine. Document this explicitly so it is a conscious, not accidental, gap. |

## Sources

### Primary (HIGH confidence)
- `src/kajiba/schema.py` — `RecordBase`, `ExperimentRecord`/`ExperimentMetadata`/`ExperimentOutcome`, `compute_record_id`/`compute_submission_hash` (`kajiba_exp_<12hex>`), `load_record()` dispatch, `EXPERIMENT_TYPES`/`RECOMMENDED_ACTIONS`
- `src/kajiba/cli.py` — `KAJIBA_BASE`/`STAGING_DIR`/`OUTBOX_DIR`, `_ensure_dirs()`, `_load_outbox_records()`, `_submit_record()`, `config` group, `publish`/`browse`/`download`
- `src/kajiba/__init__.py` — current export surface (`__version__` only)
- `tests/test_cli.py` — `CliRunner` + `monkeypatch` dir-isolation idiom, scripted `input=`
- `tests/test_schema_experiment.py` — round-trip proof, vocab rejection, eval_score bounds
- `pyproject.toml` — pinned deps, `packages.find`, pytest config
- `.planning/phases/11-experiment-logging-private-store/11-CONTEXT.md` — locked decisions D-01..D-14
- `docs.python.org/3/library/os.html#os.replace` `[CITED]` — atomic, cross-platform, overwrites on Windows

### Secondary (MEDIUM confidence)
- `.planning/STATE.md` — Phase 10 completion notes (identity format locked, SCHEMA_VERSION 0.2.0, 264 tests passing / 2 skips)

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new deps; all pinned/stdlib, read directly from pyproject.toml.
- Architecture: HIGH — every integration point read directly from source; patterns mirror existing `config` group, `_submit_record`, and test idioms.
- Pitfalls: HIGH — each pitfall traced to a specific line/behavior in the repo or the official Python docs.

**Research date:** 2026-06-03
**Valid until:** 2026-07-03 (stable — local stdlib + pinned deps; only changes if the schema or CLI structure is refactored).
