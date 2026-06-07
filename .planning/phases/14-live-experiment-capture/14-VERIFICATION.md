---
phase: 14-live-experiment-capture
verified: 2026-06-06T00:00:00Z
status: human_needed
score: 2/2 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Live Hermes v0.15.x eval session with KAJIBA_EXPERIMENT=1 produces exactly one exp_*.json (SC#1 live proof)"
    expected: "A multi-turn-then-exit eval session in live Hermes with KAJIBA_EXPERIMENT=1 yields exactly one exp_*.json in EXPERIMENTS_DIR and nothing in STAGING_DIR/OUTBOX_DIR"
    why_human: "Requires a real Hermes v0.15.x process; automated tests drive the collector directly via the real on_llm_turn/on_session_end entry points but cannot stand up a live Hermes host. Declared MANUAL/out-of-band in 14-VALIDATION.md."
---

# Phase 14: Live Experiment Capture Verification Report

**Phase Goal:** An eval run inside a live Hermes session is captured automatically as an `ExperimentRecord`.
**Verified:** 2026-06-06
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 (SC#1) | Running an evaluation inside a live Hermes session produces an `ExperimentRecord` via the shared plugin hooks | ✓ VERIFIED (automated) / ? human (live proof) | Wiring fully present in code and exercised by automated tests through the REAL plugin entry points (`on_llm_turn` + `on_session_end`). `_finalize_experiment` (collector.py:633) is reached from `on_session_end` (collector.py:712-714) and writes via `experiment_store.update_experiment`. Plugin hooks (`plugin/hooks.py` + `plugin/__init__.py`) delegate `on_session_start`/post_llm_call→`on_llm_turn`/`on_session_end` to the same module-level `_collector`, so experiment-mode state persists across the session. `test_opted_in_session_writes_one_record` passes (exactly 1 exp_*.json across 3 turn-scoped `on_session_end` firings). The end-to-end LIVE-HERMES proof is explicitly MANUAL per 14-VALIDATION.md → routed to human_needed. |
| 2 (SC#2) | A live-captured experiment record carries the same metadata/outcome structure as a deliberately-logged one | ✓ VERIFIED | `_build_experiment_record` (collector.py:856) routes through the same `build_experiment_record` constructor used by `kajiba experiment log`, giving structural parity by construction. `test_structural_parity_with_deliberate_log` asserts top-level keys ⊇ deliberate, identical `experiment`/`outcome` key sets, `record_kind=="model_experiment"`, `eval_score==0.0`, populated `trajectory` — passes. `test_field_mapping` confirms D-03..D-06 field mapping — passes. |

**Score:** 2/2 truths verified (SC#1 automated coverage complete; live-Hermes end-to-end proof deferred to human per the validation contract)

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `src/kajiba/collector.py` :: `_build_trajectory()` | Shared trajectory assembly | ✓ VERIFIED | Defined collector.py:823; called by both `_build_record` (921) and `_build_experiment_record` (906). Byte-identical refactor; coding-path lifecycle tests pass. |
| `src/kajiba/collector.py` :: `_build_experiment_record(session_id)` | D-03..D-06 ExperimentRecord assembly | ✓ VERIFIED | collector.py:856. first human→task_description, last gpt→local_model_output (defensive `next(...)`), eval_score=0.0, started_at=self._created_at, model/hardware/trajectory forwarded, rich-metadata promotion `rec.experiment.local_model` (912). |
| `src/kajiba/collector.py` :: `_finalize_experiment(session_id)` | Design B self-cleaning finalize-once | ✓ VERIFIED | collector.py:633. Zero-turn guard (659), compute_record_id before path (667), self-cleaning unlink (674-675), `update_experiment` write (680). |
| `src/kajiba/collector.py` :: on_session_end experiment branch | Branch BEFORE contribution_mode read, unconditional return | ✓ VERIFIED | collector.py:712-714 `if self._experiment_mode: self._finalize_experiment(session_id); return` — sits before the `contribution_mode = _load_config_value(...)` read at 717. Coding path below unchanged. |
| `src/kajiba/collector.py` :: experiment_store module import | `from kajiba import experiment_store` (module attr, not bound name) | ✓ VERIFIED | collector.py:17 module import; collector.py:18 `build_experiment_record` by name. Store dir referenced only as `experiment_store.EXPERIMENTS_DIR` (671, 680). No `from kajiba.experiment_store import EXPERIMENTS_DIR` bound name. |
| `src/kajiba/collector.py` :: call-time KAJIBA_EXPERIMENT* env reads | Read in on_session_start at call time | ✓ VERIFIED | collector.py:423-431 reads `KAJIBA_EXPERIMENT`/`_TYPE`/`_CATEGORY` inside on_session_start try block; type validated against `EXPERIMENT_TYPES` with fallback. `import os` at line 10. |
| `tests/test_collector.py` :: `TestExperimentCapture` | Six exactly-named ECAP-01 tests | ✓ VERIFIED | Class at line 958 with all six methods; substantive assertions (no weakened stubs). `_drive_turns` (927) drives via real `on_llm_turn`+`on_session_end`. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| on_session_end | _finalize_experiment | `if self._experiment_mode: ...; return` before contribution_mode read | ✓ WIRED | collector.py:712-714 before 717 |
| _finalize_experiment | experiment_store.update_experiment + EXPERIMENTS_DIR | live module attribute as store_dir (D-13 equal) | ✓ WIRED | collector.py:680; test passes under monkeypatch isolation (no D-13 ValueError) |
| _build_experiment_record | build_experiment_record | constructor + **extra (model/hardware/trajectory) | ✓ WIRED | collector.py:891-907 |
| _build_experiment_record | experiment.local_model | rich-metadata promotion before write | ✓ WIRED | collector.py:911-912 |
| on_session_start | os.environ KAJIBA_EXPERIMENT* | call-time env read setting mode flags | ✓ WIRED | collector.py:423-431 |
| plugin hooks | shared _collector instance | post_llm_call→on_llm_turn, on_session_end delegate to same collector | ✓ WIRED | plugin/hooks.py:84,106,157; plugin/__init__.py:40-43 |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| TestExperimentCapture suite (6 ECAP-01 behaviors) | `.venv/Scripts/python.exe -m pytest tests/test_collector.py::TestExperimentCapture -q` | 6 passed in 2.15s | ✓ PASS |
| Full regression suite | `.venv/Scripts/python.exe -m pytest -q` | 471 passed, 2 skipped (PyYAML soft-dep), 0 failed | ✓ PASS |
| Frozen-schema invariant | `git diff --quiet 61f0146 HEAD -- src/kajiba/schema.py` | exit 0 | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| ECAP-01 | 14-01, 14-02, 14-03 | An eval run inside a live Hermes session is captured into an ExperimentRecord through the shared plugin hooks | ✓ SATISFIED | All 6 ECAP-01 automated tests green; wiring verified end-to-end in code; REQUIREMENTS.md:75,148 marks ECAP-01 / Phase 14 / Complete. Live-Hermes proof routed to human (per 14-VALIDATION.md Manual-Only). |

No orphaned requirements: ECAP-01 is the sole Phase-14 requirement in REQUIREMENTS.md and is claimed by all three plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| src/kajiba/collector.py | 864 | "placeholder" in docstring | ℹ️ Info | Describes the documented D-05 design decision (`eval_score=0.0` is captured-but-unscored, scored later via `kajiba experiment score`). Not a code stub — no debt marker, no follow-up needed. |

No TODO/FIXME/XXX/TBD/HACK markers in modified files. `eval_score=0.0` is an intentional, documented placeholder per D-05, not an unimplemented stub.

### Human Verification Required

#### 1. Live Hermes SC#1 end-to-end proof

**Test:** Run a multi-turn-then-exit evaluation session in a live Hermes v0.15.x process with `KAJIBA_EXPERIMENT=1` set.
**Expected:** Exactly one `exp_*.json` lands in `EXPERIMENTS_DIR`; `STAGING_DIR` and `OUTBOX_DIR` remain empty.
**Why human:** Requires a real Hermes host process. The automated `TestExperimentCapture` suite drives the collector through the real `on_llm_turn`/`on_session_end` plugin entry points and proves the finalize-once + privacy-isolation logic, but cannot stand up a live Hermes runtime. Declared MANUAL/out-of-band in 14-VALIDATION.md (recommended on the DGX Spark per the Loop-B lab decision).

### Gaps Summary

No gaps. All must-have truths are verified in code and confirmed by a green automated suite (471 passed / 0 failed; TestExperimentCapture 6/6). The phase goal — automatic capture of a live eval run as an `ExperimentRecord` — is achieved in the codebase: the env-var opt-in trigger, the shared-trajectory `_build_experiment_record` assembly (SC#2 parity by construction), the Design-B self-cleaning finalize-once write, and the D-08 privacy guard (experiment branch before the contribution_mode read with unconditional return) are all present and wired through the shared plugin hooks. The frozen-schema invariant holds (schema.py unchanged). The only outstanding item is the live-Hermes end-to-end SC#1 proof, which is an explicit MANUAL/out-of-band verification per the phase validation contract — hence `human_needed`, not `gaps_found`.

---

_Verified: 2026-06-06_
_Verifier: Claude (gsd-verifier)_
