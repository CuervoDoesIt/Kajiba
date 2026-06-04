---
phase: 12
slug: eval-scoring-scrub-tuning
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-04
validated: 2026-06-04
---

# Phase 12 — Validation Strategy

> Per-phase validation contract. Retroactively audited 2026-06-04 against the executed phase — all tasks COVERED with green automated tests.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml ([tool.pytest.ini_options]) |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -q` |
| **Estimated runtime** | ~10 seconds |
| **Last audited result** | 291 passed, 2 skipped (pre-existing PyYAML soft-dep) |

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
| 12-01-01 | 01 | 1 | EEVAL-01/02 | T-12-01 | Fixtures load as ExperimentRecord; pii fixture carries real hex model_hash + GPU name (non-vacuous preservation input) | unit | `python -c "import json; from kajiba.schema import load_record, ExperimentRecord; [print(isinstance(load_record(json.load(open('tests/fixtures/'+p,encoding='utf-8'))),ExperimentRecord)) for p in ('experiment_complete.json','experiment_thin.json','experiment_pii.json')]"` | ✅ created (W0) | ✅ green |
| 12-01-02 | 01 | 1 | EEVAL-01/02 | T-12-02 | RED scaffolds targeted the right symbols (not vacuously green); now GREEN under Plans 02/03 | unit | `python -m pytest tests/test_eval_scorer.py tests/test_experiment_scrub.py -q` | ✅ created (W0) | ✅ green (RED→GREEN) |
| 12-02-01 | 02 | 2 | EEVAL-01 | T-12-03 / T-12-04 | Read-only compute-on-read (no schema mutation); complete/partial/thin bands, never gold/silver/bronze | unit | `python -m pytest tests/test_eval_scorer.py -x -q` (4 tests) | ✅ (W0 12-01-02) | ✅ green |
| 12-03-01 | 03 | 2 | EEVAL-02 | T-12-05 / T-12-06 | Free-text surfaces redacted; model_hash/identity/full hardware byte-identical; no privacy.* import | unit | `python -m pytest tests/test_experiment_scrub.py -x -q` (5 tests, +1 CR-01) | ✅ (W0 12-01-02) | ✅ green |
| 12-04-01 | 04 | 3 | EEVAL-01/02 | T-12-10 / T-12-12 / T-12-13 | Path-traversal + isinstance guards on store load; scrub never overwrites raw store; Confidence column distinct from Score | integration | `python -c "import kajiba; assert kajiba.compute_eval_confidence and kajiba.scrub_experiment"` | ✅ extended | ✅ green |
| 12-04-02 | 04 | 3 | EEVAL-01/02 | T-12-11 / T-12-12 | score/scrub/list-confidence/missing-id integration; raw store byte-identical after scrub (D-08); --out clobber rejected (WR-02) | integration | `python -m pytest tests/test_cli_experiment.py -x -q && python -m pytest -q` (10 passed) | ✅ extended | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Nyquist continuity check:** No 3 consecutive tasks lack an automated verify — every task above has an `<automated>` command, all confirmed green on audit. Wave 0 (12-01) established all fixtures + RED scaffolds before any implementation task ran.

**Test name inventory (audit cross-reference):**

- `tests/test_eval_scorer.py` (EEVAL-01): `test_complete_experiment_scores_complete`, `test_thin_experiment_scores_thin`, `test_band_vocabulary_distinct`, `test_experiment_only`
- `tests/test_experiment_scrub.py` (EEVAL-02): `test_free_text_redacted`, `test_task_category_redacted` (CR-01), `test_model_and_hardware_preserved`, `test_scrublog_and_outcome_fields`, `test_lessons_list_shape`
- `tests/test_cli_experiment.py` (Phase 12 subset): `test_experiment_score`, `test_experiment_scrub`, `test_experiment_scrub_out`, `test_experiment_scrub_out_into_store_rejected` (WR-02), `test_experiment_list_confidence`, `test_experiment_score_missing`

---

## Wave 0 Requirements

- [x] `tests/fixtures/experiment_complete.json` — complete ExperimentRecord (all completeness signals present) — *Plan 12-01 Task 1*
- [x] `tests/fixtures/experiment_thin.json` — sparse ExperimentRecord (missing optional eval signals) — *Plan 12-01 Task 1*
- [x] `tests/fixtures/experiment_pii.json` — PII-laden free text + real model_hash/hardware (preservation proof) — *Plan 12-01 Task 1*
- [x] `tests/test_eval_scorer.py` — RED stubs for EEVAL-01 (four contract tests) → GREEN under Plan 12-02 — *Plan 12-01 Task 2*
- [x] `tests/test_experiment_scrub.py` — RED stubs for EEVAL-02 (four contract tests) → GREEN under Plan 12-03 — *Plan 12-01 Task 2*

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
- [x] Retroactive audit confirms all tasks COVERED (green) — 2026-06-04

**Approval:** planner-approved 2026-06-04; retroactively audited & confirmed nyquist-compliant 2026-06-04 (post-execution).

---

## Validation Audit 2026-06-04

| Metric | Count |
|--------|-------|
| Tasks audited | 6 |
| COVERED (green) | 6 |
| PARTIAL | 0 |
| MISSING | 0 |
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

**Method:** Re-ran every per-task automated command against the executed codebase. All Phase 12 fixtures load as `ExperimentRecord`; `test_eval_scorer.py` (4), `test_experiment_scrub.py` (5), and the Phase-12 subset of `test_cli_experiment.py` (6) all pass; top-level re-exports import cleanly. Full suite: 291 passed, 2 skipped (pre-existing PyYAML soft-dep). No test files generated — coverage was already complete, and post-review fixes (CR-01 task_category scrub, WR-02 `--out` clobber guard) each shipped with a dedicated regression test, exceeding the planned contract set.
