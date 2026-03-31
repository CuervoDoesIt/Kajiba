---
phase: 2
slug: data-quality-transparency
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
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
| **Estimated runtime** | ~3 seconds |

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
| 01-T1-01 | 01 | 1 | QUAL-01 | unit | `python -m pytest tests/test_schema.py::TestQualityMetadata -x` | W0 | pending |
| 01-T1-02 | 01 | 1 | QUAL-01 | integration | `python -m pytest tests/test_cli.py::TestSubmitQualityPersistence -x` | W0 | pending |
| 01-T1-03 | 01 | 1 | QUAL-01 | integration | `python -m pytest tests/test_cli.py::TestHistoryStoredQuality -x` | W0 | pending |
| 02-T1-01 | 02 | 1 | QUAL-02 | integration | `python -m pytest tests/test_cli.py::TestPreviewRedactionSummary -x` | W0 | pending |
| 02-T1-02 | 02 | 1 | QUAL-02 | integration | `python -m pytest tests/test_cli.py::TestPreviewRedactionDetail -x` | W0 | pending |
| 03-T1-01 | 03 | 2 | QUAL-03 | integration | `python -m pytest tests/test_cli.py::TestRateCommand -x` | W0 | pending |
| 03-T1-02 | 03 | 2 | QUAL-03 | integration | `python -m pytest tests/test_cli.py::TestRateCommand::test_rate_saves_to_staging -x` | W0 | pending |
| 03-T1-03 | 03 | 2 | QUAL-04 | integration | `python -m pytest tests/test_cli.py::TestReportCommand -x` | W0 | pending |
| 03-T1-04 | 03 | 2 | QUAL-04 | integration | `python -m pytest tests/test_cli.py::TestReportCommand::test_report_saves_to_staging -x` | W0 | pending |
| 03-T1-05 | 03 | 2 | QUAL-05 | integration | `python -m pytest tests/test_cli.py::TestExportAnnotations -x` | W0 | pending |

*Status: pending / green / red / flaky*

*Task ID format: {plan}-T{task}-{seq} (e.g., 01-T1-01 = Plan 01, Task 1, verification 1)*

---

## Wave 0 Requirements

- [ ] `tests/test_schema.py` additions — TestQualityMetadata covering QUAL-01 schema validation
- [ ] `tests/test_cli.py` additions — TestSubmitQualityPersistence, TestHistoryStoredQuality (QUAL-01), TestPreviewRedactionSummary, TestPreviewRedactionDetail (QUAL-02), TestRateCommand (QUAL-03), TestReportCommand (QUAL-04), TestExportAnnotations (QUAL-05)

*Existing test infrastructure (CliRunner, monkeypatching, fixture helpers) covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Preview redaction inline highlighting renders correctly | QUAL-02 | Rich Text styling needs visual confirmation | Run `kajiba preview --detail` with PII data, confirm red highlighting on redacted spans |
| Interactive rate prompt UX | QUAL-03 | Rich Prompt rendering needs visual confirmation | Run `kajiba rate` interactively, confirm score/tag prompts display correctly |
| Interactive report category picker | QUAL-04 | Rich selection rendering needs visual confirmation | Run `kajiba report` interactively, confirm category picker displays correctly |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
