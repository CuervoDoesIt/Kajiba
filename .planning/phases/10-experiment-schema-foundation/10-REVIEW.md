---
phase: 10-experiment-schema-foundation
reviewed: 2026-06-03T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - src/kajiba/schema.py
  - tests/capture_golden_ids.py
  - tests/test_schema.py
  - tests/test_schema_backcompat.py
  - tests/test_schema_experiment.py
  - tests/fixtures/golden_ids.json
findings:
  critical: 0
  warning: 4
  info: 3
  total: 7
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-06-03
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Phase 10 extracts a shared `RecordBase`, adds a `record_kind` discriminator,
introduces the `ExperimentRecord` family, and adds a `load_record()` dispatch
factory. The hard back-compat constraint (ESCH-04: byte-identical
`record_id`/`submission_hash` for existing `KajibaRecord` fixtures) is **met** —
both `compute_record_id()` and `compute_submission_hash()` on `KajibaRecord` are
untouched and build their hash payload from explicit dicts (trajectory + model
+ outcome), so neither the new `record_kind` field nor the changed field
ordering perturbs the digest. All 45 tests pass, including the parametrized
golden-ID tripwire.

The refactor is sound in its core guarantee. However there are several
correctness and quality gaps in the new code: the `ExperimentRecord` hash is
not timezone-deterministic, there is no consistency validator binding a model
class to its `record_kind`, the two `ExperimentRecord` hash methods duplicate a
non-trivial payload block, and the field reordering introduced by inheritance
silently changes the on-disk JSON key order for every `KajibaRecord` (no hash
impact, but a serialization-shape change worth flagging).

No blockers. The back-compat tripwire holds and dispatch behaves correctly,
including loud failure on mis-tagged data.

## Warnings

### WR-01: ExperimentRecord hash is not timezone-deterministic

**File:** `src/kajiba/schema.py:460`, `src/kajiba/schema.py:485`
**Issue:** `compute_record_id()` and `compute_submission_hash()` both serialize
`self.experiment.started_at.isoformat()` directly into the hash payload.
`started_at` has no timezone normalization (the field is a bare `datetime` with
no validator), so the *same logical instant* produces *different* IDs depending
on the input representation. Verified empirically:

```
aware (2026-01-01T12:00+00:00) -> kajiba_exp_310b43181079
naive (2026-01-01T12:00)       -> kajiba_exp_289cdc432ad4
```

A `"...Z"` JSON value, a `"+00:00"` value, and a naive value for the same moment
all hash differently. Because these methods are the content-addressable
identity and the local-dedup key, two ingestions of the same experiment with
different timestamp formatting will not de-duplicate. Severity is bounded
(experiment records are local/private and brand-new, so no existing data is
affected), but the determinism claim in the docstrings ("same experiment
identity always produces the same ID") is not actually guaranteed.
**Fix:** Normalize `started_at` to UTC before hashing, e.g. via a
`field_validator` on `ExperimentMetadata.started_at` that coerces to aware-UTC,
or normalize at hash time:
```python
started = self.experiment.started_at
if started.tzinfo is None:
    started = started.replace(tzinfo=UTC)
started_iso = started.astimezone(UTC).isoformat()
```
Then use `started_iso` in both payloads.

### WR-02: No validator binds a record class to its record_kind

**File:** `src/kajiba/schema.py:278`, `src/kajiba/schema.py:286`, `src/kajiba/schema.py:440`
**Issue:** `record_kind` is the dispatch discriminator, but nothing prevents a
`KajibaRecord` from being constructed/validated with
`record_kind="model_experiment"` (or vice-versa). `KajibaRecord` inherits the
base default `"coding_session"` and `ExperimentRecord` overrides it to
`"model_experiment"`, but both fields are plain mutable `RecordKindType` with no
constraint. A `KajibaRecord` dict carrying `record_kind="model_experiment"`
validates successfully as a `KajibaRecord` (it only fails through `load_record`
because the experiment-specific fields are then missing — but direct
`validate_record()`/`KajibaRecord.model_validate()` calls bypass that route).
This produces a record whose self-declared kind contradicts its actual type,
which will mis-route on any future re-dispatch.
**Fix:** Add a `model_validator(mode="after")` to each subclass pinning the
discriminator, e.g. in `KajibaRecord`:
```python
@model_validator(mode="after")
def _check_record_kind(self) -> "KajibaRecord":
    if self.record_kind != "coding_session":
        raise ValueError(
            f"KajibaRecord.record_kind must be 'coding_session', "
            f"got {self.record_kind!r}"
        )
    return self
```
and the analogous check (`"model_experiment"`) on `ExperimentRecord`.

### WR-03: load_record round-trip not covered for ExperimentRecord

**File:** `tests/test_schema_experiment.py:53`, `tests/test_schema_backcompat.py:92`
**Issue:** `test_round_trip` dumps and reloads an `ExperimentRecord` via
`ExperimentRecord.model_validate(dumped)` directly, and `test_load_dispatch`
checks `load_record` only on a hand-built minimal dict. No test feeds a
*dumped* `ExperimentRecord` back through `load_record()`. Since `load_record`
is the public dispatch entry point and reads `record_kind` from the dumped
dict, a regression where the dumped payload omits/renames `record_kind` (e.g. a
future `exclude` change) would not be caught. The dispatch path is the riskiest
new surface and is under-tested for the experiment branch.
**Fix:** Add an assertion that a dumped `ExperimentRecord` re-dispatches:
```python
dumped = rec.model_dump(mode="json", by_alias=True)
assert isinstance(load_record(dumped), ExperimentRecord)
assert load_record(dumped) == rec
```

### WR-04: Duplicated hash-payload block in ExperimentRecord

**File:** `src/kajiba/schema.py:454-461`, `src/kajiba/schema.py:479-486`
**Issue:** `compute_record_id()` and `compute_submission_hash()` contain an
identical five-key payload dict (`experiment_id`, `task_description`,
`local_model_name`, `local_model_output`, `started_at`). The docstrings even
state they hash "the same experiment-identity payload." This is copy-paste
duplication of correctness-critical logic: a future edit to one payload (e.g.
the WR-01 timezone fix) must be made in two places, and missing one silently
desynchronizes the two identifiers. Note the KajibaRecord equivalents are
*intentionally* different payloads, so this duplication is specific to the
experiment family.
**Fix:** Extract a private helper that returns the canonical JSON string:
```python
def _identity_payload(self) -> str:
    return json.dumps(
        {
            "experiment_id": self.experiment.experiment_id,
            "task_description": self.experiment.task_description,
            "local_model_name": self.experiment.local_model.model_name,
            "local_model_output": self.outcome.local_model_output,
            "started_at": self.experiment.started_at.isoformat(),
        },
        sort_keys=True,
        ensure_ascii=True,
    )
```
and have both methods digest `self._identity_payload()`.

## Info

### IN-01: Inheritance reorders KajibaRecord JSON keys (no hash impact)

**File:** `src/kajiba/schema.py:265-300`
**Issue:** Moving the identity/runtime-context fields into `RecordBase` changes
the emitted key order of `model_dump(...)` for every `KajibaRecord`. Previously
`trajectory` preceded `model`/`hardware`/`submission`; now the base fields
(including `model`, `hardware`, `submission`) are emitted first, followed by
`record_type`, `trajectory`, `outcome`, `pain_points`, `quality`. The new
`record_kind` key is also added. Hashes are unaffected (they use explicit
payload dicts, confirmed by the passing golden tripwire), and consumers
(`scrubber.py`, `privacy.py`) read by key, not position. But any external tool
diffing staged/outbox JSON byte-for-byte, or a snapshot test on serialized
shape, will see churn. Worth a note in the phase summary.
**Fix:** No action required for correctness. If stable key order matters
downstream, document the change; the field grouping is reasonable as-is.

### IN-02: ExperimentRecord lacks record_type; CLI/history will show fallback

**File:** `src/kajiba/schema.py:432`
**Issue:** `ExperimentRecord` has no `record_type` field (correctly — it uses
`record_kind`/`experiment_type` instead). Existing consumers reference
`record.record_type` (`cli.py:249`) and `data.get("record_type", "—")`
(`cli.py:584`). Those files are out of Phase 10 scope and unchanged, but if an
`ExperimentRecord` ever reaches the outbox the history view will render "—" and
`cli.py:249` would `AttributeError` on a typed `ExperimentRecord`. Flagging the
forward coupling so a later phase wires CLI dispatch through `load_record`.
**Fix:** None in this phase. Track CLI `record_kind`-awareness as a follow-up
when experiment records become user-visible.

### IN-03: Unused controlled-vocabulary tuples

**File:** `src/kajiba/schema.py:111`, `src/kajiba/schema.py:114`, `src/kajiba/schema.py:117`
**Issue:** `RECORD_KINDS`, `EXPERIMENT_TYPES`, and `RECOMMENDED_ACTIONS` tuples
are defined alongside their `Literal` aliases per the project's dual-definition
convention, but unlike `OUTCOME_TAGS`/`PAIN_POINT_CATEGORIES` (which are checked
at runtime in `field_validator`s), these three tuples are never iterated or
referenced — validation is handled entirely by the `Literal` types. This is
consistent with the documented convention (tuples for "runtime iteration"), so
it is intentional scaffolding for future use, not dead code per se. Noting for
visibility; no change needed unless a `tests/` check asserts tuple/Literal
parity (recommended, mirroring `test_outcome_tags_tuple`).
**Fix:** Optionally add a parity test asserting each tuple matches its Literal
members, mirroring `TestControlledVocabulary.test_outcome_tags_tuple`, so the
two definitions cannot drift.

---

_Reviewed: 2026-06-03_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
