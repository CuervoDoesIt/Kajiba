# Coding Conventions

**Analysis Date:** 2026-03-30

## Naming Patterns

**Files:**
- All source modules use `snake_case.py`: `schema.py`, `scrubber.py`, `scorer.py`, `collector.py`, `cli.py`, `hermes_integration.py`, `scrubber_llm.py`
- Test files use `test_<module>.py` prefix: `test_schema.py`, `test_scrubber.py`, `test_scorer.py`, `test_collector.py`, `test_cli.py`
- Fixture files use `<descriptive_name>.json`: `gold_trajectory.json`, `minimal_trajectory.json`, `pii_trajectory.json`

**Classes:**
- Use `PascalCase` for all classes
- Pydantic models: `KajibaRecord`, `ConversationTurn`, `ToolCall`, `OutcomeSignals`, `ScrubLog`, `ModelMetadata`, `HardwareProfile`
- Dataclasses: `Redaction`, `ScrubResult`, `QualityResult`, `SemanticRedaction`
- Non-model classes: `KajibaCollector`
- Protocol classes: `HermesAgent` (in `src/kajiba/hermes_integration.py`)

**Functions:**
- Public functions use `snake_case`: `validate_record()`, `scrub_text()`, `scrub_record()`, `compute_quality_score()`
- Private/internal functions use `_snake_case` prefix: `_detect_hardware()`, `_extract_model_metadata()`, `_scrub_string_fields_in_turn()`, `_ensure_dirs()`, `_load_latest_staging()`, `_render_preview()`
- Sub-score functions use `score_<dimension>` pattern: `score_coherence()`, `score_tool_validity()`, `score_outcome_quality()`, `score_information_density()`, `score_metadata_completeness()`
- Test helper functions use `_<verb>_<noun>` pattern: `_load_fixture()`, `_make_record()`

**Variables:**
- Local variables use `snake_case`: `scrub_log`, `total_counts`, `record_json`
- Instance attributes use `_snake_case` for private state: `self._session_id`, `self._conversations`, `self._pain_points`
- Loop variables are terse but meaningful: `tc` for tool_call, `pp` for pain_point, `t` for turn, `cat` for category, `cnt` for count

**Constants:**
- Module-level constants use `UPPER_SNAKE_CASE`
- Examples from `src/kajiba/schema.py`: `SCHEMA_VERSION`, `OUTCOME_TAGS`, `PAIN_POINT_CATEGORIES`
- Examples from `src/kajiba/scrubber.py`: `PLACEHOLDER_PATH`, `PLACEHOLDER_KEY`, `SCRUB_PATTERNS`, `CATEGORY_TO_LOG_FIELD`
- Examples from `src/kajiba/scorer.py`: `GOLD_THRESHOLD`, `SILVER_THRESHOLD`, `BRONZE_THRESHOLD`, `WEIGHTS`
- Examples from `src/kajiba/cli.py`: `KAJIBA_BASE`, `STAGING_DIR`, `OUTBOX_DIR`

**Type Aliases:**
- Use `<Name>Type` suffix for `Literal` type aliases: `OutcomeTagType`, `PainPointCategoryType`, `SeverityType`, `ConsentLevelType`, `ToolStatusType`, `DifficultyEstimateType`, `RecordTypeType`, `ProviderType`, `TurnRoleType`
- All defined in `src/kajiba/schema.py`

## Code Style

**Formatting:**
- No formatter config file (no ruff, black, or yapf config). The `.gitignore` references `.ruff_cache/` suggesting ruff may be used informally.
- Indentation: 4 spaces (standard Python)
- Max line length: appears to be ~100-120 characters based on actual code; some lines in `src/kajiba/cli.py` and `src/kajiba/scrubber.py` extend to ~110+ characters
- String quotes: double quotes preferred throughout (e.g., `"sharegpt_extended"`, `"success"`). Single quotes appear only inside regex patterns and f-strings where needed to avoid escaping.
- Trailing commas: used consistently on multi-line data structures and function calls (see `src/kajiba/scrubber.py` lines 151-157, `src/kajiba/collector.py` lines 199-206)

**Linting:**
- No dedicated linter config file (no `.flake8`, `ruff.toml`, `.pylintrc`)
- The `Makefile` `lint` target uses `python -m py_compile` for syntax checking only -- not a real linter
- The `.gitignore` includes `.mypy_cache/` and `.ruff_cache/` but no mypy or ruff config exists in the repo

**Type Hints:**
- All public functions and methods have full type annotations for parameters and return values
- Use `Optional[X]` from `typing` (not `X | None` union syntax): see `src/kajiba/collector.py` line 13, `src/kajiba/schema.py` line 11
- Use modern generic syntax: `list[str]`, `dict[str, int]`, `tuple[KajibaRecord, ScrubLog]` (not `List`, `Dict`, `Tuple` from `typing`)
- Literal types used extensively for controlled vocabularies in `src/kajiba/schema.py`
- Protocol class with `@runtime_checkable` for interface definition in `src/kajiba/hermes_integration.py`
- `Callable` type used for function parameters in `src/kajiba/scrubber_llm.py` line 41

## Import Organization

**Order:**
1. Standard library imports (alphabetical): `hashlib`, `json`, `logging`, `platform`, `re`, `subprocess`, etc.
2. Third-party imports: `click`, `pydantic`, `rich`
3. Local imports: `from kajiba.schema import ...`, `from kajiba.scorer import ...`, `from kajiba.scrubber import ...`

**Style:**
- Use `from X import Y` for specific names rather than bare `import X` (exception: standard library modules like `json`, `logging`, `re`, `copy`)
- Group related imports on one `from` statement: see `src/kajiba/collector.py` lines 16-28 which imports 12 names from `kajiba.schema`
- No path aliases or import rewiring configured

**Examples from `src/kajiba/collector.py`:**
```python
import logging
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from kajiba.schema import (
    SCHEMA_VERSION,
    ConversationTurn,
    HardwareProfile,
    KajibaRecord,
    ...
)
from kajiba.scorer import compute_quality_score
from kajiba.scrubber import scrub_record
```

## Error Handling

**Patterns:**

1. **Collector fault tolerance (never raise to caller):** All `KajibaCollector` lifecycle methods wrap their entire body in `try/except Exception` and use `logger.exception()`. The agent session must never be disrupted by Kajiba failures. See `src/kajiba/collector.py` lines 176-186 (`on_session_start`), lines 216-219 (`on_turn_complete`), etc.

```python
def on_turn_complete(self, turn: dict) -> None:
    try:
        # ... actual logic ...
    except Exception:
        logger.exception("Error in on_turn_complete")
```

2. **Validation via Pydantic:** Schema validation errors are raised as `pydantic.ValidationError` and not caught internally. The caller is expected to handle them. See `src/kajiba/schema.py` line 384: `validate_record()` simply calls `KajibaRecord.model_validate(data)`.

3. **Graceful degradation for optional features:** Hardware detection in `src/kajiba/collector.py` catches `FileNotFoundError`, `subprocess.TimeoutExpired`, `OSError`, and `ImportError` individually, returning whatever data could be gathered. See lines 59-104.

4. **CLI error logging:** File loading errors in CLI use `logger.error()` and return `None`. See `src/kajiba/cli.py` lines 60-63.

5. **Never use bare `except:`:** All exception handlers specify at least `Exception`. No bare `except:` clauses exist.

## Logging

**Framework:** Python `logging` module (no third-party logging library)

**Setup:**
- Each module creates its own logger: `logger = logging.getLogger(__name__)` at module level
- Present in all source modules: `src/kajiba/schema.py`, `src/kajiba/scrubber.py`, `src/kajiba/scorer.py`, `src/kajiba/collector.py`, `src/kajiba/cli.py`, `src/kajiba/hermes_integration.py`, `src/kajiba/scrubber_llm.py`
- CLI configures logging in the Click group: `logging.basicConfig(level=logging.WARNING)` at `src/kajiba/cli.py` line 165

**Patterns:**
- Use `logger.info()` for lifecycle events: session start/end in `src/kajiba/collector.py` lines 184, 236
- Use `logger.debug()` for optional/skipped features: GPU detection skip in `src/kajiba/collector.py` line 89
- Use `logger.warning()` for non-fatal issues: session ID mismatch in `src/kajiba/collector.py` lines 229-232
- Use `logger.error()` for file I/O failures: `src/kajiba/cli.py` lines 61, 80
- Use `logger.exception()` for caught exceptions in fault-tolerant code: all collector methods
- Use `%s` string formatting (not f-strings) in logger calls for lazy evaluation: `logger.info("Kajiba collector started for session %s", session_id)`
- Never use `print()` for logging (stated in `CONTRIBUTING.md`)

## Comments

**When to Comment:**
- Section dividers use `# ---------------------------------------------------------------------------` horizontal rules to separate major sections within a module (constants, nested models, public API, sub-scores, etc.)
- All section dividers include a label comment: `# Constants`, `# Nested models`, `# Top-level record`, `# Public API`, `# Core scrubbing functions`, etc.

**Docstrings:**
- Google-style docstrings as stated in `CONTRIBUTING.md`
- Every module has a module-level docstring describing its purpose and its role in the Kajiba spec
- Every public class has a docstring. Key classes include usage examples (see `KajibaCollector` in `src/kajiba/collector.py` lines 144-157)
- Every public function/method has a docstring with `Args:`, `Returns:`, and optionally `Raises:` sections
- Private functions have brief docstrings (1-2 lines) or a `Returns:` section only
- Pydantic validators have one-line docstrings describing the rule: `"""Trajectory must have at least one turn."""`

**Example docstring format from `src/kajiba/schema.py`:**
```python
def compute_record_id(self) -> str:
    """Generate a deterministic SHA-256 hash from the trajectory content.

    The record_id is a content-addressable identifier: same trajectory
    content always produces the same ID.

    Returns:
        String in the format 'kajiba_<first 12 hex chars>'.
    """
```

**Inline comments:**
- Used sparingly for non-obvious logic
- Present for category-to-field mappings in `src/kajiba/scrubber.py` line 83: `# Categories map to ScrubLog field names`
- Present for algorithm explanations in `src/kajiba/scorer.py`

## Function Design

**Size:**
- Functions are typically 10-40 lines
- Largest functions: `_detect_hardware()` at ~80 lines (`src/kajiba/collector.py`), `_render_preview()` at ~70 lines (`src/kajiba/cli.py`)
- Sub-score functions in `src/kajiba/scorer.py` are 15-30 lines each

**Parameters:**
- Use keyword arguments for optional parameters with defaults: `severity: SeverityType = "medium"` in `src/kajiba/collector.py` line 260
- Use Pydantic `Field()` for validation constraints: `Field(ge=1, le=5)` in `src/kajiba/schema.py` line 187
- Limit positional parameters to 3-4 max; use keyword-only for more

**Return Values:**
- Use tuples for multi-value returns: `tuple[KajibaRecord, ScrubLog]` from `scrub_record()` in `src/kajiba/scrubber.py`
- Use dataclasses for structured results: `QualityResult`, `ScrubResult`
- Use `Optional[X]` for functions that may return nothing: `_load_latest_staging()` returns `Optional[KajibaRecord]`

## Module Design

**Exports:**
- No `__all__` lists defined in any module
- Public API is implicit: non-underscore-prefixed names are public
- `src/kajiba/__init__.py` exports only `__version__`

**Barrel Files:**
- Not used. Each module is imported directly by name: `from kajiba.schema import ...`, `from kajiba.scrubber import ...`

**Module Responsibility:**
- Each module has a single, clear responsibility documented in its module docstring
- `src/kajiba/schema.py`: Record schema and validation
- `src/kajiba/scrubber.py`: Regex-based PII scrubbing
- `src/kajiba/scrubber_llm.py`: LLM-based PII scrubbing (stub)
- `src/kajiba/scorer.py`: Quality scoring
- `src/kajiba/collector.py`: Session lifecycle capture
- `src/kajiba/cli.py`: CLI commands
- `src/kajiba/hermes_integration.py`: Hermes Agent adapter

## Data Modeling

**Pydantic v2 Patterns:**
- Use `BaseModel` for all schema models (not `dataclass`)
- Use `model_validator(mode="after")` for cross-field validation: see `src/kajiba/schema.py` lines 265-287
- Use `field_validator` with `@classmethod` for single-field validation: see `src/kajiba/schema.py` lines 148-153, 193-199
- Use `model_config = {"populate_by_name": True}` for alias support: `ConversationTurn` and `KajibaRecord`
- Use `Field(alias="from")` for Python keyword conflicts: `from_` field in `ConversationTurn`
- Use `model_dump(by_alias=True)` for serialization: `src/kajiba/scrubber.py` line 209
- Use `model_validate(data)` for deserialization: `src/kajiba/schema.py` line 384

**Dataclass Patterns:**
- Use `@dataclass` for simple value objects that don't need validation: `Redaction`, `ScrubResult`, `QualityResult` in `src/kajiba/scrubber.py` and `src/kajiba/scorer.py`
- Use `field(default_factory=list)` and `field(default_factory=dict)` for mutable defaults

**Controlled Vocabularies:**
- Define as both `tuple` (for runtime iteration) and `Literal` type (for type checking)
- Example: `OUTCOME_TAGS` tuple + `OutcomeTagType` Literal in `src/kajiba/schema.py` lines 25-65
- Validators check membership against the tuple at runtime

---

*Convention analysis: 2026-03-30*
