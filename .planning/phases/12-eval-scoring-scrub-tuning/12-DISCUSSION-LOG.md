# Phase 12: Eval Scoring & Scrub Tuning - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-04
**Phase:** 12-eval-scoring-scrub-tuning
**Areas discussed:** Eval scorer signals, Score shape & timing, Scrub preserve-list, Scrub timing

---

## Eval Scorer — what it produces (EEVAL-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Completeness/confidence | Assess how complete & trustworthy the eval record is (output, reviewer, lessons, model+hw metadata, eval_score in range); does NOT re-judge the model's answer | ✓ |
| Composite from eval signals | Weighted blend of eval_score + recommended_action + metadata completeness into one composite + tier | |
| Bucket the eval_score | Minimal: tier the existing caller-set eval_score + a light completeness check | |

**User's choice:** Completeness/confidence (Recommended).
**Notes:** eval_score stays the answer-quality judgment; the scorer is a trust/completeness lens beside it.

---

## Eval Scorer — when computed (EEVAL-01)

| Option | Description | Selected |
|--------|-------------|----------|
| On-demand command | Compute on read via `kajiba experiment score` + surface in `list`; no schema change; log path stays pure-write; re-scorable | ✓ |
| At log time, persisted | Auto-score every run and store it — requires adding a field to the frozen Phase-10 schema | |
| Both (auto + recompute) | Score at log time and allow recompute — most surface area; still needs the schema field | |

**User's choice:** On-demand command (Recommended).
**Notes:** Keeps the Phase-10 schema frozen (compute-on-read); preserves Phase 11 D-08 single-write-path.

---

## Eval Scorer — result shape

| Option | Description | Selected |
|--------|-------------|----------|
| Confidence 0–1 + eval-native bands | QualityResult-like dataclass: confidence composite + bands (complete/partial/thin) + per-check breakdown; distinct vocab from coding scorer | ✓ |
| Reuse gold/silver/bronze | Same QualityResult shape/labels as the coding scorer for consistency | |
| Align bands with recommended_action | Map confidence to use_as_is/route_to_reviewer/discard | |

**User's choice:** Confidence 0–1 + eval-native bands (Recommended).
**Notes:** gold/silver/bronze signals training-data value — kept distinct to avoid confusion with eval trustworthiness.

---

## Experiment Scrub — preserve vs redact (EEVAL-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Preserve exact, skip anonymization | Bypass privacy.py hardware anonymization; keep model_name/quantization/model_hash + full hardware; scrub only free text; model_hash explicitly protected | ✓ |
| Preserve identity, generalize hardware | Keep model identity exact but still generalize hardware tiers | |
| Allowlist — you design it | Leave the exact protected-field set to research/planner | |

**User's choice:** Preserve exact, skip anonymization (Recommended).
**Notes:** Inverse of the community pipeline; model_hash needs explicit protection from the hex-token pattern.

---

## Experiment Scrub — when it runs (EEVAL-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Store raw, scrub on export | Keep storing raw; scrub at analysis-export (Phase 15) or via `kajiba experiment scrub`; preserves real output for the Phase 13 reviewer | ✓ |
| Scrub on log (no raw at rest) | Redact before writing — strongest privacy, but reviewer only sees scrubbed output and originals can't be recovered | |
| Manual scrub command only | Add `kajiba experiment scrub`; no automatic scrubbing — max control, easy to forget | |

**User's choice:** Store raw, scrub on export (Recommended).
**Notes:** Closes AR-11-01 at the share boundary, not the log; private store makes raw-at-rest acceptable.

---

## Experiment Scrub — free-text field scope

| Option | Description | Selected |
|--------|-------------|----------|
| All free text (max-scrub) | Scrub local_model_output, reviewer_critique, task_description, lessons_learned via scrub_text | ✓ |
| Output + critique only | Scrub only the two largest free-text fields | |
| You decide (planner derives) | Leave exact field set to research/planner | |

**User's choice:** All free text (Recommended, max-scrub).
**Notes:** Matches CLAUDE.md over-redact-by-default; model/hardware preserved per the preserve-list choice.

---

## Claude's Discretion

- Exact module/file names and whether experiment scrub lives in `scrubber.py` (record_kind dispatch) vs a new module.
- The exact completeness sub-checks and their weights in the confidence composite.
- Exact band labels/thresholds (complete/partial/thin vs high/med/low).
- Whether `experiment score` renders a Rich per-check table and whether `list` gains a confidence column.
- Whether the scrub emits a `ScrubLog` (lean yes) and whether new public funcs are re-exported from `__init__.py` (lean yes).

## Deferred Ideas

- Quality-drift detection → Phase 13 (scorer reads `drift_flag` but doesn't compute it).
- Reviewer critique attachment + `lessons_learned` querying → Phase 13.
- Analysis-export format + practice-project integration → Phase 15.
- Persisting the computed score into the schema → out of scope (compute-on-read chosen).
- CR-01 re-log dedup todo — reviewed, not folded (store-dedup correctness, not scoring/scrubbing).
