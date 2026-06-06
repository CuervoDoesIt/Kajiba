---
phase: 07-turn-capture-semantic-pii-scrubbing
verified: 2026-06-05T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: none
  previous_score: n/a
---

# Phase 7: Turn Capture + Semantic PII Scrubbing Verification Report

**Phase Goal:** Real Hermes session data is captured into KajibaRecord objects and scrubbed by both regex and semantic PII layers
**Verified:** 2026-06-05
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User and assistant turns captured as ConversationTurn with correct role attribution | ✓ VERIFIED | `collector.py:443-485` `on_llm_turn` appends one `human` then one `gpt` ConversationTurn; `conversation_history` accepted for context only, never re-ingested (no double-count). Test `test_llm_turn_appends_paired_human_and_gpt` + `test_llm_turn_history_does_not_double_count` pass. Hook `on_post_llm_call` (`hooks.py:91-115`) dispatches to it. |
| 2 | Tool calls from `post_tool_call` attached to correct assistant turn via pending buffer | ✓ VERIFIED | `collector.py:487-570` `on_tool_call`: turn_id-keyed `_pending_tools` buffer, `_seen_tool_call_ids` dedup, attaches to existing gpt turn via `_gpt_turn_index` or buffers; `_map_tool_status` maps `"ok"`→`"success"` (raw "ok" never stored). Tests `test_tool_buffer_status_ok_maps_to_success`, `test_tool_buffer_dedups_on_tool_call_id`, `test_tool_buffer_parses_result_and_serializes_args` pass. Hook `on_post_tool_call` dispatches. |
| 3 | Model metadata (param count, quantization, family, context length) captured from Ollama into ModelMetadata | ✓ VERIFIED | `collector.py:169-216` `_enrich_from_ollama` soft-imports `ollama`, calls `ollama.show()`, extracts `parameter_size`/`quantization_level`/`family`/`.context_length`/`digest`; `_build_metadata_and_hardware` detects local Ollama and degrades to slug inference when remote (`test_ollama_metadata_populates_model_fields`, `test_remote_degrade_leaves_params_none_no_raise` pass). **LIVE proof (DGX):** real `ollama.show()` returned `8.0B / Q4_0 / llama / 131072` — all four fields non-null (07-LIVE-CAPTURE.md, 07-DGX-EVIDENCE.md). |
| 4 | `kajiba preview` shows GLiNER-detected person/company/project names redacted (not just regex) | ✓ VERIFIED | `scrubber_semantic.py` loads `nvidia/gliner-PII` with labels person/company/organization/project/location; `cli.py:531-575` `_apply_semantic_layer` composes Layer C after Layer B at all 3 scrub_record sites, folds GLiNER flags into the shared `all_flagged` channel and updates ScrubLog counts. **LIVE proof (DGX):** Layer C ran on real captured prose; preview surfaced a 0.52-confidence flag in the review panel (07-LIVE-CAPTURE.md). LANE-B detect test (`test_scrubber_semantic.py`) passes when `[llm-scrub]` present. |
| 5 | Entities with confidence 0.4–0.7 flagged for human review rather than auto-redacted | ✓ VERIFIED | `scrubber_semantic.py:86-123` `classify_band`/`partition_spans` implement D-05 bands: >=0.7 redact, 0.4–0.7 flag, <0.4 ignore. Verified live: `classify_band(0.70)→redact`, `(0.55)→flag`, `(0.30)→ignore`. Asymmetric coverage (D-07): turn `value` redacts+flags, tool fields FLAG-ONLY. Band tests (LANE-A) pass without the extra. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/kajiba/collector.py` | Paired-turn capture, tool buffer, ollama enrichment, finalize-once | ✓ VERIFIED | `_pending_tools`, `on_llm_turn`, `on_tool_call`, `_enrich_from_ollama` all present and tested. Imported by `hooks.py`. |
| `src/kajiba/plugin/hooks.py` | Promoted hooks dispatch to collector | ✓ VERIFIED | `on_post_llm_call`/`on_post_tool_call` extract live-verified kwargs and call collector; fault-tolerant. Dispatch tests pass. |
| `src/kajiba/scrubber_semantic.py` | GLiNER Layer-C detector: bands, asymmetric, soft-import | ✓ VERIFIED | `nvidia/gliner-PII`, D-05 bands, D-07 asymmetric, soft-import → `SemanticScrubUnavailable`, reuses `FlaggedItem`. |
| `src/kajiba/scrubber_llm.py` | Retired stub re-pointed to scrubber_semantic | ✓ VERIFIED | Module deprecated; re-exports new surface; `scrub_semantic()` raises `SemanticScrubUnavailable` (NotImplementedError removed). |
| `src/kajiba/cli.py` | Layer-C wiring + flags into preview panel | ✓ VERIFIED | `_apply_semantic_layer` wired at preview/submit/export sites; graceful degrade on missing extra. |
| `pyproject.toml` | `[llm-scrub]` extra | ✓ VERIFIED | Lists gliner>=0.2.26, torch>=2.12.0, transformers>=5.0, ollama>=0.6.2. |
| `tests/fixtures/code_content_pii.json` | D-06 calibration fixture | ✓ VERIFIED | Loaded by calibration test; known-safe code identifiers + seeded true-positive names. |
| `07-LIVE-CAPTURE.md` | D-02 live proof artifact | ✓ VERIFIED | Documents real ollama.show() metadata, finalize-once, GLiNER Layer C, FP rate 0.0000. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `hooks.py` | collector paired-turn/tool methods | kwarg extraction + dispatch | ✓ WIRED | `_collector.on_llm_turn(...)` / `_collector.on_tool_call(...)` |
| `collector.on_session_end` | `session_{id}.json` | idempotent overwrite | ✓ WIRED | `_save_to_staging` writes `session_{id}.json`; finalize-once test passes |
| `scrubber_semantic` | `scrubber.FlaggedItem` | reuse container (D-08) | ✓ WIRED | `from kajiba.scrubber import FlaggedItem` |
| `scrubber_semantic` | `gliner.GLiNER.from_pretrained` | soft-import singleton | ✓ WIRED | `_get_model` loads + caches; raises SemanticScrubUnavailable when absent |
| `cli.py preview` | `scrub_record_semantic` | Layer C after Layer B in try/except | ✓ WIRED | `_apply_semantic_layer` |
| semantic FlaggedItems | `_render_preview(flagged_items=)` | extend `all_flagged` | ✓ WIRED | `combined_flagged = regex + semantic` |
| `ollama.show()` | `ModelMetadata.parameter_count` | `_enrich_from_ollama` on real model | ✓ WIRED | Live: parameter_count="8.0B" non-null |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Core imports clean without `[llm-scrub]` | `python -c "import kajiba.collector, kajiba.scrubber_semantic, kajiba.cli, kajiba.plugin.hooks, kajiba.scrubber_llm"` | imports clean | ✓ PASS |
| Band logic (D-05) | `classify_band(0.70/0.55/0.30)` | redact / flag / ignore | ✓ PASS |
| `[llm-scrub]` extras absent on this box | find_spec gliner/ollama | both False (so LANE-B/live correctly evidenced by DGX) | ✓ PASS |
| Full test suite | `python -m pytest -q` | 430 passed, 16 skipped | ✓ PASS |

The 16 skips are expected: PyYAML soft-dep CLI tests + LANE-B GLiNER/Ollama-gated tests (no `[llm-scrub]` on this Windows box). `test_scrubber_semantic.py`: 8 LANE-A passed, 2 LANE-B skipped — exactly as designed.

### Live-Data Criteria (DGX Spark evidence)

SC#3, SC#4, and PRIV-03 require the `[llm-scrub]` ML extra and a live local-Ollama Hermes session, neither of which exists on the Windows dev box. The live proof is archived on the DGX Spark (NVIDIA GB10):

| Live criterion | Evidence | Status |
|----------------|----------|--------|
| SC#3 / CAPT-04 — real ollama.show() metadata | `8.0B / Q4_0 / llama / 131072` all non-null, sessions `..._184953_e52b56` (CPU) + `..._192518_ea3f16` (GPU) | ✓ PROVEN |
| SC#4 / PRIV-01 — GLiNER Layer C on real prose | `nvidia/gliner-PII` loaded on CUDA; preview surfaced 1 flag@0.52 | ✓ PROVEN |
| PRIV-03 — D-06 calibration hard gate | `CALIBRATION_FP_RATE=0.0000 flag_band=0` on real model; zero of 16 known-safe code identifiers auto-redacted | ✓ PROVEN |
| Finalize-once on real data | exactly one staging file per session (cleaned dir before run) | ✓ PROVEN |

Cited commits `3796e99`, `ef64e88`, `c29f8e9`, `ef1249c` all exist in the repo. The D-06 calibration test assertion was corrected in `ef64e88` (asserts `false_positives == []`, the actual D-06 intent) — verified by reading the current test source.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CAPT-02 | 07-01, 07-03 | User/assistant turns into ConversationTurn | ✓ SATISFIED | `on_llm_turn` + paired-turn tests |
| CAPT-03 | 07-01, 07-03 | Tool calls attached via pending buffer | ✓ SATISFIED | `on_tool_call` buffer/dedup + tests |
| CAPT-04 | 07-01, 07-03, 07-06 | Full metadata via ollama.show() | ✓ SATISFIED | `_enrich_from_ollama` + DGX live proof |
| PRIV-01 | 07-02, 07-04, 07-05, 07-06 | GLiNER semantic PII detection | ✓ SATISFIED | `scrubber_semantic.py` + DGX live Layer C |
| PRIV-02 | 07-02, 07-04, 07-05 | Confidence bands (auto/flag/ignore) | ✓ SATISFIED | `classify_band`/`partition_spans` + tests |
| PRIV-03 | 07-02, 07-04, 07-06 | Calibration FP rate on code fixtures | ✓ SATISFIED | D-06 gate `FP_RATE=0.0000` on DGX (LANE-B gated on this box, evidenced by artifact) |
| PRIV-04 | 07-01, 07-05 | `[llm-scrub]` extra + graceful degrade | ✓ SATISFIED | pyproject extra declared; CLI degrade verified |

All 7 phase requirement IDs accounted for. REQUIREMENTS.md marks PRIV-03 "Pending (LANE-B gated)" — the gate is proven green on the DGX; the LANE-B test correctly skips on this box without the extra. No orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No TBD/FIXME/XXX in modified source | — | None |
| scrubber_semantic.py | 60-61 | `PLACEHOLDER_PERSON`/`PLACEHOLDER_NAME` | ℹ️ Info | Legitimate `[REDACTED_*]` tag constants, not stubs |

No blocker or warning anti-patterns. The retired `scrubber_llm` stub now raises `SemanticScrubUnavailable` (its prior `NotImplementedError` is gone) and re-exports the real surface.

### Human Verification Required

None. The two manual-only verifications from 07-VALIDATION.md (live local-Ollama capture populating real metadata; GLiNER first-load model download) are both evidenced by the DGX artifacts (07-LIVE-CAPTURE.md, 07-DGX-EVIDENCE.md, 07-DGX-LIVE-CAPTURE.md), treated here as the manual-verification evidence for the live-only criteria per the phase's hybrid verification design.

### Gaps Summary

No gaps. All five ROADMAP success criteria are achieved: the implementing code for turn capture (paired-turn + tool buffer + ok→success + finalize-once), Ollama metadata enrichment, GLiNER band logic, and CLI Layer-C wiring all exist, are substantive, and are wired end-to-end. The unit-testable behavior is green on this Windows machine (430 passed / 16 expected skips). The three live-data criteria (SC#3 metadata, SC#4 GLiNER on real prose, PRIV-03 D-06 calibration gate) are proven on the DGX Spark with non-null real metadata (8.0B/Q4_0/llama/131072), an active Layer-C preview flag, and `CALIBRATION_FP_RATE=0.0000`. The phase goal — real Hermes session data captured into KajibaRecord objects and scrubbed by both regex and semantic PII layers — is achieved.

---

_Verified: 2026-06-05_
_Verifier: Claude (gsd-verifier)_
