---
phase: 3
slug: dataset-publishing
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-31
validated: 2026-04-02
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=7.0 |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `python -m pytest tests/test_publisher.py tests/test_cli.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~6 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_publisher.py tests/test_cli.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | PUB-01 | unit | `python -m pytest tests/test_publisher.py::TestNormalizeModelName tests/test_publisher.py::TestComputeShardKey tests/test_publisher.py::TestComputeRecordPath tests/test_publisher.py::TestWriteRecordsToShards -x` | yes | green |
| 03-01-02 | 01 | 1 | PUB-02 | unit | `python -m pytest tests/test_publisher.py::TestGenerateCatalog tests/test_publisher.py::TestGenerateCatalogEnriched -x` | yes | green |
| 03-01-03 | 01 | 1 | PUB-03 | unit (mocked gh) | `python -m pytest tests/test_publisher.py::TestGitHubOps tests/test_publisher.py::TestGitHubOpsRead -x` | yes | green |
| 03-01-04 | 01 | 1 | PUB-04 | unit | `python -m pytest tests/test_publisher.py::TestGenerateReadme -x` | yes | green |
| 03-02-01 | 02 | 2 | PUB-05 | CLI integration (mocked gh) | `python -m pytest tests/test_cli.py::TestPublishCommand tests/test_cli.py::TestPublishConsentReverification -x` | yes | green |
| 03-02-02 | 02 | 2 | PRIV-07 | unit + CLI integration | `python -m pytest tests/test_publisher.py::TestCreateDeletionEntry tests/test_cli.py::TestDeleteCommand -x` | yes | green |
| 03-02-03 | 02 | 2 | PRIV-08 | unit | `python -m pytest tests/test_publisher.py::TestDeletionIndex tests/test_publisher.py::TestGenerateCatalog::test_catalog_reads_deletions -x` | yes | green |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [x] `tests/test_publisher.py` -- unit tests for PUB-01 through PUB-04, PRIV-08 (63 original + 2 Nyquist = 65 tests across 12 classes)
- [x] `tests/test_cli.py` -- integration tests for PUB-05, PRIV-07 (8 original + 2 Nyquist = 10 tests across 3 classes)
- [x] Test fixtures: outbox record helper `_make_outbox_record()` in test_cli.py, `_make_record_dict()` in test_publisher.py
- [x] Mock/patch infrastructure for `subprocess.run` calls to `gh` and `git` via monkeypatch

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `gh auth status` returns valid auth | PUB-03 | Requires real GitHub credentials | Run `gh auth status` on dev machine; verify exit code 0 |
| PR opens successfully on GitHub | PUB-05 | Requires real fork + network access | Run `kajiba publish` against a test dataset repo; verify PR appears on GitHub |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** passed (Nyquist audit 2026-04-02)

---

## Validation Audit

**Audit date:** 2026-04-02
**Auditor:** Nyquist auditor (gsd-nyquist-auditor)
**Baseline tests (pre-audit):** 170 Phase 3 tests passing (85 publisher + 85 CLI)
**Post-audit tests:** 176 Phase 3 tests passing (+4 new Nyquist tests, +2 TestDeletionIndex)
**Full suite:** 356 tests passing, 0 regressions

### Gaps Found and Filled

| # | Gap | Requirement | Resolution | Tests Added |
|---|-----|-------------|------------|-------------|
| 1 | No happy-path test for `kajiba delete` (only error cases covered) | PRIV-07 | Added `TestDeleteCommand::test_delete_appends_to_deletions_jsonl` -- verifies CLI writes to deletions.jsonl and creates PR | 1 |
| 2 | No `TestDeletionIndex` class for end-to-end deletion tracking | PRIV-08 | Added `TestDeletionIndex` with 2 tests -- verifies create_deletion_entry entries are counted by generate_catalog | 2 |
| 3 | No assertion that `apply_consent_level` is called during publish | PUB-05/D-03 | Added `TestPublishConsentReverification::test_publish_calls_apply_consent_level` -- verifies consent re-verification | 1 |

### Implementation Issues Found

None. All tests pass against existing implementation without modification.
