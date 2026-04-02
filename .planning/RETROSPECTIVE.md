# Retrospective: Kajiba

## Milestone: v1.0 — MVP

**Shipped:** 2026-04-02
**Phases:** 5 | **Plans:** 13 | **Tasks:** 19
**Timeline:** 3 days (2026-03-30 → 2026-04-02)
**Commits:** 98 | **LOC:** 10,478 Python | **Tests:** 356

### What Was Built

- Privacy pipeline: consent enforcement (4 levels), hardware anonymization (GPU family, RAM ceiling), timestamp jitter, IP/token/domain scrubbing
- Quality transparency: QualityMetadata persistence, redaction preview with inline highlighting, rate and report annotation commands
- Dataset publishing: PR-based workflow with sharded JSONL, catalog.json, README.md auto-generation, deletion via PR
- Contribution modes: ad-hoc review gate (approve/reject/skip/quit), continuous auto-submit with configurable quality threshold
- Consumer experience: catalog browse with model drill-down, filtered shard download with progress bar

### What Worked

- **TDD-first execution**: Writing failing tests before implementation caught design issues early and kept rework near zero
- **Wave-based parallelization**: Plans within a wave could execute concurrently, maximizing throughput
- **Privacy-first sequencing**: Building scrubbing/consent before publishing meant the publish flow was secure from day one
- **Shared abstractions across phases**: `filter_catalog()`, `_fetch_catalog()`, `_filter_options` decorator reused cleanly between browse and download
- **Pydantic v2 as single source of truth**: Schema changes propagated validation rules automatically, no manual sync needed

### What Was Inefficient

- **SUMMARY frontmatter gaps**: 12 of 26 requirements missing from `requirements_completed` in SUMMARY frontmatter — caught during milestone audit but could have been caught per-plan
- **Nyquist VALIDATION.md left as drafts**: All 5 phases created VALIDATION.md during planning but never completed them during execution — required a separate retroactive pass
- **Progress table in ROADMAP.md drifted**: Some phases showed "Planning complete" instead of actual completion status

### Patterns Established

- Privacy pipeline order: scrub → anonymize → jitter → consent strip (consistent across all 4 export paths)
- Config pattern: `VALID_CONFIG_KEYS` dict-of-dicts schema with type/choices/default for runtime validation
- GitHubOps wrapper pattern: mockable `GhResult` dataclass for all `gh` CLI interactions
- CLI test pattern: `monkeypatch.setattr("kajiba.cli.GitHubOps", ...)` with canned `GhResult` returns

### Key Lessons

- Complete VALIDATION.md during execution, not retroactively — saves a full audit pass
- Populate SUMMARY frontmatter `requirements_completed` exhaustively — the 3-source cross-reference catches gaps
- The `auto_submit_interval` config key was declared but unused — avoid declaring config before implementation needs it

### Cost Observations

- Sessions: ~10 across 3 days
- Notable: Phase 5 execution (2 plans, 2 waves) completed in ~14 minutes total agent time
- Nyquist validation of all 5 phases completed in ~12 minutes with parallel agents

---

## Cross-Milestone Trends

| Metric | v1.0 |
|--------|------|
| Phases | 5 |
| Plans | 13 |
| Tests | 356 |
| LOC | 10,478 |
| Days | 3 |
| Commits | 98 |
| Requirement coverage | 26/26 (100%) |
| Nyquist compliance | 5/5 phases |
