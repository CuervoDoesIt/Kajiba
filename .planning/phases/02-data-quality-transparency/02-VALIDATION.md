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
| **Quick run command** | `python -m pytest tests/test_cli.py tests/test_schema.py -x -v` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~6 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_cli.py tests/test_schema.py -x -v`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-T1-01 | 01 | 1 | QUAL-01 | unit | `pytest tests/test_schema.py::TestQualityMetadata -x` | ✅ | ✅ green |
| 01-T1-02 | 01 | 1 | QUAL-01 | integration | `pytest tests/test_cli.py::TestSubmitQualityPersistence -x` | ✅ | ✅ green |
| 01-T1-03 | 01 | 1 | QUAL-01 | integration | `pytest tests/test_cli.py::TestHistoryStoredQuality -x` | ✅ | ✅ green |
| 02-T1-01 | 02 | 1 | QUAL-02 | integration | `pytest tests/test_cli.py::TestPreviewRedactionSummary -x` | ✅ | ✅ green |
| 02-T1-02 | 02 | 1 | QUAL-02 | integration | `pytest tests/test_cli.py::TestPreviewRedactionDetail -x` | ✅ | ✅ green |
| 03-T1-01 | 03 | 2 | QUAL-03 | integration | `pytest tests/test_cli.py::TestRateCommand -x` | ✅ | ✅ green |
| 03-T1-02 | 03 | 2 | QUAL-04 | integration | `pytest tests/test_cli.py::TestReportCommand -x` | ✅ | ✅ green |
| 03-T1-03 | 03 | 2 | QUAL-05 | integration | `pytest tests/test_cli.py::TestPreviewMergedQualityPanel -x` | ✅ | ✅ green |
| 03-T1-04 | 03 | 2 | QUAL-05 | e2e | `pytest tests/test_cli.py::TestFullAnnotationPipeline -x` | ✅ | ✅ green |

*Status: ✅ green — 9/9 entries covered (29 tests total)*

---

## Wave 0 Requirements

- [x] `tests/test_schema.py::TestQualityMetadata` — 5 tests for QualityMetadata model (QUAL-01)
- [x] `tests/test_cli.py::TestSubmitQualityPersistence` — quality persisted at submit (QUAL-01)
- [x] `tests/test_cli.py::TestHistoryStoredQuality` — history reads stored quality (QUAL-01)
- [x] `tests/test_cli.py::TestPreviewRedactionSummary` — 3 tests for summary table (QUAL-02)
- [x] `tests/test_cli.py::TestPreviewRedactionDetail` — 3 tests for inline highlighting (QUAL-02)
- [x] `tests/test_cli.py::TestRateCommand` — 7 tests for rate command (QUAL-03)
- [x] `tests/test_cli.py::TestReportCommand` — 5 tests for report command (QUAL-04)
- [x] `tests/test_cli.py::TestPreviewMergedQualityPanel` — 2 tests for merged panel (QUAL-05)
- [x] `tests/test_cli.py::TestFullAnnotationPipeline` — 1 e2e test: rate+report+submit (QUAL-05)

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
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-02

---

## Validation Audit 2026-04-02

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

All 9 verification entries ran green (29 tests, 0.77s). Phase 2 is Nyquist-compliant.
