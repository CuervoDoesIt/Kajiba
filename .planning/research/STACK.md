# Stack Research

**Domain:** Community AI Training Data Pipeline
**Researched:** 2026-03-30
**Confidence:** MEDIUM-HIGH (core technologies verified via PyPI; architecture patterns via multiple sources)

---

## Context: Existing Stack (Do Not Change)

The following are already established and in production. This document covers only **new additions** needed for the active milestone.

| Technology | Version | Role |
|---|---|---|
| Python | 3.11+ | Primary language |
| Pydantic | >=2.0 | Schema and validation |
| Click | >=8.0 | CLI framework |
| Rich | >=13.0 | Terminal output |
| pytest + pytest-cov | >=7.0 / >=4.0 | Testing |
| setuptools + wheel | >=68.0 | Build backend |

---

## Recommended Stack

### New Core Technologies

| Technology | Recommended Version | Purpose | Why |
|---|---|---|---|
| `ollama` (Python client) | `>=0.6.1` | LLM-based semantic PII scrubbing backend | Official first-party client (0.6.1 released Nov 2025). AsyncClient available for non-blocking calls. Requires Ollama service running locally. Model metadata (quantization, parameters) exposed via `/api/show` — solves the model config capture requirement simultaneously. |
| `presidio-analyzer` | `>=2.2.362` | Structured PII detection layer (NER + regex) | Microsoft-maintained, actively updated (2.2.362 released Mar 2026). Combines spaCy NER with rule-based recognizers. Detects PERSON, ORG, LOCATION entities that regex misses. Works 100% locally. Use as the primary NER layer; Ollama LLM as the semantic fallback for ambiguous cases. |
| `presidio-anonymizer` | `>=2.2.362` | Replace/redact detected PII spans | Paired with presidio-analyzer. Handles span replacement with typed placeholders (`<PERSON>`, `<ORG>`). Same version as analyzer — they ship together. |
| `spacy` | `>=3.8.14` | NLP engine backing Presidio | Required by presidio-analyzer as its default NER engine. 3.8.14 released Mar 2026. Requires model download: `python -m spacy download en_core_web_lg` (large model for better recall — preferred over sm for PII work). |
| `GitPython` | `>=3.1.46` | Git-based dataset repo management | Maintenance-mode but stable and complete (3.1.46 released Jan 2026). No feature gaps for Kajiba's needs: clone, add, commit, push are all well-supported. The only viable pure-Python option. For simple operations (add/commit/push), wrapping `subprocess` is a reasonable fallback if maintenance status is a concern — but GitPython avoids shell injection risk. |
| `APScheduler` | `>=3.11.2` | Continuous background collection mode | Production-grade scheduler (3.11.2 released Dec 2025). Supports interval triggers (collect every N minutes), persistent job stores, and BackgroundScheduler that runs in a daemon thread alongside the CLI process. Vastly more capable than `schedule` — required because Kajiba needs configurable intervals, graceful shutdown, and eventual persistence. |
| `pydantic-settings` | `>=2.13.1` | Structured configuration management | Already using Pydantic v2; pydantic-settings (2.13.1, Feb 2026) is the natural companion. Replaces the current ad-hoc `~/.hermes/config.yaml` read. Supports env vars, TOML, YAML, and `.env` files. Type-safe, validated config with zero boilerplate. Python 3.11+ already in stdlib has `tomllib` for read-only TOML — pydantic-settings wraps this. |

### Supporting Libraries

| Library | Recommended Version | Purpose | When to Use |
|---|---|---|---|
| `filelock` | `>=3.25.2` | Single-instance lock for background daemon | Use to prevent two concurrent background collectors from running simultaneously. Cross-platform, no external dependencies. 3.25.2 released Mar 2026. Create `~/.kajiba/kajiba.lock` on daemon start; release on exit. |
| `psutil` | `>=7.2.2` | System resource monitoring in collector | Already conditionally imported — promote to declared optional dependency. Needed for RAM detection fallback and for the background mode watchdog to check resource usage before triggering collection. |
| `pyyaml` | `>=6.0` | Read Hermes config during model-agnostic transition | Already conditionally imported — promote to declared optional dependency. Needed until the Hermes config dependency is fully replaced by pydantic-settings. |
| `watchdog` | `>=6.0.0` | Filesystem event trigger for ad-hoc collection mode | Use to detect when a session file lands in the staging directory and trigger scrubbing/scoring automatically. 6.0.0 released Nov 2024. Python 3.9+ required — compatible with Kajiba's 3.11+ baseline. Optional: only needed if real-time staging directory monitoring is desired. |

### Development Tools (No Change Needed)

The existing pytest + pytest-cov setup is adequate. No new dev dependencies are required for this milestone.

---

## Installation

```bash
# Core new dependencies (add to pyproject.toml [dependencies])
pip install "ollama>=0.6.1"
pip install "presidio-analyzer>=2.2.362" "presidio-anonymizer>=2.2.362"
pip install "spacy>=3.8.14"
pip install "gitpython>=3.1.46"
pip install "APScheduler>=3.11.2"
pip install "pydantic-settings>=2.13.1"

# spaCy model (post-install step — document in README)
python -m spacy download en_core_web_lg

# Supporting optional deps
pip install "filelock>=3.25.2" "psutil>=7.2.2" "pyyaml>=6.0"

# Optional: filesystem watching
pip install "watchdog>=6.0.0"
```

Suggested `pyproject.toml` extras structure:

```toml
[project.optional-dependencies]
llm-scrub = [
    "ollama>=0.6.1",
    "presidio-analyzer>=2.2.362",
    "presidio-anonymizer>=2.2.362",
    "spacy>=3.8.14",
]
publish = [
    "gitpython>=3.1.46",
]
daemon = [
    "APScheduler>=3.11.2",
    "filelock>=3.25.2",
    "watchdog>=6.0.0",
]
config = [
    "pydantic-settings>=2.13.1",
    "pyyaml>=6.0",
]
upload = ["huggingface_hub>=0.19"]  # existing, unchanged
dev = ["pytest>=7.0", "pytest-cov>=4.0"]  # existing, unchanged
all = [
    "kajiba[llm-scrub]",
    "kajiba[publish]",
    "kajiba[daemon]",
    "kajiba[config]",
    "kajiba[upload]",
    "kajiba[dev]",
]
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|---|---|---|---|
| Local LLM backend | `ollama` Python client | `llama-cpp-python` (0.3.19) | llama-cpp-python requires building from source (C++ compile step), has complex GPU acceleration flags, and the binary wheels are large and fragile. Ollama abstracts all of this — contributors just run `ollama pull qwen2.5:3b`. For Kajiba, ease of contributor setup beats raw control. |
| Local LLM backend | `ollama` Python client | `transformers` + `torch` | Transformers requires ~2GB PyTorch install minimum. Breaks the "no heavy dependencies for core pipeline" constraint. Acceptable for a dedicated ML server, not for a CLI tool installed on contributor machines. |
| NER/PII detection | `presidio-analyzer` + `spacy` | Pure Ollama LLM for all PII | LLM inference for every record is slow (1-3s/call vs <50ms for spaCy NER). Use spaCy/Presidio for structured entities (names, orgs, locations) and Ollama only as a second-pass for ambiguous semantic PII. Layered approach is faster and more reliable. |
| NER/PII detection | `presidio-analyzer` + `spacy` | `spacy` alone | Presidio adds regex recognizers on top of spaCy NER — covers emails, phone numbers, credit cards, SSNs out of the box. No reason not to use it when it wraps spaCy anyway. |
| Scheduler | `APScheduler` | `schedule` library | `schedule` is single-threaded and has no persistence. APScheduler runs in a daemon thread, survives config reload, and can persist job state. Required for Kajiba's continuous mode. |
| Scheduler | `APScheduler` | Python `threading.Timer` | Timer requires manual re-scheduling and has no graceful shutdown primitives. Reinventing APScheduler without the features. |
| Config management | `pydantic-settings` | Plain `pyyaml` + dict | Current approach. Untyped, no validation, no env var support. pydantic-settings costs almost nothing (already using Pydantic v2) and eliminates a class of runtime config errors. |
| Git operations | `GitPython` | `subprocess` wrapping git CLI | Subprocess works fine for simple cases but has shell injection risk if any path includes spaces or special characters. GitPython provides safe, typed API. Given that GitPython is in maintenance mode and functionally complete, it is the right choice. |
| Git operations | `GitPython` | `pygit2` (libgit2 bindings) | pygit2 requires compiled C extensions and libgit2 system dependency. Unnecessary complexity for add/commit/push. |
| Model metadata | Ollama `/api/show` | GGUF metadata via `gguf` package | GGUF package reads metadata from `.gguf` files directly — useful only if users run llama.cpp. Ollama is the primary target and its `/api/show` endpoint returns architecture, quantization, parameter count, context length — everything needed for model config records. |

---

## What NOT to Use

| Library / Approach | Reason |
|---|---|
| `langchain` or `llama-index` | Massive dependency trees that pull in dozens of transitive dependencies. Kajiba's LLM usage is narrow (one structured prompt for PII detection). Don't add 40+ packages for a feature that needs 20 lines of ollama client code. |
| `transformers` + `torch` | Too heavy for a CLI tool. 2GB+ install, requires CUDA/ROCm setup for GPU. Use Ollama to abstract the model runtime instead. |
| `DVC` (Data Version Control) | DVC is a full ML experiment tracking system. Kajiba's dataset publishing needs are simple: organize by `model/tier/`, commit JSONL files, push. Plain GitPython is sufficient. DVC would add a parallel versioning system on top of Git, creating contributor confusion. |
| `celery` or `dramatiq` | Message queue-based task runners require a broker (Redis/RabbitMQ). Kajiba is a local CLI tool — APScheduler in-process is the right scope. |
| Cloud-based PII services (AWS Comprehend, Azure Text Analytics) | Violates the "no external services for core" constraint. Sending user session data to cloud APIs for PII detection is exactly what Kajiba is designed to avoid. |
| `presidio-analyzer` with `stanza` NLP engine | Stanza requires JVM-adjacent setup and is significantly slower than spaCy for comparable accuracy on English text. Use spaCy `en_core_web_lg`. |

---

## Stack Patterns by Variant

### Pattern 1: Semantic PII Scrubbing (Two-Pass)

Fastest and most reliable approach for semantic PII detection on session records:

1. **Pass 1 — Regex** (existing `scrubber.py`): Catches paths, tokens, keys, IPs, emails, phones. Fast, zero-overhead.
2. **Pass 2 — Presidio + spaCy NER**: Catches PERSON, ORG, LOCATION entities. ~20-50ms per record. No network required.
3. **Pass 3 — Ollama LLM** (optional, `llm_pii_scrub: true` in config): Sends redacted-so-far text to a small local model (e.g., `qwen2.5:3b`) with a structured prompt asking it to identify any remaining personal identifiers. ~500ms-2s per record. Only runs if `llm_pii_scrub` is enabled and Ollama is running.

This matches the existing `scrubber_llm.py` stub architecture. Pass 3 should be optional and gracefully skipped if Ollama is unavailable.

### Pattern 2: Model Config Metadata Capture

Use `ollama.show(model=model_name)` to populate the `ModelConfig` Pydantic schema at session capture time:

- `details.parameter_size` → parameter count
- `details.quantization_level` → quantization type (Q4_K_M, Q8_0, etc.)
- `details.family` → model family
- `model_info` dict → context length, embedding length, architecture

For non-Ollama models (llama.cpp direct, etc.), fall back to user-provided config via `pydantic-settings`.

### Pattern 3: Background Daemon Mode

```
APScheduler BackgroundScheduler
  └── IntervalTrigger (user-configured: 5m, 30m, 1h)
      └── collection job: scan staging dir → scrub → score → submit
  └── filelock (prevent concurrent daemon instances)
  └── Rich Live display (optional status in foreground mode)
```

The daemon runs inside the existing CLI process when `kajiba daemon start` is invoked. APScheduler's `BackgroundScheduler` runs in a daemon thread — it does not block the main thread and exits cleanly when the process exits. No separate process management needed.

### Pattern 4: Git Dataset Repository

Directory structure for the dataset repo (no DVC required):

```
dataset/
  by_model/
    qwen2.5-3b-q4_k_m/
      gold/   ← JSONL files, one per submission batch
      silver/
      bronze/
    llama3.2-3b-q4_0/
      gold/
      ...
  catalog.json  ← machine-readable index of all records (generated on push)
  README.md     ← auto-generated stats summary
```

GitPython handles: `repo.index.add()`, `repo.index.commit()`, `repo.remotes['origin'].push()`. The catalog.json is regenerated before each commit from the JSONL index.

### Pattern 5: Configuration Evolution

Replace the current ad-hoc YAML read in `cli.py` with a `KajibaConfig` class using pydantic-settings:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class KajibaConfig(BaseSettings):
    model_config = SettingsConfigDict(
        toml_file="~/.kajiba/config.toml",
        env_prefix="KAJIBA_",
    )
    consent_level: str = "full"
    auto_submit: bool = False
    llm_pii_scrub: bool = True
    scrub_strictness: str = "high"
    collection_interval_minutes: int = 30
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    dataset_repo_path: str | None = None
```

This replaces the hardcoded defaults in `cli.py` lines 352-356 and supports user overrides via env vars (`KAJIBA_OLLAMA_MODEL=llama3.2:3b`) or a `~/.kajiba/config.toml` file.

---

## Version Compatibility

| Library | Min Python | Notes |
|---|---|---|
| `ollama` 0.6.1 | 3.8+ | AsyncClient available for non-blocking use |
| `presidio-analyzer` 2.2.362 | 3.8+ | spaCy 3.x required |
| `presidio-anonymizer` 2.2.362 | 3.8+ | Paired with analyzer |
| `spacy` 3.8.14 | 3.9+ | Kajiba requires 3.11+, no conflict |
| `GitPython` 3.1.46 | 3.7+ | Maintenance mode; stable |
| `APScheduler` 3.11.2 | 3.8+ | 3.x API used here (not 4.x alpha) |
| `pydantic-settings` 2.13.1 | 3.8+ | Requires pydantic v2 (already present) |
| `filelock` 3.25.2 | 3.8+ | Cross-platform |
| `psutil` 7.2.2 | 3.6+ | Already soft-dep in codebase |
| `watchdog` 6.0.0 | 3.9+ | Compatible with 3.11+ baseline |

All libraries are compatible with Python 3.11+. No conflicts with existing dependencies.

**APScheduler version note:** APScheduler 4.x is in alpha as of early 2026 and has a significantly different API. Use `>=3.11.2,<4.0` in pyproject.toml to pin to the stable 3.x API.

---

## Sources

- [ollama PyPI page](https://pypi.org/project/ollama/) — version 0.6.1, released Nov 13, 2025 (HIGH confidence)
- [ollama/ollama-python GitHub](https://github.com/ollama/ollama-python) — official first-party client (HIGH confidence)
- [presidio-analyzer PyPI page](https://pypi.org/project/presidio-analyzer/) — version 2.2.362, released Mar 15, 2026 (HIGH confidence)
- [presidio-anonymizer PyPI page](https://pypi.org/project/presidio-anonymizer/) — version 2.2.362, released Mar 15, 2026 (HIGH confidence)
- [Microsoft Presidio documentation](https://microsoft.github.io/presidio/analyzer/customizing_nlp_models/) — supported NLP engines: spaCy, stanza, transformers only; Ollama not natively supported (HIGH confidence)
- [spaCy PyPI page](https://pypi.org/project/spacy/) — version 3.8.14, released Mar 29, 2026 (HIGH confidence)
- [GitPython PyPI page](https://pypi.org/project/GitPython/) — version 3.1.46, released Jan 1, 2026; maintenance mode confirmed (HIGH confidence)
- [APScheduler PyPI page](https://pypi.org/project/APScheduler/) — version 3.11.2, released Dec 22, 2025 (HIGH confidence)
- [pydantic-settings PyPI page](https://pypi.org/project/pydantic-settings/) — version 2.13.1, released Feb 19, 2026; TOML/YAML support confirmed (HIGH confidence)
- [filelock PyPI page](https://pypi.org/project/filelock/) — version 3.25.2, released Mar 11, 2026 (HIGH confidence)
- [watchdog PyPI page](https://pypi.org/project/watchdog/) — version 6.0.0, released Nov 1, 2024 (HIGH confidence)
- [llama-cpp-python PyPI page](https://pypi.org/project/llama-cpp-python/) — version 0.3.19, released Mar 25, 2026; used as alternative reference (HIGH confidence)
- [Ollama API docs — Show model details](https://docs.ollama.com/api-reference/show-model-details) — model metadata fields confirmed (HIGH confidence)
- [Python tomllib stdlib docs](https://docs.python.org/3.11/library/tomllib.html) — tomllib in stdlib since Python 3.11 (HIGH confidence)
- [APScheduler vs schedule comparison](https://leapcell.io/blog/scheduling-tasks-in-python-apscheduler-versus-schedule) — APScheduler recommended for production; schedule for scripts (MEDIUM confidence)
- [llama.cpp vs Ollama tradeoffs (2026)](https://www.openxcell.com/blog/llama-cpp-vs-ollama/) — Ollama wins on setup simplicity; llama.cpp wins on control (MEDIUM confidence)
- [LLM PII scrubbing best practices — dual NER+LLM approach](https://dzone.com/articles/the-ai-firewall-using-local-small-language-models) — two-pass structured+semantic architecture (MEDIUM confidence)
