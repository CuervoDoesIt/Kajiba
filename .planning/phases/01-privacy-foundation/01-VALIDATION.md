---
phase: 1
slug: privacy-foundation
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-30
validated: 2026-04-02
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
| **Estimated runtime** | ~6 seconds |

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
| 01-T1-01 | 01 | 1 | PRIV-06 | unit | `python -m pytest tests/test_scrubber.py::TestIPFalsePositiveFix -x` | ✅ | ✅ green |
| 01-T1-02 | 01 | 1 | PRIV-06 | unit | `python -m pytest tests/test_scrubber.py::TestIPFalsePositiveFix::test_real_ip_still_redacted -x` | ✅ | ✅ green |
| 01-T1-03 | 01 | 1 | PRIV-04 | unit | `python -m pytest tests/test_scrubber.py::TestHexTokenScrubbing -x` | ✅ | ✅ green |
| 01-T1-04 | 01 | 1 | PRIV-04 | unit | `python -m pytest tests/test_scrubber.py::TestHexTokenScrubbing::test_commit_hash_preserved -x` | ✅ | ✅ green |
| 01-T1-05 | 01 | 1 | PRIV-05 | unit | `python -m pytest tests/test_scrubber.py::TestOrgDomainFlagging -x` | ✅ | ✅ green |
| 01-T1-06 | 01 | 1 | PRIV-05 | unit | `python -m pytest tests/test_scrubber.py::TestOrgDomainFlagging::test_safe_domain_github_io -x` | ✅ | ✅ green |
| 02-T1-01 | 02 | 1 | PRIV-01 | unit | `python -m pytest tests/test_privacy.py::TestConsentEnforcement -x` | ✅ | ✅ green |
| 02-T1-02 | 02 | 1 | PRIV-01 | unit | `python -m pytest tests/test_privacy.py::TestConsentEnforcement::test_anonymous_output_json_no_hardware_or_model -x` | ✅ | ✅ green |
| 02-T1-03 | 02 | 1 | PRIV-02 | unit | `python -m pytest tests/test_privacy.py::TestHardwareAnonymization::test_gpu_name_rtx_4090 -x` | ✅ | ✅ green |
| 02-T1-04 | 02 | 1 | PRIV-02 | unit | `python -m pytest tests/test_privacy.py::TestHardwareAnonymization::test_ram_gb_13_rounds_up_to_16 -x` | ✅ | ✅ green |
| 02-T1-05 | 02 | 1 | PRIV-02 | unit | `python -m pytest tests/test_privacy.py::TestHardwareAnonymization::test_anonymize_os_linux_stays_linux -x` | ✅ | ✅ green |
| 02-T1-06 | 02 | 1 | PRIV-03 | unit | `python -m pytest tests/test_privacy.py::TestTimestampJitter -x` | ✅ | ✅ green |
| 02-T1-07 | 02 | 1 | PRIV-03 | unit | `python -m pytest tests/test_privacy.py::TestTimestampJitter::test_jitter_is_deterministic -x` | ✅ | ✅ green |
| 03-T1-01 | 03 | 2 | PRIV-01..06 | integration | `python -m pytest tests/ -x -v` | ✅ | ✅ green |
| 03-T2-01 | 03 | 2 | PRIV-05 | integration | `python -m pytest tests/test_cli.py::TestPreviewFlaggedWarnings -x` | ✅ | ✅ green |
| 03-T2-02 | 03 | 2 | PRIV-01 | integration | `python -m pytest tests/test_cli.py::TestSubmitConsentEnforcement -x` | ✅ | ✅ green |
| 03-T2-03 | 03 | 2 | PRIV-02 | integration | `python -m pytest tests/test_cli.py::TestExportPrivacyPipeline -x` | ✅ | ✅ green |

*Status: ✅ green — 17/17 entries covered*

---

## Wave 0 Requirements

- [x] `tests/test_privacy.py` — 37 tests covering PRIV-01, PRIV-02, PRIV-03 (consent, anonymization, jitter)
- [x] `tests/test_scrubber.py` additions — 23 tests: IP false positive (8), hex token (6), org domain flagging (6), flagging support (3) covering PRIV-04, PRIV-05, PRIV-06
- [x] `tests/test_cli.py` additions — 6 tests: flagged warnings (3), consent enforcement (2), export privacy pipeline (1)

*All Wave 0 requirements fulfilled. 66 total tests cover all 6 requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Preview shows flagged domain warnings visually | PRIV-05 | Rich console output formatting | Run `kajiba preview` with org domain data, visually confirm warning display |
| Submit workflow with consent="anonymous" end-to-end | PRIV-01 | Interactive CLI confirmation prompt | Run `kajiba submit` on record with consent_level="anonymous", confirm outbox file has no metadata |

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

All 17 verification entries ran green (66 tests, 0.64s). No gaps detected — all requirements have full automated coverage. Phase 1 is Nyquist-compliant.
