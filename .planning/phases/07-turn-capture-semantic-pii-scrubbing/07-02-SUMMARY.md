---
phase: 07-turn-capture-semantic-pii-scrubbing
plan: 02
subsystem: privacy / semantic-scrub
tags: [tdd, red-scaffold, gliner, calibration, pii, wave-0]
requires:
  - kajiba.scrubber.FlaggedItem (reused, not redefined)
  - kajiba.schema.validate_record (fixture validation)
provides:
  - tests/fixtures/code_content_pii.json (D-06 calibration fixture)
  - tests/test_scrubber_semantic.py (RED contract for kajiba.scrubber_semantic)
  - pinned public surface for 07-04: classify_band, scrub_record_semantic,
    detect_entities, SemanticScrubUnavailable, GLINER_MODEL_ID
affects:
  - 07-04 (semantic-scrub implementation builds to these RED tests)
tech-stack:
  added: []
  patterns:
    - "TDD RED scaffolds with two lanes (pure-logic + importorskip-gated model lane)"
    - "Import-inside-test for not-yet-existing module so collection succeeds (RED via failure, not error)"
key-files:
  created:
    - tests/fixtures/code_content_pii.json
    - tests/test_scrubber_semantic.py
  modified: []
decisions:
  - "LANE A imports kajiba.scrubber_semantic INSIDE each test (not at module top) so pytest collection succeeds while the module is absent — RED surfaces as test failure, not a collection error (satisfies the no-collection-error criterion)."
  - "KNOWN_SAFE_TOKENS denominator for the D-06 FP-rate lives as a test constant mirroring the fixture's seeded identifiers; calibration test prints CALIBRATION_FP_RATE artifact and hard-asserts the score>=0.7 set is empty."
  - "Model id pinned to capital nvidia/gliner-PII in both the test constant and the asserted module export (lowercase 404s)."
metrics:
  duration: ~14m
  tasks: 2
  files: 2
  completed: "2026-06-05"
---

# Phase 7 Plan 02: Semantic-Scrub Wave 0 Foundation Summary

RED test foundation for the GLiNER semantic-PII layer: a schema-valid D-06 code-content
calibration fixture plus `tests/test_scrubber_semantic.py` pinning band logic (D-05),
asymmetric tool-field coverage (D-07), the zero-auto-redact calibration hard gate (D-06),
and soft-import degradation (PRIV-04) before `kajiba.scrubber_semantic` exists.

## What Was Built

### Task 1 — D-06 calibration fixture (`tests/fixtures/code_content_pii.json`)
A schema-valid `KajibaRecord` (loads via `validate_record`) whose turns embed known-safe
code identifiers a generalist NER over-fires on — `import pandas as pd`, `import numpy as np`,
`const App = () => <React.Fragment/>`, `def compute_quality_score(record):`, and class/var
names (`Customer`, `FastAPI`, `Flask`, `Django`, `Tornado`, `userController`, `accountManager`).
Code identifiers appear in BOTH a `ConversationTurn.value` block AND a tool_call's
`tool_input`/`tool_output` (so 07-04's asymmetric test has tool-field code to flag-only on).
Genuine PII (`Margaret Chen` at `Aldebaran Robotics`) is seeded in prose so the true-positive
`detect` test proves GLiNER still fires on real names. Commit `b57e971`.

### Task 2 — RED scaffolds (`tests/test_scrubber_semantic.py`)
Two lanes, exact 07-VALIDATION `-k` selectors:

- **LANE A (pure-logic, no extra):** `bands` (D-05: ≥0.7 redact / 0.4–0.7 flag / <0.4 ignore
  on synthetic span dicts), `asymmetric` (D-07: tool `tool_input`/`tool_output` flag-only and
  byte-stable; only turn-value may redact), `soft_import` (PRIV-04: module imports without
  gliner; `detect_entities` raises `SemanticScrubUnavailable`, never `ModuleNotFoundError`).
- **LANE B (model-gated by `pytest.importorskip("gliner")`):** `detect` (GLiNER fires on the
  true-positive prose; asserts module's `GLINER_MODEL_ID == "nvidia/gliner-PII"`),
  `calibration` (D-06 HARD GATE: `score>=0.7` span set is EMPTY on the code fixture; records
  `CALIBRATION_FP_RATE` against `KNOWN_SAFE_TOKENS`).

`FlaggedItem` is imported from `kajiba.scrubber` (not redefined). Commit `2c8ded3`.

## Verification Results

- `pytest tests/test_scrubber_semantic.py -k "bands or asymmetric or soft_import"` → **8 failed (RED)** as required.
- `pytest tests/test_scrubber_semantic.py` → 8 failed + **2 skipped** (LANE B skips cleanly, no collection error) without `[llm-scrub]`.
- Selector coverage: detect=2, bands=4, calibration=1, asymmetric=2, soft_import=2 (each ≥1).
- Calibration fixture loads via `validate_record` (3 turns, 1 tool_call with code).
- Full suite excluding the new file: 329 passed / 2 pre-existing skips / **11 failed — all confined to the known 07-01 RED scaffolds** (`test_collector.py`, `test_plugin.py`); **0 failures outside them → 0 regressions**.

## Deviations from Plan

None — plan executed exactly as written. (The two `soft_import` tests were authored as a
single clean degradation test rather than two awkward guards; this is within the task's
described behavior, not a scope deviation.)

## Known Stubs

None. This plan intentionally produces RED tests against the not-yet-existing
`kajiba.scrubber_semantic` module (Nyquist Wave 0); the module itself is built in 07-04.

## Threat Flags

None — no new security surface introduced (test fixtures + RED scaffolds only). The plan's
threat register entries (T-07-02 tampering, T-07-03 info-disclosure) are now expressed as the
`calibration` and `detect` tests respectively.

## TDD Gate Compliance

Both commits are `test(...)` commits (RED gate). GREEN/REFACTOR gates belong to 07-04, which
implements `scrubber_semantic.py` against these pinned contracts.

## Self-Check: PASSED

- FOUND: tests/fixtures/code_content_pii.json
- FOUND: tests/test_scrubber_semantic.py
- FOUND commit: b57e971 (fixture)
- FOUND commit: 2c8ded3 (RED scaffolds)
