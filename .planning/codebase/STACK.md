# Technology Stack

**Analysis Date:** 2026-03-30

## Languages

**Primary:**
- Python 3.11+ (3.13.3 detected on dev machine) - All source code

**Secondary:**
- JSON - Test fixtures, data serialization format
- Makefile - Build automation

## Runtime

**Environment:**
- Python >= 3.11 (required; `pyproject.toml` line 11)
- CPython (standard interpreter)
- Uses `datetime.UTC` (Python 3.11+ feature)

**Package Manager:**
- pip (via setuptools build backend)
- Lockfile: **Not present** - no `requirements.txt`, `pip.lock`, or `uv.lock`
- Virtual environment: `.venv/` directory present (standard venv)

## Frameworks

**Core:**
- Pydantic >= 2.0 - Data validation, schema modeling (`src/kajiba/schema.py`)
- Click >= 8.0 - CLI framework (`src/kajiba/cli.py`)
- Rich >= 13.0 - Terminal output formatting, tables, panels (`src/kajiba/cli.py`)

**Testing:**
- pytest >= 7.0 - Test runner (`tests/`)
- pytest-cov >= 4.0 - Coverage reporting

**Build/Dev:**
- setuptools >= 68.0 - Build backend (`pyproject.toml` line 2)
- wheel - Wheel distribution support (`pyproject.toml` line 2)

## Key Dependencies

**Critical (core dependencies in `pyproject.toml` lines 25-29):**
- `pydantic>=2.0` - Entire schema layer depends on Pydantic v2 models (BaseModel, Field, field_validator, model_validator). Used in `src/kajiba/schema.py` for all record types.
- `click>=8.0` - All CLI commands are Click groups/commands. Entry point: `kajiba = "kajiba.cli:cli"`.
- `rich>=13.0` - All CLI output uses Rich Console, Table, Panel, and Text. Used in `src/kajiba/cli.py`.

**Optional extras (`pyproject.toml` lines 31-42):**
- `huggingface_hub>=0.19` - Upload extra (`pip install kajiba[upload]`). Not yet used in source code; planned for HuggingFace dataset submission.
- `psutil` - Not declared as dependency but conditionally imported in `src/kajiba/collector.py` line 92 for RAM detection. Falls back gracefully if absent.
- `pyyaml` - Not declared as dependency but conditionally imported in `src/kajiba/cli.py` line 360 for reading `~/.hermes/config.yaml`. Falls back gracefully.

**Infrastructure (stdlib only - no external infra deps):**
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

**Environment:**
- No `.env` files detected
- No environment variables required for core operation
- Configuration optionally loaded from `~/.hermes/config.yaml` (PyYAML soft dependency)
- Default config values hardcoded in `src/kajiba/cli.py` lines 352-356:
  - `consent_level`: "full"
  - `auto_submit`: False
  - `llm_pii_scrub`: True
  - `scrub_strictness`: "high"

**Build:**
- `pyproject.toml` - All project metadata, dependencies, build config, tool settings
- `Makefile` - Dev workflow commands (install, dev, test, lint, clean)
- No `setup.py` or `setup.cfg` - modern PEP 621 configuration only

**Data directories (created at runtime by `src/kajiba/cli.py` lines 31-33):**
- `~/.hermes/kajiba/` - Base directory
- `~/.hermes/kajiba/staging/` - Session data awaiting review
- `~/.hermes/kajiba/outbox/` - Submitted records

## Build & Dev Commands

**From `Makefile`:**
```bash
make install          # pip install -e .
make dev              # pip install -e ".[all]" (includes upload, dev extras)
make test             # pytest tests/ -v --cov=kajiba --cov-report=term-missing
make lint             # py_compile on each source file (syntax check only)
make clean            # Remove build artifacts, __pycache__, .pytest_cache, .coverage
```

**CLI entry point:**
```bash
kajiba                # Registered via project.scripts in pyproject.toml
kajiba --version      # Shows schema version (0.1.0)
kajiba preview        # Preview latest staging session
kajiba submit         # Submit with confirmation
kajiba export <path>  # Export to JSONL file
kajiba history        # List past submissions
kajiba stats          # Aggregate statistics
kajiba config         # Show configuration
```

## Platform Requirements

**Development:**
- Python >= 3.11
- pip (for editable installs)
- make (optional, for Makefile commands)
- No OS-specific requirements; runs on Linux, macOS, Windows

**Production/Runtime:**
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

---

*Stack analysis: 2026-03-30*
