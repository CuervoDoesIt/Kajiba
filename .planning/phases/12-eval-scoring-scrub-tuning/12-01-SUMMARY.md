---
phase: 12-eval-scoring-scrub-tuning
plan: 01
subsystem: eval-scoring-scrub-tuning
tags: [test-foundation, fixtures, red-tests, tdd, experiment-record]
requires:
  - kajiba.schema.load_record (Phase 10)
  - kajiba.schema.ExperimentRecord (Phase 10)
  - kajiba.schema.ScrubLog (Phase 1)
provides:
  - tests/fixtures/experiment_complete.json
  - tests/fixtures/experiment_thin.json
  - tests/fixtures/experiment_pii.json
  - tests/test_eval_scorer.py (RED scaffold for Plan 02)
  - tests/test_experiment_scrub.py (RED scaffold for Plan 03)
affects:
  - 12-02 (eval scorer makes test_eval_scorer.py pass)
  - 12-03 (experiment scrub makes test_experiment_scrub.py pass)
tech-stack:
  added: []
  patterns:
    - "FIXTURES / _load_fixture(name) helper mirrored from test_scorer.py"
    - "RED-by-collection-error (ModuleNotFoundError) — no @pytest.mark.skip"
key-files:
  created:
    - tests/fixtures/experiment_complete.json
    - tests/fixtures/experiment_thin.json
    - tests/fixtures/experiment_pii.json
    - tests/test_eval_scorer.py
    - tests/test_experiment_scrub.py
  modified: []
decisions:
  - "thin fixture pinned to required-fields-only (only model_name on local_model; all optional completeness fields omitted) so Plan 02's locked thin-band contract (composite < 0.50) holds"
  - "pii fixture carries a real 64-hex model_hash + real GPU name as byte-identical preservation targets so Plan 03's T-12-06 preservation test cannot pass vacuously"
  - "ScrubLog imported from kajiba.schema (its canonical home) rather than the not-yet-existing experiment_scrub module, keeping the RED failure scoped to the production symbol under test"
metrics:
  duration: ~6 min
  completed: 2026-06-04
requirements: [EEVAL-01, EEVAL-02]
---

# Phase 12 Plan 01: Eval Test Foundation Summary

Established the Wave 0 test foundation for Phase 12: three `model_experiment` fixtures
(complete / thin / pii) and two RED test scaffolds (8 contract-named tests) that the
eval scorer (Plan 02) and experiment scrub (Plan 03) implement against — satisfying the
Nyquist contract that every downstream implementation task has an automated verify the
moment it runs.

## What Was Built

### Task 1 — Three experiment fixtures (commit 3a75662)

- `experiment_complete.json` — fully-populated ExperimentRecord: `local_model` with
  64-hex `model_hash`, `reviewer_model`, `completed_at`, populated top-level `hardware`,
  non-trivial `local_model_output`, `reviewer_critique`, 2-element `lessons_learned`,
  `recommended_action`, `eval_score` 0.88. Complete-band input.
- `experiment_thin.json` — required-fields-only: `local_model` carries ONLY `model_name`;
  no `reviewer_model`, `reviewer_critique`, `hardware`, `lessons_learned`,
  `recommended_action`, `completed_at`, or `model_hash`. Thin-band input (scores < 0.50
  under Plan 02's locked WEIGHTS).
- `experiment_pii.json` — PII in all four allowlist surfaces: email + unix path in
  `outcome.local_model_output`; email + API-key token in `task_description`; email in one
  of two `lessons_learned` elements; plus a real 64-hex `model_hash` and a recognizable
  `hardware.gpu_name` ("NVIDIA GeForce RTX 4070") as the byte-identical preservation
  targets.

All three round-trip through `load_record()` to `ExperimentRecord` with no `ValidationError`.

### Task 2 — RED test scaffolds (commit e102686, tdd=true)

- `tests/test_eval_scorer.py` — 4 contract tests targeting the not-yet-existing
  `kajiba.eval_scorer`: `test_complete_experiment_scores_complete`,
  `test_thin_experiment_scores_thin`, `test_band_vocabulary_distinct` (bands in
  `{complete,partial,thin}`, never `{gold,silver,bronze,review_needed}`),
  `test_experiment_only` (guard rejects a KajibaRecord).
- `tests/test_experiment_scrub.py` — 4 contract tests targeting the not-yet-existing
  `kajiba.experiment_scrub`: `test_free_text_redacted`,
  `test_model_and_hardware_preserved` (byte-identical via `model_dump`),
  `test_scrublog_and_outcome_fields`, `test_lessons_list_shape`.

Both files mirror `test_scorer.py`'s `FIXTURES` / `_load_fixture()` idiom and fail at
collection time with `ModuleNotFoundError` — the intended RED state. No `@pytest.mark.skip`,
no production code created.

## TDD Gate Compliance

This is a Wave 0 test-foundation plan: the RED gate is the deliverable, GREEN is deferred
to Plans 02/03 by design. Per the plan's `<red_state_expectation>`, no production modules
were created and no skips were added. The RED signal was verified via the plan's
inverted-exit-code wrapper (pytest exits non-zero → wrapper exits 0).

## Verification

- Task 1 automated verify: all three fixtures load as ExperimentRecord — PASS.
- thin fixture required-fields-only portable check — PASS.
- Task 2 contract-name check: all 8 named tests present — PASS.
- Task 2 RED-state wrapper: collection fails ONLY on `ModuleNotFoundError: kajiba.eval_scorer`
  / `kajiba.experiment_scrub` — PASS (RED confirmed).
- Pre-existing suite (`--ignore` both new files): 276 passed, 2 pre-existing skips
  (yaml soft-dep), 0 regressions.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED
