---
phase: 4
slug: contribution-modes
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-01
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
| **Estimated runtime** | ~5 seconds |

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
| 04-01-01 | 01 | 1 | CONT-01 | unit | `python -m pytest tests/test_cli.py -k review -x` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | CONT-02 | unit | `python -m pytest tests/test_collector.py -k continuous -x` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 1 | CONT-03 | unit | `python -m pytest tests/test_cli.py -k config -x` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 1 | CONT-04 | unit | `python -m pytest tests/test_cli.py -k config -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_review.py` — stubs for CONT-01 (ad-hoc review approve/reject)
- [ ] `tests/test_continuous.py` — stubs for CONT-02 (auto-submit threshold)
- [ ] `tests/test_config_commands.py` — stubs for CONT-03, CONT-04 (config set/get/show)

*Existing test infrastructure (pytest, conftest.py) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Interactive review prompt (approve/reject/skip) | CONT-01 | Requires TTY input | Run `kajiba review` with staged record, verify prompt appears, select approve |
| Activity notification on next CLI use | CONT-02 | Requires two sequential CLI invocations | Auto-submit a record, then run `kajiba stats`, verify summary line appears |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
