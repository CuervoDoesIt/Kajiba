# Phase 3: Dataset Publishing - Discussion Log

**Date:** 2026-03-31
**Areas discussed:** PR workflow mechanics, Repository structure, Catalog & dataset card, Deletion mechanism

## PR workflow mechanics

**Q: How should kajiba publish get records into the dataset repository?**
Options: Fork + PR (Recommended) | Branch + PR on same repo | Local staging only
**Selected:** Fork + PR (Recommended)

**Q: What should kajiba publish require for GitHub authentication?**
Options: gh CLI (Recommended) | GitHub token in config | Either works
**Selected:** gh CLI (Recommended)

**Q: Should kajiba publish verify consent enforcement before pushing?**
Options: Re-verify at publish time | Trust outbox | Verify + stamp
**Selected:** Re-verify at publish time

## Repository structure

**Q: How should JSONL files be sharded?**
Options: Append to single file | Date-based shards | Size-based shards | You decide
**Selected:** You decide

**Q: How should model names be normalized?**
Options: Lowercase + hyphens | Slugified from model_name | You decide
**Selected:** Lowercase + hyphens

## Catalog & dataset card

**Q: What metadata should catalog.json contain?**
Options: Essential only | Rich metadata | You decide
**Selected:** Rich metadata

**Q: How should the dataset README.md be generated?**
Options: Template + dynamic stats | Fully dynamic | You decide
**Selected:** Template + dynamic stats

## Deletion mechanism

**Q: How should kajiba delete work?**
Options: Deletion index file (Recommended) | Physical removal | Tombstone in record
**Selected:** Deletion index file (Recommended)

**Q: Should delete require own records or allow any ID?**
Options: Any record by ID | Only own records | You decide
**Selected:** You decide

---

*Discussion log for audit trail. Not consumed by downstream agents.*
