---
status: confirmed
phase: 06-environment-plugin-foundation
plan: 05
title: Hermes v0.15.x lifecycle hook kwargs - the living payload contract
source: live session 20260605_111446_5a978c on Hermes Agent v0.15.1 (build 2026.5.29), native Windows, remote backend
date: 2026-06-05
tags: [hermes, plugin, hooks, kwargs, payload-schema, v0.15.x]
related:
  - .planning/phases/06-environment-plugin-foundation/06-REPLAN-RESEARCH.md
  - .planning/phases/06-environment-plugin-foundation/06-CONTEXT.md
  - src/kajiba/plugin/hooks.py
  - src/kajiba/plugin/plugin.yaml
---

# Hermes v0.15.x Hook Kwargs - Living Payload Contract

This file is the single living record of the real Hermes Agent v0.15.x lifecycle
hook payload contract that Phase 7 turn/tool capture (CAPT-02/CAPT-03) builds on.

Each kwarg is dual-tagged:

- **[DOCUMENTED v0.15.x]** - present in the official v0.15.x signature table
  (`06-REPLAN-RESEARCH.md` section 3).
- **[VERIFIED]** - observed firing in the live session below.

Kwargs tagged **[VERIFIED]** with no **[DOCUMENTED v0.15.x]** tag are
*undocumented extras* - real kwargs Hermes v0.15.x passes that are NOT in the
published signature table. They are recorded here so Phase 7 can rely on them.

This artifact permanently closes the old "no formal payload schema published"
blocker (D-16, D-21).

## Capture Provenance

- **Live session id:** `20260605_111446_5a978c`
- **Hermes Agent:** v0.15.1 (build 2026.5.29), native Windows (no WSL2)
- **Backend:** REMOTE only - no GPU, no Ollama. Model
  `nvidia/nemotron-3-ultra:free` via OpenRouter for the captured run; an earlier
  same-build session used `claude-opus-4-8` (also remote). Hooks fire identically
  on any remote backend.
- **`platform` value:** `"cli"` on every hook.
- **Capture mechanism:** `KAJIBA_DEBUG=1` (built in 06-03). Debug line format:
  `KAJIBA_DEBUG <hook_label> kwarg <name>: type=<type> value=<repr[:120]>`.
  The `repr[:120]` truncation (T-06-07) limits raw-content exposure at the log
  layer; this document additionally uses synthetic/placeholder values for any
  PII-bearing kwarg (T-06-11) - it records TYPES and SHAPES, never real
  conversation content.
- **Startup log line observed:**
  `Kajiba registered hooks: on_session_start, post_llm_call, post_tool_call, on_session_end`
  (confirms `register(ctx)` ran live).

## PII Discipline (T-06-11)

Example values for `user_message`, `assistant_response`, `conversation_history`,
and the `post_tool_call` `result` body are SYNTHETIC PLACEHOLDERS. Only the
type and shape are real; no real prompt, response, or file content is
transcribed here. Run debug captures with throwaway, non-sensitive prompts and
keep debug logs local.

---

## Hook 1: on_session_start

Hermes event key: `on_session_start`. Debug label in logs: `on_session_start`.

| kwarg | type | example (synthetic where PII) | tag | notes |
|-------|------|-------------------------------|-----|-------|
| `session_id` | str | `"20260605_111446_5a978c"` | [DOCUMENTED v0.15.x][VERIFIED] | Hermes session identifier. Maps to collector `session_id`. |
| `model` | str | `"claude-opus-4-8"` or `"nvidia/nemotron-3-ultra:free"` | [DOCUMENTED v0.15.x][VERIFIED] | Model identity. Mapped hook `model` -> collector `model_name`. |
| `platform` | str | `"cli"` | [DOCUMENTED v0.15.x][VERIFIED] | Provider/platform for this session. |
| `telemetry_schema_version` | str | `"hermes.observer.v1"` | [VERIFIED] | Extra (not in documented table). Observer-schema marker stamped on every hook. See cross-cutting finding 1. |

---

## Hook 2: post_llm_call

Hermes event key: `post_llm_call`. Debug label in logs: `on_post_llm_call`.

| kwarg | type | example (synthetic where PII) | tag | notes |
|-------|------|-------------------------------|-----|-------|
| `session_id` | str | `"20260605_111446_5a978c"` | [DOCUMENTED v0.15.x][VERIFIED] | Hermes session identifier. |
| `user_message` | str | `"<user prompt text>"` (PII - placeholder) | [DOCUMENTED v0.15.x][VERIFIED] | The user's turn text. PII-bearing - shape only. |
| `assistant_response` | str | `"<assistant reply text>"` (PII - placeholder) | [DOCUMENTED v0.15.x][VERIFIED] | The model's reply text. PII-bearing - shape only. |
| `conversation_history` | list | `list[dict]` of `{"role": str, "content": str}` (PII - placeholder shape) | [DOCUMENTED v0.15.x][VERIFIED] | Prior turns. PII-bearing - shape only. |
| `model` | str | `"nvidia/nemotron-3-ultra:free"` | [DOCUMENTED v0.15.x][VERIFIED] | Model identity for the call. |
| `platform` | str | `"cli"` | [DOCUMENTED v0.15.x][VERIFIED] | Provider/platform. |
| `task_id` | str | `"20260605_111446_5a978c"` | [VERIFIED] | Extra. Correlation identity (often equals session id here). |
| `turn_id` | str | `"20260605_111446_5a978c:20260605_111446_5a978c:0cd552b7"` | [VERIFIED] | Extra. Format `"<session_id>:<task_id>:<8-hex>"`. Per-turn correlation key. |
| `telemetry_schema_version` | str | `"hermes.observer.v1"` | [VERIFIED] | Extra. Observer-schema marker (finding 1). |

**Documented-but-absent:** the documented `post_llm_call` signature does NOT
include `is_first_turn` - that kwarg belongs to `pre_llm_call`. Live capture
CONFIRMS `is_first_turn` is ABSENT from `post_llm_call`.

---

## Hook 3: post_tool_call

Hermes event key: `post_tool_call`. Debug label in logs: `on_post_tool_call`.

| kwarg | type | example (synthetic where PII) | tag | notes |
|-------|------|-------------------------------|-----|-------|
| `tool_name` | str | `"read_file"` | [DOCUMENTED v0.15.x][VERIFIED] | Name of the tool invoked. |
| `args` | dict | `{"path": "<path>"}` | [DOCUMENTED v0.15.x][VERIFIED] | Tool arguments. Arrives as a real `dict` (not a JSON string). |
| `result` | str | `'{"content": "<file text>"}'` (PII body - placeholder) | [DOCUMENTED v0.15.x][VERIFIED] | JSON STRING. CONFIRMS `result` is `str`, not a nested object (finding 3). Body PII-bearing - shape only. |
| `task_id` | str | `"20260605_111446_5a978c"` | [DOCUMENTED v0.15.x][VERIFIED] | Session/task correlation id. |
| `duration_ms` | int | `5141` | [DOCUMENTED v0.15.x][VERIFIED] | Tool execution time in milliseconds. |
| `session_id` | str | `"20260605_111446_5a978c"` | [VERIFIED] | Extra. Hermes session identifier. |
| `tool_call_id` | str | `"call_3ee741469cfa45b69e1b1d9f"` | [VERIFIED] | Extra. Unique per tool invocation - the tool-call dedup/correlation key. |
| `turn_id` | str | `"<session>:<task>:<8-hex>"` | [VERIFIED] | Extra. Ties this tool call to its turn. |
| `api_request_id` | str | `"<session>:<task>:<turnhash>:api:<n>"` | [VERIFIED] | Extra. Per-API-request correlation id within a turn. |
| `status` | str | `"ok"` | [VERIFIED] | Extra. `"ok"` on success. |
| `error_type` | str / None | `None` on success; `str` on error | [VERIFIED] | Extra. `NoneType` on success, error class name on failure. |
| `error_message` | str / None | `None` on success; `str` on error | [VERIFIED] | Extra. `NoneType` on success, message on failure. May carry PII on error - treat as sensitive. |
| `telemetry_schema_version` | str | `"hermes.observer.v1"` | [VERIFIED] | Extra. Observer-schema marker (finding 1). |

---

## Hook 4: on_session_end

Hermes event key: `on_session_end`. Debug label in logs: `on_session_end`.

| kwarg | type | example (synthetic where PII) | tag | notes |
|-------|------|-------------------------------|-----|-------|
| `session_id` | str | `"20260605_111446_5a978c"` | [DOCUMENTED v0.15.x][VERIFIED] | Hermes session identifier. |
| `completed` | bool | `True` | [DOCUMENTED v0.15.x][VERIFIED] | Whether the turn completed. Candidate Phase 7 outcome signal. |
| `interrupted` | bool | `False` (observed `True` when the user interrupts a turn) | [DOCUMENTED v0.15.x][VERIFIED] | Whether the turn was interrupted. Candidate Phase 7 outcome signal. |
| `model` | str | `"nvidia/nemotron-3-ultra:free"` | [DOCUMENTED v0.15.x][VERIFIED] | Model identity. |
| `platform` | str | `"cli"` | [DOCUMENTED v0.15.x][VERIFIED] | Provider/platform. |
| `task_id` | str | `"20260605_111446_5a978c"` | [VERIFIED] | Extra. Session/task correlation id. |
| `turn_id` | str | `"<session>:<task>:<8-hex>"` | [VERIFIED] | Extra. Per-turn correlation key. |
| `telemetry_schema_version` | str | `"hermes.observer.v1"` | [VERIFIED] | Extra. Observer-schema marker (finding 1). |

**Critical:** `on_session_end` fires per `run_conversation` (after EACH turn),
NOT once per session lifetime. See cross-cutting finding 2.

---

## Cross-cutting findings

These eight findings cut across hooks and the plugin load workflow. Record them
prominently - several change Phase 7 assumptions.

1. **`telemetry_schema_version="hermes.observer.v1"` on ALL FOUR hooks.**
   Hermes v0.15.x stamps every observer hook payload with this schema-version
   marker (matches `OBSERVER_SCHEMA_VERSION` in the installed
   `hermes_cli/plugins.py`). Phase 7 should record and/or branch on this value
   so capture can adapt if the observer schema version bumps.

2. **`on_session_end` is TURN-SCOPED, not session-final.** It fires once per
   `run_conversation` call (after each turn) - multiple `on_session_end` events
   were observed within one session. The official hook reference confirms:
   "on_session_end | End of every run_conversation call + CLI exit." Phase 7
   MUST NOT treat session-end as the single final event of a session; turn
   boundaries and final session teardown both surface here.

3. **`post_tool_call.result` is a JSON `str`; `args` is a `dict`.** This settles
   the old "Pitfall 7: is result a JSON string?" question. `result` arrives as a
   JSON string (e.g. `'{"content": "..."}'`) that the consumer must parse;
   `args` arrives already as a Python `dict`.

4. **Rich correlation identity on the turn/tool/end hooks.** `task_id` and
   `turn_id` appear on `post_llm_call`, `post_tool_call`, and `on_session_end` -
   richer than the documented signatures. `turn_id` format is
   `"<session_id>:<task_id>:<8-hex>"`. `post_tool_call` additionally carries
   `tool_call_id` and `api_request_id`. These enable precise turn/tool grouping
   in Phase 7 without inferring boundaries from event order.

5. **Discovery directory (D-17) - resolved from installed source AND confirmed
   live.** Hermes scans `get_hermes_home()/plugins`, i.e.
   `%LOCALAPPDATA%\hermes\plugins\` when `HERMES_HOME=%LOCALAPPDATA%\hermes`
   (NOT `%USERPROFILE%\.hermes\plugins\`). `get_hermes_home()` reads
   `HERMES_HOME` and falls back to `~/.hermes` (`hermes_constants.py`). Confirmed
   live: `hermes plugins list` shows `kajiba` with `source=user` from that dir.
   This sets the D-02 symlink target.

6. **`hermes plugins enable kajiba` is REQUIRED (D-19).** Standalone user
   plugins are opt-in via `plugins.enabled`; an un-enabled plugin loads with the
   error "not enabled in config". Confirmed: enable succeeded ("Plugin kajiba
   enabled. Takes effect on next session.") and `kajiba` then showed enabled.

7. **Native-Windows dev workflow: copy fallback (ENV-03).** A native-Windows
   symlink (`New-Item -ItemType SymbolicLink` / `mklink`) FAILED with
   "Administrator privilege required" (Developer Mode off). The COPY fallback
   was used and worked. Document COPY as the no-elevation dev path (edits require
   re-copy); symlink needs admin rights or Developer Mode enabled.

8. **Plugin must be importable in the Hermes venv.** The plugin was installed
   editable via `uv` into the Hermes venv
   (`%LOCALAPPDATA%\hermes\hermes-agent\venv`, `kajiba 0.2.0`). The dev repo
   `.venv` is NOT sufficient - Hermes imports the plugin from its own venv.

---

## Phase 7 implications

This section maps the confirmed kwargs to the collector turn/tool assembly
inputs that Phase 7 (CAPT-02/CAPT-03) will wire. Phase 6 hooks debug-log only;
Phase 7 promotes `post_llm_call` / `post_tool_call` from capture-only stubs to
real `ConversationTurn` / `ToolCall` assembly.

### Turn assembly (CAPT-02) from `post_llm_call`

| Collector turn input | Source kwarg | Notes |
|----------------------|--------------|-------|
| user turn content | `user_message` (str) | Scrub deferred to CLI step (never in hook). |
| assistant turn content | `assistant_response` (str) | Scrub deferred to CLI step. |
| prior context | `conversation_history` (list[dict] of `{role, content}`) | Use for ordering/dedup; avoid double-counting turns. |
| turn identity | `turn_id` (str, `"<session>:<task>:<8-hex>"`) | Primary key for grouping a turn's events. |
| model / platform | `model`, `platform` | Feed model metadata. |
| session | `session_id` | Ties the turn to its session record. |

### Tool assembly (CAPT-03) from `post_tool_call`

| Collector tool input | Source kwarg | Notes |
|----------------------|--------------|-------|
| tool name | `tool_name` (str) | Direct. |
| tool args | `args` (dict) | Already a dict - no parse needed. |
| tool result | `result` (str, JSON) | Parse the JSON string (finding 3) before storing structured output. |
| duration | `duration_ms` (int) | Direct. |
| tool-call identity | `tool_call_id` (str) | Per-invocation dedup/correlation key. |
| status / errors | `status`, `error_type`, `error_message` | `status="ok"` plus `None` error fields on success; populated on failure. Drives ToolCall status. |
| turn linkage | `turn_id`, `task_id`, `api_request_id` | Group tool calls under their turn. |

### Session-end handling (turn-scoped, finding 2)

`on_session_end` fires after EACH `run_conversation` turn AND at CLI exit. Phase 7
must treat it as a turn boundary signal, not a session-final signal. `completed`
/ `interrupted` are candidate outcome signals per turn; final session teardown
must be inferred from the last end event / CLI exit, not the first.

### Forward-compat

Record `telemetry_schema_version` (finding 1) with captured records so Phase 7
can detect an observer-schema bump beyond `hermes.observer.v1`.
