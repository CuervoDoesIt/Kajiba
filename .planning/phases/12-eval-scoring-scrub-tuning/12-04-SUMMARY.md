---
phase: 12-eval-scoring-scrub-tuning
plan: 04
subsystem: cli
tags: [cli, eval-confidence, scrub, integration, EEVAL-01, EEVAL-02]
requires:
  - kajiba.eval_scorer.compute_eval_confidence (12-02)
  - kajiba.experiment_scrub.scrub_experiment (12-03)
  - kajiba.schema.load_record / ExperimentRecord (10-02)
  - kajiba.cli experiment group + EXPERIMENTS_DIR (11-01/11-02)
provides:
  - "kajiba experiment score <id> (compute-on-read confidence breakdown)"
  - "kajiba experiment scrub <id> [--out FILE] (preview/emit scrubbed copy, raw store untouched)"
  - "experiment list Confidence column (compute-on-read band)"
  - "_load_experiment(record_id) store-load helper with path-traversal + isinstance guards"
  - "kajiba.compute_eval_confidence + kajiba.scrub_experiment top-level re-exports"
affects:
  - src/kajiba/cli.py
  - src/kajiba/__init__.py
  - tests/test_cli_experiment.py
tech-stack:
  added: []
  patterns:
    - "compute-on-read (D-03): confidence is computed at render time, never persisted"
    - "store-raw invariant (D-08): scrub previews/emits a copy, never overwrites exp_<id>.json"
    - "untrusted-id → resolved-parent path-traversal guard (T-12-10)"
    - "load_record + isinstance(ExperimentRecord) guard before processing (T-12-11)"
    - "distinct Confidence vs Score columns (Pitfall 4 / T-12-13)"
key-files:
  created: []
  modified:
    - src/kajiba/cli.py
    - src/kajiba/__init__.py
    - tests/test_cli_experiment.py
decisions:
  - "Preview panel renders task_description + local_model_output (scrubbed only); raw PII never echoed."
  - "scrub PII assertion keys on the email ([REDACTED_EMAIL]) which the shared scrubber reliably handles; the sk-live- key gap is a pre-existing community-scrubber limitation logged to deferred-items (out of scope, D-09 forbids forking the regex layer)."
metrics:
  duration: ~10m
  completed: 2026-06-04
---

# Phase 12 Plan 04: Experiment Score/Scrub CLI Wiring Summary

Wired Phase 12's two new capabilities into the user-facing CLI and package surface: `kajiba experiment score` (compute-on-read confidence breakdown + complete/partial/thin band), `kajiba experiment scrub` (preview or `--out` a scrubbed copy that never overwrites the raw store), a distinct Confidence column on `experiment list`, and top-level `compute_eval_confidence` / `scrub_experiment` re-exports — all guarded by a path-traversal + isinstance store-load helper.

## What Was Built

- **`_load_experiment(record_id)` helper (cli.py):** builds `EXPERIMENTS_DIR / f"exp_{record_id}.json"`, rejects path traversal via `path.resolve().parent != EXPERIMENTS_DIR.resolve()` (T-12-10), rejects missing/malformed/non-experiment records with clean `ClickException`s (T-12-11).
- **`experiment score <id>`:** loads the record, calls `compute_eval_confidence`, renders a per-check Rich table (sub-scores + composite + band) plus a separate panel surfacing the answer-quality `eval_score` distinctly from record confidence (Pitfall 4). Compute-on-read only — never persists (D-03).
- **`experiment scrub <id> [--out FILE]`:** calls `scrub_experiment`; with `--out` writes the scrubbed JSON to the explicit destination, otherwise previews a redaction-count table + the scrubbed free text. Never overwrites `exp_<id>.json` (D-08).
- **`experiment list` Confidence column:** added `table.add_column("Confidence")`; per row computes the band compute-on-read, guarding against per-file load/score errors. The existing `Score` (eval_score) column is preserved as a separate column.
- **Re-exports:** `from kajiba.eval_scorer import compute_eval_confidence` and `from kajiba.experiment_scrub import scrub_experiment` in `__init__.py` (A3).
- **Tests:** `test_experiment_score`, `test_experiment_scrub`, `test_experiment_scrub_out`, `test_experiment_list_confidence`, `test_experiment_score_missing` in `tests/test_cli_experiment.py`, reusing `_isolate_store` verbatim (Pitfall 3). Existing log/list tests untouched.

## Deviations from Plan

### Auto-fixed Issues

None to plan-owned files. The plan executed as written.

### Scope-boundary discovery (logged, not fixed)

**[Out of scope] Shared scrubber misses `sk-live-` style API keys**
- **Found during:** Task 2 (`test_experiment_scrub`).
- **Issue:** `tests/fixtures/experiment_pii.json` `task_description` contains `sk-live-AbCdEf1234567890XyZqrStUvWx`. The shared `scrubber.py` `api_keys` pattern `sk-[a-zA-Z0-9]{32,}` stops at the internal hyphen after `sk-`, so this key format is not redacted (`api_keys_redacted=0`). The email IS redacted.
- **Why not fixed:** This is a pre-existing gap in the SHARED community `scrubber.py` regex layer. Plan 12-04 is the integration layer and per D-09 reuses the shared scrub engine verbatim — it must not fork/modify the regex denylist. Out of scope per the executor scope boundary.
- **Action taken:** Logged to `.planning/phases/12-eval-scoring-scrub-tuning/deferred-items.md`; the scrub test asserts on the email PII the scrubber reliably handles (and the `[REDACTED_EMAIL]` placeholder) plus the D-08 byte-identical store invariant.

## Threat Mitigations Applied

| Threat ID | Mitigation |
|-----------|------------|
| T-12-10 (path traversal) | `_load_experiment` resolved-parent == EXPERIMENTS_DIR check before read; `test_experiment_score_missing` covers the rejection path |
| T-12-11 (malformed/non-experiment) | `load_record` + `isinstance(rec, ExperimentRecord)` guard → clean ClickException, no traceback |
| T-12-12 (raw PII overwrite) | scrub previews/`--out` only; `test_experiment_scrub` + `test_experiment_scrub_out` assert raw `exp_*.json` bytes unchanged (D-08) |
| T-12-13 (confidence/score confusion) | distinct "Confidence" column + separate eval_score panel (Pitfall 4) |

## Verification

- `python -m pytest tests/test_cli_experiment.py -x -q` → 9 passed.
- `python -m pytest -q` → 289 passed, 2 pre-existing skips (yaml soft-dep), 0 regressions.
- `python -c "import kajiba; kajiba.compute_eval_confidence; kajiba.scrub_experiment"` → succeeds.
- Source scans for `def experiment_score` / `def experiment_scrub` / `add_column("Confidence")` / `.resolve()` guard → present.

## Commits

- `b70ba48` feat(12-04): wire experiment score/scrub CLI + Confidence column
- `944527d` test(12-04): integration tests for experiment score/scrub + Confidence column

## Self-Check: PASSED

- src/kajiba/cli.py — FOUND (modified, experiment_score/scrub + Confidence column + _load_experiment)
- src/kajiba/__init__.py — FOUND (re-exports present)
- tests/test_cli_experiment.py — FOUND (4 new tests + --out test)
- Commit b70ba48 — FOUND
- Commit 944527d — FOUND
