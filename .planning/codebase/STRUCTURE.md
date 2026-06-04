# Codebase Structure

**Analysis Date:** 2026-03-30

## Directory Layout

```
Kajiba/
├── src/
│   └── kajiba/                  # Main Python package
│       ├── __init__.py          # Package version (__version__ = "0.1.0")
│       ├── cli.py               # Click CLI commands + Rich rendering
│       ├── collector.py         # Session lifecycle collector (KajibaCollector)
│       ├── hermes_integration.py # Hermes Agent adapter (register_hooks)
│       ├── schema.py            # Pydantic v2 models, controlled vocabularies, validation
│       ├── scorer.py            # Quality scoring system (5 sub-scores + composite)
│       ├── scrubber.py          # Regex-based PII scrubber (Layer B)
│       └── scrubber_llm.py      # LLM-based PII scrubber stub (Layer C, not implemented)
├── tests/
│   ├── __init__.py              # Empty init
│   ├── fixtures/                # JSON test data files
│   │   ├── adversarial_trajectory.json   # Intentionally bad data (review_needed tier)
│   │   ├── gold_trajectory.json          # Fully-populated gold-tier record
│   │   ├── minimal_trajectory.json       # Bare minimum valid record
│   │   ├── pii_trajectory.json           # Record with embedded PII for scrubber testing
│   │   └── silver_trajectory.json        # Mid-quality record with all sections
│   ├── test_cli.py              # CLI smoke tests (Click CliRunner)
│   ├── test_collector.py        # Collector lifecycle and fault tolerance tests
│   ├── test_schema.py           # Schema validation, export methods, record ID determinism
│   ├── test_scorer.py           # Quality tier and sub-score tests
│   └── test_scrubber.py         # PII pattern and full-record scrubbing tests
├── docs/
│   └── kajiba-project-spec.md   # Full project specification (schema, vocabularies, pipeline design)
├── pyproject.toml               # Build config, dependencies, entry points, pytest config
├── Makefile                     # Dev shortcuts: install, dev, test, lint, clean
├── README.md                    # Project overview
├── ROADMAP.md                   # 5-phase development plan with milestones
├── SKILL.md                     # Hermes Agent skill manifest (slash commands, config)
├── CONTRIBUTING.md              # Contribution guidelines
├── LICENSE                      # Apache 2.0
└── .gitignore                   # Standard Python gitignore
```

## Directory Purposes

**`src/kajiba/`:**
- Purpose: The entire application -- all source code lives in this single flat package
- Contains: 7 Python modules (no sub-packages)
- Key files: `schema.py` (data model foundation), `collector.py` (core business logic), `cli.py` (user interface)

**`tests/`:**
- Purpose: pytest test suite with fixture-driven testing
- Contains: 5 test modules + 5 JSON fixture files
- Key files: `test_schema.py` (most comprehensive, 260 lines), `test_scrubber.py` (314 lines)

**`tests/fixtures/`:**
- Purpose: JSON files representing records at different quality tiers and with different characteristics
- Contains: 5 fixture files used across multiple test modules
- Key files: `gold_trajectory.json` (reference "perfect" record), `pii_trajectory.json` (PII scrubber test data)

**`docs/`:**
- Purpose: Project specification document
- Contains: Single detailed spec file covering schema, vocabularies, pipeline design
- Key files: `kajiba-project-spec.md`

**`src/kajiba.egg-info/`:**
- Purpose: Auto-generated package metadata from `pip install -e .`
- Generated: Yes
- Committed: No (should be in .gitignore)

**`.venv/`:**
- Purpose: Python virtual environment
- Generated: Yes
- Committed: No

## Key File Locations

**Entry Points:**
- `src/kajiba/cli.py`: CLI entry point -- `cli()` Click group registered as `kajiba` console script
- `src/kajiba/hermes_integration.py`: Hermes Agent entry point -- `register_hooks(agent)` function
- `src/kajiba/__init__.py`: Package version (`__version__`)

**Configuration:**
- `pyproject.toml`: Build system, dependencies, optional extras, entry points, pytest/coverage config
- `Makefile`: Dev commands (`make install`, `make dev`, `make test`, `make lint`, `make clean`)
- `~/.hermes/config.yaml`: Runtime config (consent_level, auto_submit, llm_pii_scrub, scrub_strictness) -- NOT in repo

**Core Logic:**
- `src/kajiba/schema.py`: All Pydantic models, controlled vocabularies, validation rules, export methods, hashing
- `src/kajiba/collector.py`: `KajibaCollector` class, hardware detection, model metadata extraction
- `src/kajiba/scrubber.py`: Regex patterns for 7 PII categories, `scrub_text()`, `scrub_record()`
- `src/kajiba/scorer.py`: 5 sub-score functions, weighted composite scorer, tier assignment

**Testing:**
- `tests/test_schema.py`: Schema validation (valid records, validation failures, export methods, record ID determinism, controlled vocabularies)
- `tests/test_scorer.py`: Tier verification against fixtures, individual sub-score tests, edge cases
- `tests/test_scrubber.py`: Per-category PII detection, false positive tests, full record scrubbing, LLM stub test
- `tests/test_collector.py`: Full session lifecycle, minimal session, fault tolerance, hardware detection
- `tests/test_cli.py`: Click CliRunner smoke tests for all 6 commands

## Naming Conventions

**Files:**
- All source modules: `snake_case.py` (e.g., `scrubber_llm.py`, `hermes_integration.py`)
- Test files: `test_<module>.py` mirroring source modules (e.g., `test_scrubber.py` tests `scrubber.py`)
- Test fixtures: `<descriptor>_trajectory.json` (e.g., `gold_trajectory.json`)

**Directories:**
- Flat package structure: all source files in `src/kajiba/` (no nested packages)
- Tests mirror source layout at the module level

## Import Dependency Graph

The dependency flow is strictly layered with no circular imports:

```
hermes_integration.py
    └── collector.py
            ├── schema.py        (all models, vocabularies)
            ├── scorer.py        (depends on schema.py)
            └── scrubber.py      (depends on schema.py)

cli.py
    ├── schema.py
    ├── scorer.py
    └── scrubber.py

scrubber_llm.py                  (standalone stub, no internal imports)
```

**Detailed imports per module:**

`src/kajiba/schema.py` imports:
- Standard library only: `hashlib`, `json`, `logging`, `datetime`, `typing`
- Third-party: `pydantic` (BaseModel, Field, field_validator, model_validator)

`src/kajiba/scrubber.py` imports:
- `kajiba.schema`: `KajibaRecord`, `ScrubLog`

`src/kajiba/scorer.py` imports:
- `kajiba.schema`: `KajibaRecord`

`src/kajiba/collector.py` imports:
- `kajiba.schema`: `SCHEMA_VERSION`, `ConversationTurn`, `HardwareProfile`, `KajibaRecord`, `ModelMetadata`, `OutcomeSignals`, `PainPoint`, `PainPointCategoryType`, `SeverityType`, `SubmissionMetadata`, `ToolCall`, `Trajectory`
- `kajiba.scorer`: `compute_quality_score`
- `kajiba.scrubber`: `scrub_record`

`src/kajiba/hermes_integration.py` imports:
- `kajiba.collector`: `KajibaCollector`

`src/kajiba/cli.py` imports:
- `kajiba.schema`: `SCHEMA_VERSION`, `KajibaRecord`, `validate_record`
- `kajiba.scorer`: `compute_quality_score`
- `kajiba.scrubber`: `scrub_record`
- Conditional: `kajiba.schema.SubmissionMetadata` (imported inside `export` command)
- Conditional: `yaml` (imported inside `config` command, optional dependency)

`src/kajiba/scrubber_llm.py` imports:
- No internal imports (standalone stub)

## Where to Add New Code

**New pipeline stage (e.g., deduplication, adversarial detection):**
- Create new module: `src/kajiba/<stage_name>.py`
- Follow existing pattern: import from `kajiba.schema`, accept `KajibaRecord` as input, return processed result
- Add tests: `tests/test_<stage_name>.py`
- Wire into CLI or collector as needed

**New CLI command:**
- Add to `src/kajiba/cli.py` as a new `@cli.command()` decorated function
- Follow existing pattern: load data, process, render with Rich, handle empty states gracefully

**New schema field or model:**
- Add to `src/kajiba/schema.py`
- If adding a controlled vocabulary: define both the tuple (e.g., `NEW_VOCAB`) and the Literal type (e.g., `NewVocabType`)
- Update test fixtures in `tests/fixtures/` if the new field affects existing records
- Add validation tests to `tests/test_schema.py`

**New PII scrubbing pattern:**
- Add regex pattern tuple to `SCRUB_PATTERNS` dict in `src/kajiba/scrubber.py`
- Map category to `ScrubLog` field in `CATEGORY_TO_LOG_FIELD` dict
- If new category: add corresponding field to `ScrubLog` model in `src/kajiba/schema.py`
- Add test class to `tests/test_scrubber.py` following `TestFilePathScrubbing` pattern

**New quality sub-score:**
- Add `score_<name>(record) -> float` function to `src/kajiba/scorer.py`
- Add weight to `WEIGHTS` dict (ensure weights still sum to 1.0)
- Add test class to `tests/test_scorer.py`

**New test fixture:**
- Add JSON file to `tests/fixtures/`
- Follow naming pattern: `<descriptor>_trajectory.json`
- Must pass `validate_record()` unless testing validation failures

**Implementing LLM scrubber (Layer C):**
- Flesh out `src/kajiba/scrubber_llm.py` (stub already exists with `SemanticRedaction` and `ScrubResult` dataclasses)
- Add dependencies to `pyproject.toml` `[project.optional-dependencies.llm-scrub]`
- Integrate as second pass in `scrub_record()` within `src/kajiba/scrubber.py` or create a new orchestrating function

## Special Directories

**`~/.hermes/kajiba/staging/`:**
- Purpose: Input directory for session data to be processed by CLI
- Generated: Yes, at runtime by `_ensure_dirs()` in `src/kajiba/cli.py`
- Committed: No (user's home directory)
- Contains: JSON/JSONL files placed here by Hermes Agent or manually

**`~/.hermes/kajiba/outbox/`:**
- Purpose: Output directory for finalized, scrubbed records ready for upload
- Generated: Yes, at runtime by `_ensure_dirs()` in `src/kajiba/cli.py`
- Committed: No (user's home directory)
- Contains: JSONL files named `record_{record_id}.jsonl`

**`src/kajiba.egg-info/`:**
- Purpose: Editable install metadata from `pip install -e .`
- Generated: Yes
- Committed: No (should be gitignored)

---

*Structure analysis: 2026-03-30*
