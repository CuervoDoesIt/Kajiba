---
phase: 07-turn-capture-semantic-pii-scrubbing
plan: 04
subsystem: pii-scrubbing
tags: [gliner, semantic-pii, layer-c, soft-import, calibration]
requires: ["07-02"]
provides:
  - "kajiba.scrubber_semantic — GLiNER Layer-C semantic PII scrubber"
  - "classify_band / partition_spans (D-05 confidence bands)"
  - "scrub_record_semantic(record) -> (record, names_redacted, list[FlaggedItem]) (D-07 asymmetric)"
  - "SemanticScrubUnavailable soft-import fallback (PRIV-04/D-10)"
affects:
  - "07-05 (preview wiring consumes FlaggedItem flags + names_redacted)"
tech-stack:
  added: ["gliner (soft-import, [llm-scrub] extra)", "torch (soft-import, [llm-scrub] extra)"]
  patterns: ["soft-import singleton (psutil-style)", "deep-copy scrub discipline (model_dump->mutate->model_validate)", "asymmetric coverage (D-07)"]
key-files:
  created: ["src/kajiba/scrubber_semantic.py"]
  modified: ["src/kajiba/scrubber_llm.py", "tests/test_scrubber.py"]
decisions:
  - "scrub_record_semantic degrades to a no-op (returns record, 0, []) when [llm-scrub] absent — LANE A asymmetric calls it directly without gliner and asserts on the return value, not pytest.raises"
  - "Retired scrubber_llm.py re-exports the new entry points and raises SemanticScrubUnavailable on the legacy scrub_semantic(text, model_fn) path"
metrics:
  duration: 3m
  completed: 2026-06-05
---

# Phase 7 Plan 04: GLiNER Semantic PII Scrubber Summary

GLiNER Layer-C semantic PII scrubber with D-05 confidence bands, D-07 asymmetric coverage (prose redacts ≥0.7 / tool fields flag-only), and a `[llm-scrub]`-gated soft-import singleton — core stays import-clean and offline, retiring the old `scrubber_llm.py` string-confidence stub.

## What Was Built

- **`src/kajiba/scrubber_semantic.py` (NEW):**
  - `GLINER_MODEL_ID = "nvidia/gliner-PII"` (capital PII), `LABELS` (person/company/organization/project/location, D-04), `REDACT_THRESHOLD=0.7` / `FLAG_THRESHOLD=0.4` (D-05).
  - `SemanticScrubUnavailable(Exception)` — the soft-import fallback signal (PRIV-04/D-10).
  - `classify_band(score)` → `"redact" | "flag" | "ignore"`; `partition_spans(spans)` → `(redactions, flags)`.
  - `_get_model()` — within-run GLiNER singleton (D-09); gliner/torch soft-imported INSIDE the function (psutil-style), `ImportError` → `SemanticScrubUnavailable`; CUDA-with-CPU-fallback device; capital-PII model `.to(device)`.
  - `detect_entities(text, threshold=0.4)` — single inference pass at the flag floor; `[]` for empty text.
  - `scrub_record_semantic(record)` — deep-copy discipline (`model_dump(by_alias=True)` → mutate copy → `KajibaRecord.model_validate`); D-07 asymmetric: turn-value redacts ≥0.7 and flags 0.4–0.7, tool_input/tool_output FLAG-ONLY (text never mutated). `FlaggedItem.reason = "GLiNER {label} (confidence {score:.2f})"` (Pattern 7). Counts person redactions for `potential_names_redacted`. Degrades to a no-op when the extra is absent.
  - Reuses `FlaggedItem` from `kajiba.scrubber` (D-08); no top-level ML imports.

- **`src/kajiba/scrubber_llm.py` (RETIRED):** re-exports the new entry points so legacy import paths resolve; the legacy `scrub_semantic(text, model_fn)` string-confidence interface (and `SemanticRedaction(confidence: str)` / `model_fn`) is removed and now raises `SemanticScrubUnavailable`.

## How to Verify

- `python -m pytest tests/test_scrubber_semantic.py` — LANE A (bands/asymmetric/soft_import) GREEN; LANE B (detect/calibration) SKIPPED (no `[llm-scrub]`).
- `python -c "import kajiba.scrubber_semantic, kajiba.scrubber_llm"` — exits 0 without the extra.
- `git diff --quiet src/kajiba/scrubber.py` — Layer B untouched (exit 0, confirmed).
- Full suite: `python -m pytest` → 348 passed, 4 skipped, 0 regressions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated obsolete LLM-stub test to the retired-stub contract**
- **Found during:** Task 2 (full-suite wave-merge gate)
- **Issue:** `tests/test_scrubber.py::TestLLMScrubberStub::test_raises_not_implemented` pinned the OLD stub's `NotImplementedError("not yet implemented")`, which the plan explicitly retires (Task 2: "remove the dead model_fn/string-confidence interface").
- **Fix:** Repointed the assertion to `pytest.raises(SemanticScrubUnavailable, match="retired")`, matching the new deprecation signal. No production behavior weakened — the plan mandated removing the old interface.
- **Files modified:** `tests/test_scrubber.py`
- **Commit:** e94bc6f

## LANE B Status (environment note)

The `[llm-scrub]` extra (gliner/torch/transformers — multi-GB ML download) was NOT installed. The plan treats GLiNER model download / live detection as LANE B / opt-in (importorskip-gated), so per the execution environment guidance the heavy deps were left uninstalled. LANE B `detect` and `calibration` tests SKIP cleanly. The D-06 calibration hard gate (zero auto-redacts ≥0.7 on the code fixture) and recorded FP-rate are encoded by `test_calibration_zero_auto_redact_on_code` and will execute when `[llm-scrub]` is installed (e.g. on the RTX 4070 dev machine).

## Known Stubs

None. `scrubber_llm.py` is an intentional retired/deprecation shim (re-exports the real module), not a placeholder.

## Threat Flags

None — no new security surface introduced beyond the plan's `<threat_model>` (T-07-08..11 all addressed: ≥0.7 prose redaction, D-07 asymmetric + D-06 calibration on code, pinned capital-PII model, soft-import core protection).

## Self-Check: PASSED

- FOUND: `src/kajiba/scrubber_semantic.py`
- FOUND: `src/kajiba/scrubber_llm.py` (retired)
- FOUND commit: dfaeb6a (Task 1 — detector + bands + soft-import)
- FOUND commit: e94bc6f (Task 2 — asymmetric composition + retire stub)
