# Phase 4: Contribution Modes - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-01
**Phase:** 04-contribution-modes
**Areas discussed:** Review gate UX, Continuous mode trigger, Config management, Below-threshold handling

---

## Review gate UX

**Q: In ad-hoc mode, how should the user review and approve each captured record before it enters the outbox?**
Options: Preview-then-approve (Recommended) | Separate review command | Interactive queue | You decide
**Selected:** Preview-then-approve (Recommended)

**Q: Should the preview-then-approve flow happen automatically after session end, or require the user to run a command?**
Options: User runs kajiba review (Recommended) | Auto-prompt after session | You decide
**Selected:** User runs kajiba review (Recommended)

**Q: Should kajiba review process one record at a time or show all pending records as a batch?**
Options: One at a time (Recommended) | Batch list then drill-in | You decide
**Selected:** One at a time (Recommended)

## Continuous mode trigger

**Q: How should continuous mode auto-submit records?**
Options: Inline at session end (Recommended) | Background watcher | Post-capture hook | You decide
**Selected:** Inline at session end (Recommended)

**Q: Should continuous mode also auto-publish (push to GitHub) or just auto-submit to the local outbox?**
Options: Auto-submit to outbox only (Recommended) | Full auto-publish | You decide
**Selected:** Auto-submit to outbox only (Recommended)

## Config management

**Q: How should users set config values?**
Options: Subcommand: config set key value (Recommended) | Interactive wizard | Flag-based | You decide
**Selected:** Subcommand: config set key value (Recommended)

**Q: Should config changes take effect immediately (no restart), or require re-initialization?**
Options: Immediate, read from file each time (Recommended) | Require restart | You decide
**Selected:** Immediate, read from file each time (Recommended)

## Below-threshold handling

**Q: In continuous mode, what happens to records that score below the configured quality threshold?**
Options: Queue for manual review (Recommended) | Log and discard | Submit with flag | You decide
**Selected:** Queue for manual review (Recommended)

**Q: Should the user be notified when records are auto-submitted or below-threshold in continuous mode?**
Options: Silent with summary on next CLI use (Recommended) | Log file only | You decide
**Selected:** Silent with summary on next CLI use (Recommended)

---

## Claude's Discretion

- Rich formatting for the review command
- Summary notification format and placement
- Config validation and error messages
- Activity log format for continuous mode events

## Deferred Ideas

None — discussion stayed within phase scope.

---

*Discussion log for audit trail. Not consumed by downstream agents.*
