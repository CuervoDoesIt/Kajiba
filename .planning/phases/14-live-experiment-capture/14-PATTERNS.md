# Phase 14: Live Experiment Capture - Pattern Map

**Mapped:** 2026-06-06
**Files analyzed:** 2 (1 modified module + 1 modified test file)
**Analogs found:** 6 / 6 (all in-codebase; this is a pure wiring phase)

> **Orchestrating principle (from CONTEXT/RESEARCH):** Zero new schema, zero new
> persistence module. The executor must **COPY** the existing finalize-once
> discipline and the existing experiment write path — not invent new ones. Every
> capability already ships in a module; the only genuinely new code is a mode flag,
> a finalize branch, and a self-cleaning finalize-once for a content-addressed
> filename. If the planner finds itself adding a model or a store, that is a smell.

## File Classification

| New/Modified Symbol | Target File | Role | Data Flow | Closest Analog | Match Quality |
|---------------------|-------------|------|-----------|----------------|---------------|
| `_finalize_experiment(session_id)` (new method) | `src/kajiba/collector.py` | collector (finalize branch) | event-driven → file-I/O | coding finalize in `on_session_end` + `_save_to_staging` + `self._finalized` guard (`collector.py:603-692, 775-791`) | role + flow match (divergent tail of same handler) |
| `_build_experiment_record(session_id)` (new helper) | `src/kajiba/collector.py` | collector (record assembly) | transform | `_build_record` (`collector.py:735-773`) + `build_experiment_record(**fields)` (`experiment_store.py:231-284`) | exact (combine two analogs) |
| `_build_trajectory()` (extracted helper) | `src/kajiba/collector.py` | collector (sub-assembly) | transform | trajectory block inside `_build_record` (`collector.py:741-761`) | exact (extract-in-place) |
| New instance attrs (`_experiment_mode`, `_experiment_type`, `_task_category`, `_last_experiment_path`) | `src/kajiba/collector.py` | collector (state) | n/a | attr resets in `on_session_start` (`collector.py:393-402`) + `self._finalized` guard (`collector.py:346`) | exact |
| Env-var trigger read in `on_session_start` | `src/kajiba/collector.py` | collector (config) | request-response (env read) | `KAJIBA_DEBUG == "1"` idiom (`plugin/hooks.py:36`) | role match (read at call-time, not import-time — intentional deviation) |
| `TestExperimentCapture` (new test class) | `tests/test_collector.py` | test | event-driven lifecycle | `TestCollectorLifecycle` (`test_collector.py:13-70`) + tmp_path/store isolation (`test_experiment_store.py:1-53`) | exact |

## Pattern Assignments

### `KajibaCollector._finalize_experiment(session_id)` (collector, event-driven → file-I/O)

**Analogs:** coding finalize in `on_session_end` (`src/kajiba/collector.py:617-692`); the ad-hoc
fixed-filename overwrite trick (`collector.py:631-636`); the `self._finalized` continuous-mode
guard (`collector.py:640-642`); the overwrite write path `update_experiment` (`src/kajiba/experiment_store.py:133-223`).

**Why a new branch and not a new handler:** D-07 ("shared core, divergent tail"). The branch must
be inserted at the TOP of the existing `on_session_end` try block and `return` cleanly, leaving the
coding path below it byte-for-byte unchanged (Pitfall 2 / no-regression).

**Branch insertion point** — copy the no-regression guard shape, insert BEFORE the
`contribution_mode` read at `collector.py:628-629`:
```python
# src/kajiba/collector.py — inside on_session_end try block, FIRST thing after the mismatch warning
if self._experiment_mode:                 # NEW divergent tail (D-07/D-08)
    self._finalize_experiment(session_id) # NEVER touches STAGING_DIR/OUTBOX_DIR/auto-submit
    return
# ----- existing coding path below, UNCHANGED (collector.py:628-689) -----
contribution_mode = _load_config_value("contribution_mode", "ad-hoc")
...
```

**Finalize-once pattern to COPY (the load-bearing correctness item).** The coding path solves
per-turn-end idempotency two ways and the experiment path must adapt BOTH because its filename is
content-addressed and `local_model_output` (D-03, the last gpt turn) changes every turn:
- Ad-hoc trick (`collector.py:631-636`): rewrite the SAME file each turn → one file per session.
- Continuous guard (`collector.py:640-642`): `if self._finalized: return` once-flag.

Recommended **Design B (RESEARCH Pattern 2 / Pitfall 1)** — session-stable identity +
self-cleaning overwrite-latest. Track `self._last_experiment_path`, unlink the prior file when the
content ID moves, then write the latest:
```python
def _finalize_experiment(self, session_id: str) -> None:
    if not self._conversations:
        return  # Pitfall 3: zero-turn / interrupted end → write nothing
    rec = self._build_experiment_record(session_id)
    new_path = EXPERIMENTS_DIR / f"exp_{rec.record_id}.json"
    if self._last_experiment_path and self._last_experiment_path != new_path:
        self._last_experiment_path.unlink(missing_ok=True)  # drop stale prior-turn file
    update_experiment(rec, EXPERIMENTS_DIR)  # overwrite-safe write path (experiment_store.py:133) — NEVER log_experiment (skip-on-exists orphans files as the content ID moves)
    self._last_experiment_path = new_path
```

**Write path to COPY (do NOT hand-roll).** `update_experiment` (`experiment_store.py:133-223`)
owns the D-13 structural guard, atomic temp-file `os.replace` write, ID re-computation, and
re-validation. It INTENTIONALLY overwrites (no `dest.exists()` early-return — it closed CR-01,
`experiment_store.py:207`). Prefer it over `log_experiment` (`experiment_store.py:104-130`) whose
skip-on-exists (`experiment_store.py:111-113`) would leave orphan files as the content ID moves
(Anti-Pattern, RESEARCH line 233).

**Fault-tolerance (COPY):** the outer `on_session_end` already wraps everything in
`try/except Exception` → `logger.exception(...)` (`collector.py:617, 691-692`). Keep the experiment
finalize inside that guard; never let a hook exception reach Hermes.

---

### `KajibaCollector._build_experiment_record(session_id)` (collector, transform)

**Analogs:** `_build_record` (`src/kajiba/collector.py:735-773`) for the buffered-turns → record
shape; `build_experiment_record(**fields)` (`src/kajiba/experiment_store.py:231-284`) for the nested
`ExperimentMetadata`/`ExperimentOutcome` assembly.

**Convenience constructor signature to COPY** (`experiment_store.py:231-284`) — keyword-only fields,
`started_at` optional, `**extra` forwarded to the `ExperimentRecord(...)` constructor (i.e. sets
top-level RecordBase fields `model`/`hardware`/`trajectory`, NOT the nested `experiment.local_model`):
```python
return ExperimentRecord(
    experiment=ExperimentMetadata(
        experiment_id=experiment_id,
        experiment_type=experiment_type,
        local_model=ModelMetadata(model_name=local_model_name),  # scalar-name-only
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

**Assembly pattern (per RESEARCH Code Examples, verified against the two analogs):**
```python
def _build_experiment_record(self, session_id: str) -> "ExperimentRecord":
    # D-04 / D-03: first human turn → task_description; last gpt turn → local_model_output.
    # Search the list defensively (Pitfall 3) — do not index [0]/[-1].
    first_user = next((t.value for t in self._conversations if t.from_ == "human"), "")
    last_gpt = next((t.value for t in reversed(self._conversations) if t.from_ == "gpt"), "")
    rec = build_experiment_record(
        experiment_id=f"live_{session_id}",                 # session-stable identity (Pattern 2)
        experiment_type=self._experiment_type,
        task_category=self._task_category,
        task_description=first_user,
        local_model_name=(self._model_metadata.model_name
                          if self._model_metadata else "unknown"),
        local_model_output=last_gpt,
        eval_score=0.0,                                     # D-05 documented placeholder
        started_at=self._created_at,                        # stable across turns (set once at start)
        model=self._model_metadata,                         # **extra → RecordBase.model
        hardware=self._hardware,                            # **extra → RecordBase.hardware
        trajectory=self._build_trajectory(),                # **extra → ExperimentRecord.trajectory (D-06)
    )
    if self._model_metadata:
        rec.experiment.local_model = self._model_metadata   # Pattern 3: rich metadata for analysis
    return rec
```

**Mutation-then-validate caveat (Pitfall 4):** setting `rec.experiment.local_model` happens BEFORE
the write call. The models lack `validate_assignment`, but `update_experiment` re-validates via
`ExperimentRecord.model_validate(...)` before writing (`experiment_store.py:196-198`) and computes
IDs at write time (`experiment_store.py:203-205`) — so the on-disk filename matches the persisted
content. Ensure `self._model_metadata.model_name` is non-empty (it defaults to `"unknown"` via
`_extract_model_metadata`, per RESEARCH) because it feeds `compute_record_id`.

**Metadata reuse (Pattern 3 — do NOT re-detect):** `self._model_metadata` / `self._hardware` are
already assembled fault-tolerantly in `on_session_start` via `_build_metadata_and_hardware`
(`collector.py:403-405`), including Ollama enrichment (CAPT-04) or remote slug-inference. Remote
under eval mode (`is_local=false`, `parameter_count=None`) is acceptable — do not block on locality.

---

### `KajibaCollector._build_trajectory()` (collector, transform — extracted helper)

**Analog:** the trajectory-assembly block currently inline in `_build_record`
(`src/kajiba/collector.py:741-761`). Extract it verbatim so both the coding path and the experiment
path share ONE assembly (Don't-Hand-Roll, RESEARCH line 243).

**Block to extract** (`collector.py:741-761`):
```python
all_tool_calls = [
    tc for turn in self._conversations if turn.tool_calls for tc in turn.tool_calls
]
turn_count = len(self._conversations)
total_tool_calls = len(all_tool_calls)
successful_tool_calls = sum(1 for tc in all_tool_calls if tc.tool_status == "success")
failed_tool_calls = total_tool_calls - successful_tool_calls
trajectory = Trajectory(
    format="sharegpt_extended",
    conversations=self._conversations,
    turn_count=turn_count,
    total_tool_calls=total_tool_calls,
    successful_tool_calls=successful_tool_calls,
    failed_tool_calls=failed_tool_calls,
)
```
**Note:** `ExperimentRecord.trajectory` is `Optional[Trajectory]` with NO
`validate_turn_count`/`validate_tool_call_counts` validators (those live only on `KajibaRecord`),
so the extracted block is free-form-safe for the experiment path. After extraction, `_build_record`
calls `self._build_trajectory()` instead of the inline block — keep its behavior identical (Pitfall 2).

---

### New collector instance attributes (collector, state)

**Analog:** the existing attribute initialization in `__init__` (`collector.py:325-346`) and the
per-session reset block in `on_session_start` (`collector.py:393-402`); the `self._finalized` once-flag
(`collector.py:346`, reset at `collector.py:401`) is the direct template for `_last_experiment_path`.

**Pattern to COPY:** declare each attr with its type+default in `__init__`, and reset it in the
`on_session_start` try block alongside the existing resets (so a re-used collector across sessions
starts clean):
```python
# __init__ (mirror collector.py:346 self._finalized declaration)
self._experiment_mode: bool = False
self._experiment_type: str = "model_evaluation"
self._task_category: str = "coding"
self._last_experiment_path: Optional[Path] = None

# on_session_start, alongside the existing resets at collector.py:393-402
self._experiment_mode = os.environ.get("KAJIBA_EXPERIMENT") == "1"
self._last_experiment_path = None
```

---

### Env-var trigger read in `on_session_start` (collector, config read)

**Analog:** the `KAJIBA_DEBUG == "1"` idiom in `src/kajiba/plugin/hooks.py:36`:
```python
_DEBUG = os.environ.get("KAJIBA_DEBUG") == "1"   # hooks.py:36 — read ONCE at import time
```

**Intentional deviation (RESEARCH Pattern 1 note):** copy the `os.environ.get(...) == "1"`
comparison idiom, but read at **`on_session_start` call time**, NOT import time — the flag is
per-session, so the same loaded plugin must handle both coding and experiment sessions across the
Hermes process lifetime. Read alongside the existing resets (`collector.py:393-402`):
```python
from kajiba.schema import EXPERIMENT_TYPES  # tuple for runtime validation
self._experiment_mode = os.environ.get("KAJIBA_EXPERIMENT") == "1"
_t = os.environ.get("KAJIBA_EXPERIMENT_TYPE", "model_evaluation")
self._experiment_type = _t if _t in EXPERIMENT_TYPES else "model_evaluation"
self._task_category = os.environ.get("KAJIBA_EXPERIMENT_CATEGORY", "coding")
```
Env-var names are the planner's final call (keep the `KAJIBA_EXPERIMENT*` namespace).
`plugin/hooks.py` and `plugin/__init__.py` need NO change — the env read belongs on the collector.

---

### `tests/test_collector.py::TestExperimentCapture` (test, event-driven lifecycle)

**Analogs:** `TestCollectorLifecycle.test_full_session_lifecycle` (`tests/test_collector.py:13-70+`)
for the drive-through-lifecycle idiom (`on_session_start` → N×`on_turn_complete`/turn events →
`on_session_end`); `tests/test_experiment_store.py` (lines 1-53) for the tmp_path store-isolation
idiom and the `_make_record(**overrides)` helper shape.

**Lifecycle-drive idiom to COPY** (`test_collector.py:16-53`): instantiate `KajibaCollector()`,
call `on_session_start(session_id=..., model_config={...})`, then drive turns. For the finalize-once
scenario, drive `on_session_start` → N×(turn + `on_session_end`) to simulate the turn-scoped firing
and assert exactly ONE `exp_*.json` results.

**Isolation idiom to COPY** (`test_experiment_store.py:10-12` + RESEARCH Wave 0 Gaps):
`monkeypatch.setenv("KAJIBA_EXPERIMENT", "1")` and `monkeypatch.setattr(...)` to point
`EXPERIMENTS_DIR`/`STAGING_DIR` at `tmp_path`. The store module is Click-free; isolate by patching
`experiment_store.EXPERIMENTS_DIR` (and the collector's imported `EXPERIMENTS_DIR`/`STAGING_DIR`).

**Six tests to write** (RESEARCH Requirements→Test Map):
1. `test_opted_in_session_writes_one_record` — N turn-scoped ends → exactly ONE record (finalize-once).
2. `test_flag_absent_unchanged_coding_path` — flag absent → `session_*.json` in STAGING_DIR, EXPERIMENTS_DIR untouched (no-regression).
3. `test_structural_parity_with_deliberate_log` — compare `model_dump(by_alias=True)` keys vs a direct `build_experiment_record` shape (allow populated `trajectory` + `eval_score==0.0`).
4. `test_field_mapping` — `task_description`==first user, `local_model_output`==last gpt, `eval_score==0.0`, `experiment.local_model`==captured metadata, `trajectory` populated.
5. `test_no_staging_or_outbox_in_experiment_mode` — even with `contribution_mode=="continuous"`, never writes STAGING_DIR/OUTBOX_DIR (D-08).
6. `test_zero_turn_session_writes_nothing` — zero-turn / interrupted end → no malformed record (Pitfall 3).

## Shared Patterns

### Fault-tolerant hooks (apply to every new/edited collector method)
**Source:** `src/kajiba/collector.py:617, 691-692` (and every handler in the module).
Every public collector method wraps its body in `try/except Exception` → `logger.exception(...)` and
NEVER propagates to Hermes. The experiment finalize lives inside `on_session_end`'s existing guard;
keep it that way.
```python
try:
    ...  # experiment branch + coding path
except Exception:
    logger.exception("Error in on_session_end")
```

### Single experiment write path (apply to all persistence in experiment mode)
**Source:** `src/kajiba/experiment_store.py` — `update_experiment` (lines 133-223, overwrite-safe),
`log_experiment` (lines 104-130, skip-on-exists), `build_experiment_record` (lines 231-284).
**Apply to:** `_finalize_experiment` / `_build_experiment_record`. Only write target is
`EXPERIMENTS_DIR` via these functions — never STAGING_DIR/OUTBOX_DIR, never a new write function
(D-08, D-13 structural guard at `experiment_store.py:95-101` / `183-189`). SC#2 parity holds by
construction because the deliberate `kajiba experiment log` path uses the same two functions.

### Serialization convention
**Source:** `experiment_store.py:115-116, 208-209` and `collector.py:786-789`.
Records serialized via `model_dump(mode="json", by_alias=True)` → `json.dumps(..., ensure_ascii=False, indent=2)`.
`by_alias=True` is required (`ConversationTurn.from_` uses alias `"from"`). The write path already
does this; the test parity assertion should compare `model_dump(by_alias=True)` output.

### Scrub/score is a CLI step, never in a hook (D-09 hard rule)
**Source:** `collector.py:779` (`_save_to_staging` does NOT scrub — "that happens at submit/export time").
**Apply to:** the experiment finalize — store RAW. Scrub/score/review/drift run later via
`kajiba experiment scrub|score|review|drift` (Phases 12-13, already shipped). No scrubbing/scoring
in the finalize branch.

## No Analog Found

None. Every new symbol has a direct in-codebase analog (this is a pure wiring/bridge phase). No
file requires falling back to RESEARCH-only patterns.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| — | — | — | All six new symbols mapped to existing analogs above. |

## Metadata

**Analog search scope:** `src/kajiba/collector.py`, `src/kajiba/experiment_store.py`,
`src/kajiba/plugin/hooks.py`, `tests/test_collector.py`, `tests/test_experiment_store.py`
(plus `14-CONTEXT.md` / `14-RESEARCH.md` for the file list).
**Files scanned:** 5 source/test files (all referenced line ranges read and verified against current source).
**Pattern extraction date:** 2026-06-06
