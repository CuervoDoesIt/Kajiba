# Phase 14: Live Experiment Capture - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-06
**Phase:** 14-live-experiment-capture
**Areas discussed:** Eval-run trigger, Field mapping, Capture architecture, Capture-time pipeline

---

## Eval-run trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Env var / config opt-in | `KAJIBA_EXPERIMENT=1` read at `on_session_start`, routes whole session; default coding capture unchanged; no Hermes command-surface dependency | ✓ |
| In-session marker / command | Mid-session command/sentinel the plugin detects; depends on an unverified command-hook surface | |
| Infer from session metadata | Auto-detect from model name / task tag; misclassification = privacy risk | |

**User's choice:** Env var / config opt-in
**Notes:** Safe, explicit opt-in that reuses only the four confirmed lifecycle hooks.

## Run scope

| Option | Description | Selected |
|--------|-------------|----------|
| Whole opted-in session = one run | One session → one ExperimentRecord; multiple evals = multiple sessions | ✓ |
| Segment within a session | Start/stop markers → multiple records per session; needs in-session boundary signals | |

**User's choice:** Whole opted-in session = one run

---

## Field mapping

| Question | Selected | Alternatives not chosen |
|----------|----------|-------------------------|
| `local_model_output` source | **Final assistant response** | All assistant turns joined; Full transcript |
| `task_description` / `task_category` / `experiment_type` | **First user prompt → description; env-var defaults for category+type** | All from env vars; Prompt + fixed defaults |
| `eval_score` handling (required 0–1) | **Placeholder `0.0` at capture, scored later** | Auto-run Phase 12 scorer (completeness ≠ quality); Prompt user at session end (fragile in hook) |
| Populate `trajectory`? | **Yes — populate trajectory** | No — scalar fields only |

**Notes:** Final assistant response is the clean single "output"; the full
conversation is preserved in `trajectory` so nothing is lost. `eval_score=0.0` is a
documented captured-but-unscored convention (schema field is frozen/required).

---

## Capture architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Mode flag on KajibaCollector | Shared buffering, divergent finalize → `build_experiment_record`/`log_experiment` → EXPERIMENTS_DIR, bypass staging/outbox/auto-submit | ✓ |
| Separate ExperimentCollector + shared base | Distinct collector over an extracted base; cleaner but more refactor | |
| Capture as KajibaRecord, then convert | Reuses everything but a coding record briefly lands in staging (privacy risk) | |

**User's choice:** Mode flag on KajibaCollector
**Notes:** Implements the v1.2 "shared core, divergent tail" stance with the least code.

---

## Capture-time pipeline

| Option | Description | Selected |
|--------|-------------|----------|
| Store raw; scrub/score/review later | Finalize writes raw record (mirrors Phase 11); scrub/score/review/drift run later via subcommands; honors no-scrub-in-hook rule; reviewer not live | ✓ |
| Auto-scrub at finalize | Run `experiment_scrub` at finalize; conflicts with "scrub is a CLI step, never in a hook" rule | |

**User's choice:** Store raw; scrub/score/review later

---

## Claude's Discretion

- Finalize-once for experiments (turn-scoped `on_session_end` + content-addressed ID → multiple files; must accumulate + finalize once per session). **Correctness item, must solve.**
- `experiment_id` derivation for a live run (likely from `session_id`).
- Reuse of `self._model_metadata` (`_enrich_from_ollama`, CAPT-04) as `local_model`.
- Remote model under eval mode (`is_local=false` acceptable — capture not blocked on locality).
- Exact env-var names + defaults and where the flag is stored on the collector.

## Deferred Ideas

- Auto-scoring/scrubbing at capture — rejected (rule conflict); manual post-capture step.
- In-session eval segmentation (multiple records per session) — deferred; needs a verified boundary signal.
- Practice-project / analysis-export supplying a real `eval_score` at write time → Phase 15 (EEXP-01/02).
- Reviewed-not-folded todo: `2026-06-04-fix-experiment-relog-dedup-cr01.md` (already closed in Phase 13).
