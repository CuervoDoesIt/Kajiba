---
phase: 12-eval-scoring-scrub-tuning
plan: 03
subsystem: privacy/scrubbing
tags: [eval-logging, pii-scrub, dual-use, divergent-tail, EEVAL-02]
requires:
  - kajiba.scrubber.scrub_text
  - kajiba.scrubber.SCRUB_PATTERNS
  - kajiba.schema.ExperimentRecord
  - kajiba.schema.ScrubLog
  - tests/test_experiment_scrub.py (RED scaffold, 12-01)
  - tests/fixtures/experiment_pii.json (12-01)
provides:
  - kajiba.experiment_scrub.scrub_experiment
affects:
  - Phase 15 (share-boundary export will call scrub_experiment)
tech-stack:
  added: []
  patterns:
    - "field-allowlist scrub (not pattern denylist)"
    - "envelope-mirror: model_dump → mutate copy → model_validate"
    - "shared-core / divergent-tail: reuse scrub_text, bypass privacy.py"
key-files:
  created:
    - src/kajiba/experiment_scrub.py
  modified: []
decisions:
  - "Docstring describes the privacy SKIP boundary in prose (no literal helper names) so the portable no-coupling source scan passes while the intent stays documented."
requirements-completed: [EEVAL-02]
metrics:
  duration: ~5m
  completed: 2026-06-04
---

# Phase 12 Plan 03: Experiment PII Scrub Summary

Field-allowlist experiment scrub (EEVAL-02) that redacts the four free-text surfaces via the shared `scrub_text` engine while preserving model identity and full hardware byte-identical — the deliberate inverse of the community privacy pipeline.

## What Was Built

`src/kajiba/experiment_scrub.py` exposing `scrub_experiment(record: ExperimentRecord) -> tuple[ExperimentRecord, ScrubLog]`:

- Deep-copies the record via `model_dump(mode="json", by_alias=True)` and rebuilds with `model_validate` — the caller's record is never mutated (D-08, store-raw invariant upheld).
- Routes ONLY the allowlist surfaces through `scrub_text`: `experiment.task_description`, `outcome.local_model_output`, `outcome.reviewer_critique` (guarded for `Optional`, Pitfall 2), and each element of `outcome.lessons_learned` (per-element, list shape preserved, Pitfall 1).
- Leaves `model`, `hardware`, `experiment.local_model`, `experiment.reviewer_model`, `model_hash`, `eval_score`, `drift_flag`, `recommended_action` untouched (D-05/D-06).
- Folds `scrub_text` stats into a `ScrubLog`, mirroring `scrub_record`'s `api_keys + hex_tokens → api_keys_redacted` collapse; `potential_names_redacted` stays 0 (no regex source, Open Q2 RESOLVED).
- NEVER imports `kajiba.privacy` or calls any hardware-anonymization / GPU-generalization / VRAM-tiering / consent helper (D-05 SKIP boundary).

## TDD Gate Compliance

- RED gate: `tests/test_experiment_scrub.py` was committed in Plan 12-01 (commit e102686) and failed at collection with `ModuleNotFoundError` until this plan.
- GREEN gate: `feat(12-03)` commit `c166de6` turns all 4 contract tests green.
- REFACTOR gate: not required — implementation was clean on first pass. The single post-implementation edit (docstring rewording for the source-scan) is part of the GREEN commit, not a behavior change.

## Verification

- `python -m pytest tests/test_experiment_scrub.py -x -q` → 4 passed.
- `python -m pytest -q` → 284 passed, 2 skipped (pre-existing yaml soft-dep skips in test_cli.py/test_config.py), 0 regressions.
- No-privacy-coupling source scan → `no privacy.* coupling` (D-05 honored).

## Deviations from Plan

None functional. One cosmetic adjustment: the module docstring originally named the four bypassed privacy helpers when describing the SKIP boundary, which tripped the portable no-coupling regex scan (the scan matches any occurrence of those names, including prose). Reworded the docstring to describe the boundary without the literal names — no behavior change, intent still documented. Folded into the GREEN commit.

## Known Stubs

None.

## Threat Flags

None — no new security surface beyond the threat model in PLAN.md. The scrub returns a copy and never persists/overwrites the raw store (T-12-08 accepted; export-write gate remains Phase 15).

## Self-Check: PASSED

- FOUND: src/kajiba/experiment_scrub.py
- FOUND: .planning/phases/12-eval-scoring-scrub-tuning/12-03-SUMMARY.md
- FOUND: commit c166de6
