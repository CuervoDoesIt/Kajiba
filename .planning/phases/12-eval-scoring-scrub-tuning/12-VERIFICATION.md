---
phase: 12-eval-scoring-scrub-tuning
verified: 2026-06-04T11:46:49Z
status: passed
score: 2/2 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: null
---

# Phase 12: Eval Scoring & Scrub Tuning Verification Report

**Phase Goal:** Experiment records are scored by eval-appropriate signals and scrubbed without losing model/hardware context
**Verified:** 2026-06-04T11:46:49Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | An eval-specific scorer assigns a quality result to an ExperimentRecord using signals appropriate to model-output evaluation (not coding-trajectory coherence) | VERIFIED | `eval_scorer.compute_eval_confidence` returns `EvalConfidenceResult(composite, sub_scores, confidence_band)`; ran live: complete fixture → `complete`/1.0, thin fixture → `thin`/0.367. Six eval-native sub-checks (output_present, reviewer_critique, model_metadata, hardware_present, lessons_learned, outcome_signals), WEIGHTS sum to 1.0. Distinct band vocabulary (complete/partial/thin) — 0 occurrences of gold/silver/bronze in code. `isinstance` guard rejects KajibaRecord (coding trajectory) with TypeError — confirmed live. Reads ExperimentRecord fields only; never touches `trajectory.conversations`/coherence. |
| 2 | Scrubbing an ExperimentRecord redacts personal/PII data while preserving the model-identity and hardware fields needed for analysis | VERIFIED | `experiment_scrub.scrub_experiment` ran live on `experiment_pii.json`: hardware byte-identical (`before['hardware']==after['hardware']` True), model_hash + gpu_name preserved, experiment_id preserved. Free text redacted: local_model_output email gone, task_category `debugging-for-jane.doe@example.com` → `[REDACTED_EMAIL]` (CR-01 fix present), lessons_learned list shape + length preserved, ScrubLog non-zero (emails=3, file_paths=1). eval_score unchanged. No `kajiba.privacy` coupling (D-05 SKIP boundary honored). |

**Score:** 2/2 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `src/kajiba/eval_scorer.py` | compute_eval_confidence + EvalConfidenceResult, complete/partial/thin bands, experiment-only guard | VERIFIED | 210 lines; exports both symbols; WEIGHTS LOCKED (sum 1.0); thresholds 0.80/0.50; TypeError guard at line 181. |
| `src/kajiba/experiment_scrub.py` | scrub_experiment, field-allowlist, model/hardware byte-identical, reuses scrub_text | VERIFIED | 117 lines; 5 free-text surfaces scrubbed (task_category, task_description, local_model_output, reviewer_critique, lessons_learned[]); reuses `scrub_text`; builds ScrubLog; never imports privacy.*. |
| `src/kajiba/cli.py` | experiment score/scrub subcommands + Confidence column + path-traversal guard | VERIFIED | `experiment_score` (1046), `experiment_scrub` (1092), `_load_experiment` with resolved-parent traversal guard (109) + isinstance guard (123), `add_column("Confidence")` (1013), `--out` store-clobber rejection (1119, WR-02 fix). |
| `src/kajiba/__init__.py` | top-level re-exports | VERIFIED | `from kajiba.eval_scorer import compute_eval_confidence` + `from kajiba.experiment_scrub import scrub_experiment`; both callable from `kajiba.*` (confirmed live). |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| eval_scorer.py | kajiba.schema.ExperimentRecord | import + type annotation | WIRED | imported line 21, used in signature + guard. |
| experiment_scrub.py | kajiba.scrubber.scrub_text | import + call per field | WIRED | imported line 30, called via `_apply` on each allowlist field. |
| experiment_scrub.py | kajiba.schema.ScrubLog | import + construct | WIRED | imported line 31, constructed line 102 with category fold. |
| cli.py | eval_scorer.compute_eval_confidence | import + call in score/list | WIRED | imported line 55, called at 1030 (list) and 1061 (score). |
| cli.py | experiment_scrub.scrub_experiment | import + call in scrub | WIRED | imported line 56, called at 1108. |
| cli.py | schema.load_record | store-load helper | WIRED | called at 117 inside `_load_experiment`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| eval_scorer | sub_scores/composite | reads live ExperimentRecord fields | Yes — computed from real record fields, verified non-trivial output on fixtures | FLOWING |
| experiment_scrub | scrubbed record + ScrubLog | `scrub_text` stats fold over real free text | Yes — ScrubLog counts (emails=3, file_paths=1) reflect actual redactions | FLOWING |
| cli experiment score | result.sub_scores/band | compute_eval_confidence(rec) | Yes — rendered Rich table from real result | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| complete fixture scores complete >=0.80 | `compute_eval_confidence(complete)` | `complete` 1.0 | PASS |
| thin fixture scores thin <0.50 | `compute_eval_confidence(thin)` | `thin` 0.367 | PASS |
| non-experiment rejected | `compute_eval_confidence(KajibaRecord)` | TypeError raised | PASS |
| scrub preserves hardware byte-identical | `before['hardware']==after['hardware']` | True | PASS |
| scrub redacts task_category email (CR-01) | scrub `experiment_pii.json` | `[REDACTED_EMAIL]` | PASS |
| no privacy.* coupling | source scan of experiment_scrub.py | no anonymize_hardware/etc. | PASS |
| top-level re-exports importable | `import kajiba; kajiba.compute_eval_confidence/scrub_experiment` | both callable | PASS |
| full suite | `python -m pytest -q` | 291 passed, 2 skipped | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| EEVAL-01 | 12-01, 12-02, 12-04 | Eval-specific scorer producing signals suited to model-output evaluation, independent of coding scorer | SATISFIED | `eval_scorer.py` with distinct vocabulary + experiment-only guard; REQUIREMENTS.md marks [x]/Complete (lines 64, 143). |
| EEVAL-02 | 12-01, 12-03, 12-04 | Scrub retaining model-identity/hardware while redacting PII | SATISFIED | `experiment_scrub.py` byte-identical preservation + 5-surface allowlist; REQUIREMENTS.md marks [x]/Complete (lines 65, 144). |

No orphaned requirements: both EEVAL-01 and EEVAL-02 mapped to Phase 12 in REQUIREMENTS.md appear in plan frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (none) | — | No TODO/FIXME/XXX/TBD/HACK/PLACEHOLDER/NotImplementedError in new production files | — | Clean |

### Code Review Resolution Status

| Finding | Status | Verified |
| ------- | ------ | -------- |
| CR-01 (task_category not scrubbed) | RESOLVED (7bc7a91) | CONFIRMED — `experiment["task_category"] = _apply(...)` at experiment_scrub.py:82; live scrub redacts the email. `test_task_category_redacted` present + passing. |
| WR-02 (--out could clobber raw store) | RESOLVED (803ade4) | CONFIRMED — cli.py:1119 rejects `--out` resolving into EXPERIMENTS_DIR; `test_experiment_scrub_out_into_store_rejected` present + passing. |
| WR-01/03/04/05, IN-01..04 | DEFERRED (user decision) | Not blocking; informational. |

### Deferred / Out-of-Scope Items

- **sk-live- API-key regex gap** (`deferred-items.md`): the SHARED community `scrubber.py` `api_keys` regex misses `sk-live-` style keys with internal hyphens. Documented as out-of-scope per decision D-09 (Phase 12 reuses the shared scrub engine verbatim, must not fork the regex denylist). This is a property of the shared layer, NOT of the new experiment-scrub allowlist. It does not falsify either success criterion: SC2 requires PII redaction while preserving model/hardware context — the email/path/network categories that constitute the scrub-correctness proof are redacted, and model/hardware are preserved. The unmatched key is a pre-existing community-regex limitation slated for a separate scrubber-hardening pass.

### Human Verification Required

None. Both success criteria are deterministic and were confirmed via live behavioral checks (scoring math + byte-identical preservation). No visual/real-time/external-service behavior is in scope.

### Gaps Summary

No gaps. Both ROADMAP success criteria are observably true in the codebase:
1. The eval scorer (`eval_scorer.py`) assigns a completeness/confidence quality result using eval-native signals (output presence, reviewer critique, model metadata, hardware presence, lessons, outcome signals) with distinct complete/partial/thin vocabulary, and explicitly rejects coding-trajectory records — confirmed by live runs against all fixtures.
2. The experiment scrub (`experiment_scrub.py`) redacts the five free-text PII surfaces while preserving model identity, model_hash, full hardware profile, and experiment_id byte-identical, and never invokes the community hardware-anonymization layer — confirmed by live byte-comparison.

Both post-review fixes (CR-01, WR-02) are present in the actual code and covered by passing tests. Full suite: 291 passed, 2 skipped (pre-existing PyYAML soft-dependency skips). The one documented deferral (sk-live regex) is a shared-layer concern explicitly scoped out per D-09 and does not affect goal achievement.

---

_Verified: 2026-06-04T11:46:49Z_
_Verifier: Claude (gsd-verifier)_
