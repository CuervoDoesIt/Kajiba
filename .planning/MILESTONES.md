# Milestones

## v1.0 MVP (Shipped: 2026-04-02)

**Phases completed:** 5 phases, 13 plans, 19 tasks

**Key accomplishments:**

- Context-aware IP regex eliminating version-string false positives, hex token scrubbing with keyword context, and org domain flagging with safe-domain allowlist
- Three pure privacy functions: consent-level field stripping for 4 levels, hardware anonymization with GPU family/RAM ceiling-rounding, and deterministic timestamp jitter
- Full privacy pipeline (scrub -> anonymize -> jitter -> consent strip) wired into collector.export_record() and all CLI commands with flagged org domain warnings in preview
- QualityMetadata Pydantic model with 5 sub-scores stored at submit/export time, read back in history/stats with backward-compatible fallback
- CLI rate and report commands with interactive picker and merged quality panel for contributor annotations
- Publisher module with SHA-256 sharded JSONL layout, catalog indexing, README generation, deletion tracking, and GitHubOps gh/git CLI wrapper
- `kajiba publish` and `kajiba delete` CLI commands wiring publisher.py into Click with full D-04 workflow, consent re-verification, dry-run mode, and deletion-via-PR
- Shared config module with VALID_CONFIG_KEYS schema, tier comparison, activity logging, and restructured CLI config group with set/get/show subcommands
- Ad-hoc review command with one-at-a-time approve/reject/skip/quit flow, safe staging deletion, and activity notification banner in CLI group callback
- Extended collector on_session_end with continuous mode quality-gated auto-submit to outbox, staging fallback for below-threshold records, and activity logging
- Catalog enriched with model metadata (parameter_counts, quantizations, context_windows), GitHubOps.get_file_contents for remote file access, and filter_catalog with case-insensitive model + exact tier AND composition
- Rich-powered browse command with summary table and model drill-down, plus download command with progress bar, confirmation prompt, and skip-existing shard logic

---
