---
phase: 12-eval-scoring-scrub-tuning
reviewed: 2026-06-04T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - src/kajiba/eval_scorer.py
  - src/kajiba/experiment_scrub.py
  - src/kajiba/cli.py
  - src/kajiba/__init__.py
  - tests/test_eval_scorer.py
  - tests/test_experiment_scrub.py
  - tests/test_cli_experiment.py
  - tests/fixtures/experiment_complete.json
  - tests/fixtures/experiment_thin.json
  - tests/fixtures/experiment_pii.json
findings:
  critical: 1
  warning: 5
  info: 4
  total: 10
status: issues_found
---

# Phase 12: Code Review Report

**Reviewed:** 2026-06-04
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Phase 12 adds an eval confidence scorer (`eval_scorer.py`), an experiment-aware
PII scrub (`experiment_scrub.py`), and CLI wiring (`experiment score`/`scrub`
subcommands, a Confidence column, and a path-traversal/isinstance guard in
`_load_experiment`). The locked scoring contract is implemented correctly — I
traced both the complete fixture (composite 1.0 → `complete`) and the thin
fixture (composite ≈ 0.367 → `thin`) by hand and they match the thresholds and
test assertions. The path-traversal guard and the non-experiment `isinstance`
rejection are sound.

The dominant concern is privacy leakage, which is the project's stated core
constraint ("maximum scrubbing by default — err on the side of over-redacting").
The experiment scrub allowlist omits two caller-supplied free-text surfaces and,
worse, the new `experiment scrub` command echoes/writes unredacted secrets that
the shared regex layer fails to catch. The store-raw invariant is documented but
not actually enforced for the `--out` path.

Note on scope: the shared scrubber's `sk-live-` regex gap is logged in
`deferred-items.md` and is out of scope per decision D-09. It is referenced below
only because Phase 12 introduced new surfaces that materialize the leak; the
regex fix itself remains deferred.

## Critical Issues

### CR-01: `experiment scrub` allowlist omits free-text `task_category` and `experiment_id`, leaking any PII placed there

**File:** `src/kajiba/experiment_scrub.py:68-82`
**Issue:** The allowlist routes exactly four fields through `scrub_text`:
`experiment.task_description`, `outcome.local_model_output`,
`outcome.reviewer_critique`, and `outcome.lessons_learned`. But the schema
(`schema.py:411,415`) defines `experiment.experiment_id: str` and
`experiment.task_category: str` as unconstrained free-text fields that are also
caller-supplied. The CLI `experiment log` flow lets the user type both
interactively (`cli.py:951,964` "Experiment ID", "Task category") and via
`--from`/`--task-category`. Neither is scrubbed, and neither is preserved-by-
design like model/hardware identity — they are arbitrary user strings.

For a privacy-first pipeline whose explicit stance is "err on the side of
over-redacting," an unscrubbed free-text surface that flows into the scrubbed
`--out` artifact (the share-boundary copy, `cli.py:1110-1117`) is a PII leak
path. A user who writes a path, email, or token into the experiment ID or task
category (e.g. `task_category="debug for jane.doe@example.com"`) ships it raw.

The module docstring even asserts "only ... are scrubbed" as if the surface set
were exhaustive; it is not.

**Fix:** Route the remaining caller-supplied free-text surfaces through `_apply`,
or, if `experiment_id` must stay byte-stable for the content-addressable
`record_id` (`schema.py:454-467`), at minimum scrub `task_category` and add an
explicit, tested decision documenting why `experiment_id` is exempt:
```python
experiment["task_category"] = _apply(experiment["task_category"])
# experiment_id is part of the record_id hash payload — if it must survive
# byte-identical, validate it against a strict id charset at log time so PII
# can never enter it, and document the exemption.
```

## Warnings

### WR-01: `experiment scrub` preview Panel echoes unredacted secrets to stdout

**File:** `src/kajiba/cli.py:1143-1149`
**Issue:** The preview path prints `scrubbed.experiment.task_description` and
`scrubbed.outcome.local_model_output` in a Rich Panel. The PII fixture's
`task_description` (`experiment_pii.json:18`) contains
`sk-live-AbCdEf1234567890XyZqrStUvWx`, which the shared `api_keys` regex
(`scrubber.py:71`, `sk-[a-zA-Z0-9]{32,}`) does not match because of the internal
hyphen. The result: `kajiba experiment scrub <id>` prints a live-looking API key
to the terminal under a banner that claims the text is scrubbed ("Scrubbed free
text"). The test `test_experiment_scrub` only asserts the *email* is gone
(`test_cli_experiment.py:161`), so this passes while the key leaks.

The root-cause regex gap is correctly deferred (D-09, `deferred-items.md`). The
warning here is about the *new Phase 12 surface*: a command that confidently
labels output as scrubbed while emitting a secret the engine missed. Even with
the regex deferred, the new code amplifies the exposure.

**Fix:** Either (a) gate the preview behind an explicit `--show-text` flag and
default to counts-only, or (b) tighten the deferred regex before shipping the
preview surface. At minimum, soften the Panel title so it does not assert
completeness it cannot guarantee, and add a regression test that asserts the
`sk-live-` token is absent from preview output (which will fail until the regex
is widened, making the gap visible).

### WR-02: Store-raw invariant is documented but not enforced for `--out`

**File:** `src/kajiba/cli.py:1110-1117`
**Issue:** Both the command docstring (`cli.py:1099-1100`) and the module
docstring (`experiment_scrub.py:20-21`) promise the raw `exp_<id>.json` is
"NEVER" overwritten. But `--out` is a free `click.Path()` with no validation
(`cli.py:1086-1091`), and the write is an unconditional `out_path.write_text(...)`.
Nothing stops a user from running
`kajiba experiment scrub <id> --out ~/.hermes/kajiba/experiments/exp_<id>.json`,
which silently clobbers the raw store with the scrubbed copy — destroying the
store-raw invariant the phase is built around (D-08). The test suite only checks
the invariant for paths *outside* the store (`test_cli_experiment.py:170-190`),
so this is uncovered.

**Fix:** Resolve `out_path` and reject any destination inside `EXPERIMENTS_DIR`,
mirroring the `_load_experiment` traversal guard:
```python
out_path = Path(out).resolve()
if out_path.parent == EXPERIMENTS_DIR.resolve():
    raise click.ClickException(
        "Refusing to write a scrubbed copy into the raw experiment store."
    )
```

### WR-03: Flagged items (org domains) are counted but never surfaced in the experiment scrub path

**File:** `src/kajiba/experiment_scrub.py:59-66`; `src/kajiba/cli.py:1128-1149`
**Issue:** `_apply` folds `len(result.flagged)` into `items_flagged`, but the
flagged items themselves (org-domain candidates that pass through un-redacted,
per `scrubber.py:201-221`) are discarded. The community pipeline's
`_render_preview` (`cli.py:384-398`) explicitly lists each flagged item with its
reason and warns "Flagged items will pass through if you submit." The experiment
scrub preview shows only a numeric `items_flagged` count with no indication of
*what* will leak. For a privacy-sensitive share boundary, a non-zero
`items_flagged` that the user cannot inspect undermines informed consent and the
over-redaction stance.

**Fix:** Collect the `FlaggedItem` objects (not just the count) in
`scrub_experiment` and return/render them, or have the CLI re-run
`flag_org_domains` on the scrubbed free-text fields and list them as the
community preview does.

### WR-04: `experiment list` recomputes the band and silently shows blank on failure, masking corrupt records

**File:** `src/kajiba/cli.py:1015-1039`
**Issue:** The loop reads each file twice — once raw via `json.loads`
(line 1017) and again via `load_record` for the band (line 1028). When
`load_record`/`compute_eval_confidence` raises, the exception is logged and
`band` stays `""` (line 1026,1031-1032), so the row renders with an empty
Confidence cell that is indistinguishable from a legitimately-empty band. A
malformed or non-experiment file in the store therefore appears as a normal row
with a blank confidence, rather than being flagged as an error. Compare with
`history`/`stats` which surface a `?`/`error` marker (`cli.py:662,710`).

**Fix:** Render a distinct error sentinel on failure so a broken record is
visible:
```python
band = ""
try:
    rec = load_record(data)
    band = compute_eval_confidence(rec).confidence_band if isinstance(rec, ExperimentRecord) else "n/a"
except Exception as exc:
    logger.error("Failed to score experiment file %s: %s", f, exc)
    band = "error"
```

### WR-05: `_load_experiment` accepts a `record_id` that bypasses the `exp_` naming contract

**File:** `src/kajiba/cli.py:106-110`
**Issue:** The path is built as `EXPERIMENTS_DIR / f"exp_{record_id}.json"`. The
traversal guard correctly blocks separators/`..`. But a `record_id` containing a
leading dot or other filename metacharacters that resolve within the directory
(e.g. ids that collapse to a sibling `exp_*.json` written by another tool) are
accepted as long as the parent resolves to the store. More practically, callers
pass the *bare* id and the stored files are named `exp_kajiba_exp_<hex>.json`
(double prefix, since `record_id` is `kajiba_exp_<hex>` per
`schema.py:466`). The seeding helper in the tests reads `record_id` from disk and
passes it back, so the double-`exp_` round-trips, but any human invoking
`experiment score <id>` by copying the displayed `record_id` works only because
of this exact double-prefix coincidence. It is fragile and undocumented.

**Fix:** Validate `record_id` against an explicit charset before path
construction (`re.fullmatch(r"[A-Za-z0-9_]+", record_id)`) and document the
double-`exp_` filename convention, or normalize so the on-disk name and the
displayed id use one consistent prefix.

## Info

### IN-01: `experiment scrub --out` write drops `ensure_ascii=False`

**File:** `src/kajiba/cli.py:1115`
**Issue:** Every other JSON write in the codebase uses
`json.dumps(..., ensure_ascii=False)` (`cli.py:242,467,622`,
`scrubber` round-trips), but the scrubbed `--out` write omits it, so non-ASCII
characters in scrubbed free text are escaped to `\uXXXX`. Harmless but
inconsistent with the established convention.
**Fix:** Add `ensure_ascii=False` to match the rest of the codebase.

### IN-02: `experiment_pii.json` fixture carries a live-shaped API key with no test asserting its redaction

**File:** `tests/fixtures/experiment_pii.json:18`
**Issue:** The fixture embeds `sk-live-AbCdEf1234567890XyZqrStUvWx`, but no test
asserts it is redacted (the scrub tests check only email/path). This silently
encodes the deferred regex gap as accepted behavior with no failing guardrail to
track it.
**Fix:** Add an `xfail`-marked test asserting the key is redacted, linked to the
deferred item, so the gap is tracked and flips to passing when the regex is
widened.

### IN-03: Double JSON parse per file in `experiment list`

**File:** `src/kajiba/cli.py:1017,1028`
**Issue:** Each file is `json.loads`-ed once for table cells and again inside
`load_record(data)` reuses the same dict — actually `load_record` reuses `data`,
so this is fine — but `experiment_meta`/`outcome` are pulled from the raw dict
while the band comes from the validated record, creating two parallel views of
the same record that can drift if the schema adds coercion. Prefer reading
display fields from the validated `rec` once it exists.
**Fix:** Read `experiment_type`/`task_category`/`eval_score` from the validated
`rec` when available, falling back to the raw dict only on validation failure.

### IN-04: `__init__.py` import ordering is not alphabetized / grouped

**File:** `src/kajiba/__init__.py:5-7`
**Issue:** The three new eager imports (`experiment_store`, `eval_scorer`,
`experiment_scrub`) are added after `__version__` in non-alphabetical order.
Eager package-level imports also mean importing `kajiba` now pulls the full
scrub/score stack even for callers that only need `__version__`. Minor; flagged
for consistency with the project's "from X import Y, grouped" convention.
**Fix:** Group/sort the imports, or defer them to module access if import cost
matters.

---

_Reviewed: 2026-06-04_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
