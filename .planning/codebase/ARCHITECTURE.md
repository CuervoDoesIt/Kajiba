# Architecture

**Analysis Date:** 2026-03-30

## Pattern Overview

**Overall:** Pipeline architecture with a linear data flow: Capture -> Scrub -> Score -> Export

**Key Characteristics:**
- Single-pass data pipeline operating on one record (session) at a time
- Plugin-based integration with Hermes Agent via event hooks (observer pattern)
- Fault-tolerant collector that swallows all exceptions to avoid disrupting the host agent
- Pydantic v2 models as the single source of truth for data validation and serialization
- Local-first design: all processing happens on the user's machine, no network calls required
- CLI as the primary user interface via Click, with Rich for terminal rendering

## Layers

**Schema Layer (data contracts):**
- Purpose: Define the complete data model with validation rules, controlled vocabularies, and serialization methods
- Location: `src/kajiba/schema.py`
- Contains: All Pydantic models (`KajibaRecord`, `Trajectory`, `ConversationTurn`, `ToolCall`, `ModelMetadata`, `HardwareProfile`, `OutcomeSignals`, `PainPoint`, `ScrubLog`, `SubmissionMetadata`), Literal type aliases for controlled vocabularies, `validate_record()` public API
- Depends on: `pydantic`, `hashlib`, `json`
- Used by: Every other module in the package

**Collection Layer (data capture):**
- Purpose: Hook into Hermes Agent session lifecycle and capture turns, tool calls, model metadata, and hardware info
- Location: `src/kajiba/collector.py`
- Contains: `KajibaCollector` class with event handlers (`on_session_start`, `on_turn_complete`, `on_session_end`, `on_rate`, `on_report`), hardware detection (`_detect_hardware()`), model metadata extraction (`_extract_model_metadata()`)
- Depends on: `schema`, `scorer`, `scrubber`, `platform`, `subprocess`, `psutil` (optional)
- Used by: `hermes_integration`, CLI (indirectly)

**Integration Layer (Hermes Agent adapter):**
- Purpose: Thin adapter that wires `KajibaCollector` lifecycle hooks into Hermes Agent's event system
- Location: `src/kajiba/hermes_integration.py`
- Contains: `HermesAgent` Protocol class, `register_hooks(agent)` function
- Depends on: `collector`
- Used by: Hermes Agent (external)

**Scrubbing Layer (PII removal):**
- Purpose: Remove personally identifiable information from records before export/submission
- Location: `src/kajiba/scrubber.py` (regex-based, Layer B), `src/kajiba/scrubber_llm.py` (LLM-based, Layer C -- stub)
- Contains: Regex pattern categories, `scrub_text()` for individual strings, `scrub_record()` for full records, `ScrubResult` and `Redaction` dataclasses
- Depends on: `schema` (for `KajibaRecord`, `ScrubLog`)
- Used by: `collector` (via `export_record()`), `cli` (via `preview`/`submit`/`export` commands)

**Scoring Layer (quality assessment):**
- Purpose: Compute a composite quality score from five weighted sub-scores and assign a quality tier
- Location: `src/kajiba/scorer.py`
- Contains: Five sub-score functions, `compute_quality_score()`, `QualityResult` dataclass, threshold constants
- Depends on: `schema` (for `KajibaRecord`)
- Used by: `collector` (not directly, but the result is consumed by CLI), `cli`

**CLI Layer (user interface):**
- Purpose: Provide command-line interface for previewing, submitting, exporting, and managing records
- Location: `src/kajiba/cli.py`
- Contains: Click command group with 6 commands (`preview`, `submit`, `export`, `history`, `stats`, `config`), directory management, Rich-based rendering
- Depends on: `schema`, `scorer`, `scrubber`, `click`, `rich`
- Used by: End users via `kajiba` console script entry point

## Data Flow

**Session Capture Flow (Hermes Agent integration):**

1. Hermes Agent calls `register_hooks(agent)` from `src/kajiba/hermes_integration.py`
2. `register_hooks` creates a `KajibaCollector` instance and subscribes to three events: `session_start`, `turn_complete`, `session_end`
3. On `session_start`: collector captures model metadata (from agent config dict) and hardware profile (auto-detected via `nvidia-smi`, `psutil`, `platform`)
4. On each `turn_complete`: collector appends a `ConversationTurn` with optional `ToolCall` objects
5. User can invoke `/rate` or `/report` slash commands, which call `collector.on_rate()` / `collector.on_report()`
6. On `session_end`: collector logs completion
7. `collector.export_record()` assembles the full `KajibaRecord`, runs PII scrubbing, computes record ID and submission hash

**CLI Submit Flow:**

1. User runs `kajiba submit`
2. CLI loads most recent JSON/JSONL file from `~/.hermes/kajiba/staging/` via `_load_latest_staging()`
3. Record is parsed and validated through `validate_record()` (Pydantic validation)
4. PII scrubbing via `scrub_record()` produces a scrubbed copy and a `ScrubLog`
5. Quality scoring via `compute_quality_score()` produces a `QualityResult` with composite score and tier
6. Rich preview rendered to terminal via `_render_preview()`
7. User confirms submission
8. `compute_record_id()` generates a deterministic SHA-256 hash from trajectory content
9. `compute_submission_hash()` generates a dedup key from trajectory + model + outcome
10. Scrubbed record written as JSONL to `~/.hermes/kajiba/outbox/record_{record_id}.jsonl`

**PII Scrubbing Flow:**

1. `scrub_record()` deep-copies the record via `model_dump(by_alias=True)` to avoid mutation
2. Iterates over all conversation turns, scrubbing `value`, `tool_input`, and `tool_output` fields
3. Scrubs pain point descriptions and outcome user comments
4. Each text field is run through `scrub_text()` which applies 7 regex pattern categories in order: file_paths, api_keys, network, emails, phone, crypto, connection_strings
5. Each match is replaced with a typed placeholder (e.g., `[REDACTED_PATH]`, `[REDACTED_KEY]`)
6. Returns a new `KajibaRecord` reconstructed from scrubbed data, plus a `ScrubLog` with per-category counts

**Quality Scoring Flow:**

1. `compute_quality_score()` runs five sub-score functions on the record
2. Sub-scores: `coherence` (0.30 weight), `tool_validity` (0.25), `outcome_quality` (0.20), `information_density` (0.15), `metadata_completeness` (0.10)
3. Weighted sum produces composite score (0.0-1.0)
4. Tier assignment: gold >= 0.85, silver >= 0.65, bronze >= 0.45, else review_needed

**State Management:**
- No persistent state or database; all data is stored as JSON/JSONL files on disk
- Three filesystem locations: `~/.hermes/kajiba/staging/` (input), `~/.hermes/kajiba/outbox/` (output), `~/.hermes/config.yaml` (config)
- `KajibaCollector` holds in-memory state during a session via instance attributes (`_conversations`, `_pain_points`, `_outcome`, etc.)

## Key Abstractions

**KajibaRecord (top-level data unit):**
- Purpose: Represents one complete task attempt -- the atomic unit of the pipeline
- Location: `src/kajiba/schema.py` (line 242)
- Pattern: Pydantic BaseModel with model validators for cross-field consistency (turn_count matches conversations length, tool call counts add up)
- Key methods: `to_sharegpt()` (strip to vanilla ShareGPT), `to_dpo_candidate()` (extract prompt/response for DPO training), `compute_record_id()` (deterministic content hash), `compute_submission_hash()` (dedup key)

**KajibaCollector (session lifecycle):**
- Purpose: Accumulates data during a Hermes Agent session via event-driven hooks
- Location: `src/kajiba/collector.py` (line 144)
- Pattern: Observer/listener that receives events from the agent. All public methods are wrapped in try/except to ensure fault tolerance -- errors are logged but never propagated.
- API: `on_session_start(session_id, model_config)`, `on_turn_complete(turn_dict)`, `on_session_end(session_id)`, `on_rate(rating, tags, comment)`, `on_report(category, description, severity)`, `export_record()`

**HermesAgent Protocol:**
- Purpose: Define the expected interface for Hermes Agent integration via structural typing
- Location: `src/kajiba/hermes_integration.py` (line 36)
- Pattern: Python `Protocol` class (runtime_checkable) -- Hermes Agent does not need to import or inherit from Kajiba
- Expected methods: `agent.on(event, callback)`, `agent.register_command(name, handler)`

**QualityResult:**
- Purpose: Result container for the five-sub-score quality assessment
- Location: `src/kajiba/scorer.py` (line 39)
- Pattern: Python dataclass with `composite_score`, `sub_scores` dict, and `quality_tier` string

**ScrubResult / Redaction:**
- Purpose: Track what was redacted during PII scrubbing of a single text string
- Location: `src/kajiba/scrubber.py` (lines 101, 112)
- Pattern: Python dataclasses; `ScrubResult` contains the scrubbed text, a list of `Redaction` objects, and per-category stats

**Controlled Vocabularies:**
- Purpose: Constrain values for outcome tags, pain point categories, severity levels, etc.
- Location: `src/kajiba/schema.py` (lines 25-109)
- Pattern: Dual definition -- Python tuples for runtime iteration (e.g., `OUTCOME_TAGS`), `Literal` type unions for static type checking (e.g., `OutcomeTagType`)

## Entry Points

**CLI (`kajiba` console script):**
- Location: `src/kajiba/cli.py` -> `cli()` function (line 163)
- Registered in: `pyproject.toml` `[project.scripts]` -> `kajiba = "kajiba.cli:cli"`
- Triggers: User runs `kajiba <command>` from terminal
- Commands: `preview`, `submit`, `export <path>`, `history`, `stats`, `config`

**Hermes Agent Integration (`register_hooks`):**
- Location: `src/kajiba/hermes_integration.py` -> `register_hooks(agent)` function (line 48)
- Triggers: Hermes Agent imports and calls `register_hooks(agent)` at startup
- Returns: `KajibaCollector` instance for manual access if needed

**Programmatic API (`validate_record`):**
- Location: `src/kajiba/schema.py` -> `validate_record(data)` function (line 372)
- Triggers: Any Python code that needs to parse/validate a raw JSON dict into a `KajibaRecord`

**Package Version:**
- Location: `src/kajiba/__init__.py` -> `__version__ = "0.1.0"`

## Error Handling

**Strategy:** Fault-tolerant collector, strict validation everywhere else

**Patterns:**
- `KajibaCollector` wraps every public method body in `try/except Exception` and logs errors via `logger.exception()`. This ensures the host Hermes Agent session is never disrupted by Kajiba failures. See `src/kajiba/collector.py` lines 169-186 for example.
- Schema validation uses Pydantic's built-in `ValidationError` which raises immediately on invalid data. The `validate_record()` function in `src/kajiba/schema.py` is the single entry point for validation.
- CLI commands catch exceptions during file loading (`_load_latest_staging()`, `_load_outbox_records()`) and display user-friendly messages via Rich console.
- The `scrub_record()` function in `src/kajiba/scrubber.py` operates on a deep copy (via `model_dump`) so the original record is never mutated.
- The LLM scrubber stub in `src/kajiba/scrubber_llm.py` raises `NotImplementedError` explicitly.

## Cross-Cutting Concerns

**Logging:**
- Standard library `logging` module used throughout
- Each module creates its own logger: `logger = logging.getLogger(__name__)`
- CLI sets base log level to `WARNING` in `cli()` group function
- Collector uses `logger.info()` for lifecycle events, `logger.exception()` for errors, `logger.debug()` for optional detection (GPU)

**Validation:**
- All data validation goes through Pydantic v2 models in `src/kajiba/schema.py`
- Field-level validators: `conversations_not_empty`, `validate_outcome_tags`
- Model-level validators: `validate_turn_count`, `validate_tool_call_counts`
- Controlled vocabularies enforced via `Literal` types and explicit validation

**Configuration:**
- Config read from `~/.hermes/config.yaml` (optional, YAML format)
- Default values defined inline in `src/kajiba/cli.py` `config` command (line 351)
- No environment variable configuration detected
- Config keys: `consent_level`, `auto_submit`, `llm_pii_scrub`, `scrub_strictness`

**Serialization:**
- Records serialized via Pydantic's `model_dump(mode="json", by_alias=True)` for JSON output
- `by_alias=True` is critical because `ConversationTurn.from_` uses alias `"from"` (Python reserved word)
- Input deserialization via `KajibaRecord.model_validate(data)`
- Content-addressable hashing via SHA-256 in `compute_record_id()` and `compute_submission_hash()`

---

*Architecture analysis: 2026-03-30*
