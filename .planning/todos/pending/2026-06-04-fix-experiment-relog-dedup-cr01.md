---
created: 2026-06-04
title: Fix experiment re-log dedup data loss (CR-01) + Phase 11 review warnings
area: experiment-store / cli
priority: high
source: .planning/phases/11-experiment-logging-private-store/11-REVIEW.md
files:
  - src/kajiba/experiment_store.py
  - src/kajiba/schema.py:454-464
  - src/kajiba/cli.py:843-969
---

## Problem

Phase 11 code review (`11-REVIEW.md`) found defects deferred at phase completion (user
chose "complete, CR-01 as follow-up" on 2026-06-04). Phase goal was met (first-log + privacy
both verified); these affect the re-log / edge-input paths.

**CR-01 (Critical — data loss):** `log_experiment` dedups on `dest.exists()`, where `dest` is
keyed off `record.compute_record_id()`. `ExperimentRecord.compute_record_id()`
(`schema.py:454-464`) hashes only experiment *identity* and excludes all `outcome` fields. So
re-logging a *corrected* evaluation (e.g. eval_score 0.10 → 0.90) hits the dedup early-return,
prints a misleading "identical content" INFO, and silently keeps the stale score on disk.
This corrupts the dataset the milestone exists to build, and defeats the `--score`/`--type`/
`--task-category` override flags on any re-log. Verified empirically in review.

**WR-01:** `experiment log --score 0.5` (partial scalar flags, no `--from`) silently falls
through to the interactive branch and discards the supplied flag.
**WR-02:** A `--from` file missing the `record_kind` discriminator routes to `KajibaRecord`
and raises an uncaught `ValidationError` before the friendly `isinstance` ClickException.
**WR-03:** Malformed `--from` / `--local-model` JSON surfaces a raw `JSONDecodeError`
traceback instead of a Rich error (inconsistent with the rest of the CLI).
**WR-04:** D-13 write guard checks only the leaf name `experiments`, not that the path is
under `KAJIBA_BASE` — privacy claim weaker than the docstring states (latent, not exploited;
CLI always passes the real `EXPERIMENTS_DIR`).

## Solution

TBD — needs a design call (touches the D-01/D-02 dedup contract and the frozen Phase 10
`compute_record_id`). Options for CR-01: (a) make re-log overwrite when content differs while
identity matches (compare full content hash / `compute_submission_hash` before skip), (b)
version experiment files, or (c) add an explicit `--force`/`--update` flag. Resolve CR-01
before or during Phase 12 (Eval Scoring) since the scorer writes outcome fields. WR-01/02/03
are localized error-handling fixes in `experiment_log`; WR-04 is a one-line guard tightening
(`resolved == EXPERIMENTS_DIR` or `is_relative_to(KAJIBA_BASE)`).

Quick path: `/gsd-code-review 11 --fix` (auto-applies review findings), then re-verify.
