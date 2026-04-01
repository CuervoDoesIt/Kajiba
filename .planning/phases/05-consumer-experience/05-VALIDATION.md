---
phase: 5
slug: consumer-experience
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-01
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/test_cli.py tests/test_publisher.py -x -v` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_cli.py tests/test_publisher.py -x -v`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | CONS-02 | unit | `pytest tests/test_publisher.py::TestGenerateCatalogEnriched -x` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | CONS-02 | unit | `pytest tests/test_publisher.py::TestGitHubOpsRead -x` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 1 | CONS-03 | unit | `pytest tests/test_cli.py::TestBrowseCommand -x` | ❌ W0 | ⬜ pending |
| 05-02-02 | 02 | 1 | CONS-01, CONS-04 | unit | `pytest tests/test_cli.py::TestDownloadCommand -x` | ❌ W0 | ⬜ pending |
| 05-02-03 | 02 | 1 | CONS-03, CONS-04 | unit | `pytest tests/test_publisher.py::TestFilterCatalog -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_publisher.py::TestGenerateCatalogEnriched` — stubs for CONS-02 catalog enrichment
- [ ] `tests/test_publisher.py::TestFilterCatalog` — stubs for catalog filtering pure function
- [ ] `tests/test_publisher.py::TestGitHubOpsRead` — stubs for read-only gh api methods (mocked)
- [ ] `tests/test_cli.py::TestBrowseCommand` — stubs for browse command (mocked GitHubOps)
- [ ] `tests/test_cli.py::TestDownloadCommand` — stubs for download command (mocked GitHubOps, tmp_path)
- [ ] Test fixtures: sample `catalog.json` with enriched model metadata

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Rich progress bar renders correctly during download | CONS-04 | Visual rendering depends on terminal | Run `kajiba download --model <name> --tier gold` and observe progress bar |
| gh CLI authentication prompt | CONS-03, CONS-04 | Requires actual gh auth state | Run `kajiba browse` without gh auth, verify error message suggests `gh auth status` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
