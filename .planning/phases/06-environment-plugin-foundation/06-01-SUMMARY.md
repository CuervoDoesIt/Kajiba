---
phase: 06-environment-plugin-foundation
plan: 01
subsystem: testing
tags: [wave-0, test-scaffold, nyquist, plugin, hermes]
requires:
  - "Existing tests/test_config.py with fake_home fixture"
  - "src/kajiba/hermes_integration.py present (guard target, deleted in Plan 02)"
provides:
  - "tests/test_config.py::TestGetHermesHome — RED scaffold for get_hermes_home() (Plan 02)"
  - "tests/test_plugin.py — RED scaffold + StubCtx fixture for register(ctx)/hooks (Plan 03)"
  - "tests/test_no_hermes_integration.py — D-07 static guard locking the deletion (Plan 02)"
affects:
  - "Plan 02 (get_hermes_home + hermes_integration deletion) lands against these tests"
  - "Plan 03 (kajiba.plugin package) lands against test_plugin.py"
tech-stack:
  added: []
  patterns:
    - "Deferred imports inside test bodies so RED files still collect"
    - "Static source-scan guard via abs path from __file__ (cwd/Windows-safe)"
    - "Patch module-level _DEBUG attribute instead of setenv-after-import"
key-files:
  created:
    - tests/test_plugin.py
    - tests/test_no_hermes_integration.py
  modified:
    - tests/test_config.py
decisions:
  - "Did NOT modify the importorskip('yaml') line; PyYAML temporarily installed only to OBSERVE the collection/RED acceptance criteria for test_config.py, then uninstalled to restore the dev-machine baseline (the 2 pre-existing yaml-soft-dep skips)."
metrics:
  duration: ~3m
  completed: 2026-06-04
---

# Phase 6 Plan 01: Wave 0 Test Scaffolds Summary

RED test scaffolds for the three Phase 6 code surfaces (get_hermes_home, the kajiba.plugin package, and the hermes_integration deletion guard), each failing only on a not-yet-built symbol or a not-yet-deleted module — never on existing-suite breakage.

## What Was Built

**Task 1 — `tests/test_config.py::TestGetHermesHome` (commit d4ac6ea)**
Added three named tests with deferred `from kajiba.config import get_hermes_home`:
- `test_get_hermes_home_env` — `monkeypatch.setenv("HERMES_HOME", str(tmp_path))` → asserts `get_hermes_home() == tmp_path`.
- `test_get_hermes_home_unset` — reuses existing `fake_home` fixture + `monkeypatch.delenv("HERMES_HOME", raising=False)` → asserts `get_hermes_home() == fake_home / ".hermes"`.
- `test_hermes_home_isolation_under_temp` — path-constant isolation test (name contains `hermes_home`) asserting a derived `kajiba` base resolves under the temp HERMES_HOME.

**Task 2 — `tests/test_plugin.py` (NEW, commit 0686ab5)**
`StubCtx` class with `register_hook(event, callback)` recording into `self.hooks`, plus a `stub_ctx` fixture. Three named tests with deferred imports from `kajiba.plugin` / `kajiba.plugin.hooks`:
- `test_register_hooks` — asserts all four event keys present: `on_session_start`, `post_llm_call`, `post_tool_call`, `on_session_end`.
- `test_handlers_accept_extra_kwarg` — calls each of the four handlers with an unexpected `surprise=` kwarg, asserting no exception (MP-2 tolerance).
- `test_debug_logging` — patches `kajiba.plugin.hooks._DEBUG` (NOT setenv-after-import) and asserts a `KAJIBA_DEBUG` warning record via `caplog`.

**Task 3 — `tests/test_no_hermes_integration.py` (NEW, commit 84037bf)**
D-07 static guard:
- `test_no_source_imports_hermes_integration` — walks `src/kajiba/*.py` (abs path from `__file__`, Windows/cwd-safe) asserting none contain `import hermes_integration`, `from kajiba.hermes_integration`, or `from .hermes_integration`.
- `test_hermes_integration_module_absent` — `pytest.raises(ModuleNotFoundError)` around `importlib.import_module("kajiba.hermes_integration")`. RED now (module exists), GREEN after Plan 02 deletes it.

## RED-State Verification

| File | Acceptance | Observed |
|------|-----------|----------|
| test_config.py | collects 3 hermes_home tests; RED on `ImportError: cannot import name 'get_hermes_home'`; full file collects exit 0 | PASS |
| test_plugin.py | collects 3 named tests; RED on `ModuleNotFoundError: No module named 'kajiba.plugin'` | PASS |
| test_no_hermes_integration.py | collects 2 guard tests; RED (`DID NOT RAISE ModuleNotFoundError`) while module present | PASS |
| full suite | `pytest --co -q` exits 0 (442 collected, no collection/syntax error) | PASS |

All three surfaces are RED only on not-yet-built symbols or the not-yet-deleted module, not on existing-suite breakage.

## Deviations from Plan

None — plan executed exactly as written. No code-behavior deviations (Rules 1–4 not triggered); this is a test-only scaffold plan.

### Note on PyYAML (environmental, not a deviation)

`tests/test_config.py` opens with `yaml = pytest.importorskip("yaml")`, and PyYAML is not installed on this dev machine (one of the two known pre-existing skips per STATE.md). With the whole module skipped, the Task 1 collection/RED acceptance commands cannot be observed. The plan explicitly forbids touching the `importorskip` line. Resolution: PyYAML 6.0.3 was temporarily `pip install`ed solely to OBSERVE the acceptance criteria (3 tests collected; `ImportError` on `get_hermes_home`; full-file collect exit 0 — all confirmed), then `pip uninstall`ed to restore the original baseline. No source or test file was changed to accommodate this; the dev-machine skip state is preserved.

## Self-Check: PASSED

- tests/test_config.py — FOUND (modified, TestGetHermesHome present)
- tests/test_plugin.py — FOUND
- tests/test_no_hermes_integration.py — FOUND
- commit d4ac6ea — FOUND
- commit 0686ab5 — FOUND
- commit 84037bf — FOUND
