---
phase: 13
slug: reviewer-critique-drift
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-04
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Derived from
> `13-RESEARCH.md` § Validation Architecture (source-verified test infra). The Per-Task
> map below is a scaffold keyed to requirements; task IDs (`13-PP-TT`) are bound after
> `gsd-planner` assigns plans/waves.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (9.0.2 on dev machine; `>=7.0` pinned) + `click.testing.CliRunner` for CLI |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`) — no separate `pytest.ini` |
| **Quick run command** | `python -m pytest tests/test_experiment_store.py tests/test_cli_experiment.py tests/test_experiment_drift.py -x -q` |
| **Full suite command** | `python -m pytest -q` |
| **Estimated runtime** | ~10 seconds |
| **Baseline (must stay green)** | 289 passed, 2 skipped (pre-existing PyYAML soft-dep) — 0 regressions allowed |
| **Store isolation idiom** | `_isolate_store(tmp_path, monkeypatch)` (`tests/test_cli_experiment.py:28`) for CLI; pass `tmp_path/"experiments"` directly for unit tests. **Never touch real `~/.hermes`.** |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_experiment_store.py tests/test_cli_experiment.py tests/test_experiment_drift.py -x -q`
- **After every plan wave:** Run `python -m pytest -q` (full suite green)
- **Before `/gsd-verify-work`:** Full suite green **AND** `git diff --quiet src/kajiba/schema.py` exits 0 (Phase 10 schema provably untouched)
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

> Scaffold — one row per validated behavior, grouped by requirement. `Task ID` / `Plan` /
> `Wave` are bound after planning; `gsd-plan-checker` (Dimension 8) confirms every task with
> code impact maps to a row here.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | — | 0 | CR-01 | T-13-CR01 | `update_experiment` overwrites in place; corrected score persists; exactly one file; `record_id`/filename byte-stable across mutation | unit | `python -m pytest tests/test_experiment_store.py -k "update or identity_stable" -x -q` | ❌ W0 (extend) | ⬜ pending |
| TBD | — | TBD | EREV-01 | — | `experiment review <id> --critique "..."` sets `reviewer_critique`; re-review **replaces** (D-07); `--reviewer-model` sets/omits `reviewer_model` (D-05); `--action` validated vs `RECOMMENDED_ACTIONS` (D-06); `--from .txt`/`.json` + interactive stdin paste (D-04, offline) | integration | `python -m pytest tests/test_cli_experiment.py -k review -x -q` | ❌ W0 (extend) | ⬜ pending |
| TBD | — | TBD | EREV-02 | — | `lessons <id> --add --category X` appends `"x: text"`; read mode prints; `--category` filters; store-wide `lessons --category X` (D-11); `_parse_lesson` first-`:` split + lowercase + `uncategorized` fallback + colon-in-text preserved (D-08/D-10) | integration + unit | `python -m pytest tests/test_cli_experiment.py -k "lessons or parse_lesson" -x -q` | ❌ W0 (extend) | ⬜ pending |
| TBD | — | TBD | EREV-03 | T-13-DRIFT | `compute_drift` flags **both** directions beyond threshold; `<2`-run groups never flagged (no `mean([])` crash); `--threshold` overrides `DRIFT_THRESHOLD=0.15`; `drift` persists `drift_flag` AND **clears idempotently** on re-run (D-12..D-15) | unit + integration | `python -m pytest tests/test_experiment_drift.py tests/test_cli_experiment.py -k "drift" -x -q` | ❌ W0 (new file) | ⬜ pending |
| TBD | — | TBD | WR-01..04 | T-13-ERR | Partial scalar flags raise clear error (not silent interactive, WR-01); `--from` missing `record_kind` → friendly ClickException (WR-02); malformed JSON → Rich ClickException, no traceback (WR-03); tightened D-13 guard rejects same-named dir outside `KAJIBA_BASE` (WR-04) | integration + unit | `python -m pytest tests/test_cli_experiment.py tests/test_experiment_store.py -k "partial_flags or missing_record_kind or malformed_json or guard" -x -q` | ❌ W0 (extend) | ⬜ pending |
| TBD | — | final | regression | — | Full suite green; Phase 10 schema untouched (golden-ID tripwire intact) | suite | `python -m pytest -q && git diff --quiet src/kajiba/schema.py` | ✅ exists (`test_schema_backcompat.py`) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Nyquist continuity rule for the planner:** No 3 consecutive tasks may lack an `<automated>` verify. Wave 0 must land all test scaffolds (RED) before any implementation task runs.

---

## Wave 0 Requirements

- [ ] Extend `tests/test_experiment_store.py` — `update_experiment` overwrite, identity-stable (record_id/filename byte-stable), tightened path guard (CR-01, WR-04).
- [ ] Extend `tests/test_cli_experiment.py` — `review` (3 input modes + reviewer-model + action + re-review), `lessons` (add/read/filter/cross-record + `_parse_lesson`), `drift` (persist + idempotent clear), WR-01/02/03 error paths. **Reuse `_isolate_store` verbatim.**
- [ ] New `tests/test_experiment_drift.py` — pure `compute_drift` unit tests (both directions, `<2`-run, `--threshold`, leave-one-out prior-mean baseline). Build records via the `_make_record` helper pattern (`tests/test_experiment_store.py:27`).
- [ ] Fixtures: none strictly required (build records in-test); a small multi-run fixture set for drift grouping is optional readability sugar.
- [ ] Framework install: none — pytest already present.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Rich interactive multi-line critique paste UX (terminal rendering) | EREV-01 | Visual terminal rendering of the paste prompt is not asserted in CI (the stdin path **is** auto-tested via `CliRunner(input=...)`) | Run `kajiba experiment review <id>` with no flags, paste 2+ lines, confirm critique stored and rendered |
| Drift summary table readability (Rich columns) | EREV-03 | Column layout/coloring is presentation, not logic (the flag values **are** auto-tested) | Run `kajiba experiment drift` over a store with a known regression; eyeball the summary table |

*All correctness behaviors have automated verification; only terminal presentation is manual.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (3 test files above)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] Phase gate includes `git diff --quiet src/kajiba/schema.py` (schema-frozen proof)
- [ ] `nyquist_compliant: true` set in frontmatter (after Wave 0 lands + audit)

**Approval:** pending
