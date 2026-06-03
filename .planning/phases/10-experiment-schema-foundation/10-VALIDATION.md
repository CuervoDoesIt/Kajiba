---
phase: 10
slug: experiment-schema-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-03
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `10-RESEARCH.md` § Validation Architecture (HIGH confidence — claims verified against live pydantic 2.12.5 / Python 3.13.3).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest `>=7.0` (+ pytest-cov `>=4.0`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (tests auto-discovered under `tests/`) |
| **Quick run command** | `python -m pytest tests/test_schema_backcompat.py tests/test_schema_experiment.py -x -q` |
| **Full suite command** | `python -m pytest -q` |
| **Estimated runtime** | ~5 seconds (pure in-memory Pydantic validation; no I/O beyond reading repo fixtures) |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_schema_backcompat.py tests/test_schema_experiment.py -x -q`
- **After every plan wave:** Run `python -m pytest -q` (full suite — existing `test_scorer.py` exercises `validate_record()` on fixtures and will catch regressions)
- **Before `/gsd-verify-work`:** Full suite must be green AND `git diff src/kajiba/schema.py` confirms `ConversationTurn` and the `validate_record()` body are unchanged
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

> Task IDs are assigned by the planner. Rows below are keyed by requirement + test so the planner can attach each to the task that delivers it.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD (planner) | — | 0 | ESCH-04 | — | N/A | unit (capture) | `python tests/capture_golden_ids.py` (PRE-refactor; writes `tests/fixtures/golden_ids.json`) | ❌ W0 | ⬜ pending |
| TBD (planner) | — | — | ESCH-04 | — | N/A | unit (golden) | `python -m pytest tests/test_schema_backcompat.py::test_record_id_and_submission_hash_stable -q` | ❌ W0 | ⬜ pending |
| TBD (planner) | — | — | ESCH-04 | — | N/A | unit | `python -m pytest tests/test_schema_backcompat.py::test_legacy_dicts_load -q` | ❌ W0 | ⬜ pending |
| TBD (planner) | — | — | ESCH-01 | — | N/A | unit | `python -m pytest tests/test_schema_backcompat.py::test_record_kind_default -q` | ❌ W0 | ⬜ pending |
| TBD (planner) | — | — | ESCH-02 | — | N/A | unit | `python -m pytest tests/test_schema_backcompat.py::test_base_inheritance -q` | ❌ W0 | ⬜ pending |
| TBD (planner) | — | — | ESCH-03 | — | N/A | unit | `python -m pytest tests/test_schema_experiment.py -q` | ❌ W0 | ⬜ pending |
| TBD (planner) | — | — | Load-dispatch (5th) | — | N/A | unit | `python -m pytest tests/test_schema_backcompat.py::test_load_dispatch -q` | ❌ W0 | ⬜ pending |
| TBD (planner) | — | — | ConversationTurn unchanged | — | N/A | manual/CI | `git diff src/kajiba/schema.py` — inspect `ConversationTurn` block | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/fixtures/golden_ids.json` — **generated from the PRE-refactor schema** over the five `*_trajectory.json` fixtures, committed BEFORE `schema.py` is touched (capture procedure in `10-RESEARCH.md` § Golden Baseline Capture). Exclude `enriched_catalog.json` (publisher catalog, not a `KajibaRecord` — has no `trajectory`).
- [ ] `tests/test_schema_backcompat.py` — golden-ID stability, legacy-dict load, `record_kind` default, base inheritance, load-dispatch (covers ESCH-01 / ESCH-02 / ESCH-04 + 5th)
- [ ] `tests/test_schema_experiment.py` — `ExperimentRecord` JSON round-trip, out-of-vocab rejection, `recommended_action=None` accepted, `lessons_learned` default (covers ESCH-03)
- [ ] Confirm `[tool.pytest.ini_options]` in `pyproject.toml` (absent → pytest still auto-discovers `tests/`; no install needed)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `ConversationTurn` is byte-for-byte unchanged | ESCH-02 boundary | A diff is the ground truth; no runtime assertion proves "the model definition did not change" | `git diff src/kajiba/schema.py` and confirm no add/remove/modify within the `ConversationTurn` class block |
| `validate_record()` call sites unchanged | Load-dispatch (5th) | Behavioral non-change at 6 cli.py + privacy.py + collector.py sites is best confirmed by diff | `git diff src/kajiba/cli.py src/kajiba/privacy.py src/kajiba/collector.py` — confirm no behavioral change at `validate_record(` calls |

---

## Validation Sign-Off

- [ ] All tasks have an `<automated>` verify or a Wave 0 dependency
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (golden baseline + two test modules)
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter once the planner maps every requirement to a task-level automated verify

**Approval:** pending
