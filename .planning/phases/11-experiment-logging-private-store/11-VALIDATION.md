---
phase: 11
slug: experiment-logging-private-store
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-03
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
| TBD | store | — | ELOG-02 | — | `build_experiment_record(**fields)` returns a valid `ExperimentRecord` | unit | `python -m pytest tests/test_experiment_store.py::test_build_record -x` | ❌ W0 | ⬜ pending |
| TBD | store | — | ELOG-02 | — | `log_experiment(record, dir)` writes file, returns path, computes IDs | unit | `python -m pytest tests/test_experiment_store.py::test_log_writes_file -x` | ❌ W0 | ⬜ pending |
| TBD | store | — | ELOG-02 | T-integrity | write is atomic (temp+`os.replace`; no `.tmp` left; valid JSON) | unit | `python -m pytest tests/test_experiment_store.py::test_atomic_write -x` | ❌ W0 | ⬜ pending |
| TBD | store | — | ELOG-02 | — | re-logging identical content is skipped, returns same path (dedup) | unit | `python -m pytest tests/test_experiment_store.py::test_dedup_skip -x` | ❌ W0 | ⬜ pending |
| TBD | store | — | ELOG-02 | — | `from kajiba import log_experiment, build_experiment_record` works (D-07) | unit | `python -m pytest tests/test_experiment_store.py::test_public_exports -x` | ❌ W0 | ⬜ pending |
| TBD | store | — | ELOG-03 | T-leak | `log_experiment` refuses a non-`experiments` dir (structural guard, D-13) | unit | `python -m pytest tests/test_experiment_store.py::test_refuses_outbox_dir -x` | ❌ W0 | ⬜ pending |
| TBD | cli | — | ELOG-01 | — | `kajiba experiment log --from run.json` writes `exp_<id>.json` + prints success | integration | `python -m pytest tests/test_cli_experiment.py::test_log_from_file -x` | ❌ W0 | ⬜ pending |
| TBD | cli | — | ELOG-01 | — | scalar flags (`--score`/`--type`/`--task-category`) override/fill before validation (D-11) | integration | `python -m pytest tests/test_cli_experiment.py::test_log_scalar_overrides -x` | ❌ W0 | ⬜ pending |
| TBD | cli | — | ELOG-01 | — | interactive fallback persists with scripted `input=` (D-12) | integration | `python -m pytest tests/test_cli_experiment.py::test_log_interactive -x` | ❌ W0 | ⬜ pending |
| TBD | cli | — | ELOG-01 | — | `kajiba experiment list` shows logged runs (read-back) | integration | `python -m pytest tests/test_cli_experiment.py::test_list -x` | ❌ W0 | ⬜ pending |
| TBD | guard | — | ELOG-03 | T-leak | `publish` skips `record_kind == "model_experiment"` (active guard, D-13) | integration | `python -m pytest tests/test_experiment_exclusion.py::test_publish_skips_experiment -x` | ❌ W0 | ⬜ pending |
| TBD | guard | — | ELOG-03 | T-leak | logged experiment never appears in publish/browse/download output (D-14 regression) | integration | `python -m pytest tests/test_experiment_exclusion.py::test_experiment_absent_from_community_paths -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_experiment_store.py` — stubs for ELOG-02 + ELOG-03 structural guard
- [ ] `tests/test_cli_experiment.py` — stubs for ELOG-01 (log + list; file / flags / interactive)
- [ ] `tests/test_experiment_exclusion.py` — stubs for ELOG-03 active guard + D-14 regression
- [ ] `tests/fixtures/experiment_run.example.json` — canonical `--from` fixture (doubles as the documented example)
- [ ] Framework install: none needed (pytest + `CliRunner` already present)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live `kajiba experiment log` against a real `~/.hermes/kajiba/experiments/` | ELOG-01 | CliRunner uses an isolated temp dir; a once-off real-home smoke check confirms `_ensure_dirs()` creates `EXPERIMENTS_DIR` on the actual machine | Run `kajiba experiment log --from tests/fixtures/experiment_run.example.json`, confirm `exp_<id>.json` appears under `~/.hermes/kajiba/experiments/` and not under `staging/`/`outbox/` |

*All requirement-level behaviors above have automated verification; the manual check is a defense-in-depth smoke test only.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
