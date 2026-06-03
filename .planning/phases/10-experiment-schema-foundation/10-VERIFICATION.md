---
phase: 10-experiment-schema-foundation
verified: 2026-06-03T00:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Phase 10: Experiment Schema Foundation Verification Report

**Phase Goal:** A separate `ExperimentRecord` type exists on a shared base with a `record_kind` discriminator, and all existing records keep working.
**Verified:** 2026-06-03
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth (Success Criterion) | Status | Evidence |
|---|---------------------------|--------|----------|
| 1 | `record_kind` field distinguishes coding-session and model-experiment records and defaults to `coding_session` when omitted (ESCH-01) | ✓ VERIFIED | `RecordBase.record_kind: RecordKindType = "coding_session"` (schema.py:278). Independent run: all 5 legacy fixtures (which omit `record_kind`) load with `record_kind == 'coding_session'`. `ExperimentRecord.record_kind` defaults to `"model_experiment"` (schema.py:440). `test_record_kind_default` + `test_record_kind_is_model_experiment` green. |
| 2 | `KajibaRecord` and `ExperimentRecord` share a common base holding model metadata, hardware profile, scrub log, and IDs (ESCH-02) | ✓ VERIFIED | `class RecordBase(BaseModel)` (schema.py:265) holds `schema_version, record_id, submission_hash, created_at, record_kind, model, hardware, submission`. Scrub log reachable via `submission.scrub_log` (SubmissionMetadata.scrub_log, schema.py:257). Independent run: `issubclass(KajibaRecord, RecordBase)` and `issubclass(ExperimentRecord, RecordBase)` both True. `record_type`/`quality` correctly absent from ExperimentRecord (independently confirmed). `test_base_inheritance` green. |
| 3 | `ExperimentRecord` constructs with experiment metadata + outcome and round-trips through JSON (ESCH-03) | ✓ VERIFIED | `ExperimentMetadata`, `ExperimentOutcome`, `ExperimentRecord` exist with locked field sets (schema.py:408–492). Independent run: `model_dump(mode='json', by_alias=True)` → `model_validate` yields equal record; `record_id` is `kajiba_exp_<12hex>`; `submission_hash` is `sha256:<hex>`; out-of-vocab `experiment_type`/`recommended_action` rejected; `recommended_action=None` accepted; `lessons_learned` defaults `[]`. `eval_score` bounds enforced (0.0–1.0). All 7 experiment tests green. |
| 4 | All existing fixtures load without error and produce identical record/submission IDs to before the refactor (ESCH-04) | ✓ VERIFIED | Independently recomputed `compute_record_id()` + `compute_submission_hash()` for all 5 `*_trajectory.json` fixtures from the LIVE post-refactor schema and compared to `tests/fixtures/golden_ids.json` — ALL 5 byte-identical (record_id AND submission_hash). Golden baseline committed (`85b3866`) BEFORE schema edits (`fa0d4bf`/`05d08ec`/`89152eb`), so the guarantee is falsifiable. `test_record_id_and_submission_hash_stable` (5 params) + `test_legacy_dicts_load` green. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/kajiba/schema.py` | RecordBase, KajibaRecord(RecordBase), ExperimentRecord family, load_record(), bumped SCHEMA_VERSION | ✓ VERIFIED | All present and substantive (536 lines). `SCHEMA_VERSION = "0.2.0"`; no `EXPERIMENT_SCHEMA_VERSION`. Imported/used by tests, cli, collector, privacy. |
| `tests/fixtures/golden_ids.json` | Pre-refactor baseline for 5 fixtures | ✓ VERIFIED | Exactly 5 `*_trajectory.json` keys; `enriched_catalog.json` excluded. Committed before refactor. |
| `tests/capture_golden_ids.py` | Reproducible baseline capture script | ✓ VERIFIED | Exists; imports `validate_record`; globs `*_trajectory.json`. |
| `tests/test_schema_backcompat.py` | ESCH-01/02/04/05 tests | ✓ VERIFIED | 13 collected cases, all green; parametrized golden tripwire over `golden_ids.json`. |
| `tests/test_schema_experiment.py` | ESCH-03 tests | ✓ VERIFIED | 7 cases, all green. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| KajibaRecord | RecordBase | subclass | ✓ WIRED | `class KajibaRecord(RecordBase)` (schema.py:286); issubclass True |
| ExperimentRecord | RecordBase | subclass | ✓ WIRED | `class ExperimentRecord(RecordBase)` (schema.py:432); issubclass True |
| load_record | KajibaRecord / ExperimentRecord | manual branch on record_kind | ✓ WIRED | `data.get("record_kind", "coding_session")` manual factory (schema.py:532); NO `Field(discriminator=...)` (only docstring mention). Dispatch verified both directions. |
| test_schema_backcompat | golden_ids.json | parametrized read | ✓ WIRED | `GOLDEN = json.loads(... golden_ids.json ...)` parametrized over keys. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite | `python -m pytest -q` | 264 passed, 2 skipped (pre-existing yaml-import skips, unrelated) | ✓ PASS |
| Golden ID recompute (independent) | direct python over 5 fixtures vs golden_ids.json | all 5 byte-identical | ✓ PASS |
| ExperimentRecord round-trip + vocab + dispatch | direct python | round_trip equal; vocab rejected; dispatch correct | ✓ PASS |
| Constraint: ConversationTurn unchanged | `git diff e1bae76 HEAD -- schema.py` | no changes to ConversationTurn block | ✓ PASS |
| Constraint: KajibaRecord compute_* / validate_record unchanged | git diff | no hash-content or validate_record return lines removed | ✓ PASS |
| Constraint: no new deps | `git diff -- pyproject.toml` | empty | ✓ PASS |

### Probe Execution

No probes declared for this schema/library phase. Behavioral verification performed via direct Python invocation (above).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ESCH-01 | 10-02, 10-03 | record_kind discriminator, defaults coding_session | ✓ SATISFIED | Truth 1 |
| ESCH-02 | 10-02, 10-03 | Shared base model | ✓ SATISFIED | Truth 2 |
| ESCH-03 | 10-02, 10-03 | ExperimentRecord metadata + outcome + round-trip | ✓ SATISFIED | Truth 3 |
| ESCH-04 | 10-01, 10-03 | Back-compat with stable IDs | ✓ SATISFIED | Truth 4 (independent recompute) |
| ESCH-05 | 10-02, 10-03 | Load dispatch contract (plan-internal, not a formal REQUIREMENTS.md ID) | ✓ SATISFIED | load_record/validate_record split verified |

No orphaned requirements: REQUIREMENTS.md maps only ESCH-01..04 to Phase 10, all marked Complete and independently verified. ESCH-05 is a plan-internal supporting requirement (correctly absent from the formal list).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER in any modified file | — | — |

`ExperimentRecord.trajectory: Optional[Trajectory] = None` (schema.py:443) is a reserved field declared with no population logic — this is explicitly in-scope per SPEC R3 ("declared/reserved only — no capture or population logic in this phase"), NOT a gap.

### Human Verification Required

None. All success criteria are programmatically verifiable (schema behavior, content hashes, JSON round-trip) and were independently confirmed. No visual/UX/real-time/external-service surface in this phase.

### Gaps Summary

No gaps. All 4 success criteria are independently verified against the live `src/kajiba/schema.py` — not merely accepted from SUMMARY.md. The critical ESCH-04 back-compat guarantee was independently re-derived: all 5 fixtures produce byte-identical record_id and submission_hash from the post-refactor schema, and the golden baseline was provably committed before the schema was touched. All phase constraints (ConversationTurn frozen, KajibaRecord hash bodies frozen, validate_record unchanged, no discriminated union, no new dependencies) hold. Full suite: 264 passed, 2 skipped (pre-existing, unrelated).

---

_Verified: 2026-06-03_
_Verifier: Claude (gsd-verifier)_
