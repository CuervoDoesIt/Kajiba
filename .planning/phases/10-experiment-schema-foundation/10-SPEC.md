# Phase 10: Experiment Schema Foundation — Specification

**Created:** 2026-06-03
**Ambiguity score:** 0.09 (gate: ≤ 0.20)
**Requirements:** 5 locked

## Goal

Refactor the schema so a `record_kind` discriminator and a shared base model let a new `ExperimentRecord` coexist with `KajibaRecord` — and every existing coding-session record loads unchanged with byte-identical `record_id` and `submission_hash`.

## Background

`src/kajiba/schema.py` defines `KajibaRecord` as a single monolithic top-level Pydantic v2 model with no base class, no discriminator, and no concept of an experiment. It owns `schema_version`, `record_id`, `record_type`, `created_at`, `submission_hash`, `trajectory`, `model`, `hardware`, `outcome`, `pain_points`, `submission`, `quality`, plus `compute_record_id()` / `compute_submission_hash()` (content hashes over trajectory turns + model name + rating + tags) and two cross-field validators.

`validate_record(data)` is the single load entry point, called from `cli.py` (6 sites), `privacy.py`, and `collector.py`; all callers assume the return value is a `KajibaRecord`. Existing staged/outbox JSON and the test fixtures (`tests/fixtures/*.json`) carry no `record_kind` field.

The v1.2 milestone (Experiment Logging, dual-use) needs a private, eval-oriented record type that reuses the schema base and scrub primitives but diverges into its own scorer, store, and export (Phases 11–15). This phase builds **only** the schema foundation: the discriminator, the shared base, the `ExperimentRecord` family, and a back-compat guarantee. The source proposal (`docs/dual-use-roadmap.md` §4.1) supplies candidate `ExperimentMetadata` / `ExperimentOutcome` shapes; this spec locks them.

## Requirements

1. **record_kind discriminator (ESCH-01)**: A `record_kind` field distinguishes the two record families and defaults to `coding_session` when absent.
   - Current: No discriminator exists; nothing distinguishes coding sessions from experiments
   - Target: `record_kind: Literal["coding_session", "model_experiment"]` lives on the shared base, defaults to `"coding_session"`, and is defined with the project's dual `tuple` + `Literal` vocabulary pattern
   - Acceptance: A record dict omitting `record_kind` validates and exposes `record_kind == "coding_session"`; a dict with `record_kind == "model_experiment"` validates as an `ExperimentRecord`

2. **Shared base model (ESCH-02)**: A common base holds fields shared by both record kinds; `KajibaRecord` and `ExperimentRecord` both extend it.
   - Current: `KajibaRecord` is a standalone model; no base class exists
   - Target: A shared base model (candidate name `RecordBase`) holds `schema_version`, `record_id`, `submission_hash`, `created_at`, `record_kind`, `model` (`ModelMetadata`), `hardware` (`HardwareProfile`), and `submission` (`SubmissionMetadata`, which wraps `scrub_log`). `record_type` and `quality` remain on `KajibaRecord` (record-specific, NOT promoted to base). `ConversationTurn` is unchanged.
   - Acceptance: `issubclass(KajibaRecord, <base>)` and `issubclass(ExperimentRecord, <base>)` are both true; an instance of each exposes `model`, `hardware`, `submission`, `record_id`, `submission_hash`, `created_at`, `schema_version`, and `record_kind` via the inherited base

3. **ExperimentRecord with metadata + outcome (ESCH-03)**: An `ExperimentRecord` captures experiment metadata and a flat outcome, and round-trips through JSON.
   - Current: No experiment models exist
   - Target: Three new models exist —
     - `ExperimentMetadata`: `experiment_id: str`, `experiment_type: Literal["model_evaluation","routing_test","quality_drift","prompt_ablation"]`, `local_model: ModelMetadata`, `reviewer_model: Optional[ModelMetadata] = None`, `task_category: str`, `task_description: str`, `started_at: datetime`, `completed_at: Optional[datetime] = None`
     - `ExperimentOutcome`: `local_model_output: str`, `reviewer_critique: Optional[str] = None`, `eval_score: float` (0.0–1.0), `drift_flag: bool = False`, `lessons_learned: list[str]` (default_factory=list), `recommended_action: Optional[Literal["use_as_is","needs_fine_tune","route_to_reviewer","discard"]] = None`
     - `ExperimentRecord(<base>)`: `experiment: ExperimentMetadata`, `outcome: ExperimentOutcome`, `trajectory: Optional[Trajectory] = None` (declared/reserved only — no capture or population logic in this phase)
     - `experiment_type` and `recommended_action` are both defined with the dual `tuple` + `Literal` vocabulary pattern and reject out-of-vocabulary values
   - Acceptance: A fully populated `ExperimentRecord` survives `model_dump(mode="json", by_alias=True)` → `model_validate` with an identical result; assigning an out-of-vocab `experiment_type` or `recommended_action` raises `ValidationError`; `recommended_action=None` is accepted

4. **Backward compatibility with stable IDs (ESCH-04)**: Every existing record loads unchanged and keeps its exact `record_id` and `submission_hash`.
   - Current: All existing fixtures and any staged/outbox JSON are plain `KajibaRecord` dicts with no `record_kind`
   - Target: After the refactor, all existing records still validate via `validate_record()`, and `KajibaRecord.compute_record_id()` / `compute_submission_hash()` produce byte-identical output to before. Achieved by runtime default only — existing files are never rewritten on disk; no migration command is introduced.
   - Acceptance: A golden baseline of `record_id` + `submission_hash` is captured for every existing fixture/staged/outbox record BEFORE the refactor; after the refactor, recomputed values are byte-identical to that baseline for every record, and every file loads without error

5. **Load dispatch contract (supports ESCH-01/03/04)**: Existing `validate_record()` callers are unaffected; experiments load via a separate function.
   - Current: `validate_record(data) -> KajibaRecord` is the only loader, called from `cli.py`, `privacy.py`, `collector.py`
   - Target: `validate_record()` keeps its `KajibaRecord`-only signature and behavior; a separate loader (candidate name `validate_experiment` / `load_record`) handles `ExperimentRecord`. No existing call site is changed.
   - Acceptance: `validate_record()` on a coding-session dict returns a `KajibaRecord` exactly as before; the new experiment loader returns an `ExperimentRecord` for a `model_experiment` dict; a `git diff` shows no behavioral change at the existing `validate_record` call sites

## Boundaries

**In scope:**
- `record_kind` discriminator on a shared base, defaulting to `coding_session`
- Extraction of a shared base model that both `KajibaRecord` and `ExperimentRecord` extend
- New `ExperimentMetadata`, `ExperimentOutcome`, and `ExperimentRecord` models with the locked field sets
- Controlled vocabularies (`tuple` + `Literal`) for `experiment_type` and `recommended_action`
- An optional `trajectory` field on `ExperimentRecord` — declared/reserved only, no population logic
- A separate experiment loader function; `validate_record()` remains `KajibaRecord`-only
- A golden-ID back-compat test over all existing fixtures/staged/outbox records
- JSON round-trip (serialize → validate) for `ExperimentRecord`

**Out of scope:**
- `kajiba experiment` CLI command group — Phase 11 (this phase is schema only)
- Programmatic logging entry point and the private store namespace — Phase 11
- Eval-specific scorer for experiment records — Phase 12
- Scrub tuning that preserves model/hardware fields on experiments — Phase 12
- Reviewer-critique attachment workflow, `lessons_learned` query interface, and drift computation — Phase 13 (this phase only declares the fields)
- Live Hermes capture of experiment runs and any logic that populates the optional `trajectory` — Phase 14
- Analysis/export formats and practice-project integration — Phase 15
- Modifying `ConversationTurn` (e.g. a `reviewer_turn` field) — explicitly excluded (Round 2 decision); reviewer critique is captured flat on `ExperimentOutcome` for now
- Any migration command or rewriting of existing on-disk records — explicitly excluded (Round 2: runtime default only)
- Multi-turn experiment conversation capture logic — the field is reserved; the logic is deferred

## Constraints

- Python 3.11+ and Pydantic v2 only — no new third-party dependencies may be added to `pyproject.toml`
- `KajibaRecord.compute_record_id()` and `compute_submission_hash()` output must remain byte-identical to the pre-refactor implementation
- `ConversationTurn` must not be modified (verified by diff)
- No existing CLI behavior or on-disk file format may change; existing files are never rewritten
- Follow established project conventions: dual `tuple` + `Literal` vocabulary definitions, `Optional[X]` typing (not `X | None`), `model_config = {"populate_by_name": True}` where aliases apply, double-quoted strings, Google-style docstrings, module-level `logger`

## Acceptance Criteria

- [ ] A record dict with no `record_kind` validates and yields `record_kind == "coding_session"`
- [ ] A record dict with `record_kind == "model_experiment"` validates as an `ExperimentRecord`
- [ ] `KajibaRecord` and `ExperimentRecord` both subclass the shared base and inherit `model`, `hardware`, `submission`, `record_id`, `submission_hash`, `created_at`, `schema_version`, and `record_kind`
- [ ] `record_type` and `quality` remain `KajibaRecord`-only (not present on `ExperimentRecord`)
- [ ] A fully populated `ExperimentRecord` round-trips: `model_dump(mode="json", by_alias=True)` → `model_validate` yields an equal record
- [ ] `experiment_type` rejects any value outside `{model_evaluation, routing_test, quality_drift, prompt_ablation}`
- [ ] `recommended_action` rejects any value outside its vocabulary and accepts `None`
- [ ] `lessons_learned` defaults to an empty list and accepts a `list[str]`
- [ ] Every existing fixture/staged/outbox record loads via `validate_record()` without error
- [ ] For every existing record, post-refactor `record_id` and `submission_hash` are byte-identical to a golden baseline captured before the refactor
- [ ] `validate_record()` still returns a `KajibaRecord` for coding-session input; the separate loader returns an `ExperimentRecord` for experiment input
- [ ] `ConversationTurn` is unchanged (diff shows no new/modified fields)
- [ ] The full existing test suite passes with no regressions
- [ ] No new dependency entries are added to `pyproject.toml`

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes                                              |
|--------------------|-------|------|--------|----------------------------------------------------|
| Goal Clarity       | 0.92  | 0.75 | ✓      | Shape, base composition, and vocabularies locked   |
| Boundary Clarity   | 0.92  | 0.70 | ✓      | Explicit phase-by-phase out-of-scope list          |
| Constraint Clarity | 0.88  | 0.65 | ✓      | Back-compat mechanism + stable-ID + no-new-deps    |
| Acceptance Criteria| 0.90  | 0.70 | ✓      | Golden-ID pinning + round-trip + dispatch checks    |
| **Ambiguity**      | 0.09  | ≤0.20| ✓      |                                                    |

Status: ✓ = met minimum, ⚠ = below minimum (planner treats as assumption)

## Interview Log

| Round | Perspective     | Question summary                                  | Decision locked                                                                                                  |
|-------|-----------------|--------------------------------------------------|------------------------------------------------------------------------------------------------------------------|
| 1     | Researcher      | Output shape / base composition / vocabularies   | Flat outcome + optional reserved `trajectory`; base = IDs+model+hardware+submission +created_at+schema_version+record_kind; `quality`/`record_type` stay record-specific; lock both vocabularies |
| 2     | Boundary Keeper | reviewer_turn? migration? lessons_learned shape  | `ConversationTurn` untouched; runtime-default back-compat (no migration command); `lessons_learned` = `list[str]` |
| 3     | Failure Analyst | ID-stability strength / load dispatch            | Golden-pin `record_id`+`submission_hash` before refactor, assert byte-identical; `validate_record` stays `KajibaRecord`-only + separate experiment loader |

---

*Phase: 10-experiment-schema-foundation*
*Spec created: 2026-06-03*
*Next step: /gsd-discuss-phase 10 — implementation decisions (base/loader naming, discriminated-union wiring, golden-fixture mechanics)*
