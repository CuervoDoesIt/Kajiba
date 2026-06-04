---
phase: 11-experiment-logging-private-store
verified: 2026-06-04T03:05:00Z
status: human_needed
score: 3/3 success criteria verified
overrides_applied: 0
re_verification:
  previous_status: null
  previous_score: null
human_verification:
  - test: "Smoke the real CLI write path against the live ~/.hermes store (not the monkeypatched test dir)"
    expected: "kajiba experiment log --from tests/fixtures/experiment_run.example.json writes one exp_<id>.json under ~/.hermes/kajiba/experiments/ and prints its path; kajiba experiment list shows the run"
    why_human: "Tests monkeypatch EXPERIMENTS_DIR to tmp_path; the real ~/.hermes/_ensure_dirs() side of the path is never exercised by automated tests (11-VALIDATION Manual-Only section)"
  - test: "Confirm a logged experiment is invisible to the community surfaces end to end"
    expected: "After logging an experiment, kajiba browse and kajiba download show no experiment record; kajiba publish --dry-run prints the skip notice and never includes the experiment record_id"
    why_human: "browse/download require live network access to the dataset repo (GitHubOps); automated tests stub the network. Visual confirmation that the experiment never surfaces requires a real catalog round-trip"
---

# Phase 11: Experiment Logging Private Store Verification Report

**Phase Goal:** A developer can log an eval run — by CLI or script — into a private local store separate from coding sessions.
**Verified:** 2026-06-04T03:05:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | Running a `kajiba experiment` CLI command records an experiment run as an `ExperimentRecord` without a live Hermes session | ✓ VERIFIED | `experiment` Click group at cli.py:803-805; `experiment_log` at cli.py:843 supports `--from`, scalar flags, and interactive fallback — all call `log_experiment(rec, EXPERIMENTS_DIR)` at cli.py:932. No collector/Hermes session involved. `experiment --help` exits 0. Tests test_log_from_file / test_log_scalar_overrides / test_log_interactive / test_list all PASS |
| 2 | An external script can create and persist an `ExperimentRecord` via a programmatic entry point | ✓ VERIFIED | `from kajiba import build_experiment_record, log_experiment` re-exported in `__init__.py:5`. Live spot-check: `build_experiment_record(...)` returns record with `record_kind == "model_experiment"`; `log_experiment(rec, dir)` wrote `exp_kajiba_exp_acba081825cb.json`. Module is Click-free (imports only schema). Tests test_build_record / test_log_writes_file / test_public_exports PASS |
| 3 | Experiment records are written to a private namespace distinct from coding-session staging/outbox and never appear in publish/browse/download output | ✓ VERIFIED | `EXPERIMENTS_DIR = KAJIBA_BASE / "experiments"` (cli.py:68), created in `_ensure_dirs()` (cli.py:77), distinct from STAGING_DIR/OUTBOX_DIR. D-13 structural write guard (experiment_store.py:71-76) refused an `outbox` dir in live spot-check. publish active guard (cli.py:1673) skips `record_kind == "model_experiment"` before validate_record. browse (cli.py:1385) and download (cli.py:1542) read ONLY the remote dataset repo via `GitHubOps`/`_fetch_catalog` — they never glob the local store, and experiments are never published, so they cannot enter the remote catalog. submit defensive guard at cli.py:491. Tests test_publish_skips_experiment / test_experiment_absent_from_community_paths PASS |

**Score:** 3/3 success criteria verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `src/kajiba/experiment_store.py` | log_experiment + build_experiment_record | ✓ VERIFIED | 167 lines; `def log_experiment` (atomic write via tempfile.mkstemp + os.replace, D-13 guard, dedup), `def build_experiment_record`; calls `record.compute_record_id()` / `compute_submission_hash()`; `model_dump(mode="json", by_alias=True)`; no import of kajiba.cli |
| `src/kajiba/__init__.py` | Public re-export of both functions (D-07) | ✓ VERIFIED | Line 5: `from kajiba.experiment_store import build_experiment_record, log_experiment` |
| `tests/fixtures/experiment_run.example.json` | Canonical --from example | ✓ VERIFIED | Valid JSON, `"record_kind": "model_experiment"`, full experiment + outcome blocks, omits record_id/submission_hash |
| `src/kajiba/cli.py` (experiment group + guards) | log/list cmds, EXPERIMENTS_DIR, publish/submit guards | ✓ VERIFIED | `experiment` group + `experiment_log` (cli.py:843) + `experiment_list` (cli.py:942); EXPERIMENTS_DIR (68); publish guard (1673); submit guard (491) |
| `tests/test_experiment_store.py` | 6 store tests | ✓ VERIFIED | All 6 PASS |
| `tests/test_cli_experiment.py` | 4 CLI tests | ✓ VERIFIED | All 4 PASS |
| `tests/test_experiment_exclusion.py` | 2 exclusion/regression tests | ✓ VERIFIED | Both PASS |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| experiment_store.py | kajiba.schema.ExperimentRecord | import + compute_record_id/compute_submission_hash | ✓ WIRED | experiment_store.py:35-40 import; :81-82 calls |
| __init__.py | experiment_store.py | re-export | ✓ WIRED | __init__.py:5 |
| cli.py experiment_log | experiment_store.log_experiment | single shared write path (D-08) | ✓ WIRED | cli.py:54 import, :932 call (CLI never writes file itself) |
| cli.py experiment_log | kajiba.schema.load_record | --from parse + isinstance guard | ✓ WIRED | cli.py:884 load_record, :885 isinstance(ExperimentRecord) + ClickException |
| cli.py publish loop | data.get("record_kind") | raw-dict discriminator before validate_record | ✓ WIRED | cli.py:1673, continue at :1678 |
| cli.py experiment group | EXPERIMENTS_DIR | log writes / list globs here | ✓ WIRED | cli.py:932 (log), :946 (list glob) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| experiment_list table | exp_*.json files | EXPERIMENTS_DIR.glob (cli.py:946) → json.loads | ✓ FLOWING | Reads the same files log_experiment writes; round-trip confirmed by test_list |
| log_experiment dest file | record.model_dump | live ExperimentRecord → JSON | ✓ FLOWING | Live spot-check wrote a parseable file with real eval_score |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Programmatic build + log + dedup (SC-2) | `python -c "build_experiment_record(...); log_experiment(...)"` | wrote exp_kajiba_exp_acba081825cb.json; re-log returned same path, 1 file | ✓ PASS |
| D-13 structural guard (SC-3) | log_experiment(rec, .../outbox) | ValueError raised — refused | ✓ PASS |
| CLI group registers (SC-1) | `python -m kajiba.cli experiment --help` | exit 0 | ✓ PASS |
| Full suite regression | `python -m pytest tests/ -q` | 276 passed, 2 skipped (pyyaml soft-dep) | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| ELOG-01 | 11-02 | Record an eval run via `kajiba experiment` CLI without a live Hermes session | ✓ SATISFIED | experiment group + log/list; SC-1 verified; REQUIREMENTS.md:58 marks complete |
| ELOG-02 | 11-01 | Programmatic logging entry point for external scripts | ✓ SATISFIED | Package re-exports; SC-2 verified; REQUIREMENTS.md:59 |
| ELOG-03 | 11-01, 11-03 | Private namespace separate from staging/outbox, excluded from publish | ✓ SATISFIED | EXPERIMENTS_DIR + D-13 guard + publish skip + browse/download remote-only; SC-3 verified; REQUIREMENTS.md:60 |

No orphaned requirements: all three IDs declared in plan frontmatter map to Phase 11 in REQUIREMENTS.md.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| — | — | No TODO/FIXME/XXX/TBD/PLACEHOLDER/NotImplemented markers in any phase-11 source or test file | ℹ️ Info | Clean — completion is auditable |

### Code-Review Findings (11-REVIEW.md) — Impact on the Three Success Criteria

The standard-depth review found 1 Critical + 4 Warnings. Assessed against the phase goal (logging works AND stays private):

| Finding | Affects a success criterion? | Disposition |
| ------- | ---------------------------- | ----------- |
| CR-01: dedup keyed on identity-only hash silently drops a re-logged corrected outcome | ⚠️ Partial — SC-1/SC-2 first-log path works; the *re-log/correction* path silently keeps the stale score | WARNING. Does NOT block "a developer can log an eval run" — the initial log persists correctly. It is a data-correctness defect on re-evaluation that corrupts the dataset the milestone is building. Route to follow-up (review fix), not a phase-goal blocker |
| WR-01: partial scalar flags silently discarded, re-prompts | No | WARNING — UX/footgun on the `log` dispatch; happy paths (full flags / --from / interactive) work |
| WR-02: --from file missing `record_kind` raises raw ValidationError instead of friendly ClickException | No | WARNING — error-message quality only; valid experiment files (with record_kind, as the fixture has) load correctly |
| WR-03: malformed --from/--local-model JSON surfaces raw traceback | No | WARNING — error-handling polish |
| WR-04: D-13 guard checks leaf name only, not location under KAJIBA_BASE | ⚠️ Latent — SC-3 privacy guarantee is weaker than docstring claims | WARNING — CLI always passes the real EXPERIMENTS_DIR, and browse/download are remote-only, so SC-3 holds in practice. Tighten guard or soften docstring as follow-up |

**Conclusion:** None of the review findings block the three success criteria. The goal — log an eval run by CLI or script into a private store separate from coding sessions — is achieved. CR-01 and WR-04 are flagged as WARNINGs for the developer to schedule, but they do not falsify goal achievement.

### Human Verification Required

The automated suite monkeypatches `EXPERIMENTS_DIR` to a tmp dir and stubs the network, so two real-world paths are not exercised by code:

#### 1. Real CLI write against live ~/.hermes store

**Test:** `kajiba experiment log --from tests/fixtures/experiment_run.example.json` then `kajiba experiment list`
**Expected:** One `exp_<id>.json` appears under `~/.hermes/kajiba/experiments/`, the command prints its path, and `list` shows the run.
**Why human:** Tests pass `tmp_path / "experiments"`; the real `_ensure_dirs()` + `~/.hermes` path is never run by automated tests (11-VALIDATION Manual-Only).

#### 2. End-to-end community-surface invisibility

**Test:** After logging an experiment, run `kajiba browse`, `kajiba download`, and `kajiba publish --dry-run`.
**Expected:** browse/download show no experiment record; publish prints the skip notice and never lists the experiment record_id.
**Why human:** browse/download require a live network round-trip to the dataset repo (GitHubOps); automated tests stub the network. Visual confirmation needs a real catalog.

### Gaps Summary

No gaps block the phase goal. All 3 ROADMAP success criteria are verified in the codebase, all 3 requirement IDs (ELOG-01/02/03) are satisfied and traced, all 12 phase-11 tests pass, the full suite is green (276 passed / 2 pre-existing pyyaml soft-dep skips), and no debt markers exist. Status is `human_needed` solely because the live `~/.hermes` write path and the networked browse/download invisibility check cannot be verified programmatically — both are documented Manual-Only items in 11-VALIDATION. The 11-REVIEW findings (CR-01 dedup data-loss on re-log; WR-04 name-only privacy guard) are real robustness/correctness defects to schedule as follow-ups but do not falsify goal achievement.

---

_Verified: 2026-06-04T03:05:00Z_
_Verifier: Claude (gsd-verifier)_
