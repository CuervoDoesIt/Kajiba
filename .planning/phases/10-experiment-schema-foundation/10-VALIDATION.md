---
phase: 10
slug: experiment-schema-foundation
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-03
validated: 2026-06-04
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `10-RESEARCH.md` § Validation Architecture (HIGH confidence — claims verified against live pydantic 2.12.5 / Python 3.13.3).
> Retroactively audited 2026-06-04 against the executed phase — all requirements COVERED with green automated tests; the draft flags were flipped to compliant.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest `>=7.0` (+ pytest-cov `>=4.0`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (tests auto-discovered under `tests/`) |
| **Quick run command** | `python -m pytest tests/test_schema_backcompat.py tests/test_schema_experiment.py -x -q` |
| **Full suite command** | `python -m pytest -q` |
| **Estimated runtime** | ~5 seconds (pure in-memory Pydantic validation; no I/O beyond reading repo fixtures) |
| **Last audited result** | 20 passed (13 backcompat + 7 experiment); full suite 291 passed, 2 skipped (pre-existing PyYAML soft-dep) |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_schema_backcompat.py tests/test_schema_experiment.py -x -q`
- **After every plan wave:** Run `python -m pytest -q` (full suite — existing `test_scorer.py` exercises `validate_record()` on fixtures and will catch regressions)
- **Before `/gsd-verify-work`:** Full suite must be green AND `git diff src/kajiba/schema.py` confirms `ConversationTurn` and the `validate_record()` body are unchanged
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

> Retroactively keyed to the executed plans. Phase 10 ran Wave 1 (golden baseline capture, 10-01) → Wave 2 (schema refactor, 10-02) → Wave 3 (back-compat + experiment test suites, 10-03). The critical Nyquist ordering requirement — the golden baseline captured **before** `schema.py` was touched — held (baseline committed `85b3866` before schema edits).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | ESCH-04 (baseline) | — | N/A | unit (capture) | `python tests/capture_golden_ids.py` (PRE-refactor; wrote `tests/fixtures/golden_ids.json` over the 5 `*_trajectory.json` fixtures) | ✅ committed pre-refactor (85b3866) | ✅ green |
| 10-03-01 | 03 | 3 | ESCH-04 (ID stability) | — | N/A | unit (golden, ×5 params) | `python -m pytest tests/test_schema_backcompat.py::test_record_id_and_submission_hash_stable -q` | ✅ | ✅ green |
| 10-03-02 | 03 | 3 | ESCH-04 (legacy load) | — | N/A | unit (×5 params) | `python -m pytest tests/test_schema_backcompat.py::test_legacy_dicts_load -q` | ✅ | ✅ green |
| 10-03-03 | 03 | 3 | ESCH-01 | — | N/A | unit | `python -m pytest tests/test_schema_backcompat.py::test_record_kind_default -q` | ✅ | ✅ green |
| 10-03-04 | 03 | 3 | ESCH-02 | — | N/A | unit | `python -m pytest tests/test_schema_backcompat.py::test_base_inheritance -q` | ✅ | ✅ green |
| 10-03-05 | 03 | 3 | ESCH-05 (load dispatch) | — | N/A | unit | `python -m pytest tests/test_schema_backcompat.py::test_load_dispatch -q` | ✅ | ✅ green |
| 10-03-06 | 03 | 3 | ESCH-03 | — | N/A | unit (7 tests) | `python -m pytest tests/test_schema_experiment.py -q` | ✅ | ✅ green |
| 10-02-01 | 02 | 2 | ESCH-02 / ESCH-05 boundary | — | N/A | manual/CI (diff) | `git diff src/kajiba/schema.py` — `ConversationTurn` block + `validate_record()` body unchanged | n/a | ✅ verified (10-VERIFICATION) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Nyquist continuity check:** No 3 consecutive tasks lack an automated verify — every requirement-bearing task above has an `<automated>` command, all confirmed green on audit. The lone manual/CI row (boundary non-change) is a diff-confirmed invariant, not a behavioral gap.

**Test name inventory (audit cross-reference):**

- `tests/test_schema_backcompat.py` (ESCH-01/02/04/05): `test_record_id_and_submission_hash_stable` (×5 params), `test_legacy_dicts_load` (×5 params), `test_record_kind_default`, `test_base_inheritance`, `test_load_dispatch` → 13 cases
- `tests/test_schema_experiment.py` (ESCH-03): `test_round_trip`, `test_record_kind_is_model_experiment`, `test_experiment_type_rejects_out_of_vocab`, `test_recommended_action_rejects_out_of_vocab`, `test_recommended_action_none_accepted`, `test_lessons_learned_defaults_empty`, `test_eval_score_bounds` → 7 cases

---

## Wave 0 Requirements

- [x] `tests/fixtures/golden_ids.json` — **generated from the PRE-refactor schema** over the five `*_trajectory.json` fixtures, committed BEFORE `schema.py` was touched (`85b3866`, pre-edit). `enriched_catalog.json` excluded (publisher catalog, not a `KajibaRecord`). — *Plan 10-01*
- [x] `tests/test_schema_backcompat.py` — golden-ID stability, legacy-dict load, `record_kind` default, base inheritance, load-dispatch (covers ESCH-01 / ESCH-02 / ESCH-04 / ESCH-05) — *Plan 10-03*
- [x] `tests/test_schema_experiment.py` — `ExperimentRecord` JSON round-trip, out-of-vocab rejection, `recommended_action=None` accepted, `lessons_learned` default, `eval_score` bounds (covers ESCH-03) — *Plan 10-03*
- [x] Confirm `[tool.pytest.ini_options]` in `pyproject.toml` (present; tests auto-discovered under `tests/`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `ConversationTurn` is byte-for-byte unchanged | ESCH-02 boundary | A diff is the ground truth; no runtime assertion proves "the model definition did not change" | `git diff src/kajiba/schema.py` and confirm no add/remove/modify within the `ConversationTurn` class block — confirmed in 10-VERIFICATION |
| `validate_record()` call sites unchanged | ESCH-05 (load dispatch) | Behavioral non-change at the cli.py + privacy.py + collector.py call sites is best confirmed by diff | `git diff src/kajiba/cli.py src/kajiba/privacy.py src/kajiba/collector.py` — confirm no behavioral change at `validate_record(` calls — confirmed in 10-VERIFICATION |

*Both manual items are diff-confirmed invariants (already verified in 10-VERIFICATION.md), not unverified functional behavior.*

---

## Validation Sign-Off

- [x] All tasks have an `<automated>` verify or a Wave 0 dependency
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (golden baseline + two test modules)
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter — every requirement maps to a task-level automated verify
- [x] Retroactive audit confirms all tasks COVERED (green) — 2026-06-04

**Approval:** planner-approved 2026-06-03; retroactively audited & confirmed nyquist-compliant 2026-06-04 (post-execution).

---

## Validation Audit 2026-06-04

| Metric | Count |
|--------|-------|
| Tasks audited | 8 |
| COVERED (green) | 8 |
| PARTIAL | 0 |
| MISSING | 0 |
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

**Method:** Cross-referenced every per-task automated command in the validation map against the executed codebase, confirming each referenced test node exists with the exact name specified, then re-ran them. `tests/test_schema_backcompat.py` + `tests/test_schema_experiment.py` → 20 passed (13 + 7); the 5 explicitly-named backcompat node IDs all resolve and pass; `tests/capture_golden_ids.py` and `tests/fixtures/golden_ids.json` present (baseline committed pre-refactor). Full suite: 291 passed, 2 skipped (pre-existing PyYAML soft-dep). No test files generated — coverage was already complete; this audit only flipped the stale draft flags (`status: draft → validated`, `nyquist_compliant: false → true`, `wave_0_complete: false → true`) that were never updated after execution.
