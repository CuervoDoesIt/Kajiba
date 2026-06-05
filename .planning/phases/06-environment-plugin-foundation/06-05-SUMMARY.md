---
phase: 06-environment-plugin-foundation
plan: 05
subsystem: infra
tags: [hermes, plugin, hooks, kwargs, payload-schema, v0.15.x, native-windows]

# Dependency graph
requires:
  - phase: 06-03
    provides: "src/kajiba/plugin/ package (register(ctx) + 4 hooks + KAJIBA_DEBUG diagnostic mode)"
  - phase: 06-04
    provides: "native-Windows v0.15.x setup guide (install -> editable-install -> resolve discovery dir -> enable -> load)"
provides:
  - "06-HOOK-KWARGS.md: the living v0.15.x hook payload contract, dual-tagged [DOCUMENTED v0.15.x] + [VERIFIED] for all four hooks"
  - "Confirmed plugin discovery dir under overridden HERMES_HOME (<HERMES_HOME>/plugins/) (D-17)"
  - "plugin.yaml manifest tags promoted to [CONFIRMED v0.15.x] (D-18)"
  - "Confirmed post_tool_call.result is a JSON str; args is a dict"
  - "Confirmed on_session_end is turn-scoped (per run_conversation), not session-final"
affects: [07-turn-capture, 14-live-experiment-capture]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dual-tag payload contract: [DOCUMENTED v0.15.x] (from official docs) + [VERIFIED] (from live capture); undocumented extras tagged [VERIFIED]-only"
    - "Synthetic-placeholder PII discipline when transcribing live debug captures into committed artifacts (T-06-11)"

key-files:
  created:
    - .planning/phases/06-environment-plugin-foundation/06-HOOK-KWARGS.md
  modified:
    - src/kajiba/plugin/plugin.yaml

key-decisions:
  - "06-HOOK-KWARGS.md is the single living record of the v0.15.x hook contract; Phase 7 turn/tool assembly builds on it"
  - "plugin.yaml header promoted [ASSUMED] -> [CONFIRMED v0.15.x] (comment-only; no field rename)"
  - "Native-Windows dev path documented as COPY fallback (symlink needs admin/Developer Mode); plugin installed editable into the Hermes venv, not the repo .venv"

patterns-established:
  - "Pattern 1: dual-tagged hook payload contract artifact (documented + verified) closing the no-published-schema blocker"
  - "Pattern 2: live debug captures transcribed as types/shapes with synthetic PII placeholders"

requirements-completed: [ENV-01, ENV-02, ENV-03, PLUG-01, PLUG-02, CAPT-01]

# Metrics
duration: 2min
completed: 2026-06-05
---

# Phase 6 Plan 5: Live v0.15.x Hook-Kwargs Verification Summary

**Live Hermes v0.15.1 native-Windows session confirmed all four lifecycle hooks fire on a remote backend, capturing their real kwargs into 06-HOOK-KWARGS.md (dual-tagged documented + verified) and promoting plugin.yaml to [CONFIRMED v0.15.x].**

## Performance

- **Duration:** 2 min (CLAUDE authoring portion; the live human-verify session and discovery-dir resolution happened out of band)
- **Started:** 2026-06-05T15:21:51Z
- **Completed:** 2026-06-05T15:23:59Z
- **Tasks:** 2 CLAUDE tasks (the 2 live checkpoint:human-verify tasks were completed out of band)
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments

- Wrote `06-HOOK-KWARGS.md` - the living v0.15.x hook payload contract: per-hook
  kwarg tables for `on_session_start`, `post_llm_call`, `post_tool_call`,
  `on_session_end`, each kwarg dual-tagged `[DOCUMENTED v0.15.x]` + `[VERIFIED]`
  (undocumented extras tagged `[VERIFIED]`-only). Permanently closes the old
  "no formal payload schema published" blocker (D-16/D-21).
- Recorded 8 cross-cutting findings: `telemetry_schema_version="hermes.observer.v1"`
  on all four hooks; `on_session_end` is turn-scoped (per `run_conversation`);
  `post_tool_call.result` is a JSON `str` while `args` is a `dict`;
  `task_id`/`turn_id`/`tool_call_id`/`api_request_id` correlation identity; the
  D-17 discovery dir; D-19 enable requirement; ENV-03 copy fallback; Hermes-venv
  install.
- Added a Phase 7 implications section mapping `post_llm_call` /
  `post_tool_call` kwargs to the collector turn/tool assembly inputs
  (CAPT-02/CAPT-03), and flagging session-end as turn-scoped.
- Promoted `src/kajiba/plugin/plugin.yaml` header tag `[ASSUMED]` ->
  `[CONFIRMED v0.15.x]` (D-18; comment-only). Plugin tests stay green.

## Task Commits

Each task was committed atomically:

1. **Task 1: record live v0.15.x hook kwargs in 06-HOOK-KWARGS.md** - `e401885` (docs)
2. **Task 2: promote plugin.yaml manifest tags to [CONFIRMED v0.15.x]** - `3b13724` (docs)

_Note: the two live `checkpoint:human-verify` tasks (resolve discovery dir + enable + load; run the ~15-min KAJIBA_DEBUG=1 session) were completed out of band by the developer; their captured data seeded the two commits above._

## Files Created/Modified

- `.planning/phases/06-environment-plugin-foundation/06-HOOK-KWARGS.md` - NEW. The
  dual-tagged living v0.15.x hook contract (four per-hook tables + 8 cross-cutting
  findings + Phase 7 implications), with synthetic PII placeholders.
- `src/kajiba/plugin/plugin.yaml` - header comment promoted `[ASSUMED]` ->
  `[CONFIRMED v0.15.x]` (no field rename).

## Decisions Made

- **Live verification autonomous:false (live human-in-the-loop).** The four hooks
  cannot be unit-tested on the host; the developer ran a ~15-min Hermes v0.15.1
  session on a remote backend (model `nvidia/nemotron-3-ultra:free` via
  OpenRouter; an earlier same-build run used `claude-opus-4-8`) with
  `KAJIBA_DEBUG=1`, and all four hooks fired. The startup line
  `Kajiba registered hooks: on_session_start, post_llm_call, post_tool_call, on_session_end`
  confirmed `register(ctx)` ran.
- **Discovery dir (D-17):** Hermes scans `<HERMES_HOME>/plugins/`, i.e.
  `%LOCALAPPDATA%\hermes\plugins\` under the overridden
  `HERMES_HOME=%LOCALAPPDATA%\hermes` (NOT `%USERPROFILE%\.hermes\plugins\`).
  Confirmed both from the installed source and live via `hermes plugins list`
  (`kajiba`, `source=user`). This sets the D-02 symlink target.
- **Enable required (D-19):** `hermes plugins enable kajiba` was required - the
  plugin was discovered but inert until enabled.
- **Native-Windows dev workflow (ENV-03):** symlink creation FAILED with
  "Administrator privilege required" (Developer Mode off); the COPY fallback was
  used and worked. Copy is the documented no-elevation dev path (edits require
  re-copy); symlink needs admin or Developer Mode.
- **Hermes-venv install:** the plugin must be importable in the Hermes venv
  (`%LOCALAPPDATA%\hermes\hermes-agent\venv`); installed editable via `uv`
  (`kajiba 0.2.0`). The dev repo `.venv` alone is not enough.
- **PII discipline (T-06-11):** synthetic/placeholder example values were used for
  `user_message`, `assistant_response`, `conversation_history`, and the
  `post_tool_call` result body - types and shapes only, no real conversation
  content transcribed.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None during the CLAUDE authoring portion. The live workflow surfaced two
environment realities now documented as findings (recorded, not blocking):
native-Windows symlink requires elevation (used copy fallback, ENV-03), and the
plugin must be installed into the Hermes venv rather than the repo `.venv`.

## Threat Model

- **T-06-11 (Information Disclosure)** - mitigated: `06-HOOK-KWARGS.md` uses
  synthetic placeholder values for all PII-bearing kwargs; only types/shapes are
  recorded. The `KAJIBA_DEBUG` `repr[:120]` truncation limits exposure at the log
  layer; debug logs kept local.
- **T-06-13 / T-06-SC** - accept (unchanged): the plugin load/enable targets the
  developer's own trusted repo; the plugin.yaml change is comment-only and adds no
  dependencies.

## Follow-up (Phase 7 territory - NOT edited here)

- `src/kajiba/plugin/hooks.py` docstrings still carry `[ASSUMED]` kwarg-name notes
  on the handler signatures. These are intentionally left for Phase 7, when the
  turn/tool hooks graduate from debug-log-only stubs to real ConversationTurn /
  ToolCall assembly and the confirmed kwarg names from 06-HOOK-KWARGS.md get
  wired in. Out of 06-05 scope.

## Next Phase Readiness

- 06-HOOK-KWARGS.md is the confirmed payload schema Phase 7 turn capture
  (CAPT-02/CAPT-03) depends on - the live half of the phase goal is closed.
- Plugin confirmed discovered, enabled, and loaded; all four hooks fire on a
  remote backend (no GPU/Ollama). ENV-01/ENV-02/ENV-03, PLUG-01/PLUG-02, CAPT-01
  satisfied.
- Note for the orchestrator: ROADMAP Phase 6 Success Criterion #1 and ENV-01/
  ENV-02 wording still name WSL2/GPU/Ollama/v0.6.0 as required (D-20 flag) - the
  native-Windows-primary intent is satisfied; reconcile wording via /gsd-phase.

## Self-Check: PASSED

Created files verified present:
- `.planning/phases/06-environment-plugin-foundation/06-HOOK-KWARGS.md` - FOUND
- `src/kajiba/plugin/plugin.yaml` - FOUND (modified, contains `CONFIRMED v0.15.x`)

Commits verified present:
- `e401885` - docs(06-05): record live v0.15.x hook kwargs in 06-HOOK-KWARGS.md
- `3b13724` - docs(06-05): promote plugin.yaml manifest tags to [CONFIRMED v0.15.x]

Plugin tests: `tests/test_plugin.py` 3/3 PASSED after the plugin.yaml edit.

---
*Phase: 06-environment-plugin-foundation*
*Completed: 2026-06-05*
