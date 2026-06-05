---
phase: 07-turn-capture-semantic-pii-scrubbing
plan: 01
subsystem: capture-foundation
tags: [packaging, tdd, red-scaffolds, collector, plugin-hooks, llm-scrub]
requires:
  - "06-HOOK-KWARGS.md (live-verified Hermes v0.15.x hook kwargs)"
  - "src/kajiba/collector.py (existing on_session_start/on_turn_complete/on_session_end)"
  - "src/kajiba/plugin/hooks.py (Phase 6 debug-only post_llm_call/post_tool_call stubs)"
provides:
  - "Populated [llm-scrub] optional-dependencies extra (gliner/torch/transformers/ollama)"
  - "RED collector capture scaffolds (llm_turn, tool_buffer, session_end_once, ollama_metadata, remote_degrade)"
  - "RED plugin hook-dispatch + fault-tolerance scaffolds (post_llm, post_tool, fault)"
affects:
  - "07-02 (GLiNER install lane depends on the [llm-scrub] extra)"
  - "07-03 (collector + hook implementation must turn these RED scaffolds GREEN)"
tech-stack:
  added:
    - "gliner>=0.2.26 (declared, not installed)"
    - "torch>=2.12.0 (declared, not installed)"
    - "transformers>=5.0 (declared, not installed)"
    - "ollama>=0.6.2 (declared, not installed)"
  patterns:
    - "RED-first TDD: scaffolds reference not-yet-built collector methods (on_llm_turn/on_tool_call)"
    - "Soft-dep declaration in optional-dependencies, never core dependencies (D-10 import-clean)"
key-files:
  created: []
  modified:
    - "pyproject.toml"
    - "tests/test_collector.py"
    - "tests/test_plugin.py"
decisions:
  - "Encoded the four CRITICAL CORRECTIONS as executable assertions so 07-03 cannot reintroduce the bugs"
  - "Fault-tolerance tests assert a contract that already holds (debug-only hooks never raise) and must keep holding post-promotion — they pass now; the dispatch tests carry the RED signal"
metrics:
  duration: 11m
  completed: 2026-06-05
---

# Phase 7 Plan 01: Capture Foundation (packaging + RED scaffolds) Summary

Populated the `[llm-scrub]` packaging extra (PRIV-04/D-10) and authored the RED
TDD scaffolds that pin the collector + plugin-hook capture surface — encoding the
four CRITICAL CORRECTIONS (one staging file per session, `ok`→`success`, no
double-count, ollama soft-import) as failing assertions before any implementation
exists.

## What Was Built

### Task 1 — `[llm-scrub]` extra (PRIV-04/D-10) · commit `c96519e`
Replaced the empty `llm-scrub = []` with the four slopcheck-clean packages from
RESEARCH §Standard Stack, lower-bound pinned: `gliner>=0.2.26`, `torch>=2.12.0`,
`transformers>=5.0`, `ollama>=0.6.2`. Core `dependencies` untouched; verified
`import kajiba; import kajiba.cli/scrubber/collector` exits 0 WITHOUT the ML deps
installed (core import-clean, T-07-01). No packages were installed — declaration
only (the GLiNER install lane is 07-02; live run is 07-05). All four passed
slopcheck (RESEARCH §Package Legitimacy Audit), so no legitimacy checkpoint fired.

### Task 2 — RED collector capture scaffolds (CAPT-02/03/04) · commit `f57dfcc`
Five test groups appended to `tests/test_collector.py`, using the exact
07-VALIDATION `-k` selectors:
- `llm_turn` — one `on_llm_turn(user_message, assistant_response, turn_id)` appends
  exactly one `human` + one `gpt` turn (CAPT-02); a populated `conversation_history`
  adds NO extra turns (Correction 4 — no double-count).
- `tool_buffer` — a tool event keyed by `turn_id` with `status="ok"` yields a
  `ToolCall` with `tool_status == "success"` (Correction 2); duplicate
  `tool_call_id` dedups to one; `result` (JSON str, 06-HOOK-KWARGS finding 3) parsed
  into `tool_output`; `args` (dict) serialized into `tool_input`.
- `session_end_once` — N `on_session_end` firings for one session produce EXACTLY
  ONE staging file (asserts a file COUNT of 1, Correction 3) and that file reflects
  the full accumulated trajectory (`turn_count` grows to 4, does not reset).
- `ollama_metadata` — `ollama.show()` monkeypatched (synthetic module in
  `sys.modules`) populates `parameter_count`/`quantization`/`model_family`/
  `context_window`/`model_hash` (CAPT-04, mocked).
- `remote_degrade` — ollama absent + remote slug yields `is_local=False`,
  slug-inferred `provider`/`model_family`, param/quant/hash `None`,
  `HardwareProfile.inference_backend` set (D-03); no exception propagates.

All 9 new tests are RED on unimplemented behavior; the 19 pre-existing collector
tests stay green.

### Task 3 — RED hook-dispatch scaffolds · commit `9561970`
Appended to `tests/test_plugin.py` (kwarg payloads verbatim from 06-HOOK-KWARGS):
- `TestHookDispatch` (selectors `post_llm`/`post_tool`/`dispatch`) — asserts the
  promoted `on_post_llm_call` dispatches to `collector.on_llm_turn` with
  `user_message`/`assistant_response`/`turn_id`, and `on_post_tool_call` dispatches
  to `collector.on_tool_call` with `tool_name`/`args`/`result`/`tool_call_id`/
  `turn_id`/`status`. Both are RED (hooks are still debug-log-only).
- `TestHookFaultTolerance` (selector `fault`) — asserts a raising collector method
  does NOT propagate out of either hook. See note below.

## Deviations from Plan

None — plan executed as written. One clarification worth recording (not a code
deviation):

**Fault-tolerance tests pass now (by design).** The two `fault` tests assert the
try/except contract that the Phase 6 hooks already satisfy (the debug-only stubs
never call a collector, so nothing can raise). They are GREEN today and must STAY
green after 07-03 promotes the hooks to real dispatch. The RED signal for this
plan is carried by the two `dispatch` tests (collector not invoked yet) — so the
plan's verify command (`-k "post_llm or post_tool or dispatch or fault" -x`)
correctly exits non-zero (RED). This matches the acceptance criterion ("a test
asserts a raising collector method does NOT propagate") — that assertion is meant
to hold, not fail.

## Verification

- New RED selectors RED: `pytest tests/test_collector.py -k "llm_turn or tool_buffer or session_end_once or ollama_metadata or remote_degrade"` → 9 failed; `tests/test_plugin.py -k "post_llm or post_tool or dispatch or fault" -x` → exits non-zero.
- Each of the five collector selectors and the plugin dispatch selectors collect ≥1 test.
- `session_end_once` asserts a file COUNT of exactly 1 (not just existence).
- Full suite excluding the new RED selectors: **312 passed, 2 pre-existing skips, 0 regressions**.
- `python -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))"` parses; core import-clean verified.

## Known Stubs

None introduced. The RED scaffolds are intentional pre-implementation failures
(TDD RED), to be turned GREEN by 07-03 — not stubs that ship inert behavior.

## Self-Check: PASSED
