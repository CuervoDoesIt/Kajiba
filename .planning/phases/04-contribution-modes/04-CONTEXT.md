# Phase 4: Contribution Modes - Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Add ad-hoc (manual review) and continuous (auto-submit) contribution modes to the Kajiba pipeline. In ad-hoc mode, each captured record requires explicit user review and approval via a new `kajiba review` command before entering the outbox. In continuous mode, records meeting a configured quality threshold are auto-submitted to the local outbox at session end. Users switch modes and configure thresholds via an enhanced `kajiba config` command. After this phase, contributors control how their data flows from staging to outbox.

</domain>

<decisions>
## Implementation Decisions

### Review Gate (Ad-hoc Mode)
- **D-01:** Preview-then-approve flow. New `kajiba review` command shows each pending staged record with full preview (reuses existing preview infrastructure), then prompts approve/reject/skip.
- **D-02:** User-initiated review. Records land in staging silently after session end. User explicitly runs `kajiba review` when ready. Does not auto-prompt or block the agent session. Consistent with fault-tolerant collector pattern.
- **D-03:** One record at a time. `kajiba review` shows the most recent staged record, user decides, then moves to next. Focused attention per record rather than batch overview.

### Continuous Mode Trigger
- **D-04:** Inline at session end. `KajibaCollector.on_session_end` checks if mode is continuous, computes quality score, and if the record meets the threshold, calls the submit pipeline directly. No separate background process or daemon. Extends existing fault-tolerant collector pattern.
- **D-05:** Auto-submit to local outbox only. Continuous mode moves qualifying records from staging to outbox. Publishing to GitHub still requires explicit `kajiba publish`. Keeps network operations user-initiated (local-first principle).

### Config Management
- **D-06:** Subcommand pattern: `kajiba config set <key> <value>` and `kajiba config get <key>`. Existing `kajiba config` display becomes `kajiba config show`. Familiar CLI pattern (like `git config`).
- **D-07:** Immediate effect — config read from `~/.hermes/config.yaml` at each command invocation. Mode switch is just `kajiba config set contribution_mode continuous`; next session uses the new value. Consistent with existing `_load_config_value()` pattern.
- **D-08:** Configurable keys for this phase: `contribution_mode` (ad-hoc/continuous), `min_quality_tier` (gold/silver/bronze), `consent_level`, `auto_submit_interval` (reserved for future — not used in inline trigger but stored for potential background mode later).

### Below-Threshold Handling
- **D-09:** Queue for manual review. In continuous mode, records scoring below the configured threshold stay in staging. User can review them later via `kajiba review`. Nothing is lost, nothing is auto-discarded.
- **D-10:** Silent with summary on next CLI use. Auto-submit activity happens silently during sessions. Next time user runs any kajiba command, a brief summary appears: "2 records auto-submitted, 1 queued for review". Non-intrusive notification.

### Claude's Discretion
- Rich formatting for the review command (panel layout, approve/reject prompt style)
- Exact summary notification format and placement in CLI output
- Config validation (e.g., rejecting invalid tier names, showing available options)
- How `auto_submit_interval` config key is stored and documented (placeholder for future use)
- Activity log format for continuous mode events

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Implementation
- `src/kajiba/cli.py` — Current CLI commands including `config` (read-only display), `submit`, `preview`. Extension point for `review` command and `config set/get/show` subcommands. Contains `_load_config_value()` helper.
- `src/kajiba/collector.py` — `KajibaCollector` class with `on_session_end()` hook. Extension point for continuous mode auto-submit logic. Fault-tolerant pattern (all public methods wrapped in try/except).
- `src/kajiba/schema.py` — `KajibaRecord`, `QualityMetadata` (quality_tier field), `ConsentLevelType`, `SubmissionMetadata`.
- `src/kajiba/scorer.py` — `compute_quality_score()` returns `QualityResult` with `quality_tier` and `composite_score`.
- `src/kajiba/privacy.py` — `apply_consent_level()` for consent enforcement at submit time.

### Privacy (Phase 1 outputs)
- `.planning/phases/01-privacy-foundation/01-CONTEXT.md` — D-01: consent at both submit and publish. Submit pipeline MUST re-verify consent.

### Quality (Phase 2 outputs)
- `.planning/phases/02-data-quality-transparency/02-CONTEXT.md` — D-06: quality computed at submit time. Auto-submit must compute quality before threshold check.

### Publishing (Phase 3 outputs)
- `src/kajiba/publisher.py` — Publishing is separate from submission. Continuous mode does NOT auto-publish.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_load_config_value(key, default)` in `cli.py` — reads from `~/.hermes/config.yaml` under `kajiba` section. Reuse for reading contribution mode and threshold.
- `_render_preview()` in `cli.py` — Rich-based record preview. Reuse in `kajiba review` command.
- `_load_all_staging()` in `cli.py` — loads all staged records. Reuse for review queue.
- `compute_quality_score()` in `scorer.py` — quality tier computation. Reuse for threshold check in continuous mode.
- `apply_consent_level()` in `privacy.py` — consent enforcement. Reuse in submit pipeline called by both modes.

### Established Patterns
- Config defaults defined inline: `cli.py:641-645` defines `consent_level`, `auto_submit`, `llm_pii_scrub`, `scrub_strictness`.
- Click command group: all commands registered under `@cli.command()`.
- Rich Console for all output: `console = Console()` at module level.
- Fault-tolerant collector: `try/except Exception` wrapping with `logger.exception()`.
- Submit pipeline: scrub -> anonymize -> jitter -> consent-strip -> write to outbox.

### Integration Points
- New `review` command registers under existing Click group in `cli.py`.
- Continuous mode logic extends `KajibaCollector.on_session_end()` in `collector.py`.
- Config subcommands (`set`, `get`, `show`) restructure existing `config` command.
- Activity summary notification hooks into CLI command startup.

</code_context>

<specifics>
## Specific Ideas

- The collector's fault-tolerant pattern (never disrupt host agent) means continuous mode auto-submit must also be wrapped in try/except — a failed auto-submit should log but never crash the session.
- `auto_submit: False` already exists as a config default, confirming the project anticipated this feature.
- The review command's one-at-a-time flow mirrors the deliberate, trust-building approach of the project — contributors are never rushed into approving data.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 04-contribution-modes*
*Context gathered: 2026-04-01*
