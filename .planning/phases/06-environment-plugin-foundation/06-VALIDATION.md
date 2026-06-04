---
phase: 6
slug: environment-plugin-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-04
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `06-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 7.0 `[VERIFIED: pyproject.toml:35]` |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=["tests"], addopts="-v") |
| **Quick run command** | `python -m pytest tests/test_config.py tests/test_collector.py -x` |
| **Full suite command** | `python -m pytest` |
| **Estimated runtime** | ~15 seconds (unit suite; live checkpoints excluded) |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_config.py tests/test_collector.py -x`
- **After every plan wave:** Run `python -m pytest`
- **Before `/gsd-verify-work`:** Full suite must be green AND live manual checkpoints recorded in `06-HOOK-KWARGS.md`
- **Max feedback latency:** 20 seconds (unit); live checkpoints are out-of-band (require WSL2 env)

---

## Per-Task Verification Map

> Task IDs are assigned by the planner; rows below are keyed by requirement + behavior and
> the planner MUST map each task to the matching automated command (or to a manual checkpoint).

| Behavior | Requirement | Test Type | Automated Command | File Exists | Status |
|----------|-------------|-----------|-------------------|-------------|--------|
| `get_hermes_home()` returns `$HERMES_HOME` when set, `~/.hermes` when unset | PLUG-03 | unit | `pytest tests/test_config.py::test_get_hermes_home_env -x` | ❌ W0 | ⬜ pending |
| All path constants resolve under a temp `HERMES_HOME` | PLUG-03 | unit | `pytest tests/test_config.py -k hermes_home -x` | ❌ W0 | ⬜ pending |
| `cli.EXPERIMENTS_DIR == experiment_store.EXPERIMENTS_DIR` parity holds after migration | PLUG-03 | unit | `pytest tests/test_experiment_store.py::test_experiments_dir_matches_cli -x` | ✅ (must stay green) | ⬜ pending |
| `hermes_integration` module gone; no import references remain | ENV (D-07) | unit/static | `pytest tests/ -x` + grep guard for `import.*hermes_integration` | ✅ (full suite) | ⬜ pending |
| Collector standalone; `on_session_start` still accepts positional `model_config` dict | ENV (D-08) | unit | `pytest tests/test_collector.py -x` | ✅ (must stay green) | ⬜ pending |
| `register(ctx)` registers 4 hooks against a stub `ctx` | PLUG-02 | unit | `pytest tests/test_plugin.py::test_register_hooks -x` | ❌ W0 | ⬜ pending |
| Each hook handler tolerates an unexpected extra kwarg (no exception) | PLUG-02 / MP-2 | unit | `pytest tests/test_plugin.py::test_handlers_accept_extra_kwarg -x` | ❌ W0 | ⬜ pending |
| `KAJIBA_DEBUG=1` makes handlers log kwarg names/types | CAPT-01 | unit | `pytest tests/test_plugin.py::test_debug_logging -x` (caplog) | ❌ W0 | ⬜ pending |
| Hermes loads plugin; `on_session_start` fires | PLUG-01/02 (live) | manual checkpoint | `KAJIBA_DEBUG=1` Hermes session, observe log | N/A — live env | ⬜ pending |
| Real kwargs captured for all 4 hooks | CAPT-01 (live) | manual checkpoint | run session, record in `06-HOOK-KWARGS.md` | N/A — live env | ⬜ pending |
| WSL2 + GPU + Ollama + Hermes verified | ENV-01/02 (live) | manual checkpoint | guide verification steps (nvidia-smi VRAM, ollama run, plugin loads) | N/A — live env | ⬜ pending |
| Symlink dev workflow loads plugin | ENV-03 (live) | manual checkpoint | symlink + restart Hermes | N/A — live env | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_config.py` — add `get_hermes_home()` cases (env set / unset / temp dir isolation) covering PLUG-03
- [ ] `tests/test_plugin.py` — NEW: `register(ctx)` against stub ctx, `**kwargs` tolerance, `KAJIBA_DEBUG` logging (PLUG-01/02, CAPT-01, MP-2)
- [ ] Stub `ctx` fixture (records `register_hook` calls) — in `tests/conftest.py` or inline in `test_plugin.py`
- [ ] Grep/static guard test that no source file imports `hermes_integration` (locks D-07)
- [ ] Path-migration tests for `cli.py` / `publisher.py` / `experiment_store.py` constants under temp `HERMES_HOME` (or confirm lazy-eval makes existing tests sufficient)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Plugin loads in live Hermes; 4 hooks fire | PLUG-01/02, CAPT-01 | Requires running Hermes v0.6.0 + Ollama in WSL2 — cannot be unit-tested | Set `KAJIBA_DEBUG=1`, start a Hermes session, observe hook logs; record real kwargs in `06-HOOK-KWARGS.md` |
| GPU acceleration verified | ENV-01/02 | Requires live WSL2 + NVIDIA passthrough | Follow `docs/hermes-setup.md` checkpoints: `nvidia-smi` shows VRAM, `ollama run` uses GPU |
| Symlink edit-reload dev cycle | ENV-03 | Requires live Hermes plugin discovery | Symlink `~/.hermes/plugins/kajiba/` → `src/kajiba/plugin/`, restart Hermes, confirm load |

> These map to success criteria 1, 2, 3, 5 and are gated on the developer completing the env-setup tasks. The planner MUST mark them as `checkpoint:human-verify` tasks (`autonomous: false`), not automated verifies.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (live behaviors marked manual-checkpoint)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
