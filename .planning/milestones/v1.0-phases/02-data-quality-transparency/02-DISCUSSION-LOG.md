# Phase 2: Data Quality & Transparency - Discussion Log

**Date:** 2026-03-30
**Areas discussed:** Redaction diff display, Quality score storage, Rate & report commands, Annotation visibility

## Redaction diff display

**Q: How should kajiba preview show redacted content?**
Options: Inline highlighted | Side-by-side diff | Before/after sections | You decide
**Selected:** Inline highlighted

**Q: How should flagged items appear alongside redactions?**
Options: Yellow warnings below text | Inline with different color | Separate flagged section
**Selected:** Yellow warnings below text

**Q: Should the preview show a redaction summary?**
Options: Yes, summary table | Just inline highlights | Summary + detail toggle
**Selected:** Summary + detail toggle

## Quality score storage

**Q: Where should quality_tier and composite_score be stored?**
Options: Top-level fields on KajibaRecord | Nested quality object | Inside SubmissionMetadata
**Selected:** Nested quality object

**Q: Should the quality object also store individual sub-scores?**
Options: Yes, store all sub-scores | Just tier and composite | You decide
**Selected:** Yes, store all sub-scores

**Q: When should scoring happen?**
Options: Score at submit, show in preview | Score only at submit | Score at capture time
**Selected:** Score at submit, show in preview

## Rate & report commands

**Q: How should kajiba rate work?**
Options: Flags only | Interactive with defaults | Interactive only
**Selected:** Interactive with defaults

**Q: Should rate and report operate on latest staged or require selection?**
Options: Latest staged by default | Always require record ID | Interactive picker
**Selected:** Interactive picker

**Q: Should kajiba report use existing PainPoint schema or simplified?**
Options: Use existing PainPoint schema | Simplified freeform | Structured with category picker
**Selected:** Structured with category picker

## Annotation visibility

**Q: How should annotations appear alongside auto-scores in preview?**
Options: Merged quality panel | Separate sections | Auto-score with annotation badge
**Selected:** Merged quality panel

**Q: Should annotation status be visible in history list?**
Options: Show annotation indicator | Only show in detail view | You decide
**Selected:** Only show in detail view

---

*Discussion log for audit trail. Not consumed by downstream agents.*
