---
phase: 4
slug: contribution-modes
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-01
validated: 2026-04-02
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~6 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 6 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | CONT-03, CONT-04 | unit | `python -m pytest tests/test_config.py -x -v` | tests/test_config.py | green |
| 04-01-02 | 01 | 1 | CONT-03, CONT-04 | unit | `python -m pytest tests/test_cli.py::TestConfigSubcommands -x -v` | tests/test_cli.py | green |
| 04-02-01 | 02 | 2 | CONT-01 | integration | `python -m pytest tests/test_cli.py::TestReviewCommand -x -v` | tests/test_cli.py | green |
| 04-02-02 | 02 | 2 | CONT-01 | integration | `python -m pytest tests/test_cli.py::TestActivityNotification -x -v` | tests/test_cli.py | green |
| 04-03-01 | 03 | 2 | CONT-02 | unit | `python -m pytest tests/test_collector.py::TestContinuousMode -x -v` | tests/test_collector.py | green |
| 04-03-02 | 03 | 2 | CONT-02 | unit | `python -m pytest tests/test_collector.py::TestSaveToStaging -x -v` | tests/test_collector.py | green |

*Status: pending -- green -- red -- flaky*

---

## Requirement Coverage Detail

### CONT-01: Ad-hoc review mode

| # | Behavior | Test Class | Test Method | Status |
|---|----------|------------|-------------|--------|
| 1 | Review with no staged records prints empty-state message | TestReviewCommand | test_review_empty_staging | green |
| 2 | Approve moves record to outbox, staging deleted | TestReviewCommand | test_review_approve_moves_to_outbox | green |
| 3 | Reject removes staging file, nothing in outbox | TestReviewCommand | test_review_reject_removes_from_staging | green |
| 4 | Skip preserves staging file | TestReviewCommand | test_review_skip_preserves_staging | green |
| 5 | Quit exits early with summary counts | TestReviewCommand | test_review_quit_with_summary | green |
| 6 | Summary line shows approved/rejected/skipped | TestReviewCommand | test_review_summary_line | green |
| 7 | Approve creates outbox file (_submit_record called) | TestReviewCommand | test_review_approve_calls_submit_record | green |
| 8 | Submit error preserves staging (data loss prevention) | TestReviewCommand | test_review_submit_error_preserves_staging | green |
| 9 | Activity notification shown when activity.jsonl has entries | TestActivityNotification | test_notification_shown_when_activity_exists | green |
| 10 | Activity log deleted after notification display | TestActivityNotification | test_notification_cleared_after_display | green |
| 11 | No notification when activity.jsonl missing | TestActivityNotification | test_no_notification_when_no_activity | green |

### CONT-02: Continuous mode auto-submit

| # | Behavior | Test Class | Test Method | Status |
|---|----------|------------|-------------|--------|
| 1 | Ad-hoc mode saves to staging, not outbox | TestContinuousMode | test_adhoc_mode_saves_to_staging_not_outbox | green |
| 2 | Continuous with qualifying record auto-submits to outbox | TestContinuousMode | test_continuous_mode_gold_record_goes_to_outbox | green |
| 3 | Continuous below threshold saves to staging | TestContinuousMode | test_continuous_mode_below_threshold_goes_to_staging | green |
| 4 | Auto-submit applies full privacy pipeline | TestContinuousMode | test_continuous_mode_auto_submit_applies_full_pipeline | green |
| 5 | Logs auto_submitted activity when above threshold | TestContinuousMode | test_continuous_mode_logs_auto_submitted_activity | green |
| 6 | Logs queued_for_review when below threshold | TestContinuousMode | test_continuous_mode_logs_queued_for_review_activity | green |
| 7 | Bronze threshold accepts bronze record | TestContinuousMode | test_continuous_mode_bronze_threshold_accepts_bronze | green |
| 8 | Fault tolerance: scrub_record raises, no crash | TestContinuousMode | test_fault_tolerance_scrub_raises | green |
| 9 | Fault tolerance: _save_to_staging raises, no crash | TestContinuousMode | test_fault_tolerance_save_to_staging_raises | green |
| 10 | _save_to_staging creates valid JSON file | TestSaveToStaging | test_save_to_staging_creates_file | green |
| 11 | Staging file round-trips through validate_record | TestSaveToStaging | test_save_to_staging_round_trip | green |

### CONT-03: Config mode switching

| # | Behavior | Test Class | Test Method | Status |
|---|----------|------------|-------------|--------|
| 1 | Bare `kajiba config` still shows table (backward compat) | TestConfigSubcommands | test_bare_config_shows_table | green |
| 2 | `config show` has Source column | TestConfigSubcommands | test_config_show_has_source_column | green |
| 3 | Source shows "default" for hardcoded defaults | TestConfigSubcommands | test_config_show_source_indicates_default | green |
| 4 | Source shows "config" for file-configured values | TestConfigSubcommands | test_config_show_source_indicates_config | green |
| 5 | `config set contribution_mode continuous` persists | TestConfigSubcommands | test_config_set_valid_choice | green |
| 6 | `config set min_quality_tier gold` persists | TestConfigSubcommands | test_config_set_min_quality_tier | green |
| 7 | Invalid choice rejected with valid options | TestConfigSubcommands | test_config_set_invalid_choice | green |
| 8 | Unknown key rejected with valid keys list | TestConfigSubcommands | test_config_set_unknown_key | green |
| 9 | `config get` after set shows stored value | TestConfigSubcommands | test_config_get_after_set | green |
| 10 | `config get` unset shows default with (default) | TestConfigSubcommands | test_config_get_default_value | green |
| 11 | `config get unknown_key` prints error | TestConfigSubcommands | test_config_get_unknown_key | green |
| 12 | Integer value stored as int | TestConfigSubcommands | test_config_set_integer_value | green |
| 13 | Boolean value stored as bool | TestConfigSubcommands | test_config_set_boolean_value | green |

### CONT-04: Configurable parameters

| # | Behavior | Test Class | Test Method | Status |
|---|----------|------------|-------------|--------|
| 1 | _load_config_value returns default when no file | TestLoadConfigValue | test_returns_default_when_no_config_file | green |
| 2 | _load_config_value reads YAML value | TestLoadConfigValue | test_reads_value_from_yaml | green |
| 3 | _load_config_value returns default when no PyYAML | TestLoadConfigValue | test_returns_default_when_yaml_not_importable | green |
| 4 | _save_config_value writes to YAML | TestSaveConfigValue | test_writes_value_to_yaml | green |
| 5 | _save_config_value creates file if missing | TestSaveConfigValue | test_creates_config_file_if_missing | green |
| 6 | _save_config_value preserves non-kajiba keys | TestSaveConfigValue | test_preserves_existing_non_kajiba_keys | green |
| 7 | _save_config_value coerces booleans | TestSaveConfigValue | test_coerces_true_false_to_booleans | green |
| 8 | _save_config_value coerces digits | TestSaveConfigValue | test_coerces_digit_strings_to_integers | green |
| 9 | _save_config_value raises ClickException no yaml | TestSaveConfigValue | test_raises_click_exception_when_yaml_missing | green |
| 10 | tier_meets_threshold gold > silver | TestTierMeetsThreshold | test_gold_meets_silver | green |
| 11 | tier_meets_threshold bronze < gold | TestTierMeetsThreshold | test_bronze_does_not_meet_gold | green |
| 12 | tier_meets_threshold silver == silver | TestTierMeetsThreshold | test_silver_meets_silver | green |
| 13 | tier_meets_threshold unknown tier | TestTierMeetsThreshold | test_unknown_tier_does_not_meet | green |
| 14 | VALID_CONFIG_KEYS contains required keys | TestValidConfigKeys | test_contains_required_keys | green |
| 15 | contribution_mode choices correct | TestValidConfigKeys | test_contribution_mode_choices | green |
| 16 | _log_activity writes JSON line | TestLogActivity | test_writes_json_line_to_activity_log | green |
| 17 | _show_pending_notifications returns formatted parts | TestShowPendingNotifications | test_returns_formatted_parts | green |
| 18 | _show_pending_notifications deletes log after reading | TestShowPendingNotifications | test_deletes_activity_log_after_reading | green |
| 19 | _submit_record writes to outbox | TestSubmitRecord | test_submit_record_writes_to_outbox | green |

---

## Wave 0 Requirements

- [x] `tests/test_config.py` -- 19 tests for CONT-04 (config module functions: load/save, tier, activity, submit)
- [x] `tests/test_cli.py::TestConfigSubcommands` -- 13 tests for CONT-03 (config set/get/show subcommands)
- [x] `tests/test_cli.py::TestReviewCommand` -- 8 tests for CONT-01 (ad-hoc review approve/reject/skip/quit)
- [x] `tests/test_cli.py::TestActivityNotification` -- 3 tests for CONT-01 (activity notifications)
- [x] `tests/test_collector.py::TestContinuousMode` -- 9 tests for CONT-02 (continuous mode auto-submit)
- [x] `tests/test_collector.py::TestSaveToStaging` -- 2 tests for CONT-02 (staging persistence)

*Existing test infrastructure (pytest, conftest.py) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Interactive review prompt (approve/reject/skip) | CONT-01 | Requires TTY input | Run `kajiba review` with staged record, verify prompt appears, select approve |
| Activity notification on next CLI use | CONT-02 | Requires two sequential CLI invocations | Auto-submit a record, then run `kajiba stats`, verify summary line appears |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 6s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** passed

---

## Validation Audit

**Audited:** 2026-04-02
**Auditor:** Claude (gsd-nyquist-auditor)

### Gap Analysis

| Requirement | Plan Behaviors | Tests Found | Gaps | Status |
|-------------|---------------|-------------|------|--------|
| CONT-01 | 11 | 11 | 0 | COVERED |
| CONT-02 | 11 | 11 | 0 | COVERED |
| CONT-03 | 13 | 13 | 0 | COVERED |
| CONT-04 | 19 | 19 | 0 | COVERED |

**Total behaviors specified:** 54
**Total tests covering them:** 54
**Gaps found:** 0
**Tests created by audit:** 0
**Escalations:** 0

### Test Run Results

```
127 passed in 5.88s
```

Command: `python -m pytest tests/test_config.py tests/test_cli.py tests/test_collector.py -x -v --tb=short`

All 127 tests across the three Phase 4 test files pass with zero failures.
