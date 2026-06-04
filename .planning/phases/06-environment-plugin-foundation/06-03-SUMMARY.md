---
phase: 06-environment-plugin-foundation
plan: 03
subsystem: plugin
tags: [wave-3, plugin, hermes, register, hooks, kajiba-debug, capt-01, green]
requires:
  - "Plan 01 RED scaffold: tests/test_plugin.py (StubCtx + register/kwargs/debug tests)"
  - "Plan 02: collector.on_session_start keyword model_name/platform signature + on_session_end(session_id); hermes_integration.py deleted"
provides:
  - "src/kajiba/plugin/ package: register(ctx) entry point (PLUG-01/PLUG-02)"
  - "Four **kwargs-tolerant hook handlers + set_collector singleton (MP-2)"
  - "KAJIBA_DEBUG=1 kwarg logging mechanism (_log_kwargs) for live hook-shape discovery (CAPT-01 code half, D-05)"
  - "plugin.yaml manifest for Hermes discovery (PLUG-01)"
affects:
  - "Plan 04 (setup guide / symlink) — exposes src/kajiba/plugin/ incl. plugin.yaml via the dev symlink"
  - "Plan 05 (live session) — KAJIBA_DEBUG mode captures ground-truth hook kwargs → 06-HOOK-KWARGS.md"
  - "Phase 7 live capture — turn hooks (post_llm_call/post_tool_call) assemble ConversationTurn/ToolCall from the confirmed kwarg shapes"
tech-stack:
  added: []
  patterns:
    - "ctx.register_hook(event, callback) plugin contract (NOT the deleted agent.on Protocol style, MP-1)"
    - "**kwargs forward-compat handlers — tolerate unexpected kwargs, never raise into Hermes (MP-2 / T-06-06)"
    - "Module-level _DEBUG read once at import; tests patch the attribute, not setenv-after-import"
    - "repr(v)[:120] truncation in debug logging — full PII-bearing hook bodies never logged (T-06-07)"
key-files:
  created:
    - src/kajiba/plugin/hooks.py
    - src/kajiba/plugin/__init__.py
    - src/kajiba/plugin/plugin.yaml
  modified: []
decisions:
  - "Whole handler body (incl. the _log_kwargs call) wrapped in try/except, not just the collector dispatch — strictly honors 'never raise into Hermes' (T-06-06) even if _log_kwargs were to fail; functionally equivalent to the PATTERNS skeleton since _log_kwargs cannot realistically raise on dict iteration."
  - "post_llm_call/post_tool_call are debug-log-only stubs with empty named={} and all payload flowing through **kwargs — turn/tool assembly deferred to Phase 7 (kwarg shapes [ASSUMED] until Plan 05 confirms live, locked scope boundary)."
  - "plugin.yaml version 0.2.0 matches the SCHEMA_VERSION family (0.2.0) bumped in Phase 10; manifest field names commented [ASSUMED] pending Plan 05 live load."
  - "kajiba.plugin.hooks imports as a namespace package even before __init__.py exists — Task 1's two handler/debug tests passed pre-__init__; Task 2 added register wiring + manifest."
metrics:
  duration: ~6m
  completed: 2026-06-04
---

# Phase 6 Plan 03: Kajiba Hermes Plugin Package Summary

Greenfield `src/kajiba/plugin/` package that replaces the deleted `hermes_integration.py`: `register(ctx)` wires the four Hermes lifecycle hooks via `ctx.register_hook` fault-tolerantly, the four handlers tolerate unexpected kwargs and dispatch to the unchanged `KajibaCollector`, and a permanent `KAJIBA_DEBUG=1` mode logs every hook's kwarg names/types/truncated-values — the designed mechanism Plan 05 uses to capture the ground-truth hook payloads that unblock Phase 7. All three Plan 01 RED plugin tests turn GREEN.

## What Was Built

**Task 1 — `src/kajiba/plugin/hooks.py` (commit c4b26d8)**
Module docstring (handler role + Phase 6 scope note). Top-level: `_collector: Optional[KajibaCollector] = None`, `_DEBUG = os.environ.get("KAJIBA_DEBUG") == "1"`. `set_collector(collector)` installs the singleton. `_log_kwargs(hook_name, named, extra)` early-returns unless `_DEBUG`, then loops `{**named, **extra}.items()` emitting one `logger.warning("KAJIBA_DEBUG %s kwarg %s: type=%s value=%s", ...)` per kwarg with `repr(v)[:120]` truncation (PII safety, %s lazy logging). Four handlers, each `**kwargs`-tolerant and wrapped in `try/except Exception + logger.exception` (never raise into Hermes):
- `on_session_start(session_id=None, model=None, platform=None, **kwargs)` → `_log_kwargs` + dispatch `_collector.on_session_start(session_id=, model_name=model, platform=platform)` if collector set.
- `on_post_llm_call(**kwargs)` → `_log_kwargs` only (capture stub, Phase 7 assembles turns).
- `on_post_tool_call(**kwargs)` → `_log_kwargs` only.
- `on_session_end(session_id=None, **kwargs)` → `_log_kwargs` + dispatch `_collector.on_session_end(session_id=)`.
No `print(` anywhere (debug uses `logger.warning`).

**Task 2 — `src/kajiba/plugin/__init__.py` + `src/kajiba/plugin/plugin.yaml` (commit 60adf3b)**
`__init__.py`: module docstring, imports `KajibaCollector` + the four handlers + `set_collector` from `kajiba.plugin.hooks`. `register(ctx) -> None` with a Google docstring; body wrapped in `try/except Exception + logger.exception("Kajiba plugin registration failed; plugin disabled")`. Inside: `set_collector(KajibaCollector())`, four `ctx.register_hook("<event>", handler)` calls using the exact strings `on_session_start`/`post_llm_call`/`post_tool_call`/`on_session_end`, then a `logger.info` naming the registered hooks. Uses `ctx.register_hook` (NOT `ctx.on`); no HermesAgent Protocol (MP-1 avoided).
`plugin.yaml`: `name: kajiba`, `version: "0.2.0"`, `description`, `provides_hooks` listing the four events, `provides_tools: []`; a header comment marks the manifest field names `[ASSUMED]` until Plan 05's live load.

## Verification Results

- `python -m pytest tests/test_plugin.py -x` → **3 passed** (`test_register_hooks`, `test_handlers_accept_extra_kwarg`, `test_debug_logging` — all Plan 01 RED → GREEN).
- `python -c "from kajiba.plugin import register; print(register)"` → imports cleanly (`<function register ...>`).
- `python -m pytest` full suite → **327 passed, 2 skipped** (324 baseline + 3 new plugin tests; the 2 skips are the pre-existing yaml-soft-dep skips). **0 regressions.**
- `grep -c "print(" src/kajiba/plugin/hooks.py` → 0 (debug uses logger.warning only).
- `plugin.yaml` present inside `src/kajiba/plugin/` so the Plan 04 symlink exposes it.

## Requirements Satisfied

- **PLUG-01** — `src/kajiba/plugin/` package created (`__init__.py` register, `hooks.py` 4 handlers + KAJIBA_DEBUG, `plugin.yaml` manifest).
- **PLUG-02** — `register(ctx)` registers the four lifecycle hooks via `ctx.register_hook`, fault-tolerantly.
- **CAPT-01** (code half) — handlers tolerate unexpected kwargs (MP-2); `KAJIBA_DEBUG=1` logs kwarg names/types/values. Live capture (the data half) is Plan 05.

## Threat Mitigations Applied

- **T-06-06** (DoS — register/handler crashing Hermes): `register(ctx)` and every handler body wrapped in `try/except Exception + logger.exception`; never raise into the host.
- **T-06-07** (Info disclosure — debug logging raw PII): `_log_kwargs` truncates every value to `repr[:120]`, logs type+name primarily, and is opt-in (OFF unless `KAJIBA_DEBUG=1`). Full bodies never logged.
- **T-06-08** (symlink code execution): accept disposition — local-first single-operator model, symlink points into the developer's own trusted repo. No code change needed.

## Phase 7 Boundary Respected

`on_post_llm_call` / `on_post_tool_call` are debug-log-only stubs — they do NOT call any collector turn-assembly method with guessed kwarg shapes. All hook kwarg names (`session_id`, `model`, `platform`) remain `[ASSUMED]` until Plan 05's live session confirms them and records them in `06-HOOK-KWARGS.md`.

## Deviations from Plan

None — plan executed exactly as written. Rules 1–4 not triggered. One documented choice (see frontmatter `decisions`): the whole handler body, including the `_log_kwargs` call, is inside `try/except` rather than only the collector dispatch — a strict reading of "never raise into Hermes" (T-06-06), functionally equivalent to the PATTERNS skeleton.

## Self-Check: PASSED

- src/kajiba/plugin/hooks.py — FOUND
- src/kajiba/plugin/__init__.py — FOUND
- src/kajiba/plugin/plugin.yaml — FOUND
- commit c4b26d8 — FOUND
- commit 60adf3b — FOUND
