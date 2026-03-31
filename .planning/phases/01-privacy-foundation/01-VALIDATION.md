---
phase: 1
slug: privacy-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `python -m pytest tests/test_scrubber.py tests/test_privacy.py -x -v` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_scrubber.py tests/test_privacy.py -x -v`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-T1-01 | 01 | 1 | PRIV-06 | unit | `python -m pytest tests/test_scrubber.py::TestIPFalsePositiveFix -x` | W0 | pending |
| 01-T1-02 | 01 | 1 | PRIV-06 | unit | `python -m pytest tests/test_scrubber.py::TestIPFalsePositiveFix::test_real_ips_still_detected -x` | W0 | pending |
| 01-T1-03 | 01 | 1 | PRIV-04 | unit | `python -m pytest tests/test_scrubber.py::TestHexTokenScrubbing -x` | W0 | pending |
| 01-T1-04 | 01 | 1 | PRIV-04 | unit | `python -m pytest tests/test_scrubber.py::TestHexTokenScrubbing::test_git_commit_preserved -x` | W0 | pending |
| 01-T1-05 | 01 | 1 | PRIV-05 | unit | `python -m pytest tests/test_scrubber.py::TestOrgDomainFlagging -x` | W0 | pending |
| 01-T1-06 | 01 | 1 | PRIV-05 | unit | `python -m pytest tests/test_scrubber.py::TestOrgDomainFlagging::test_safe_domains_not_flagged -x` | W0 | pending |
| 02-T1-01 | 02 | 1 | PRIV-01 | unit | `python -m pytest tests/test_privacy.py::TestConsentEnforcement -x` | W0 | pending |
| 02-T1-02 | 02 | 1 | PRIV-01 | unit | `python -m pytest tests/test_privacy.py::TestConsentEnforcement::test_anonymous_strips_all_metadata -x` | W0 | pending |
| 02-T1-03 | 02 | 1 | PRIV-02 | unit | `python -m pytest tests/test_privacy.py::TestHardwareAnonymization::test_gpu_generalization -x` | W0 | pending |
| 02-T1-04 | 02 | 1 | PRIV-02 | unit | `python -m pytest tests/test_privacy.py::TestHardwareAnonymization::test_ram_rounding -x` | W0 | pending |
| 02-T1-05 | 02 | 1 | PRIV-02 | unit | `python -m pytest tests/test_privacy.py::TestHardwareAnonymization::test_os_family_only -x` | W0 | pending |
| 02-T1-06 | 02 | 1 | PRIV-03 | unit | `python -m pytest tests/test_privacy.py::TestTimestampJitter -x` | W0 | pending |
| 02-T1-07 | 02 | 1 | PRIV-03 | unit | `python -m pytest tests/test_privacy.py::TestTimestampJitter::test_jitter_deterministic -x` | W0 | pending |
| 03-T1-01 | 03 | 2 | PRIV-01..06 | integration | `python -m pytest tests/ -x -v` | existing | pending |
| 03-T2-01 | 03 | 2 | PRIV-05 | integration | `python -m pytest tests/test_cli.py::TestPreviewFlaggedWarnings -x` | W0 | pending |
| 03-T2-02 | 03 | 2 | PRIV-01 | integration | `python -m pytest tests/test_cli.py::TestSubmitConsentEnforcement -x` | W0 | pending |
| 03-T2-03 | 03 | 2 | PRIV-02 | integration | `python -m pytest tests/test_cli.py::TestExportPrivacyPipeline -x` | W0 | pending |

*Status: pending / green / red / flaky*

*Task ID format: {plan}-T{task}-{seq} (e.g., 01-T1-01 = Plan 01, Task 1, verification 1)*

---

## Wave 0 Requirements

- [ ] `tests/test_privacy.py` — NEW file covering PRIV-01, PRIV-02, PRIV-03 (consent, anonymization, jitter)
- [ ] `tests/test_scrubber.py` additions — IP false positive tests, hex token tests, org domain flagging tests (PRIV-04, PRIV-05, PRIV-06)
- [ ] `tests/test_cli.py` additions — flagged warning display in preview, consent enforcement in submit/export

*Existing infrastructure covers pytest framework and test fixtures.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Preview shows flagged domain warnings visually | PRIV-05 | Rich console output formatting | Run `kajiba preview` with org domain data, visually confirm warning display |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
