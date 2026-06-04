# Codebase Concerns

**Analysis Date:** 2026-03-30

## Tech Debt

**Unused `import copy` in scrubber module:**
- Issue: `import copy` at `src/kajiba/scrubber.py:7` is imported but never used. The module uses `model_dump()` and `model_validate()` for deep-copy behavior instead.
- Files: `src/kajiba/scrubber.py:7`
- Impact: Minor lint noise. No runtime effect.
- Fix approach: Remove the unused import.

**Duplicated `ScrubResult` class name across modules:**
- Issue: Both `src/kajiba/scrubber.py:112` and `src/kajiba/scrubber_llm.py:34` define a class named `ScrubResult` with different fields. The regex version has `redactions: list[Redaction]`, while the LLM version has `redactions: list[SemanticRedaction]`. When the LLM scrubber is implemented, these will collide in any module that imports both.
- Files: `src/kajiba/scrubber.py:112`, `src/kajiba/scrubber_llm.py:34`
- Impact: Name collision will cause import confusion or require aliasing when the LLM scrubber becomes real. The two-pass pipeline (spec Section 2.2) will need to combine results from both, which the differing shapes complicate.
- Fix approach: Rename to `RegexScrubResult` and `SemanticScrubResult`, or define a shared base class in `schema.py`. Create a unified `ScrubResult` that carries both regex and semantic redactions.

**Duplicated outcome-tag and pain-point-category definitions (tuple + Literal):**
- Issue: Each controlled vocabulary is defined twice: once as a tuple constant (`OUTCOME_TAGS`) and once as a `Literal` type (`OutcomeTagType`). Adding a new tag requires edits in both places, and they can drift.
- Files: `src/kajiba/schema.py:25-65` (OUTCOME_TAGS + OutcomeTagType), `src/kajiba/schema.py:67-95` (PAIN_POINT_CATEGORIES + PainPointCategoryType)
- Impact: Low risk today but will cause silent validation mismatches if only one is updated. The `field_validator` at `schema.py:194` checks against the tuple, but Pydantic's type narrowing uses the Literal.
- Fix approach: Derive one from the other. Use `typing.get_args(OutcomeTagType)` to produce the tuple, or define the tuple and use `Literal[*OUTCOME_TAGS]` (Python 3.12+). Since the project targets Python 3.11+, stick with deriving the tuple from the Literal: `OUTCOME_TAGS = typing.get_args(OutcomeTagType)`.

**`config` command imports PyYAML at runtime without declaring it as a dependency:**
- Issue: `src/kajiba/cli.py:360` does `import yaml` inside the `config()` command, but `pyyaml` is not listed in any dependency group in `pyproject.toml:25-41`. The code handles `ImportError` gracefully (line 366), but the SKILL.md and spec both reference `~/.hermes/config.yaml` as the primary configuration source. Users who install Kajiba cannot read their own config without manually installing PyYAML.
- Files: `src/kajiba/cli.py:349-368`, `pyproject.toml:25-41`
- Impact: The `kajiba config` command silently falls back to defaults even when a config file exists, with only a dim console message. Users may believe their config is active when it is not.
- Fix approach: Add `pyyaml` to a new optional dependency group `config` (or to the core dependencies since config reading is a basic function). At minimum, add it to the `all` extras.

**`psutil` used in hardware detection but not declared as dependency:**
- Issue: `src/kajiba/collector.py:92` imports `psutil` inside `_detect_hardware()` to read RAM. It is wrapped in a try/except ImportError with a Linux-only fallback. On macOS and Windows without `psutil`, RAM detection silently returns `None`.
- Files: `src/kajiba/collector.py:91-104`
- Impact: Hardware profiles will be incomplete on non-Linux systems unless the user has independently installed psutil. This affects quality scoring via `score_metadata_completeness`.
- Fix approach: Either add `psutil` as an optional dependency (e.g., `[hardware]` extra) or implement cross-platform fallbacks using `platform` and OS-specific commands (e.g., `wmic` on Windows, `sysctl` on macOS).

**Spec-mandated "generic 40-char hex token" pattern omitted from scrubber:**
- Issue: The spec at Section 2.2 Layer B lists `r"[a-zA-Z0-9]{40}"` (generic 40-char hex tokens with context) as an API key pattern. This was intentionally or accidentally omitted from the implementation at `src/kajiba/scrubber.py:40-51`. The spec notes "with context" suggesting it needs surrounding-text heuristics to avoid false positives.
- Files: `src/kajiba/scrubber.py:40-51`, `docs/kajiba-project-spec.md:277`
- Impact: Some generic hex tokens (e.g., Git commit hashes, older-format API keys) will not be scrubbed. This is a PII leak vector.
- Fix approach: Implement the pattern with contextual guards (e.g., preceded by `key=`, `token=`, `secret=`) to avoid false positives on SHA-1 hashes and similar.

**Spec-mandated "org domain" network pattern omitted from scrubber:**
- Issue: The spec lists `r"[a-zA-Z0-9-]+\.(?:company|org|io)\b"` as a network pattern for "potential org domains (flagged, not auto-redacted)". The implementation at `src/kajiba/scrubber.py:51-56` only includes `internal|local|corp|lan` patterns. The spec's flagging-not-redacting behavior is entirely unimplemented.
- Files: `src/kajiba/scrubber.py:51-56`, `docs/kajiba-project-spec.md:284`
- Impact: Organizational domain names that could identify a contributor's employer will pass through unscrubbed.
- Fix approach: Add the org domain pattern. Implement a "flagged for review" mechanism in `ScrubResult` that records potential matches without auto-redacting them, and surface these in the CLI preview.

## Missing Functionality

**LLM-based semantic PII scrubber is a complete stub:**
- Issue: `src/kajiba/scrubber_llm.py` is entirely unimplemented. The single function `scrub_semantic()` raises `NotImplementedError` at line 66. The `[llm-scrub]` optional dependency group at `pyproject.toml:33` is empty (no packages listed). This is documented in the ROADMAP as M2.2 but the spec and SKILL.md both reference it as a core feature.
- Files: `src/kajiba/scrubber_llm.py:41-72`, `pyproject.toml:33`
- Impact: The regex scrubber cannot catch semantic PII: personal names mentioned in conversation, company names, project names, or context-dependent identifying info. This is the primary gap in privacy protection. A trajectory like "Tell John at Acme Corp to deploy the Whisperforge project" will pass through with zero redactions.
- Fix approach: Implement using the local model via Ollama/llama.cpp API. Use the prompt template from spec Section 2.2 Layer C. Parse response for PII items with confidence levels. Auto-redact high-confidence, flag medium. Wire into `scrub_record()` as a second pass after regex.

**Metadata anonymization (Layer D) is entirely unimplemented:**
- Issue: The spec Section 2.2 Layer D defines four metadata anonymization steps: GPU name generalization (rare hardware), timestamp jitter (plus/minus 0-30 min), RAM/VRAM rounding to standard tiers, and OS version stripping. None of these are implemented anywhere in the codebase.
- Files: Nowhere -- not started. Spec: `docs/kajiba-project-spec.md:339-345`
- Impact: Hardware profiles combined with timestamps could fingerprint individual users even without explicit PII. A user with "NVIDIA A100 80GB SXM" + precise timestamp + specific RAM is potentially unique.
- Fix approach: Add an `anonymize_metadata()` function (new module or extend `scrubber.py`) that rounds VRAM/RAM to standard tiers, applies timestamp jitter, and generalizes rare GPU names. Call it in `scrub_record()` after PII scrubbing.

**Consent level is not enforced during record export:**
- Issue: The `consent_level` field exists in the schema at `src/kajiba/schema.py:232` and can be set in config, but no code actually enforces it. The spec Section 2.2 Layer E defines four levels that should strip different data (e.g., `anonymous` strips everything except trajectory, `metadata_only` strips the actual trajectory text). The `export_record()` at `src/kajiba/collector.py:321-344` and `submit` command at `src/kajiba/cli.py:191-225` export all fields regardless of consent level.
- Files: `src/kajiba/schema.py:232`, `src/kajiba/collector.py:321-344`, `src/kajiba/cli.py:191-225`
- Impact: Users who set `consent_level: anonymous` or `trajectory_only` will unknowingly have all their data exported, violating their privacy preference. This is a privacy breach.
- Fix approach: Add a `apply_consent_level(record, level)` function that strips fields based on the consent table in the spec. Call it in `export_record()` and the CLI `submit`/`export` commands before writing to disk.

**HuggingFace upload helper is not implemented:**
- Issue: The ROADMAP M1.6 mentions a `kajiba-upload` helper script using `huggingface_hub`. The `[upload]` dependency group at `pyproject.toml:32` declares `huggingface_hub>=0.19` but no upload command or function exists anywhere in the codebase.
- Files: `pyproject.toml:32`, `src/kajiba/cli.py` (no `upload` command)
- Impact: Users have no automated way to submit records to HuggingFace. The current workflow ends at writing a JSONL file to the local outbox.
- Fix approach: Add an `upload` CLI command that uses `huggingface_hub` to create dataset PRs against the target repository.

**`/rate` and `/report` slash commands are collector methods only -- no CLI surface:**
- Issue: The `KajibaCollector.on_rate()` and `on_report()` methods exist at `src/kajiba/collector.py:240-278`, and `register_hooks()` at `src/kajiba/hermes_integration.py:48-94` wires them to Hermes Agent events. But there is no standalone CLI command to rate or report on an existing staging record. Without a running Hermes Agent, these features are inaccessible.
- Files: `src/kajiba/collector.py:240-278`, `src/kajiba/cli.py` (no rate/report commands)
- Impact: Standalone users who manually create records cannot attach ratings or pain points through the CLI.
- Fix approach: Add `kajiba rate` and `kajiba report` CLI commands that load the latest staging record, attach the outcome/pain-point, and save back.

## Security Considerations

**IP address regex produces false positives on version numbers:**
- Risk: The IPv4 pattern at `src/kajiba/scrubber.py:52` (`\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b`) matches any four dot-separated numbers, including version strings like `3.11.0.0`, library versions in pip output, or CUDA version numbers. This can corrupt legitimate technical content in tool outputs.
- Files: `src/kajiba/scrubber.py:52`
- Current mitigation: None. The test suite at `tests/test_scrubber.py` does not test for version-number false positives.
- Recommendations: Add negative lookbehind/lookahead for common version contexts (e.g., `Python 3.11.x`, `version X.Y.Z.W`). At minimum, filter out RFC 5737 documentation ranges and known non-routable patterns. Add false-positive tests for version strings.

**Phone number regex is overly aggressive:**
- Risk: The phone pattern at `src/kajiba/scrubber.py:63-65` matches any sequence of 10 digits with optional separators. This will match numeric IDs, timestamps formatted with dashes, zip+4 codes, and other non-phone numeric sequences. For example, "Error code 555-123-4567" or "Ticket #5551234567" would be scrubbed.
- Files: `src/kajiba/scrubber.py:63-65`
- Current mitigation: None.
- Recommendations: Require a leading `+` or common phone prefixes. Add word boundary context. Add false-positive tests.

**Regex scrubber stores original PII text in `Redaction.original` field:**
- Risk: The `Redaction` dataclass at `src/kajiba/scrubber.py:101-108` stores the original matched text in the `original` field. The `ScrubResult` (line 112) carries a list of these. If `ScrubResult` objects are logged, serialized, or cached, the original PII is exposed.
- Files: `src/kajiba/scrubber.py:101-108`, `src/kajiba/scrubber.py:151-152`
- Current mitigation: The `Redaction` objects are created inside `scrub_text()` and returned in `ScrubResult`, but `scrub_record()` only uses `ScrubResult.stats` and the `scrubbed_text`. The `ScrubResult` with its `redactions` list is discarded at the call site in `scrub_record()` (line 179-181). However, nothing prevents a future caller from logging or persisting the redactions.
- Recommendations: Consider not storing the original text at all, or only storing a truncated/hashed version. Add a comment warning that `Redaction.original` contains sensitive data and must never be persisted or transmitted.

**No input validation on `tool_input`/`tool_output` size in schema:**
- Risk: The `ToolCall` model at `src/kajiba/schema.py:116-123` accepts arbitrary-length strings for `tool_input` and `tool_output`. While `collector.py:205` truncates to 2000 chars, the schema itself has no max-length constraint. Records created directly (not through the collector) could contain megabytes of tool output.
- Files: `src/kajiba/schema.py:116-123`, `src/kajiba/collector.py:205`
- Current mitigation: Truncation in collector only.
- Recommendations: Add `max_length` validators on `tool_input` and `tool_output` in the `ToolCall` model, or at least in `validate_record()`.

**CLI reads arbitrary filesystem paths without sandboxing:**
- Risk: `_load_latest_staging()` at `src/kajiba/cli.py:42-63` reads JSON files from `~/.hermes/kajiba/staging/`. If a malicious file is placed there (e.g., via symlink), it will be parsed by `json.loads()` and `model_validate()`. While JSON parsing is generally safe, Pydantic validation on untrusted input could trigger unexpected behavior.
- Files: `src/kajiba/cli.py:42-63`
- Current mitigation: Pydantic validation rejects non-conforming data. Errors are caught and logged.
- Recommendations: Add a maximum file size check before reading. Resolve symlinks and verify the file is within the expected directory.

## Performance Bottlenecks

**`scrub_text()` applies all regex patterns sequentially on the full text each time:**
- Problem: The `scrub_text()` function at `src/kajiba/scrubber.py:125-167` iterates through all pattern categories, and within each category applies each regex pattern independently via `pattern.finditer()` followed by `pattern.sub()`. For a long tool output with many matches, this is O(patterns * text_length).
- Files: `src/kajiba/scrubber.py:125-167`
- Cause: Each pattern scans the entire text independently. The `reversed(matches)` trick at line 150 is used for correct index tracking but then `pattern.sub()` at line 159 rescans the entire text again, making the match-then-sub redundant.
- Improvement path: Combine all patterns into a single pass using `re.Scanner` or a union regex `(pattern1|pattern2|...)`. Alternatively, collect all match spans, merge overlapping regions, and do a single text replacement pass.

**`history` and `stats` commands re-score every record on each invocation:**
- Problem: `src/kajiba/cli.py:257-287` and `src/kajiba/cli.py:290-335` call `compute_quality_score()` on every outbox record every time. For a user with hundreds of submitted records, this recomputes all five sub-scores per record on each `history` or `stats` invocation.
- Files: `src/kajiba/cli.py:280-282`, `src/kajiba/cli.py:304-306`
- Cause: Quality tier is not stored in the outbox record. It is always re-derived.
- Improvement path: Store the `quality_tier` and `composite_score` in the record's submission metadata at submit time. Read from the stored value in `history`/`stats`.

**Hardware detection runs `nvidia-smi` twice per session start:**
- Problem: `_detect_hardware()` at `src/kajiba/collector.py:59-86` calls `nvidia-smi` twice in separate `subprocess.run()` calls: once for GPU name/VRAM and once for driver version. Each call has a 10-second timeout.
- Files: `src/kajiba/collector.py:59-86`
- Cause: The two queries could be combined into a single `nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits` call.
- Improvement path: Combine into a single subprocess call. Cache the result if multiple sessions are created.

## Fragile Areas

**Regex pattern ordering in `scrub_text()` can cause cascade corruption:**
- Files: `src/kajiba/scrubber.py:145-159`
- Why fragile: Patterns are applied in dictionary insertion order (file_paths, api_keys, network, emails, phone, crypto, connection_strings). A placeholder inserted by an earlier pattern can be partially matched by a later pattern. For example, `[REDACTED_CONNSTR]` contains dots that could match the IP regex, and `[REDACTED_KEY]` could match the email regex if it contains `@`. The `reversed(matches)` at line 150 handles within-pattern overlap but not cross-pattern interference.
- Safe modification: When adding new patterns, test against all existing placeholder strings to ensure no cross-pattern matches. Consider using unique placeholder formats that cannot match any regex (e.g., `<<KAJIBA:PATH:1>>` with a counter).
- Test coverage: The test suite at `tests/test_scrubber.py` tests individual patterns and full record scrubbing but does not test cascade scenarios where one pattern's placeholder triggers another pattern.

**`KajibaCollector` lifecycle has no state machine enforcement:**
- Files: `src/kajiba/collector.py:144-344`
- Why fragile: Nothing prevents calling `on_turn_complete()` before `on_session_start()`, or calling `export_record()` twice on the same session. The collector will produce a record with `_model_metadata=None` and `_created_at=None` if `on_session_start()` was skipped. The `_build_record()` at line 281 gracefully handles None timestamps (falls back to `datetime.now(UTC)`) but this masks bugs.
- Safe modification: Add an enum state (`idle`, `active`, `ended`) and assert transitions. Log warnings on out-of-order calls.
- Test coverage: `tests/test_collector.py` tests the happy path and bad-data tolerance but does not test out-of-order lifecycle calls.

**CLI commands depend on hardcoded paths tied to Hermes Agent:**
- Files: `src/kajiba/cli.py:32-33`
- Why fragile: `KAJIBA_BASE = Path.home() / ".hermes" / "kajiba"` hardcodes the base directory. If Hermes Agent changes its config directory, or if a user wants to use Kajiba standalone without Hermes, the paths break. There is no environment variable override or CLI flag.
- Safe modification: Add a `--data-dir` global CLI option or check for a `KAJIBA_DATA_DIR` environment variable, falling back to the current default.
- Test coverage: CLI tests at `tests/test_cli.py` rely on the real `~/.hermes/kajiba/` directory. They do not mock or override the path, so tests create directories in the user's home. Tests pass because the commands handle empty directories gracefully, but this is a side effect.

## Scaling Limits

**Outbox is an unbounded directory of JSONL files:**
- Current capacity: Each `submit` writes a new `.jsonl` file to `~/.hermes/kajiba/outbox/`. The `history` and `stats` commands at `src/kajiba/cli.py:66-81` glob all `*.jsonl` files and read every single one into memory.
- Limit: With thousands of submissions, `_load_outbox_records()` will read all files sequentially, parse all JSON lines, and hold all records in memory. The `stats` command additionally validates and scores every record.
- Scaling path: Add an index file or SQLite database for outbox metadata. Implement pagination for `history`. Cache quality scores at submit time.

## Dependencies at Risk

**Minimum version pins are too loose for core dependencies:**
- Risk: `pyproject.toml:25-29` specifies `pydantic>=2.0`, `click>=8.0`, `rich>=13.0`. These allow installation of any version from 2.0+ onward. Pydantic 2.x has had breaking changes between minor versions (e.g., 2.0 vs 2.6 validator behavior). The code uses `model_validator(mode="after")` and `field_validator` which were stable, but future Pydantic 3.x could break these.
- Impact: Users installing fresh may get different behavior depending on which Pydantic 2.x version resolves.
- Migration plan: Add upper bounds or pin to tested ranges (e.g., `pydantic>=2.4,<3`). Add a lockfile or pin in CI.

**No lockfile present:**
- Risk: There is no `requirements.txt`, `poetry.lock`, `pdm.lock`, or `pip-compile` output. Development installs resolve to whatever versions are latest at install time.
- Impact: Non-reproducible builds. A dependency update could break CI or user installs without any codebase change.
- Migration plan: Add `pip-compile` (pip-tools) or adopt a lockfile-capable tool. Generate `requirements-dev.txt` from `pyproject.toml[dev]`.

## Test Coverage Gaps

**No tests for `hermes_integration.py`:**
- What's not tested: The `register_hooks()` function at `src/kajiba/hermes_integration.py:48-94` and the `HermesAgent` protocol at line 36 have zero test coverage. The module is 94 lines with event wiring, protocol checking, and error handling.
- Files: `src/kajiba/hermes_integration.py`
- Risk: The integration is the primary way Kajiba connects to its target platform. A regression in `register_hooks()` would silently break data collection for all Hermes Agent users.
- Priority: High. Create mock `HermesAgent` objects (both conforming and non-conforming) and verify that hooks are registered, events flow to the collector, and fallback to standalone mode works.

**CLI tests do not test actual data flow:**
- What's not tested: `tests/test_cli.py` (83 lines) only tests empty-state behavior: version, help, empty staging, empty outbox. No test creates a staging file, runs `preview`, or runs `submit` with data. No test verifies that `export` writes correct output.
- Files: `tests/test_cli.py`
- Risk: The entire CLI data path (load staging -> scrub -> score -> display -> write outbox) is untested. Regressions in preview rendering, submit flow, or export formatting will go undetected.
- Priority: High. Add tests that write fixture data to a temp staging directory (using `tmp_path` and monkeypatching `STAGING_DIR`/`OUTBOX_DIR`), then invoke commands and verify output.

**No tests for `scrub_text()` cascade/overlap scenarios:**
- What's not tested: What happens when a single text contains multiple PII types that overlap or when a placeholder inserted by one pattern matches another pattern. For example, a connection string `postgres://user@email.com:pass@host/db` contains both an email and a connection string.
- Files: `tests/test_scrubber.py`
- Risk: Cascade scrubbing could produce garbled output like `[REDACTED_CONNSTR]` where the email inside the connection string is separately matched, or double-redaction where `[REDACTED_EMAIL]` appears inside `[REDACTED_CONNSTR]`.
- Priority: Medium. Add tests with text containing overlapping PII types.

**No tests for `compute_record_id()` / `compute_submission_hash()` mutation:**
- What's not tested: Both `compute_record_id()` at `src/kajiba/schema.py:322-341` and `compute_submission_hash()` at `src/kajiba/schema.py:343-364` mutate `self.record_id` / `self.submission_hash` as a side effect AND return the value. Tests verify return values but do not verify that the instance is also mutated (or test what happens if called twice).
- Files: `tests/test_schema.py:196-234`, `src/kajiba/schema.py:322-364`
- Risk: Low. Current callers use the mutation. But the dual interface (mutate + return) is surprising and could lead to bugs if a caller assumes it is pure.
- Priority: Low.

**No negative/boundary tests for `score_coherence()` score clamping:**
- What's not tested: The coherence scorer at `src/kajiba/scorer.py:53-88` subtracts penalties that can accumulate beyond 1.0 total. The `max(0.0, score)` clamp at line 88 prevents negative values, but no test verifies behavior with adversarial inputs that would drive the raw score well below zero (e.g., 50 consecutive same-role turns).
- Files: `tests/test_scorer.py`
- Risk: Low. The clamp works correctly. But extreme inputs could reveal integer overflow or performance issues.
- Priority: Low.

## Spec vs Implementation Gaps Summary

| Spec Feature | Status | Location |
|---|---|---|
| Layer B: Regex PII scrubber | Implemented (missing 2 patterns) | `src/kajiba/scrubber.py` |
| Layer C: LLM semantic PII scrubber | Stub only | `src/kajiba/scrubber_llm.py` |
| Layer D: Metadata anonymization | Not started | Nowhere |
| Layer E: Consent level enforcement | Schema field exists, not enforced | `src/kajiba/schema.py:232` |
| Generic 40-char hex token pattern | Omitted | `src/kajiba/scrubber.py` |
| Org domain flagging (not redacting) | Omitted | `src/kajiba/scrubber.py` |
| HuggingFace upload command | Not implemented | `src/kajiba/cli.py` |
| `/rate` and `/report` as CLI commands | Not implemented (collector methods only) | `src/kajiba/collector.py` |
| `auto_submit` config option | Referenced in SKILL.md, not implemented | `src/kajiba/cli.py` |
| Quality tier stored in submission | Not stored | `src/kajiba/cli.py` |
| Edit-before-submit in preview | Not implemented | `src/kajiba/cli.py` |
| Pain point `turn_index` validation in scorer | Spec mentions it, not implemented | `src/kajiba/scorer.py:127-153` |
| Tool name vocabulary checking in scorer | Spec mentions "known Hermes toolset vocabulary", not implemented | `src/kajiba/scorer.py:91-124` |

---

*Concerns audit: 2026-03-30*
