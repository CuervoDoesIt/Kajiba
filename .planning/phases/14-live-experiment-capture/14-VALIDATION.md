---
phase: 14
slug: live-experiment-capture
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-06
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `14-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=7.0 (+ pytest-cov >=4.0) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `addopts = "-v"`) |
| **Quick run command** | `python -m pytest tests/test_collector.py -x -q` |
| **Full suite command** | `python -m pytest -q` |
| **Estimated runtime** | ~30 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_collector.py -x -q`
- **After every plan wave:** Run `python -m pytest -q` (must include `test_experiment_store.py`, `test_experiment_exclusion.py`, `test_schema_experiment.py` to confirm no regression in the experiment store/guards)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

> Task IDs are planner-assigned (PLAN.md not yet written at validation-strategy time).
> Each ECAP-01 behavior below MUST land on at least one task's `<automated>` verify.

| Behavior | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|----------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| Opted-in session → exactly ONE `ExperimentRecord` in `EXPERIMENTS_DIR` (finalize-once across N turn-scoped `on_session_end` firings) | TBD | TBD | ECAP-01 | — | One file per session; no orphan `exp_*.json` | unit | `pytest tests/test_collector.py::TestExperimentCapture::test_opted_in_session_writes_one_record -x` | ❌ W0 | ⬜ pending |
| Flag absent → unchanged coding capture (writes `session_*.json` to `STAGING_DIR`, NEVER touches `EXPERIMENTS_DIR`) — no regression | TBD | TBD | ECAP-01 | T-14-priv | Coding path byte-for-byte unchanged when `KAJIBA_EXPERIMENT` unset | unit | `pytest tests/test_collector.py::TestExperimentCapture::test_flag_absent_unchanged_coding_path -x` | ❌ W0 | ⬜ pending |
| Structural parity: live-captured record has same model/metadata/outcome structure as `kajiba experiment log` output (SC#2) | TBD | TBD | ECAP-01 | — | Identical schema shape (allowing populated `trajectory` + `eval_score==0.0`) | unit | `pytest tests/test_collector.py::TestExperimentCapture::test_structural_parity_with_deliberate_log -x` | ❌ W0 | ⬜ pending |
| Field mapping: `task_description`==first user turn, `local_model_output`==last gpt turn, `eval_score`==0.0, `experiment.local_model`==captured metadata, `trajectory` populated | TBD | TBD | ECAP-01 | — | Fields map per D-03..D-06 | unit | `pytest tests/test_collector.py::TestExperimentCapture::test_field_mapping -x` | ❌ W0 | ⬜ pending |
| Experiment mode never writes to `STAGING_DIR`/`OUTBOX_DIR` even in `continuous` contribution_mode (D-08) | TBD | TBD | ECAP-01 | T-14-priv | Private experiment data cannot reach the publish path | unit | `pytest tests/test_collector.py::TestExperimentCapture::test_no_staging_or_outbox_in_experiment_mode -x` | ❌ W0 | ⬜ pending |
| Defensive: zero-turn / interrupted session → no malformed record written (Pitfall 3) | TBD | TBD | ECAP-01 | — | No `exp_*.json` with empty `local_model_output`; no IndexError | unit | `pytest tests/test_collector.py::TestExperimentCapture::test_zero_turn_session_writes_nothing -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_collector.py` — new test class `TestExperimentCapture` covering all six ECAP-01 rows above. Use `monkeypatch.setenv("KAJIBA_EXPERIMENT", "1")` and `monkeypatch.setattr` to point `EXPERIMENTS_DIR`/`STAGING_DIR` at `tmp_path` (mirror the isolation pattern in `tests/test_experiment_store.py`).
- [ ] Shared fixture/helper that drives the collector through `on_session_start` → N×(`on_llm_turn` + `on_session_end`) to simulate the turn-scoped firing (the exact finalize-once scenario). Extend the existing full-lifecycle idiom in `tests/test_collector.py`.
- [ ] Parity assertion helper: build a record via `build_experiment_record` directly (the deliberate-log shape) and assert the live-captured record's `model_dump(by_alias=True)` keys/structure match (allowing `trajectory` populated + `eval_score==0.0`).
- [ ] Framework install: none — pytest already present.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Hermes session with `KAJIBA_EXPERIMENT=1` produces exactly one `exp_*.json` (SC#1 live proof) | ECAP-01 | Requires a real Hermes v0.15.x session; automated tests mock the collector directly | Run a multi-turn-then-exit eval session in live Hermes with `KAJIBA_EXPERIMENT=1`; confirm exactly one `exp_*.json` lands in `EXPERIMENTS_DIR` and nothing in `STAGING_DIR`/`OUTBOX_DIR` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
