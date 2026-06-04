---
phase: 12
slug: eval-scoring-scrub-tuning
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-04
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml ([tool.pytest.ini_options]) |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| {N}-01-01 | 01 | 1 | REQ-{XX} | T-{N}-01 / — | {expected secure behavior or "N/A"} | unit | `{command}` | ✅ / ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*(Populated by the planner — one row per task, covering EEVAL-01 (eval scorer) and EEVAL-02 (experiment scrub).)*

---

## Wave 0 Requirements

- [ ] `tests/fixtures/experiment_complete.json` — complete ExperimentRecord (all completeness signals present)
- [ ] `tests/fixtures/experiment_thin.json` — sparse ExperimentRecord (missing optional eval signals)
- [ ] `tests/fixtures/experiment_pii.json` — PII-laden free text + real model_hash/hardware (preservation proof)
- [ ] `tests/test_eval_scorer.py` — stubs for EEVAL-01
- [ ] `tests/test_experiment_scrub.py` — stubs for EEVAL-02

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `kajiba experiment score` / `scrub` Rich rendering | EEVAL-01/02 | Terminal table formatting is visual | Run the subcommand on a fixture record; confirm breakdown table + bands render |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
