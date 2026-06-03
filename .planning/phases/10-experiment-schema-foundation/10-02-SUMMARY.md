---
phase: 10-experiment-schema-foundation
plan: 02
subsystem: schema
tags: [pydantic, base-class-extraction, record-kind, experiment-record, content-hash, back-compat, sha256]

# Dependency graph
requires:
  - phase: 10-01
    provides: tests/fixtures/golden_ids.json (immutable ESCH-04 baseline)
  - phase: existing v1.0 schema
    provides: KajibaRecord, validate_record, compute_record_id, compute_submission_hash, ModelMetadata, Trajectory
provides:
  - RecordBase shared base model (schema_version, record_id, submission_hash, created_at, record_kind, model, hardware, submission)
  - KajibaRecord(RecordBase) — reparented, hash methods frozen, legacy hashes byte-identical
  - ExperimentMetadata, ExperimentOutcome, ExperimentRecord(RecordBase) family
  - record_kind / experiment_type / recommended_action dual vocabularies
  - load_record() manual dispatch factory (record_kind, default coding_session)
  - SCHEMA_VERSION bumped 0.1.0 -> 0.2.0
affects: [10-03 back-compat + experiment tests, Phase 11 dual-use eval-logging]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared base + record-specific tails: RecordBase holds cross-kind identity/metadata; each record adds its own payload"
    - "Manual factory dispatch on record_kind (NOT a discriminated union) for legacy-dict back-compat"
    - "Per-subclass compute_* overrides (not abstract on base) so the two hash payloads stay decoupled"
    - "Frozen hash methods: KajibaRecord.compute_* left byte-for-byte unchanged to preserve content-addressable IDs"

key-files:
  created: []
  modified:
    - src/kajiba/schema.py
    - tests/test_schema.py

key-decisions:
  - "Experiment-id format LOCKED: kajiba_exp_<first 12 hex> over json.dumps(sort_keys=True, ensure_ascii=True) of {experiment_id, task_description, local_model_name, local_model_output, started_at} with started_at serialized via .isoformat()"
  - "ExperimentRecord.compute_submission_hash() IS computed (sha256:<hex>) over the same experiment-identity payload — local dedup only, never publishes"
  - "load_record() uses data.get('record_kind', 'coding_session') manual branch; Field(discriminator=...) rejected (union_tag_not_found on legacy dicts)"
  - "model_config = {populate_by_name: True} declared once on RecordBase; subclasses inherit (not re-declared — Pydantic overrides wholesale)"
  - "validate_turn_count / validate_tool_call_counts stay on KajibaRecord (reference self.trajectory); not attached to ExperimentRecord"
  - "test_schema gold-tier assertion decoupled from the live SCHEMA_VERSION constant — legacy fixtures keep their stored 0.1.0 value (D-07, records never rewritten)"

requirements-completed: [ESCH-01, ESCH-02, ESCH-03, ESCH-05]

# Metrics
duration: 14min
completed: 2026-06-03
---

# Phase 10 Plan 02: Experiment Schema Refactor Summary

**Extracted RecordBase, reparented KajibaRecord onto it without perturbing a single legacy hash, added the ExperimentRecord family (ExperimentMetadata/ExperimentOutcome/ExperimentRecord) with a kajiba_exp_ content-hash identity, and added a manual load_record() dispatch factory — all five golden record_id/submission_hash values remain byte-identical (ESCH-04 confirmed).**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-06-03
- **Completed:** 2026-06-03
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- **Task 1** — Bumped `SCHEMA_VERSION` `0.1.0` -> `0.2.0` (single shared constant, no `EXPERIMENT_SCHEMA_VERSION`). Added three dual vocabularies (`RECORD_KINDS`/`RecordKindType`, `EXPERIMENT_TYPES`/`ExperimentTypeType`, `RECOMMENDED_ACTIONS`/`RecommendedActionType`) using the exact locked SPEC R3 values (`route_to_reviewer`, not `route_to_grok`). Extracted `RecordBase(BaseModel)` carrying the eight shared fields + `record_kind` default `coding_session` + `model_config` once.
- **Task 2** — Reparented `class KajibaRecord(RecordBase)`. Removed the seven now-inherited base fields and the redundant `model_config`; kept `record_type`, `trajectory`, `outcome`, `pain_points`, `quality`, both `@model_validator`s, `to_sharegpt`, `to_dpo_candidate`, and both `compute_*` methods byte-for-byte unchanged.
- **Task 3** — Added `ExperimentMetadata`, `ExperimentOutcome`, and `ExperimentRecord(RecordBase)` with the locked field sets; gave `ExperimentRecord` its own `compute_record_id()` (`kajiba_exp_<12hex>`) and `compute_submission_hash()` (`sha256:<hex>`) over the experiment-identity payload with `started_at.isoformat()`. Added the `load_record()` manual dispatch factory and imported `Union`.

## ESCH-04 Back-Compat Confirmation (CRITICAL)

After the full refactor, the post-refactor schema was run against the SAME five fixtures and compared to the immutable `tests/fixtures/golden_ids.json` baseline (NOT regenerated):

| Fixture | record_id | submission_hash | Match |
|---------|-----------|-----------------|-------|
| adversarial_trajectory.json | kajiba_c9a682a0f395 | sha256:5c6461...210b4b | IDENTICAL |
| gold_trajectory.json | kajiba_40f6331f7ff1 | sha256:da289e...d4f654c | IDENTICAL |
| minimal_trajectory.json | kajiba_c2eac32fcdc4 | sha256:52b1ed...91e87bfa | IDENTICAL |
| pii_trajectory.json | kajiba_6ce9ef1a3c39 | sha256:9e7f5b...4e4f9b63df | IDENTICAL |
| silver_trajectory.json | kajiba_5fcc0553f6e8 | sha256:29fbd7...febfe63181f | IDENTICAL |

**Result: ALL 5 GOLDEN HASHES BYTE-IDENTICAL.** `golden_ids.json` was never overwritten or committed — it was read-only ground truth.

Locked experiment-id format (for Phase 11 consumers): `kajiba_exp_<first 12 hex of sha256>` over `json.dumps({experiment_id, task_description, local_model_name, local_model_output, started_at}, sort_keys=True, ensure_ascii=True)` with `started_at` serialized via `.isoformat()`.

## Frozen Boundaries (verified via git diff)

- `KajibaRecord.compute_record_id()` / `compute_submission_hash()` bodies — unchanged.
- `validate_record()` — unchanged (`-> KajibaRecord`, `return KajibaRecord.model_validate(data)`).
- `ConversationTurn` (including the `from`/`from_` alias) — unchanged.
- `load_record()` does NOT use `Field(discriminator=...)`.

## New Symbols

- Constants/vocabs: `RECORD_KINDS`, `RecordKindType`, `EXPERIMENT_TYPES`, `ExperimentTypeType`, `RECOMMENDED_ACTIONS`, `RecommendedActionType`.
- Models: `RecordBase`, `ExperimentMetadata`, `ExperimentOutcome`, `ExperimentRecord`.
- Function: `load_record(data) -> Union[KajibaRecord, ExperimentRecord]`.
- Modified: `KajibaRecord` now subclasses `RecordBase`; `Union` added to the `typing` import; `SCHEMA_VERSION = "0.2.0"`.

## Task Commits

1. **Task 1: Bump SCHEMA_VERSION, add dual vocabularies, extract RecordBase** - `fa0d4bf` (feat)
2. **Task 2: Reparent KajibaRecord onto RecordBase (hashes frozen)** - `05d08ec` (refactor)
3. **Task 3: Add ExperimentRecord family + load_record() factory** - `89152eb` (feat)

## Decisions Made

All locked technical decisions (D-01 through D-08, plus the experiment-id `.isoformat()` lock) were implemented as specified. See frontmatter `key-decisions`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_schema gold-tier assertion coupled to the live SCHEMA_VERSION constant**
- **Found during:** Task 3 (full-suite run after the refactor)
- **Issue:** `tests/test_schema.py::TestValidRecords::test_gold_tier_record` asserted `record.schema_version == SCHEMA_VERSION`. The `gold_trajectory.json` fixture stores `"schema_version": "0.1.0"` (a legacy record, never rewritten per D-07), but the constant is now `"0.2.0"` — so the assertion failed by construction after the Task 1 bump.
- **Fix:** Changed the assertion to `record.schema_version == data["schema_version"]` (asserts the stored value round-trips) and removed the now-unused `SCHEMA_VERSION` import. This keeps the test meaningful (schema_version is preserved on load) and decouples it from the live constant.
- **Files modified:** tests/test_schema.py
- **Commit:** `89152eb`

This was in scope — a regression directly caused by this plan's SCHEMA_VERSION bump.

## Verification

- `python -c "import kajiba.schema"` succeeds; `SCHEMA_VERSION == "0.2.0"`.
- `issubclass(KajibaRecord, RecordBase)` and `issubclass(ExperimentRecord, RecordBase)` both True.
- All five golden hashes byte-identical to the 10-01 baseline (ESCH-04).
- Dict without `record_kind` -> `coding_session`; `model_experiment` dict -> `ExperimentRecord` via `load_record`; `validate_record` still -> `KajibaRecord`.
- `ExperimentRecord` round-trips `model_dump(mode="json", by_alias=True)` -> `model_validate` (equal).
- Out-of-vocab `experiment_type` / `recommended_action` raise `ValidationError`; `recommended_action=None` accepted; `lessons_learned` defaults to `[]`.
- Full existing suite: **244 passed, 2 skipped**.
- No new dependency added to `pyproject.toml`.

## Known Stubs

`ExperimentRecord.trajectory: Optional[Trajectory] = None` is a RESERVED field with no population logic this phase (declared only). This is intentional per the locked decision — it is reserved for a later phase and carries no validators. Not a blocking stub.

## Threat Flags

None. No new network endpoint, auth path, or publish path was introduced. The experiment-record privacy boundary (T-10-06) is preserved: this phase is schema-only with no publish/browse/download path.

## User Setup Required

None — no external service configuration; zero dependencies added.

## Next Phase Readiness

- Plan 10-03 can now write `tests/test_schema_backcompat.py` (golden-ID, legacy-load, record_kind default, base-inheritance, load-dispatch) and `tests/test_schema_experiment.py` (round-trip, vocab rejection, `recommended_action=None`) against the now-refactored schema.
- Phase 11 can consume `ExperimentRecord` and the locked `kajiba_exp_` id format.

## Self-Check: PASSED

- FOUND: src/kajiba/schema.py (RecordBase, ExperimentRecord, load_record present)
- FOUND: tests/test_schema.py (modified)
- FOUND commit: fa0d4bf (Task 1)
- FOUND commit: 05d08ec (Task 2)
- FOUND commit: 89152eb (Task 3)

---
*Phase: 10-experiment-schema-foundation*
*Completed: 2026-06-03*
