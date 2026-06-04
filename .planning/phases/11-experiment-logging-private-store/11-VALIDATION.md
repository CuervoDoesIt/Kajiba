---
phase: 11
slug: experiment-logging-private-store
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-03
validated: 2026-06-04
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from 11-RESEARCH.md "Validation Architecture".

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=7.0 + `click.testing.CliRunner` (both already present) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `addopts="-v"`) |
| **Quick run command** | `python -m pytest tests/test_experiment_store.py tests/test_cli_experiment.py tests/test_experiment_exclusion.py -x` |
| **Full suite command** | `python -m pytest` |
| **Estimated runtime** | ~5 seconds (new files); full suite ~15s (baseline 264 passed, 2 yaml-soft-dep skips) |

---

## Sampling Rate

- **After every task commit:** Run the relevant new test file's quick run (e.g. `python -m pytest tests/test_experiment_store.py -x`)
- **After every plan wave:** Run all three new test files (quick run command above)
- **Before `/gsd-verify-work`:** Full suite must be green (`python -m pytest`); the 2 pre-existing yaml-soft-dep skips remain expected
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

> Task IDs are assigned by the planner; rows below map each phase requirement to its
> observable behavior and automated command. The plan-checker / nyquist-auditor binds
> each row to a concrete `{N}-PP-TT` task ID during planning.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 11-01-T2 | store | 1 | ELOG-02 | — | `build_experiment_record(**fields)` returns a valid `ExperimentRecord` | unit | `python -m pytest tests/test_experiment_store.py::test_build_record -x` | ✅ | ✅ green |
| 11-01-T2 | store | 1 | ELOG-02 | — | `log_experiment(record, dir)` writes file, returns path, computes IDs | unit | `python -m pytest tests/test_experiment_store.py::test_log_writes_file -x` | ✅ | ✅ green |
| 11-01-T2 | store | 1 | ELOG-02 | T-integrity | write is atomic (temp+`os.replace`; no `.tmp` left; valid JSON) | unit | `python -m pytest tests/test_experiment_store.py::test_atomic_write -x` | ✅ | ✅ green |
| 11-01-T2 | store | 1 | ELOG-02 | — | re-logging identical content is skipped, returns same path (dedup) | unit | `python -m pytest tests/test_experiment_store.py::test_dedup_skip -x` | ✅ | ✅ green |
| 11-01-T3 | store | 1 | ELOG-02 | — | `from kajiba import log_experiment, build_experiment_record` works (D-07) | unit | `python -m pytest tests/test_experiment_store.py::test_public_exports -x` | ✅ | ✅ green |
| 11-01-T2 | store | 1 | ELOG-03 | T-leak | `log_experiment` refuses a non-`experiments` dir (structural guard, D-13) | unit | `python -m pytest tests/test_experiment_store.py::test_refuses_outbox_dir -x` | ✅ | ✅ green |
| 11-02-T2 | cli | 2 | ELOG-01 | — | `kajiba experiment log --from run.json` writes `exp_<id>.json` + prints success | integration | `python -m pytest tests/test_cli_experiment.py::test_log_from_file -x` | ✅ | ✅ green |
| 11-02-T2 | cli | 2 | ELOG-01 | — | scalar flags (`--score`/`--type`/`--task-category`) override/fill before validation (D-11) | integration | `python -m pytest tests/test_cli_experiment.py::test_log_scalar_overrides -x` | ✅ | ✅ green |
| 11-02-T2 | cli | 2 | ELOG-01 | — | interactive fallback persists with scripted `input=` (D-12) | integration | `python -m pytest tests/test_cli_experiment.py::test_log_interactive -x` | ✅ | ✅ green |
| 11-02-T2 | cli | 2 | ELOG-01 | — | `kajiba experiment list` shows logged runs (read-back) | integration | `python -m pytest tests/test_cli_experiment.py::test_list -x` | ✅ | ✅ green |
| 11-03-T2 | guard | 3 | ELOG-03 | T-leak | `publish` skips `record_kind == "model_experiment"` (active guard, D-13) | integration | `python -m pytest tests/test_experiment_exclusion.py::test_publish_skips_experiment -x` | ✅ | ✅ green |
| 11-03-T2 | guard | 3 | ELOG-03 | T-leak | logged experiment never appears in publish/browse/download output (D-14 regression) | integration | `python -m pytest tests/test_experiment_exclusion.py::test_experiment_absent_from_community_paths -x` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_experiment_store.py` — stubs for ELOG-02 + ELOG-03 structural guard
- [x] `tests/test_cli_experiment.py` — stubs for ELOG-01 (log + list; file / flags / interactive)
- [x] `tests/test_experiment_exclusion.py` — stubs for ELOG-03 active guard + D-14 regression
- [x] `tests/fixtures/experiment_run.example.json` — canonical `--from` fixture (doubles as the documented example)
- [x] Framework install: none needed (pytest + `CliRunner` already present)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live `kajiba experiment log` against a real `~/.hermes/kajiba/experiments/` | ELOG-01 | CliRunner uses an isolated temp dir; a once-off real-home smoke check confirms `_ensure_dirs()` creates `EXPERIMENTS_DIR` on the actual machine | Run `kajiba experiment log --from tests/fixtures/experiment_run.example.json`, confirm `exp_<id>.json` appears under `~/.hermes/kajiba/experiments/` and not under `staging/`/`outbox/` |

*All requirement-level behaviors above have automated verification; the manual check is a defense-in-depth smoke test only.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** validated 2026-06-04 (retroactive audit)

---

## Validation Audit 2026-06-04

Retroactive Nyquist audit of executed Phase 11 (State A — VALIDATION.md existed in
`draft` from planning). All 12 requirement behaviors cross-referenced against the
implemented test files; every test exists and runs green. `TBD` task IDs bound to their
implementing tasks; all rows promoted to ✅ green. No gaps found, so no gsd-nyquist-auditor
spawn was required.

| Metric | Count |
|--------|-------|
| Requirement behaviors mapped | 12 |
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

**Verification command (re-runnable):**
`python -m pytest tests/test_experiment_store.py tests/test_cli_experiment.py tests/test_experiment_exclusion.py -v`
→ 18 passed (12 Phase-11 requirement tests + 6 added by Phase 12 in the shared CLI test file).

**Requirement coverage:** ELOG-01 ✅ · ELOG-02 ✅ · ELOG-03 ✅ — all COVERED with green automated tests.
