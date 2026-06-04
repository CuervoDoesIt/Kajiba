---
phase: 06-environment-plugin-foundation
plan: 02
subsystem: environment
tags: [hermes-home, profile-isolation, path-migration, plugin-foundation, collector-signature, d-07]
requires:
  - "Plan 01 RED scaffolds: tests/test_config.py::TestGetHermesHome, tests/test_no_hermes_integration.py"
  - "Existing module-level path constants (KAJIBA_BASE/EXPERIMENTS_DIR/DOWNLOADS_DIR/CLONE_DIR) and config.yaml read/write paths"
provides:
  - "kajiba.config.get_hermes_home() — single HERMES_HOME resolution helper (D-10, PLUG-03)"
  - "All five modules (config/collector/cli/publisher/experiment_store) route paths through get_hermes_home()"
  - "collector.on_session_start backwards-compatible signature + keyword-only model_name/platform (D-08)"
  - "hermes_integration.py deleted; CLAUDE.md points to src/kajiba/plugin/ register(ctx) (D-07)"
affects:
  - "Plan 03 (kajiba.plugin package) — collector.on_session_start now accepts the real hook kwargs"
  - "Phase 7 live capture — file I/O follows the active HERMES_HOME profile (MP-4 closed)"
tech-stack:
  added: []
  patterns:
    - "Constant-vs-lazy split: module-level constants derive at import from get_hermes_home(); function-body config.yaml paths call it lazily at use time"
    - "get_hermes_home() reads os.environ on every call (never cached) so a later-set HERMES_HOME is honored"
    - "Backwards-compatible event-hook signature: Optional positional dict + keyword-only kwargs, adapter builds minimal dict"
key-files:
  created: []
  modified:
    - src/kajiba/config.py
    - src/kajiba/collector.py
    - src/kajiba/publisher.py
    - src/kajiba/cli.py
    - src/kajiba/experiment_store.py
    - tests/test_config.py
    - tests/test_cli.py
    - CLAUDE.md
  deleted:
    - src/kajiba/hermes_integration.py
decisions:
  - "Constant-vs-lazy split applied per the plan's locked strategy: KAJIBA_BASE/EXPERIMENTS_DIR/DOWNLOADS_DIR/CLONE_DIR stay module-level constants (preserving ~30 monkeypatch.setattr sites); config.yaml read/write goes lazy."
  - "experiment_store.EXPERIMENTS_DIR derives from get_hermes_home() (NOT a kajiba.cli import) — parity with cli.py held because both call the same helper; module stays Click-free."
  - "collector signature: on_session_start(session_id, model_config=None, *, model_name=None, platform=None); builds {model_name, provider: platform} when dict omitted, empty {} when all None."
  - "CLAUDE.md keeps four mentions of hermes_integration.py as 'removed / superseded by src/kajiba/plugin/ register(ctx)' historical pointers — none describe it as current architecture."
metrics:
  duration: ~13m
  completed: 2026-06-04
---

# Phase 6 Plan 02: HERMES_HOME Path Migration + Collector Adaptation + hermes_integration Deletion Summary

Every hardcoded `~/.hermes` path now resolves through a single `get_hermes_home()` helper that follows the active Hermes v0.6.0 profile (HERMES_HOME env), the collector absorbs the real plugin-hook `model_name`/`platform` kwargs without breaking legacy positional-dict callers, and the obsolete Protocol-based `hermes_integration.py` adapter is deleted cleanly with CLAUDE.md repointed at the forthcoming `src/kajiba/plugin/` package.

## What Was Built

**Task 1 — get_hermes_home() + config/collector/publisher migration (commit ea5e958)**
Added `get_hermes_home() -> Path` to `config.py` after the Constants divider (reads `os.environ.get("HERMES_HOME")` on every call, returns `Path(env)` if truthy else `Path.home() / ".hermes"`). Migrated `config.KAJIBA_BASE = get_hermes_home() / "kajiba"` (ACTIVITY_LOG derives from it); `_load_config_value`/`_save_config_value` now read/write `get_hermes_home() / "config.yaml"` lazily inside the function bodies. `collector.KAJIBA_BASE` and `publisher.CLONE_DIR` route through the same helper via `from kajiba.config import get_hermes_home`. No import cycle (config.py never imports collector/publisher).

**Task 2 — cli/experiment_store migration + collector signature (commit 0026091)**
`cli.KAJIBA_BASE`/`DOWNLOADS_DIR` and the two `config show`/`config get` config.yaml reads route through `get_hermes_home()`. `experiment_store.EXPERIMENTS_DIR = get_hermes_home() / "kajiba" / "experiments"` (Click-free; parity with cli held because both derive from the same helper — `test_experiments_dir_matches_cli` green). `collector.on_session_start` rewritten to `(self, session_id, model_config=None, *, model_name=None, platform=None)`: legacy positional-dict calls still work; when `model_config` is omitted a minimal `{"model_name", "provider": platform}` dict is built, and an empty `{}` guards the all-None case so `_extract_model_metadata` never crashes. Verified the keyword path produces a valid record (`model_name=m`, `provider=ollama`).

**Task 3 — delete hermes_integration.py + CLAUDE.md cleanup (commit 5059003)**
`git rm src/kajiba/hermes_integration.py` (HermesAgent Protocol + register_hooks). Confirmed no source or test file imports it (only the Plan 01 static guard references the strings). CLAUDE.md's Module Design / Architecture / Layers / Key Abstractions / Entry Points sections updated to describe Hermes integration as the `src/kajiba/plugin/` package via `register(ctx)`, with the deleted adapter noted as removed/superseded.

## Verification Results

- `python -m pytest tests/test_config.py` → 22 passed (TestGetHermesHome RED→GREEN: env-set, unset-fallback, isolation).
- `python -m pytest tests/test_collector.py` → 19 passed (positional-dict + keyword call both valid).
- `python -m pytest tests/test_experiment_store.py` → 11 passed (parity `test_experiments_dir_matches_cli` green).
- `python -m pytest tests/test_cli.py` → 93 passed.
- `python -m pytest tests/test_no_hermes_integration.py` → 2 passed (module absent + no source import).
- `pytest --co -q` → 442 collected, exit 0 (no orphaned import).
- HERMES_HOME smoke: `HERMES_HOME=/tmp/x` → `get_hermes_home()` returns it and `KAJIBA_BASE` lands under it.
- No `Path.home() / ".hermes" / "config.yaml"` literal remains in config.py or cli.py.
- Full suite baseline restored (PyYAML uninstalled): **324 passed, 2 pre-existing yaml-soft-dep skips**, plus 3 RED-by-design `test_plugin.py` failures (Plan 03 builds `kajiba.plugin`). Zero regressions in this plan's scope.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-existing config tests leaked the dev machine's real HERMES_HOME**
- **Found during:** Task 1 (test_config.py) and overall verification (test_cli.py).
- **Issue:** The dev machine has `HERMES_HOME` set to a real Hermes profile whose `config.yaml` carries a `kajiba.min_quality_tier: gold` override. Pre-existing tests (`fake_home` fixture in test_config.py; `TestConfigSubcommands` in test_cli.py) monkeypatched only `Path.home` for temp-home isolation. Once config reads went lazy through `get_hermes_home()`, those tests read the real profile instead of the temp home — `test_reads_value_from_yaml` and `test_config_get_default_value` failed (asserted `silver`/`anonymous`, got the real `gold`/`full`).
- **Fix:** Added `monkeypatch.delenv("HERMES_HOME", raising=False)` to the `fake_home` fixture (test_config.py) and an autouse `_isolate_hermes_home` fixture to `TestConfigSubcommands` (test_cli.py). This *strengthens* the temp-home isolation the tests already intended (consistent with the Plan 01 `test_get_hermes_home_unset` case) rather than weakening any assertion. The new TestGetHermesHome setenv cases are unaffected (they set their own HERMES_HOME after the fixture runs).
- **Files modified:** tests/test_config.py, tests/test_cli.py
- **Commits:** ea5e958 (test_config.py fixture), f5acbf7 (test_cli.py fixture)

### Environmental note (not a deviation)

PyYAML is a pre-existing soft-dep skip on this dev machine (documented in 06-01-SUMMARY). It was temporarily `pip install`ed solely to OBSERVE the config-test acceptance criteria (TestGetHermesHome + the config.yaml read/write suites, which are `pytest.importorskip("yaml")`-gated), then `pip uninstall`ed to restore the original baseline (324 passed / 2 yaml skips). No source or test was changed to accommodate the install; the `importorskip` line was never touched.

## Self-Check: PASSED

- src/kajiba/config.py — FOUND (contains `def get_hermes_home`, `KAJIBA_BASE = get_hermes_home() / "kajiba"`)
- src/kajiba/collector.py — FOUND (backwards-compatible signature with `model_name`)
- src/kajiba/experiment_store.py — FOUND (`get_hermes_home`, no kajiba.cli import)
- src/kajiba/hermes_integration.py — CONFIRMED DELETED (ModuleNotFoundError; not on disk)
- commit ea5e958 — FOUND
- commit 0026091 — FOUND
- commit 5059003 — FOUND
- commit f5acbf7 — FOUND
