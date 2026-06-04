---
status: partial
phase: 11-experiment-logging-private-store
source: [11-VERIFICATION.md]
started: 2026-06-04
updated: 2026-06-04
---

## Current Test

[awaiting human testing]

## Tests

### 1. Real CLI write against the live ~/.hermes store
expected: `kajiba experiment log --from tests/fixtures/experiment_run.example.json` writes one `exp_<id>.json` under `~/.hermes/kajiba/experiments/` and prints its path; `kajiba experiment list` then shows the run.
why_human: Automated tests monkeypatch `EXPERIMENTS_DIR` to a tmp dir, so the real `_ensure_dirs()` + `~/.hermes` path is never exercised (11-VALIDATION Manual-Only).
result: [pending]

### 2. End-to-end community-surface invisibility
expected: After logging an experiment, `kajiba browse` and `kajiba download` show no experiment record; `kajiba publish --dry-run` prints the skip notice and never lists the experiment `record_id`.
why_human: browse/download require a live network round-trip to the dataset repo (GitHubOps); automated tests stub the network. Visual confirmation needs a real catalog.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
