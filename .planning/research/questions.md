# Research Questions

Open questions captured during exploration that need deeper investigation before
or during planning. Resolve in the relevant phase's spec/discuss/research step.

---

## Q1 — Migrating existing records to a discriminated-union shared base

**Raised:** 2026-06-03 (`/gsd-explore` dual-use direction)
**Blocks:** v1.2 Phase P-A (Schema & core types)
**Related:** `.planning/seeds/v1.2-experiment-logging.md`, `src/kajiba/schema.py`

The v1.2 schema decision extracts a common base out of `KajibaRecord` and turns
the record layer into a discriminated union keyed on a new `record_kind` field
(`"coding_session"` | `"model_experiment"`). Existing staged/outbox records on
disk were written *without* `record_kind` and against the current flat
`KajibaRecord` shape.

**Question:** What is the safest migration path so existing staged/outbox
`KajibaRecord` JSON keeps loading after the refactor?

Sub-questions to resolve:
- Default `record_kind` to `"coding_session"` when absent on load (back-compat
  via a field default + `populate_by_name`), or run a one-time migration script
  over `staging/` and `outbox/`?
- Does Pydantic v2 discriminated-union validation tolerate a missing
  discriminator with a default, or must every record carry it explicitly?
- Does `compute_record_id()` / `compute_submission_hash()` change if a base
  refactor reorders or renames fields? (Content-hash stability — must not
  silently change IDs of already-published records.)
- Where does the discriminator live — on the base model, or only on the
  serialized form via alias?

**Why it matters:** getting this wrong either breaks existing local records or
silently changes content-addressable IDs of already-published data.
