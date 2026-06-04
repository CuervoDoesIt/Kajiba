# Phase 12: Eval Scoring & Scrub Tuning - Pattern Map

**Mapped:** 2026-06-04
**Files analyzed:** 6 (2 new src modules, 2 modified src, 3 new test files + 3 fixtures)
**Analogs found:** 6 / 6 (all exact or strong role+data-flow matches)

This phase is ~90% orchestration over existing primitives. Every new file has a
close in-repo analog; nothing needs RESEARCH.md-only fallback. All excerpts below
are verified against current source with line numbers.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/kajiba/eval_scorer.py` | service (scorer) | transform (record → result dataclass) | `src/kajiba/scorer.py` | exact (mirror structure, new vocab) |
| `src/kajiba/experiment_scrub.py` | service (scrub) | transform (record → record + ScrubLog) | `src/kajiba/scrubber.py` (`scrub_record`) | exact (reuse `scrub_text`, allowlist orchestration) |
| `src/kajiba/cli.py` (MODIFIED) | route/CLI | request-response | `cli.py` `experiment` group `log`/`list` (lines 803-975) | exact (same group, same render idiom) |
| `src/kajiba/__init__.py` (MODIFIED) | config (export surface) | n/a | `__init__.py` line 5 (Phase 11 re-export) | exact |
| `tests/test_eval_scorer.py` | test | unit | `tests/test_scorer.py` | exact |
| `tests/test_experiment_scrub.py` | test | unit | `tests/test_scrubber.py` + `tests/test_scorer.py` (`_load_fixture`) | role-match |
| `tests/test_cli_experiment.py` (EXTEND) | test | integration | existing file (`_isolate_store`, lines 26-31) | exact (extend) |
| `tests/fixtures/experiment_{complete,thin,pii}.json` | fixture | data | `tests/fixtures/experiment_run.example.json` | role-match |

---

## Pattern Assignments

### `src/kajiba/eval_scorer.py` (service, transform) — EEVAL-01

**Analog:** `src/kajiba/scorer.py` — mirror the module skeleton EXACTLY; swap in
eval-native sub-checks and distinct bands. **Do NOT reuse the 5 coding sub-scores**
(they read `trajectory.conversations`/`tool_calls`). **Do NOT reuse `gold/silver/bronze`**
(D-02 — confuses training-data tier with eval trust).

**Module header + imports pattern** (`scorer.py` lines 1-14): module docstring,
`import logging`, `from dataclasses import dataclass, field`, `from typing import Optional`,
domain import, `logger = logging.getLogger(__name__)`. For the new module import
`from kajiba.schema import ExperimentRecord` instead of `KajibaRecord`.

**Constants + WEIGHTS idiom** (`scorer.py` lines 16-31) — module-level
`UPPER_SNAKE_CASE` thresholds + a `WEIGHTS` dict whose keys equal the sub-score keys:
```python
GOLD_THRESHOLD = 0.85
SILVER_THRESHOLD = 0.65
BRONZE_THRESHOLD = 0.45

WEIGHTS = {
    "coherence": 0.30,
    "tool_validity": 0.25,
    "outcome_quality": 0.20,
    "information_density": 0.15,
    "metadata_completeness": 0.10,
}
```
New module substitutes `COMPLETE_THRESHOLD`/`PARTIAL_THRESHOLD` and eval-native
`WEIGHTS` keys (proposed in RESEARCH Pattern 1: `output_present` 0.30 / `reviewer_critique`
0.20 / `model_metadata` 0.20 / `hardware_present` 0.10 / `lessons_learned` 0.10 /
`outcome_signals` 0.10 — Claude's discretion, A1, tunable).

**Result dataclass shape** (`scorer.py` lines 39-45) — mirror the *shape*, new TYPE
name + new band field (D-02 forbids reusing `QualityResult` directly):
```python
@dataclass
class QualityResult:
    """Result of quality scoring a record."""

    composite_score: float
    sub_scores: dict[str, float]
    quality_tier: str  # "gold", "silver", "bronze", "review_needed"
```
New: `EvalConfidenceResult` with `composite_score`, `sub_scores: dict[str, float]`,
`confidence_band: str  # "complete" | "partial" | "thin"`.

**Sub-score function shape** (`scorer.py` lines 53-88, 196-214) — each `score_*` /
`_score_*` takes the record, returns a `float` in `[0.0, 1.0]`, clamps with
`max(0.0, ...)` / `min(1.0, ...)`, has a Google-style docstring listing the checks.
The completeness check shape mirrors `score_metadata_completeness` (lines 196-214)
most closely — additive presence checks guarded against `Optional` fields:
```python
def score_metadata_completeness(record: KajibaRecord) -> float:
    score = 0.0
    if record.model and record.model.model_name:
        score += 0.30
    ...
    return min(1.0, score)
```
Eval sub-checks read: `outcome.local_model_output` present/non-trivial;
`outcome.reviewer_critique` present (Optional → 0, not error — Pitfall 2);
`experiment.local_model` identity fields; `record.hardware` present;
`outcome.lessons_learned` non-empty; `outcome.recommended_action`/`completed_at`
present + `eval_score` in range (always true by schema `Field(ge=0,le=1)`).

**Composite entrypoint** (`scorer.py` lines 222-257) — copy this control flow
verbatim, swapping tier→band labels:
```python
def compute_quality_score(record: KajibaRecord) -> QualityResult:
    sub_scores = {
        "coherence": score_coherence(record),
        ...
    }
    composite = sum(sub_scores[k] * WEIGHTS[k] for k in WEIGHTS)
    if composite >= GOLD_THRESHOLD:
        tier = "gold"
    elif composite >= SILVER_THRESHOLD:
        tier = "silver"
    elif composite >= BRONZE_THRESHOLD:
        tier = "bronze"
    else:
        tier = "review_needed"
    return QualityResult(
        composite_score=round(composite, 3),
        sub_scores={k: round(v, 3) for k, v in sub_scores.items()},
        quality_tier=tier,
    )
```
New entrypoint `compute_eval_confidence(record: ExperimentRecord) -> EvalConfidenceResult`
with `complete (>=0.80) / partial (>=0.50) / thin` bands. Add an experiment-only
guard (test `test_experiment_only`): treat a non-`ExperimentRecord` as an error
or `isinstance` check.

---

### `src/kajiba/experiment_scrub.py` (service, transform) — EEVAL-02

**Analog:** `src/kajiba/scrubber.py` — REUSE `scrub_text` + `SCRUB_PATTERNS`
verbatim (D-10, import them; do not fork). Mirror `scrub_record`'s
`model_dump → scrub → model_validate` envelope (lines 314-370), but replace the
blind deep-walk with a **field allowlist** (D-06/D-07).

**Imports pattern** (mirror `scrubber.py` lines 7-14): `import logging`, domain
imports, module logger. New module imports the engine, NOT a copy:
```python
from kajiba.scrubber import scrub_text
from kajiba.schema import ExperimentRecord, ScrubLog
```

**`scrub_text` contract** (`scrubber.py` lines 229-281) — already early-returns on
falsy input (line 242-243), returns `ScrubResult(scrubbed_text, redactions, flagged, stats)`.
Use `res.scrubbed_text`, `res.stats` (per-category counts), `len(res.flagged)`. Reuse as-is.

**`scrub_record` envelope to mirror** (`scrubber.py` lines 314-370) — the
`model_dump(by_alias=True) → mutate dict → ScrubLog → model_validate` pattern and the
exact `ScrubLog` field mapping (note `api_keys` + `hex_tokens` both fold into
`api_keys_redacted`, lines 357-366):
```python
    data = record.model_dump(by_alias=True)
    total_counts: dict[str, int] = {}
    total_flagged = 0
    ...
    scrub_log = ScrubLog(
        file_paths_redacted=total_counts.get("file_paths", 0),
        api_keys_redacted=total_counts.get("api_keys", 0) + total_counts.get("hex_tokens", 0),
        emails_redacted=total_counts.get("emails", 0),
        network_redacted=total_counts.get("network", 0),
        phone_redacted=total_counts.get("phone", 0),
        crypto_redacted=total_counts.get("crypto", 0),
        connection_strings_redacted=total_counts.get("connection_strings", 0),
        items_flagged=total_flagged,
    )
    scrubbed_record = KajibaRecord.model_validate(data)
    return scrubbed_record, scrub_log
```

**Per-field count-folding helper** (`scrubber.py` lines 290-299, inside
`_scrub_string_fields_in_turn`) — the canonical "scrub one string, fold stats" idiom
to lift into a local `_apply` closure:
```python
    if turn_data.get("value"):
        result = scrub_text(turn_data["value"])
        turn_data["value"] = result.scrubbed_text
        for cat, cnt in result.stats.items():
            counts[cat] = counts.get(cat, 0) + cnt
        flagged_count += len(result.flagged)
```

**Allowlist orchestration (the divergence, D-06/D-07):** apply `scrub_text` to ONLY
these four surfaces in the dumped dict:
`data["experiment"]["task_description"]`, `data["outcome"]["local_model_output"]`,
`data["outcome"]["reviewer_critique"]` (guard `if out.get("reviewer_critique")` —
Optional, Pitfall 2), and each element of `data["outcome"]["lessons_learned"]`
(`list[str]` — scrub per element, preserve list shape, Pitfall 1).
Signature: `scrub_experiment(record: ExperimentRecord) -> tuple[ExperimentRecord, ScrubLog]`,
rebuild via `ExperimentRecord.model_validate(data)`.

**PRESERVE (never touched):** `data["model"]`, `data["hardware"]`,
`experiment.local_model`, `experiment.reviewer_model`, `model_hash`, `eval_score`,
`drift_flag`, `recommended_action`. Do NOT iterate model/hardware sub-objects.

**Anti-analog — `scrub_record` deep-walk (lines 332-354):** that function blindly
walks the trajectory; copying it would feed `model_hash` to `hex_tokens`. Mirror the
*envelope* (dump/log/validate) but NOT the walk loop.

---

### `src/kajiba/cli.py` (route/CLI, MODIFIED) — EEVAL-01/02 surface

**Analog:** the existing `experiment` group (`cli.py` lines 803-975). Add
`@experiment.command("score")` and `@experiment.command("scrub")`; enrich `list`.

**Group + command decorator pattern** (lines 803-806, 941-943):
```python
@cli.group()
def experiment() -> None:
    """Log and inspect private model-experiment runs."""


@experiment.command("list")
def experiment_list() -> None:
    """List logged experiment runs from the private store (read-back)."""
```

**Store load idiom to mirror** (`experiment_list` lines 944-973) + `load_record`
routing — for `score <id>` / `scrub <id>`, build path as
`EXPERIMENTS_DIR / f"exp_{record_id}.json"`, `json.loads(path.read_text(...))`,
`rec = load_record(data)`, then `isinstance(rec, ExperimentRecord)` guard raising
`click.ClickException` (mirrors `experiment_log` lines 884-886). Add a path-traversal
check (resolve parent == `EXPERIMENTS_DIR`) per SECURITY domain.

**Existing imports to extend** (lines 49-56) — add the two new public funcs:
```python
from kajiba.scorer import compute_quality_score
from kajiba.scrubber import flag_org_domains, scrub_record
```
Add `from kajiba.eval_scorer import compute_eval_confidence` and
`from kajiba.experiment_scrub import scrub_experiment`.

**Rich table render idiom** (`experiment_list` lines 954-973) — for the per-check
breakdown (`score` subcommand) and the new `list` column:
```python
    table = Table(title="Logged Experiments")
    table.add_column("Record ID")
    table.add_column("Type")
    table.add_column("Task")
    table.add_column("Score", justify="right")
    for f in files:
        ...
        table.add_row(...)
    console.print(table)
```
Add a **"Confidence"** column to `list` (compute-on-read via `compute_eval_confidence`),
labeled distinctly from the existing `eval_score` "Score" column (Pitfall 4: do NOT
call it "Score"). `score` subcommand renders a sub-check breakdown table + composite + band.

**Flag-vs-subcommand collision (Pitfall 4):** `experiment log --score` (lines 816-822)
is the answer-quality `eval_score` input; the new `experiment score` subcommand computes
*confidence*. Keep vocabulary separate; never persist (D-03).

**Output policy (Open Q1):** `experiment scrub <id>` defaults to preview/stdout
(or `--out FILE`); never overwrite the raw store file (store-raw invariant, D-08).

---

### `src/kajiba/__init__.py` (config, MODIFIED)

**Analog:** current line 5 (Phase 11 re-export precedent):
```python
from kajiba.experiment_store import build_experiment_record, log_experiment
```
Add (A3, lean-yes for Phase 15 programmatic use):
```python
from kajiba.eval_scorer import compute_eval_confidence
from kajiba.experiment_scrub import scrub_experiment
```

---

### Tests — `tests/test_eval_scorer.py`, `tests/test_experiment_scrub.py`

**Analog:** `tests/test_scorer.py` (lines 1-44) — `_load_fixture` helper and
import-the-public-API structure:
```python
FIXTURES = Path(__file__).parent / "fixtures"

def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))
```
Load fixtures → `load_record(data)` → call `compute_eval_confidence` / `scrub_experiment`,
assert bands / preservation. Required cases per RESEARCH Test Map:
- scorer: `complete`/`thin` bands, band-vocabulary-distinct (no gold/silver/bronze),
  experiment-only guard.
- scrub: free-text redacted; `model_hash`/`model_name`/full `HardwareProfile`/
  `local_model`/`reviewer_model` BYTE-IDENTICAL (Pitfall 5 — the EEVAL-02 acceptance
  proof); `ScrubLog` counts; `lessons_learned` list shape preserved; outcome fields
  (`eval_score`/`drift_flag`/`recommended_action`) preserved.

### Tests — extend `tests/test_cli_experiment.py`

**Analog:** same file, `_isolate_store` fixture (lines 26-31) — REUSE verbatim:
```python
def _isolate_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    store = tmp_path / "experiments"
    monkeypatch.setattr("kajiba.cli.EXPERIMENTS_DIR", store)
    monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)
    return store
```
Add `test_experiment_score` / `test_experiment_scrub` invoking via `CliRunner` (assert
exit 0, expected render). Pitfall 3: must monkeypatch the module-level `EXPERIMENTS_DIR`.

### Fixtures

**Analog:** `tests/fixtures/experiment_run.example.json` (the only existing
`ExperimentRecord` fixture). Create `experiment_complete.json` (reviewer + lessons +
action + `model_hash` + hardware), `experiment_thin.json` (required fields only —
no reviewer, no lessons, bare model), `experiment_pii.json` (PII in
`local_model_output`/`task_description`/a `lessons_learned` element + real hex
`model_hash` + GPU name to prove preservation).

---

## Shared Patterns

### PII detection engine (REUSE, never fork)
**Source:** `src/kajiba/scrubber.py` `scrub_text` (lines 229-281), `SCRUB_PATTERNS`
(lines 63-119), `CATEGORY_TO_LOG_FIELD` (lines 122-131).
**Apply to:** `experiment_scrub.py` (import and call; D-10). `hex_tokens` only fires
when preceded by `key|token|secret|...` (lines 87-94), so a bare `model_hash` value
would survive `scrub_text` anyway — but the allowlist is still mandatory (D-06).

### Redaction accounting (REUSE)
**Source:** `src/kajiba/schema.py` `ScrubLog` (lines 222-233); fold idiom in
`scrubber.py` `scrub_record` (lines 357-366).
**Apply to:** `experiment_scrub.py`. Leave `potential_names_redacted=0` (no regex
source; GLiNER/`scrubber_llm` owns names — Open Q2).

### Result dataclass convention
**Source:** `src/kajiba/scorer.py` `QualityResult` (lines 39-45).
**Apply to:** `eval_scorer.py` `EvalConfidenceResult` — same shape, new type + band field.

### CLI store-load + isolation
**Source:** `cli.py` `experiment_list` (lines 941-975), `experiment_log` `isinstance`
guard (lines 884-886); `schema.load_record` routing; test `_isolate_store` (lines 26-31).
**Apply to:** new `score`/`scrub` subcommands and their tests.

### Conventions (CLAUDE.md)
`Optional[X]` typing; modern generics (`dict[str,int]`, `tuple[...]`); double quotes;
Google-style docstrings; module-level `logger = logging.getLogger(__name__)`;
`UPPER_SNAKE_CASE` constants; `%s` lazy logging, `logger.exception` for IO; never log
raw PII; one module per responsibility.

---

## Privacy Boundary — what experiments MUST SKIP (D-05)

**Source:** `src/kajiba/privacy.py` — `generalize_gpu_name` (line 73),
`round_to_tier` (line 89), `anonymize_hardware` (line 115), `apply_consent_level`
(line 189).
**Rule:** `experiment_scrub.py` must NEVER import or call any of these. They would
destroy exactly the `model_hash`/`gpu_name`/VRAM/OS analysis fields EEVAL-02 preserves.
This is the deliberate inverse of the community pipeline. A byte-identical preservation
test is the acceptance signal (Pitfall 5).

## No Analog Found

None. Every file has a close in-repo analog. No file needs RESEARCH.md-only fallback.

## Metadata

**Analog search scope:** `src/kajiba/` (scorer, scrubber, cli, __init__,
experiment_store, privacy, schema), `tests/` (test_scorer, test_cli_experiment).
**Files scanned (read):** 8 source/test files + CONTEXT.md + RESEARCH.md.
**Pattern extraction date:** 2026-06-04
