# Phase 10: Experiment Schema Foundation - Context

**Gathered:** 2026-06-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the data-model foundation for Kajiba's dual-use direction: extract a shared `RecordBase` out of `KajibaRecord`, add a `record_kind` discriminator, and introduce the `ExperimentRecord` family (`ExperimentMetadata`, `ExperimentOutcome`) — while guaranteeing every existing coding-session record loads unchanged with byte-identical `record_id` and `submission_hash`. Pure schema/refactor work; no CLI, scorer, scrubber, store, or capture logic (those are Phases 11–15).

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**5 requirements are locked.** See `10-SPEC.md` for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read `10-SPEC.md` before planning or implementing. Requirements are not duplicated here.

**In scope (from SPEC.md):**
- `record_kind` discriminator on a shared base, defaulting to `coding_session`
- Extraction of a shared base model that both `KajibaRecord` and `ExperimentRecord` extend
- New `ExperimentMetadata`, `ExperimentOutcome`, and `ExperimentRecord` models with the locked field sets
- Controlled vocabularies (`tuple` + `Literal`) for `experiment_type` and `recommended_action`
- An optional `trajectory` field on `ExperimentRecord` — declared/reserved only, no population logic
- A separate experiment loader function; `validate_record()` remains `KajibaRecord`-only
- A golden-ID back-compat test over all existing fixtures/staged/outbox records
- JSON round-trip (serialize → validate) for `ExperimentRecord`

**Out of scope (from SPEC.md):**
- `kajiba experiment` CLI command group — Phase 11
- Programmatic logging entry point and the private store namespace — Phase 11
- Eval-specific scorer — Phase 12
- Scrub tuning for experiment records — Phase 12
- Reviewer-critique workflow, `lessons_learned` query interface, drift computation — Phase 13
- Live Hermes capture and any logic populating the optional `trajectory` — Phase 14
- Analysis/export formats and practice-project integration — Phase 15
- Modifying `ConversationTurn` (e.g. `reviewer_turn`) — explicitly excluded
- Any migration command or rewriting of existing on-disk records — runtime default only
- Multi-turn experiment conversation capture logic — field reserved, logic deferred

</spec_lock>

<decisions>
## Implementation Decisions

### Module Organization
- **D-01:** All new models — `RecordBase`, `ExperimentRecord`, `ExperimentMetadata`, `ExperimentOutcome` — live in the existing `src/kajiba/schema.py`. Keep `schema.py` as the single schema module per the CLAUDE.md convention ("schema.py = the record schema"). Do NOT create a separate experiment schema module.
- **D-02:** The shared base model is named **`RecordBase`**. Both records subclass it: `KajibaRecord(RecordBase)` and `ExperimentRecord(RecordBase)`.
- **D-03 (from SPEC R2):** `RecordBase` holds `schema_version`, `record_id`, `submission_hash`, `created_at`, `record_kind`, `model` (`ModelMetadata`), `hardware` (`HardwareProfile`), and `submission` (`SubmissionMetadata`, which wraps `scrub_log`). `record_type` and `quality` stay on `KajibaRecord` (record-specific). `ConversationTurn` is untouched.

### Experiment Record Identity
- **D-04:** `ExperimentRecord.compute_record_id()` hashes **experiment identity content** = `experiment_id` + `task_description` + `local_model.model_name` + `outcome.local_model_output` + `started_at`, using the same idiom as `KajibaRecord` (`json.dumps(..., sort_keys=True, ensure_ascii=True)` → SHA-256). Content-addressable: the same logged experiment yields the same id.
- **D-05:** Experiment record IDs use a **distinct prefix**: `kajiba_exp_<first 12 hex chars>`. Coding-session records keep `kajiba_<12hex>`. This makes the private/experiment namespace visually distinguishable at a glance.
- **D-06:** `ExperimentRecord.compute_submission_hash()` **is computed** (not left `None`), over the same experiment-identity content, format `sha256:<hex>`. Its purpose here is **local duplicate detection**, not community dedup (experiment records never publish, per ELOG-03).

### Schema Version
- **D-07:** Bump `SCHEMA_VERSION` from `0.1.0` → **`0.2.0`** (semver minor — additive and back-compatible). New records default to `0.2.0`; existing `0.1.0` files still validate via the `record_kind` default. Does NOT affect `record_id`/`submission_hash` (content hashes exclude `schema_version`), so ESCH-04 holds.
- **D-08:** A **single shared `SCHEMA_VERSION`** constant on `RecordBase` covers both kinds; they evolve together. No separate `EXPERIMENT_SCHEMA_VERSION`.

### Claude's Discretion
Left to researcher/planner — capture the cleanest approach, don't re-ask the user:
- **Dispatch wiring:** how `validate_record()` and the new experiment loader dispatch on `record_kind` (e.g. `Annotated[Union[...], Field(discriminator="record_kind")]`, a `RootModel`, or a manual factory branching on `record_kind`). Constraint: `validate_record()` stays `KajibaRecord`-only and unchanged for callers; the new loader's name (`validate_experiment` vs `load_record`) is open.
- **Back-compat test mechanics** (user opted not to discuss): how to capture/store the golden `record_id`/`submission_hash` baseline (committed golden JSON vs hardcoded test constants) and whether to cover only repo fixtures (`tests/fixtures/*.json`) or also scan real `HERMES_HOME` staging/outbox at runtime. Suggested default: commit a golden baseline generated from the pre-refactor schema over `tests/fixtures/*.json`; treat real staging/outbox as a runtime/manual check since they are not in the repo.
- Where the `compute_*` methods live (abstract on `RecordBase` vs per-subclass override) and exact field ordering.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Requirements (locked)
- `.planning/phases/10-experiment-schema-foundation/10-SPEC.md` — Locked requirements, boundaries, acceptance criteria — MUST read before planning

### Design Source & Rationale
- `docs/dual-use-roadmap.md` §4.1 — Candidate `ExperimentMetadata`/`ExperimentOutcome` field shapes (now locked in SPEC); §4.4 `record_kind` strategy; §6 open questions
- `.planning/seeds/v1.2-experiment-logging.md` — Converged dual-use decisions (shared base, shared-core/divergent-tail, private/no-publish)

### Existing Codebase
- `src/kajiba/schema.py` — The single schema module being refactored: `KajibaRecord` + nested models + `validate_record()`; `compute_record_id()` / `compute_submission_hash()` whose output must stay byte-identical
- `src/kajiba/cli.py` — 6 `validate_record()` call sites that must stay `KajibaRecord`-only
- `src/kajiba/privacy.py`, `src/kajiba/collector.py` — additional `validate_record()` / `KajibaRecord` consumers to keep unaffected
- `tests/fixtures/*.json` — existing records (gold/silver/minimal/pii/adversarial) for the ESCH-04 golden-ID baseline

### Project Spec
- `docs/kajiba-project-spec.md` — Full pipeline/schema design and controlled vocabularies

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Nested models in `schema.py` (`ModelMetadata`, `HardwareProfile`, `SubmissionMetadata`, `ScrubLog`, `Trajectory`) — reused by `RecordBase`/`ExperimentRecord`; `ModelMetadata` serves both `local_model` and `reviewer_model`.
- Dual `tuple` + `Literal` vocabulary pattern (`OUTCOME_TAGS`/`OutcomeTagType`) — the template for the new `experiment_type` and `recommended_action` vocabularies.
- The hashing idiom (`json.dumps(..., sort_keys=True, ensure_ascii=True)` → SHA-256, prefixed id) — reused for the experiment identity hash (D-04/D-06).

### Established Patterns
- `schema.py` is the single source of truth for the data model; `model_config = {"populate_by_name": True}`; `Optional[X]` typing (not `X | None`); `field_validator`/`model_validator`; Google-style docstrings; module-level `logger`.
- Back-compat constraint baked into the codebase: `ConversationTurn` stays untouched; existing files are never rewritten (runtime default only).

### Integration Points
- `validate_record()` in `schema.py` — the load entry point; stays `KajibaRecord`-only. The new experiment loader is added alongside it.
- Callers in `cli.py` (6 sites), `privacy.py`, `collector.py` — must remain unaffected by the refactor.

</code_context>

<specifics>
## Specific Ideas

- The `kajiba_exp_` prefix should make private experiment records visually distinguishable from community coding records at a glance.
- `RecordBase` composition is fixed by SPEC R2 (D-03 above): `model`, `hardware`, `submission` (wrapping `scrub_log`), `record_id`, `submission_hash`, `created_at`, `schema_version`, `record_kind` on the base; `record_type` and `quality` remain on `KajibaRecord`.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 10-experiment-schema-foundation*
*Context gathered: 2026-06-03*
