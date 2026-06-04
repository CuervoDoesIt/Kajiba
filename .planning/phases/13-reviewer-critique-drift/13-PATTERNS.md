# Phase 13: Reviewer Critique & Drift - Pattern Map

**Mapped:** 2026-06-04
**Files analyzed:** 7 (3 source ADD/MODIFY, 1 NEW source, 1 frozen READ-ONLY, 2 test EXTEND, 1 test NEW)
**Analogs found:** 7 / 7 (all in-repo, all verified at file:line)

All file:line claims in CONTEXT/RESEARCH were re-verified against live source this session. No drift found — pointers are accurate.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/kajiba/experiment_store.py` (ADD `update_experiment`) | store / persistence | file-I/O (atomic overwrite) | `log_experiment` same file (`:49-105`) | exact (same module, same write mechanics) |
| `src/kajiba/cli.py` (ADD `review`/`lessons`/`drift`, enrich `list`) | controller / CLI | request-response (Click) | `experiment_log` (`:894`), `experiment_score` (`:1044`), `_load_experiment` (`:82`) | exact (same group, same idioms) |
| `src/kajiba/experiment_drift.py` (NEW pure compute) | service / compute | transform (records → verdict dict) | `eval_scorer.py` (`:1-55`) | role-match (compute module shape; but drift PERSISTS, eval does not) |
| `src/kajiba/__init__.py` (re-export) | config / package API | — | existing re-export block (`:5-7`) | exact |
| `src/kajiba/schema.py` | model | READ-ONLY (frozen) | — (do not modify) | n/a |
| `tests/test_experiment_store.py` (EXTEND) | test | unit | `_make_record` (`:27`), `test_build_record` (`:56`) | exact |
| `tests/test_cli_experiment.py` (EXTEND) | test | integration | `_isolate_store` (`:28`), `test_log_from_file` (`:36`) | exact |
| `tests/test_experiment_drift.py` (NEW) | test | unit | `test_eval_scorer.py` (`:1-45`) + `_make_record` pattern | role-match |

## Pattern Assignments

### `src/kajiba/experiment_store.py` — ADD `update_experiment()` (store, file-I/O)

**Analog:** `log_experiment` (same file, `:49-105`) — the proven atomic write. `update_experiment` is `log_experiment` MINUS the `dest.exists()` early-return (CR-01 fix) PLUS a re-validate step and a tightened guard (WR-04).

**Module imports already present** (`:27-40`) — reuse verbatim, no new imports needed except possibly `KAJIBA_BASE` for the WR-04 guard:
```python
import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional
from kajiba.schema import (ExperimentMetadata, ExperimentOutcome, ExperimentRecord, ModelMetadata)
logger = logging.getLogger(__name__)
```

**Atomic write mechanics to COPY** (`:90-105`) — `mkstemp` + `os.fdopen` + `os.replace` + `BaseException` cleanup. This is cross-platform-proven and already tested (`test_atomic_write`):
```python
data = record.model_dump(mode="json", by_alias=True)
payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
fd, tmp_name = tempfile.mkstemp(dir=store_dir, suffix=".tmp")
try:
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(payload)
    os.replace(tmp_name, dest)
except BaseException:
    Path(tmp_name).unlink(missing_ok=True)
    raise
```

**Identity computation to COPY** (`:81-83`):
```python
record.compute_record_id()
record.compute_submission_hash()
dest = store_dir / f"exp_{record.record_id}.json"
```

**KEY DIFFERENCES from analog (do NOT copy these from `log_experiment`):**
- DELETE the `if dest.exists(): return dest` dedup-skip (`:86-88`) — this is the CR-01 bug. `update_experiment` always overwrites.
- ADD a re-validate-after-mutation step before computing identity:
  `record = ExperimentRecord.model_validate(record.model_dump(mode="json", by_alias=True))` (models lack `validate_assignment`; re-validation is the project rule).
- TIGHTEN the D-13 guard. Analog uses leaf-name only (`:72-76`, the WR-04 defect):
```python
# CURRENT (weak) — also fix in log_experiment per WR-04:
resolved = store_dir.resolve()
if resolved.name != "experiments":
    raise ValueError(f"Experiment store must be the 'experiments' directory, got {resolved}")
```
  Replace with `resolved == EXPERIMENTS_DIR.resolve()` or `resolved.is_relative_to(KAJIBA_BASE)`. Apply the SAME tightened guard to both `log_experiment` and the new `update_experiment`.

**Docstring style:** Google-style with `Args:`/`Returns:`/`Raises:`, mirroring `log_experiment:50-69`. Note in docstring why in-place is safe (identity excludes outcome, `schema.py:445-467`) and that it closes CR-01.

---

### `src/kajiba/cli.py` — ADD `review` / `lessons` / `drift`; enrich `list` (controller, request-response)

**Analog (command structure):** `experiment_log` (`:859-989`) and `experiment_score` (`:1044-1081`).

**Group decorator + command idiom to COPY** (`:854-859`):
```python
@experiment.command("log")     # -> @experiment.command("review") etc.
@click.option("--score", "eval_score", type=click.FloatRange(0.0, 1.0), default=None, help="...")
@click.option("--type", "experiment_type", type=click.Choice(list(EXPERIMENT_TYPES)), default=None, help="...")
def experiment_log(...) -> None:
    _ensure_dirs()
```
For `--action` use the `click.Choice(list(RECOMMENDED_ACTIONS))` pattern exactly as `--type` uses `click.Choice(list(EXPERIMENT_TYPES))` (`:875-879`). `RECOMMENDED_ACTIONS` is at `schema.py:117` (verified).

**Load-by-id to REUSE verbatim** — `_load_experiment(record_id)` (`:82-128`). Already has the path-traversal guard (`:108-110`) and `isinstance(rec, ExperimentRecord)` check (`:123-126`). Single-argument commands take `@click.argument("record_id")` like `experiment_score` (`:1045`). DO NOT reinvent loading.

**Single-write-path discipline** — `experiment_log` ends with `path = log_experiment(rec, EXPERIMENTS_DIR)` (`:983`); the CLI NEVER writes the file. All three new commands mutate the loaded record then call `update_experiment(record, EXPERIMENTS_DIR)`. Recommended shared private helper `_mutate_experiment(record_id, mutate_fn)` wrapping load → mutate → `update_experiment` (RESEARCH Pattern 1).

**Rich rendering to COPY** — `experiment_score` Table + Panel (`:1063-1081`) for drift summary / critique display:
```python
table = Table(title=f"Eval Confidence — {record_id}")
table.add_column("Check")
table.add_column("Sub-score", justify="right")
...
console.print(table)
console.print(Panel(f"...", title="..."))
```

**`list` enrichment** — extend the existing per-file-guarded loop (`:1015-1039`). Read `lessons_learned`/`drift_flag` from the RAW dict (no full validation needed for display); keep the `try/except ... continue` per-file guard (`:1016-1020`, Pitfall 6). Add two columns after the existing five (`:1006-1013`):
```python
outcome = data.get("outcome", {})
lessons = outcome.get("lessons_learned", [])
drift = "⚠" if outcome.get("drift_flag") else ""
# add to table.add_row(...): str(len(lessons)), drift
```

**WR fix sites in `experiment_log` (sweep while editing):**
- **WR-01** (`:939-943`): the `elif eval_score is not None and experiment_type is not None and task_category is not None:` branch requires ALL three scalars. When SOME-but-not-all are supplied (and no `--from`), it silently drops into interactive and discards the flags. Fix: raise `click.ClickException` naming the missing flags.
- **WR-02** (`:935`): `rec = load_record(data)` — a `--from` file missing `record_kind` routes to `KajibaRecord` and raises raw `ValidationError`. Fix: `data.setdefault("record_kind", "model_experiment")` before load, OR try/except → `ClickException`. (Note `load_record` defaults to `coding_session` per `schema.py`, so default-inject is the cleaner fix.)
- **WR-03** (`:917`, `:921`): raw `json.loads` on `--local-model` / `--from` surfaces a `JSONDecodeError` traceback. Fix: wrap each in `try/except json.JSONDecodeError` → `click.ClickException(f"Malformed JSON in {path}: {exc}")`. Apply same to the new `review --from .json` path.

---

### `src/kajiba/experiment_drift.py` — NEW pure compute module (service, transform)

**Analog:** `eval_scorer.py` (`:1-55`) — same single-responsibility, Click-free, stdlib-only compute-module shape (module docstring explaining the role, `logger = logging.getLogger(__name__)`, `UPPER_SNAKE_CASE` threshold constants, a pure `compute_*` entrypoint).

**Imports/header pattern to MIRROR** (`eval_scorer.py:18-23`):
```python
import logging
from statistics import mean          # stdlib — drift baseline (verified Python 3.13)
from kajiba.schema import ExperimentRecord
logger = logging.getLogger(__name__)
```

**Threshold-constant pattern to MIRROR** (`eval_scorer.py:29-30`):
```python
DRIFT_THRESHOLD = 0.15   # default; overridable via --threshold (flag-only, D-14)
```

**CRITICAL CONTRAST with the analog (document in the module docstring):** `eval_scorer` is compute-on-read and NEVER persisted (`eval_scorer.py:14-15`). Drift is the OPPOSITE — `compute_drift` returns a verdict that the `drift` CLI command WRITES to `outcome.drift_flag` via `update_experiment` (D-02). The shape mirrors eval_scorer; the persistence does not.

**Grouping/baseline fields (verified):** `r.experiment.local_model.model_name` (`schema.py:413` ModelMetadata), `r.experiment.task_category` (`schema.py:415`), `r.outcome.eval_score` (`schema.py:426`, `Field(ge=0.0, le=1.0)`), `r.outcome.drift_flag` (`schema.py:427`, `bool = False`). Group `<2` runs: never flag, guard before `mean([])` (Pitfall 3). Return a verdict over ALL records so the CLI can SET and CLEAR idempotently (D-15).

---

### `src/kajiba/__init__.py` — re-export (config)

**Analog:** existing block (`:5-7`):
```python
from kajiba.experiment_store import build_experiment_record, log_experiment
from kajiba.eval_scorer import compute_eval_confidence
from kajiba.experiment_scrub import scrub_experiment
```
Add `update_experiment` to the `experiment_store` import line; add `from kajiba.experiment_drift import compute_drift` (D-discretion: lean yes, Phase 15 may call programmatically).

---

### `src/kajiba/schema.py` — READ-ONLY (frozen, model)

**DO NOT MODIFY.** Confirmed all five target fields already exist:
- `ExperimentOutcome` (`:421-429`): `reviewer_critique: Optional[str]`, `eval_score: float = Field(ge=0.0, le=1.0)`, `drift_flag: bool = False`, `lessons_learned: list[str]`, `recommended_action: Optional[RecommendedActionType]`.
- `ExperimentMetadata` (`:408-418`): `local_model`, `reviewer_model: Optional[ModelMetadata]`, `task_category`, `started_at`.
- `RECOMMENDED_ACTIONS` / `RecommendedActionType` (`:117-118`).
- `compute_record_id` (`:445-467`) / `compute_submission_hash` (`:469-492`) — VERIFIED both hash the same 5-key identity payload (`experiment_id`, `task_description`, `local_model_name`, `local_model_output`, `started_at.isoformat()`) and exclude ALL `outcome` fields. This is the proof that in-place mutation keeps the filename byte-stable (D-01).

A golden-ID tripwire (`test_schema_backcompat.py`) guards this. Phase gate: `git diff --quiet src/kajiba/schema.py` must exit 0.

---

### `tests/test_experiment_store.py` — EXTEND (test, unit)

**Analog:** `_make_record(**overrides)` helper (`:27-53`) — builds a fully-populated `ExperimentRecord` with nested `ExperimentMetadata`/`ExperimentOutcome`/`ModelMetadata`; accepts `overrides` to vary fields. REUSE for `update_experiment` tests (vary `eval_score`/`drift_flag`/`outcome`).

**Isolation idiom:** pass `tmp_path / "experiments"` directly as `store_dir` (the store is Click-free, no monkeypatch needed — header note `:10-12`).

**Test-shape to MIRROR** (`test_build_record:56`, and the existing atomic/dedup/guard tests). Add: `update` overwrite (corrected score persists, exactly one file), `identity_stable` (record_id byte-stable across mutation), tightened `guard` (WR-04 — same-named dir outside KAJIBA_BASE rejected).

---

### `tests/test_cli_experiment.py` — EXTEND (test, integration)

**Analog:** `_isolate_store(tmp_path, monkeypatch)` (`:28-33`) — monkeypatches `kajiba.cli.EXPERIMENTS_DIR` and `kajiba.cli.KAJIBA_BASE`. REUSE VERBATIM. `CliRunner` fixture (`:23-25`).

**Test-shape to MIRROR** (`test_log_from_file:36`, `test_log_scalar_overrides:54`):
```python
store = _isolate_store(tmp_path, monkeypatch)
result = runner.invoke(cli, ["experiment", "review", "<id>", "--critique", "..."])
assert result.exit_code == 0, result.output
data = json.loads(written[0].read_text(encoding="utf-8"))
assert data["outcome"]["reviewer_critique"] == "..."
```
Interactive paste tests pass the blob via `runner.invoke(..., input="...")`. Add: review (3 input modes + reviewer-model + action + re-review-replaces), lessons (add/read/filter/cross-record), drift (persist + idempotent clear), WR-01/02/03 error paths.

---

### `tests/test_experiment_drift.py` — NEW (test, unit)

**Analog:** `test_eval_scorer.py` (`:1-45`) for the pure-compute-unit-test structure (RED-import header note, fixture/builder loads, direct `compute_*` assertions) + `_make_record` builder pattern from `test_experiment_store.py:27`.

Build records in-test via `_make_record` (copy the helper or import it). Cover: both directions beyond threshold, `<2`-run group never flagged (no `mean([])` crash), `--threshold` override, leave-one-out baseline. Pure function — no store/CLI needed.

## Shared Patterns

### Single write path (D-03)
**Source:** `experiment_store.py` (module docstring `:1-25`, project rule "single write path through experiment_store.py").
**Apply to:** All three new CLI commands. CLI mutates an in-memory record then calls `update_experiment(record, EXPERIMENTS_DIR)`. The CLI never opens `exp_*.json` for writing; `experiment_list` only reads.

### Load-by-id with path-safety + isinstance
**Source:** `_load_experiment` (`cli.py:82-128`).
**Apply to:** `review`, `lessons <id>`, `drift --id`. Reuse verbatim — it owns the T-12-10 traversal guard and T-12-11 type check.

### Re-validate after mutation
**Source:** project rule + RESEARCH Pattern 2. Models have NO `validate_assignment`.
**Apply to:** `update_experiment` — `ExperimentRecord.model_validate(record.model_dump(mode="json", by_alias=True))` before writing. Gate `--action` at the CLI with `click.Choice(RECOMMENDED_ACTIONS)`.

### load_record (not validate_record) for experiment data
**Source:** `_load_experiment` uses `load_record` (`cli.py:117`); `experiment_log` uses `load_record` (`:935`).
**Apply to:** any `--from`/dict load. `validate_record` forces `KajibaRecord` and raises (WR-02).

### Per-file guarded store glob
**Source:** `experiment_list` loop (`cli.py:1015-1020`) and `log_experiment` glob conventions.
**Apply to:** cross-record `lessons --category`, `drift` store scan, enriched `list`. `for f in sorted(EXPERIMENTS_DIR.glob("exp_*.json")): try json.loads ... except: continue`.

### Module conventions (project-wide)
**Source:** CLAUDE.md + every module.
**Apply to:** all new code — `snake_case`, double quotes, `Optional[X]` (not `X | None`), `list[str]`/`dict[str,bool]` generics, module-level `logger = logging.getLogger(__name__)`, Google-style docstrings, `UPPER_SNAKE_CASE` constants, section-divider comment rules, `model_dump(mode="json", by_alias=True)` for serialization.

## No Analog Found

None. Every file in this phase has a strong in-repo analog. The only genuinely new logic (drift algorithm, lesson parse rule) is pure/small and modeled on `eval_scorer.py`'s compute-module shape (drift) and standard string helpers (lessons).

## Metadata

**Analog search scope:** `src/kajiba/` (experiment_store, cli, eval_scorer, experiment_scrub, schema, __init__), `tests/` (test_experiment_store, test_cli_experiment, test_eval_scorer).
**Files scanned:** 9 source/test files, all read at the relevant line ranges; all CONTEXT/RESEARCH file:line pointers verified accurate.
**Pattern extraction date:** 2026-06-04
