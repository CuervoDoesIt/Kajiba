---
phase: 07-turn-capture-semantic-pii-scrubbing
plan: 03
subsystem: collector + plugin hooks
tags: [capture, turns, tools, ollama, metadata, hermes-hooks, CAPT-02, CAPT-03, CAPT-04]
requires:
  - "07-01 RED capture scaffolds (test_collector.py, test_plugin.py)"
  - "06-HOOK-KWARGS.md live-verified Hermes v0.15.x payload contract"
provides:
  - "KajibaCollector.on_llm_turn paired-turn capture (human + gpt)"
  - "KajibaCollector.on_tool_call turn_id-keyed tool buffer with ok->success mapping"
  - "KajibaCollector._enrich_from_ollama + _build_metadata_and_hardware (CAPT-04)"
  - "finalize-once on_session_end (idempotent overwrite + _finalized guard)"
  - "promoted plugin hooks on_post_llm_call / on_post_tool_call (real dispatch)"
affects:
  - "07-04 (semantic scrub) consumes captured records; 07-05 live-validates capture"
tech-stack:
  added: ["ollama (soft-import, optional)"]
  patterns: ["soft-import + graceful degradation", "turn_id-keyed pending buffer", "idempotent-overwrite finalize-once", "fault-tolerant hook dispatch"]
key-files:
  created:
    - ".planning/phases/07-turn-capture-semantic-pii-scrubbing/deferred-items.md"
  modified:
    - "src/kajiba/collector.py"
    - "src/kajiba/plugin/hooks.py"
decisions:
  - "telemetry_schema_version stored as module constant TELEMETRY_SCHEMA_VERSION (no schema change)"
  - "platform (e.g. 'cli') is NOT the provider; provider is explicit or slug-inferred"
  - "Anthropic remote backend -> provider='custom' + inference_backend='anthropic' (Correction 5)"
metrics:
  duration: ~12m
  completed: 2026-06-05
---

# Phase 7 Plan 03: Turn/Tool Capture + Hook Dispatch Summary

Promoted the Phase 6 debug-only Hermes hook stubs into real turn/tool capture and
fixed the turn-scoped `on_session_end` correctness bug: one `post_llm_call` now
becomes a paired human+gpt `ConversationTurn`, tool events attach to the right
turn via a `turn_id`-keyed pending buffer with `ok`->`success` mapping, model
metadata enriches from `ollama.show()` locally and degrades to slug inference
remotely, and N per-turn session-end firings write exactly ONE staging file.

## What Was Built

### Task 1+2 — collector.py (committed `fad5b8a`)
The collector work for CAPT-02/03/04 and the session-end fix is a single file
(`collector.py`) coupled through `on_session_start`, so it landed as one atomic
commit covering both plan tasks:

- **`on_llm_turn(*, user_message, assistant_response, turn_id=None, **_)`** —
  appends exactly one `human` then one `gpt` `ConversationTurn` (CAPT-02). Any
  `conversation_history` kwarg is accepted for context only and never re-ingested
  (Correction 4 — no double-count). Flushes tools buffered under `turn_id` onto
  the gpt turn.
- **`on_tool_call(*, tool_name, args, result, tool_call_id, turn_id, status, error_type, error_message, duration_ms, **_)`**
  (CAPT-03) — maps status via `_map_tool_status` (error fields -> `error`/`timeout`;
  else `status=="ok"` -> `"success"` EXACTLY, Correction 2; raw `"ok"` never stored),
  `json.loads` the `result` JSON string with try/except fallback (finding 3) truncated
  to `[:2000]`, serializes the dict `args` into `tool_input` via `json.dumps(...)[:2000]`,
  dedups by `tool_call_id`, and attaches to the gpt turn for `turn_id` if present or
  buffers under `turn_id` (covers tool-before-turn and tool-after-turn orderings).
- **`_enrich_from_ollama(model_name)`** — psutil-style soft-import of `ollama`
  (`try: import ollama / except ImportError: return {}`) plus a second try/except
  around `ollama.show()` so remote sessions never error (D-01). Maps
  `details.parameter_size`/`quantization_level`/`family`, `model_info.*context_length`,
  and `digest` (handles dict-like and object-like returns, A1).
- **`_build_metadata_and_hardware(model_config)`** — always sets
  `model_name`/`provider`/`is_local`; detects local Ollama (explicit `provider=="ollama"`
  or a bare slug with no provider prefix) and enriches; remote slugs get light
  `_infer_provider_and_family` inference, params left None, and
  `HardwareProfile.inference_backend` set to the real backend (D-03).
- **`on_session_start`** signature extended to accept `provider` + `**_` and to
  stop mis-mapping `platform` onto `provider`. Resets all new buffer state.
- **finalize-once `on_session_end`** — ad-hoc mode keeps calling `_save_to_staging()`,
  which overwrites `session_{id}.json`, so N firings accumulate and yield ONE file
  (Correction 3). Continuous-mode auto-submit is gated by a `_finalized` once-flag.

### Task 3 — plugin/hooks.py (committed `cb67f21`)
- **`on_post_llm_call`** / **`on_post_tool_call`** promoted from debug-log-only
  stubs to real dispatch: each keeps `_log_kwargs(...)`, the `try/except Exception:
  logger.exception(...)` shell, and the `if _collector is not None` guard, then
  extracts the 06-HOOK-KWARGS payload via `kwargs.get(...)` (MP-2) and calls
  `on_llm_turn` / `on_tool_call`. No `pre_llm_call` registered (reserved for Phase 8).
- Module/handler docstrings updated to describe Phase 7 real-capture handlers.

## telemetry_schema_version Storage
Stored as the module constant `TELEMETRY_SCHEMA_VERSION = "hermes.observer.v1"` in
`collector.py`. `ModelMetadata` has no dedicated field, and the plan forbids a
schema change, so the value is held as a constant for a future schema bump to
read rather than folded into a free-text field (avoids polluting `inference_backend`,
which carries the real backend name). The hooks tolerate the incoming
`telemetry_schema_version` kwarg via `**_`/`kwargs` without error.

## Verification
- `python -m pytest tests/test_collector.py -k "llm_turn or tool_buffer"` — 5 passed.
- `python -m pytest tests/test_collector.py -k "ollama_metadata or remote_degrade or session_end_once"` — passed.
- `python -m pytest tests/test_plugin.py -k "post_llm or post_tool or dispatch or fault"` — 4 passed.
- `tests/test_collector.py tests/test_plugin.py` — **35 passed** (all 07-03 selectors GREEN; the two `fault` tests stayed green).
- `git diff --quiet src/kajiba/schema.py` — exit 0 (schema untouched; no `anthropic` literal added).
- `python -c "import kajiba.collector, kajiba.plugin.hooks"` — import clean without ollama/gliner installed.

## Deviations from Plan

### Structural (commit decomposition)
**Task 1 and Task 2 landed in a single commit (`fad5b8a`).** Both tasks edit only
`collector.py` and are inseparably coupled through `on_session_start`
(`_build_metadata_and_hardware` is invoked there and the buffer/finalize state is
reset there). Per-hunk staging of logically-interleaved edits in one file would not
produce independently-meaningful commits, so the collector capture (Task 1) and the
ollama/finalize-once work (Task 2) were committed together. Both tasks' acceptance
selectors pass (`llm_turn`/`tool_buffer` and `ollama_metadata`/`remote_degrade`/`session_end_once`).
No behavior was skipped or merged away.

### Auto-fixed
None. The four CRITICAL CORRECTIONS were implemented as designed; no bugs required
Rule 1/2/3 fixes during implementation.

## Deferred Issues (out of scope — logged, not fixed)
`tests/test_scrubber_semantic.py` has 8 RED tests failing on the absent
`kajiba.scrubber_semantic` module. Those are sibling-plan **07-04** RED scaffolds
committed by 07-02 (`2c8ded3`); 07-03 only touches `collector.py` and
`plugin/hooks.py`. Logged in `deferred-items.md`; NOT fixed (out of scope).

## Threat Model Outcomes
- **T-07-04 (Tampering, ToolCall)** mitigated — `_map_tool_status` maps `"ok"`->`"success"`,
  so `ToolStatusType` validation passes and no valid tool event is silently dropped.
  Validated by `tool_buffer` tests.
- **T-07-05 (DoS, Hermes session)** mitigated — every new collector method and both
  promoted hooks wrap their body in try/except and never propagate. Validated by `fault` tests.
- **T-07-07 (Tampering, core import surface)** mitigated — `ollama` is soft-imported
  inside `_enrich_from_ollama`; `import kajiba.collector` stays clean offline.
- **T-07-06 (Info Disclosure, error_message)** accepted this phase — raw capture is
  intentional; scrub runs at the CLI step (07-04), staging stays local under HERMES_HOME.

No new security surface beyond the plan's `<threat_model>` was introduced.

## Self-Check: PASSED
- FOUND: src/kajiba/collector.py (modified)
- FOUND: src/kajiba/plugin/hooks.py (modified)
- FOUND: .planning/phases/07-turn-capture-semantic-pii-scrubbing/deferred-items.md
- FOUND commit: fad5b8a (collector capture + metadata + finalize-once)
- FOUND commit: cb67f21 (hooks promotion)
- FOUND commit: 326859f (deferred-items)
