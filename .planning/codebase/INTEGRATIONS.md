# External Integrations

**Analysis Date:** 2026-03-30

## APIs & External Services

**Hermes Agent (primary integration target):**
- Kajiba is designed as a plugin/collector for NousResearch's Hermes Agent
- Integration layer: `src/kajiba/hermes_integration.py`
- Protocol-based interface: `HermesAgent` Protocol class (lines 36-45)
- Expected agent API:
  - `agent.on(event_name, callback)` - Subscribe to lifecycle events
  - `agent.register_command(name, handler)` - Register slash commands
- Events consumed: `session_start`, `turn_complete`, `session_end`
- Graceful degradation: If Hermes Agent is unavailable, collector works in standalone mode
- **Current status:** Integration layer is wired up but Hermes Agent is not a dependency. The protocol defines the expected interface; actual integration requires Hermes Agent to be installed separately.

**HuggingFace Hub (planned, not yet active):**
- SDK: `huggingface_hub>=0.19` (optional extra: `pip install kajiba[upload]`)
- Purpose: Upload curated datasets to HuggingFace as dataset PRs
- Target dataset: `CuervoDoesIt/kajiba-community` (referenced in `ROADMAP.md` line 86)
- **Current status:** Dependency declared in `pyproject.toml` line 32 but no source code imports it yet. Upload functionality is a Phase 1 milestone (M1.6) not yet implemented.

**NVIDIA nvidia-smi (local system tool):**
- Used in: `src/kajiba/collector.py` lines 59-88
- Purpose: GPU detection (name, VRAM, count, CUDA/driver version)
- Invoked via `subprocess.run()` with 10-second timeout
- Queries: `--query-gpu=name,memory.total` and `--query-gpu=driver_version`
- Graceful fallback: Catches `FileNotFoundError`, `TimeoutExpired`, `OSError`

## Data Storage

**Databases:**
- None. All data is stored as local JSON/JSONL files on the filesystem.

**File Storage:**
- Local filesystem only
- Base path: `~/.hermes/kajiba/` (defined in `src/kajiba/cli.py` line 31)
- Staging directory: `~/.hermes/kajiba/staging/` - Holds session JSON files pending review
- Outbox directory: `~/.hermes/kajiba/outbox/` - Holds submitted JSONL records
- File formats:
  - `.json` - Individual session records in staging
  - `.jsonl` - Submitted records in outbox (one JSON object per line)
- Directories auto-created on first use (`_ensure_dirs()` in `src/kajiba/cli.py` line 36)

**Caching:**
- None

## Data Format & Serialization

**Schema format:** JSON (Pydantic v2 models)
- Primary record type: `KajibaRecord` (`src/kajiba/schema.py` line 242)
- Serialization: `model_dump(mode="json", by_alias=True)` for JSON output
- Deserialization: `KajibaRecord.model_validate(data)` via `validate_record()` function
- Content addressing: SHA-256 hashes for `record_id` and `submission_hash`

**Export formats:**
- JSONL (primary export via `kajiba export` command)
- ShareGPT-compatible JSON via `KajibaRecord.to_sharegpt()` (`src/kajiba/schema.py` line 289)
- DPO pair format via `KajibaRecord.to_dpo_candidate()` (`src/kajiba/schema.py` line 303)

## Authentication & Identity

**Auth Provider:**
- None currently implemented
- Planned: Pseudonymous contributor ID (`contributor_id` field in `SubmissionMetadata`, `src/kajiba/schema.py` line 229)
- Consent model: `consent_level` field supports "trajectory_only", "metadata_only", "full", "anonymous" (`src/kajiba/schema.py` line 99)

## Monitoring & Observability

**Error Tracking:**
- None (no external error tracking service)

**Logs:**
- Python stdlib `logging` module used in every source file
- Logger name follows module path: `logging.getLogger(__name__)`
- CLI sets log level to WARNING by default (`src/kajiba/cli.py` line 165)
- Collector logs session start/end at INFO level, errors at EXCEPTION level
- All collector errors are caught and logged but never raised (fault-tolerant design)

## CI/CD & Deployment

**Hosting:**
- Not deployed as a service. Distributed as a pip-installable Python package.

**CI Pipeline:**
- No `.github/workflows/` directory detected
- No CI configuration present
- Linting is manual via `make lint` (runs `py_compile` on each source file)

**Distribution:**
- Installable via `pip install -e .` (editable) or standard pip from source
- Entry point: `kajiba` CLI command registered in `pyproject.toml` line 44
- Not published to PyPI (yet)

## Environment Configuration

**Required env vars:**
- None. Kajiba has zero required environment variables.

**Optional configuration:**
- `~/.hermes/config.yaml` - Hermes Agent config file; Kajiba reads the `kajiba` section if present (`src/kajiba/cli.py` lines 349-368)
- Config keys (with defaults):
  - `consent_level`: "full"
  - `auto_submit`: False
  - `llm_pii_scrub`: True
  - `scrub_strictness`: "high"

**Secrets location:**
- No secrets required for current functionality
- Future: HuggingFace Hub token will be needed for upload functionality (managed by `huggingface_hub` library, typically via `huggingface-cli login`)

## Webhooks & Callbacks

**Incoming:**
- None (no network server component in Phase 1)
- Planned for Phase 2: FastAPI ingestion API with POST endpoint for record submission (per `ROADMAP.md` line 62)

**Outgoing:**
- None

## Integration Points Summary

| Integration | Status | Module | Soft/Hard Dep |
|-------------|--------|--------|---------------|
| Hermes Agent | Protocol defined, not yet connected | `src/kajiba/hermes_integration.py` | Soft (graceful fallback) |
| HuggingFace Hub | Declared, not implemented | N/A (extra: `upload`) | Soft (optional extra) |
| nvidia-smi | Active (GPU detection) | `src/kajiba/collector.py` | Soft (graceful fallback) |
| psutil | Conditionally imported | `src/kajiba/collector.py` | Soft (undeclared, fallback) |
| PyYAML | Conditionally imported | `src/kajiba/cli.py` | Soft (undeclared, fallback) |
| Local filesystem | Active (staging/outbox) | `src/kajiba/cli.py` | Hard (required) |

## Planned Integrations (Not Yet Implemented)

Per `ROADMAP.md` and `docs/kajiba-project-spec.md`:

- **Phase 2:** FastAPI ingestion API, LLM-based semantic PII scrubber (local model calls via Ollama/llama.cpp), direct submission from Hermes Agent
- **Phase 3:** HuggingFace Spaces dataset browser, community voting system, Atropos RL environment
- **Phase 5:** Cross-harness support (OpenHands, SWE-agent), federated collection

---

*Integration audit: 2026-03-30*
