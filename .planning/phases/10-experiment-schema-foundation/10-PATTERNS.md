# Phase 10: Experiment Schema Foundation - Pattern Map

**Mapped:** 2026-06-03
**Files analyzed:** 8 symbols / 3 files (1 modified module, 2 new test modules, 1 new fixture)
**Analogs found:** 8 / 8 (every symbol has an in-repo analog — this phase is pure replication of existing idioms)

> **Key fact for planner/executor:** Per decision D-01, ALL new models live in the EXISTING `src/kajiba/schema.py`. There are no new source modules. Every analog below is in `src/kajiba/schema.py` or `tests/test_scorer.py`. Replicate the existing idiom exactly; do not invent new patterns.

## File Classification

| New/Modified Symbol | File | Role | Data Flow | Closest Analog | Match Quality |
|---------------------|------|------|-----------|----------------|---------------|
| `RecordBase` (NEW class) | `src/kajiba/schema.py` | model (base) | transform/validation | `KajibaRecord` class body + `model_config` (schema.py:256-278) | exact (same module, same idioms) |
| `KajibaRecord` (MODIFIED → subclass) | `src/kajiba/schema.py` | model | transform/validation | itself, current declaration (schema.py:256-379) | self |
| `ExperimentMetadata` (NEW class) | `src/kajiba/schema.py` | model (nested) | transform/validation | `ModelMetadata` (schema.py:157-168), `OutcomeSignals` (schema.py:184-200) | exact |
| `ExperimentOutcome` (NEW class) | `src/kajiba/schema.py` | model (nested) | transform/validation | `OutcomeSignals` (schema.py:184-200), `QualityMetadata` (schema.py:227-237) | exact |
| `ExperimentRecord` (NEW class) | `src/kajiba/schema.py` | model | transform/validation | `KajibaRecord` top-level structure (schema.py:256-278) | exact |
| `experiment_type` + `recommended_action` + `record_kind` vocabs (NEW) | `src/kajiba/schema.py` | config (controlled vocab) | n/a | `OUTCOME_TAGS` + `OutcomeTagType` (schema.py:25-65) | exact |
| `ExperimentRecord.compute_record_id()` / `compute_submission_hash()` (NEW) | `src/kajiba/schema.py` | model method (hashing) | transform | `KajibaRecord.compute_record_id()` (schema.py:337-356) / `compute_submission_hash()` (schema.py:358-379) | exact |
| `load_record()` (NEW public fn) | `src/kajiba/schema.py` | utility (loader/factory) | request-response | `validate_record()` (schema.py:387-399) | role-match (factory wraps it) |
| `test_schema_backcompat.py` / `test_schema_experiment.py` (NEW) | `tests/` | test | n/a | `tests/test_scorer.py` (`_load_fixture`, `FIXTURES`, parametrize) | exact (house style) |

---

## Pattern Assignments

### Constants: SCHEMA_VERSION bump + new vocabularies (config)

**Analog:** dual `tuple` + `Literal` pattern — `OUTCOME_TAGS` / `OutcomeTagType` (schema.py:25-65); the shorter single-line Literals (schema.py:97-109).

**Existing dual-vocab idiom** (schema.py:25-65, abbreviated):
```python
OUTCOME_TAGS = (
    "task_completed",
    "task_partial",
    ...
)
OutcomeTagType = Literal[
    "task_completed",
    "task_partial",
    ...
]
```

**Existing version constant** (schema.py:21):
```python
SCHEMA_VERSION = "0.1.0"
```

**What to replicate / change:**
- Bump to `SCHEMA_VERSION = "0.2.0"` (D-07). Single shared constant; do NOT add `EXPERIMENT_SCHEMA_VERSION` (D-08).
- Add THREE new dual vocabularies next to the existing ones (after line 109), mirroring the tuple+Literal idiom exactly:
  - `RECORD_KINDS = ("coding_session", "model_experiment")` + `RecordKindType = Literal["coding_session", "model_experiment"]`
  - `EXPERIMENT_TYPES = ("model_evaluation", "routing_test", "quality_drift", "prompt_ablation")` + `ExperimentTypeType = Literal[...]`
  - `RECOMMENDED_ACTIONS = ("use_as_is", "needs_fine_tune", "route_to_reviewer", "discard")` + `RecommendedActionType = Literal[...]`
- **Runtime membership validation:** `OUTCOME_TAGS` has an explicit `field_validator` (schema.py:193-200) because it's a `list[OutcomeTagType]`. The new vocabs are **single scalar Literal fields**, NOT lists — so Pydantic rejects out-of-vocab values automatically via the `Literal` type. Do NOT hand-roll a `field_validator` for `experiment_type` / `recommended_action` / `record_kind`. (The `tuple` is kept only for parity/iteration, matching the house dual-definition convention.)

---

### `RecordBase` (NEW base model) — ESCH-02

**Analog:** `KajibaRecord` class declaration + `model_config` (schema.py:256-278). Field types for the promoted fields are copied verbatim from the current `KajibaRecord`.

**Current `KajibaRecord` field block to harvest from** (schema.py:264-278):
```python
    schema_version: str = SCHEMA_VERSION
    record_id: Optional[str] = None
    record_type: RecordTypeType = "task_trajectory"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    submission_hash: Optional[str] = None

    trajectory: Trajectory
    model: Optional[ModelMetadata] = None
    hardware: Optional[HardwareProfile] = None
    outcome: Optional[OutcomeSignals] = None
    pain_points: Optional[list[PainPoint]] = None
    submission: Optional[SubmissionMetadata] = None
    quality: Optional[QualityMetadata] = None

    model_config = {"populate_by_name": True}
```

**What to replicate / change (D-03):**
- Create `class RecordBase(BaseModel):` holding ONLY the shared fields, copied verbatim with their current types/defaults:
  `schema_version`, `record_id`, `submission_hash`, `created_at`, `model`, `hardware`, `submission`.
- ADD `record_kind: RecordKindType = "coding_session"` to the base (the back-compat default — ESCH-01).
- Move `model_config = {"populate_by_name": True}` ONTO `RecordBase` (Pitfall 3). Subclasses inherit it — do NOT re-declare a partial/empty config on `KajibaRecord` or `ExperimentRecord` (it would override wholesale, not merge).
- `Literal`-typed-field-with-default idiom for `record_kind` follows the existing `record_type: RecordTypeType = "task_trajectory"` (schema.py:266) — Literal type + a string default.

---

### `KajibaRecord` (MODIFIED → `KajibaRecord(RecordBase)`) — ESCH-02 / ESCH-04

**Analog:** itself (schema.py:256-379). This is a subtractive refactor, not a rewrite.

**What to replicate / change (D-02, D-03):**
- Change declaration `class KajibaRecord(BaseModel):` → `class KajibaRecord(RecordBase):`.
- REMOVE the base-promoted fields from the body (now inherited): `schema_version`, `record_id`, `created_at`, `submission_hash`, `model`, `hardware`, `submission`.
- KEEP on `KajibaRecord` (record-specific, NOT promoted): `record_type` (schema.py:266), `trajectory` (270), `outcome` (273), `pain_points` (274), `quality` (276).
- REMOVE the now-redundant `model_config` line (278) — inherited from base (Pitfall 3).
- KEEP the two `@model_validator(mode="after")` methods (`validate_turn_count` schema.py:280-289; `validate_tool_call_counts` 291-302) on `KajibaRecord` — they reference `self.trajectory` which is `KajibaRecord`-only. Do NOT move them to the base (Pitfall 5).
- KEEP `to_sharegpt` (304-316), `to_dpo_candidate` (318-335), `compute_record_id` (337-356), `compute_submission_hash` (358-379) **byte-for-byte unchanged** — only their class location is now a subclass. This is the ESCH-04 tripwire (Pitfall 2).

---

### `ExperimentMetadata` (NEW nested model) — ESCH-03

**Analog:** `ModelMetadata` (schema.py:157-168) and `OutcomeSignals` (schema.py:184-200) — field-only BaseModels with `Optional` fields and Literal-typed fields.

**ModelMetadata excerpt** (schema.py:157-168) — the "field-only nested model with Optionals" shape:
```python
class ModelMetadata(BaseModel):
    """Metadata about the model used for inference."""

    model_name: str
    model_family: Optional[str] = None
    ...
    provider: Optional[ProviderType] = None   # Literal-typed Optional field
    is_local: Optional[bool] = None
```

**What to replicate (field set locked by SPEC R3):**
```python
class ExperimentMetadata(BaseModel):
    experiment_id: str
    experiment_type: ExperimentTypeType          # scalar Literal → auto-rejects out-of-vocab
    local_model: ModelMetadata                   # REUSE existing nested model
    reviewer_model: Optional[ModelMetadata] = None
    task_category: str
    task_description: str
    started_at: datetime
    completed_at: Optional[datetime] = None
```
- `Optional[X] = None` typing (NOT `X | None`) — matches the whole module.
- Reuse the existing `ModelMetadata` for both `local_model` and `reviewer_model` (CONTEXT reusable assets).

---

### `ExperimentOutcome` (NEW nested model) — ESCH-03

**Analog:** `OutcomeSignals` (schema.py:184-200) for the `Field(ge=..., le=...)` + `default_factory=list` + Literal patterns; `QualityMetadata` (schema.py:227-237) for the `composite_score: float = Field(ge=0.0, le=1.0)` constraint.

**OutcomeSignals excerpts** (schema.py:187-191):
```python
    user_rating: int = Field(ge=1, le=5)                          # bounded numeric
    outcome_tags: list[OutcomeTagType] = Field(default_factory=list)  # mutable default
    user_comment: Optional[str] = None
    difficulty_estimate: Optional[DifficultyEstimateType] = None  # Optional Literal
```

**QualityMetadata bounded-float excerpt** (schema.py:235):
```python
    composite_score: float = Field(ge=0.0, le=1.0)
```

**What to replicate (field set locked by SPEC R3):**
```python
class ExperimentOutcome(BaseModel):
    local_model_output: str
    reviewer_critique: Optional[str] = None
    eval_score: float = Field(ge=0.0, le=1.0)            # mirror composite_score (schema.py:235)
    drift_flag: bool = False
    lessons_learned: list[str] = Field(default_factory=list)   # mirror outcome_tags (schema.py:188)
    recommended_action: Optional[RecommendedActionType] = None # Optional scalar Literal → None accepted
```
- `eval_score` constraint mirrors `composite_score` / `user_rating` constraint style (Assumption A2 — SPEC says "0.0-1.0").
- `lessons_learned` uses `Field(default_factory=list)` exactly like `outcome_tags`.
- `recommended_action: Optional[Literal[...]] = None` — `None` is valid; any non-None out-of-vocab value raises `ValidationError` for free (no validator needed).

---

### `ExperimentRecord(RecordBase)` (NEW top-level) — ESCH-03

**Analog:** `KajibaRecord` top-level structure (schema.py:256-278) — a `RecordBase` subclass with a record-specific tail and a narrowed `record_kind` default.

**What to replicate / change:**
```python
class ExperimentRecord(RecordBase):
    record_kind: RecordKindType = "model_experiment"   # narrow the base default for this kind
    experiment: ExperimentMetadata
    outcome: ExperimentOutcome
    trajectory: Optional[Trajectory] = None            # RESERVED — no population logic this phase
```
- Inherits `schema_version`, `record_id`, `submission_hash`, `created_at`, `model`, `hardware`, `submission`, and `model_config` from `RecordBase`.
- Re-declaring `record_kind` to default `"model_experiment"` is the analog of `KajibaRecord`'s `record_type` default (schema.py:266) — same Literal-default idiom.
- Do NOT attach `validate_turn_count` / `validate_tool_call_counts` here — `trajectory` is Optional/reserved (Pitfall 5).
- `trajectory: Optional[Trajectory] = None` reuses the existing `Trajectory` nested model (schema.py:138); declared only, no logic.

---

### `ExperimentRecord.compute_record_id()` / `compute_submission_hash()` (NEW methods) — D-04/D-05/D-06

**Analog (quote verbatim — reuse this exact idiom with a different payload + prefix):**

`KajibaRecord.compute_record_id()` (schema.py:337-356):
```python
    def compute_record_id(self) -> str:
        content = json.dumps(
            [
                {"from": t.from_, "value": t.value}
                for t in self.trajectory.conversations
            ],
            sort_keys=True,
            ensure_ascii=True,
        )
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        self.record_id = f"kajiba_{digest[:12]}"
        return self.record_id
```

`KajibaRecord.compute_submission_hash()` (schema.py:358-379):
```python
    def compute_submission_hash(self) -> str:
        parts = {
            "trajectory": [...],
            "model_name": self.model.model_name if self.model else None,
            "rating": self.outcome.user_rating if self.outcome else None,
            "tags": sorted(self.outcome.outcome_tags) if self.outcome else None,
        }
        content = json.dumps(parts, sort_keys=True, ensure_ascii=True)
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        self.submission_hash = f"sha256:{digest}"
        return self.submission_hash
```

**What to replicate / change (D-04/D-05/D-06):**
- Same idiom: build a dict/list payload → `json.dumps(..., sort_keys=True, ensure_ascii=True)` → `hashlib.sha256(...).hexdigest()`.
- **Different payload** (experiment identity, D-04): `experiment_id`, `task_description`, `local_model.model_name`, `outcome.local_model_output`, `started_at`.
- **`started_at` MUST be serialized via `.isoformat()`** (Pitfall 4 / Assumption A1 — `datetime` is not JSON-serializable). Lock this in the PLAN as the experiment-id format before Phase 11 consumes it.
- **Different prefix** (D-05): `self.record_id = f"kajiba_exp_{digest[:12]}"` (NOT `kajiba_`).
- `compute_submission_hash()` IS computed (D-06), `f"sha256:{digest}"` format, over the same experiment-identity content (local dedup, not community dedup).
- **Per-subclass, NOT abstract on base** (Pattern 3): keep `KajibaRecord`'s methods untouched; give `ExperimentRecord` its own overrides. The two payloads share nothing.

---

### `load_record()` (NEW public factory) + `validate_record()` (UNCHANGED) — ESCH-05

**Analog:** `validate_record()` (schema.py:387-399).

**Existing loader to mirror — and leave untouched** (schema.py:387-399):
```python
def validate_record(data: dict) -> KajibaRecord:
    """Parse raw JSON data into a validated KajibaRecord.
    ...
    Raises:
        pydantic.ValidationError: If the data fails schema validation.
    """
    return KajibaRecord.model_validate(data)
```

**What to replicate / change (Research Pattern 2 — manual factory):**
- `validate_record()` stays **byte-for-byte unchanged** (`-> KajibaRecord`, `KajibaRecord.model_validate(data)`). `git diff` must show no change at its call sites (cli.py ×6, privacy.py, collector.py).
- Add a SEPARATE `load_record(data)` factory next to it:
```python
def load_record(data: dict) -> Union[KajibaRecord, ExperimentRecord]:
    kind = data.get("record_kind", "coding_session")
    if kind == "model_experiment":
        return ExperimentRecord.model_validate(data)
    return KajibaRecord.model_validate(data)
```
- **Do NOT use `Field(discriminator="record_kind")` / discriminated `Union` as the loader** (Anti-pattern / Pitfall 1) — it raises `union_tag_not_found` on every legacy dict that omits `record_kind`. The manual `data.get("record_kind", "coding_session")` factory is the verified correct approach.
- Same Google-style docstring shape as `validate_record` (Args/Returns/Raises).
- `Union` will need to be imported from `typing` (the module currently imports `Literal, Optional` at schema.py:11 — add `Union`).

---

### `tests/test_schema_backcompat.py` + `tests/test_schema_experiment.py` (NEW)

**Analog:** `tests/test_scorer.py` — house test style.

**Imports + fixtures helper** (test_scorer.py:1-34):
```python
import json
from pathlib import Path
import pytest
from kajiba.schema import (..., validate_record)

FIXTURES = Path(__file__).parent / "fixtures"

def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))
```

**Class grouping + fixture-driven assertions** (test_scorer.py:63-97, the `TestQualityTiers` pattern):
- Tests are grouped in `class TestXxx:` with one-line docstrings per method.
- Each loads a fixture via `_load_fixture(...)`, validates via `validate_record(...)`, asserts.
- The module ALSO uses `@pytest.mark.parametrize` for fixture loops (the loop in test_scorer.py:282-291 is a manual list; the research recommends parametrizing the golden test).

**What to replicate / change:**
- `test_schema_backcompat.py` (ESCH-01/02/04 + ESCH-05): reuse `FIXTURES` constant + `_load_fixture` helper. Parametrize the golden-ID test over `golden_ids.json` keys:
```python
GOLDEN = json.loads((FIXTURES / "golden_ids.json").read_text(encoding="utf-8"))

@pytest.mark.parametrize("name", list(GOLDEN.keys()))
def test_record_id_and_submission_hash_stable(name: str) -> None:
    data = _load_fixture(name)
    rec = validate_record(data)
    assert rec.compute_record_id() == GOLDEN[name]["record_id"]
    assert rec.compute_submission_hash() == GOLDEN[name]["submission_hash"]
```
  Plus: `test_legacy_dicts_load`, `test_record_kind_default` (no `record_kind` → `"coding_session"`), `test_base_inheritance` (`issubclass(KajibaRecord, RecordBase)` and `issubclass(ExperimentRecord, RecordBase)`; inherited attrs present), `test_load_dispatch` (`validate_record` → `KajibaRecord`; `load_record` on `model_experiment` dict → `ExperimentRecord`).
- `test_schema_experiment.py` (ESCH-03): round-trip `model_dump(mode="json", by_alias=True)` → `model_validate` equality (Pydantic models support `==`); out-of-vocab `experiment_type` / `recommended_action` raises `ValidationError` (use `pytest.raises`); `recommended_action=None` accepted; `lessons_learned` defaults to `[]`.

---

### `tests/fixtures/golden_ids.json` (NEW — Wave 0, BEFORE refactor)

**Analog:** the existing fixtures (`tests/fixtures/*_trajectory.json`) and the capture procedure in RESEARCH §"Golden Baseline Capture Procedure".

**What to do:**
- Generate from the **PRE-refactor** schema (run on current `master` before editing `schema.py`) using `validate_record` → `compute_record_id()` / `compute_submission_hash()` over the FIVE `*_trajectory.json` fixtures.
- **Exclude `enriched_catalog.json`** (publisher catalog, no `trajectory` — not a `KajibaRecord`). Confirm each fixture has a top-level `trajectory` key before including it.
- Commit `golden_ids.json` BEFORE touching `schema.py`. It is the ESCH-04 tripwire.

---

## Shared Patterns

### Controlled vocabulary (dual tuple + Literal)
**Source:** `OUTCOME_TAGS` + `OutcomeTagType` (schema.py:25-65); scalar Literals (schema.py:97-109).
**Apply to:** `record_kind`, `experiment_type`, `recommended_action`.
**Rule:** Define a `tuple` (UPPER_SNAKE) AND a matching `Literal` (`XxxType`). For SCALAR Literal fields, Pydantic rejects out-of-vocab automatically — do NOT add a `field_validator` (that's only needed for `list[Literal]` fields like `outcome_tags`, schema.py:193-200).

### Typing & config conventions
**Source:** throughout schema.py.
**Apply to:** every new model.
**Rule:** `Optional[X] = None` (NOT `X | None`); modern generics `list[str]` / `dict[str, float]`; `Field(default_factory=list)` for mutable defaults; `Field(ge=..., le=...)` for bounded numerics; `model_config = {"populate_by_name": True}` declared ONCE on `RecordBase` and inherited (do not re-declare partial config in subclasses — Pitfall 3); double-quoted strings; Google-style docstrings; module-level `logger`.

### Content-hash identity idiom
**Source:** `compute_record_id` / `compute_submission_hash` (schema.py:337-379).
**Apply to:** `ExperimentRecord` hash methods only.
**Rule:** `json.dumps(<explicit payload>, sort_keys=True, ensure_ascii=True)` → `hashlib.sha256(content.encode("utf-8")).hexdigest()` → prefixed id. NEVER hash via `model_dump()` (would couple to field set / `record_kind` / `schema_version` and break ESCH-04 — Pitfall 2). Serialize `datetime` with `.isoformat()` (Pitfall 4).

### Test house style
**Source:** `tests/test_scorer.py` (`FIXTURES`, `_load_fixture`, `class TestXxx`, `@pytest.mark.parametrize`).
**Apply to:** both new test modules.

---

## No Analog Found

None. Every symbol in this phase replicates an existing idiom in `src/kajiba/schema.py` or `tests/test_scorer.py`. This phase is replication, not invention.

## Metadata

**Analog search scope:** `src/kajiba/schema.py` (full, 400 lines), `tests/test_scorer.py` (full, 292 lines). No broader search needed — D-01 confines all source changes to one module, and RESEARCH already verified every analog empirically against pydantic 2.12.5.
**Files scanned:** 5 (CONTEXT, SPEC, RESEARCH, schema.py, test_scorer.py).
**Pattern extraction date:** 2026-06-03

## PATTERN MAPPING COMPLETE
