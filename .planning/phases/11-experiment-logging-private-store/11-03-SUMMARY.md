---
phase: 11-experiment-logging-private-store
plan: 03
subsystem: cli
tags: [experiment-logging, publish-guard, exclusion, defense-in-depth, dual-use, private-store, elog-03]

# Dependency graph
requires:
  - phase: 11-experiment-logging-private-store
    plan: 01
    provides: "log_experiment(record, store_dir), build_experiment_record(**fields), EXPERIMENTS_DIR (cli.py), structural OUTBOX_DIR/EXPERIMENTS_DIR separation"
  - phase: 11-experiment-logging-private-store
    plan: 02
    provides: "kajiba experiment group (log + list) — exercises the real experiment write path used by the D-14 regression"
provides:
  - "publish active guard: skips any outbox record whose raw-dict record_kind == model_experiment BEFORE validate_record (Pitfall 1), with a skip notice"
  - "submit defensive ClickException if a loaded record is a model_experiment (T-11-09, Assumption A2)"
  - "tests/test_experiment_exclusion.py — ELOG-03 active-guard test + D-14 community-path-absence regression (network-free)"
affects: [experiment-logging, 12-eval-scoring, 13-reviewer-critique]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Defense in depth: structural dir separation (primary, 11-01) PLUS an active raw-dict discriminator skip in the publish consent loop (backstop)"
    - "Raw-dict record_kind check BEFORE validate_record — an experiment is never fed into the KajibaRecord validator (Pitfall 1 / T-11-10)"
    - "Network-free publish test via a GitHubOps stub whose check_auth passes so the Step 4 guard loop is reached, but no PR is ever opened"

key-files:
  created:
    - tests/test_experiment_exclusion.py
  modified:
    - src/kajiba/cli.py

key-decisions:
  - "publish guard reads data.get('record_kind') on the raw dict as the FIRST statement in the Step 4 loop, before the existing try/validate_record — never mis-validates an experiment (Pitfall 1)"
  - "submit guard is a single defensive ClickException, not dead branching — Assumption A2: submit only reads STAGING via _load_latest_staging and only log_experiment writes experiments (to EXPERIMENTS_DIR), so it is structurally unreachable today"
  - "test_publish_skips_experiment stays network-free by stubbing kajiba.cli.GitHubOps with a passing check_auth; the run exits at 'No valid records' after the skip, so no fork/push/PR is attempted"

requirements-completed: [ELOG-03]

# Metrics
duration: 4min
completed: 2026-06-04
---

# Phase 11 Plan 03: Publish Exclusion Guard Summary

**Closes the active half of ELOG-03 — a `record_kind == "model_experiment"` skip guard in the `publish` Step 4 consent loop (raw-dict discriminator before validation) plus a defensive `submit` ClickException, proven by a network-free active-guard test and a D-14 community-path-absence regression; full suite 276 passed / 2 pre-existing skips, 0 regressions.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-06-04 (Wave 3 — final plan of Phase 11)
- **Tasks:** 3 (TDD: RED test → GREEN impl → full-suite gate)
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments
- `src/kajiba/cli.py` publish Step 4 loop: as the FIRST statement inside `for path, data in outbox_records:`, an active guard reads the raw-dict discriminator `data.get("record_kind") == "model_experiment"`, logs a warning, prints `Skipping experiment record (never published): <name>`, and `continue`s — before the existing `try`/`validate_record(data)`. This avoids feeding an experiment into the `KajibaRecord` validator (Pitfall 1 / T-11-10) and is defense in depth on top of the structural `OUTBOX_DIR`/`EXPERIMENTS_DIR` separation from 11-01 (T-11-08, D-13).
- `src/kajiba/cli.py` submit: a defensive `if getattr(record, "record_kind", "coding_session") == "model_experiment": raise click.ClickException(...)` after the `_load_latest_staging()` None check (T-11-09, Assumption A2) — a single guard, not dead branching.
- `tests/test_experiment_exclusion.py`: two tests named exactly per 11-VALIDATION.md —
  - `test_publish_skips_experiment`: a misplaced `model_experiment` `.jsonl` line dropped into the monkeypatched `OUTBOX_DIR`; `publish --dry-run` (with `GitHubOps` stubbed so no network/PR) does not echo its `record_id`, prints the skip notice, and exits at "No valid records".
  - `test_experiment_absent_from_community_paths`: a real experiment written via `log_experiment` into the monkeypatched `EXPERIMENTS_DIR`, asserting (a) it is not in the outbox glob, (b) the file is byte-identical on disk after a publish run, (c) its `record_id` never appears in publish output.
- Full suite: **276 passed, 2 skipped** (was 274 + 2) — the two new exclusion tests strictly add to the passed count; the only skips remain the two pre-existing pyyaml-soft-dep skips (`test_cli.py`, `test_config.py`). 0 regressions.

## Task Commits

Each implementing task committed atomically (TDD: RED test → GREEN impl); Task 3 is a verification gate that added no production code:

1. **Task 1: Wave-0 exclusion test stubs (RED)** - `c43d63f` (test)
2. **Task 2: publish record_kind skip guard + submit defensive assertion (GREEN)** - `5610028` (feat)
3. **Task 3: Full-suite regression gate** - no code commit (verification only); 276 passed / 2 skipped

## Files Created/Modified
- `tests/test_experiment_exclusion.py` - New test file; `runner` CliRunner fixture, `_isolate_dirs` monkeypatching `OUTBOX_DIR`/`EXPERIMENTS_DIR`/`KAJIBA_BASE` to `tmp_path` subdirs (Pitfall 2), a `_StubGitHubOps` (passing `check_auth`, never opening a PR) so the publish test is fully network-free, and the two exclusion tests.
- `src/kajiba/cli.py` - Added the raw-dict `record_kind == "model_experiment"` skip+notice as the first statement of the publish Step 4 loop (mirroring the existing skip phrasing), and the defensive `model_experiment` ClickException guard in `submit`. No other publish/submit behavior altered.

## Decisions Made
- **Guard on the raw dict before validation:** placing the `record_kind` check before `validate_record` matches how `_load_outbox_records` returns raw dicts and prevents the validator from ever seeing a `model_experiment` (which would otherwise fail as a malformed `KajibaRecord`, surfacing as a generic "invalid record" rather than an explicit experiment refusal). The RED run confirmed the pre-guard behavior fell into the generic "Skipping invalid record" path; the guard makes the refusal explicit and intentional.
- **submit guard kept defensive, not live:** per Assumption A2 it is structurally unreachable today (only `log_experiment` writes experiments, only to `EXPERIMENTS_DIR`; `submit` only reads `STAGING_DIR`), so it stays a single ClickException for future-path safety rather than introducing branching for a path that cannot occur.
- **Network-free publish test:** stubbing `kajiba.cli.GitHubOps` with a passing `check_auth` lets the run reach the Step 4 guard loop, after which the experiment-skip leaves no valid records and the run exits before any fork/clone/push — so no real network is touched (RESEARCH line 535). The D-14 regression also asserts on the structural outbox-glob path, which needs no network at all.
- Followed plan task order and the TDD gate sequence exactly (test → feat → verify gate).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None. Git emitted expected LF→CRLF warnings on Windows (cosmetic, no impact). The RED run's `test_experiment_absent_from_community_paths` passed immediately (the structural separation from 11-01 already holds), as designed — only the active-guard assertion in `test_publish_skips_experiment` was red until Task 2.

## TDD Gate Compliance
- RED gate: `c43d63f` is a `test(11-03)` commit; `test_publish_skips_experiment` failed before the guard (the experiment was caught by the generic `validate_record` "invalid record" path, not the explicit experiment skip notice), as expected.
- GREEN gate: `5610028` is a `feat(11-03)` commit adding the publish guard + submit assertion; both exclusion tests pass.
- No REFACTOR commit needed (implementation was clean on first pass).

## Threat Surface Notes
- T-11-08 (experiment reaching the community publish path) mitigated: structural dir separation (11-01, primary) + active raw-dict skip in the publish Step 4 loop (backstop), proven by `test_experiment_absent_from_community_paths` (D-14) and `test_publish_skips_experiment`.
- T-11-09 (experiment routed into submit) mitigated: defensive ClickException in `submit`.
- T-11-10 (experiment fed into the KajibaRecord validator) mitigated: the guard reads `data.get("record_kind")` on the raw dict BEFORE `validate_record`.
- No new security surface introduced beyond the plan's threat register. No external packages installed (T-11-SC N/A).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- ELOG-03 fully satisfied: structural separation (11-01) + active publish refusal (this plan) + D-14 regression all in place. Phase 11 is ready for `/gsd-verify-work` (phase-level completion is owned by the orchestrator).
- Manual smoke remaining (11-VALIDATION Manual-Only): after `kajiba experiment log --from <fixture>`, confirm `kajiba experiment list` shows the run and `kajiba browse` does not.
- No blockers.

## Self-Check: PASSED

All created/modified files verified present (tests/test_experiment_exclusion.py, src/kajiba/cli.py, 11-03-SUMMARY.md) and both task commits (c43d63f, 5610028) exist in git history.

---
*Phase: 11-experiment-logging-private-store*
*Completed: 2026-06-04*
