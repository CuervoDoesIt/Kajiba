# Phase 10: Experiment Schema Foundation - Research

**Researched:** 2026-06-03
**Domain:** Pydantic v2 schema refactor (base-class extraction, discriminated record families, content-hash stability)
**Confidence:** HIGH (every key claim verified by running the project's real code against `pydantic 2.12.5` / `Python 3.13.3`)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** All new models (`RecordBase`, `ExperimentRecord`, `ExperimentMetadata`, `ExperimentOutcome`) live in the existing `src/kajiba/schema.py`. Do NOT create a separate experiment schema module.
- **D-02:** The shared base model is named **`RecordBase`**. `KajibaRecord(RecordBase)` and `ExperimentRecord(RecordBase)`.
- **D-03:** `RecordBase` holds `schema_version`, `record_id`, `submission_hash`, `created_at`, `record_kind`, `model` (`ModelMetadata`), `hardware` (`HardwareProfile`), `submission` (`SubmissionMetadata`). `record_type` and `quality` stay on `KajibaRecord`. `ConversationTurn` untouched.
- **D-04:** `ExperimentRecord.compute_record_id()` hashes experiment identity = `experiment_id` + `task_description` + `local_model.model_name` + `outcome.local_model_output` + `started_at`, using the same `json.dumps(..., sort_keys=True, ensure_ascii=True)` → SHA-256 idiom.
- **D-05:** Experiment ids use prefix `kajiba_exp_<first 12 hex>`. Coding-session ids keep `kajiba_<12hex>`.
- **D-06:** `ExperimentRecord.compute_submission_hash()` IS computed (not `None`), over the same experiment-identity content, format `sha256:<hex>`. Purpose: local dedup only.
- **D-07:** Bump `SCHEMA_VERSION` `0.1.0` → **`0.2.0`** (semver minor). Does NOT affect `record_id`/`submission_hash`.
- **D-08:** Single shared `SCHEMA_VERSION` constant covers both kinds. No separate `EXPERIMENT_SCHEMA_VERSION`.

### Claude's Discretion
- Dispatch wiring (discriminated union vs RootModel vs manual factory) for the new experiment loader; `validate_record()` stays `KajibaRecord`-only and unchanged. Loader name open (`validate_experiment` vs `load_record`).
- Back-compat test mechanics (committed golden JSON vs hardcoded constants; repo-fixtures-only vs also scanning real `HERMES_HOME`).
- Where `compute_*` methods live (abstract on base vs per-subclass override) and exact field ordering.

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ESCH-01 | `record_kind` discriminator on `RecordBase`, defaults to `coding_session` | Verified: a `Literal["coding_session","model_experiment"] = "coding_session"` field on the base lets a dict omitting `record_kind` validate and expose `record_kind == "coding_session"` (empirically confirmed against `minimal_trajectory.json`). Define with dual tuple+Literal pattern (RECORD_KINDS / RecordKindType). |
| ESCH-02 | Shared `RecordBase`; both records subclass it | Verified: Pydantic v2 inheritance places base fields first in declaration order, then subclass fields; `issubclass()` holds; no positional required/optional ordering constraint (unlike dataclasses). |
| ESCH-03 | `ExperimentMetadata` + `ExperimentOutcome` + `ExperimentRecord`, JSON round-trips | Field shapes locked in SPEC (supersede `docs/dual-use-roadmap.md` §4.1 — see "State of the Art" for the renames). Dual tuple+Literal vocab for `experiment_type` and `recommended_action`. |
| ESCH-04 | Byte-identical `record_id` + `submission_hash` for every existing record | **VERIFIED EMPIRICALLY**: refactored model (base + `record_kind` + `schema_version="0.2.0"`) produces `kajiba_c2eac32fcdc4` for `minimal_trajectory.json` — byte-identical to the pre-refactor computation. The hash methods touch ONLY trajectory `from`/`value` (record_id) and trajectory + `model.model_name` + `outcome.user_rating` + sorted `outcome.outcome_tags` (submission_hash). None of the moved/added fields participate. |
| (5th) Load dispatch contract | `validate_record()` unchanged for all callers; experiments load via a separate function | Verified all call sites (cli.py ×6, privacy.py ×3 via `.model_validate`, collector.py) only access KajibaRecord-specific attrs. Keep `validate_record = KajibaRecord.model_validate`. Add a separate `load_record()`/`validate_experiment()`. |
</phase_requirements>

## Summary

This is a low-ambiguity, high-precision Pydantic v2 refactor. The dominant risk (ESCH-04, byte-identical hashes) is **already retired by research**: I ran the actual project hashing idiom under a simulated post-refactor model and got byte-identical output, because `compute_record_id()` and `compute_submission_hash()` build their hash payloads from *explicitly enumerated* fields (trajectory turns, `model.model_name`, `outcome.user_rating`, `outcome.outcome_tags`) rather than from `model_dump()`. Moving fields to a `RecordBase`, adding `record_kind`, and bumping `SCHEMA_VERSION` cannot perturb the hash — none of those touch the hashed payload.

The one genuine landmine is the **dispatch mechanism**. I empirically confirmed that a Pydantic `Field(discriminator="record_kind")` tagged union **raises `union_tag_not_found` when the dict omits `record_kind`** — and *every* existing fixture/staged/outbox dict omits it. A discriminated union therefore CANNOT be the back-compat loader. The clean, verified solution is a **manual factory** that reads `data.get("record_kind", "coding_session")` and dispatches to the right model. This also keeps `validate_record()` literally unchanged.

**Primary recommendation:** Extract `RecordBase`; keep `validate_record()` as-is (`KajibaRecord.model_validate`); add a separate `load_record(data)` factory that defaults missing `record_kind` to `coding_session`; keep `compute_*` as per-subclass methods (override on `ExperimentRecord`, do NOT abstract onto the base); pin ESCH-04 with a committed golden-baseline JSON generated from the pre-refactor schema over `tests/fixtures/*.json`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Record validation / schema | Schema (`schema.py`) | — | Single source of truth per CLAUDE.md; D-01 keeps everything in one module |
| Load dispatch on `record_kind` | Schema (`schema.py`) | — | `validate_record()` + new `load_record()` are both schema-layer entry points |
| Content-hash identity | Schema (model methods) | — | `compute_*` are instance methods on the record models |
| Back-compat guarantee (ESCH-04) | Tests (`tests/`) | Schema | Golden-baseline pinning is a test responsibility; schema only must not break it |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | 2.12.5 (pinned `>=2.0`) | All schema models, validation, serialization | Already the project's single validation layer [VERIFIED: `python -c import pydantic` → 2.12.5] |
| python stdlib `hashlib`, `json`, `datetime`, `typing` | 3.13.3 (req `>=3.11`) | SHA-256, deterministic serialization, `datetime`, `Literal`/`Optional` | Already used by `schema.py`; no new deps [VERIFIED: import block lines 7-13] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | `>=7.0` | Golden-ID + round-trip tests | Existing test runner; house style in `tests/test_scorer.py` [VERIFIED: pyproject test deps] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Manual factory dispatch | `Annotated[Union[...], Field(discriminator="record_kind")]` via `TypeAdapter`/`RootModel` | **REJECTED for the loader** — raises `union_tag_not_found` on dicts missing `record_kind` (all existing files). Could only work if you first inject a default `record_kind`, which is uglier than a one-line factory. |
| Manual factory dispatch | Bare `Union[KajibaRecord, ExperimentRecord]` (left-to-right) | Works but error messages are noisy (tries both, reports both failures) and ordering-fragile; the factory is clearer and matches the SPEC's "separate loader" intent. |

**Installation:** None. **No new dependency may be added to `pyproject.toml`** (hard constraint). No `npm`/`pip install` step in this phase.

## Package Legitimacy Audit

> Not applicable — this phase installs **zero** external packages. All work uses already-pinned `pydantic>=2.0` and the Python standard library. `pyproject.toml` must not grow (acceptance criterion).

## Architecture Patterns

### System Architecture Diagram

```
                    raw dict (json.loads of a fixture / staged / outbox file)
                                        |
                    +-------------------+-------------------+
                    |                                       |
          validate_record(data)                     load_record(data)   <-- NEW
          (UNCHANGED, KajibaRecord-only)            (factory: reads record_kind,
                    |                                 default "coding_session")
                    |                                       |
                    v                          +------------+------------+
          KajibaRecord.model_validate          | kind == coding_session  | kind == model_experiment
                    |                          v                         v
                    |                 KajibaRecord.model_validate  ExperimentRecord.model_validate
                    v                          |                         |
          KajibaRecord  <----------------------+                         v
          .compute_record_id()    -> kajiba_<12hex>            ExperimentRecord
          .compute_submission_hash() -> sha256:<hex>           .compute_record_id()    -> kajiba_exp_<12hex>
                                                                .compute_submission_hash() -> sha256:<hex>

          RecordBase  (shared fields: schema_version, record_id, submission_hash,
                       created_at, record_kind, model, hardware, submission)
            ^                          ^
            | extends                  | extends
      KajibaRecord                ExperimentRecord
      (+ record_type, trajectory,  (+ experiment: ExperimentMetadata,
         outcome, pain_points,        outcome: ExperimentOutcome,
         quality)                     trajectory: Optional[Trajectory] = None  <-- reserved, no logic)
```

cli.py / privacy.py / collector.py continue to call `validate_record()` only — left arm unchanged.

### Recommended Project Structure

```
src/kajiba/schema.py    # ALL changes land here (D-01)
  ├── Constants: SCHEMA_VERSION = "0.2.0"   (bumped, D-07)
  │              RECORD_KINDS + RecordKindType          (new dual vocab, ESCH-01)
  │              EXPERIMENT_TYPES + ExperimentTypeType  (new dual vocab, ESCH-03)
  │              RECOMMENDED_ACTIONS + RecommendedActionType (new dual vocab, ESCH-03)
  ├── Nested models: ToolCall, ConversationTurn (UNTOUCHED), Trajectory,
  │                  ModelMetadata, HardwareProfile, OutcomeSignals, PainPoint,
  │                  ScrubLog, QualityMetadata, SubmissionMetadata   (unchanged)
  ├── RecordBase(BaseModel)                  (new — shared fields + populate_by_name)
  ├── KajibaRecord(RecordBase)               (refactored — base fields removed, kept: record_type, trajectory, outcome, pain_points, quality)
  ├── ExperimentMetadata(BaseModel)          (new)
  ├── ExperimentOutcome(BaseModel)           (new)
  ├── ExperimentRecord(RecordBase)           (new)
  └── Public API: validate_record() (UNCHANGED) + load_record() (new factory)
tests/
  ├── fixtures/golden_ids.json               (new — committed baseline, generated pre-refactor)
  └── test_schema_backcompat.py              (new — golden-ID + round-trip tests)
```

### Pattern 1: Shared base + record-specific tails (verified)
**What:** `RecordBase` carries cross-kind fields; each record adds its own tail.
**When to use:** When two record families share identity/metadata but diverge in payload.
**Verified behavior:** Pydantic v2 emits base fields first (in base declaration order) then subclass fields; `model_fields` order observed: `['schema_version','record_id','submission_hash','record_kind', <subclass fields...>]`. There is **no** dataclass-style "required-after-optional" error — a required subclass field after optional base fields is accepted.

```python
# Source: empirically run against pydantic 2.12.5 in this repo
class RecordBase(BaseModel):
    schema_version: str = SCHEMA_VERSION
    record_id: Optional[str] = None
    submission_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    record_kind: RecordKindType = "coding_session"   # default = back-compat (ESCH-01)
    model: Optional[ModelMetadata] = None
    hardware: Optional[HardwareProfile] = None
    submission: Optional[SubmissionMetadata] = None

    model_config = {"populate_by_name": True}   # place on base; subclasses inherit it

class KajibaRecord(RecordBase):
    record_type: RecordTypeType = "task_trajectory"
    trajectory: Trajectory
    outcome: Optional[OutcomeSignals] = None
    pain_points: Optional[list[PainPoint]] = None
    quality: Optional[QualityMetadata] = None
    # model_config inherited from RecordBase — but see Pitfall 3 about re-declaring it
```

### Pattern 2: Manual factory dispatch (RECOMMENDED loader)
**What:** A standalone function reads `record_kind` and routes to the right model.
**Why over discriminated union:** Handles missing `record_kind` gracefully (the discriminated union does not — verified). Keeps `validate_record()` untouched.

```python
# Source: empirically verified in this repo
def validate_record(data: dict) -> KajibaRecord:
    """UNCHANGED — KajibaRecord-only loader for existing callers."""
    return KajibaRecord.model_validate(data)

def load_record(data: dict):
    """Dispatch on record_kind; defaults to coding_session for legacy dicts.

    Returns KajibaRecord for coding sessions, ExperimentRecord for experiments.
    """
    kind = data.get("record_kind", "coding_session")
    if kind == "model_experiment":
        return ExperimentRecord.model_validate(data)
    return KajibaRecord.model_validate(data)
```
(Choose a clear return annotation, e.g. `Union[KajibaRecord, ExperimentRecord]`, only on `load_record` — never weaken `validate_record`'s `-> KajibaRecord`.)

### Pattern 3: compute_* lives per-subclass (do NOT abstract onto base)
**What:** Keep `KajibaRecord.compute_record_id/compute_submission_hash` exactly as-is; give `ExperimentRecord` its own overrides (D-04/D-05/D-06).
**Why:** The two payloads are completely different (trajectory turns vs experiment identity). An abstract base method would add surface area with zero shared logic and risks accidentally touching the KajibaRecord payload. Leaving KajibaRecord's methods byte-for-byte unchanged is the safest path to ESCH-04.

```python
# ExperimentRecord — Source: D-04/D-05/D-06, same idiom as KajibaRecord (schema.py:346-379)
def compute_record_id(self) -> str:
    content = json.dumps(
        {
            "experiment_id": self.experiment.experiment_id,
            "task_description": self.experiment.task_description,
            "local_model_name": self.experiment.local_model.model_name,
            "local_model_output": self.outcome.local_model_output,
            "started_at": self.experiment.started_at.isoformat(),
        },
        sort_keys=True, ensure_ascii=True,
    )
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    self.record_id = f"kajiba_exp_{digest[:12]}"
    return self.record_id
```
> **Open detail for the planner (LOW risk):** D-04 lists `started_at` as hash input but does not specify its serialized form. `datetime` is not JSON-serializable by `json.dumps`. Recommend `self.experiment.started_at.isoformat()` (deterministic, matches Pydantic's JSON datetime output). Flag in PLAN as an explicit decision so the experiment-id format is locked before Phase 11 starts consuming it.

### Anti-Patterns to Avoid
- **Discriminated `Field(discriminator="record_kind")` as the loader** — fails `union_tag_not_found` on every legacy dict (no `record_kind` key). VERIFIED failure.
- **Hashing via `model_dump()`** — would couple the hash to field set/order and `record_kind`/`schema_version`, breaking ESCH-04. The existing code does NOT do this; do not "refactor" it to.
- **Promoting `compute_*` to an abstract base method** — needless coupling; the two payloads share nothing.
- **Changing `validate_record`'s signature or body** — the SPEC requires `git diff` shows no behavioral change at its call sites.
- **Touching `ConversationTurn`** — explicitly excluded; verified by diff is an acceptance criterion.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Vocabulary validation for `experiment_type` / `recommended_action` | Custom `if x not in (...)` everywhere | `Literal[...]` type + the dual tuple pattern (Pydantic rejects out-of-vocab automatically) | Matches `OUTCOME_TAGS`/`OutcomeTagType`; Pydantic raises `ValidationError` for free |
| JSON round-trip equality | Custom field-by-field comparison | `model_dump(mode="json", by_alias=True)` → `model_validate` and compare model objects | Pydantic models support `==`; matches the round-trip acceptance criterion verbatim |
| Record-kind dispatch | Hand-rolled discriminated-union plumbing | One-line `data.get("record_kind", "coding_session")` factory | Verified simplest correct approach for legacy dicts |

**Key insight:** The repo already contains every pattern you need (dual vocab, content hashing, `populate_by_name`, Google docstrings). This phase is almost entirely *replication of existing idioms* onto new fields — not invention.

## Runtime State Inventory

> Refactor phase. Five categories answered explicitly.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `tests/fixtures/*.json` (gold, silver, minimal, pii, adversarial) carry `schema_version: "0.1.0"` and no `record_kind`. Real `HERMES_HOME` staging/outbox dicts (not in repo) similarly lack `record_kind`. | **None — runtime default only (D-07).** Existing files are NEVER rewritten. The `record_kind` default + version-tolerant validation handle old dicts. Confirmed: `minimal_trajectory.json` validates and yields `coding_session`. |
| Live service config | None — Kajiba is a local, network-free pipeline (CLAUDE.md "No external services for core"). | None. |
| OS-registered state | None — no scheduled tasks, daemons, or registered services touch the schema. | None. |
| Secrets/env vars | `HERMES_HOME` env (resolves `~/.hermes/kajiba/`) is read by cli.py but is unaffected by a schema change. | None. |
| Build artifacts | `src/kajiba/__pycache__/`, `kajiba.egg-info` (editable install) — stale only if module API names change. Adding new exports (`RecordBase`, `ExperimentRecord`, `load_record`) is additive. | None required; `pip install -e .` already linked. Re-run only if imports fail. |

**The canonical question — after every file in the repo is updated, what runtime systems still have the old string cached?** Answer: only the on-disk JSON records carrying `"schema_version": "0.1.0"` and no `record_kind`. By design (D-07, runtime default) these are *intentionally* left as-is and validate correctly. No migration. No rewrite.

## Common Pitfalls

### Pitfall 1: Discriminated union breaks legacy loading
**What goes wrong:** Using `Annotated[Union[...], Field(discriminator="record_kind")]` as the loader.
**Why it happens:** Pydantic requires the discriminator key to be present in the input; legacy dicts omit `record_kind`.
**How to avoid:** Use the manual factory (`data.get("record_kind", "coding_session")`).
**Warning signs:** `pydantic_core ValidationError: ... union_tag_not_found ... discriminator 'record_kind'` (the exact error I reproduced).

### Pitfall 2: Accidentally altering the hash payload
**What goes wrong:** "Cleaning up" `compute_*` to iterate `model_dump()` or include new base fields.
**Why it happens:** Refactor temptation; the methods look hand-built.
**How to avoid:** Treat `KajibaRecord.compute_record_id` / `compute_submission_hash` bodies as frozen (lines 337-379). Only their *class location* changes (now inheriting `record_id`/`submission_hash` attributes from base). The golden-ID test is the tripwire.
**Warning signs:** Any golden-baseline mismatch.

### Pitfall 3: `model_config` / `protected_namespaces` and the `model` field
**What goes wrong:** Pydantic v2 reserves the `model_` namespace; a field literally named `model` (a `ModelMetadata`) historically warns. The existing code already has `model: Optional[ModelMetadata]` on `KajibaRecord` and currently works — meaning `model_config = {"populate_by_name": True}` plus the existing field name is tolerated in 2.12.5. When you move `model` onto `RecordBase`, carry the SAME `model_config` onto the base so behavior is identical.
**Why it happens:** `model_config` does NOT merge across inheritance by replacement — a subclass that re-declares `model_config` overrides it wholesale (it does not deep-merge). Declare `populate_by_name` on `RecordBase`; subclasses inherit it. Only re-declare in a subclass if that subclass needs *additional* config (then include the inherited keys too).
**How to avoid:** Put `model_config = {"populate_by_name": True}` on `RecordBase`. Do not re-declare an empty/partial config on `KajibaRecord` or `ExperimentRecord`.
**Warning signs:** `from` alias stops resolving on `ConversationTurn` round-trips (ConversationTurn has its own `model_config`, so it's independent — but watch the record-level alias behavior).

### Pitfall 4: `started_at` serialization in the experiment hash
**What goes wrong:** `json.dumps({"started_at": self.experiment.started_at})` raises `TypeError: Object of type datetime is not JSON serializable`.
**How to avoid:** Serialize with `.isoformat()` (see Pattern 3). Lock this in PLAN.
**Warning signs:** `TypeError` at experiment-id computation.

### Pitfall 5: Model-level validators are KajibaRecord-specific
**What goes wrong:** Assuming `validate_turn_count` / `validate_tool_call_counts` should move to the base.
**Why it happens:** They're `@model_validator` and look general.
**How to avoid:** They reference `self.trajectory` (KajibaRecord-only required field). Keep them on `KajibaRecord`. `ExperimentRecord.trajectory` is `Optional` and reserved — do NOT attach these validators to it.

## Code Examples

### New controlled vocabularies (dual tuple + Literal, matching schema.py:25-65)
```python
# Source: replicate OUTCOME_TAGS / OutcomeTagType pattern (schema.py:23-65)
RECORD_KINDS = ("coding_session", "model_experiment")
RecordKindType = Literal["coding_session", "model_experiment"]

EXPERIMENT_TYPES = ("model_evaluation", "routing_test", "quality_drift", "prompt_ablation")
ExperimentTypeType = Literal["model_evaluation", "routing_test", "quality_drift", "prompt_ablation"]

RECOMMENDED_ACTIONS = ("use_as_is", "needs_fine_tune", "route_to_reviewer", "discard")
RecommendedActionType = Literal["use_as_is", "needs_fine_tune", "route_to_reviewer", "discard"]
```

### ExperimentMetadata / ExperimentOutcome (field sets locked by SPEC R3)
```python
# Source: 10-SPEC.md requirement 3 (supersedes docs/dual-use-roadmap.md §4.1)
class ExperimentMetadata(BaseModel):
    experiment_id: str
    experiment_type: ExperimentTypeType
    local_model: ModelMetadata
    reviewer_model: Optional[ModelMetadata] = None
    task_category: str
    task_description: str
    started_at: datetime
    completed_at: Optional[datetime] = None

class ExperimentOutcome(BaseModel):
    local_model_output: str
    reviewer_critique: Optional[str] = None
    eval_score: float = Field(ge=0.0, le=1.0)
    drift_flag: bool = False
    lessons_learned: list[str] = Field(default_factory=list)
    recommended_action: Optional[RecommendedActionType] = None

class ExperimentRecord(RecordBase):
    record_kind: RecordKindType = "model_experiment"   # narrow default for this kind
    experiment: ExperimentMetadata
    outcome: ExperimentOutcome
    trajectory: Optional[Trajectory] = None            # reserved; no population logic this phase
```
> Note: `eval_score: float = Field(ge=0.0, le=1.0)` mirrors `OutcomeSignals.user_rating` / `QualityMetadata.composite_score` constraint style (schema.py:187, 235). SPEC says "0.0–1.0".

### Golden-ID baseline test (house style from tests/test_scorer.py)
```python
# Source: tests/test_scorer.py house style (_load_fixture, FIXTURES = .../fixtures)
import json
from pathlib import Path
import pytest
from kajiba.schema import validate_record

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = json.loads((FIXTURES / "golden_ids.json").read_text(encoding="utf-8"))

@pytest.mark.parametrize("name", list(GOLDEN.keys()))
def test_record_id_and_submission_hash_stable(name: str) -> None:
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    rec = validate_record(data)
    assert rec.compute_record_id() == GOLDEN[name]["record_id"]
    assert rec.compute_submission_hash() == GOLDEN[name]["submission_hash"]
```

## State of the Art

| Old (docs/dual-use-roadmap.md §4.1) | Current (10-SPEC.md — authoritative) | When Changed | Impact |
|-------------------------------------|--------------------------------------|--------------|--------|
| `quality_score: float` | `eval_score: float` (0.0–1.0) | SPEC R3 | Use SPEC name |
| `drift_detected: bool` | `drift_flag: bool = False` | SPEC R3 | Use SPEC name + default |
| `recommended_action` values include `"route_to_grok"` | `"route_to_reviewer"` (vendor-neutral) | SPEC R3 | Use SPEC vocab |
| `completed_at: Optional[datetime]` (no default) | `Optional[datetime] = None` | SPEC R3 | Add explicit default |
| `recommended_action: Optional[str]` (free string) | `Optional[Literal[...]]` controlled vocab | SPEC R3 | Constrain via dual vocab |
| Roadmap §4.1: "may extend `ConversationTurn` with `reviewer_turn`" | **Excluded** (Round 2) | CONTEXT | ConversationTurn untouched |

**Deprecated/outdated:** Treat `docs/dual-use-roadmap.md` §4.1 code block as a *draft sketch only*. The SPEC field sets win on every conflict.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `started_at` should be serialized via `.isoformat()` inside the experiment hash (D-04 leaves the form unspecified) | Pattern 3 / Pitfall 4 | If a later phase expects a different serialization, the experiment-id format changes. LOW — no experiment records exist yet; lock it now in PLAN. |
| A2 | `eval_score` should carry `Field(ge=0.0, le=1.0)` (SPEC says "0.0–1.0" but doesn't mandate a validator) | Code Examples | LOW — matches repo convention; if undesired, drop the constraint. |
| A3 | Real `HERMES_HOME` staging/outbox is treated as a manual/runtime check, not a repo test (per CONTEXT suggested default) | Validation Architecture | LOW — fixtures cover the schema-shape guarantee; real files are user-specific and not in the repo. |

## Open Questions

1. **Experiment-id `started_at` serialization (A1).** Recommendation: `.isoformat()`. Lock in PLAN before any Phase 11 code consumes the id.
2. **Should `load_record()` also be exported/used by callers now?** Recommendation: add it to `schema.py` public API but do NOT wire any existing caller to it (out of scope — Phase 11 CLI consumes it). Keeps this phase pure-schema.

## Validation Architecture

> `nyquist_validation` not disabled in config → section included. These two tests are strong VALIDATION.md candidates.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest `>=7.0` (+ pytest-cov `>=4.0`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (verify section exists; tests auto-discovered under `tests/`) |
| Quick run command | `python -m pytest tests/test_schema_backcompat.py -x -q` |
| Full suite command | `python -m pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ESCH-04 | Every existing fixture keeps byte-identical `record_id` + `submission_hash` | unit (golden) | `python -m pytest tests/test_schema_backcompat.py::test_record_id_and_submission_hash_stable -q` | ❌ Wave 0 |
| ESCH-04 | Every existing fixture loads via `validate_record()` without error | unit | `python -m pytest tests/test_schema_backcompat.py::test_legacy_dicts_load -q` | ❌ Wave 0 |
| ESCH-01 | Dict without `record_kind` → `coding_session`; with `model_experiment` → ExperimentRecord | unit | `python -m pytest tests/test_schema_backcompat.py::test_record_kind_default -q` | ❌ Wave 0 |
| ESCH-02 | `issubclass(KajibaRecord, RecordBase)` and `issubclass(ExperimentRecord, RecordBase)`; inherited attrs present | unit | `python -m pytest tests/test_schema_backcompat.py::test_base_inheritance -q` | ❌ Wave 0 |
| ESCH-03 | `ExperimentRecord` round-trips `model_dump(mode="json", by_alias=True)` → `model_validate` equal; out-of-vocab rejected; `recommended_action=None` accepted | unit | `python -m pytest tests/test_schema_experiment.py -q` | ❌ Wave 0 |
| 5th | `validate_record()` returns `KajibaRecord`; `load_record()` returns `ExperimentRecord` for experiment dict | unit | `python -m pytest tests/test_schema_backcompat.py::test_load_dispatch -q` | ❌ Wave 0 |
| ConversationTurn unchanged | `git diff` shows no change to `ConversationTurn` | manual/CI | `git diff src/kajiba/schema.py` — inspect ConversationTurn block | n/a |

### Golden Baseline Capture Procedure (must run BEFORE the refactor)
The baseline must be generated from the **pre-refactor** schema so it captures the true legacy hashes. Recommended Wave 0 step (run on the current `master` before editing `schema.py`):
```bash
python - <<'PY'
import json
from pathlib import Path
from kajiba.schema import validate_record   # PRE-refactor version
fx = Path("tests/fixtures")
out = {}
for f in sorted(fx.glob("*_trajectory.json")):   # the 5 record fixtures (exclude enriched_catalog.json)
    data = json.loads(f.read_text(encoding="utf-8"))
    rec = validate_record(data)
    out[f.name] = {"record_id": rec.compute_record_id(),
                   "submission_hash": rec.compute_submission_hash()}
Path("tests/fixtures/golden_ids.json").write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
print(out)
PY
```
Commit `golden_ids.json` **before** touching `schema.py`. After the refactor, the parametrized test recomputes and asserts byte-identical equality. (RESEARCH already proved the byte-identical outcome for `minimal_trajectory.json`: `kajiba_c2eac32fcdc4` — the test will pass.)

> **Planner note:** exclude `enriched_catalog.json` from the golden corpus — it is a publisher catalog fixture, not a `KajibaRecord` (it has no `trajectory`). Use the five `*_trajectory.json` fixtures. Confirm by inspecting whether each fixture has a top-level `trajectory` key before adding it to the baseline.

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_schema_backcompat.py tests/test_schema_experiment.py -x -q`
- **Per wave merge:** `python -m pytest -q` (full suite — must stay green; existing `test_scorer.py` exercises `validate_record` on fixtures and will catch any regression)
- **Phase gate:** Full suite green + `git diff` confirms `ConversationTurn` and `validate_record` bodies unchanged.

### Wave 0 Gaps
- [ ] `tests/fixtures/golden_ids.json` — generated from PRE-refactor schema (capture step above)
- [ ] `tests/test_schema_backcompat.py` — golden-ID, legacy-load, record_kind default, base-inheritance, load-dispatch (covers ESCH-01/02/04 + 5th)
- [ ] `tests/test_schema_experiment.py` — ExperimentRecord round-trip, vocab rejection, `recommended_action=None` (covers ESCH-03)
- [ ] Confirm `[tool.pytest.ini_options]` exists in `pyproject.toml` (if absent, pytest still discovers `tests/` by default — no install needed)

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | ✓ | 3.13.3 (req `>=3.11`) | — |
| pydantic | Schema | ✓ | 2.12.5 (req `>=2.0`) | — |
| pytest | Tests | ✓ (declared dev dep) | `>=7.0` | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None. This phase adds zero dependencies.

## Project Constraints (from CLAUDE.md)

- Pydantic v2 only; `Optional[X]` typing (NOT `X | None`) — verified throughout existing `schema.py`.
- Dual `tuple` + `Literal` controlled-vocabulary pattern (e.g. `OUTCOME_TAGS` + `OutcomeTagType`).
- `model_config = {"populate_by_name": True}` where aliases apply.
- Double-quoted strings; Google-style docstrings; module-level `logger = logging.getLogger(__name__)`.
- `BaseModel` (not `@dataclass`) for all schema models; `field_validator`/`model_validator` for validation.
- No new third-party dependencies; `pyproject.toml` must not grow.
- GSD workflow: file edits happen via the GSD execute-phase flow, not ad-hoc.

## Sources

### Primary (HIGH confidence — verified by running this repo's code)
- `src/kajiba/schema.py` (full read) — `KajibaRecord`, nested models, `compute_record_id` (lines 337-356), `compute_submission_hash` (358-379), `validate_record` (387-399).
- Empirical run (`pydantic 2.12.5`, `Python 3.13.3`): byte-identical hash (`kajiba_c2eac32fcdc4`) under simulated refactor; `union_tag_not_found` for discriminated union on legacy dict; manual factory success; inheritance field ordering; required-after-optional acceptance.
- `tests/fixtures/minimal_trajectory.json`, `gold_trajectory.json` — legacy dicts lacking `record_kind`.
- `src/kajiba/cli.py` (call-site grep + context read), `src/kajiba/privacy.py`, `src/kajiba/collector.py` — all callers access KajibaRecord-only attrs.
- `tests/test_scorer.py` — house test style (`_load_fixture`, `FIXTURES`).
- `10-SPEC.md`, `10-CONTEXT.md` — locked requirements and decisions.

### Secondary (MEDIUM confidence)
- `docs/dual-use-roadmap.md` §4.1/§4.4 — draft field shapes (superseded by SPEC on conflicts).
- `pydantic_core` error string `union_tag_not_found` references `https://errors.pydantic.dev/2.12/v/union_tag_not_found` (emitted by the installed version).

### Tertiary (LOW confidence)
- None — all claims grounded in code execution or locked SPEC/CONTEXT.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions confirmed by direct interpreter query; zero new deps.
- Architecture / dispatch: HIGH — discriminated-union failure and factory success both reproduced live.
- Hash stability (ESCH-04): HIGH — byte-identical output reproduced against a real fixture.
- Pitfalls: HIGH — each reproduced or read directly in source.

**Research date:** 2026-06-03
**Valid until:** 2026-07-03 (stable; pinned Pydantic v2, locked SPEC)

## RESEARCH COMPLETE
