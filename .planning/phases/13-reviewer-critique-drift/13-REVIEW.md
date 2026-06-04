---
phase: 13-reviewer-critique-drift
reviewed: 2026-06-04T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - src/kajiba/__init__.py
  - src/kajiba/cli.py
  - src/kajiba/experiment_drift.py
  - src/kajiba/experiment_store.py
  - tests/test_cli_experiment.py
  - tests/test_experiment_drift.py
  - tests/test_experiment_exclusion.py
  - tests/test_experiment_store.py
findings:
  critical: 0
  warning: 5
  info: 3
  total: 8
status: issues_found
---

# Phase 13: Code Review Report

**Reviewed:** 2026-06-04
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Phase 13 adds the `kajiba experiment review` / `lessons` / `drift` subcommands, the
in-place `update_experiment` corrective write path, and the pure `compute_drift`
module. I reviewed all four source files and four test files adversarially against
the project conventions (Pydantic v2, EQUAL store guard, frozen schema, drift
algorithm correctness, write atomicity, path-traversal safety) and ran the full
49-test phase suite (all pass).

The core machinery is sound and well-tested:

- **No blockers found.** The content-addressable identity (`schema.py:445-467`)
  hashes only `experiment_id / task_description / local_model_name /
  local_model_output / started_at` — none of which `update_experiment` mutates for
  reviews/lessons/drift — so the in-place overwrite genuinely keeps the on-disk
  filename byte-stable (verified). The dedup-skip data-loss bug (CR-01) is correctly
  closed by removing the `dest.exists()` early-return in `update_experiment`.
- **The store guard is the EQUAL predicate** (`store_dir.resolve() != expected_base.resolve()`)
  in both `log_experiment` and `update_experiment`, resolved at call time so the
  monkeypatch-isolated tests and the production default both work. Verified.
- **The path-traversal guard** in `_load_experiment` (`cli.py:119`) was exercised
  directly: a `record_id` of `../../../Windows/System32/foo` resolves to a parent
  outside the store and is correctly rejected.
- **schema.py is untouched** — no frozen-schema modification.
- **The drift algorithm is correct** per the locked unit + CLI tests:
  nearest-in-group-neighbor baseline, both-direction flagging, `<2`-run guard
  before any neighbor lookup, verdict spanning every input record_id, and group
  isolation by `(model_name, task_category)`.

The findings below are all WARNING/INFO: a significant test-documentation defect
that actively misdescribes the shipped algorithm, two ordering/UX rough edges in the
new CLI commands, an unbounded `--threshold`, and a doc/behavior mismatch on
reviewer-model clearing.

## Warnings

### WR-01: Drift test file docstring and inline comments describe the WRONG algorithm

**File:** `tests/test_experiment_drift.py:1-16, 61, 64, 75, 78, 114-115`
**Issue:** The test module docstring and multiple inline comments assert the
algorithm is **leave-one-out MEAN** ("compares every run's `outcome.eval_score` to
the leave-one-out mean of the OTHER runs in its group (RESEARCH Pattern 3)",
"Leave-one-out mean for c = mean(0.90, 0.90) = 0.90", "the `mean([])` guard"). The
shipped `compute_drift` (`experiment_drift.py:106-113`) uses **nearest-in-group-neighbor**
distance, NOT a leave-one-out mean. The module docstring of `experiment_drift.py`
explicitly documents that 13-03 abandoned the mean because it is outlier-contaminated,
but the test file was never updated to match. The tests still pass only because the
chosen fixtures (0.90/0.90/0.50 etc.) happen to yield the same verdict under both
baselines — the comments are nonetheless false and will mislead the next maintainer
who reasons about a 4-vs-3 balanced-cluster case (exactly the case the production
docstring warns the mean gets wrong). This is a correctness-relevant documentation
defect, not a style nit: a maintainer trusting the test comments would "fix" a
non-bug or write a new test asserting mean behavior that the code does not implement.
**Fix:** Rewrite the `tests/test_experiment_drift.py` module docstring and the
per-test deviation comments to describe nearest-neighbor distance, e.g.:
```python
# Nearest in-group neighbor for c = min(|0.50-0.90|, |0.50-0.90|) = 0.40 > 0.15.
c = _make_record(experiment_id="c", eval_score=0.50, started_minute=2)
```
and replace "the `mean([])` guard" with "the `<2`-run guard (no neighbor lookup on a
lone run)" in `test_group_of_one_never_flagged`.

### WR-02: `experiment review` blocks on stdin paste BEFORE validating the record_id

**File:** `src/kajiba/cli.py:1361-1370`
**Issue:** `experiment_review` calls `text = _read_critique_input(critique, from_path)`
(line 1361) — which, when neither `--critique` nor `--from` is supplied, blocks
reading an interactive paste from stdin (`_read_critique_input` →
`sys.stdin.read()`, line 229) — BEFORE `_mutate_experiment` → `_load_experiment`
ever checks that `record_id` exists or is path-safe. A user who runs
`kajiba experiment review bad_id` (typo, or a traversal probe) is forced to type and
EOF a full critique into the void only to then receive "No experiment found". The
expensive/blocking interactive input should come after cheap validation of the
target.
**Fix:** Load and validate the record first, then resolve the critique text:
```python
record = _load_experiment(record_id)          # cheap path-safe existence check
text = _read_critique_input(critique, from_path)

def _apply_review(rec: ExperimentRecord) -> None:
    rec.outcome.reviewer_critique = text
    ...
mutate_loaded(record, _apply_review)           # or refactor _mutate_experiment to accept a pre-loaded record
```

### WR-03: `drift --threshold` is unbounded; negative values silently flag everything

**File:** `src/kajiba/cli.py:1512-1517`, consumed at `experiment_drift.py:113`
**Issue:** The `--threshold` option is declared `type=float` with no range. A
negative threshold (e.g. `--threshold -1`) makes `nearest > threshold` true for every
run in every multi-run group, mass-flagging (and persisting `drift_flag=True` on) the
entire store with no warning — a silently destructive no-op-looking command. A
threshold of `0` flags any two non-identical runs. Every other numeric/score flag in
this CLI is bounded (`--score` uses `click.FloatRange(0.0, 1.0)`); this one breaks
the convention. Since the verdict is PERSISTED (unlike the compute-on-read scorer),
an out-of-range threshold writes nonsense to disk across the whole store.
**Fix:** Bound the option to the meaningful eval_score-distance range:
```python
@click.option(
    "--threshold",
    type=click.FloatRange(0.0, 1.0),
    default=None,
    help="Override the default DRIFT_THRESHOLD (0.15); both directions (D-14).",
)
```

### WR-04: `experiment review` cannot revert a reviewer_model back to human; docstring says it can

**File:** `src/kajiba/cli.py:1363-1368`, docstring `cli.py:1350-1351`
**Issue:** The docstring states "`--reviewer-model` records the reviewer identity
(omit = human, D-05)". But `_apply_review` only SETS `reviewer_model` when
`reviewer_model is not None` (line 1365); omitting the flag on a record that already
carries a reviewer_model leaves the old identity in place. So a run first reviewed by
`gpt-4o` and then re-reviewed by a human (omitting `--reviewer-model`) is still
attributed to `gpt-4o` on disk — the opposite of "omit = human". The locked test
(`test_review_reviewer_model_set_and_omitted`) only covers omitting on a record that
STARTS null, so the regression is untested. Either the behavior (omit = leave
unchanged) or the docstring (omit = human) is wrong; they disagree.
**Fix:** Decide the contract and align both. If "omit = leave unchanged" is intended,
correct the docstring to "omit = leave the existing reviewer identity unchanged" and
add an explicit `--human` / `--clear-reviewer` flag for reverting. If "omit = human"
is intended, set `rec.experiment.reviewer_model = ModelMetadata(...) if reviewer_model
else None` and add a re-review-by-human test.

### WR-05: `update_experiment` re-validation discards the trajectory round-trip silently if alias handling regresses

**File:** `src/kajiba/experiment_store.py:195-197`
**Issue:** `update_experiment` re-validates via
`ExperimentRecord.model_validate(record.model_dump(mode="json", by_alias=True))`.
This round-trip is only lossless because `RecordBase` carries
`model_config = {"populate_by_name": True}` (schema.py:283) AND the nested
`ConversationTurn.from_` alias (schema.py:144) is also `populate_by_name` — both
verified present today. There is no test in this phase that round-trips an
ExperimentRecord carrying a populated `trajectory` (with aliased `from`/`from_`
turns) through `update_experiment`; every Phase 13 store/CLI test uses
`trajectory=None`. If a future schema edit drops `populate_by_name` from either model,
`model_validate` of the `by_alias=True` dump would raise on the `from` key and the
corrective write path would break for any experiment that captured a trajectory — and
nothing in the suite would catch it.
**Fix:** Add a store-level regression test that builds an ExperimentRecord WITH a
populated `trajectory` (at least one `ConversationTurn`), runs it through
`update_experiment`, and asserts the reloaded file still contains the turn. This pins
the alias round-trip the corrective write path silently depends on.

## Info

### IN-01: `compute_drift` uses exact float comparison for the threshold boundary

**File:** `src/kajiba/experiment_drift.py:113`
**Issue:** `verdict[r.record_id] = nearest > threshold` compares floating-point
eval-score gaps directly. A run exactly `threshold` away from its nearest neighbor
(e.g. scores 0.80 and 0.65 with `threshold=0.15`) depends on binary float
representation: `0.80 - 0.65` is `0.1500000000000000...` and may land just above or
below 0.15. The current tests avoid exact-boundary fixtures so this never bites, but
a user logging round eval scores at exactly the threshold gap could see
implementation-defined flagging.
**Fix:** Document the boundary as "strictly greater than threshold flags" (it already
is) and, if exact-boundary stability matters, compare with a small epsilon or round
gaps to a fixed precision (eval scores are inherently low-precision). Optional.

### IN-02: `import re as _re` inside `_build_highlighted_text` is a function-local import (pre-existing, not Phase 13)

**File:** `src/kajiba/cli.py:383`
**Issue:** `_build_highlighted_text` imports `re` locally as `_re`. CLAUDE.md's import
convention is module-top `import re`. This predates Phase 13 and is out of scope, but
noting it since it sits in the reviewed file. No action required for this phase.

### IN-03: `experiment_drift` command redefines `_apply_drift` inside the loop on every iteration

**File:** `src/kajiba/cli.py:1575-1576`
**Issue:** A fresh `_apply_drift` closure is defined per loop iteration with
`value=flagged` bound as a default argument. This is CORRECT (the default-arg binding
avoids the classic late-binding closure bug, and tests confirm set+clear work), so
this is not a defect — flagging only so a future reader does not "simplify" it into a
shared closure that would reintroduce late binding. Consider lifting it to a
module-level helper `def _set_drift(r, value): r.outcome.drift_flag = value` and
passing `lambda r, v=flagged: _set_drift(r, v)` for clarity. Optional.

---

_Reviewed: 2026-06-04_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
