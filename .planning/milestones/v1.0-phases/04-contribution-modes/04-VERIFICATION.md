---
phase: 04-contribution-modes
verified: 2026-04-01T14:30:00Z
status: passed
score: 4/4 must-haves verified
---

# Phase 4: Contribution Modes Verification Report

**Phase Goal:** Contributors can choose between reviewing each record manually or running a background mode that auto-submits records above a quality threshold
**Verified:** 2026-04-01T14:30:00Z
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | In ad-hoc mode, each record captured requires explicit user review and approval in the CLI before it is submitted to the outbox | VERIFIED | `kajiba review` command exists at cli.py:914 with approve/reject/skip/quit prompt via `click.prompt` with `click.Choice`. Collector `on_session_end` calls `_save_to_staging()` in ad-hoc mode (collector.py:256-258), never writes to outbox directly. Test `test_adhoc_mode_saves_to_staging_not_outbox` confirms staging-only behavior. Test `test_review_approve_moves_to_outbox` confirms explicit approval required. |
| 2 | In continuous mode, records that meet the configured quality threshold are automatically submitted to the outbox without per-record interaction | VERIFIED | Collector `on_session_end` (collector.py:261-300) checks `contribution_mode == "continuous"`, runs full privacy pipeline (scrub, anonymize, jitter, consent, quality scoring), and writes directly to OUTBOX_DIR when `tier_meets_threshold` passes. Test `test_continuous_mode_gold_record_goes_to_outbox` and `test_continuous_mode_auto_submit_applies_full_pipeline` confirm auto-submit with full pipeline. |
| 3 | A user can switch between ad-hoc and continuous modes by running `kajiba config` with no restart required | VERIFIED | `kajiba config set contribution_mode continuous` persists to config.yaml via `_save_config_value` (cli.py:741). Both collector and CLI read the value at runtime via `_load_config_value` -- collector reads it fresh on each `on_session_end` call (collector.py:255), so no restart is needed. `VALID_CONFIG_KEYS["contribution_mode"]["choices"] == ["ad-hoc", "continuous"]` validated at config.py:32-36. Behavioral spot-check confirmed `config set/get/show` commands work. |
| 4 | Continuous mode minimum quality tier, consent level, and auto-submit interval are all configurable via `kajiba config` | VERIFIED | `VALID_CONFIG_KEYS` in config.py contains `min_quality_tier` (choices: gold/silver/bronze, default: silver), `consent_level` (choices: anonymous/trajectory_only/metadata_only/full, default: full), and `auto_submit_interval` (type: int, min: 0, default: 0). Config set validates against schema (cli.py:717-739). Test `test_contains_required_keys` confirms all keys present. Behavioral spot-check confirmed invalid values are rejected with helpful messages. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/kajiba/config.py` | Config read/write, validation schema, tier comparison, activity log | VERIFIED | 236 lines. Contains `_load_config_value`, `_save_config_value`, `VALID_CONFIG_KEYS`, `tier_meets_threshold`, `_log_activity`, `_show_pending_notifications`, `TIER_ORDER`, `ACTIVITY_LOG`. All exports importable. |
| `src/kajiba/cli.py` | review command, _submit_record helper, config set/get/show subcommands, activity notifications | VERIFIED | `review()` at line 915 with full approve/reject/skip/quit flow. `_submit_record()` at line 361 with full privacy pipeline. Config group at line 667 with `invoke_without_command=True`. `config_show`, `config_set`, `config_get` subcommands at lines 676, 715, 747. `_show_pending_notifications()` called in `cli()` group callback at line 420. |
| `src/kajiba/collector.py` | Extended on_session_end with continuous mode, _save_to_staging helper | VERIFIED | `on_session_end` at line 229 reads `contribution_mode` config, branches to ad-hoc staging or continuous auto-submit. `_save_to_staging` at line 394. Imports `_load_config_value`, `tier_meets_threshold`, `_log_activity` from config.py (line 31). |
| `tests/test_config.py` | Tests for config module | VERIFIED | 358 lines. Classes: TestLoadConfigValue, TestSaveConfigValue, TestTierMeetsThreshold, TestValidConfigKeys, TestLogActivity, TestShowPendingNotifications, TestSubmitRecord. All pass. |
| `tests/test_cli.py` | Tests for review and config subcommands | VERIFIED | TestReviewCommand (8 tests), TestActivityNotification (3 tests), TestConfigSubcommands present. All pass. |
| `tests/test_collector.py` | Tests for continuous mode and staging | VERIFIED | TestContinuousMode (9 tests), TestSaveToStaging (2 tests). All pass. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| cli.py | config.py | `from kajiba.config import _load_config_value, _save_config_value, _show_pending_notifications, VALID_CONFIG_KEYS` | WIRED | Import at line 20-25. All four names used in config_set, config_get, config_show, cli group callback. |
| cli.py config_set | config.py _save_config_value | `_save_config_value(key, value)` call | WIRED | Called at cli.py:741 after validation passes. |
| cli.py review | cli.py _submit_record | `_submit_record(record, scrubbed, scrub_log)` call | WIRED | Called at cli.py:972 inside approve try-block. |
| cli.py review | cli.py _render_preview | `_render_preview(preview_record, quality_dict, scrub_stats, flagged_items=all_flagged)` | WIRED | Called at cli.py:955-958. |
| cli.py review | cli.py _load_all_staging | `_load_all_staging()` call | WIRED | Called at cli.py:922. |
| cli.py cli group | config.py _show_pending_notifications | `_show_pending_notifications()` call | WIRED | Called at cli.py:420, result printed at line 422. |
| collector.py on_session_end | config.py _load_config_value | `_load_config_value("contribution_mode", "ad-hoc")` | WIRED | Called at collector.py:255. Also reads min_quality_tier at line 267. |
| collector.py on_session_end | config.py tier_meets_threshold | `tier_meets_threshold(quality.quality_tier, min_tier)` | WIRED | Called at collector.py:268. |
| collector.py on_session_end | config.py _log_activity | `_log_activity("auto_submitted", ...)` and `_log_activity("queued_for_review", ...)` | WIRED | Called at collector.py:299 and 304. |
| collector.py _save_to_staging | STAGING_DIR filesystem | `STAGING_DIR.mkdir(); staging_file.write_text()` | WIRED | Writes record JSON at collector.py:402-409. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| config.py _load_config_value | config value | `~/.hermes/config.yaml` via PyYAML safe_load | Yes -- reads actual YAML file | FLOWING |
| collector.py on_session_end | contribution_mode, min_quality_tier | `_load_config_value()` from config.yaml | Yes -- runtime config read per invocation | FLOWING |
| collector.py on_session_end (auto-submit) | record data | `_build_record()` -> `scrub_record()` -> `anonymize_hardware()` -> `compute_quality_score()` | Yes -- full pipeline with real DB (Pydantic models, scorer) | FLOWING |
| cli.py review | staged records | `_load_all_staging()` -> reads STAGING_DIR/*.json files | Yes -- reads real filesystem | FLOWING |
| cli.py _submit_record | outbox file | Full privacy pipeline -> write to OUTBOX_DIR | Yes -- produces real JSONL files | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All config.py exports importable | `python -c "from kajiba.config import ..."` | All 8 names imported successfully | PASS |
| _submit_record importable | `python -c "from kajiba.cli import _submit_record"` | Imported OK | PASS |
| Collector imports without circular dep | `python -c "from kajiba.collector import KajibaCollector, STAGING_DIR, OUTBOX_DIR"` | Imported OK, paths correct | PASS |
| review command shows staged record and prompts | `CliRunner().invoke(cli, ['review'])` | Shows full preview with quality scores, action prompt with approve/reject/skip/quit | PASS |
| config show displays all settings with Source column | `CliRunner().invoke(cli, ['config', 'show'])` | Table with Setting/Value/Source columns, all 8 config keys + 4 path/version rows | PASS |
| bare config shows same as config show | `CliRunner().invoke(cli, ['config'])` | Identical output to config show (invoke_without_command works) | PASS |
| config set rejects unknown key | `CliRunner().invoke(cli, ['config', 'set', 'unknown_key', 'foo'])` | "Unknown config key: unknown_key" with valid keys list | PASS |
| config set rejects invalid value | `CliRunner().invoke(cli, ['config', 'set', 'min_quality_tier', 'platinum'])` | "Invalid value for min_quality_tier: platinum" with valid options | PASS |
| tier_meets_threshold logic correct | `tier_meets_threshold("gold","silver")` -> True, `("bronze","gold")` -> False | Correct | PASS |
| Full test suite passes | `python -m pytest tests/ -x -v` | 313 passed in 5.84s | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CONT-01 | 04-02-PLAN.md | User can contribute in ad-hoc mode -- review and approve each record before submission | SATISFIED | `kajiba review` command with one-at-a-time approve/reject/skip/quit flow. Collector saves to staging in ad-hoc mode. 8 review tests + 3 notification tests pass. |
| CONT-02 | 04-03-PLAN.md | User can contribute in continuous mode -- records meeting configured quality threshold are auto-submitted | SATISFIED | Collector `on_session_end` auto-submits qualifying records in continuous mode with full privacy pipeline. Below-threshold records saved to staging. Activity logged for notifications. 9 continuous mode tests + 2 staging tests pass. |
| CONT-03 | 04-01-PLAN.md | User can switch between ad-hoc and continuous modes via `kajiba config` | SATISFIED | `kajiba config set contribution_mode continuous` persists value. Config is read at runtime (no restart needed). Config set validates against `VALID_CONFIG_KEYS`. 13 config subcommand tests pass. |
| CONT-04 | 04-01-PLAN.md | Continuous mode parameters are configurable: minimum quality tier, consent level, auto-submit interval | SATISFIED | `VALID_CONFIG_KEYS` contains `min_quality_tier` (gold/silver/bronze), `consent_level` (4 levels), `auto_submit_interval` (int >= 0). All configurable via `kajiba config set`. Collector reads `min_quality_tier` at runtime for threshold comparison. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| src/kajiba/config.py:51 | 51 | `auto_submit_interval` description says "Currently unused" | Info | The interval key is configurable but the current continuous mode submits inline at session end, not on a timer. This is by design (D-04 decision) and documented. No blocker. |

### Human Verification Required

### 1. Visual Preview Quality During Review

**Test:** Run `kajiba review` with a real staged record containing tool calls and PII.
**Expected:** Preview shows quality scores, scrubbing summary, flagged org domains, and first/last turns in a readable Rich-formatted table.
**Why human:** Visual layout quality and readability cannot be verified programmatically.

### 2. End-to-End Config Switch Flow

**Test:** Run `kajiba config set contribution_mode continuous`, then `kajiba config set min_quality_tier bronze`, then trigger a Hermes Agent session.
**Expected:** Session records that score bronze or better are auto-submitted to outbox. Next CLI command shows activity notification. Running `kajiba config set contribution_mode ad-hoc` switches back to manual review mode.
**Why human:** Requires running a real Hermes Agent session to trigger collector lifecycle.

### Gaps Summary

No gaps found. All four success criteria are verified through code inspection, key link tracing, data-flow analysis, behavioral spot-checks, and a passing test suite of 313 tests.

The phase delivers:
- **Ad-hoc mode (CONT-01):** `kajiba review` with explicit approve/reject/skip/quit per record
- **Continuous mode (CONT-02):** Auto-submit at session end for qualifying records, staging fallback for below-threshold
- **Mode switching (CONT-03):** `kajiba config set contribution_mode` with runtime reads (no restart)
- **Configurable parameters (CONT-04):** min_quality_tier, consent_level, auto_submit_interval all in VALID_CONFIG_KEYS with validation

---

_Verified: 2026-04-01T14:30:00Z_
_Verifier: Claude (gsd-verifier)_
