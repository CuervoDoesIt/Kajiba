# Phase 6: Environment + Plugin Foundation - Research

**Researched:** 2026-06-04
**Domain:** Hermes Agent v0.6.0 plugin integration, WSL2+Ollama GPU environment, HERMES_HOME profile isolation
**Confidence:** HIGH for migration scope (codebase verified line-by-line); HIGH for Hermes plugin API shape (existing project research verified against official docs); MEDIUM for exact hook kwargs (must be empirically confirmed — this is the explicit purpose of the first task, D-05/D-06)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Plugin source code lives at `src/kajiba/plugin/` as a subdirectory of the main package. The plugin's `__init__.py` exports `register(ctx)` and imports from the parent `kajiba` package (`from kajiba.collector import KajibaCollector`).
- **D-02:** During development, a symlink from `~/.hermes/plugins/kajiba/` points into `src/kajiba/plugin/`. ENV-03 covers documenting this workflow.
- **D-03:** Environment setup documented as a standalone guide at `docs/hermes-setup.md` with step-by-step instructions and verification checkpoints at each stage (WSL2, GPU passthrough, Ollama, Hermes, Kajiba plugin loading).
- **D-04:** Guide must include troubleshooting for known pitfalls: CUDA driver stub overwrite (install only `cuda-toolkit-12-x`), Ollama `num_ctx` default truncation, Ollama network binding in WSL2.
- **D-05:** Hook discovery is built into the final plugin as a debug mode (`KAJIBA_DEBUG=1` env var). When enabled, the plugin logs all hook kwargs (names, types, values) to stderr/log. This stays as a permanent diagnostic tool, not a throwaway script.
- **D-06:** First task of the phase: deploy plugin with debug mode on, run a short Hermes session, capture the actual kwargs for `on_session_start`, `post_llm_call`, `post_tool_call`, `on_session_end`. Document findings in the phase directory.
- **D-07:** Delete `src/kajiba/hermes_integration.py` entirely. The `HermesAgent` Protocol and `register_hooks()` function are completely wrong for the real Hermes API. Clean break.
- **D-08:** Tests that currently import from `hermes_integration` will be updated to use `KajibaCollector` directly — the collector is already independently usable without any adapter layer.
- **D-09:** All hardcoded `~/.hermes` paths in `collector.py`, `cli.py`, `config.py`, and `publisher.py` must be replaced with HERMES_HOME-aware resolution. The `HERMES_HOME` env var (introduced in Hermes v0.6.0) specifies the active profile directory.
- **D-10:** Create a shared path resolution helper (e.g., `get_hermes_home()` in `config.py`) that checks `HERMES_HOME` env var first, falls back to `~/.hermes`. All modules import from this single source.

### Claude's Discretion
- Plugin directory structure details (`plugin.yaml` fields, `__init__.py` scaffolding)
- HERMES_HOME helper implementation approach
- Test migration strategy for `hermes_integration` imports
- Hook registration wiring between Hermes events and `KajibaCollector` methods

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ENV-01 | Documented WSL2 + NVIDIA GPU passthrough + Hermes v0.6.0 + Ollama setup guide with verification steps | `docs/hermes-setup.md` outline (this doc, Setup Guide section); pitfalls MP-8 (CUDA stub), MP-9 (Ollama binding) drive the troubleshooting sections |
| ENV-02 | Documented Ollama configuration (num_ctx override, Hermes 3 8B model pull, custom endpoint setup) | Ollama config section of guide; MP-5 (num_ctx truncation) and Performance Traps table |
| ENV-03 | Dev symlink script/instructions linking plugin dir into `~/.hermes/plugins/` | Symlink dev workflow (this doc, Pattern 2); D-01/D-02 set source-of-truth at `src/kajiba/plugin/` |
| PLUG-01 | Plugin scaffold at `~/.hermes/plugins/kajiba/` with `plugin.yaml` + `register(ctx)` | Plugin structure section; plugin.yaml field table; `register(ctx)` skeleton |
| PLUG-02 | Plugin registers hooks for the 4 lifecycle events via `ctx.register_hook()` | Hook wiring table (this doc, Pattern 1); maps each hook to a `KajibaCollector` method |
| PLUG-03 | All `~/.hermes` paths replaced with HERMES_HOME-aware resolution | Complete hardcoded-path inventory (Runtime State Inventory + Migration Map); `get_hermes_home()` contract |
| CAPT-01 | Logging-only plugin stub deployed to empirically confirm hook kwargs against live Hermes v0.6.0 | `KAJIBA_DEBUG=1` debug-mode design (this doc, Pattern 3); the discovery task that unblocks Phase 7 |
</phase_requirements>

## Summary

This phase is **80% migration / wiring and 20% empirical discovery**, sitting on top of an unusually complete body of prior project research. The Hermes plugin API shape (`register(ctx)` + `ctx.register_hook(event, callback)`, plugin directory at `~/.hermes/plugins/<name>/` with `plugin.yaml` + `__init__.py`) is already verified against official NousResearch docs in `FEATURES.md`, `ARCHITECTURE.md`, and `STACK.md`. The `KajibaCollector` lifecycle logic is tested and stays intact — only its input signatures change. Do **not** re-derive the plugin API from scratch; cite the existing research and extend it where this phase's scope (env setup, path migration, debug discovery) needs more depth.

The single largest *unknown* is the exact kwargs each hook receives. Prior research lists best-guess signatures (`on_session_start(session_id, model, platform)`, etc.) but flags them as requiring empirical confirmation (MP-2). D-05/D-06 turn this uncertainty into a designed, permanent feature: a `KAJIBA_DEBUG=1` mode that logs every hook's kwargs. The **first task** of the phase deploys this and captures ground truth — everything downstream (Phase 7 turn assembly) depends on these real kwargs, so they must be tagged `[ASSUMED]` until the discovery task runs.

The HERMES_HOME migration is wider than CONTEXT.md anticipated. CONTEXT.md lists `collector.py`, `cli.py`, `config.py`, `publisher.py` — but a codebase grep also found **`experiment_store.py:50`** carrying a hardcoded `~/.hermes/kajiba/experiments` path that is *contractually pinned* to `cli.py`'s value by a parity test (`test_experiments_dir_matches_cli`). Any migration must update both sides together or that test breaks. The good news on D-07/D-08: **no test file imports `hermes_integration`** (verified — the module has zero test coverage per `.planning/codebase/TESTING.md`), so deletion is a near-clean removal with only CLAUDE.md/doc references to clean up.

**Primary recommendation:** Sequence as (1) `get_hermes_home()` helper + full path migration with tests, (2) delete `hermes_integration.py` + collector signature adaptation (backwards-compatible), (3) plugin scaffold `src/kajiba/plugin/` with `KAJIBA_DEBUG=1` discovery mode, (4) live debug-session to capture real kwargs (manual checkpoint), (5) wire confirmed kwargs into the 4 hooks, (6) `docs/hermes-setup.md` + symlink workflow. The env guide and path migration can proceed in parallel with the plugin scaffold.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Plugin discovery & load (`plugin.yaml`, `register(ctx)`) | Hermes plugin host | Kajiba library | Hermes scans `~/.hermes/plugins/`, calls `register(ctx)` once at startup; Kajiba only provides the entry point |
| Hook event delivery (`ctx.register_hook`) | Hermes plugin host | Kajiba plugin handlers | Hermes owns the event loop and fires hooks; Kajiba handlers are synchronous, fast, capture-only |
| Session data accumulation | Kajiba library (`KajibaCollector`) | — | Module-level collector singleton holds in-memory session state; unchanged logic |
| Hardware/model metadata detection | Kajiba library (`collector._detect_hardware`, `_extract_model_metadata`) | nvidia-smi / Ollama | `_detect_hardware` unchanged; `_extract_model_metadata` adapts input shape |
| Path resolution (HERMES_HOME) | Kajiba library (`config.get_hermes_home`) | OS env / Hermes profile | Single helper; CLI reads env var, plugin context may also read env (see Open Questions) |
| GPU acceleration | OS / WSL2 / NVIDIA stub | Ollama | Documented in setup guide; not Kajiba code — env-level prerequisite |
| Hook kwargs discovery | Kajiba plugin (`KAJIBA_DEBUG=1`) | Live Hermes session | Permanent diagnostic; the empirical bridge to ground truth |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Hermes Agent | v0.6.0 | Plugin host — discovers/loads Kajiba, fires lifecycle hooks | Target platform; v0.6.0 introduced HERMES_HOME profile isolation. Installed via Hermes install script (not pip). `[CITED: .planning/research/STACK.md:30]` `[ASSUMED]` exact v0.6.0 hook payloads |
| Ollama | current | Local LLM inference + model metadata (`ollama.show()` in Phase 7) | Self-contained, GPU-aware via WSL2 CUDA stub. Used for inference in dev env; metadata capture is Phase 7. `[CITED: .planning/research/STACK.md]` |
| Python | 3.11+ (3.13.3 dev) | All Kajiba source | Project constraint, established `[VERIFIED: pyproject.toml:11]` |

### Supporting (already in project — no new installs this phase)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | >=2.0 | Schema models (`KajibaRecord`, `ModelMetadata`) | Unchanged this phase `[VERIFIED: pyproject.toml:26]` |
| click | >=8.0 | CLI | Path migration touches CLI commands `[VERIFIED: pyproject.toml:27]` |
| pytest | >=7.0 | Test runner | Path-migration tests, collector signature tests `[VERIFIED: pyproject.toml:35]` |

**Installation:** **No new Python packages required for Phase 6.** This phase installs *system-level* components in the WSL2 dev environment (documented, not pip): WSL2, NVIDIA Windows driver, `cuda-toolkit-12-x` (toolkit only — see MP-8), Ollama, Hermes Agent v0.6.0. The Kajiba `pyproject.toml` may gain a `[hermes]` extra entry point in a *later* phase (PLUG-04, Phase 8) — **not this phase** (D-01/D-02 use the symlink dev workflow).

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Symlink dev workflow (D-02) | `pip install kajiba[hermes]` entry point | Entry point is PLUG-04/Phase 8; symlink is the explicit Phase 6 decision for rapid edit-reload |
| Plugin at `src/kajiba/plugin/` (D-01) | Standalone plugin dir outside the package | D-01 locks the in-package location; imports `from kajiba.collector` cleanly when `pip install -e .` is active |

## Package Legitimacy Audit

**No external packages are installed by this phase.** All Python dependencies already exist in `pyproject.toml` and were vetted in prior phases. System components (WSL2, Ollama, Hermes Agent, CUDA toolkit) are installed via official vendor channels documented in the setup guide, not via a package registry — slopcheck does not apply.

| Package | Registry | Disposition |
|---------|----------|-------------|
| (none new) | — | N/A — phase installs no registry packages |

*slopcheck not run: no registry package installs in scope.*

## Architecture Patterns

### System Architecture Diagram

```
Hermes Agent v0.6.0  (plugin host, owns event loop)
        │
        │ on startup: scan ~/.hermes/plugins/*/  → find plugin.yaml + __init__.py
        │ call register(ctx) once
        ▼
~/.hermes/plugins/kajiba/  ──symlink──>  src/kajiba/plugin/   (D-01/D-02)
        │ __init__.py: register(ctx)
        │   ctx.register_hook("on_session_start", _on_session_start)
        │   ctx.register_hook("post_llm_call",    _on_post_llm_call)
        │   ctx.register_hook("post_tool_call",   _on_post_tool_call)
        │   ctx.register_hook("on_session_end",   _on_session_end)
        │
        │ if KAJIBA_DEBUG=1: each handler logs (name, type, value) of all kwargs  ← D-05 discovery
        ▼
   hook handlers  ──map kwargs──>  KajibaCollector  (src/kajiba/collector.py, unchanged logic)
        │                              │ _conversations[], _model_metadata, _hardware
        │                              ▼
        │                         on_session_end → _save_to_staging()
        ▼                              ▼
   (Phase 7 assembles turns)    get_hermes_home()/kajiba/staging/session_{id}.json
                                       ▲
                                       │ all paths resolve through ONE helper
                  config.get_hermes_home():  HERMES_HOME env var  →  fallback ~/.hermes
                                       ▲
        ┌──────────────┬──────────────┼──────────────┬──────────────┐
   collector.py     cli.py        config.py     publisher.py   experiment_store.py
   (KAJIBA_BASE)  (KAJIBA_BASE,  (KAJIBA_BASE, (CLONE_DIR)    (EXPERIMENTS_DIR —
                  DOWNLOADS_DIR,  config.yaml)                 parity-pinned to cli.py)
                  config.yaml)
```

A reader can trace the primary use case: Hermes loads the plugin → hooks fire → handlers (optionally logging kwargs in debug mode) dispatch to the collector → collector writes to a HERMES_HOME-resolved staging path.

### Recommended Project Structure
```
src/kajiba/
├── plugin/                 # NEW (D-01) — the Hermes plugin package
│   ├── __init__.py         # register(ctx); imports from kajiba.collector
│   ├── plugin.yaml         # Hermes manifest (name, version, provides_hooks)
│   └── hooks.py            # the 4 hook handler functions + KAJIBA_DEBUG logging
├── collector.py            # CHANGED — on_session_start signature adapts (backwards-compat)
├── config.py               # CHANGED — add get_hermes_home(); migrate KAJIBA_BASE/config paths
├── cli.py                  # CHANGED — KAJIBA_BASE, DOWNLOADS_DIR, config.yaml, EXPERIMENTS_DIR
├── publisher.py            # CHANGED — CLONE_DIR
├── experiment_store.py     # CHANGED — EXPERIMENTS_DIR (keep parity with cli.py!)
└── hermes_integration.py   # DELETED (D-07)

docs/
└── hermes-setup.md         # NEW (D-03) — env guide with verification checkpoints

.planning/phases/06-environment-plugin-foundation/
└── 06-HOOK-KWARGS.md       # NEW (D-06) — captured ground-truth kwargs from live session
```

### Pattern 1: Plugin `register(ctx)` Wiring Hooks to the Existing Collector

The Hermes plugin contract (verified in prior research): define `register(ctx)`, call `ctx.register_hook(event, handler)` inside it; **every handler must accept `**kwargs`** (MP-2 — forward compatibility and silent-skip avoidance). The plugin holds a module-level `KajibaCollector` singleton (correct because Hermes fires `on_session_start` before any turn hook; single-session CLI use case).

```python
# Source: extends .planning/research/ARCHITECTURE.md Pattern 1 (verified vs official Hermes docs)
# src/kajiba/plugin/__init__.py
import logging
from kajiba.collector import KajibaCollector
from kajiba.plugin.hooks import (
    on_session_start, on_post_llm_call, on_post_tool_call, on_session_end, set_collector,
)

logger = logging.getLogger(__name__)

def register(ctx) -> None:
    """Hermes calls this once at startup. Never raise — Hermes disables the plugin on crash."""
    try:
        set_collector(KajibaCollector())
        ctx.register_hook("on_session_start", on_session_start)
        ctx.register_hook("post_llm_call", on_post_llm_call)
        ctx.register_hook("post_tool_call", on_post_tool_call)
        ctx.register_hook("on_session_end", on_session_end)
        logger.info("Kajiba registered hooks: on_session_start, post_llm_call, "
                    "post_tool_call, on_session_end")  # MP-2: log registration explicitly
    except Exception:
        logger.exception("Kajiba plugin registration failed; plugin disabled")
```

**Hook → collector method map (signatures `[ASSUMED]` until D-06 discovery confirms):**

| Hermes hook | Assumed kwargs | KajibaCollector method | Signature delta |
|-------------|----------------|------------------------|-----------------|
| `on_session_start` | `session_id, model, platform, **kwargs` | `on_session_start(session_id, *, model_name, platform)` | Collector currently takes `model_config: dict`; add `model_name`/`platform` kwargs (Pattern 2) |
| `post_llm_call` | `session_id, user_message, assistant_response, conversation_history, model, platform, **kwargs` | (Phase 7 assembles turns) — Phase 6 only logs/captures raw | Phase 6 = capture-only; turn assembly is CAPT-02/Phase 7 |
| `post_tool_call` | `tool_name, args, result, task_id, **kwargs` | (Phase 7) — note `result` is a JSON **string**, `json.loads()` before use | Integration gotcha from PITFALLS |
| `on_session_end` | `session_id, completed, interrupted, model, platform, **kwargs` | `on_session_end(session_id)` | Extra kwargs absorbed by `**kwargs` |

**Phase 6 scope note:** Success criterion 3 only requires the 4 hooks **fire and log their kwargs**. Full turn *assembly* (mapping `post_llm_call`/`post_tool_call` into `ConversationTurn`/`ToolCall`) is Phase 7 (CAPT-02/03). Phase 6 wires the hooks to the collector enough to prove the pipe is connected (e.g., `on_session_start`/`on_session_end` drive real collector state; the turn hooks at minimum log via debug mode).

### Pattern 2: KajibaCollector Signature Adaptation (Backwards-Compatible)

`collector.on_session_start` is currently `(self, session_id: str, model_config: dict)` `[VERIFIED: src/kajiba/collector.py:177]`. The existing test suite calls it **positionally with a dict** — e.g. `collector.on_session_start("s2", {"model_name": "test-model"})` `[VERIFIED: tests/test_collector.py:134]`. Therefore the signature change **must keep `model_config` working** or those tests break.

```python
# Source: .planning/research/ARCHITECTURE.md Pattern 2 — minimal breaking change
def on_session_start(
    self,
    session_id: str,
    model_config: Optional[dict] = None,   # kept: existing tests + standalone CLI
    *,
    model_name: Optional[str] = None,       # new: from Hermes hook
    platform: Optional[str] = None,         # new: from Hermes hook
) -> None:
    if model_config is None and model_name is not None:
        model_config = {"model_name": model_name, "provider": platform}
    ...  # existing body unchanged
```

`_extract_model_metadata(model_config: dict)` `[VERIFIED: src/kajiba/collector.py:131]` stays as-is — the plugin path constructs a minimal `model_config` from `model_name`+`platform`. **Full Ollama metadata enrichment (`ollama.show()` → parameter count, quantization, family) is CAPT-04/Phase 7, not this phase.** Note `model_name` here uses CLAUDE.md `Optional[X]` style (not `X | None`) — the ARCHITECTURE.md snippet used `| None` which violates the project convention; the planner must use `Optional[...]`.

### Pattern 3: `KAJIBA_DEBUG=1` Hook Discovery Mode (D-05/D-06)

The discovery mechanism is a permanent diagnostic, not a throwaway. Each handler, when `KAJIBA_DEBUG=1`, logs the name, type, and (truncated/redacted) value of every kwarg it receives — including anything caught by `**kwargs` that the assumed signature did not name.

```python
# Source: new — designed for D-05/D-06
import os, logging
logger = logging.getLogger(__name__)
_DEBUG = os.environ.get("KAJIBA_DEBUG") == "1"

def _log_kwargs(hook_name: str, named: dict, extra: dict) -> None:
    if not _DEBUG:
        return
    for k, v in {**named, **extra}.items():
        # truncate to avoid PII/log bloat; report type so Phase 7 knows the shape
        preview = repr(v)[:120]
        logger.warning("KAJIBA_DEBUG %s kwarg %s: type=%s value=%s",
                       hook_name, k, type(v).__name__, preview)

def on_session_start(session_id=None, **kwargs):
    _log_kwargs("on_session_start", {"session_id": session_id}, kwargs)
    ... # dispatch to collector
```

**Why log to stderr/`logger.warning`:** Hermes sets base log level; `WARNING` ensures visibility without `-v`. The CLAUDE.md `%s`-style lazy logging is mandatory (no f-strings in logger calls). **Security note:** truncate values and never log full message bodies — hook payloads contain raw session content (PII). 120-char preview is enough to learn field names/types/shapes without dumping conversations.

**D-06 first-task output:** a captured-kwargs document at `.planning/phases/06-environment-plugin-foundation/06-HOOK-KWARGS.md` recording the *actual* names/types/values, which converts the `[ASSUMED]` signatures above into `[VERIFIED: live Hermes v0.6.0 session]` for Phase 7.

### Symlink Dev Workflow (ENV-03, D-02)

Source of truth is `src/kajiba/plugin/`. The 2-3 command workflow for the guide:

```bash
# WSL2, from the repo root, with `pip install -e .` already done
mkdir -p ~/.hermes/plugins
ln -s "$(pwd)/src/kajiba/plugin" ~/.hermes/plugins/kajiba
# edit src/kajiba/plugin/* → restart Hermes to reload
```

`plugin.yaml` must sit inside `src/kajiba/plugin/` so the symlink exposes it. Confirm Hermes follows symlinks during plugin discovery (Open Question Q3).

### Anti-Patterns to Avoid
- **Calling `ctx.on(event, cb)` (the old Protocol style):** `ctx` has no `.on()`; use `ctx.register_hook(event, cb)`. Carrying any logic from `hermes_integration.py` produces a plugin that loads but captures zero turns (MP-1).
- **Hook handlers without `**kwargs`:** silent `TypeError` → Hermes skips the hook → silent data loss (MP-2).
- **Returning anything from a `pre_llm_call` handler:** injects content into the session (MP-3). Phase 6 does **not** subscribe to `pre_llm_call` at all — but if added later, it must return `None`.
- **Any Ollama/inference call inside a hook handler:** blocks Hermes event loop (MP-7). Phase 6 hooks are capture-only.
- **Two sources of truth for `plugin.yaml`/`register`:** keep them only in `src/kajiba/plugin/`; the symlink is the single deployment (Anti-Pattern 5, ARCHITECTURE.md).
- **Hardcoding `Path.home() / ".hermes"`:** breaks under HERMES_HOME profiles (MP-4). Everything goes through `get_hermes_home()`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Hook kwarg discovery | A throwaway print-script run once and deleted | `KAJIBA_DEBUG=1` permanent mode (D-05) | Hermes versions change kwargs; a permanent diagnostic re-confirms on every upgrade |
| Path resolution per-module | Repeating `os.environ.get("HERMES_HOME", ...)` in each file | One `get_hermes_home()` helper (D-10) | Single source of truth; one place to test; no drift |
| Plugin event subscription | A custom dispatcher/observer | `ctx.register_hook()` (Hermes-provided) | The host owns the event loop; rolling your own re-creates MP-1 |
| GPU detection | New code | Existing `_detect_hardware()` (collector.py:43) | Already works via nvidia-smi; no changes needed |

**Key insight:** The collector's data logic is tested and correct. This phase's risk is entirely in the *seams* — registration wiring, path resolution, and the env it runs in. Treat the plugin rewrite as greenfield wiring around an unchanged collector, not a refactor of the collector.

## Runtime State Inventory

> This is a refactor/migration phase (delete `hermes_integration.py`, migrate hardcoded paths, deploy a new plugin directory). Inventory below.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | Existing staging/outbox/experiment records live under `~/.hermes/kajiba/{staging,outbox,experiments}/`. After migration, code reads from `get_hermes_home()/kajiba/...`. **Default profile (HERMES_HOME unset) resolves to the same `~/.hermes` path — existing records remain readable.** Risk only arises if a user runs under a non-default profile expecting old data. | Code edit only (fallback preserves default path). No data migration needed for the default profile. Document in guide that profile switch implies a separate data namespace. |
| **Live service config** | `~/.hermes/config.yaml` (Kajiba `kajiba:` section) read/written at `config.py:89,123` and `cli.py:852,932`. Path must migrate too, or config is read from the wrong profile. | Code edit — route config.yaml path through `get_hermes_home()`. |
| **OS-registered state** | New `~/.hermes/plugins/kajiba/` symlink is created by the dev (manual, documented in ENV-03). No OS scheduler/service registration. | Manual (symlink), documented. |
| **Secrets/env vars** | `HERMES_HOME` (read), `KAJIBA_DEBUG` (read), `OLLAMA_HOST` (set in env guide for WSL2 binding). No secret keys renamed. | None — these are inputs the code/guide consume, not renames. |
| **Build artifacts / installed packages** | `pip install -e .` editable install must be active for the plugin's `from kajiba.collector import ...` to resolve when Hermes loads it. After deleting `hermes_integration.py`, any stale `.pyc` / egg-info referencing it is harmless but a reinstall is cleanest. | Re-run `pip install -e .` after structure changes; document in guide. |

**Complete hardcoded-path inventory (verified by grep — wider than CONTEXT.md D-09):**

| File:Line | Constant / usage | In CONTEXT.md? |
|-----------|------------------|----------------|
| `collector.py:38` | `KAJIBA_BASE = Path.home() / ".hermes" / "kajiba"` | Yes |
| `config.py:28` | `KAJIBA_BASE` | Yes |
| `config.py:89` | `config.yaml` path (`_load_config_value`) | Yes |
| `config.py:123` | `config.yaml` path (`_save_config_value`) | Yes |
| `cli.py:74` | `KAJIBA_BASE` | Yes |
| `cli.py:78` | `DOWNLOADS_DIR` | Partially (D-09 says "cli.py") |
| `cli.py:852` | `config.yaml` path | Yes |
| `cli.py:932` | `config.yaml` path | Yes |
| `cli.py:2163` | help-text string `~/.hermes/kajiba/downloads/` (cosmetic) | No — update text for accuracy |
| `publisher.py:38` | `CLONE_DIR = ... / "dataset-clone"` | Yes |
| **`experiment_store.py:50`** | **`EXPERIMENTS_DIR`** | **NO — missed by CONTEXT.md** |

**Critical drift trap:** `experiment_store.py:50` is **parity-pinned** to `cli.py`'s `EXPERIMENTS_DIR` by `tests/test_experiment_store.py:260 test_experiments_dir_matches_cli` `[VERIFIED]`, which asserts `cli.EXPERIMENTS_DIR.resolve() == experiment_store.EXPERIMENTS_DIR.resolve()`. If the migration routes `cli.py` through `get_hermes_home()` but not `experiment_store.py` (or vice versa), this test fails. Both module-level constants are evaluated at import time — if `get_hermes_home()` reads the env var at import time, both will agree **only if** they call the same helper. **Recommendation:** both constants must call `get_hermes_home()` and the parity test must continue to pass; consider whether `EXPERIMENTS_DIR` should be computed lazily (function) vs at import (constant) given env vars can change between import and use (Open Question Q2).

## Common Pitfalls

(Drawn from `.planning/research/PITFALLS.md` — all `[CITED]`. Phase-6-relevant subset.)

### Pitfall 1: MP-1 — Protocol-vs-Plugin silent data loss
**What goes wrong:** Plugin loads with no errors but captures zero turns because old `agent.on()` logic was carried over. **How to avoid:** greenfield `register(ctx)`; verify `on_session_start` fires (debug mode) **before** writing capture logic. **Warning sign:** no staging file after a session. `[CITED: PITFALLS.md MP-1]`

### Pitfall 2: MP-2 — Hook kwarg mismatch crashes capture silently
**What goes wrong:** a handler without `**kwargs` raises `TypeError`; Hermes isolates hook crashes → silent failure. **How to avoid:** every handler ends in `**kwargs`; log registration at startup; test handlers with an unexpected extra kwarg. `[CITED: PITFALLS.md MP-2]`

### Pitfall 3: MP-4 — HERMES_HOME breaks hardcoded paths
**What goes wrong:** code writes to `~/.hermes/kajiba/` while the active profile is elsewhere → `kajiba preview` shows nothing. **How to avoid:** `get_hermes_home()` everywhere; test with `HERMES_HOME=/tmp/test` and assert files land in `/tmp/test/kajiba/`. `[CITED: PITFALLS.md MP-4]`

### Pitfall 4: MP-8 — WSL2 CUDA stub overwrite kills GPU
**What goes wrong:** installing `cuda`/`cuda-drivers` meta-package overwrites the WSL2 `libcuda.so` stub → Ollama silently falls back to CPU (60x slower). **How to avoid:** install **only** `cuda-toolkit-12-x`; verify `libcuda.so` is a symlink; confirm VRAM usage during inference. Keep models in WSL2 native FS, not `/mnt/c/`. `[CITED: PITFALLS.md MP-8]` — **must be a checkpoint in the setup guide (D-04).**

### Pitfall 5: MP-9 — Ollama network binding in WSL2
**What goes wrong:** Ollama binds `127.0.0.1`; cross-namespace calls refused. **How to avoid:** run Hermes + Ollama both inside WSL2; set `OLLAMA_HOST=0.0.0.0:11434` if Windows-host access needed; document topology. `[CITED: PITFALLS.md MP-9]` — **guide checkpoint (D-04).**

### Pitfall 6: MP-5 — Ollama num_ctx default truncation
**What goes wrong:** Ollama's reported context length ≠ effective context (defaults to 2048). **Relevance to Phase 6:** the ENV-02 Ollama config section must document setting `num_ctx` explicitly (actual scrubbing use is Phase 7). `[CITED: PITFALLS.md MP-5]` — **guide content (D-04).**

### Pitfall 7: `post_tool_call` `result` is a JSON string
**What goes wrong:** treating `result` as a dict. **How to avoid:** `json.loads(result)` before use (relevant to Phase 7 capture, but the debug-mode discovery should record its type to confirm). `[CITED: PITFALLS.md Integration Gotchas]`

## Code Examples

### `get_hermes_home()` helper (D-10) — recommended contract
```python
# Source: new — implements D-10; lives in config.py (D-10 specifies config.py)
import os
from pathlib import Path

def get_hermes_home() -> Path:
    """Resolve the active Hermes home directory.

    Checks the HERMES_HOME environment variable first (v0.6.0 profile
    isolation); falls back to ``~/.hermes`` when unset.

    Returns:
        Path to the active Hermes home directory.
    """
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    return Path.home() / ".hermes"
```
Then derive bases: `KAJIBA_BASE = get_hermes_home() / "kajiba"`. **Decision point (Q2):** module-level constants evaluate `get_hermes_home()` once at import. If tests / runtime set `HERMES_HOME` *after* import, constants are stale. Existing tests set env via monkeypatch — verify whether they patch before import or expect lazy evaluation. Lazy (function returning the path) is safer for testability; the planner should choose and apply consistently across all 5 files.

### Hook handler skeleton with `**kwargs` + debug
```python
# Source: new — combines Pattern 1 + Pattern 3
def on_session_start(session_id=None, model=None, platform=None, **kwargs) -> None:
    _log_kwargs("on_session_start", {"session_id": session_id, "model": model,
                                     "platform": platform}, kwargs)
    c = _collector
    if c is None:
        return
    c.on_session_start(session_id=session_id, model_name=model, platform=platform)
```

### `plugin.yaml` manifest (fields per prior research — confirm against live Hermes)
```yaml
# Source: .planning/research/FEATURES.md (verified vs official Hermes docs) — fields [ASSUMED] until live load confirms
name: kajiba
version: "0.2.0"
description: "Captures Hermes session data for the Kajiba community dataset"
provides_hooks:
  - on_session_start
  - post_llm_call
  - post_tool_call
  - on_session_end
provides_tools: []
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `hermes_integration.py` Protocol + `agent.on()` | Plugin dir + `register(ctx)` + `ctx.register_hook()` | Hermes v0.5.0+ | Full rewrite (D-07); old module deleted |
| Single fixed `~/.hermes` | `HERMES_HOME` profile isolation | Hermes v0.6.0 | All paths must resolve via env var (D-09/D-10) |
| `model_config: dict` at session start | `model` (str) + `platform` (str) from hook | Hermes hook API | Collector signature adapts, backwards-compatible (Pattern 2) |

**Deprecated/outdated:**
- `HermesAgent` Protocol, `register_hooks(agent)` — deleted (D-07). CLAUDE.md and `.planning/codebase/*` still reference them as current; the planner should flag a doc-update task so CLAUDE.md's architecture section stops describing the deleted module (it lists `hermes_integration.py` in module lists at CLAUDE.md:91, 178, 216-217, 249, 266).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Hermes v0.6.0 hooks receive exactly the kwargs listed (`on_session_start(session_id, model, platform)`, etc.) | Pattern 1 table | HIGH — Phase 7 turn assembly depends on this. **Mitigated by design:** D-06 discovery task confirms before Phase 7. Tag stays `[ASSUMED]` until then. |
| A2 | `plugin.yaml` field names (`provides_hooks`, etc.) are correct for v0.6.0 | Code Examples | MEDIUM — plugin won't load if fields wrong; first live-load task surfaces this immediately |
| A3 | Hermes follows symlinks during plugin discovery | Symlink workflow | MEDIUM — if not, dev workflow needs copy-not-symlink; verify on first deploy (Q3) |
| A4 | In plugin context, reading `HERMES_HOME` env var resolves the same dir Hermes uses (vs a Hermes-provided `get_hermes_home()` / `ctx` accessor) | get_hermes_home contract | MEDIUM — PITFALLS MP-4 mentions a Hermes-internal `get_hermes_home()`; if plugin must use that instead of the env var, the helper needs a plugin-context branch (Q1) |
| A5 | Default-profile data (HERMES_HOME unset) keeps resolving to `~/.hermes`, so existing staging/outbox records stay readable with no migration | Runtime State Inventory | LOW — fallback preserves the literal path; verified by helper logic |
| A6 | Hermes Agent v0.6.0 is the current/installable version | Standard Stack | LOW — prior research dated 2026-04; confirm latest at setup time |

## Open Questions

1. **Plugin-context path resolution (A4):** Does the Kajiba plugin, running inside Hermes, get the active profile dir from the `HERMES_HOME` env var (which Hermes presumably sets for the subprocess), or must it call a Hermes-provided `get_hermes_home()` / read it off `ctx`? PITFALLS MP-4 says "use `get_hermes_home()` from Hermes internals" inside the plugin but "read `HERMES_HOME` env var" in the CLI.
   - **What we know:** CLI side is clear (env var, fallback `~/.hermes`).
   - **What's unclear:** whether the env var is reliably set in the plugin's process, or whether `ctx` exposes a path accessor.
   - **Recommendation:** The D-06 debug session should also log `os.environ.get("HERMES_HOME")` and inspect `ctx` attributes. Until confirmed, the single `get_hermes_home()` (env-var-based) is the default; add a plugin-context override only if discovery shows the env var is absent.

2. **Constant vs lazy path evaluation (Q2):** Module-level `KAJIBA_BASE = get_hermes_home() / "kajiba"` freezes the value at import. Tests and profile switches may set `HERMES_HOME` later.
   - **Recommendation:** Decide one strategy for all 5 files. Lazy (helper functions returning paths, or re-reading in each function) maximizes testability and correctness under profile changes; constants are simpler but stale-prone. Check how existing path tests are written before choosing. Must keep `test_experiments_dir_matches_cli` green either way.

3. **Symlink discovery (A3):** Confirm Hermes v0.6.0 resolves a symlinked plugin directory during startup scan. If not, the dev workflow becomes a copy step (and ENV-03 changes).
   - **Recommendation:** Verify in the first live deploy; document the working method in the guide.

4. **Phase-6 depth of turn-hook wiring:** Success criterion 3 requires the turn hooks to *fire and log kwargs*. How much real dispatch (vs debug-log-only) should Phase 6 wire for `post_llm_call`/`post_tool_call` given full assembly is Phase 7?
   - **Recommendation:** Phase 6 wires `on_session_start`/`on_session_end` to drive real collector state (proves end-to-end staging write — success criterion via a staging file appearing), and wires the two turn hooks to debug-log + a minimal capture stub. Defer `ConversationTurn`/`ToolCall` assembly to Phase 7 (CAPT-02/03). Planner should make this boundary explicit.

## Environment Availability

| Dependency | Required By | Available (dev machine) | Version | Fallback |
|------------|------------|-------------------------|---------|----------|
| Python 3.11+ | All Kajiba code | ✓ (Windows host) | 3.13.3 | — |
| WSL2 | Hermes + Ollama runtime (ENV-01) | ✗ (not verified installed) | — | None — required for live session; **dev sets up via the guide this phase produces** |
| NVIDIA Windows driver | GPU passthrough (ENV-01) | ✗ unverified (RTX 4070 present per MEMORY) | — | CPU-only (60x slower, not acceptable for real sessions) |
| `cuda-toolkit-12-x` (in WSL2) | Ollama GPU (ENV-01) | ✗ | — | None |
| Ollama (in WSL2) | Inference + metadata (ENV-02) | ✗ | — | None for live session |
| Hermes Agent v0.6.0 (in WSL2) | Plugin host, hook firing (PLUG-*) | ✗ | — | None — the whole point of the phase |

**Missing dependencies with no fallback:** WSL2, NVIDIA driver, CUDA toolkit, Ollama, Hermes Agent. **This is expected and not a blocker** — Phase 6's ENV-01/02/03 deliverables *are the act of installing and documenting these*. The code-side work (path migration, plugin scaffold, `hermes_integration.py` deletion, signature adaptation, debug-mode plugin) is **fully implementable and unit-testable on the Windows host without any of the above**. Only the *live verification* tasks (hook firing, kwarg capture, symlink load) require the WSL2 env, which the dev builds as the first env-setup tasks.

## Validation Architecture

> nyquist_validation is enabled (`config.json` workflow.nyquist_validation: true).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 7.0 `[VERIFIED: pyproject.toml:35]` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=["tests"], addopts="-v") |
| Quick run command | `python -m pytest tests/test_config.py tests/test_collector.py -x` |
| Full suite command | `python -m pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PLUG-03 | `get_hermes_home()` returns `$HERMES_HOME` when set, `~/.hermes` when unset | unit | `pytest tests/test_config.py::test_get_hermes_home_env -x` | ❌ Wave 0 |
| PLUG-03 | All path constants resolve under a temp `HERMES_HOME` | unit | `pytest tests/test_config.py -k hermes_home -x` | ❌ Wave 0 |
| PLUG-03 | `cli.EXPERIMENTS_DIR == experiment_store.EXPERIMENTS_DIR` still holds after migration | unit | `pytest tests/test_experiment_store.py::test_experiments_dir_matches_cli -x` | ✅ exists (must stay green) |
| D-07 | `hermes_integration` module is gone; no import references remain | unit/static | `pytest tests/ -x` (no collection error) + grep guard | ✅ (full suite) |
| D-08 | Collector usable standalone; `on_session_start` still accepts positional `model_config` dict | unit | `pytest tests/test_collector.py -x` | ✅ exists (must stay green) |
| PLUG-02 | `register(ctx)` registers 4 hooks against a stub `ctx` | unit | `pytest tests/test_plugin.py::test_register_hooks -x` | ❌ Wave 0 |
| PLUG-02/MP-2 | Each hook handler tolerates an unexpected extra kwarg (no exception) | unit | `pytest tests/test_plugin.py::test_handlers_accept_extra_kwarg -x` | ❌ Wave 0 |
| CAPT-01 | `KAJIBA_DEBUG=1` makes handlers log kwarg names/types | unit | `pytest tests/test_plugin.py::test_debug_logging -x` (caplog) | ❌ Wave 0 |
| PLUG-01/02 (live) | Hermes loads plugin; `on_session_start` fires | **manual checkpoint** | `KAJIBA_DEBUG=1` Hermes session, observe log | N/A — live env |
| CAPT-01 (live) | Real kwargs captured for all 4 hooks | **manual checkpoint** | run session, record in `06-HOOK-KWARGS.md` | N/A — live env |
| ENV-01/02 (live) | WSL2+GPU+Ollama+Hermes verified | **manual checkpoint** | guide's verification steps (nvidia-smi VRAM, ollama run, plugin loads) | N/A — live env |
| ENV-03 (live) | Symlink dev workflow loads plugin | **manual checkpoint** | symlink + restart Hermes | N/A — live env |

### Auto-verifiable vs Manual-checkpoint split
- **Auto-verifiable (CI/unit, no WSL2 needed):** `get_hermes_home()` behavior, path migration under temp `HERMES_HOME`, parity test, collector backwards-compat, `register(ctx)` wiring against a stub `ctx`, `**kwargs` tolerance, debug-logging via `caplog`, full-suite green after `hermes_integration` deletion.
- **Manual checkpoint (require live WSL2+Hermes+Ollama the dev sets up):** plugin actually loads in Hermes; the 4 hooks actually fire; real kwargs captured (D-06); GPU acceleration confirmed; symlink load works. These map to success criteria 1, 2, 3, 5 and **cannot be unit-tested** — the planner must mark them as `checkpoint:human-verify` tasks gated on the env-setup tasks.

### Sampling Rate
- **Per task commit:** quick run (`pytest tests/test_config.py tests/test_collector.py -x`)
- **Per wave merge:** full suite (`python -m pytest`)
- **Phase gate:** full suite green + the live manual checkpoints recorded in `06-HOOK-KWARGS.md`

### Wave 0 Gaps
- [ ] `tests/test_config.py` — add `get_hermes_home()` cases (env set / unset / temp dir isolation) covering PLUG-03
- [ ] `tests/test_plugin.py` — NEW: `register(ctx)` against stub ctx, `**kwargs` tolerance, `KAJIBA_DEBUG` logging (PLUG-01/02, CAPT-01, MP-2)
- [ ] Stub `ctx` fixture (records `register_hook` calls) — likely in `tests/conftest.py` or inline in `test_plugin.py`
- [ ] Grep/static guard test that no source file imports `hermes_integration` (locks D-07)
- [ ] Path-migration tests for `cli.py`/`publisher.py`/`experiment_store.py` constants under temp `HERMES_HOME` (or confirm lazy-eval makes existing tests sufficient)

## Project Constraints (from CLAUDE.md)

The planner must ensure all tasks comply:
- **Stack:** Python 3.11+, Pydantic v2, Click, Rich — no new frameworks this phase.
- **Type hints:** use `Optional[X]` from `typing`, **not** `X | None` (the ARCHITECTURE.md snippet used `| None` — correct it). Use modern generics `list[str]`, `dict[str, int]`.
- **Strings:** double quotes preferred.
- **Logging:** `logger = logging.getLogger(__name__)` per module; `%s` lazy formatting in logger calls (no f-strings); **never `print()`** (relevant to debug mode — use `logger`, not print).
- **Docstrings:** Google-style with `Args:`/`Returns:`/`Raises:`; module-level docstring on every module (the new `plugin/__init__.py`, `hooks.py` need them).
- **Naming:** `snake_case.py` modules; `UPPER_SNAKE_CASE` module constants; `_snake_case` private functions.
- **Fault tolerance:** collector methods wrap body in `try/except Exception` + `logger.exception()` — `register(ctx)` and handlers must follow this (never raise into Hermes).
- **Soft-dependency pattern:** conditional imports with graceful fallback (e.g. the plugin must not hard-fail if optional pieces are missing).
- **GSD workflow:** edits go through a GSD command (already in effect for execution).

## Sources

### Primary (HIGH confidence)
- `.planning/research/FEATURES.md` — Hermes plugin API, hook event table, `register(ctx)` (verified vs official Hermes docs 2026-04-02)
- `.planning/research/ARCHITECTURE.md` — plugin wiring patterns, collector signature adaptation, build order, anti-patterns
- `.planning/research/PITFALLS.md` — MP-1/2/4/5/8/9, integration gotchas, "looks done but isn't" checklist
- `.planning/research/STACK.md` — Hermes v0.6.0 plugin API, key differences from old `hermes_integration.py`
- Codebase (line-verified this session): `src/kajiba/hermes_integration.py`, `collector.py:38,131,177`, `config.py:28,89,123`, `cli.py:74,78,852,932,2163`, `publisher.py:38`, `experiment_store.py:45-50`, `pyproject.toml`, `tests/test_collector.py:134`, `tests/test_experiment_store.py:260`
- `.planning/codebase/TESTING.md:71,336` — confirms `hermes_integration.py` has no test file (D-08 is near-trivial)

### Secondary (MEDIUM confidence)
- Official Hermes docs / release notes (v0.5.0, v0.6.0) and NVIDIA WSL2 CUDA guide — cited within the prior research files above (not re-fetched this session; cited transitively)

### Tertiary (LOW confidence)
- Exact hook kwargs — `[ASSUMED]` from prior research; **resolved empirically by the D-06 discovery task**, not by literature

## Metadata

**Confidence breakdown:**
- Migration scope (paths, deletion, signatures): HIGH — every file/line verified by direct read this session
- Plugin API shape: HIGH — verified in prior project research against official docs; cited not re-derived
- Exact hook kwargs: MEDIUM/LOW — `[ASSUMED]`; the phase is explicitly designed to confirm these empirically (D-05/D-06)
- Env setup steps: MEDIUM — drawn from prior research's official-doc-sourced pitfalls; live verification is part of the phase

**Research date:** 2026-06-04
**Valid until:** 2026-07-04 (stable) — but re-confirm Hermes Agent latest version and hook kwargs at execution time; hook kwargs in particular are confirmed only by the live discovery task, not by this document.
