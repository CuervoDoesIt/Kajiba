---
phase: 11-experiment-logging-private-store
reviewed: 2026-06-04T02:44:48Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - src/kajiba/experiment_store.py
  - src/kajiba/cli.py
  - src/kajiba/__init__.py
  - tests/test_experiment_store.py
  - tests/test_cli_experiment.py
  - tests/test_experiment_exclusion.py
  - tests/fixtures/experiment_run.example.json
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-06-04T02:44:48Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Reviewed the phase-11 experiment-logging private store: the new
`experiment_store.py` write path, the `experiment` CLI group (`log`/`list`),
the package re-exports, the publish/submit exclusion guards, and the three
test files plus the fixture. The privacy backbone is sound: experiments live
in a separate `EXPERIMENTS_DIR`, the publish loop skips `model_experiment`
records on the raw dict before validation, the D-13 structural write guard
works, and the atomic temp-file-plus-`os.replace` write cleans up on
`BaseException`. All 12 phase-11 tests pass.

The defects are concentrated in the `log` command's input handling and the
dedup contract. The most serious is a **silent data-loss bug**: because the
experiment `record_id` is hashed only over experiment *identity* (not the
*outcome*), re-logging a corrected evaluation is silently dropped by dedup,
leaving the stale score on disk. Two further `log`-path bugs silently discard
user input or surface raw tracebacks. None of these breach the privacy
guarantees, but the dedup bug actively corrupts the experiment dataset the
milestone exists to build.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Dedup silently discards corrected experiment outcomes (data loss)

**File:** `src/kajiba/experiment_store.py:81-88`, `src/kajiba/schema.py:445-467`
**Issue:** `log_experiment` derives the on-disk filename and dedup key from
`record.compute_record_id()`, which for `ExperimentRecord` hashes **only**
experiment identity: `experiment_id`, `task_description`, `local_model_name`,
`local_model_output`, `started_at` (schema.py:454-464). It excludes every
outcome field (`eval_score`, `reviewer_critique`, `drift_flag`,
`lessons_learned`, `recommended_action`) and the `experiment_type` /
`task_category` fields. Consequently, re-logging the same run with a corrected
score takes the `if dest.exists():` early-return branch and **silently keeps
the old outcome** — only an `INFO` log is emitted ("Experiment already logged
(identical content)"), which is false: the content differs.

Verified empirically:
```
log run eval_score=0.10  -> exp_<id>.json (score 0.10)
log SAME run eval_score=0.90 -> same path returned, score on disk still 0.10
```
This is the inverse of the community pipeline's intent — a re-evaluation (the
normal workflow when fixing a bad eval) is the exact case that gets dropped.
The `--score`/`--type`/`--task-category` override flags (cli.py:873-878) are
also defeated on any re-log for the same reason.

**Fix:** Either (a) include the outcome payload in the experiment identity hash
so a changed outcome produces a new `record_id`, or (b) make `log_experiment`
overwrite-on-conflict instead of skip-on-conflict, or (c) detect a content
mismatch on the existing file and refuse with a clear error instead of a
misleading "identical content" notice. Option (a) preserves content-addressing:
```python
# schema.py compute_record_id() for ExperimentRecord — add outcome to payload
content = json.dumps(
    {
        "experiment_id": self.experiment.experiment_id,
        "task_description": self.experiment.task_description,
        "local_model_name": self.experiment.local_model.model_name,
        "local_model_output": self.outcome.local_model_output,
        "eval_score": self.outcome.eval_score,
        "reviewer_critique": self.outcome.reviewer_critique,
        "started_at": self.experiment.started_at.isoformat(),
    },
    sort_keys=True,
    ensure_ascii=True,
)
```
If skip-with-notice dedup is intentionally identity-only, then at minimum
`log_experiment` must compare the existing file's content to `payload` and warn
loudly (not "identical content") when they differ — otherwise corrected evals
are lost without any signal.

## Warnings

### WR-01: Partial scalar flags are silently discarded by the `log` dispatch

**File:** `src/kajiba/cli.py:888-907`
**Issue:** The scalar-convenience branch requires **all three** of `eval_score`,
`experiment_type`, and `task_category` to be non-`None`. If a user passes only
some (e.g. `kajiba experiment log --score 0.5`), the `elif` is false and control
falls into the interactive `else`, which **re-prompts for the eval score** and
silently ignores the `--score 0.5` already supplied. Verified: invoking with
`--score 0.5` and answering the eval-score prompt `0.99` writes `0.99` to disk;
the flag value is discarded with no warning.

**Fix:** In the interactive branch, seed prompt defaults from any flags already
provided, or detect "some-but-not-all scalar flags" and raise a `ClickException`
telling the user which flags are still required:
```python
provided = {"--score": eval_score, "--type": experiment_type,
            "--task-category": task_category}
if any(v is not None for v in provided.values()) and not all(...):
    missing = [k for k, v in provided.items() if v is None]
    raise click.ClickException(f"Provide all scalar flags or none; missing: {missing}")
```

### WR-02: `--from` experiment file missing `record_kind` raises an uncaught ValidationError

**File:** `src/kajiba/cli.py:883-886`, `src/kajiba/schema.py:532-535`
**Issue:** `load_record` routes by `record_kind`, defaulting absent values to
`coding_session` (schema.py:532). A `--from` file that is clearly an experiment
(has `experiment`/`outcome` blocks) but omits the `record_kind` discriminator is
sent to `KajibaRecord.model_validate`, which requires a `trajectory`
(schema.py:296) the experiment lacks. This raises a raw `pydantic.ValidationError`
that escapes the command — the `isinstance(rec, ExperimentRecord)` friendly-error
check at line 885 is never reached because validation explodes first. Verified:
exit code 1 with an unhandled `ValidationError`, not the intended
"--from file is not a model_experiment record." message.

**Fix:** Wrap the `load_record(data)` call in a `try/except ValidationError` and
convert to a `click.ClickException` with guidance, or pre-check the dict shape
before dispatch:
```python
try:
    rec = load_record(data)
except ValidationError as exc:
    raise click.ClickException(f"--from file failed validation: {exc}")
if not isinstance(rec, ExperimentRecord):
    raise click.ClickException("--from file is not a model_experiment record.")
```

### WR-03: Malformed `--from` / `--local-model` JSON surfaces a raw traceback

**File:** `src/kajiba/cli.py:864-870`
**Issue:** Both `json.loads(Path(model_json).read_text(...))` (line 866) and
`json.loads(Path(from_path).read_text(...))` (line 870) run with no error
handling. A non-JSON or truncated file raises `json.JSONDecodeError`, which
escapes the command as an unhandled traceback rather than a user-facing message.
`click.Path(exists=True)` validates existence but not content. The rest of this
codebase consistently catches load failures and emits friendly Rich messages
(e.g. `_load_latest_staging` cli.py:96-101, `experiment list` cli.py around the
`try/except Exception` per-file read).

**Fix:** Catch `json.JSONDecodeError` (or broad `Exception`) around each
`json.loads` and raise `click.ClickException(f"Invalid JSON in {path}: {exc}")`.

### WR-04: D-13 structural guard validates only the leaf directory name, not its location

**File:** `src/kajiba/experiment_store.py:71-76`
**Issue:** The privacy guard accepts any path whose resolved leaf name is
`experiments` (`resolved.name != "experiments"`). It does not verify the path is
under `KAJIBA_BASE`/`~/.hermes`. Any caller-supplied `/anywhere/experiments`
directory passes the check, so the docstring's claim that an experiment "can
never leak into the community `staging`/`outbox` namespaces" holds only against
the *names* `staging`/`outbox`, not against arbitrary misplacement. This is a
weaker guarantee than the surrounding documentation implies. (The CLI always
passes the real `EXPERIMENTS_DIR`, so this is latent, not currently exploited.)

**Fix:** If the intent is a hard privacy boundary, also assert the resolved path
is a descendant of the known base, e.g.:
```python
if resolved.name != "experiments" or KAJIBA_BASE.resolve() not in resolved.parents:
    raise ValueError(...)
```
Since the module is deliberately Click-free, pass the expected base in as an
argument rather than importing it. If name-only checking is intentional,
soften the docstring claim to match.

## Info

### IN-01: `build_experiment_record` `**extra` passthrough is silently lossy on typos

**File:** `src/kajiba/experiment_store.py:113-166`
**Issue:** `**extra` forwards arbitrary top-level fields to the `ExperimentRecord`
constructor. Pydantic's default `extra="ignore"` means a mistyped keyword (e.g.
`hardwre=...`) is silently dropped rather than rejected, so callers can believe
they attached hardware metadata that never lands. Not a correctness bug for the
documented fields, but an easy-to-miss footgun for the ELOG-02 programmatic
callers this module targets.
**Fix:** Document the accepted `**extra` keys explicitly, or set
`model_config = {"extra": "forbid"}` on `ExperimentRecord` so unknown fields
raise.

### IN-02: Acknowledged-dead submit guard reads a discriminator that is always `coding_session`

**File:** `src/kajiba/cli.py:487-494`
**Issue:** The submit guard checks `record.record_kind == "model_experiment"`,
but `record` comes from `_load_latest_staging()`, which validates via
`validate_record` → `KajibaRecord` (cli.py:98). A `KajibaRecord` always has
`record_kind == "coding_session"`, and an actual experiment dict placed in
staging would fail `KajibaRecord` validation and return `None` before this line.
The branch is therefore unreachable, as the comment candidly admits. It is
harmless defense-in-depth, but the `getattr(record, "record_kind", ...)` default
and the comment's "single guard against future paths" framing slightly overstate
its current value. Consider asserting on the raw staging dict (mirroring the
publish-loop guard) if a real backstop is wanted.
**Fix:** Optional. Either leave as documented dead code, or move the check to the
raw `data` dict inside `_load_latest_staging` before `validate_record` so it can
actually fire.

---

_Reviewed: 2026-06-04T02:44:48Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
