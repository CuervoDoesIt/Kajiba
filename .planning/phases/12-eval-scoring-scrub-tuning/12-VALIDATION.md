---
phase: 12
slug: eval-scoring-scrub-tuning
status: planned
nyquist_compliant: true
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
| 12-01-01 | 01 | 1 | EEVAL-01/02 | T-12-01 | Fixtures load as ExperimentRecord; pii fixture carries real hex model_hash + GPU name (non-vacuous preservation input) | unit | `python -c "import json; from kajiba.schema import load_record, ExperimentRecord; [print(isinstance(load_record(json.load(open('tests/fixtures/'+p,encoding='utf-8'))),ExperimentRecord)) for p in ('experiment_complete.json','experiment_thin.json','experiment_pii.json')]"` | ❌ W0 (this task creates them) | ⬜ pending |
| 12-01-02 | 01 | 1 | EEVAL-01/02 | T-12-02 | RED scaffolds fail ONLY on missing modules (target the right symbols, not vacuously green) | unit | `python -m pytest tests/test_eval_scorer.py tests/test_experiment_scrub.py -q` (expected NON-ZERO = RED) | ❌ W0 (this task creates them) | ⬜ pending |
| 12-02-01 | 02 | 2 | EEVAL-01 | T-12-03 / T-12-04 | Read-only compute-on-read (no schema mutation); complete/partial/thin bands, never gold/silver/bronze | unit | `python -m pytest tests/test_eval_scorer.py -x -q` | ✅ (W0 12-01-02) | ⬜ pending |
| 12-03-01 | 03 | 2 | EEVAL-02 | T-12-05 / T-12-06 | Four free-text surfaces redacted; model_hash/identity/full hardware byte-identical; no privacy.* import | unit | `python -m pytest tests/test_experiment_scrub.py -x -q` | ✅ (W0 12-01-02) | ⬜ pending |
| 12-04-01 | 04 | 3 | EEVAL-01/02 | T-12-10 / T-12-12 / T-12-13 | Path-traversal + isinstance guards on store load; scrub never overwrites raw store; Confidence column distinct from Score | integration | `python -c "import kajiba; assert kajiba.compute_eval_confidence and kajiba.scrub_experiment" && python -m pytest tests/test_cli_experiment.py -q` | ⚠️ extend (existing file) | ⬜ pending |
| 12-04-02 | 04 | 3 | EEVAL-01/02 | T-12-11 / T-12-12 | score/scrub/list-confidence/missing-id integration; raw store byte-identical after scrub (D-08) | integration | `python -m pytest tests/test_cli_experiment.py -x -q && python -m pytest -q` | ⚠️ extend (existing file) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Nyquist continuity check:** No 3 consecutive tasks lack an automated verify — every task above has an `<automated>` command. Wave 0 (12-01) establishes all fixtures + RED scaffolds before any implementation task runs.

---

## Wave 0 Requirements

- [ ] `tests/fixtures/experiment_complete.json` — complete ExperimentRecord (all completeness signals present) — *Plan 12-01 Task 1*
- [ ] `tests/fixtures/experiment_thin.json` — sparse ExperimentRecord (missing optional eval signals) — *Plan 12-01 Task 1*
- [ ] `tests/fixtures/experiment_pii.json` — PII-laden free text + real model_hash/hardware (preservation proof) — *Plan 12-01 Task 1*
- [ ] `tests/test_eval_scorer.py` — RED stubs for EEVAL-01 (four contract tests) — *Plan 12-01 Task 2*
- [ ] `tests/test_experiment_scrub.py` — RED stubs for EEVAL-02 (four contract tests) — *Plan 12-01 Task 2*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `kajiba experiment score` / `scrub` Rich rendering | EEVAL-01/02 | Terminal table/panel formatting is visual | Run the subcommand on a fixture record; confirm breakdown table + bands render. (Note: automated tests already assert exit 0 + presence of band words + "Confidence" header + PII-absence; only the visual layout is manual.) |

*All functional behaviors have automated verification; only visual table layout is manual.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planner-approved 2026-06-04 (pending execution)
