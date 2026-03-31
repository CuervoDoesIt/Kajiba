---
phase: 3
slug: dataset-publishing
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-31
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
| **Estimated runtime** | ~10 seconds |

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
| 03-01-01 | 01 | 1 | PUB-01 | unit | `python -m pytest tests/test_publisher.py::TestFileLayout tests/test_publisher.py::TestSharding -x` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | PUB-02 | unit | `python -m pytest tests/test_publisher.py::TestCatalog -x` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | PUB-03 | unit (mocked gh) | `python -m pytest tests/test_publisher.py::TestGitHubOps -x` | ❌ W0 | ⬜ pending |
| 03-01-04 | 01 | 1 | PUB-04 | unit | `python -m pytest tests/test_publisher.py::TestReadmeGeneration -x` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 2 | PUB-05 | CLI integration (mocked gh) | `python -m pytest tests/test_cli.py::TestPublishCommand -x` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 2 | PRIV-07 | unit + CLI integration | `python -m pytest tests/test_publisher.py::TestDeletion tests/test_cli.py::TestDeleteCommand -x` | ❌ W0 | ⬜ pending |
| 03-02-03 | 02 | 2 | PRIV-08 | unit | `python -m pytest tests/test_publisher.py::TestDeletionIndex -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_publisher.py` — stubs for PUB-01 through PUB-05, PRIV-07, PRIV-08 (new file)
- [ ] Test fixtures: outbox record files for publish testing
- [ ] Mock/patch infrastructure for `subprocess.run` calls to `gh` and `git`

*All test files are new — no existing infrastructure covers Phase 3 requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `gh auth status` returns valid auth | PUB-03 | Requires real GitHub credentials | Run `gh auth status` on dev machine; verify exit code 0 |
| PR opens successfully on GitHub | PUB-05 | Requires real fork + network access | Run `kajiba publish` against a test dataset repo; verify PR appears on GitHub |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
