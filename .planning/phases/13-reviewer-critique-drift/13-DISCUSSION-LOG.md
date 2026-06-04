# Phase 13: Reviewer Critique & Drift - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-04
**Phase:** 13-reviewer-critique-drift
**Areas discussed:** Persistence model, Critique & reviewer ID, Lessons structure, Drift definition

> Note: the "Persistence model" area was discussed in a prior session that froze
> mid-discussion; its decisions were recovered from the discussion checkpoint and
> are reproduced here for completeness.

---

## Persistence model

| Option | Description | Selected |
|--------|-------------|----------|
| Mutate in place | Write reviewer fields/drift_flag back into exp_<id>.json (record_id excludes outcome → ID stable) | ✓ |
| Sidecar file | Keep reviewer-authored data in a companion file | |
| You decide | Defer to Claude | |

| Option | Description | Selected |
|--------|-------------|----------|
| Persist | drift_flag written onto the record by the drift command | ✓ |
| Compute-on-read only | Derive drift at read time, never store | |
| Both with --write | Compute-on-read, persist only on --write | |

| Option | Description | Selected |
|--------|-------------|----------|
| Single update_experiment() | One write path in experiment_store.py; in-place overwrite on identity match; all 3 commands funnel through it; closes CR-01 | ✓ |
| --update/--force on log | Extend log_experiment with an override flag | |
| You decide | Defer to Claude | |

**User's choice:** Mutate in place; persist drift_flag; single `update_experiment()`.
**Notes:** Choosing `update_experiment()` as the funnel is the structural fix for the CR-01 dedup data-loss bug (folded todo).

---

## Critique & reviewer ID

| Option | Description | Selected |
|--------|-------------|----------|
| File + interactive + inline | --from FILE for model output, Rich paste when no flag, --critique inline for short notes (offline; human + model reviewers) | ✓ |
| Inline --critique only | Simplest; awkward for multi-paragraph model critiques | |
| Interactive paste only | Always prompt; no scripting/pipe path | |

| Option | Description | Selected |
|--------|-------------|----------|
| Optional --reviewer-model NAME | ModelMetadata(model_name); omit = human, stays None | ✓ |
| Full --reviewer-model-json | Complete ModelMetadata; more friction | |
| Free-text reviewer label | Plain string; needs mapping (schema field is ModelMetadata) | |

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, optional --action flag | Capture recommended_action verdict alongside critique | ✓ |
| Critique only | Leave recommended_action to a separate step | |
| Prompt interactively | Ask for the action in the Rich flow | |

| Option | Description | Selected |
|--------|-------------|----------|
| Replace | Overwrite via update_experiment; matches in-place persistence | ✓ |
| Append with separator | Accumulate multiple reviewers in one string | |
| Refuse unless --force | Guard against accidental clobber | |

**User's choice:** File + interactive + inline; optional `--reviewer-model NAME`; optional `--action`; replace on re-review.
**Notes:** Critique is brought in (paste/file), never pulled from a live API — core stays offline.

---

## Lessons structure

| Option | Description | Selected |
|--------|-------------|----------|
| Tagged-string convention | "category: lesson text"; parse prefix on read; zero schema change | ✓ |
| Plain free-text list | Strings; substring/keyword query only | |
| Compute-on-read index | Derive category index at read time | |

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated `experiment lessons` cmd | --add (repeatable) [--category]; no --add = read; --category filters | ✓ |
| Folded into `experiment review` | Capture lessons only during critique | |
| Both (review seeds + lessons cmd) | review seeds, dedicated cmd adds/queries later | |

| Option | Description | Selected |
|--------|-------------|----------|
| Free-form strings | No frozen vocab; suggest common in --help | ✓ |
| Controlled vocab constant | LESSON_CATEGORIES tuple + Literal | |
| No categories | Pure free text, drop category dimension | |

| Option | Description | Selected |
|--------|-------------|----------|
| Per-record + cross-record filter | lessons <id> prints one; lessons --category X across store; list shows count/flag | ✓ |
| Per-record only now | Defer cross-record to Phase 15 | |
| List flag only | Only has-lessons/count in list | |

**User's choice:** Tagged-string convention; dedicated `experiment lessons` command; free-form categories; per-record + cross-record query.
**Notes:** experiment_scrub.py already scrubs lessons_learned elements, so the tagged convention needs no scrub changes.

---

## Drift definition

| Option | Description | Selected |
|--------|-------------|----------|
| model_name + task_category | Tolerates task_description wording variance; enough runs per group | ✓ |
| model_name + task_description | Exact task text; minor wording changes split groups | |
| model_name + type + category | Finer-grained; smaller/sparser groups | |

| Option | Description | Selected |
|--------|-------------|----------|
| eval_score deviation from baseline | Compare run's eval_score to group prior mean/first run; |delta| > threshold | ✓ |
| Variance / std-dev over group | Flag group when spread exceeds threshold | |
| Monotonic decline trend | Flag sustained downward trend across >=N runs | |

| Option | Description | Selected |
|--------|-------------|----------|
| Both directions, configurable | Regressions AND improvements beyond default 0.15; --threshold override | ✓ |
| Regressions only | Flag only score drops | |
| Both, fixed 0.15 default | Both directions, no override knob | |

| Option | Description | Selected |
|--------|-------------|----------|
| Store-wide scan, write flagged | Scan store, group, compute, write drift_flag via update_experiment; --id for one group; idempotent; Rich summary | ✓ |
| Single --id only | Compute only for a given record's group | |
| Dry-run default + --write | Show without writing unless --write (tension with persist decision) | |

**User's choice:** Group by (model_name, task_category); eval_score deviation from baseline; both directions with configurable --threshold (default 0.15); store-wide scan that writes flagged records, idempotent.
**Notes:** Idempotent re-runs must also clear drift_flag on records that no longer drift.

---

## Claude's Discretion

- `update_experiment()` signature/placement; shared load→mutate→validate→write helper across the three commands.
- `--from` accepting `.txt` (raw) vs `.json` (record fragment) for critique.
- Whether `--threshold` default is also read from `~/.hermes/config.yaml` vs a named module constant (flag-only leaning).
- Exact drift baseline (prior mean vs first run vs rolling window); handling of groups with <2 runs.
- Lesson category-prefix parse rule (delimiter, case, uncategorized fallback).
- Rich rendering details (drift summary table; lessons/critique display).
- Re-export of new public functions from `kajiba/__init__.py`.

## Deferred Ideas

- Multi-reviewer critique history (re-review currently replaces).
- Controlled lesson-category vocabulary (LESSON_CATEGORIES constant).
- Drift threshold in `~/.hermes/config.yaml`.
- Cross-record lessons/drift in the analysis export → Phase 15.
- Live-captured review/drift from Hermes sessions → Phase 14.
