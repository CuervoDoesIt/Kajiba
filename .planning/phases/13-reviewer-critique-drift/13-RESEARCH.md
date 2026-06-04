# Phase 13: Reviewer Critique & Drift - Research

**Researched:** 2026-06-04
**Domain:** Local Python data-pipeline CLI (Pydantic v2 / Click / Rich) — in-place record mutation, queryable tagged metadata, longitudinal drift detection
**Confidence:** HIGH (all findings verified against the actual frozen source in this repo; no external dependencies introduced)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Persistence model (cross-cutting — all 3 commands)**
- **D-01: Mutate `exp_<id>.json` in place.** Reviewer-authored fields (critique, reviewer_model, recommended_action, lessons_learned) and `drift_flag` are written back into the existing record file. Safe because `ExperimentRecord.compute_record_id()` / `compute_submission_hash()` (`schema.py:445-492`) hash only experiment **identity** (experiment_id, task_description, local_model.model_name, local_model_output, started_at) and **exclude all `outcome` fields** — so the filename/ID stay stable across re-writes. No sidecar files.
- **D-02: `drift_flag` is persisted** on the record (not compute-on-read). The `drift` command computes, then writes. (Contrast with Phase 12's eval score, which stays compute-on-read.)
- **D-03: One `update_experiment()` write path** in `experiment_store.py`. All three commands (review, lessons, drift) funnel through it. In-place overwrite when identity matches (load → mutate → re-validate → atomic replace of same `exp_<id>.json`). **This closes CR-01.**

**Critique & reviewer ID (EREV-01)**
- **D-04: Critique input = file + interactive + inline.** `--from FILE` (paste a model's reply into a file), a Rich **interactive paste** prompt when no flag given, and `--critique "..."` inline. Core stays offline.
- **D-05: Reviewer identity via optional `--reviewer-model NAME`.** Builds `ModelMetadata(model_name=NAME)` into `experiment.reviewer_model`; **omitting it = human reviewer**, `reviewer_model` stays `None`.
- **D-06: `review` also captures the verdict** via optional `--action` flag → `outcome.recommended_action` (one of `use_as_is` / `needs_fine_tune` / `route_to_reviewer` / `discard`). Optional.
- **D-07: Re-review replaces.** `reviewer_critique` is a single `Optional[str]`; a new review overwrites the prior critique. No append/multi-reviewer accumulation.

**Lessons structure (EREV-02)**
- **D-08: Tagged-string convention** makes the frozen `list[str]` queryable with zero schema change: each lesson stored as `"category: lesson text"`; the category prefix is parsed on read for filtering.
- **D-09: Dedicated `kajiba experiment lessons <id>` command.** `--add "..."` (repeatable) with optional `--category X` appends lessons; **no `--add` = read mode**; `--category X` filters. Writes funnel through `update_experiment()`.
- **D-10: Free-form category strings.** No controlled vocabulary frozen; common categories suggested in `--help`.
- **D-11: Per-record + cross-record read-back.** `lessons <id>` prints one record's lessons; `lessons --category X` (no id) queries **across the whole store**; `experiment list` surfaces a lessons count/flag.

**Drift definition (EREV-03)**
- **D-12: Grouping key = `(local_model.model_name, task_category)`.**
- **D-13: Metric = `eval_score` deviation from the group baseline.**
- **D-14: Both directions, configurable threshold.** Flag regressions **and** improvements beyond a default of **0.15**, overridable via `--threshold`.
- **D-15: Store-wide scan that writes flagged records.** `kajiba experiment drift` scans the store, groups runs, computes per group, writes `drift_flag` via `update_experiment()` on affected records; prints Rich summary. Accepts `--id` to scan just one record's group. **Idempotent** — a re-run must also *clear* `drift_flag` on records that no longer meet the drift condition.

### Claude's Discretion
- Exact signature/placement of `update_experiment()` and whether review/lessons/drift share a common load→mutate→validate→write helper (lean yes).
- Whether `--from` for critique accepts both `.txt` (raw) and `.json` (a record fragment) and how each is parsed.
- Whether the drift `--threshold` default (0.15) is also readable from `~/.hermes/config.yaml` vs flag-only — lean flag-only with a named module constant.
- Exact baseline choice for D-13 (prior mean vs first run vs rolling window) and how groups with `<2` runs are handled (no drift, not flagged).
- The lesson category-prefix parse rule (delimiter, case handling, uncategorized-lesson fallback) and how `lessons --category` matches.
- Rich rendering details (drift summary table columns; lessons/critique display).
- Whether the new public funcs are re-exported from `kajiba/__init__.py` (lean yes).

### Deferred Ideas (OUT OF SCOPE)
- **Multi-reviewer history** — out of scope; `reviewer_critique` is a single string and re-review replaces (D-07).
- **Controlled lesson-category vocabulary** — deferred (D-10 chose free-form).
- **Drift threshold in `~/.hermes/config.yaml`** — flag-only for now.
- **Cross-record lessons/drift in the analysis export** → Phase 15.
- **Live-captured review/drift** (from Hermes sessions) → Phase 14.
- Analysis-**export** format + practice-project integration → Phase 15.
- **Live capture** of eval runs from Hermes sessions → Phase 14.
- Any change to the Phase-10-frozen `ExperimentRecord`/`ExperimentMetadata`/`ExperimentOutcome` schema.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EREV-01 | User (or reviewer model such as Grok) can attach a critique to an existing experiment record via `kajiba experiment review` | `review` subcommand writes `outcome.reviewer_critique` (+ optional `experiment.reviewer_model`, `outcome.recommended_action`) via `update_experiment()`; three input modes (`--critique`, `--from FILE`, Rich interactive paste). All target fields already exist in the frozen schema. See Standard Stack, Architecture Pattern 1 & 4. |
| EREV-02 | User can capture `lessons_learned` in a queryable form | `lessons` subcommand appends `"category: text"` tagged strings to the frozen `outcome.lessons_learned: list[str]`; read mode prints per-record; `--category X` filters per-record or store-wide. Parse rule in Architecture Pattern 5. |
| EREV-03 | Quality drift across repeated runs of same model+task is computed and flagged | `drift` subcommand groups records by `(local_model.model_name, task_category)`, compares each run's `outcome.eval_score` to the group prior-mean baseline, sets/clears the persisted `outcome.drift_flag` via `update_experiment()`, idempotently. Algorithm in Architecture Pattern 3. |
| CR-01 (folded) | `log_experiment` dedup-skip silently keeps stale outcome on re-log | `update_experiment()` provides an intentional in-place overwrite path for outcome-mutating writes, bypassing the `dest.exists()` early-return. See Common Pitfall 1 + Architecture Pattern 2. |
| WR-01..04 (folded) | Localized CLI/store error-handling and guard fixes | Pinpointed in "WR-01..04 Fix Locations" below. |
</phase_requirements>

## Summary

Phase 13 is a **pure local-Python feature phase** on an already-established stack (Python 3.13.3, Pydantic 2.12.5, Click 8.3.1, Rich 14.3.3, pytest 9.0.2 — all installed, no new dependencies). It adds three Click subcommands (`review`, `lessons`, `drift`) under the existing `experiment` group, plus one new write function `update_experiment()` in `experiment_store.py`, and enriches `experiment list`. **No schema fields are added** — every field this phase writes (`reviewer_critique`, `reviewer_model`, `recommended_action`, `lessons_learned`, `drift_flag`) already exists in the Phase-10-frozen `ExperimentOutcome` / `ExperimentMetadata` models.

**The central safety claim (D-01) is VERIFIED, not assumed.** I read `ExperimentRecord.compute_record_id()` (`schema.py:445-467`) and `compute_submission_hash()` (`schema.py:469-492`) directly. Both hash an identical 5-key identity payload — `experiment_id`, `task_description`, `local_model.model_name`, `local_model_output`, `started_at.isoformat()` — and **exclude every `outcome` field** (including `reviewer_critique`, `eval_score`, `drift_flag`, `lessons_learned`, `recommended_action`) **and** the metadata fields `task_category`, `reviewer_model`, and `completed_at`. Therefore mutating any reviewer-authored field or `drift_flag` and re-writing leaves `record_id` and the `exp_<id>.json` filename byte-stable. In-place mutation is provably safe.

This same property is exactly why **CR-01 is a data-loss bug**: `log_experiment` early-returns on `dest.exists()` (`experiment_store.py:86-88`), and because the filename is identity-only, a corrected re-log with a different `eval_score` silently keeps the stale file. The phase resolves this not with a `--force` flag but by giving outcome-mutating writes a first-class `update_experiment()` path that intentionally overwrites (D-03).

**Primary recommendation:** Add one private helper `_mutate_experiment(record_id, mutate_fn)` in `cli.py` that wraps `_load_experiment` → apply mutation → `update_experiment()`, and have all three subcommands call it. Add `update_experiment(record, store_dir)` to `experiment_store.py` that mirrors `log_experiment`'s atomic temp-file-replace but **skips the `dest.exists()` early-return** (always overwrites), re-computing identity to assert the filename is unchanged. Drift uses a **prior-mean baseline** (each run compared to the mean of all *other* runs in its group), skips groups with `<2` runs (never flagged), and clears flags that no longer qualify on every run (idempotent).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Load experiment by id (path-safe) | CLI helper (`_load_experiment`) | — | Already exists at `cli.py:82`; owns the path-traversal guard (T-12-10) and `isinstance` check (T-12-11). Reuse verbatim. |
| Mutate + atomically persist a record | Store (`experiment_store.update_experiment`) | — | Single write path (D-03, project rule "single write path through experiment_store.py"). Click-free, test-isolatable via `store_dir` arg. |
| Parse critique input (file/inline/interactive) | CLI (`review` subcommand) | — | Input acquisition is a UI concern; the store receives an already-built record. Offline (no network). |
| Drift algorithm (group, baseline, threshold) | Store-or-new-module compute fn | CLI (`drift` subcommand renders) | Pure function over a list of records → set of flagged ids. Mirrors `eval_scorer.py` shape but RESULT IS PERSISTED (D-02). |
| Lesson tagged-string parse/filter | CLI helper (`_parse_lesson`) | — | Pure string helper; consumed by `lessons` read/filter and `list`. |
| Re-validate after mutation | Pydantic (`ExperimentRecord.model_validate`) | — | Source-of-truth validation; never hand-roll field checks. |
| Rich rendering (tables/panels) | CLI | — | All user output via Rich (project convention; never `print()`). |

## Standard Stack

### Core
| Library | Version (verified) | Purpose | Why Standard |
|---------|--------------------|---------|--------------|
| Python | 3.13.3 | Runtime | Project floor 3.11+; uses `datetime.UTC`. `[VERIFIED: python -c sys.version]` |
| Pydantic | 2.12.5 | Schema validation / serialization | Source of truth for all records; `model_validate` / `model_dump(mode="json", by_alias=True)`. `[VERIFIED: importlib.metadata]` |
| Click | 8.3.1 | CLI framework | Existing `experiment` group; mirror `experiment_log` option idiom. `[VERIFIED: importlib.metadata]` |
| Rich | 14.3.3 | Terminal rendering | `Console`, `Table`, `Panel`, `Text` already used throughout `cli.py`. `[VERIFIED: importlib.metadata]` |
| pytest | 9.0.2 | Test runner | Existing `tests/test_*.py` suite (289 passing). `[VERIFIED: importlib.metadata]` |

### Supporting (all stdlib — already imported in the touched modules)
| Module | Purpose | When to Use |
|--------|---------|-------------|
| `json` | Read/write record dicts | Loading `--from` files; serializing in `update_experiment`. |
| `os` / `tempfile` | Atomic write (`mkstemp` + `os.replace`) | In `update_experiment`, copied from `log_experiment:95-102`. |
| `pathlib.Path` | Filesystem paths | Store globbing, file reads. |
| `statistics` (stdlib) | `mean()` for drift baseline | Group prior-mean computation in the drift algorithm. `[VERIFIED: stdlib, Python 3.13]` |
| `click.testing.CliRunner` | CLI integration tests | Mirror `test_cli_experiment.py` `_isolate_store` pattern. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `statistics.mean` | numpy / pandas | Rejected — adds a heavy dependency for a 1-line mean; violates "no external services / minimal core". Group sizes are tiny. |
| New `update_experiment` write path | `--force` flag on `log_experiment` | Rejected by D-03 — a flag is a bolt-on; the funnel is the structural CR-01 fix and the path all three commands need. |
| `drift` as compute-on-read (like eval_scorer) | persisted `drift_flag` | D-02 chose persist: drift is a longitudinal verdict worth freezing. eval_scorer stays compute-on-read by contrast. |

**Installation:** None. No `pyproject.toml` change. This phase introduces **zero new packages**, so there is no Package Legitimacy Audit and no Environment Availability gap — the entire stack is already installed and verified above.

## Architecture Patterns

### System Architecture Diagram

```
                          kajiba experiment <subcommand> <id?>
                                       │
        ┌──────────────────┬──────────┴───────────┬─────────────────────┐
        │                  │                       │                     │
   review <id>        lessons <id>            drift [--id]          list (enriched)
        │                  │                       │                     │
  acquire critique    --add? ──> append      scan EXPERIMENTS_DIR   glob exp_*.json
  (--critique |       tagged "cat: text"     glob exp_*.json        read raw dicts
   --from FILE |      to lessons_learned     │                      (no mutation)
   Rich paste)        else READ mode         group by               │
        │             (print / filter)       (model_name,           render Table +
  build reviewer_     │                        task_category)       lessons count +
  model? (D-05)       │                       │                     drift flag col
  set recommended_    │                      per group:             │
  action? (D-06)      │                       baseline = mean of    └─> Rich output
        │             │                        OTHER runs' eval_score
        │             │                       flag if |dev| > thresh (both dirs)
        │             │                       <2 runs => never flag
        │             │                       │
        └─────────────┴────── _mutate_experiment(id, fn) ──┐  (drift writes/clears
                                       │                     │   each affected record)
                                       ▼                     │
                          _load_experiment(id)  ◄────────────┘
                          (cli.py:82, path-safe, isinstance)
                                       │
                          apply mutate_fn(record)
                                       │
                          update_experiment(record, EXPERIMENTS_DIR)
                          (experiment_store.py — NEW)
                                       │
                          compute_record_id() (assert filename stable)
                          model_dump(json,by_alias) → mkstemp → os.replace
                          ── NO dest.exists() early-return (overwrites) ──
                                       │
                                       ▼
                          ~/.hermes/kajiba/experiments/exp_<id>.json
```

### Recommended Code Placement (no new module strictly required)
```
src/kajiba/
├── experiment_store.py   # ADD update_experiment(); keep log_experiment for first-log
├── cli.py                # ADD review/lessons/drift subcommands under `experiment` group
│                         #   ADD _mutate_experiment(), _parse_lesson(), _read_critique_input()
│                         #   ENRICH experiment_list (lessons count + drift col)
│                         #   FIX WR-01..04 in experiment_log + (WR-04) experiment_store guard
├── __init__.py           # RE-EXPORT update_experiment (+ compute_drift if extracted)
schema.py                 # FROZEN — DO NOT TOUCH
```
**Drift compute placement decision:** keep the drift algorithm as a **pure function** (e.g. `compute_drift(records, threshold) -> dict[str, bool]`). It can live in `experiment_store.py` (it reads the store) or a thin new `experiment_drift.py` mirroring `eval_scorer.py`. Lean: **a small new `experiment_drift.py`** (one-module-per-responsibility convention, mirrors `eval_scorer.py`), Click-free and unit-testable in isolation. This is a Claude's-discretion call — either placement is acceptable; document the choice in the plan.

### Pattern 1: Shared load→mutate→validate→write helper (resolves Discretion #1)
**What:** A single private CLI helper that all three subcommands route through.
**When to use:** Every outcome-mutating write in this phase.
```python
# Source: derived from cli.py:82 (_load_experiment) + experiment_store.py:90-105
# In cli.py:
def _mutate_experiment(record_id: str, mutate: Callable[[ExperimentRecord], None]) -> Path:
    """Load one experiment, apply an in-place mutation, re-validate, persist.

    The single CLI-side funnel for review/lessons/drift writes. Loads via the
    path-safe _load_experiment, applies the caller's mutation, then writes
    through experiment_store.update_experiment (the only write path, D-03).
    """
    record = _load_experiment(record_id)           # path-safe, isinstance-checked
    mutate(record)                                  # set critique / append lesson / set flag
    return update_experiment(record, EXPERIMENTS_DIR)
```
Note: mutating the loaded `ExperimentRecord` directly works because the models have **no `validate_assignment`** (confirmed: `model_config` on these models does not set it). To force re-validation after mutation, `update_experiment` re-runs `ExperimentRecord.model_validate(record.model_dump(...))` (see Pattern 2). For list mutation (`lessons_learned.append`), Pydantic v2 mutates the live list fine.

### Pattern 2: `update_experiment()` — the new in-place overwrite write path (D-03, fixes CR-01)
**What:** Mirror `log_experiment`'s atomic write but **always overwrite** (no dedup skip).
**When to use:** Any write that changes outcome/metadata of an existing record.
```python
# Source: experiment_store.py:49-105 (log_experiment) — the proven atomic pattern,
#          minus the dest.exists() early-return that causes CR-01.
def update_experiment(record: ExperimentRecord, store_dir: Path) -> Path:
    """Overwrite an existing experiment record in place (the outcome-mutating path).

    Unlike log_experiment (first-log, dedup-skip), this intentionally OVERWRITES
    the same exp_<id>.json. Safe because compute_record_id() hashes identity only
    (schema.py:445-467) — mutating outcome/metadata keeps the filename stable.
    Closes CR-01: a corrected eval is a first-class non-lossy write.
    """
    resolved = store_dir.resolve()
    if resolved.name != "experiments":                       # D-13 guard (see WR-04)
        raise ValueError(f"Experiment store must be 'experiments', got {resolved}")
    store_dir.mkdir(parents=True, exist_ok=True)

    # Re-validate after mutation, then re-compute identity (must be unchanged).
    record = ExperimentRecord.model_validate(record.model_dump(mode="json", by_alias=True))
    record.compute_record_id()
    record.compute_submission_hash()
    dest = store_dir / f"exp_{record.record_id}.json"

    # NO dest.exists() skip — overwrite is the whole point.
    payload = json.dumps(record.model_dump(mode="json", by_alias=True),
                         ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=store_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp_name, dest)                           # atomic, overwrite-safe
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    logger.info("Experiment updated in place: %s", dest)
    return dest
```
**Decision point for the planner:** whether `log_experiment` should *also* be changed to overwrite-on-content-difference, or stay first-log-only with `update_experiment` as the correction path. The CONTEXT D-03 framing ("giving outcome-mutating writes a path that intentionally overwrites rather than early-returning") means **CR-01 is closed by routing writes through `update_experiment`**, not necessarily by altering `log_experiment`'s dedup. Recommend: keep `log_experiment` as first-log (its dedup is still correct for *identical* re-logs), add `update_experiment` for corrections. If the planner wants belt-and-suspenders, `log_experiment` could compare full content before skipping — but that is optional given D-03's funnel.

### Pattern 3: Drift algorithm (EREV-03 / D-12..D-15) — resolves Discretion #4
**What:** Group runs, compute per-run deviation from a prior-mean baseline, flag both directions, idempotently clear.
**Baseline choice (recommended):** **prior-mean = mean of the OTHER runs in the group** (leave-one-out mean). This is symmetric, stable, and treats every run consistently regardless of insertion order (avoids the "first run can never drift / is always the anchor" asymmetry of a first-run baseline, and avoids the recency bias of a rolling window). Document `DRIFT_THRESHOLD = 0.15` as a module constant; expose `--threshold` to override (flag-only per Discretion #3 — do NOT read from config.yaml this phase).
```python
# Source: new pure function; uses statistics.mean (stdlib).
from statistics import mean

DRIFT_THRESHOLD = 0.15  # default; overridable via --threshold (flag-only, D-14)

def compute_drift(records, threshold=DRIFT_THRESHOLD):
    """Return {record_id: should_be_flagged} over all experiment records.

    Groups by (local_model.model_name, task_category). Within each group of >=2
    runs, each run's eval_score is compared to the mean of the OTHER runs
    (leave-one-out baseline). |deviation| > threshold => flagged (both directions,
    D-14). Groups with <2 runs are never flagged. Result is total over all
    records, so callers can both SET and CLEAR drift_flag idempotently (D-15).
    """
    groups = {}
    for r in records:
        key = (r.experiment.local_model.model_name, r.experiment.task_category)
        groups.setdefault(key, []).append(r)

    verdict = {}
    for key, group in groups.items():
        scores = [g.outcome.eval_score for g in group]
        for r in group:
            if len(group) < 2:                       # <2 runs: no baseline, never flag
                verdict[r.record_id] = False
                continue
            others = [g.outcome.eval_score for g in group if g.record_id != r.record_id]
            baseline = mean(others)
            verdict[r.record_id] = abs(r.outcome.eval_score - baseline) > threshold
    return verdict
```
**Idempotent set-AND-clear (D-15):** the `drift` command computes the full verdict, then for every record whose on-disk `drift_flag` differs from the verdict, calls `_mutate_experiment(id, set drift_flag = verdict)`. Records already correct are not rewritten (avoids needless disk churn and keeps the Rich summary honest about what changed). `--id` scopes the *scan* to that record's group only (still needs the whole group to compute a baseline).

**`eval_score` field confirmed:** `ExperimentOutcome.eval_score: float = Field(ge=0.0, le=1.0)` (`schema.py:426`). **`task_category` confirmed:** `ExperimentMetadata.task_category: str` (`schema.py:415`). **`local_model.model_name`:** `ExperimentMetadata.local_model: ModelMetadata` (`schema.py:413`), `.model_name` is the grouping field.

### Pattern 4: Critique input acquisition (D-04) — resolves Discretion #2
**What:** Three offline input modes for `review`, precedence `--critique` > `--from` > interactive.
```python
# Source: offline-safe; Click + Rich. No network.
def _read_critique_input(critique: Optional[str], from_path: Optional[str]) -> str:
    if critique is not None:
        return critique
    if from_path is not None:
        p = Path(from_path)
        text = p.read_text(encoding="utf-8")
        if p.suffix == ".json":
            # JSON fragment: accept {"reviewer_critique": "..."} or a raw string.
            try:
                obj = json.loads(text)
            except json.JSONDecodeError as exc:                     # WR-03 idiom
                raise click.ClickException(f"Malformed JSON in {from_path}: {exc}")
            return obj.get("reviewer_critique", text) if isinstance(obj, dict) else str(obj)
        return text                                                 # .txt / raw: whole file
    # Interactive multi-line paste (offline). End with EOF (Ctrl-D / Ctrl-Z+Enter).
    console.print("[dim]Paste critique; finish with Ctrl-D (Unix) / Ctrl-Z then Enter (Windows):[/dim]")
    return sys.stdin.read().strip()
```
**Interactive multi-line paste idiom (offline, cross-platform):** `sys.stdin.read()` reads until EOF — the cleanest offline multi-line capture and it is `CliRunner`-testable (pass the whole blob as `input=`). `click.edit()` is an alternative but opens an external editor (less predictable in tests and on a headless box) — recommend `sys.stdin.read()`. `Prompt.ask` (Rich) is single-line only, so not suitable for pasted multi-paragraph critiques.
**`--from` accepts both `.txt` and `.json`** (recommended answer to Discretion #2): `.json` parses a `{"reviewer_critique": ...}` fragment (or a bare JSON string); anything else is treated as raw text. Dispatch on suffix.

### Pattern 5: Lesson tagged-string parse rule (D-08/D-10) — resolves Discretion #5
**What:** Store/parse `"category: lesson text"`; filter by category.
```python
# Source: new pure helper.
UNCATEGORIZED = "uncategorized"

def _parse_lesson(lesson: str) -> tuple[str, str]:
    """Split a tagged lesson into (category, text). Delimiter is the FIRST ':'.

    'prompting: needs explicit output format' -> ('prompting', 'needs explicit output format')
    'just a free note'                        -> ('uncategorized', 'just a free note')
    Category is lowercased + stripped for case-insensitive filtering (D-10 free-form).
    """
    if ":" in lesson:
        cat, _, text = lesson.partition(":")
        return cat.strip().lower(), text.strip()
    return UNCATEGORIZED, lesson.strip()
```
**Rules (recommended):** delimiter = the **first** `:` (use `str.partition`, not `split`, so colons in the lesson text survive); category **lowercased + stripped** for case-insensitive matching; a lesson with no `:` falls back to `uncategorized`. When `--add --category X`, store `f"{X}: {text}"`. `lessons --category X` matches `_parse_lesson(l)[0] == X.strip().lower()`. Cross-store filter globs `exp_*.json`, loads each via `load_record`, and collects matching lessons grouped by record id.

### Pattern 6: Reviewer identity + verdict (D-05/D-06)
```python
# review subcommand mutation, inside _mutate_experiment's callback:
def _apply_review(rec):
    rec.outcome.reviewer_critique = critique_text          # D-07 replace, single str
    if reviewer_model:                                     # D-05 optional model id
        rec.experiment.reviewer_model = ModelMetadata(model_name=reviewer_model)
    if action:                                             # D-06 optional verdict
        rec.outcome.recommended_action = action            # Choice-validated vocab
```
`--action` should use `click.Choice(list(RECOMMENDED_ACTIONS))` (`schema.py:117`) so an invalid verdict is rejected at the CLI boundary, mirroring `--type` for `experiment_log`.

### Anti-Patterns to Avoid
- **Adding schema fields.** Frozen. The tagged-string convention (D-08) exists specifically to avoid a new lessons model.
- **Writing files directly from `cli.py`.** Project rule + D-03: the CLI never writes `exp_*.json`; it funnels through `experiment_store`. `experiment_list` only *reads*.
- **Stringifying `lessons_learned`.** It is `list[str]`; append per-element, never join into one string (mirrors `experiment_scrub.py` Pitfall 1).
- **Reusing `validate_record` for experiment records.** Use `load_record` (record_kind dispatch) — `validate_record` forces `KajibaRecord` and raises (this is exactly WR-02 and Phase 11 Pitfall 1).
- **Mutating then forgetting to re-validate.** Re-validate via `model_validate` before persisting (project pattern: "re-validate after mutation before writing").
- **Computing drift on a group of 1.** No baseline exists; never flag (D-15 / Discretion #4).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic file overwrite | Custom write-then-rename with manual cleanup | Copy `log_experiment`'s `mkstemp`+`os.replace`+`BaseException` cleanup (`experiment_store.py:95-102`) | Already proven cross-platform (Windows + POSIX), already tested (`test_atomic_write`). |
| Record identity / dedup key | New hashing | `record.compute_record_id()` / `compute_submission_hash()` (frozen, `schema.py:445-492`) | Frozen contract; golden-ID tripwire (`test_schema_backcompat.py`) guards it. |
| Field validation after mutation | Manual `if`-checks on eval_score range, action vocab | `ExperimentRecord.model_validate(...)` | Pydantic v2 enforces `ge=0/le=1`, the `RecommendedActionType` Literal, etc. |
| Record loading by id | New file resolver | `_load_experiment(record_id)` (`cli.py:82`) | Has the path-traversal guard (T-12-10) + `isinstance` check (T-12-11). Reuse, don't reinvent. |
| Mean for drift baseline | Manual `sum()/len()` | `statistics.mean` | Stdlib, handles float precision, reads clearly. |
| First-`:` split | `str.split(":")` (loses colons in text) | `str.partition(":")` | partition keeps the remainder intact. |
| PII scrub of critique/lessons | New scrub call here | Nothing — already handled at the Phase-15 share boundary | `experiment_scrub.py:82-93` already scrubs `reviewer_critique` and each `lessons_learned` element; store-raw is the rule (D-08, AR-11-01). **No scrub change in this phase.** |

**Key insight:** This phase is almost entirely *composition of existing, tested primitives*. The only genuinely new logic is the drift algorithm and the lesson parse rule — both small, pure, and trivially unit-testable.

## Runtime State Inventory

> This is a refactor-adjacent phase (it changes how records are written and fixes a data-loss bug), so a state inventory is warranted.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Existing `~/.hermes/kajiba/experiments/exp_*.json` records written by Phase 11/12. These have `drift_flag: false`, empty `lessons_learned`, `reviewer_critique: null` by default. | None — new fields write into existing optional fields; existing records remain valid. The first `drift` run may legitimately set/clear `drift_flag` on them (D-15). |
| Live service config | None — purely local filesystem pipeline, no external services, no network. | None. Verified: CLAUDE.md "No external services for core". |
| OS-registered state | None — no scheduled tasks, daemons, or registered hooks for the experiment store. | None. |
| Secrets/env vars | None — no env vars required for core operation (CLAUDE.md: "No environment variables required"). Drift threshold is flag-only (Discretion #3). | None. |
| Build artifacts | Editable install (`.venv/`); adding `update_experiment` to `experiment_store.py` and re-exporting from `__init__.py` requires no reinstall (editable). | None — editable install picks up source changes. |

**Critical correctness note (the canonical question — "after every file is updated, what runtime state still holds the old behavior?"):** The CR-01 bug means any record previously re-logged with a correction currently holds a **stale outcome on disk**. After Phase 13, `update_experiment` fixes the *write path*, but **already-corrupted records are not auto-healed** — a user must re-run the correction through `review`/`log`. The plan should note this in the CR-01 task's verification (it is a code fix, not a data migration; no existing record is known-corrupted in this single-user dev store, but the path is now safe).

## Common Pitfalls

### Pitfall 1: CR-01 — the identity-only dedup silently keeps stale outcomes
**What goes wrong:** `log_experiment` returns early on `dest.exists()` (`experiment_store.py:86-88`). Because the filename is `exp_<record_id>.json` and `record_id` hashes identity only, a re-log with a corrected `eval_score`/critique writes nothing and prints a misleading "identical content" INFO.
**Why it happens:** D-01's identity-only hashing (the very property that makes in-place mutation safe) makes content-blind dedup lossy for corrections.
**How to avoid:** Route all outcome-mutating writes through `update_experiment` (no `dest.exists()` skip). Verify with a test that logs, then updates with a new score, then asserts the on-disk score changed and exactly one file exists.
**Warning signs:** A re-run that should change a value leaves the file byte-identical; an "already logged (identical content)" log line on a write you expected to change something.

### Pitfall 2: Using `validate_record` instead of `load_record` for experiment data (WR-02)
**What goes wrong:** `validate_record(data)` forces `KajibaRecord.model_validate` and raises an ugly `ValidationError` on experiment dicts (especially `--from` files missing `record_kind`).
**Why it happens:** Two entry points exist; only `load_record` dispatches on `record_kind` (`schema.py:515-535`).
**How to avoid:** Always `load_record` then `isinstance(rec, ExperimentRecord)` (the established `_load_experiment` idiom). For `--from` files missing `record_kind`, either default-inject `record_kind="model_experiment"` into the raw dict before load, or catch `ValidationError` and raise a friendly `ClickException` (WR-02 fix).
**Warning signs:** Raw Pydantic traceback instead of a one-line Rich error.

### Pitfall 3: Mutation without re-validation persists invalid data
**What goes wrong:** Setting `outcome.recommended_action` to a bad string or appending a non-string lesson and writing without re-validation would persist invalid JSON (the models lack `validate_assignment`).
**Why it happens:** Pydantic v2 does not validate attribute assignment unless `validate_assignment=True` is configured (it is not, on these models).
**How to avoid:** `update_experiment` re-runs `ExperimentRecord.model_validate(record.model_dump(...))` before writing. Also gate `--action` with `click.Choice(RECOMMENDED_ACTIONS)` at the CLI boundary.
**Warning signs:** An out-of-vocab action or a malformed lesson survives to disk.

### Pitfall 4: Drift flag not cleared on re-run (non-idempotent)
**What goes wrong:** If `drift` only *sets* flags, a record that drifted once stays flagged forever even after later runs bring it back in line.
**Why it happens:** Treating drift as append-only rather than as a recomputed verdict.
**How to avoid:** Compute the full verdict over the group and write `drift_flag = verdict[id]` for *every* record whose flag differs — set **and** clear (D-15). Test: flag a record, add runs that normalize it, re-run drift, assert the flag cleared.
**Warning signs:** A second `drift` run leaves a stale `true` on a now-consistent record.

### Pitfall 5: WR-04 weak D-13 guard (leaf-name only)
**What goes wrong:** The guard checks only `resolved.name == "experiments"`, so any `.../something/experiments` path passes — privacy claim weaker than the docstring.
**Why it happens:** Leaf-name check instead of an under-`KAJIBA_BASE` check.
**How to avoid:** Tighten to `resolved == EXPERIMENTS_DIR.resolve()` or `resolved.is_relative_to(KAJIBA_BASE)`. Apply the **same** tightened guard to the new `update_experiment`. (Latent, not exploited — CLI always passes the real dir — but sweep it while editing the file.)
**Warning signs:** A test pointing the store at a same-named dir outside `~/.hermes/kajiba` succeeds.

### Pitfall 6: `experiment list` enrichment crashing on a bad file
**What goes wrong:** Adding a lessons-count / drift column that loads each record could throw on one malformed file and abort the whole listing.
**Why it happens:** Listing currently uses lightweight `json.loads` with a per-file try/except `continue` (`cli.py:1015-1020`).
**How to avoid:** Keep per-file guards; read `lessons_learned`/`drift_flag` straight from the raw dict (no full validation needed for display), `continue` on error — mirror the existing loop.
**Warning signs:** One corrupt file blanks the entire table.

## WR-01..04 Fix Locations (folded scope — pinpointed)

| ID | Defect | Exact location | Fix |
|----|--------|----------------|-----|
| **CR-01** | dedup-skip keeps stale outcome on re-log | `experiment_store.py:86-88` (`if dest.exists(): return dest`) | Add `update_experiment()` (no skip) and route review/lessons/drift through it (D-03). |
| **WR-01** | `--score 0.5` alone (partial scalar flags, no `--from`) silently falls through to interactive and discards the flag | `cli.py:939-943` (the `elif eval_score is not None and experiment_type is not None and task_category is not None:` branch — requires *all three*) | When *some but not all* required scalars are supplied (and no `--from`), raise a `ClickException` telling the user which flags are missing, instead of dropping into interactive. |
| **WR-02** | `--from` file missing `record_kind` routes to `KajibaRecord` → uncaught `ValidationError` before the friendly `isinstance` error | `cli.py:935` (`rec = load_record(data)`) — relies on `data.get("record_kind", "coding_session")` in `load_record` (`schema.py:532`) | Default-inject `data.setdefault("record_kind", "model_experiment")` before `load_record`, OR wrap `load_record` in try/except → `ClickException`. |
| **WR-03** | Malformed `--from` / `--local-model` JSON surfaces a raw `JSONDecodeError` traceback | `cli.py:917` (`json.loads(Path(model_json)...)`) and `cli.py:921` (`json.loads(Path(from_path)...)`) | Wrap each `json.loads` in try/except `json.JSONDecodeError` → `click.ClickException(f"Malformed JSON in {path}: {exc}")`. Apply the same to the new `review --from .json` path. |
| **WR-04** | D-13 guard checks only leaf name `experiments`, not under `KAJIBA_BASE` | `experiment_store.py:72-76` (`if resolved.name != "experiments":`) | Tighten to `resolved.is_relative_to(KAJIBA_BASE)` (import the base) or `resolved == EXPERIMENTS_DIR.resolve()`; replicate in `update_experiment`. |

## Code Examples

### Enriching `experiment list` (read-only, raw-dict, per-file guarded)
```python
# Source: cli.py:1015-1039 — extend the existing guarded loop.
outcome = data.get("outcome", {})
lessons = outcome.get("lessons_learned", [])
drift = "⚠" if outcome.get("drift_flag") else ""
table.add_row(
    str(data.get("record_id", "")),
    str(experiment_meta.get("experiment_type", "")),
    str(experiment_meta.get("task_category", "")),
    str(outcome.get("eval_score", "")),
    band,
    str(len(lessons)),   # NEW: lessons count
    drift,               # NEW: drift flag column
)
```

### Cross-store lessons query (`lessons --category X`, no id)
```python
# Source: mirrors experiment_list's glob + per-file json.loads guard.
EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
for f in sorted(EXPERIMENTS_DIR.glob("exp_*.json")):
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        continue
    for lesson in data.get("outcome", {}).get("lessons_learned", []):
        cat, text = _parse_lesson(lesson)
        if category is None or cat == category.strip().lower():
            console.print(f"[cyan]{data.get('record_id','')}[/cyan] [{cat}] {text}")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `log_experiment` dedup-skips on `dest.exists()` (lossy for corrections) | `update_experiment()` intentional in-place overwrite for outcome-mutating writes | This phase (D-03) | CR-01 closed; corrections become first-class. |
| eval_score = compute-on-read, never persisted (Phase 12) | drift_flag = computed then **persisted** (D-02) | This phase | Deliberate split: derived confidence stays ephemeral; longitudinal verdict is frozen. |
| `click.__version__` attribute | `importlib.metadata.version("click")` | Click 8.3+ | Cosmetic; not used in this phase's code. No action. |

**Deprecated/outdated:** None affecting this phase. (Click 8.3.1 deprecation of `click.__version__` is unrelated to anything written here.)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Leave-one-out prior-mean is the best baseline for D-13 | Pattern 3 | LOW — Discretion #4 explicitly delegates baseline choice; first-run or rolling-window are valid alternatives the planner may pick. Algorithm structure (group/threshold/idempotent clear) is unaffected. |
| A2 | `sys.stdin.read()` is the cleanest offline multi-line paste idiom | Pattern 4 | LOW — `click.edit()` is a valid alternative; `sys.stdin.read()` is simpler to test. Either satisfies D-04. |
| A3 | New drift logic belongs in a small `experiment_drift.py` (vs inline in `experiment_store.py`) | Code Placement | LOW — pure organizational; Discretion. Both honor "single write path" since the write still goes through `update_experiment`. |
| A4 | `--from .json` should parse a `{"reviewer_critique": ...}` fragment | Pattern 4 | LOW — Discretion #2 asks exactly this; raw `.txt` is the simpler always-works path. |
| A5 | Keep `log_experiment`'s dedup as-is (first-log only); CR-01 closed via the funnel | Pattern 2 | MEDIUM — if the planner expects `log_experiment` itself to overwrite-on-difference, the CR-01 test must target whichever path. D-03 wording supports the funnel approach; confirm in planning. |

**All other claims in this research are `[VERIFIED]` against the repo source (file:line cited) or `[VERIFIED]` against installed package versions.**

## Open Questions

1. **Should `log_experiment` change at all, or only `update_experiment` be added?**
   - What we know: D-03 says route outcome-mutating writes through a new path; CR-01 is "resolved by routing through `update_experiment`".
   - What's unclear: whether the planner also wants `log_experiment` to detect content-difference and overwrite (defense in depth).
   - Recommendation: Add `update_experiment`; leave `log_experiment` first-log-only. Note the choice explicitly so the CR-01 regression test targets the right path. (A5)

2. **`--id` drift scope semantics.**
   - What we know: D-15 says `--id` scans "just one record's group".
   - What's unclear: whether `--id` writes only that one record's flag or the whole group's flags (the baseline needs the whole group regardless).
   - Recommendation: compute over the whole group; write/clear flags for **all** records in that group (consistent verdict), and Rich-summarize what changed. Confirm in planning.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | everything | ✓ | 3.13.3 | — |
| Pydantic | schema validation | ✓ | 2.12.5 | — |
| Click | CLI | ✓ | 8.3.1 | — |
| Rich | rendering | ✓ | 14.3.3 | — |
| pytest | tests | ✓ | 9.0.2 | — |
| `statistics` (stdlib) | drift mean | ✓ | stdlib | manual `sum/len` (not needed) |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None. This phase adds **zero** external packages — no `pyproject.toml` change, no Package Legitimacy Audit required.

## Validation Architecture

> Nyquist validation is enabled for this project (no `nyquist_validation: false` in config). This section is REQUIRED and feeds `13-VALIDATION.md`.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 (+ `click.testing.CliRunner` for CLI) |
| Config file | `pyproject.toml` `[tool.pytest...]` (no separate `pytest.ini`); tests under `tests/` |
| Quick run command | `python -m pytest tests/test_experiment_store.py tests/test_cli_experiment.py -x -q` |
| Full suite command | `python -m pytest -q` (current baseline: 289 passed, 2 pre-existing yaml-soft-dep skips, 0 regressions — must stay green) |
| Store isolation idiom | `_isolate_store(tmp_path, monkeypatch)` (`test_cli_experiment.py:28`) for CLI tests; pass `tmp_path/"experiments"` directly to store fns for unit tests. **Never touch real `~/.hermes`.** |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CR-01 | `update_experiment` overwrites in place; corrected score persists; exactly one file; record_id unchanged | unit | `pytest tests/test_experiment_store.py -k update` | ❌ Wave 0 (extend file) |
| CR-01 | `update_experiment` preserves identity (record_id/filename byte-stable across mutation) | unit | `pytest tests/test_experiment_store.py -k identity_stable` | ❌ Wave 0 |
| EREV-01 | `experiment review <id> --critique "..."` sets `reviewer_critique`; re-review replaces (D-07) | integration | `pytest tests/test_cli_experiment.py -k review` | ❌ Wave 0 (extend file) |
| EREV-01 | `--reviewer-model NAME` sets `reviewer_model`; omitting leaves it `None` (D-05) | integration | `pytest tests/test_cli_experiment.py -k reviewer_model` | ❌ Wave 0 |
| EREV-01 | `--action` validated against `RECOMMENDED_ACTIONS`; bad value rejected (D-06) | integration | `pytest tests/test_cli_experiment.py -k review_action` | ❌ Wave 0 |
| EREV-01 | `--from .txt` (raw) and `--from .json` (fragment) input modes (D-04) | integration | `pytest tests/test_cli_experiment.py -k review_from` | ❌ Wave 0 |
| EREV-01 | interactive paste via stdin (offline, CliRunner `input=`) | integration | `pytest tests/test_cli_experiment.py -k review_interactive` | ❌ Wave 0 |
| EREV-02 | `lessons <id> --add --category X` appends `"x: text"`; read mode prints; `--category` filters | integration | `pytest tests/test_cli_experiment.py -k lessons` | ❌ Wave 0 |
| EREV-02 | `_parse_lesson` rule: first-`:` split, lowercase category, uncategorized fallback, colon-in-text preserved | unit | `pytest tests/test_cli_experiment.py -k parse_lesson` (or a helper test) | ❌ Wave 0 |
| EREV-02 | `lessons --category X` (no id) queries store-wide (D-11) | integration | `pytest tests/test_cli_experiment.py -k lessons_crossrecord` | ❌ Wave 0 |
| EREV-03 | `compute_drift` flags both directions beyond threshold; <2-run groups never flagged | unit | `pytest tests/test_experiment_drift.py` (new file) | ❌ Wave 0 (new file) |
| EREV-03 | `experiment drift` persists `drift_flag` AND clears it idempotently on re-run (D-15) | integration | `pytest tests/test_cli_experiment.py -k drift_idempotent` | ❌ Wave 0 |
| EREV-03 | `--threshold` override changes flagging; default = `DRIFT_THRESHOLD` (0.15) | unit | `pytest tests/test_experiment_drift.py -k threshold` | ❌ Wave 0 |
| WR-01 | partial scalar flags (no `--from`) raise a clear error, do NOT silently go interactive | integration | `pytest tests/test_cli_experiment.py -k partial_flags` | ❌ Wave 0 |
| WR-02 | `--from` missing `record_kind` → friendly ClickException (no raw ValidationError) | integration | `pytest tests/test_cli_experiment.py -k missing_record_kind` | ❌ Wave 0 |
| WR-03 | malformed `--from`/`--local-model` JSON → Rich ClickException (no traceback) | integration | `pytest tests/test_cli_experiment.py -k malformed_json` | ❌ Wave 0 |
| WR-04 | tightened D-13 guard rejects same-named dir outside `KAJIBA_BASE` | unit | `pytest tests/test_experiment_store.py -k guard` | ❌ Wave 0 (extend) |
| regression | full suite stays green (no schema drift; golden-ID tripwire intact) | suite | `python -m pytest -q && git diff --quiet src/kajiba/schema.py` | ✅ exists (`test_schema_backcompat.py`) |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_experiment_store.py tests/test_cli_experiment.py tests/test_experiment_drift.py -x -q`
- **Per wave merge:** `python -m pytest -q` (full suite green)
- **Phase gate:** Full suite green + `git diff --quiet src/kajiba/schema.py` exits 0 (schema untouched) before `/gsd-verify-work`.

### Edge Cases (must each have a test)
- Re-review replaces (not appends) the single `reviewer_critique` string (D-07).
- Idempotent drift clear: flag set, then group normalizes, re-run clears it (D-15 / Pitfall 4).
- `<2`-run group: never flagged, no crash on `mean([])` (guard before computing baseline).
- Uncategorized lesson (no `:`) → `uncategorized`; lesson text containing `:` keeps the trailing colons.
- CR-01 overwrite: corrected `eval_score` persists; exactly one file; `record_id` unchanged.
- WR-04 guard: store dir named `experiments` but outside `~/.hermes/kajiba` is rejected.
- `experiment list` does not crash on one malformed file (per-file `continue`).

### Wave 0 Gaps
- [ ] Extend `tests/test_experiment_store.py` — `update_experiment` overwrite, identity-stable, tightened guard (CR-01, WR-04).
- [ ] Extend `tests/test_cli_experiment.py` — review (3 input modes + reviewer-model + action + re-review), lessons (add/read/filter/cross-record), drift (persist + idempotent clear), WR-01/02/03 error paths. Reuse `_isolate_store` verbatim.
- [ ] New `tests/test_experiment_drift.py` — pure `compute_drift` unit tests (both directions, <2-run, threshold, leave-one-out baseline). Build records via the `_make_record` helper pattern from `test_experiment_store.py:27`.
- [ ] No new fixtures strictly required (build records in-test), but a small multi-run fixture set for drift grouping may improve readability — optional.
- [ ] Framework install: none — pytest 9.0.2 already present.

*"Enough validation" = every requirement row above has a passing automated test, all edge cases covered, full suite green with zero regressions, and `schema.py` provably untouched.*

## Sources

### Primary (HIGH confidence — read directly this session)
- `src/kajiba/schema.py:100-118, 408-492, 500-535` — frozen vocab, `ExperimentMetadata`/`ExperimentOutcome`/`ExperimentRecord`, `compute_record_id`/`compute_submission_hash` (D-01 proof), `load_record` dispatch.
- `src/kajiba/experiment_store.py:1-167` — `log_experiment` atomic write + CR-01 dedup site (`:86-88`), D-13 guard (`:71-76`), `build_experiment_record`.
- `src/kajiba/cli.py:49-128, 854-1082` — imports, `_load_experiment` (`:82`), `experiment` group, `experiment_log` (`:894`) input branches + WR fix sites, `experiment_list`/`experiment_score`.
- `src/kajiba/experiment_scrub.py:1-117` — confirms `reviewer_critique` + `lessons_learned` already scrubbed (no scrub change this phase).
- `src/kajiba/__init__.py:1-7` — re-export pattern (lean: add `update_experiment`).
- `tests/test_experiment_store.py:1-112`, `tests/test_cli_experiment.py:1-90` — isolation idioms (`_isolate_store`, `_make_record`), dedup/atomic test patterns.
- `.planning/phases/13-reviewer-critique-drift/13-CONTEXT.md` — all 15 locked decisions + folded CR-01/WR-01..04.
- `.planning/REQUIREMENTS.md` — EREV-01/02/03 wording + traceability.
- `.planning/todos/pending/2026-06-04-fix-experiment-relog-dedup-cr01.md` — CR-01 + WR-01..04 exact symptoms.
- Installed versions via `importlib.metadata` — Python 3.13.3, Pydantic 2.12.5, Click 8.3.1, Rich 14.3.3, pytest 9.0.2.

### Secondary (MEDIUM)
- `.planning/STATE.md` Accumulated Context (Phase 10/11/12 decision log) — confirms frozen-schema rule, single-write-path rule, compute-on-read vs persist split.

### Tertiary (LOW)
- None. No external/web sources were needed; this is an internal-stack composition phase.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified on the dev machine; zero new deps.
- Architecture: HIGH — every integration point read at file:line; D-01 safety proven from source, not assumed.
- Pitfalls: HIGH — CR-01/WR-01..04 located exactly in source; idempotency/validation pitfalls derived from the actual model config and existing tests.
- Drift baseline choice: MEDIUM — explicitly a Discretion item (A1); algorithm shape is HIGH, the specific baseline is a recommendation.

**Research date:** 2026-06-04
**Valid until:** 2026-07-04 (stable internal stack; no fast-moving external dependencies). Re-verify only if `schema.py` or `experiment_store.py` change before planning.
