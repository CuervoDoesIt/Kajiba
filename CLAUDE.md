<!-- GSD:project-start source:PROJECT.md -->
## Project

**Kajiba**

Kajiba is an open-source, model-agnostic data pipeline that lets developers contribute their AI-assisted coding session data — prompts, responses, tool calls, model configurations, and hardware profiles — to a community dataset. Other developers browse and download subsets of this dataset to fine-tune their local LLMs, filtered by model type, quality tier, or runtime context. The pipeline handles collection, PII scrubbing, quality scoring, and publishing.

**Core Value:** Real-world AI session data, tagged with full runtime context (model identity, config, hardware), flowing into a community dataset that accelerates local model fine-tuning for everyone.

### Constraints

- **Tech stack**: Python 3.11+, Pydantic v2, Click, Rich — already established, no reason to change
- **Privacy**: Maximum scrubbing by default — err on the side of over-redacting
- **Local-first**: All processing happens on the contributor's machine before any data leaves
- **Open source**: Apache 2.0 license, community-friendly contribution flow
- **No external services for core**: Core pipeline must work without API keys or network access
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.11+ (3.13.3 detected on dev machine) - All source code
- JSON - Test fixtures, data serialization format
- Makefile - Build automation
## Runtime
- Python >= 3.11 (required; `pyproject.toml` line 11)
- CPython (standard interpreter)
- Uses `datetime.UTC` (Python 3.11+ feature)
- pip (via setuptools build backend)
- Lockfile: **Not present** - no `requirements.txt`, `pip.lock`, or `uv.lock`
- Virtual environment: `.venv/` directory present (standard venv)
## Frameworks
- Pydantic >= 2.0 - Data validation, schema modeling (`src/kajiba/schema.py`)
- Click >= 8.0 - CLI framework (`src/kajiba/cli.py`)
- Rich >= 13.0 - Terminal output formatting, tables, panels (`src/kajiba/cli.py`)
- pytest >= 7.0 - Test runner (`tests/`)
- pytest-cov >= 4.0 - Coverage reporting
- setuptools >= 68.0 - Build backend (`pyproject.toml` line 2)
- wheel - Wheel distribution support (`pyproject.toml` line 2)
## Key Dependencies
- `pydantic>=2.0` - Entire schema layer depends on Pydantic v2 models (BaseModel, Field, field_validator, model_validator). Used in `src/kajiba/schema.py` for all record types.
- `click>=8.0` - All CLI commands are Click groups/commands. Entry point: `kajiba = "kajiba.cli:cli"`.
- `rich>=13.0` - All CLI output uses Rich Console, Table, Panel, and Text. Used in `src/kajiba/cli.py`.
- `huggingface_hub>=0.19` - Upload extra (`pip install kajiba[upload]`). Not yet used in source code; planned for HuggingFace dataset submission.
- `psutil` - Not declared as dependency but conditionally imported in `src/kajiba/collector.py` line 92 for RAM detection. Falls back gracefully if absent.
- `pyyaml` - Not declared as dependency but conditionally imported in `src/kajiba/cli.py` line 360 for reading `~/.hermes/config.yaml`. Falls back gracefully.
- `hashlib` - SHA-256 for record_id and submission_hash (`src/kajiba/schema.py`)
- `re` - Regex-based PII pattern matching (`src/kajiba/scrubber.py`)
- `subprocess` - nvidia-smi for GPU detection (`src/kajiba/collector.py`)
- `platform` - OS and CPU detection (`src/kajiba/collector.py`)
- `json` - Record serialization throughout
- `pathlib` - File system operations throughout
- `logging` - Used in every module
- `copy` - Deep copy for scrubbing (`src/kajiba/scrubber.py`)
- `dataclasses` - Used for non-Pydantic result types in `src/kajiba/scrubber.py`, `src/kajiba/scrubber_llm.py`, `src/kajiba/scorer.py`
## Configuration
- No `.env` files detected
- No environment variables required for core operation
- Configuration optionally loaded from `~/.hermes/config.yaml` (PyYAML soft dependency)
- Default config values hardcoded in `src/kajiba/cli.py` lines 352-356:
- `pyproject.toml` - All project metadata, dependencies, build config, tool settings
- `Makefile` - Dev workflow commands (install, dev, test, lint, clean)
- No `setup.py` or `setup.cfg` - modern PEP 621 configuration only
- `~/.hermes/kajiba/` - Base directory
- `~/.hermes/kajiba/staging/` - Session data awaiting review
- `~/.hermes/kajiba/outbox/` - Submitted records
## Build & Dev Commands
## Platform Requirements
- Python >= 3.11
- pip (for editable installs)
- make (optional, for Makefile commands)
- No OS-specific requirements; runs on Linux, macOS, Windows
- Python >= 3.11
- Local filesystem access for `~/.hermes/kajiba/` data directories
- Optional: NVIDIA GPU with `nvidia-smi` for hardware detection
- Optional: `psutil` for RAM detection on non-Linux systems
- Optional: `pyyaml` for reading Hermes config
- No network services required for core operation (purely local pipeline)
## Version Information
- Project version: `0.1.0` (`src/kajiba/__init__.py`, `pyproject.toml`)
- Schema version: `0.1.0` (`src/kajiba/schema.py` line 21)
- Status: Early MVP (Phase 1 per `ROADMAP.md`)
- License: Apache 2.0
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- All source modules use `snake_case.py`: `schema.py`, `scrubber.py`, `scorer.py`, `collector.py`, `cli.py`, `hermes_integration.py`, `scrubber_llm.py`
- Test files use `test_<module>.py` prefix: `test_schema.py`, `test_scrubber.py`, `test_scorer.py`, `test_collector.py`, `test_cli.py`
- Fixture files use `<descriptive_name>.json`: `gold_trajectory.json`, `minimal_trajectory.json`, `pii_trajectory.json`
- Use `PascalCase` for all classes
- Pydantic models: `KajibaRecord`, `ConversationTurn`, `ToolCall`, `OutcomeSignals`, `ScrubLog`, `ModelMetadata`, `HardwareProfile`
- Dataclasses: `Redaction`, `ScrubResult`, `QualityResult`, `SemanticRedaction`
- Non-model classes: `KajibaCollector`
- Protocol classes: `HermesAgent` (in `src/kajiba/hermes_integration.py`)
- Public functions use `snake_case`: `validate_record()`, `scrub_text()`, `scrub_record()`, `compute_quality_score()`
- Private/internal functions use `_snake_case` prefix: `_detect_hardware()`, `_extract_model_metadata()`, `_scrub_string_fields_in_turn()`, `_ensure_dirs()`, `_load_latest_staging()`, `_render_preview()`
- Sub-score functions use `score_<dimension>` pattern: `score_coherence()`, `score_tool_validity()`, `score_outcome_quality()`, `score_information_density()`, `score_metadata_completeness()`
- Test helper functions use `_<verb>_<noun>` pattern: `_load_fixture()`, `_make_record()`
- Local variables use `snake_case`: `scrub_log`, `total_counts`, `record_json`
- Instance attributes use `_snake_case` for private state: `self._session_id`, `self._conversations`, `self._pain_points`
- Loop variables are terse but meaningful: `tc` for tool_call, `pp` for pain_point, `t` for turn, `cat` for category, `cnt` for count
- Module-level constants use `UPPER_SNAKE_CASE`
- Examples from `src/kajiba/schema.py`: `SCHEMA_VERSION`, `OUTCOME_TAGS`, `PAIN_POINT_CATEGORIES`
- Examples from `src/kajiba/scrubber.py`: `PLACEHOLDER_PATH`, `PLACEHOLDER_KEY`, `SCRUB_PATTERNS`, `CATEGORY_TO_LOG_FIELD`
- Examples from `src/kajiba/scorer.py`: `GOLD_THRESHOLD`, `SILVER_THRESHOLD`, `BRONZE_THRESHOLD`, `WEIGHTS`
- Examples from `src/kajiba/cli.py`: `KAJIBA_BASE`, `STAGING_DIR`, `OUTBOX_DIR`
- Use `<Name>Type` suffix for `Literal` type aliases: `OutcomeTagType`, `PainPointCategoryType`, `SeverityType`, `ConsentLevelType`, `ToolStatusType`, `DifficultyEstimateType`, `RecordTypeType`, `ProviderType`, `TurnRoleType`
- All defined in `src/kajiba/schema.py`
## Code Style
- No formatter config file (no ruff, black, or yapf config). The `.gitignore` references `.ruff_cache/` suggesting ruff may be used informally.
- Indentation: 4 spaces (standard Python)
- Max line length: appears to be ~100-120 characters based on actual code; some lines in `src/kajiba/cli.py` and `src/kajiba/scrubber.py` extend to ~110+ characters
- String quotes: double quotes preferred throughout (e.g., `"sharegpt_extended"`, `"success"`). Single quotes appear only inside regex patterns and f-strings where needed to avoid escaping.
- Trailing commas: used consistently on multi-line data structures and function calls (see `src/kajiba/scrubber.py` lines 151-157, `src/kajiba/collector.py` lines 199-206)
- No dedicated linter config file (no `.flake8`, `ruff.toml`, `.pylintrc`)
- The `Makefile` `lint` target uses `python -m py_compile` for syntax checking only -- not a real linter
- The `.gitignore` includes `.mypy_cache/` and `.ruff_cache/` but no mypy or ruff config exists in the repo
- All public functions and methods have full type annotations for parameters and return values
- Use `Optional[X]` from `typing` (not `X | None` union syntax): see `src/kajiba/collector.py` line 13, `src/kajiba/schema.py` line 11
- Use modern generic syntax: `list[str]`, `dict[str, int]`, `tuple[KajibaRecord, ScrubLog]` (not `List`, `Dict`, `Tuple` from `typing`)
- Literal types used extensively for controlled vocabularies in `src/kajiba/schema.py`
- Protocol class with `@runtime_checkable` for interface definition in `src/kajiba/hermes_integration.py`
- `Callable` type used for function parameters in `src/kajiba/scrubber_llm.py` line 41
## Import Organization
- Use `from X import Y` for specific names rather than bare `import X` (exception: standard library modules like `json`, `logging`, `re`, `copy`)
- Group related imports on one `from` statement: see `src/kajiba/collector.py` lines 16-28 which imports 12 names from `kajiba.schema`
- No path aliases or import rewiring configured
## Error Handling
## Logging
- Each module creates its own logger: `logger = logging.getLogger(__name__)` at module level
- Present in all source modules: `src/kajiba/schema.py`, `src/kajiba/scrubber.py`, `src/kajiba/scorer.py`, `src/kajiba/collector.py`, `src/kajiba/cli.py`, `src/kajiba/hermes_integration.py`, `src/kajiba/scrubber_llm.py`
- CLI configures logging in the Click group: `logging.basicConfig(level=logging.WARNING)` at `src/kajiba/cli.py` line 165
- Use `logger.info()` for lifecycle events: session start/end in `src/kajiba/collector.py` lines 184, 236
- Use `logger.debug()` for optional/skipped features: GPU detection skip in `src/kajiba/collector.py` line 89
- Use `logger.warning()` for non-fatal issues: session ID mismatch in `src/kajiba/collector.py` lines 229-232
- Use `logger.error()` for file I/O failures: `src/kajiba/cli.py` lines 61, 80
- Use `logger.exception()` for caught exceptions in fault-tolerant code: all collector methods
- Use `%s` string formatting (not f-strings) in logger calls for lazy evaluation: `logger.info("Kajiba collector started for session %s", session_id)`
- Never use `print()` for logging (stated in `CONTRIBUTING.md`)
## Comments
- Section dividers use `# ---------------------------------------------------------------------------` horizontal rules to separate major sections within a module (constants, nested models, public API, sub-scores, etc.)
- All section dividers include a label comment: `# Constants`, `# Nested models`, `# Top-level record`, `# Public API`, `# Core scrubbing functions`, etc.
- Google-style docstrings as stated in `CONTRIBUTING.md`
- Every module has a module-level docstring describing its purpose and its role in the Kajiba spec
- Every public class has a docstring. Key classes include usage examples (see `KajibaCollector` in `src/kajiba/collector.py` lines 144-157)
- Every public function/method has a docstring with `Args:`, `Returns:`, and optionally `Raises:` sections
- Private functions have brief docstrings (1-2 lines) or a `Returns:` section only
- Pydantic validators have one-line docstrings describing the rule: `"""Trajectory must have at least one turn."""`
- Used sparingly for non-obvious logic
- Present for category-to-field mappings in `src/kajiba/scrubber.py` line 83: `# Categories map to ScrubLog field names`
- Present for algorithm explanations in `src/kajiba/scorer.py`
## Function Design
- Functions are typically 10-40 lines
- Largest functions: `_detect_hardware()` at ~80 lines (`src/kajiba/collector.py`), `_render_preview()` at ~70 lines (`src/kajiba/cli.py`)
- Sub-score functions in `src/kajiba/scorer.py` are 15-30 lines each
- Use keyword arguments for optional parameters with defaults: `severity: SeverityType = "medium"` in `src/kajiba/collector.py` line 260
- Use Pydantic `Field()` for validation constraints: `Field(ge=1, le=5)` in `src/kajiba/schema.py` line 187
- Limit positional parameters to 3-4 max; use keyword-only for more
- Use tuples for multi-value returns: `tuple[KajibaRecord, ScrubLog]` from `scrub_record()` in `src/kajiba/scrubber.py`
- Use dataclasses for structured results: `QualityResult`, `ScrubResult`
- Use `Optional[X]` for functions that may return nothing: `_load_latest_staging()` returns `Optional[KajibaRecord]`
## Module Design
- No `__all__` lists defined in any module
- Public API is implicit: non-underscore-prefixed names are public
- `src/kajiba/__init__.py` exports only `__version__`
- Not used. Each module is imported directly by name: `from kajiba.schema import ...`, `from kajiba.scrubber import ...`
- Each module has a single, clear responsibility documented in its module docstring
- `src/kajiba/schema.py`: Record schema and validation
- `src/kajiba/scrubber.py`: Regex-based PII scrubbing
- `src/kajiba/scrubber_llm.py`: LLM-based PII scrubbing (stub)
- `src/kajiba/scorer.py`: Quality scoring
- `src/kajiba/collector.py`: Session lifecycle capture
- `src/kajiba/cli.py`: CLI commands
- `src/kajiba/hermes_integration.py`: Hermes Agent adapter
## Data Modeling
- Use `BaseModel` for all schema models (not `dataclass`)
- Use `model_validator(mode="after")` for cross-field validation: see `src/kajiba/schema.py` lines 265-287
- Use `field_validator` with `@classmethod` for single-field validation: see `src/kajiba/schema.py` lines 148-153, 193-199
- Use `model_config = {"populate_by_name": True}` for alias support: `ConversationTurn` and `KajibaRecord`
- Use `Field(alias="from")` for Python keyword conflicts: `from_` field in `ConversationTurn`
- Use `model_dump(by_alias=True)` for serialization: `src/kajiba/scrubber.py` line 209
- Use `model_validate(data)` for deserialization: `src/kajiba/schema.py` line 384
- Use `@dataclass` for simple value objects that don't need validation: `Redaction`, `ScrubResult`, `QualityResult` in `src/kajiba/scrubber.py` and `src/kajiba/scorer.py`
- Use `field(default_factory=list)` and `field(default_factory=dict)` for mutable defaults
- Define as both `tuple` (for runtime iteration) and `Literal` type (for type checking)
- Example: `OUTCOME_TAGS` tuple + `OutcomeTagType` Literal in `src/kajiba/schema.py` lines 25-65
- Validators check membership against the tuple at runtime
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- Single-pass data pipeline operating on one record (session) at a time
- Plugin-based integration with Hermes Agent via event hooks (observer pattern)
- Fault-tolerant collector that swallows all exceptions to avoid disrupting the host agent
- Pydantic v2 models as the single source of truth for data validation and serialization
- Local-first design: all processing happens on the user's machine, no network calls required
- CLI as the primary user interface via Click, with Rich for terminal rendering
## Layers
- Purpose: Define the complete data model with validation rules, controlled vocabularies, and serialization methods
- Location: `src/kajiba/schema.py`
- Contains: All Pydantic models (`KajibaRecord`, `Trajectory`, `ConversationTurn`, `ToolCall`, `ModelMetadata`, `HardwareProfile`, `OutcomeSignals`, `PainPoint`, `ScrubLog`, `SubmissionMetadata`), Literal type aliases for controlled vocabularies, `validate_record()` public API
- Depends on: `pydantic`, `hashlib`, `json`
- Used by: Every other module in the package
- Purpose: Hook into Hermes Agent session lifecycle and capture turns, tool calls, model metadata, and hardware info
- Location: `src/kajiba/collector.py`
- Contains: `KajibaCollector` class with event handlers (`on_session_start`, `on_turn_complete`, `on_session_end`, `on_rate`, `on_report`), hardware detection (`_detect_hardware()`), model metadata extraction (`_extract_model_metadata()`)
- Depends on: `schema`, `scorer`, `scrubber`, `platform`, `subprocess`, `psutil` (optional)
- Used by: `hermes_integration`, CLI (indirectly)
- Purpose: Thin adapter that wires `KajibaCollector` lifecycle hooks into Hermes Agent's event system
- Location: `src/kajiba/hermes_integration.py`
- Contains: `HermesAgent` Protocol class, `register_hooks(agent)` function
- Depends on: `collector`
- Used by: Hermes Agent (external)
- Purpose: Remove personally identifiable information from records before export/submission
- Location: `src/kajiba/scrubber.py` (regex-based, Layer B), `src/kajiba/scrubber_llm.py` (LLM-based, Layer C -- stub)
- Contains: Regex pattern categories, `scrub_text()` for individual strings, `scrub_record()` for full records, `ScrubResult` and `Redaction` dataclasses
- Depends on: `schema` (for `KajibaRecord`, `ScrubLog`)
- Used by: `collector` (via `export_record()`), `cli` (via `preview`/`submit`/`export` commands)
- Purpose: Compute a composite quality score from five weighted sub-scores and assign a quality tier
- Location: `src/kajiba/scorer.py`
- Contains: Five sub-score functions, `compute_quality_score()`, `QualityResult` dataclass, threshold constants
- Depends on: `schema` (for `KajibaRecord`)
- Used by: `collector` (not directly, but the result is consumed by CLI), `cli`
- Purpose: Provide command-line interface for previewing, submitting, exporting, and managing records
- Location: `src/kajiba/cli.py`
- Contains: Click command group with 6 commands (`preview`, `submit`, `export`, `history`, `stats`, `config`), directory management, Rich-based rendering
- Depends on: `schema`, `scorer`, `scrubber`, `click`, `rich`
- Used by: End users via `kajiba` console script entry point
## Data Flow
- No persistent state or database; all data is stored as JSON/JSONL files on disk
- Three filesystem locations: `~/.hermes/kajiba/staging/` (input), `~/.hermes/kajiba/outbox/` (output), `~/.hermes/config.yaml` (config)
- `KajibaCollector` holds in-memory state during a session via instance attributes (`_conversations`, `_pain_points`, `_outcome`, etc.)
## Key Abstractions
- Purpose: Represents one complete task attempt -- the atomic unit of the pipeline
- Location: `src/kajiba/schema.py` (line 242)
- Pattern: Pydantic BaseModel with model validators for cross-field consistency (turn_count matches conversations length, tool call counts add up)
- Key methods: `to_sharegpt()` (strip to vanilla ShareGPT), `to_dpo_candidate()` (extract prompt/response for DPO training), `compute_record_id()` (deterministic content hash), `compute_submission_hash()` (dedup key)
- Purpose: Accumulates data during a Hermes Agent session via event-driven hooks
- Location: `src/kajiba/collector.py` (line 144)
- Pattern: Observer/listener that receives events from the agent. All public methods are wrapped in try/except to ensure fault tolerance -- errors are logged but never propagated.
- API: `on_session_start(session_id, model_config)`, `on_turn_complete(turn_dict)`, `on_session_end(session_id)`, `on_rate(rating, tags, comment)`, `on_report(category, description, severity)`, `export_record()`
- Purpose: Define the expected interface for Hermes Agent integration via structural typing
- Location: `src/kajiba/hermes_integration.py` (line 36)
- Pattern: Python `Protocol` class (runtime_checkable) -- Hermes Agent does not need to import or inherit from Kajiba
- Expected methods: `agent.on(event, callback)`, `agent.register_command(name, handler)`
- Purpose: Result container for the five-sub-score quality assessment
- Location: `src/kajiba/scorer.py` (line 39)
- Pattern: Python dataclass with `composite_score`, `sub_scores` dict, and `quality_tier` string
- Purpose: Track what was redacted during PII scrubbing of a single text string
- Location: `src/kajiba/scrubber.py` (lines 101, 112)
- Pattern: Python dataclasses; `ScrubResult` contains the scrubbed text, a list of `Redaction` objects, and per-category stats
- Purpose: Constrain values for outcome tags, pain point categories, severity levels, etc.
- Location: `src/kajiba/schema.py` (lines 25-109)
- Pattern: Dual definition -- Python tuples for runtime iteration (e.g., `OUTCOME_TAGS`), `Literal` type unions for static type checking (e.g., `OutcomeTagType`)
## Entry Points
- Location: `src/kajiba/cli.py` -> `cli()` function (line 163)
- Registered in: `pyproject.toml` `[project.scripts]` -> `kajiba = "kajiba.cli:cli"`
- Triggers: User runs `kajiba <command>` from terminal
- Commands: `preview`, `submit`, `export <path>`, `history`, `stats`, `config`
- Location: `src/kajiba/hermes_integration.py` -> `register_hooks(agent)` function (line 48)
- Triggers: Hermes Agent imports and calls `register_hooks(agent)` at startup
- Returns: `KajibaCollector` instance for manual access if needed
- Location: `src/kajiba/schema.py` -> `validate_record(data)` function (line 372)
- Triggers: Any Python code that needs to parse/validate a raw JSON dict into a `KajibaRecord`
- Location: `src/kajiba/__init__.py` -> `__version__ = "0.1.0"`
## Error Handling
- `KajibaCollector` wraps every public method body in `try/except Exception` and logs errors via `logger.exception()`. This ensures the host Hermes Agent session is never disrupted by Kajiba failures. See `src/kajiba/collector.py` lines 169-186 for example.
- Schema validation uses Pydantic's built-in `ValidationError` which raises immediately on invalid data. The `validate_record()` function in `src/kajiba/schema.py` is the single entry point for validation.
- CLI commands catch exceptions during file loading (`_load_latest_staging()`, `_load_outbox_records()`) and display user-friendly messages via Rich console.
- The `scrub_record()` function in `src/kajiba/scrubber.py` operates on a deep copy (via `model_dump`) so the original record is never mutated.
- The LLM scrubber stub in `src/kajiba/scrubber_llm.py` raises `NotImplementedError` explicitly.
## Cross-Cutting Concerns
- Standard library `logging` module used throughout
- Each module creates its own logger: `logger = logging.getLogger(__name__)`
- CLI sets base log level to `WARNING` in `cli()` group function
- Collector uses `logger.info()` for lifecycle events, `logger.exception()` for errors, `logger.debug()` for optional detection (GPU)
- All data validation goes through Pydantic v2 models in `src/kajiba/schema.py`
- Field-level validators: `conversations_not_empty`, `validate_outcome_tags`
- Model-level validators: `validate_turn_count`, `validate_tool_call_counts`
- Controlled vocabularies enforced via `Literal` types and explicit validation
- Config read from `~/.hermes/config.yaml` (optional, YAML format)
- Default values defined inline in `src/kajiba/cli.py` `config` command (line 351)
- No environment variable configuration detected
- Config keys: `consent_level`, `auto_submit`, `llm_pii_scrub`, `scrub_strictness`
- Records serialized via Pydantic's `model_dump(mode="json", by_alias=True)` for JSON output
- `by_alias=True` is critical because `ConversationTurn.from_` uses alias `"from"` (Python reserved word)
- Input deserialization via `KajibaRecord.model_validate(data)`
- Content-addressable hashing via SHA-256 in `compute_record_id()` and `compute_submission_hash()`
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
