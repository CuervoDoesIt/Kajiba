# Architecture Research

**Domain:** Community AI Training Data Pipeline
**Researched:** 2026-03-30
**Confidence:** MEDIUM-HIGH (core patterns verified against official Python docs and real dataset repos; community-specific patterns derived from analogous systems)

---

## Standard Architecture

### System Overview

The evolved Kajiba architecture introduces three new vertical concerns layered on top of the existing linear pipeline: a **Source Layer** (pluggable adapters for any AI tool), a **Contribution Mode Layer** (ad-hoc vs continuous behavioral contract), and a **Dataset Repository Layer** (structured Git repo + catalog for consumers). The existing Capture → Scrub → Score → Export core pipeline is preserved and made source-agnostic.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CONTRIBUTOR MACHINE                             │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      SOURCE LAYER                               │   │
│  │                                                                 │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │   │
│  │  │ HermesAdapter│  │ GenericAdapter│  │ FutureToolAdapter... │  │   │
│  │  │ (existing)   │  │ (new)         │  │ (community plugins)  │  │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │   │
│  │         │                 │                      │              │   │
│  │         └─────────────────┼──────────────────────┘              │   │
│  │                           │                                     │   │
│  │               ┌───────────▼────────────┐                        │   │
│  │               │   SourceAdapter ABC    │                        │   │
│  │               │ (common interface)     │                        │   │
│  │               └───────────┬────────────┘                        │   │
│  └───────────────────────────┼─────────────────────────────────────┘   │
│                              │ raw session dict                        │
│  ┌───────────────────────────▼─────────────────────────────────────┐   │
│  │                   CORE PIPELINE (existing)                      │   │
│  │                                                                 │   │
│  │   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌─────────┐  │   │
│  │   │ Collector│───▶│ Scrubber │───▶│  Scorer  │───▶│ Outbox  │  │   │
│  │   │ (schema) │    │ (PII)    │    │ (quality)│    │ (JSONL) │  │   │
│  │   └──────────┘    └──────────┘    └──────────┘    └────┬────┘  │   │
│  └──────────────────────────────────────────────────────────┼──────┘   │
│                                                             │           │
│  ┌──────────────────────────────────────────────────────────┼──────┐   │
│  │              CONTRIBUTION MODE LAYER                     │      │   │
│  │                                                          │      │   │
│  │  ┌─────────────────────────────────────────────────────┐ │      │   │
│  │  │  ContributionManager                                │ │      │   │
│  │  │  - mode: "adhoc" | "continuous"                     │◀┘      │   │
│  │  │  - consent_level: anonymous|trajectory|metadata|full│        │   │
│  │  │  - auto_submit: bool                                │        │   │
│  │  │  - review_queue: List[PendingRecord]                │        │   │
│  │  └──────────────────────────┬──────────────────────────┘        │   │
│  │                             │                                   │   │
│  │     ad-hoc: pause, show     │     continuous: process           │   │
│  │     preview, await confirm  │     automatically per config      │   │
│  └─────────────────────────────┼───────────────────────────────────┘   │
└────────────────────────────────┼────────────────────────────────────────┘
                                 │ scrubbed + scored JSONL records
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   DATASET REPOSITORY (GitHub)                           │
│                                                                         │
│  kajiba-dataset/                                                        │
│  ├── README.md              (browsable catalog entry point)             │
│  ├── catalog.json           (machine-readable index, auto-generated)    │
│  ├── data/                                                              │
│  │   ├── by-model/                                                      │
│  │   │   ├── hermes-3-8b/                                               │
│  │   │   │   ├── gold/     *.jsonl                                      │
│  │   │   │   ├── silver/   *.jsonl                                      │
│  │   │   │   └── bronze/   *.jsonl                                      │
│  │   │   └── llama-3.1-8b/                                              │
│  │   │       └── ...                                                    │
│  │   └── by-tier/          (symlinks or duplicate index)                │
│  │       ├── gold/                                                      │
│  │       └── silver/                                                    │
│  └── schemas/                                                           │
│      └── v1/kajiba_record.schema.json                                   │
│                                                                         │
│         ▲ contributors push via CLI ("kajiba publish")                  │
│         ▼ consumers pull subsets via CLI or direct git clone/filter     │
└─────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Inputs | Outputs | Communicates With |
|-----------|---------------|--------|---------|------------------|
| `SourceAdapter` (ABC) | Define the contract every source must satisfy | (abstract) | raw session dict | Collector |
| `HermesAdapter` | Map Hermes Agent events to SourceAdapter interface | Hermes event hooks | raw session dict | SourceAdapter |
| `GenericAdapter` | Accept a manually-constructed session dict from any tool | CLI input / direct call | raw session dict | SourceAdapter |
| `SourceRegistry` | Discover and hold all registered adapters by name | adapter classes | adapter instance by key | CLI, ContributionManager |
| `KajibaCollector` (existing) | Build a `KajibaRecord` from a raw session dict | raw session dict | `KajibaRecord` | Scrubber, Scorer |
| `Scrubber` (existing) | PII-strip the record | `KajibaRecord` | scrubbed `KajibaRecord` + `ScrubLog` | Scorer, Outbox |
| `Scorer` (existing) | Assign composite quality score and tier | `KajibaRecord` | `QualityResult` | CLI, ContributionManager |
| `ContributionManager` | Gate outbox → publish based on mode and consent | mode config, `KajibaRecord`, user input | approved JSONL | Publisher |
| `Publisher` | Write records into the dataset repo directory structure | approved JSONL, `KajibaRecord` metadata | JSONL files in `data/by-model/` | Dataset Repository |
| `CatalogBuilder` | Regenerate `catalog.json` from repo contents | repo data directory | `catalog.json` | Dataset Repository |
| `CLI` (extended) | Expose `publish`, `review`, `sync`, `sources` commands | user input | (side effects) | All components |

---

## Recommended Project Structure

The existing `src/kajiba/` flat layout is sufficient for the new modules. Introduce sub-packages only when the source adapter ecosystem needs external plugin distribution.

```
src/kajiba/
├── __init__.py
├── schema.py                 (existing — no changes required for Phase 1)
├── collector.py              (decouple from Hermes-specific calls)
├── scrubber.py               (existing)
├── scrubber_llm.py           (existing stub)
├── scorer.py                 (existing)
├── cli.py                    (add: publish, review, sources commands)
│
├── sources/                  (NEW sub-package — source adapters)
│   ├── __init__.py           (SourceRegistry + adapter discovery)
│   ├── base.py               (SourceAdapter ABC + SessionData dataclass)
│   ├── hermes.py             (refactored HermesAdapter — wraps existing hermes_integration.py)
│   └── generic.py            (GenericAdapter — accepts raw dict/JSON input)
│
├── contribution/             (NEW sub-package — contribution modes)
│   ├── __init__.py
│   ├── manager.py            (ContributionManager — ad-hoc vs continuous logic)
│   └── consent.py            (ConsentEnforcer — field stripping by consent level)
│
└── publisher/                (NEW sub-package — dataset repo output)
    ├── __init__.py
    ├── git_publisher.py      (write JSONL to dataset repo, git add/commit/push)
    └── catalog.py            (CatalogBuilder — regenerate catalog.json)

kajiba-dataset/               (SEPARATE git repository)
├── README.md
├── catalog.json
├── data/
│   └── by-model/
│       └── {model-slug}/
│           ├── gold/
│           ├── silver/
│           └── bronze/
└── schemas/
    └── v1/
        └── kajiba_record.schema.json
```

**Rationale for `sources/` sub-package over flat modules:** Once community contributors write adapters for tools like Cursor, Aider, or Continue, they need a clear namespace to target (`kajiba.sources.cursor`). A sub-package makes the namespace discoverable and allows future `importlib.metadata` entry_point registration without restructuring.

**Rationale for separate dataset repo:** The `kajiba-dataset` repo grows append-only with contributor data. Mixing it into the Kajiba code repo would pollute git history and make code contributions harder. Consumers clone or sparse-checkout only the dataset repo.

---

## Architectural Patterns

### Pattern 1: Abstract Source Adapter (ABC with Protocol fallback)

Use `ABC` with `@abstractmethod` to define the source interface. This is the right tool when:
- You control all adapters (they are in the same codebase)
- You want to prevent instantiation of incomplete adapters at class-definition time
- The interface is non-trivial (more than one method)

For community-contributed adapters that live outside the Kajiba package, expose a `Protocol` version of the same interface for structural subtyping — they can satisfy the contract without inheriting from Kajiba's ABC.

```python
# src/kajiba/sources/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass
class SessionData:
    """Normalized session dict that the Collector accepts."""
    session_id: str
    model_config: dict[str, Any]
    turns: list[dict[str, Any]]
    source_tool: str          # e.g., "hermes", "cursor", "aider"
    source_version: str | None = None

class SourceAdapter(ABC):
    """Every source adapter must satisfy this contract."""

    @abstractmethod
    def get_source_name(self) -> str:
        """Short identifier, e.g. 'hermes', 'generic'."""
        ...

    @abstractmethod
    def build_session_data(self, raw: dict[str, Any]) -> SessionData:
        """Normalize tool-specific raw data into SessionData."""
        ...

    def register_hooks(self, agent: Any) -> None:
        """Optional: wire into a live agent's event system."""
        pass  # not required for file-based adapters
```

### Pattern 2: Registry with Explicit Registration (not entry_points)

For the current milestone, a simple dictionary registry is the right choice. Entry points are for distributable plugins across separate packages — overkill while adapters live inside the Kajiba package.

```python
# src/kajiba/sources/__init__.py
from kajiba.sources.hermes import HermesAdapter
from kajiba.sources.generic import GenericAdapter

_REGISTRY: dict[str, type[SourceAdapter]] = {}

def register(name: str, adapter_cls: type[SourceAdapter]) -> None:
    _REGISTRY[name] = adapter_cls

def get(name: str) -> SourceAdapter:
    if name not in _REGISTRY:
        raise KeyError(f"Unknown source: {name!r}. Available: {list(_REGISTRY)}")
    return _REGISTRY[name]()

# Built-in registrations at import time
register("hermes", HermesAdapter)
register("generic", GenericAdapter)
```

Future community plugins call `from kajiba.sources import register` and add themselves.

### Pattern 3: Contribution Mode as a Strategy Object

The `ContributionManager` selects behavior based on `mode` config, following the Strategy pattern. Do not use inheritance — modes differ only in the decision gate, not in data flow.

```python
# src/kajiba/contribution/manager.py
class ContributionManager:
    def __init__(self, mode: str, consent_level: str, auto_submit: bool):
        self.mode = mode                  # "adhoc" | "continuous"
        self.consent_level = consent_level
        self.auto_submit = auto_submit
        self._queue: list[KajibaRecord] = []

    def accept(self, record: KajibaRecord, quality: QualityResult) -> bool:
        """Returns True if the record should proceed to publish."""
        stripped = ConsentEnforcer.apply(record, self.consent_level)
        if self.mode == "continuous" and self.auto_submit:
            return True                   # pass through immediately
        # ad-hoc: enqueue and wait for user confirmation via CLI
        self._queue.append(stripped)
        return False

    def flush_approved(self) -> list[KajibaRecord]:
        """Return all records the user approved via `kajiba review`."""
        approved, self._queue = self._queue, []
        return approved
```

### Pattern 4: Append-Only Dataset Repository with Catalog Index

The dataset repository is a plain Git repo. Records are never deleted or modified — only appended. The catalog is a generated index file, regenerated on every publish.

```
catalog.json structure:
{
  "schema_version": "1",
  "generated_at": "2026-03-30T...",
  "total_records": 1482,
  "models": {
    "hermes-3-8b": {
      "record_count": 840,
      "tiers": { "gold": 120, "silver": 400, "bronze": 320 },
      "paths": {
        "gold":   "data/by-model/hermes-3-8b/gold/",
        "silver": "data/by-model/hermes-3-8b/silver/",
        "bronze": "data/by-model/hermes-3-8b/bronze/"
      }
    }
  }
}
```

Consumers discover available subsets by reading `catalog.json` before deciding what to clone/download. This avoids needing to traverse the directory tree.

---

## Data Flow

### Contribution Flow (ad-hoc mode)

```
AI Tool Session
     │
     ▼
SourceAdapter.build_session_data(raw)      ← tool-specific normalization
     │ SessionData
     ▼
KajibaCollector.build_record(session_data) ← existing schema construction
     │ KajibaRecord
     ▼
scrubber.scrub_record(record)              ← existing PII removal
     │ scrubbed KajibaRecord + ScrubLog
     ▼
scorer.compute_quality_score(record)       ← existing quality tier
     │ QualityResult
     ▼
ContributionManager.accept(record, quality)
     │ enqueued in review queue
     ▼
[user runs: kajiba review]
     │ user approves/rejects each record
     ▼
ContributionManager.flush_approved()
     │ approved KajibaRecord list
     ▼
ConsentEnforcer.apply(record, consent_level) ← field stripping
     │ consent-stripped KajibaRecord
     ▼
Publisher.write_record(record, repo_path)  ← append JSONL file
     │ written to data/by-model/{model-slug}/{tier}/
     ▼
CatalogBuilder.rebuild(repo_path)          ← regenerate catalog.json
     │
     ▼
git add + commit + push                    ← to dataset repository
```

### Contribution Flow (continuous mode)

Same as above except `ContributionManager.accept()` returns `True` immediately — no review queue — and publish happens automatically after each session ends, subject to the configured consent level and quality tier threshold.

### Consumer Download Flow

```
consumer: git clone kajiba-dataset/        ← full dataset, or
consumer: reads catalog.json               ← discover what exists
consumer: sparse-checkout data/by-model/hermes-3-8b/gold/
consumer: loads *.jsonl files              ← standard format, loadable by
                                              LLaMA-Factory, Axolotl, etc.
```

---

## Scaling Considerations

| Concern | Now (MVP, <10K records) | Later (>100K records) |
|---------|--------------------------|----------------------|
| Storage | JSONL files in git, fine | Git LFS or migrate to Hugging Face Hub dataset repo |
| Catalog | Full `catalog.json` rebuild on every push | Incremental update: only update changed model/tier entries |
| Dedup | SHA-256 submission hash checked client-side | Server-side dedup check endpoint or shared bloom filter |
| Contributor conflicts | Last-write-wins on PR merge | Each contributor writes to a namespaced subdirectory; catalog merge is non-conflicting |
| Discovery | Single `catalog.json` | Add per-model `catalog_fragment.json` files; main catalog aggregates |

**Recommended now:** Keep everything in a plain Git repo with a flat JSONL structure. Git history gives version control for free. When the repo exceeds ~500MB (roughly 200K gold-tier records), evaluate Git LFS or migration to Hugging Face Hub.

---

## Anti-Patterns

### Anti-Pattern 1: Embedding Hermes Calls Directly in Collector

**What:** Keeping `collector.py` with Hermes-specific method signatures (`on_session_start(session_id, model_config)`) as the only entry point.
**Why bad:** Every new source requires forking collector logic rather than adding an adapter. The Collector becomes a maintenance target rather than a stable processing unit.
**Instead:** Collector accepts `SessionData` (a neutral dataclass). Adapters are responsible for constructing `SessionData` from their tool's native format.

### Anti-Pattern 2: Contribution Mode Logic Inside CLI Commands

**What:** Scattering `if auto_submit:` and `if consent_level == "anonymous":` conditionals across individual Click commands.
**Why bad:** Mode behavior is duplicated across commands, diverges silently, and cannot be unit-tested without invoking Click's test runner.
**Instead:** `ContributionManager` is the single authority on mode behavior. CLI commands call `manager.accept()` and `manager.flush_approved()`.

### Anti-Pattern 3: One JSONL File Per Record in Dataset Repo

**What:** Writing one `record_{sha}.jsonl` file per contribution, as the current outbox does.
**Why bad:** A dataset repo with 50K records has 50K files. Git operations (clone, status, log) degrade significantly above ~10K files. Consumer tooling (LLaMA-Factory, Axolotl) expects shard files, not per-record files.
**Instead:** Shard files within each `{model}/{tier}/` directory. A new shard file is opened when the previous exceeds a size threshold (e.g., 50MB or 10K records). Shards are named `shard-0001.jsonl`, `shard-0002.jsonl`.

### Anti-Pattern 4: Mutable Dataset Records

**What:** Allowing contributors to update or delete previously submitted records.
**Why bad:** Breaks reproducibility for consumers who have already loaded the data. Makes `catalog.json` stale. Makes audit trails untrustworthy.
**Instead:** Dataset is append-only. Records are never modified post-publish. If a record was submitted in error, it is added to a `revoked.json` list — consumers filter it out at load time. The original file is never deleted (preserves git history integrity).

### Anti-Pattern 5: Consent Enforcement at Display Time Only

**What:** Stripping fields when rendering a CLI preview but writing the full record to the outbox.
**Why bad:** If the submit/publish step happens without a preview step (e.g., continuous mode), full PII-adjacent data is published.
**Instead:** `ConsentEnforcer.apply()` runs as an explicit pipeline stage before any write to outbox or dataset repo, regardless of mode.

### Anti-Pattern 6: Rebuilding Full Catalog on Every Record

**What:** Scanning the entire `data/` directory tree to rebuild `catalog.json` after each record publish.
**Why bad:** With 10K+ records, this scan becomes slow. Contributors submitting many records at once will wait for repeated full scans.
**Instead:** Publisher increments counts in-memory during a batch run and calls `CatalogBuilder.rebuild()` once at the end of the publish operation, not per-record.

---

## Integration Points

### Inbound (data enters Kajiba)

| Integration | Protocol | How |
|-------------|----------|-----|
| Hermes Agent | Observer / event hooks | `HermesAdapter.register_hooks(agent)` subscribes to session lifecycle events |
| Any AI tool via file drop | Manual / file-based | `GenericAdapter.build_session_data(json.load(file))` — user drops a JSON file, runs `kajiba submit --source generic --file session.json` |
| Future: Cursor, Aider, Continue | Same `SourceAdapter` ABC | Each tool gets its own adapter module in `kajiba/sources/` |

### Outbound (data leaves Kajiba)

| Integration | Protocol | How |
|-------------|----------|-----|
| Dataset repository | Git | `Publisher` writes JSONL files, runs `git add/commit/push` against a locally-cloned dataset repo path |
| Consumer training frameworks (LLaMA-Factory, Axolotl) | JSONL file read | No integration needed — consumers read JSONL directly; `to_sharegpt()` export method already exists on `KajibaRecord` |
| Future: Hugging Face Hub | HF datasets API | Publisher gains a `HuggingFacePublisher` variant — same interface, different backend |

### Configuration

The existing `~/.hermes/config.yaml` is renamed or extended to `~/.kajiba/config.yaml` (source-agnostic path). New keys:

```yaml
# existing
consent_level: full
auto_submit: false
llm_pii_scrub: false
scrub_strictness: standard

# new
contribution_mode: adhoc          # adhoc | continuous
dataset_repo_path: ~/datasets/kajiba-data
min_publish_tier: silver          # bronze | silver | gold
source: hermes                    # which adapter to use by default
```

---

## Suggested Build Order

This ordering reflects hard dependencies: later components require earlier ones to exist.

1. **`sources/base.py` — SourceAdapter ABC + SessionData** (no dependencies)
   Unblocks everything. All other new components depend on this interface.

2. **`sources/hermes.py` — HermesAdapter** (depends on: `base.py`, existing `hermes_integration.py`)
   Migrates the existing Hermes integration to the new interface. Existing tests must still pass. This is the highest-risk step because it touches working code.

3. **Refactor `collector.py`** (depends on: `base.py`)
   Change `KajibaCollector` to accept `SessionData` instead of raw Hermes dicts. All downstream components (scrubber, scorer) are unaffected — they still consume `KajibaRecord`.

4. **`sources/generic.py` — GenericAdapter** (depends on: `base.py`, refactored `collector.py`)
   Validates that the source-agnostic path works with manually-constructed data.

5. **`contribution/consent.py` — ConsentEnforcer** (depends on: `schema.py`)
   Pure function: takes a `KajibaRecord` and consent level, returns a stripped copy. Can be built and tested in isolation.

6. **`contribution/manager.py` — ContributionManager** (depends on: `consent.py`, `scorer.py`)
   Implements ad-hoc and continuous mode behavioral gates.

7. **`publisher/catalog.py` — CatalogBuilder** (depends on: nothing but filesystem)
   Builds `catalog.json` from a directory scan. Testable with fixture directories.

8. **`publisher/git_publisher.py` — Publisher** (depends on: `schema.py`, `catalog.py`)
   Writes JSONL to dataset repo directory structure and invokes git.

9. **CLI extensions** (depends on: all above)
   Add `publish`, `review`, `sources`, `sync` commands. Wire `ContributionManager` and `Publisher` into the existing command group.

10. **Dataset repository scaffolding** (depends on: `Publisher`)
    Initialize the `kajiba-dataset` git repo with `README.md`, `catalog.json`, directory skeleton, and `schemas/v1/`.

---

## Sources

- [HuggingFace — Structure your repository](https://huggingface.co/docs/datasets/en/repository_structure) — canonical reference for how to organize JSONL datasets in a Git repo with YAML-defined splits and configurations (MEDIUM confidence — official HuggingFace docs)
- [LLaMA-Factory data/README.md](https://raw.githubusercontent.com/hiyouga/LLaMA-Factory/main/data/README.md) — real-world dataset catalog format using `dataset_info.json` with per-entry metadata for format, columns, and source (HIGH confidence — official project docs)
- [DataFlow: LLM-Driven Framework](https://arxiv.org/html/2512.16676v1) — reference architecture for multi-source LLM data pipelines with operator categorization, extension ecosystem, and storage abstraction (MEDIUM confidence — peer-reviewed preprint)
- [Python Packaging — Creating and discovering plugins](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/) — official Python guidance on entry_points vs namespace packages for plugin discovery (HIGH confidence — official Python docs, accessed via search)
- [Abstract Base Classes vs Protocols](https://jellis18.github.io/post/2022-01-11-abc-vs-protocol/) — practical comparison of when to use ABC vs Protocol for interface design in Python (MEDIUM confidence — community blog, well-sourced)
- [DVC — Versioning Data and Models](https://doc.dvc.org/use-cases/versioning-data-and-models) — patterns for append-only dataset growth with git-tracked metadata (MEDIUM confidence — official DVC docs)
- [Datasets Should Behave Like Git Repositories](https://towardsdatascience.com/datasets-should-behave-like-git-repositories-9acb83a0dae5/) — principles for treating dataset evolution with version-control discipline (LOW confidence — opinion article, principles are sound but not authoritative)
