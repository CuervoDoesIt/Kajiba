# Phase 12: Eval Scoring & Scrub Tuning - Research

**Researched:** 2026-06-04
**Domain:** Deterministic record scoring + field-allowlist PII scrubbing (pure Python, in-repo reuse)
**Confidence:** HIGH

## Summary

Phase 12 adds two deterministic, compute-on-read capabilities to the dual-use experiment
pipeline: (1) an **eval-specific completeness/confidence scorer** for `ExperimentRecord`, and
(2) an **experiment-aware scrub** that redacts free-text PII while preserving model-identity
and hardware fields. Both are pure Python over the **frozen Phase 10 schema** — no new
dependencies, no model calls, no schema mutation. Every answer comes from reading the actual
source (`schema.py`, `scorer.py`, `scrubber.py`, `privacy.py`, `experiment_store.py`, `cli.py`);
no external research was required because nothing new is installed.

The scorer **mirrors the structure** of `scorer.py` (`QualityResult`-shaped dataclass,
`WEIGHTS` dict, threshold bands, `compute_*` entrypoint) but uses **distinct band vocabulary**
(`complete / partial / thin`) and **eval-native sub-checks** — never the 5 coding sub-scores
(which assume `trajectory.conversations`/`tool_calls`). The scrub **reuses `scrub_text` and
`SCRUB_PATTERNS` verbatim** but applies them only to a **free-text allowlist**
(`local_model_output`, `reviewer_critique`, `task_description`, `lessons_learned`) and
**explicitly bypasses `privacy.anonymize_hardware`** so `model_hash`, model identity, and the
full `HardwareProfile` survive intact — the deliberate inverse of the community pipeline.

**Primary recommendation:** Create two new single-responsibility modules — `eval_scorer.py`
(scorer) and `experiment_scrub.py` (scrub) — mirroring the `experiment_store.py` precedent for
the divergent tail. Wire `kajiba experiment score` and `kajiba experiment scrub` subcommands
into the existing `experiment` Click group, add a confidence column to `experiment list`, and
re-export `compute_eval_confidence` + `scrub_experiment` from `kajiba/__init__.py`. Reuse
`scrub_text`/`SCRUB_PATTERNS`, the `ScrubLog` model, and the `QualityResult` *shape* — fork
nothing.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Eval confidence scoring | Domain logic (new `eval_scorer.py`) | CLI (`experiment score`) | Pure function over a loaded record; mirrors `scorer.py` placement |
| Experiment PII scrub | Domain logic (new `experiment_scrub.py`) | CLI (`experiment scrub`) + Phase 15 export | Reuses `scrub_text` engine; orchestration only |
| Free-text PII detection | Shared core (`scrubber.scrub_text`) | — | Already exists; reused verbatim, NOT forked (D-10) |
| Hardware/model preservation | Experiment scrub (allowlist) | — | Deliberate bypass of `privacy.anonymize_hardware` (D-05) |
| Record load/dispatch | Schema (`load_record`) | — | Frozen Phase 10 API routes by `record_kind` |
| Result rendering | CLI (Rich `Table`/`Panel`) | — | Matches existing `experiment list` / `preview` rendering |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib (`dataclasses`, `logging`, `json`, `pathlib`) | 3.11+ | Result types, logging, IO | Already the project baseline (CLAUDE.md) |
| Pydantic | >= 2.0 (installed) | Read `ExperimentRecord`, reuse `ScrubLog` | Frozen schema layer; reused, not extended |
| Click | >= 8.0 (installed) | `score`/`scrub` subcommands | Existing `experiment` group host |
| Rich | >= 13.0 (installed) | Per-check breakdown table, panels | Matches existing CLI rendering idiom |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest / pytest-cov | >= 7.0 / >= 4.0 (dev extra) | Tests + coverage | Validation Architecture (below) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Two new modules (`eval_scorer.py`, `experiment_scrub.py`) | `record_kind` dispatch inside `scorer.py`/`scrubber.py` | Dispatch keeps file count down but violates the locked "one module per responsibility / divergent tail" stance (D-09) and couples coding + eval logic. **Reject.** |
| New `QualityResult`-like dataclass | Reuse `scorer.QualityResult` directly | Reusing it forces gold/silver/bronze vocabulary semantics onto eval trust; D-02 explicitly forbids confusing the two. Mirror the *shape*, new type. **New type.** |

**Installation:** None. No new packages. This phase installs nothing.

**Version verification:** N/A — no external packages introduced. All dependencies
(`pydantic>=2.0`, `click>=8.0`, `rich>=13.0`) are already declared in `pyproject.toml`
[VERIFIED: D:\Kajiba\pyproject.toml lines 25-29] and present in the environment.

## Package Legitimacy Audit

**Not applicable.** Phase 12 installs **zero** external packages. All code reuses in-repo
modules and the already-installed stack. No registry verification, slopcheck, or postinstall
audit is required. [VERIFIED: pyproject.toml — no dependency changes needed]

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EEVAL-01 | An eval-specific scorer produces quality signals suited to model-output evaluation, independent of the coding-trajectory scorer | New `eval_scorer.py` mirrors `scorer.py` structure with eval-native completeness sub-checks + `complete/partial/thin` bands; reads only `ExperimentRecord` fields enumerated below. Compute-on-read via `kajiba experiment score` (D-03), never persisted (frozen schema). |
| EEVAL-02 | Scrubbing on experiment records retains model-identity and hardware fields needed for analysis while still redacting personal/PII data | New `experiment_scrub.py` reuses `scrub_text`/`SCRUB_PATTERNS` on a free-text allowlist (`local_model_output`, `reviewer_critique`, `task_description`, `lessons_learned`), preserves `model`/`hardware`/`local_model`/`reviewer_model` + `model_hash` exactly, bypasses `privacy.anonymize_hardware`. Store-raw / scrub-at-share-boundary (D-08). |
</phase_requirements>

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** The scorer is a **completeness/confidence** assessment of the eval *record*, not a re-judgment of the model output. Signals: `local_model_output` present, reviewer critique attached, `lessons_learned` captured, model + hardware metadata present, `eval_score` within range. The existing `eval_score` (Phase 10) stays the answer-quality judgment and stands *beside* the confidence result.
- **D-02:** Result is a **`QualityResult`-like dataclass**: a confidence composite (`0.0–1.0`) + **eval-native bands** (e.g. `complete / partial / thin`, or high/med/low confidence) + a per-check breakdown. **Distinct vocabulary from `gold/silver/bronze`.**
- **D-03:** **Compute-on-read** via a new `kajiba experiment score` subcommand; surface result in `kajiba experiment list`. The score is **NOT persisted** → **no change to the Phase-10-frozen `ExperimentRecord`/`ExperimentOutcome` schema**. `log_experiment` stays a pure write path.
- **D-04:** The score is **advisory / analysis-only**. Experiments never publish; it never gates anything — a filtering/triage signal for the user and Phase 15.
- **D-05:** **Preserve model identity + hardware EXACT.** Experiments **bypass `privacy.py`'s hardware anonymization** (`generalize_gpu_name`, `round_to_tier` VRAM, OS strip, cuda strip) entirely. Keep `model_name`, `model_family`, `parameter_count`, `quantization`, `provider`, `model_hash`, and all `HardwareProfile` fields intact — for both `RecordBase.model` and `experiment.local_model`/`reviewer_model`.
- **D-06:** **`model_hash` must be explicitly protected.** It is hex and the scrubber's `hex_tokens` pattern would otherwise redact it. The experiment scrub must operate on a **field allowlist/denylist**, not blindly walk every string.
- **D-07:** **Scrub ALL caller-supplied free text** through the existing `scrub_text` regex engine: `local_model_output`, `reviewer_critique`, `task_description`, and `lessons_learned`. Max-scrub default per CLAUDE.md's over-redact stance.
- **D-08:** **Store raw, scrub at the export/share boundary** (Phase 15) or via an explicit `kajiba experiment scrub` command — **NOT at log time.** Closes Phase 11's accepted-risk **AR-11-01** at the *share* boundary.
- **D-09:** New single-responsibility module(s) per the locked "shared core, divergent tail" stance. Leaning: a new eval-scorer module; experiment-aware scrub as a new function/module that **reuses `scrub_text`/`SCRUB_PATTERNS`** (do **not** fork the regex engine).
- **D-10:** **Reuse, don't rewrite.** The scrub regex engine, the `ScrubLog` accounting model, and the `QualityResult` dataclass *shape* are reused; only orchestration diverges.

### Claude's Discretion
- Exact module/file names, and whether experiment scrub lives in `scrubber.py` via `record_kind` dispatch vs a new `experiment_scrub`-style module (D-09).
- The exact set of completeness sub-checks and their weights in the confidence composite (D-01/D-02).
- Exact band labels/thresholds (`complete/partial/thin` vs high/med/low) — pick the clearest; keep distinct from gold/silver/bronze.
- Whether `experiment score` renders a Rich per-check breakdown table and whether `list` gains a confidence column.
- Whether the scrub emits a `ScrubLog` (consistent with the existing scrubber); lean yes.
- Whether the two new public functions are re-exported from `kajiba/__init__.py` (lean yes if the Phase 15 practice project needs them programmatically).

### Deferred Ideas (OUT OF SCOPE)
- **Quality-drift detection** across repeated runs → **Phase 13.** Scorer reads `drift_flag` if present but does not compute it.
- **Reviewer critique attachment** + **`lessons_learned` querying** → **Phase 13.**
- **Analysis-export format** + practice-project integration (where scrub-on-export actually fires) → **Phase 15.**
- **Persisting the computed eval score** into the schema → out of scope (compute-on-read chosen, D-03).
- **CR-01 / Phase 11 experiment-store dedup todo** (`2026-06-04-fix-experiment-relog-dedup-cr01.md`) — reviewed, NOT folded; it is store correctness, not scoring/scrubbing.
</user_constraints>

## Verified Schema Surface (Phase 10 — FROZEN, do NOT add fields)

All from `src/kajiba/schema.py` [VERIFIED: schema.py lines as noted].

### `RecordBase` (lines 265-283) — shared identity/context, inherited by both record kinds
| Field | Type | Optional | Notes |
|-------|------|----------|-------|
| `schema_version` | `str` | default `"0.2.0"` | `SCHEMA_VERSION` (line 21) |
| `record_id` | `Optional[str]` | yes | set by `compute_record_id()` |
| `submission_hash` | `Optional[str]` | yes | |
| `created_at` | `datetime` | default factory `now(UTC)` | |
| `record_kind` | `Literal["coding_session","model_experiment"]` | default `"coding_session"` | discriminator |
| `model` | `Optional[ModelMetadata]` | yes | **PRESERVE in scrub (D-05)** |
| `hardware` | `Optional[HardwareProfile]` | yes | **PRESERVE in scrub (D-05)** |
| `submission` | `Optional[SubmissionMetadata]` | yes | holds `scrub_log` |

### `ExperimentRecord(RecordBase)` (lines 432-492)
| Field | Type | Optional | Notes |
|-------|------|----------|-------|
| `record_kind` | overrides default to `"model_experiment"` | — | |
| `experiment` | `ExperimentMetadata` | **required** | |
| `outcome` | `ExperimentOutcome` | **required** | |
| `trajectory` | `Optional[Trajectory]` | yes | usually `None` for experiments |
- Methods: `compute_record_id()` → `kajiba_exp_<12hex>` (line 445); `compute_submission_hash()` → `sha256:<hex>` (line 469).

### `ExperimentMetadata` (lines 408-418)
| Field | Type | Optional | Scorer reads | Scrub action |
|-------|------|----------|--------------|--------------|
| `experiment_id` | `str` | required | — | preserve |
| `experiment_type` | `Literal[EXPERIMENT_TYPES]` | required | — | preserve |
| `local_model` | `ModelMetadata` | **required** | **completeness** | **PRESERVE (D-05)** |
| `reviewer_model` | `Optional[ModelMetadata]` | yes | completeness (bonus) | **PRESERVE (D-05)** |
| `task_category` | `str` | required | — | preserve |
| `task_description` | `str` | required | — | **SCRUB free text (D-07)** |
| `started_at` | `datetime` | required | — | preserve |
| `completed_at` | `Optional[datetime]` | yes | completeness (bonus) | preserve |

### `ExperimentOutcome` (lines 421-429)
| Field | Type | Optional | Scorer reads | Scrub action |
|-------|------|----------|--------------|--------------|
| `local_model_output` | `str` | **required** | present + non-trivial | **SCRUB free text (D-07)** |
| `reviewer_critique` | `Optional[str]` | yes | present → +confidence | **SCRUB free text (D-07)** |
| `eval_score` | `float` `Field(ge=0.0, le=1.0)` | required | always in range by schema | preserve |
| `drift_flag` | `bool` | default `False` | read-only (Phase 13 owns compute) | preserve |
| `lessons_learned` | `list[str]` | default `[]` | non-empty → +confidence | **SCRUB each element (D-07)** |
| `recommended_action` | `Optional[RecommendedActionType]` | yes | present → +confidence | preserve |

### `ModelMetadata` (lines 166-177) — **entire model PRESERVED in scrub (D-05)**
`model_name` (req `str`), `model_family`, `parameter_count`, `quantization`, `context_window`,
`context_used`, `provider` (`Literal[ProviderType]`), `is_local`, **`model_hash` (Optional[str], hex — D-06 protect)**.

### `HardwareProfile` (lines 180-190) — **entire profile PRESERVED in scrub (D-05)**
`gpu_name`, `gpu_vram_gb`, `gpu_count`, `cpu_name`, `ram_gb`, `os`, `inference_backend`, `cuda_version`.

### `ScrubLog` (lines 222-233) — **REUSE for the experiment scrub log (D-10)**
`file_paths_redacted`, `potential_names_redacted`, `api_keys_redacted`, `emails_redacted`,
`network_redacted`, `phone_redacted`, `crypto_redacted`, `connection_strings_redacted`, `items_flagged` — all `int = 0`.

### Constants
- `EXPERIMENT_TYPES = ("model_evaluation","routing_test","quality_drift","prompt_ablation")` (line 114) [VERIFIED]
- `RECOMMENDED_ACTIONS = ("use_as_is","needs_fine_tune","route_to_reviewer","discard")` (line 117) [VERIFIED]
- `load_record(data)` (line 515) routes by `record_kind` → `ExperimentRecord` for `"model_experiment"`, else `KajibaRecord` [VERIFIED]

## Architecture Patterns

### System Architecture Diagram

```
                          kajiba experiment score <id|--from>
                                      │
                                      ▼
          ┌──────────────────────────────────────────────┐
          │  CLI (cli.py, experiment group)               │
          │  load exp_<id>.json from EXPERIMENTS_DIR       │
          │  → json.loads → load_record(data)              │
          └──────────────────────────────────────────────┘
                                      │ ExperimentRecord
                ┌─────────────────────┴──────────────────────┐
                ▼                                             ▼
   ┌────────────────────────────┐            ┌──────────────────────────────┐
   │ eval_scorer.py             │            │ experiment_scrub.py            │
   │ compute_eval_confidence()  │            │ scrub_experiment()             │
   │  ├ check_output_present    │            │  ├ ALLOWLIST free-text fields: │
   │  ├ check_reviewer_critique │            │  │   local_model_output,       │
   │  ├ check_lessons_learned   │            │  │   reviewer_critique,        │
   │  ├ check_model_metadata    │            │  │   task_description,         │
   │  ├ check_hardware_present  │            │  │   lessons_learned[]         │
   │  └ check_eval_score_range  │            │  ├ for each → scrub_text() ────┼──► scrubber.scrub_text
   │  → weighted composite      │            │  │            (SCRUB_PATTERNS) │     (SHARED CORE, reused)
   │  → band (complete/partial/ │            │  ├ PRESERVE model/hardware/    │
   │     thin)                  │            │  │   local_model/reviewer_model│
   │  → EvalConfidenceResult    │            │  │   + model_hash (D-05/D-06)  │
   └────────────────────────────┘            │  ├ BYPASS privacy.anonymize_*  │
                │                             │  └ aggregate → ScrubLog        │
                ▼                             └──────────────────────────────┘
   Rich breakdown table / Panel                          │
   + confidence column in `list`             scrubbed ExperimentRecord + ScrubLog
                                              (returned to caller / Phase 15 export)
                                                          ▲
                                              kajiba experiment scrub  (NOT at log time, D-08)
```

`log_experiment` (write path) is intentionally absent from both flows — scoring and scrub never
hook into it (D-03/D-08). [VERIFIED: experiment_store.py — pure write path]

### Component Responsibilities
| File | Responsibility | New / Existing |
|------|----------------|----------------|
| `src/kajiba/eval_scorer.py` | Eval completeness/confidence scorer + result dataclass + bands | **NEW** |
| `src/kajiba/experiment_scrub.py` | Field-allowlist experiment scrub reusing `scrub_text` | **NEW** |
| `src/kajiba/cli.py` | `experiment score` / `experiment scrub` subcommands; confidence column in `list` | edit (experiment group, lines 803-976) |
| `src/kajiba/__init__.py` | Re-export `compute_eval_confidence`, `scrub_experiment` | edit (line 5) |
| `src/kajiba/scrubber.py` | `scrub_text`, `SCRUB_PATTERNS` reused **read-only** | unchanged |
| `src/kajiba/schema.py` | `ExperimentRecord`, `ScrubLog`, `load_record` reused | **FROZEN — unchanged** |

### Pattern 1: Mirror `compute_quality_score` structure with new vocabulary
**What:** Scorer module follows `scorer.py` exactly — module-level `WEIGHTS` dict + threshold
constants + `compute_*` entrypoint returning a frozen-shape dataclass — but with eval-native
checks and bands.
**When to use:** The eval scorer (EEVAL-01).
**Example (proposed, mirrors scorer.py lines 222-257):**
```python
# Source: mirrors src/kajiba/scorer.py compute_quality_score (lines 222-257)
COMPLETE_THRESHOLD = 0.80
PARTIAL_THRESHOLD = 0.50

WEIGHTS = {
    "output_present": 0.30,        # local_model_output non-empty / non-trivial
    "reviewer_critique": 0.20,     # critique attached
    "model_metadata": 0.20,        # local_model identity fields populated
    "hardware_present": 0.10,      # HardwareProfile populated
    "lessons_learned": 0.10,       # lessons captured
    "outcome_signals": 0.10,       # recommended_action + completed_at + eval_score sane
}

@dataclass
class EvalConfidenceResult:
    composite_score: float
    sub_scores: dict[str, float]
    confidence_band: str  # "complete" | "partial" | "thin"

def compute_eval_confidence(record: ExperimentRecord) -> EvalConfidenceResult:
    sub = {
        "output_present": _score_output_present(record),
        "reviewer_critique": _score_reviewer_critique(record),
        "model_metadata": _score_model_metadata(record),
        "hardware_present": _score_hardware_present(record),
        "lessons_learned": _score_lessons_learned(record),
        "outcome_signals": _score_outcome_signals(record),
    }
    composite = sum(sub[k] * WEIGHTS[k] for k in WEIGHTS)
    if composite >= COMPLETE_THRESHOLD:
        band = "complete"
    elif composite >= PARTIAL_THRESHOLD:
        band = "partial"
    else:
        band = "thin"
    return EvalConfidenceResult(
        composite_score=round(composite, 3),
        sub_scores={k: round(v, 3) for k, v in sub.items()},
        confidence_band=band,
    )
```
[ASSUMED: A1 — exact weights/thresholds are Claude's-discretion proposals, not user-locked]

### Pattern 2: Field-allowlist scrub reusing `scrub_text`, preserving model/hardware
**What:** Walk only the four free-text fields; preserve everything else; aggregate per-category
counts into a `ScrubLog`; rebuild via `model_validate`. Never call `privacy.anonymize_hardware`.
**When to use:** The experiment scrub (EEVAL-02).
**Example (proposed, mirrors scrubber.scrub_record's model_dump→scrub→validate pattern, lines 314-370):**
```python
# Source: mirrors src/kajiba/scrubber.py scrub_record (lines 314-370)
from kajiba.scrubber import scrub_text
from kajiba.schema import ExperimentRecord, ScrubLog

def scrub_experiment(record: ExperimentRecord) -> tuple[ExperimentRecord, ScrubLog]:
    data = record.model_dump(mode="json", by_alias=True)
    counts: dict[str, int] = {}
    flagged = 0

    def _apply(text: str) -> str:
        nonlocal flagged
        res = scrub_text(text)
        for cat, cnt in res.stats.items():
            counts[cat] = counts.get(cat, 0) + cnt
        flagged += len(res.flagged)
        return res.scrubbed_text

    exp = data["experiment"]
    out = data["outcome"]
    # ALLOWLIST — only these four free-text surfaces (D-07)
    exp["task_description"] = _apply(exp["task_description"])
    out["local_model_output"] = _apply(out["local_model_output"])
    if out.get("reviewer_critique"):
        out["reviewer_critique"] = _apply(out["reviewer_critique"])
    out["lessons_learned"] = [_apply(s) for s in out.get("lessons_learned", [])]
    # model, hardware, experiment.local_model, experiment.reviewer_model,
    # model_hash, eval_score, drift_flag, recommended_action — UNTOUCHED (D-05/D-06)

    scrub_log = ScrubLog(
        file_paths_redacted=counts.get("file_paths", 0),
        api_keys_redacted=counts.get("api_keys", 0) + counts.get("hex_tokens", 0),
        emails_redacted=counts.get("emails", 0),
        network_redacted=counts.get("network", 0),
        phone_redacted=counts.get("phone", 0),
        crypto_redacted=counts.get("crypto", 0),
        connection_strings_redacted=counts.get("connection_strings", 0),
        items_flagged=flagged,
    )
    return ExperimentRecord.model_validate(data), scrub_log
```

### Anti-Patterns to Avoid
- **Deep-walking every string in the record.** `scrub_record` walks the trajectory blindly;
  doing that to an experiment would feed `model_hash` (hex) to the `hex_tokens` pattern — but
  note `hex_tokens` only fires when preceded by `key|token|secret|...` (lines 87-94), so a bare
  `model_hash` value in a dict *value* would actually survive `scrub_text`. **Regardless, the
  allowlist is mandatory (D-06):** never iterate the model/hardware sub-objects. Allowlist by
  field, do not denylist by pattern.
- **Calling `privacy.anonymize_hardware` / `apply_consent_level` on experiments.** That destroys
  exactly the analysis fields EEVAL-02 preserves (D-05). Experiments bypass `privacy.py` entirely.
- **Reusing `gold/silver/bronze`** band labels for eval confidence (D-02). Use `complete/partial/thin`.
- **Persisting the score** into the record / adding a schema field (D-03, frozen schema).
- **Hooking score/scrub into `log_experiment`** (D-03/D-08 — pure write path stays pure).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PII regex detection | A second regex engine for experiments | `scrubber.scrub_text` + `SCRUB_PATTERNS` | D-10 reuse; one source of truth for PII patterns |
| Redaction accounting | A new counts dataclass | `schema.ScrubLog` | D-10; consistent with community scrub |
| Result container shape | Bespoke return tuple | `QualityResult`-shaped dataclass | D-02; mirrors `scorer.py` so callers/tests are familiar |
| Record load/dispatch | `json.loads` + manual branch | `schema.load_record(data)` | Frozen API already routes by `record_kind` |
| Atomic store reads | Re-implementing path globbing | Mirror `experiment_list` glob (`exp_*.json`, cli.py line 946) | Consistent store access |

**Key insight:** This phase is 90% orchestration over existing primitives. The only genuinely
new logic is the *set of eval-completeness checks* and *band thresholds* — everything else is
wiring already-tested code.

## Runtime State Inventory

> This is **not** a rename/refactor phase — it is additive (two new modules + CLI subcommands).
> No stored data keys, service config, OS registrations, secrets, or build artifacts are renamed
> or migrated.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — score is compute-on-read (D-03), never written; scrub output returned to caller, not persisted at log time (D-08). Existing `exp_*.json` files in `~/.hermes/kajiba/experiments/` are read-only here. | None |
| Live service config | None — no external services (core is local-only, CLAUDE.md). | None |
| OS-registered state | None. | None |
| Secrets/env vars | None — no API keys, no env config (CLAUDE.md: no `.env`, no env vars). | None |
| Build artifacts | New modules picked up automatically by `setuptools` `packages.find` (`where=["src"]`, pyproject line 52-53). Editable install already covers `src/kajiba/`. New CLI subcommands auto-register via the `@experiment.command` decorator. | Re-run `pip install -e .` only if not already editable; no egg-info rename needed. |

## Common Pitfalls

### Pitfall 1: `lessons_learned` is a `list[str]`, not a string
**What goes wrong:** Passing the whole list to `scrub_text` (which expects `str`) raises, or
silently `str()`-ifies it.
**Why it happens:** Every other free-text field is a scalar `str`.
**How to avoid:** Scrub each element (`[scrub_text(s).scrubbed_text for s in lessons]`) and
preserve list shape. Test with a multi-element fixture containing PII in one element.
**Warning signs:** `TypeError` in `scrub_text`, or a stringified list in output.

### Pitfall 2: `reviewer_critique` and `reviewer_model` are Optional
**What goes wrong:** `scrub_text(None)` / `KeyError` on absent keys; scorer crediting confidence
for a `None` critique.
**Why it happens:** `reviewer_critique: Optional[str] = None`, `reviewer_model: Optional[...] = None`.
**How to avoid:** Guard with `if out.get("reviewer_critique")`. In the scorer, treat absent
critique as 0 for that sub-check, not an error. (`scrub_text` already early-returns on falsy
input, line 242 — but `data.get(...)` may be missing the key entirely.)
**Warning signs:** Crashes on a minimal experiment (no reviewer).

### Pitfall 3: Test isolation must monkeypatch `EXPERIMENTS_DIR`
**What goes wrong:** Tests touch the real `~/.hermes/kajiba/experiments/`.
**Why it happens:** `EXPERIMENTS_DIR` is module-level in `cli.py` (line 68).
**How to avoid:** Reuse the existing `_isolate_store` pattern from `test_cli_experiment.py`
(monkeypatch `kajiba.cli.EXPERIMENTS_DIR` and `KAJIBA_BASE` to `tmp_path`). [VERIFIED:
test_cli_experiment.py lines 26-31]
**Warning signs:** Tests pollute the dev machine's store; flaky `list` counts.

### Pitfall 4: Distinguishing the eval `score` flag from the new `score` subcommand
**What goes wrong:** `experiment log --score` already exists (cli.py line 817) as the
answer-quality `eval_score` input. The new `experiment score` is a *subcommand* computing
confidence. Naming collision can confuse users.
**Why it happens:** Both legitimately use the word "score" for different concepts (D-01: they
stand beside each other).
**How to avoid:** In `score` subcommand output and `list` column, label it **"Confidence"**
(not "Score") and render `eval_score` separately. Keep the band vocabulary distinct.
**Warning signs:** Users conflate eval_score (answer quality) with confidence band (record completeness).

### Pitfall 5: `model_hash` survival is the EEVAL-02 acceptance signal
**What goes wrong:** A future "tighten the scrub" change starts walking model/hardware and nukes
`model_hash`/`gpu_name`.
**How to avoid:** A dedicated test asserting `model_hash`, `model_name`, full `HardwareProfile`,
and `local_model`/`reviewer_model` are **byte-identical** before/after scrub, while a
PII-laden `local_model_output`/`task_description` IS redacted. This is the inverse-of-community
proof (D-05/D-06).

## Code Examples

### Load an experiment record from the store (mirror `experiment_list`)
```python
# Source: src/kajiba/cli.py experiment_list (lines 941-975) + load_record (schema.py 515)
import json
from kajiba.schema import ExperimentRecord, load_record

def _load_experiment(record_id: str) -> ExperimentRecord:
    path = EXPERIMENTS_DIR / f"exp_{record_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    rec = load_record(data)
    if not isinstance(rec, ExperimentRecord):
        raise click.ClickException(f"{path.name} is not a model_experiment record.")
    return rec
```

### Render a Rich per-check breakdown (mirror existing CLI tables)
```python
# Source: mirrors src/kajiba/cli.py experiment_list Table usage (lines 954-975)
from rich.table import Table

def _render_confidence(result) -> Table:
    t = Table(title="Eval Confidence")
    t.add_column("Check"); t.add_column("Score", justify="right")
    for k, v in result.sub_scores.items():
        t.add_row(k, f"{v:.2f}")
    t.add_row("[bold]composite[/bold]", f"[bold]{result.composite_score:.2f}[/bold]")
    t.add_row("[bold]band[/bold]", f"[bold]{result.confidence_band}[/bold]")
    return t
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single `KajibaRecord` + `compute_quality_score` | `record_kind` discriminator + divergent scorer per kind | Phase 10 (schema 0.2.0) | Phase 12 adds the experiment-side scorer/scrub as the "divergent tail" |
| Scrub-at-capture (community pipeline) | Store-raw, scrub-at-share-boundary (experiments) | Phase 12 (D-08) | Raw output preserved for Phase 13 reviewer; closes AR-11-01 at export |

**Deprecated/outdated:** None. No deprecations introduced.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Proposed sub-check set + weights (output 0.30 / reviewer 0.20 / model_metadata 0.20 / hardware 0.10 / lessons 0.10 / outcome_signals 0.10) and bands (`complete` ≥0.80 / `partial` ≥0.50 / `thin`) | Pattern 1 | These are explicitly Claude's-discretion (CONTEXT.md). Planner may tune; nothing else depends on exact numbers. Low risk — advisory signal only (D-04). |
| A2 | Module names `eval_scorer.py` + `experiment_scrub.py` | Component Responsibilities | Discretion item (D-09); planner may rename. Wiring (imports, re-exports) is the only consumer. Low risk. |
| A3 | Re-export both public functions from `__init__.py` | Component Responsibilities | Discretion (lean-yes in CONTEXT.md); needed if Phase 15 practice project imports programmatically. Low risk — additive. |
| A4 | `experiment list` gains a "Confidence" column computed on read | Pitfall 4 | Discretion; if it makes `list` slow on large stores, can be opt-in (`--with-confidence`). Low risk. |

**If this table is empty:** N/A — four assumed (all discretion items, none compliance/security-critical).

## Open Questions

1. **Should `experiment scrub` write back to the store or only stdout/return?**
   - What we know: D-08 says scrub fires at the share/export boundary (Phase 15) or via the
     explicit command; store-raw is the at-rest invariant.
   - What's unclear: Whether `kajiba experiment scrub <id>` should overwrite/emit a scrubbed
     copy or just preview the redactions for the user.
   - Recommendation: Default to **preview/emit-to-stdout (or `--out FILE`)**, never overwrite the
     raw store file, to preserve the store-raw invariant (D-08) and keep the real output for
     Phase 13's reviewer. Let Phase 15 own the actual export-write.

2. **`potential_names_redacted` has no source pattern.**
   - What we know: `ScrubLog.potential_names_redacted` exists (schema line 226) but `SCRUB_PATTERNS`
     has no "names" category and `scrub_text` never sets it (name detection is the GLiNER
     `scrubber_llm` path, PRIV-01, not in scope here).
   - Recommendation: Leave `potential_names_redacted=0` in the experiment `ScrubLog` (consistent
     with `scrub_record`, which also omits it). Document that semantic name redaction is the
     Phase-7 GLiNER layer, out of scope for Phase 12's regex reuse.

## Environment Availability

> All dependencies are in-repo Python modules or the already-installed stack. No external tools,
> services, or runtimes beyond Python 3.11+ (3.13.3 on dev machine per CLAUDE.md).

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | everything | ✓ | 3.13.3 (>=3.11 req) | — |
| pydantic | read ExperimentRecord, reuse ScrubLog | ✓ | >=2.0 | — |
| click | subcommands | ✓ | >=8.0 | — |
| rich | breakdown rendering | ✓ | >=13.0 | — |
| pytest / pytest-cov | tests | ✓ (dev extra) | >=7.0 / >=4.0 | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Validation Architecture

> `workflow.nyquist_validation: true` [VERIFIED: .planning/config.json line 18].

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 7.0 (+ pytest-cov >= 4.0) [VERIFIED: pyproject.toml lines 34-37] |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths=["tests"]`, `addopts="-v"` (lines 55-57) |
| Quick run command | `python -m pytest tests/test_eval_scorer.py tests/test_experiment_scrub.py -x -q` |
| Full suite command | `python -m pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EEVAL-01 | Complete experiment → `band == "complete"`, composite high | unit | `pytest tests/test_eval_scorer.py::test_complete_experiment_scores_complete -x` | ❌ Wave 0 |
| EEVAL-01 | Thin experiment (no reviewer, no lessons, bare model) → `band == "thin"` | unit | `pytest tests/test_eval_scorer.py::test_thin_experiment_scores_thin -x` | ❌ Wave 0 |
| EEVAL-01 | Bands use `complete/partial/thin`, NEVER gold/silver/bronze | unit | `pytest tests/test_eval_scorer.py::test_band_vocabulary_distinct -x` | ❌ Wave 0 |
| EEVAL-01 | `compute_eval_confidence` rejects/ignores `KajibaRecord` (experiment-only) | unit | `pytest tests/test_eval_scorer.py::test_experiment_only -x` | ❌ Wave 0 |
| EEVAL-02 | PII in `local_model_output` + `task_description` + a `lessons_learned` element IS redacted | unit | `pytest tests/test_experiment_scrub.py::test_free_text_redacted -x` | ❌ Wave 0 |
| EEVAL-02 | `model_hash`, `model_name`, full `HardwareProfile`, `local_model`/`reviewer_model` survive BYTE-IDENTICAL | unit | `pytest tests/test_experiment_scrub.py::test_model_and_hardware_preserved -x` | ❌ Wave 0 |
| EEVAL-02 | `ScrubLog` counts match redactions; `eval_score`/`drift_flag`/`recommended_action` preserved | unit | `pytest tests/test_experiment_scrub.py::test_scrublog_and_outcome_fields -x` | ❌ Wave 0 |
| EEVAL-02 | `lessons_learned` list shape preserved (not stringified) | unit | `pytest tests/test_experiment_scrub.py::test_lessons_list_shape -x` | ❌ Wave 0 |
| EEVAL-01/02 | `kajiba experiment score <id>` and `scrub` CLI exit 0, render expected output | integration | `pytest tests/test_cli_experiment.py::test_experiment_score -x` (extend existing file) | ⚠️ extend |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_eval_scorer.py tests/test_experiment_scrub.py -x -q`
- **Per wave merge:** `python -m pytest -q` (full suite — guards the frozen schema + golden IDs)
- **Phase gate:** Full suite green before `/gsd-verify-work`. Existing `tests/test_schema_experiment.py`
  and `tests/fixtures/golden_ids.json` golden tripwire must stay green (proves schema un-mutated, D-03).

### Wave 0 Gaps
- [ ] `tests/test_eval_scorer.py` — covers EEVAL-01 (mirror `tests/test_scorer.py` structure + `_load_fixture`)
- [ ] `tests/test_experiment_scrub.py` — covers EEVAL-02 (mirror `tests/test_scrubber.py`)
- [ ] `tests/fixtures/experiment_complete.json` — fully-populated experiment (reviewer, lessons, action, model_hash, hardware)
- [ ] `tests/fixtures/experiment_thin.json` — minimal valid experiment (required fields only)
- [ ] `tests/fixtures/experiment_pii.json` — PII in `local_model_output`/`task_description`/`lessons_learned`, real `model_hash` (hex) + GPU name to prove preservation
- [ ] Extend `tests/test_cli_experiment.py` with `score`/`scrub` subcommand cases (reuse `_isolate_store`)
- [ ] Framework install: none — pytest already present (`pip install -e .[dev]` if env not set up)

## Security Domain

> `security_enforcement` key is **absent** from `.planning/config.json` → treat as enabled.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Local CLI, no auth surface |
| V3 Session Management | no | No sessions |
| V4 Access Control | no | Local filesystem only; structural store separation owned by Phase 11 (D-13 guard) |
| V5 Input Validation | yes | Pydantic schema validation on `load_record`/`model_validate`; CLI `--from` already validated via `load_record` (cli.py 884) |
| V6 Cryptography | no | `model_hash` is a content hash, not a secret; no crypto introduced |
| V7 Error Handling/Logging | yes | Use `%s` lazy logging, `logger.exception` for IO (CLAUDE.md); never log raw PII at INFO |

### Known Threat Patterns for {local CLI + PII scrub}
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| PII leak via incomplete scrub (free-text fields missed) | Information Disclosure | Allowlist ALL four free-text surfaces (D-07); test asserts redaction on each |
| Over-scrub destroying analysis fields (`model_hash`, hardware) | Tampering (data integrity) | Field allowlist, NOT pattern denylist (D-06); byte-identical preservation test |
| Raw PII at rest in store | Information Disclosure (AR-11-01) | Accepted at rest (private store, D-08); scrub fires at share boundary — Phase 12 provides the scrub, Phase 15 the export gate |
| Malformed experiment JSON via `--from` | Tampering / DoS | `load_record` + Pydantic `ValidationError`; `isinstance(rec, ExperimentRecord)` guard before processing |
| Path traversal via crafted record_id in `score <id>` | Tampering | Construct path as `EXPERIMENTS_DIR / f"exp_{record_id}.json"` and verify resolved parent == `EXPERIMENTS_DIR` (mirror D-13 store guard) before reading |

## Sources

### Primary (HIGH confidence)
- `src/kajiba/schema.py` — `ExperimentRecord`/`ExperimentMetadata`/`ExperimentOutcome`/`RecordBase`/`ModelMetadata`/`HardwareProfile`/`ScrubLog`, `load_record`, `EXPERIMENT_TYPES`, `RECOMMENDED_ACTIONS` (all line numbers verified)
- `src/kajiba/scorer.py` — `QualityResult`, `WEIGHTS`, thresholds, `compute_quality_score` (the mirror template)
- `src/kajiba/scrubber.py` — `scrub_text`, `SCRUB_PATTERNS`, `hex_tokens` behavior, `scrub_record`, `_scrub_string_fields_in_turn`, `CATEGORY_TO_LOG_FIELD`
- `src/kajiba/privacy.py` — `anonymize_hardware`, `generalize_gpu_name`, `round_to_tier`, `apply_consent_level` (what experiments SKIP)
- `src/kajiba/experiment_store.py` — `log_experiment` (pure write path), `build_experiment_record`
- `src/kajiba/cli.py` — `experiment` group, `log`/`list`, `EXPERIMENTS_DIR`, imports (lines 49-77, 803-976)
- `src/kajiba/__init__.py` — current export surface (line 5)
- `pyproject.toml`, `.planning/config.json`, `.planning/REQUIREMENTS.md` — config + requirements
- `tests/test_scorer.py`, `tests/test_cli_experiment.py`, `tests/fixtures/experiment_run.example.json` — test patterns to mirror

### Secondary (MEDIUM confidence)
- `.planning/phases/12-eval-scoring-scrub-tuning/12-CONTEXT.md` — locked decisions D-01..D-10

### Tertiary (LOW confidence)
- None. No web research performed (no external dependencies introduced).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; verified against installed `pyproject.toml`
- Architecture: HIGH — every reuse surface read directly from source with line numbers
- Pitfalls: HIGH — derived from actual field types and existing test isolation patterns
- Sub-check weights/bands: MEDIUM — proposals only (Claude's discretion, A1); advisory signal

**Research date:** 2026-06-04
**Valid until:** 2026-07-04 (stable — pure in-repo Python, frozen schema; no fast-moving deps)
