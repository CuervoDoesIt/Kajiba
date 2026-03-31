# Phase 2: Data Quality & Transparency - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Surface scrub transparency and quality signals to contributors. After this phase, `kajiba preview` shows inline-highlighted redactions with a summary/detail toggle, quality scores are persisted in the record at submit time, and contributors can annotate records with ratings and pain points via `kajiba rate` and `kajiba report`. No publishing or contribution modes — purely making the quality layer visible and interactive.

</domain>

<decisions>
## Implementation Decisions

### Redaction Diff Display
- **D-01:** Preview shows scrubbed text with redacted spans highlighted inline (e.g., `[REDACTED:email]` in red). Compact, single-pass through text. Not side-by-side or before/after.
- **D-02:** Flagged items (org domains from Phase 1) appear as yellow warning lines below the scrubbed text. Visually distinct from red redactions. Builds on Phase 1's existing partial implementation.
- **D-03:** Summary + detail toggle: `kajiba preview` shows a summary table by default (category | count), with a `--detail` flag to see full inline-highlighted text. Good for large records.

### Quality Score Storage
- **D-04:** Quality data stored in a new nested `QualityMetadata` Pydantic model on `KajibaRecord`. Field: `record.quality`. Contains `quality_tier`, `composite_score`, `sub_scores` dict (all 5 dimensions), and `scored_at` timestamp.
- **D-05:** All sub-scores (coherence, tool_validity, outcome_quality, information_density, metadata_completeness) are stored alongside the composite score. Enables consumers to filter by specific quality dimensions.
- **D-06:** Quality computed and stored at submit time. Preview also computes and displays the score (but doesn't persist until submit). User sees quality before committing.

### Rate & Report Commands
- **D-07:** `kajiba rate` uses interactive Rich prompts by default (score 1-5, optional tags). CLI flags (`--score`, `--tags`) override for non-interactive/scripting use.
- **D-08:** Both `kajiba rate` and `kajiba report` use an interactive picker to select which staged record to annotate (when multiple exist). No implicit "latest" default.
- **D-09:** `kajiba report` uses the existing `PainPoint` schema: interactive Rich picker for category (from `PAIN_POINT_CATEGORIES`), free-text description, severity selection. Structured but guided.

### Annotation Visibility
- **D-10:** Preview shows a merged quality panel: auto-score, sub-scores, AND user rating/tags/pain points together in one Rich panel. Single place to see everything about quality.
- **D-11:** `kajiba history` list shows tier and score only. Annotations visible when drilling into a specific record's detail view. Keeps the list clean.

### Claude's Discretion
- Rich formatting details (colors, padding, panel borders) for the redaction diff display
- Exact layout of the merged quality panel (table vs key-value pairs vs hybrid)
- Whether `--detail` flag applies to quality panel too or just redaction diff
- Tag vocabulary for `kajiba rate` — use existing `OUTCOME_TAGS` or define a separate quality-tag vocabulary

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Quality Scoring
- `src/kajiba/scorer.py` — Current 5-dimension scoring system with `QualityResult` dataclass. Extension point for persisting scores.
- `src/kajiba/schema.py` — `KajibaRecord` model where `QualityMetadata` nested model will be added. Also has `OutcomeSignals`, `PainPoint`, and controlled vocabularies.

### Scrubber (Phase 1 outputs)
- `src/kajiba/scrubber.py` — `ScrubResult` with `flagged` list, `FlaggedItem` dataclass, `scrub_record()` return. Source of redaction data for diff display.
- `src/kajiba/schema.py` lines 210-234 — `ScrubLog` model with `items_flagged` field.

### CLI
- `src/kajiba/cli.py` — `_render_preview()` function (extension point for redaction diff), `submit`/`export` commands (where quality scoring must be wired), `history`/`stats` commands (where stored scores replace recomputation).

### Privacy Pipeline (from Phase 1)
- `src/kajiba/privacy.py` — Privacy transformation functions. Quality scoring happens BEFORE privacy transforms in the pipeline (score the original, then scrub/anonymize).

### Spec
- `docs/kajiba-project-spec.md` — Quality scoring spec sections, annotation spec if present.

### Codebase Analysis
- `.planning/codebase/CONCERNS.md` — Gap analysis including quality and annotation gaps.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `QualityResult` dataclass in `scorer.py` — already has `composite_score`, `sub_scores`, `quality_tier`. Can derive `QualityMetadata` Pydantic model from this shape.
- `OUTCOME_TAGS` tuple and `OutcomeTagType` in `schema.py` — candidate tag vocabulary for `kajiba rate`.
- `PainPoint` Pydantic model in `schema.py` — already defines `category`, `description`, `severity` with controlled vocabularies. `kajiba report` maps directly to this.
- `PAIN_POINT_CATEGORIES` tuple in `schema.py` — category vocabulary for the interactive picker.
- Rich `Console`, `Table`, `Panel`, `Text` already imported in `cli.py` — all formatting primitives available.

### Established Patterns
- CLI commands use Click decorators with Rich console output. New commands (`rate`, `report`) follow same pattern.
- Scrubbing operates on deep copy via `model_dump(by_alias=True)` → mutate → `model_validate()`. Quality storage follows the same schema-first pattern.
- `_render_preview()` in `cli.py` is the central preview renderer — extend for inline highlights and summary table.
- Quality is currently computed on-the-fly in `submit` and `export` commands. Refactor to compute once and store.

### Integration Points
- `submit` command at `cli.py:224` — where quality scoring is computed. Add persistence to record before writing outbox.
- `_render_preview()` at `cli.py:85` — where redaction diff display is added.
- `history` command at `cli.py:333` — currently recomputes quality. Switch to reading stored `record.quality`.
- `stats` command at `cli.py:361` — same: switch to stored quality.
- `KajibaRecord` model — add `quality: Optional[QualityMetadata]` field.

</code_context>

<specifics>
## Specific Ideas

- STATE.md notes: "Phase 2 plan must confirm the diff surface uses the new mechanism, not the old ScrubResult shape" — the redaction diff MUST use `ScrubResult.flagged` and `ScrubResult.redactions` from Phase 1, not a parallel mechanism.
- Interactive picker for `rate`/`report` aligns with the project's contributor-trust philosophy — deliberate annotation over accidental.
- Summary + detail toggle follows the existing `kajiba` CLI pattern of sensible defaults with opt-in verbosity.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-data-quality-transparency*
*Context gathered: 2026-03-30*
