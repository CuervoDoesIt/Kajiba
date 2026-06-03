# Phase 10: Experiment Schema Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-03
**Phase:** 10-experiment-schema-foundation
**Areas discussed:** Module organization, Experiment record identity, Schema version policy

> Requirements were locked beforehand by `10-SPEC.md` (5 requirements). This discussion covered implementation decisions only. The "Back-compat test mechanics" gray area was offered but not selected — left to researcher/planner discretion.

---

## Module Organization

**Where should the shared base + ExperimentRecord/Metadata/Outcome models live?**

| Option | Description | Selected |
|--------|-------------|----------|
| All in schema.py | Base + experiment models added to existing schema.py; matches the single-schema-module convention | ✓ |
| New experiment_schema.py | Base+KajibaRecord in schema.py; experiments in a new module ('divergent tail') | |
| Base + experiment split out | Extract base to its own module, experiments to another; maximum separation/churn | |

**What should the shared base model be named?**

| Option | Description | Selected |
|--------|-------------|----------|
| RecordBase | Matches the SPEC candidate; 'the base for records' | ✓ |
| BaseRecord | Same meaning, base-first ordering | |
| KajibaRecordBase | Project-branded but verbose | |

**User's choice:** All in schema.py; base named `RecordBase`.
**Notes:** Keeps schema.py as the single source of truth per CLAUDE.md.

---

## Experiment Record Identity

**What content seeds an ExperimentRecord's deterministic record_id?**

| Option | Description | Selected |
|--------|-------------|----------|
| Experiment content hash | Hash over experiment_id + task_description + local_model name + local_model_output + started_at | ✓ |
| experiment_id-based | Derive directly from the caller-supplied experiment_id | |
| Full payload hash | Hash the entire experiment+outcome dump (brittle) | |

**ID prefix to distinguish kinds?**

| Option | Description | Selected |
|--------|-------------|----------|
| Distinct: kajiba_exp_ | Experiment ids read kajiba_exp_<hex>, distinct from coding kajiba_<hex> | ✓ |
| Same kajiba_ prefix | Uniform prefix; rely on record_kind field | |

**How should ExperimentRecord handle submission_hash (a community-dedup key)?**

| Option | Description | Selected |
|--------|-------------|----------|
| Compute for local dedup | Compute over experiment identity content for local duplicate detection | ✓ |
| Leave it None | Community-publish concept doesn't apply to private experiments | |

**User's choice:** Content hash of experiment identity fields; `kajiba_exp_` prefix; submission_hash computed for local dedup.
**Notes:** Mirrors KajibaRecord's content-addressable hashing idiom. Experiments are private (ELOG-03) so submission_hash serves local dedup, not community dedup.

---

## Schema Version Policy

**How should SCHEMA_VERSION be handled?**

| Option | Description | Selected |
|--------|-------------|----------|
| Bump to 0.2.0 (minor) | Additive, back-compatible evolution per semver | ✓ |
| Keep 0.1.0 | No version change | |
| Bump to 1.0.0 (major) | Declare stable; overstates the change | |

**Share one schema version or separate constants?**

| Option | Description | Selected |
|--------|-------------|----------|
| Single shared SCHEMA_VERSION | One constant on the base; kinds evolve together | ✓ |
| Separate constants | SCHEMA_VERSION + EXPERIMENT_SCHEMA_VERSION versioned independently | |

**User's choice:** Bump to `0.2.0`; single shared `SCHEMA_VERSION` on `RecordBase`.
**Notes:** Content hashes exclude schema_version, so the bump doesn't affect existing record IDs (ESCH-04 holds).

---

## Claude's Discretion

- Discriminated-union / dispatch wiring approach (`validate_record()` stays KajibaRecord-only; experiment loader name + union mechanism open).
- Back-compat test mechanics (golden file vs constants; repo fixtures vs real staging/outbox) — offered but not selected for discussion.
- Placement of `compute_*` methods (abstract on base vs per-subclass) and field ordering.

## Deferred Ideas

None — discussion stayed within phase scope.
