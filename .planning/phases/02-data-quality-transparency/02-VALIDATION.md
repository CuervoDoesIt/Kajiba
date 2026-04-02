---
phase: 2
slug: data-quality-transparency
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-30
validated: 2026-04-02
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-T1-01 | 01 | 1 | QUAL-01 | unit | `python -m pytest tests/test_schema.py::TestQualityMetadata -x` | yes | green |
| 01-T1-02 | 01 | 1 | QUAL-01 | integration | `python -m pytest tests/test_cli.py::TestSubmitQualityPersistence -x` | yes | green |
| 01-T1-03 | 01 | 1 | QUAL-01 | integration | `python -m pytest tests/test_cli.py::TestHistoryStoredQuality -x` | yes | green |
| 01-T1-04 | 01 | 1 | QUAL-01 | integration | `python -m pytest tests/test_cli.py::TestStatsStoredQuality -x` | yes | green |
| 01-T1-05 | 01 | 1 | QUAL-01 | integration | `python -m pytest tests/test_cli.py::TestExportQualityPersistence -x` | yes | green |
| 02-T1-01 | 02 | 1 | QUAL-02 | integration | `python -m pytest tests/test_cli.py::TestPreviewRedactionSummary -x` | yes | green |
| 02-T1-02 | 02 | 1 | QUAL-02 | integration | `python -m pytest tests/test_cli.py::TestPreviewRedactionDetail -x` | yes | green |
| 03-T1-01 | 03 | 2 | QUAL-03 | integration | `python -m pytest tests/test_cli.py::TestRateCommand -x` | yes | green |
| 03-T1-02 | 03 | 2 | QUAL-03 | integration | `python -m pytest tests/test_cli.py::TestRateCommand::test_rate_saves_to_staging -x` | yes | green |
| 03-T1-03 | 03 | 2 | QUAL-04 | integration | `python -m pytest tests/test_cli.py::TestReportCommand -x` | yes | green |
| 03-T1-04 | 03 | 2 | QUAL-04 | integration | `python -m pytest tests/test_cli.py::TestReportCommand::test_report_saves_to_staging -x` | yes | green |
| 03-T1-05 | 03 | 2 | QUAL-05 | integration | `python -m pytest tests/test_cli.py::TestExportAnnotations -x` | yes | green |
| 03-T1-06 | 03 | 2 | QUAL-05 | e2e | `python -m pytest tests/test_cli.py::TestFullAnnotationPipeline -x` | yes | green |

*Status: green -- 13/13 entries covered (34 tests total)*

*Task ID format: {plan}-T{task}-{seq} (e.g., 01-T1-01 = Plan 01, Task 1, verification 1)*

---

## Wave 0 Requirements

- [x] `tests/test_schema.py::TestQualityMetadata` -- 5 tests for QualityMetadata model (QUAL-01)
- [x] `tests/test_cli.py::TestSubmitQualityPersistence` -- quality persisted at submit (QUAL-01)
- [x] `tests/test_cli.py::TestHistoryStoredQuality` -- 2 tests for history reading stored quality (QUAL-01)
- [x] `tests/test_cli.py::TestStatsStoredQuality` -- 1 test for stats reading stored quality (QUAL-01, Nyquist gap-fill)
- [x] `tests/test_cli.py::TestExportQualityPersistence` -- 1 test for export writing quality (QUAL-01, Nyquist gap-fill)
- [x] `tests/test_cli.py::TestPreviewRedactionSummary` -- 3 tests for summary table (QUAL-02)
- [x] `tests/test_cli.py::TestPreviewRedactionDetail` -- 3 tests for inline highlighting (QUAL-02)
- [x] `tests/test_cli.py::TestRateCommand` -- 7 tests for rate command (QUAL-03)
- [x] `tests/test_cli.py::TestReportCommand` -- 5 tests for report command (QUAL-04)
- [x] `tests/test_cli.py::TestPreviewMergedQualityPanel` -- 2 tests for merged panel (QUAL-03/04/05)
- [x] `tests/test_cli.py::TestExportAnnotations` -- 1 test for annotation passthrough (QUAL-05)
- [x] `tests/test_cli.py::TestFullAnnotationPipeline` -- 1 e2e test: rate+report+submit (QUAL-05)

*All Wave 0 requirements fulfilled.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual redaction highlighting (bold red markers) | QUAL-02 | Rich ANSI styling stripped by CliRunner | Run `kajiba preview --detail` on PII record, confirm red markers |
| Interactive picker for multiple staged records | QUAL-03/04 | Multi-record prompt interaction | Place 2+ files in staging, run `kajiba rate --score 4` |
| Merged Quality Panel layout | QUAL-05 | Visual grouping/spacing | Run `kajiba preview` on rated record with pain points |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** complete

---

## Validation Audit

**Auditor:** Nyquist auditor (gsd-nyquist-auditor)
**Date:** 2026-04-02
**Suite command:** `python -m pytest tests/test_cli.py tests/test_schema.py tests/test_scorer.py -x -v --tb=short`
**Result:** 137 passed in 1.74s (135 pre-existing + 2 Nyquist gap-fill)

### Gaps Found and Resolved

| # | Requirement | Gap Type | Resolution | Test Class | Status |
|---|-------------|----------|------------|------------|--------|
| 1 | QUAL-01 | no_test (stats reads stored quality) | Created `TestStatsStoredQuality::test_stats_reads_stored_quality_tier` | `tests/test_cli.py::TestStatsStoredQuality` | green |
| 2 | QUAL-01 | no_test (export persists quality) | Created `TestExportQualityPersistence::test_export_writes_quality_to_file` | `tests/test_cli.py::TestExportQualityPersistence` | green |

### Requirements Coverage Summary

| Requirement | Description | Test Count | Status |
|-------------|-------------|------------|--------|
| QUAL-01 | Quality tier/score stored at submit/export, read in history/stats | 11 | COVERED |
| QUAL-02 | Preview shows redaction summary table and --detail inline highlighting | 6 | COVERED |
| QUAL-03 | User can rate staged record via `kajiba rate` | 7 | COVERED |
| QUAL-04 | User can report pain points via `kajiba report` | 5 | COVERED |
| QUAL-05 | User annotations included in exported record alongside auto-scores | 5 | COVERED |

**Total Phase 2 behavioral tests:** 34
**All green:** yes
**Escalated issues:** 0
