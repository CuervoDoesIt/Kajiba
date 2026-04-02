# Phase 3: Dataset Publishing - Research

**Researched:** 2026-03-31
**Domain:** GitHub PR-based dataset contribution workflow, JSONL storage/sharding, catalog indexing, deletion tracking
**Confidence:** HIGH

## Summary

Phase 3 introduces Kajiba's first external network operations: publishing scrubbed outbox records to a GitHub dataset repository via a fork + PR workflow. The phase spans six distinct technical concerns: (1) a `gh` CLI wrapper for authentication checking, forking, cloning, committing, pushing, and PR creation; (2) JSONL file sharding under a `data/{model}/{tier}/` directory hierarchy with deterministic shard assignment; (3) a `catalog.json` index that aggregates model/tier statistics for Phase 5 consumer commands; (4) an auto-generated dataset README.md with license, scrubbing methods, and dynamic statistics; (5) a `deletions.jsonl` index-based deletion mechanism via PR; and (6) consent re-verification as a last-mile privacy gate before data leaves the machine.

The existing codebase provides strong foundations: `subprocess.run()` patterns in `collector.py`, `KajibaRecord.model_dump(mode="json", by_alias=True)` for JSONL serialization, `apply_consent_level()` for re-verification, `QualityMetadata.quality_tier` for directory routing, and `ModelMetadata.model_name` for model directory naming. The primary new infrastructure is a `publisher.py` module encapsulating all GitHub operations and file layout logic, plus two new CLI commands (`publish`, `delete`) wired into the existing Click group.

**Primary recommendation:** Build a standalone `src/kajiba/publisher.py` module with pure functions for file layout, sharding, catalog generation, and README rendering, plus a `GitHubOps` wrapper class that isolates all `subprocess.run(["gh", ...])` calls behind a mockable interface. This separation keeps business logic testable without `gh` installed.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Fork + PR model. User forks the dataset repo. `kajiba publish` clones their fork, adds records, pushes to fork, opens PR to upstream via `gh pr create`. Standard open-source contribution flow.
- **D-02:** GitHub authentication via `gh` CLI only. Require `gh` installed and authenticated (`gh auth login`). No token management in Kajiba. All GitHub operations use `gh api` / `gh pr create`.
- **D-03:** Consent re-verification at publish time. Before writing records to the PR, re-run `apply_consent_level()` on each record. Belt-and-suspenders per Phase 1 D-01. Even manually-placed outbox records get stripped.
- **D-04:** `kajiba publish` workflow: check gh auth -> clone/update fork -> re-verify consent -> write records to `{model}/{tier}/` directories -> update catalog.json -> regenerate README.md -> commit -> push -> open PR.
- **D-05:** Records stored as sharded JSONL files under `data/{model}/{tier}/` directories. Model names normalized to lowercase + hyphens (e.g., "GPT-4o" -> "gpt-4o", "Claude 3.5 Sonnet" -> "claude-3-5-sonnet").
- **D-06:** Sharding strategy is Claude's discretion. Goal: keep files manageable for git (avoid single files > 50MB), deterministic shard assignment, easy merge of new data with existing shards.
- **D-07:** Rich metadata in `catalog.json`: model name, tier, record count, average quality score, hardware distribution, file sizes, shard list, last updated timestamp. Enough for Phase 5 consumer browse/download commands.
- **D-08:** Dataset README.md uses a static template with dynamic stats sections. Template includes License (Apache 2.0), Scrubbing Methods, How to Use prose. Dynamic sections include model coverage table, quality distribution chart, total record counts. Regenerated on each publish.
- **D-09:** Deletion via index file, not physical removal. `kajiba delete <record_id>` appends the ID to `deletions.jsonl` in the dataset repo via PR. Records are NOT physically removed from data shards. Consumers filter out deleted IDs when loading.
- **D-10:** Deletion scope is Claude's discretion. Goal: privacy-friendly, minimal abuse surface. Recommend allowing any record by ID (no identity tracking required).

### Claude's Discretion
- Sharding strategy details (date-based, size-based, or hybrid)
- Deletion scope (any record by ID vs contributor-verified)
- Fork detection and setup flow (what if user hasn't forked yet?)
- PR title/body template content
- Catalog.json schema details (exact field names and types)
- Error handling for network failures during publish

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PRIV-07 | User can request deletion of a contributed record via `kajiba delete <record_id>` | `delete` CLI command appends to `deletions.jsonl` via PR; D-09 deletion index pattern |
| PRIV-08 | Deletion requests are tracked in a deletion index file in the dataset repository | `deletions.jsonl` at repo root with record_id + timestamp + reason fields |
| PUB-01 | Scrubbed records organized as sharded JSONL under `{model}/{tier}/` directories | `publisher.py` file layout with hash-based sharding; D-05 model name normalization |
| PUB-02 | `catalog.json` generated/updated on each publish with models, tiers, counts, metadata | Catalog generation function scans `data/` directory tree; D-07 rich metadata schema |
| PUB-03 | PR-based workflow (not direct push) for review and poisoning defense | Fork + PR via `gh` CLI; D-01 and D-02 authentication flow |
| PUB-04 | Dataset card (README.md) auto-generated with license, scrubbing, quality, coverage | Static Jinja2-free template with f-string interpolation; D-08 template structure |
| PUB-05 | User can publish scrubbed records via `kajiba publish` | Full D-04 workflow: auth check -> clone/update -> consent -> write -> catalog -> README -> commit -> push -> PR |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| click | >=8.0 | CLI framework (already in project) | Established; `publish` and `delete` are new Click commands |
| rich | >=13.0 | Terminal output (already in project) | Progress display during publish workflow |
| pydantic | >=2.0 | Schema validation (already in project) | Record serialization, catalog schema |
| subprocess (stdlib) | 3.11+ | `gh` CLI execution | Already used for `nvidia-smi` in collector.py |
| pathlib (stdlib) | 3.11+ | File system operations | Already used throughout |
| json (stdlib) | 3.11+ | JSONL serialization | Already used throughout |
| hashlib (stdlib) | 3.11+ | Deterministic shard assignment | Already used for record_id in schema.py |
| re (stdlib) | 3.11+ | Model name normalization | Already used in scrubber.py |
| shutil (stdlib) | 3.11+ | Directory operations for clone cleanup | Standard library |
| textwrap (stdlib) | 3.11+ | README template formatting | Standard library |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tempfile (stdlib) | 3.11+ | Temporary clone directory | During publish workflow if no persistent clone |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| subprocess + gh CLI | PyGithub / ghapi | Adds dependency; `gh` is per D-02 locked decision |
| hashlib shard assignment | Date-based sharding | Date sharding creates uneven shard sizes; hash is deterministic and uniform |
| Jinja2 for README | f-string templates | Jinja2 is an unnecessary dependency for a static template with a few dynamic sections |

**Installation:**
No new dependencies required. All libraries are either already in `pyproject.toml` or are Python standard library.

## Architecture Patterns

### Recommended Project Structure
```
src/kajiba/
    publisher.py       # NEW: File layout, sharding, catalog, README generation, gh wrapper
    cli.py             # MODIFIED: Add publish and delete commands
    privacy.py         # EXISTING: apply_consent_level() for re-verification
    schema.py          # EXISTING: KajibaRecord, ModelMetadata, QualityMetadata
tests/
    test_publisher.py  # NEW: Unit tests for publisher module
    test_cli.py        # MODIFIED: CLI integration tests for publish/delete
```

### Pattern 1: GitHubOps Wrapper (Mockable subprocess boundary)
**What:** A class that encapsulates all `subprocess.run(["gh", ...])` calls behind named methods. Each method returns a structured result (success/failure + output).
**When to use:** Every `gh` CLI interaction goes through this class.
**Why:** Isolates the network/process boundary so all business logic can be tested with a mock. The existing `collector.py` subprocess pattern (`capture_output=True, text=True, timeout=N`) is the template.
**Example:**
```python
import logging
import subprocess
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

@dataclass
class GhResult:
    """Result of a gh CLI command."""
    success: bool
    stdout: str
    stderr: str
    returncode: int

class GitHubOps:
    """Wrapper for gh CLI operations.

    All GitHub interactions go through this class so business logic
    is testable without gh installed.
    """

    def __init__(self, upstream_repo: str, timeout: int = 120) -> None:
        self._upstream = upstream_repo
        self._timeout = timeout

    def _run_gh(self, args: list[str]) -> GhResult:
        """Run a gh CLI command and return structured result."""
        try:
            result = subprocess.run(
                ["gh"] + args,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
            return GhResult(
                success=result.returncode == 0,
                stdout=result.stdout.strip(),
                stderr=result.stderr.strip(),
                returncode=result.returncode,
            )
        except FileNotFoundError:
            return GhResult(success=False, stdout="", stderr="gh CLI not found", returncode=-1)
        except subprocess.TimeoutExpired:
            return GhResult(success=False, stdout="", stderr="Command timed out", returncode=-2)

    def check_auth(self) -> GhResult:
        """Check if gh is authenticated."""
        return self._run_gh(["auth", "status"])

    def fork_repo(self) -> GhResult:
        """Create a fork of the upstream repo (idempotent)."""
        return self._run_gh(["repo", "fork", self._upstream, "--clone=false"])

    def clone_fork(self, dest: str) -> GhResult:
        """Clone the user's fork to a local directory."""
        return self._run_gh(["repo", "clone", f"{{owner}}/{self._upstream.split('/')[-1]}", dest])

    def create_pr(self, title: str, body: str, head: str, base: str = "main") -> GhResult:
        """Create a PR from fork to upstream."""
        return self._run_gh([
            "pr", "create",
            "--repo", self._upstream,
            "--title", title,
            "--body", body,
            "--head", head,
            "--base", base,
        ])
```

### Pattern 2: Pure Functions for File Layout and Catalog
**What:** Stateless functions that compute file paths, shard assignments, catalog entries, and README content from input data. No side effects.
**When to use:** All business logic for where records go, what catalog.json contains, and what README.md says.
**Why:** Testable without filesystem or network. Follows the project's established pure-function pattern (privacy.py functions are all pure).
**Example:**
```python
import hashlib
import re

def normalize_model_name(name: str) -> str:
    """Normalize model name to filesystem-safe slug.

    Examples:
        "GPT-4o" -> "gpt-4o"
        "Claude 3.5 Sonnet" -> "claude-3-5-sonnet"
        "Hermes-3-Llama-3.1-8B" -> "hermes-3-llama-3-1-8b"

    Args:
        name: Raw model name from ModelMetadata.

    Returns:
        Lowercase, hyphen-separated, filesystem-safe string.
    """
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)  # Remove special chars except hyphens
    slug = re.sub(r"[\s_.]+", "-", slug)  # Whitespace/underscores/dots to hyphens
    slug = re.sub(r"-+", "-", slug)       # Collapse multiple hyphens
    slug = slug.strip("-")
    return slug


def compute_shard_key(record_id: str, num_shards: int = 256) -> str:
    """Compute deterministic shard filename from record_id.

    Uses SHA-256 of record_id, takes first 2 hex chars as shard number.
    256 shards keeps individual files small while being predictable.

    Args:
        record_id: The record's content-addressable ID.
        num_shards: Number of shard buckets (default 256 = 2 hex chars).

    Returns:
        Shard filename like "shard_a3.jsonl".
    """
    digest = hashlib.sha256(record_id.encode("utf-8")).hexdigest()
    shard_num = int(digest[:2], 16) % num_shards
    return f"shard_{shard_num:02x}.jsonl"


def compute_record_path(model_name: str, quality_tier: str, record_id: str) -> str:
    """Compute the relative path for a record in the dataset repo.

    Args:
        model_name: Raw model name (will be normalized).
        quality_tier: Quality tier string (gold/silver/bronze/review_needed).
        record_id: Record ID for shard assignment.

    Returns:
        Relative path like "data/gpt-4o/gold/shard_a3.jsonl".
    """
    model_dir = normalize_model_name(model_name)
    shard_file = compute_shard_key(record_id)
    return f"data/{model_dir}/{quality_tier}/{shard_file}"
```

### Pattern 3: Staged Workflow with Rich Progress
**What:** The `kajiba publish` command executes a multi-step workflow with progress feedback at each stage, using Rich console output.
**When to use:** The `publish` command orchestration.
**Why:** Network operations are slow and can fail; users need to see what is happening and where failures occur.
**Workflow steps per D-04:**
1. Check `gh auth status` -- fail fast if not authenticated
2. Load outbox records -- fail if empty
3. Re-verify consent on each record (D-03)
4. Clone/update fork (handle "already cloned" case)
5. Write records to `data/{model}/{tier}/` sharded JSONL files
6. Generate/update `catalog.json`
7. Regenerate `README.md`
8. Git add + commit
9. Git push to fork
10. Open PR via `gh pr create`

### Anti-Patterns to Avoid
- **Direct push to upstream:** D-01 explicitly requires fork + PR. Never use `git push` to the upstream repo.
- **Token management in Kajiba:** D-02 says all auth goes through `gh`. Do not accept `GITHUB_TOKEN` env vars or store tokens.
- **Mutating outbox records during publish:** The publish workflow should work on copies. The local outbox is the source of truth.
- **Shell=True in subprocess:** Security risk. Always pass command as list, never as shell string.
- **Blocking on git operations without timeout:** Network operations can hang. Always set `timeout` on `subprocess.run()`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| GitHub authentication | Token storage/refresh | `gh auth status` / `gh auth login` | `gh` handles OAuth, tokens, SSH keys, 2FA -- per D-02 |
| GitHub forking | API calls to GitHub REST API | `gh repo fork` | Handles idempotency, remote setup -- per D-02 |
| PR creation | Direct GitHub API POST | `gh pr create` | Handles auth headers, fork detection, branch resolution -- per D-02 |
| Git operations | Manual git plumbing | `git` CLI via subprocess | Git is installed as prerequisite of `gh`; simpler than GitPython |
| Model name slugification | Full unicode transliteration | Simple regex (re.sub) | Model names are ASCII in practice; no need for python-slugify dependency |

**Key insight:** The `gh` CLI is the entire GitHub integration layer. Kajiba delegates all authentication, forking, and PR creation to `gh`, keeping the codebase free of GitHub API complexity. The tradeoff is that `gh` must be installed and authenticated, but this aligns with the project's "no external services for core" constraint since `gh` is only needed for the optional publish feature.

## Common Pitfalls

### Pitfall 1: gh repo fork idempotency issues
**What goes wrong:** `gh repo fork` behaves differently when the fork already exists vs. first-time creation. The `--clone` flag can fail if the directory already exists. Error messages vary between TTY and non-TTY contexts.
**Why it happens:** The `gh` CLI was designed for interactive use; programmatic use surfaces edge cases.
**How to avoid:** Separate fork creation from clone. Use `gh repo fork --clone=false` to create/verify the fork, then use `git clone` or `git pull` separately. Check for existing clone directory before cloning.
**Warning signs:** "already exists" in stderr, non-zero exit codes on second run.

### Pitfall 2: Consent re-verification ordering
**What goes wrong:** Records are written to the dataset repo before consent is re-verified, or consent is checked but the stripped version is not the one written.
**Why it happens:** The publish workflow has many steps; it is easy to apply consent to a copy but write the original.
**How to avoid:** Per D-03, re-run `apply_consent_level()` on each record immediately before serialization. The consent-verified record is the ONLY thing that gets written to the JSONL shard. Use the same pipeline as `submit`: scrub -> anonymize -> jitter -> consent strip.
**Warning signs:** Outbox records contain fields that should have been stripped at the given consent level.

### Pitfall 3: JSONL append vs. overwrite
**What goes wrong:** Publishing to an existing shard file overwrites previous records instead of appending.
**Why it happens:** Using `write_text()` instead of appending mode, or reading the existing file and losing data.
**How to avoid:** Open shard files in append mode (`"a"`) for new records. For dedup, read existing record_ids from the shard first, skip duplicates, then append only new records.
**Warning signs:** Record counts decrease after publish; catalog shows fewer records than expected.

### Pitfall 4: Git merge conflicts in JSONL files
**What goes wrong:** Multiple contributors publish to the same shard file simultaneously, causing merge conflicts in PRs.
**Why it happens:** JSONL files are append-only but git treats them as regular text files subject to merge conflicts.
**How to avoid:** The 256-shard strategy distributes records across many files, reducing collision probability. Each PR adds to different shards based on record_id hashes. The PR review process handles remaining conflicts manually. This is acceptable for a community dataset at early scale.
**Warning signs:** PR shows merge conflicts in shard files.

### Pitfall 5: Missing model name or quality tier
**What goes wrong:** Records without `model.model_name` or `quality.quality_tier` cannot be routed to the correct directory.
**Why it happens:** Optional fields in KajibaRecord; records from early pipeline versions or manual creation may lack these.
**How to avoid:** Default model to `"unknown"` and tier to `"review_needed"` when missing. Log a warning for each such record.
**Warning signs:** Records silently dropped during publish; empty directories.

### Pitfall 6: Cross-platform path separators
**What goes wrong:** JSONL path computation uses backslashes on Windows, creating wrong directory structure in the dataset repo.
**Why it happens:** `pathlib.Path` uses OS-native separators; Windows uses backslashes.
**How to avoid:** Use forward slashes explicitly in all dataset repo path construction (string concatenation or PurePosixPath). The dataset repo is a git repo which always uses forward slashes.
**Warning signs:** Directories with backslash-containing names on Windows; tests pass on Linux but fail on Windows.

## Code Examples

Verified patterns from existing codebase:

### Subprocess Pattern (from collector.py)
```python
# Source: src/kajiba/collector.py lines 61-88
result = subprocess.run(
    ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
    capture_output=True,
    text=True,
    timeout=10,
)
if result.returncode == 0 and result.stdout.strip():
    # Process output
    pass

# Exception handling pattern:
try:
    result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, timeout=30)
except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
    logger.debug("gh CLI not available")
```

### Record Serialization Pattern (from cli.py submit)
```python
# Source: src/kajiba/cli.py lines 456-457
record_json = final.model_dump(mode="json", by_alias=True)
outbox_file.write_text(json.dumps(record_json, ensure_ascii=False) + "\n", encoding="utf-8")
```

### Consent Re-verification Pattern (from cli.py submit)
```python
# Source: src/kajiba/cli.py lines 430-434
# Read consent level from record's submission metadata
consent_level = "full"
if record.submission and record.submission.consent_level:
    consent_level = record.submission.consent_level
final = apply_consent_level(jittered, consent_level)
```

### Full Privacy Pipeline (from cli.py submit, lines 426-434)
```python
# Apply full privacy pipeline: scrub -> anonymize -> jitter -> consent strip
anonymized = anonymize_hardware(scrubbed)
jittered = jitter_timestamp(anonymized)

consent_level = "full"
if record.submission and record.submission.consent_level:
    consent_level = record.submission.consent_level
final = apply_consent_level(jittered, consent_level)
```

### Catalog.json Schema (recommended)
```json
{
  "schema_version": "0.1.0",
  "generated_at": "2026-03-31T12:00:00Z",
  "total_records": 1234,
  "total_size_bytes": 52428800,
  "models": {
    "hermes-3-llama-3-1-8b": {
      "display_name": "Hermes-3-Llama-3.1-8B",
      "tiers": {
        "gold": {
          "record_count": 150,
          "avg_quality_score": 0.85,
          "shards": ["shard_0a.jsonl", "shard_1f.jsonl"],
          "total_size_bytes": 2097152,
          "last_updated": "2026-03-31T12:00:00Z"
        },
        "silver": { "..." : "..." }
      },
      "total_records": 500,
      "hardware_distribution": {
        "NVIDIA RTX 40xx": 120,
        "NVIDIA RTX 30xx": 80,
        "Apple Silicon": 50
      }
    }
  },
  "quality_distribution": {
    "gold": 400,
    "silver": 500,
    "bronze": 300,
    "review_needed": 34
  },
  "deletions_count": 5
}
```

### Deletions.jsonl Entry Schema
```json
{"record_id": "kajiba_a1b2c3d4e5f6", "deleted_at": "2026-03-31T14:00:00Z", "reason": "contributor_request"}
```

### Dataset README.md Template Structure
```markdown
# Kajiba Community Dataset

> Real-world AI session data for local model fine-tuning

## License

Apache 2.0

## About

[Static prose about what Kajiba is and how data is collected]

## Privacy & Scrubbing

[Static prose: regex PII scrubbing, hardware anonymization, consent levels, timestamp jittering]

## Dataset Statistics

<!-- AUTO-GENERATED: Do not edit below this line -->

| Metric | Value |
|--------|-------|
| Total Records | {total_records} |
| Models | {model_count} |
| Last Updated | {last_updated} |

### Quality Distribution

| Tier | Count | Percentage |
|------|-------|------------|
| Gold | {gold_count} | {gold_pct}% |
| Silver | {silver_count} | {silver_pct}% |
| Bronze | {bronze_count} | {bronze_pct}% |

### Model Coverage

| Model | Records | Avg Score | Top Tier |
|-------|---------|-----------|----------|
{model_rows}

## How to Use

[Static prose: loading JSONL, filtering by tier, handling deletions.jsonl]

## Deletions

Records listed in `deletions.jsonl` have been requested for removal.
Consumers MUST filter these record IDs when loading data.

## Contributing

See the [Kajiba project](https://github.com/CuervoDoesIt/Kajiba) for the data pipeline.
```

## Sharding Strategy Recommendation (Claude's Discretion)

**Recommendation: Hash-based sharding with 256 buckets.**

| Property | Value |
|----------|-------|
| Algorithm | SHA-256 of `record_id`, first 2 hex chars as shard index |
| Bucket count | 256 (0x00 to 0xff) |
| Filename pattern | `shard_{hex}.jsonl` (e.g., `shard_a3.jsonl`) |
| Max expected file size | ~200KB per shard at 50K records (well under 50MB git limit) |
| Determinism | Same record always maps to same shard (content-addressable) |
| Merge friendliness | Different contributors touch different shards (low collision) |

**Why not date-based:** Date sharding creates uneven distributions (busy days get huge shards) and does not help with merge conflicts.

**Why not size-based:** Size-based sharding requires reading existing files to decide where to put new records, and shard boundaries drift over time.

**Why 256:** 2 hex characters = 256 buckets. At 50,000 records, each shard averages ~195 records. At 1 record ~ 2-5KB, each shard is 400KB-1MB. Well within git's comfort zone. Scales to 500K+ records before any shard approaches 50MB.

## Deletion Scope Recommendation (Claude's Discretion)

**Recommendation: Allow deletion of any record by ID, no contributor verification.**

**Rationale:**
- Kajiba does not track contributor identity (no accounts, no personal identity tracking -- per Out of Scope requirements).
- Requiring proof of contribution would need identity infrastructure that contradicts the project's privacy-first design.
- The deletion mechanism is via PR, so maintainers review each deletion request. This provides a human gate against abuse.
- False deletion requests (requesting deletion of someone else's record) are low-impact: the record is soft-deleted, not physically removed. A maintainer can reverse a deletion by rejecting the PR or removing the entry.
- This matches GDPR "right to erasure" spirit: anyone can request, but it goes through review.

**Abuse mitigation:** PR review. Mass deletion requests are visible in the PR diff and can be rejected.

## Fork Detection Recommendation (Claude's Discretion)

**Recommendation: Three-phase fork detection.**

1. **Check if fork exists:** Use `gh api repos/{user}/{repo_name}` to check if the user already has a fork.
2. **Create fork if needed:** Use `gh repo fork {upstream} --clone=false`. This is idempotent -- if fork exists, it outputs "already exists" with exit code 0.
3. **Clone or pull:** Check if local clone directory exists. If yes, `git pull`. If no, `git clone`.

The local clone directory should be stored at a well-known path: `~/.hermes/kajiba/dataset-clone/`. This avoids re-cloning on every publish and enables incremental updates.

## PR Template Recommendation (Claude's Discretion)

**Publish PR:**
```
Title: "kajiba: add {N} record(s) [{model_list}]"
Body:
  ## Records Added
  - {N} new record(s)
  - Models: {comma-separated model names}
  - Tiers: {comma-separated tiers}

  ## Catalog Updated
  - catalog.json regenerated
  - README.md regenerated

  ## Consent Verification
  All records passed consent re-verification before inclusion.

  ---
  *Generated by Kajiba v{version}*
```

**Deletion PR:**
```
Title: "kajiba: delete record {record_id}"
Body:
  ## Deletion Request
  - Record ID: {record_id}
  - Requested at: {timestamp}

  This adds the record ID to `deletions.jsonl`. The record data
  remains in shard files but consumers MUST filter deleted IDs.

  ---
  *Generated by Kajiba v{version}*
```

## Error Handling Recommendation (Claude's Discretion)

| Failure Point | User Experience | Recovery |
|---------------|-----------------|----------|
| `gh` not installed | "Error: gh CLI not found. Install from https://cli.github.com/" | Exit with clear message |
| `gh` not authenticated | "Error: Not authenticated. Run `gh auth login` first." | Exit with clear message |
| Fork creation fails | "Error: Could not fork {repo}. Check your GitHub permissions." | Exit with error details |
| Clone/pull fails | "Error: Could not clone/update fork. Check network connection." | Exit; user retries |
| Push fails | "Error: Push to fork failed. {stderr}" | Exit; user retries |
| PR creation fails | "Records committed to fork but PR creation failed. Create PR manually at {url}" | Partial success: data is on fork |
| No outbox records | "No records to publish. Submit records first with `kajiba submit`." | Exit with guidance |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Direct GitHub API tokens | `gh` CLI with `gh auth login` | 2020+ | No token management in applications |
| GitPython library | `subprocess.run(["git", ...])` | Project convention | No extra dependency; matches collector.py pattern |
| Single large JSONL file | Sharded JSONL with hash-based routing | Common in HF datasets | Avoids git performance issues with large files |
| Physical deletion | Soft deletion via index file | GDPR-era practice | Simpler, auditable, reversible |

**Deprecated/outdated:**
- `hub` CLI: Replaced by `gh` CLI. Do not use.
- Direct `requests` calls to GitHub API: `gh api` wraps authentication and pagination.

## Open Questions

1. **Dataset repository name and owner**
   - What we know: The project is at `CuervoDoesIt/Kajiba` on GitHub. The spec mentions `NousResearch/kajiba-community` as a future HF dataset.
   - What's unclear: The exact GitHub repository name for the dataset repo (e.g., `CuervoDoesIt/kajiba-dataset`).
   - Recommendation: Make the upstream repo URL configurable (default in config, overridable via CLI flag). Store in `~/.hermes/config.yaml` under `kajiba.dataset_repo`. This allows the community to point at different dataset repos.

2. **Branch naming for PRs**
   - What we know: PRs need a branch on the fork.
   - What's unclear: Should each publish create a unique branch? What naming convention?
   - Recommendation: Use `kajiba/publish-{timestamp}` (e.g., `kajiba/publish-20260331-1422`) for publish PRs and `kajiba/delete-{record_id_short}` for deletion PRs. Unique branches avoid conflicts with previous unpublished branches.

3. **Existing clone directory handling**
   - What we know: Re-cloning the entire repo on every publish is wasteful.
   - What's unclear: How to handle stale clones, upstream changes, diverged state.
   - Recommendation: Store clone at `~/.hermes/kajiba/dataset-clone/`. On publish: check if directory exists and is a git repo. If yes, `git fetch origin && git reset --hard origin/main` to sync. If no, clone fresh. This is safe because the clone only contains published data, never local work.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | Yes | 3.13.3 | -- |
| pip | Package install | Yes | 26.0.1 | -- |
| git | Clone, commit, push | Yes | 2.50.0 | -- |
| gh (GitHub CLI) | Fork, PR, auth | **No** | -- | Cannot publish without it; graceful error message |
| pytest | Testing | Yes | (in dev deps) | -- |

**Missing dependencies with no fallback:**
- `gh` CLI is NOT installed on the development machine. The publish/delete commands MUST detect this gracefully and provide a clear installation message. All `gh`-dependent functionality must degrade gracefully. Tests MUST mock subprocess calls rather than relying on `gh` being installed.

**Missing dependencies with fallback:**
- None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=7.0 |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `python -m pytest tests/test_publisher.py tests/test_cli.py -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PRIV-07 | `kajiba delete <record_id>` creates deletion entry | unit + CLI integration | `python -m pytest tests/test_publisher.py::TestDeletion tests/test_cli.py::TestDeleteCommand -x` | Wave 0 |
| PRIV-08 | Deletion tracked in `deletions.jsonl` | unit | `python -m pytest tests/test_publisher.py::TestDeletionIndex -x` | Wave 0 |
| PUB-01 | Records organized as sharded JSONL under `{model}/{tier}/` | unit | `python -m pytest tests/test_publisher.py::TestFileLayout tests/test_publisher.py::TestSharding -x` | Wave 0 |
| PUB-02 | `catalog.json` generated with models, tiers, counts | unit | `python -m pytest tests/test_publisher.py::TestCatalog -x` | Wave 0 |
| PUB-03 | PR-based workflow via fork | unit (mocked gh) | `python -m pytest tests/test_publisher.py::TestGitHubOps -x` | Wave 0 |
| PUB-04 | README.md auto-generated | unit | `python -m pytest tests/test_publisher.py::TestReadmeGeneration -x` | Wave 0 |
| PUB-05 | `kajiba publish` end-to-end | CLI integration (mocked gh) | `python -m pytest tests/test_cli.py::TestPublishCommand -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_publisher.py tests/test_cli.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_publisher.py` -- covers PUB-01 through PUB-05, PRIV-07, PRIV-08 (new file)
- [ ] Test fixtures: outbox record files for publish testing
- [ ] Mock/patch infrastructure for `subprocess.run` calls to `gh` and `git`

## Sources

### Primary (HIGH confidence)
- `src/kajiba/cli.py` -- Current CLI structure, outbox loading, privacy pipeline, Click patterns
- `src/kajiba/schema.py` -- KajibaRecord, ModelMetadata, QualityMetadata, serialization patterns
- `src/kajiba/privacy.py` -- apply_consent_level(), anonymize_hardware(), jitter_timestamp()
- `src/kajiba/collector.py` lines 61-88 -- subprocess.run() pattern with timeout and error handling
- `tests/test_cli.py` -- Test patterns: CliRunner, monkeypatch for directory paths, fixture helpers

### Secondary (MEDIUM confidence)
- [gh repo fork documentation](https://cli.github.com/manual/gh_repo_fork) -- Fork command flags and behavior
- [gh pr create documentation](https://cli.github.com/manual/gh_pr_create) -- PR creation flags including `--repo` for cross-fork PRs
- [gh auth status documentation](https://cli.github.com/manual/gh_auth_status) -- Authentication checking, exit codes
- [GitHub CLI triangular workflow support](https://www.infoq.com/news/2025/06/GitHub-CLI-Triangular-Workflows/) -- Enhanced fork+PR workflow in gh CLI (2025)
- [GitHub REST API forks endpoint](https://docs.github.com/en/rest/repos/forks) -- `GET /repos/{owner}/{repo}/forks` for fork checking

### Tertiary (LOW confidence)
- [gh repo fork idempotency issues](https://github.com/cli/cli/issues/4560) -- Known quirks with `--clone` flag on existing forks
- [gh auth status exit code bug](https://github.com/cli/cli/issues/8845) -- Some versions return wrong exit codes; version-dependent behavior
- [gh pr create from different fork](https://mikefrobbins.com/2025/08/21/how-to-open-a-pr-in-a-different-fork-with-the-github-cli/) -- Using `--head` flag for cross-fork PRs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries are already in the project or stdlib; no new dependencies
- Architecture: HIGH - Patterns directly derived from existing codebase conventions (publisher.py follows privacy.py pattern, subprocess follows collector.py pattern)
- Pitfalls: HIGH - gh CLI idempotency and cross-platform path issues are well-documented; consent ordering verified against existing code
- Sharding strategy: MEDIUM - Hash-based sharding is standard practice but the specific 256-bucket choice is a recommendation based on estimated scale
- Deletion mechanism: HIGH - Soft deletion via index file is standard GDPR-era practice; PR review provides abuse gate

**Research date:** 2026-03-31
**Valid until:** 2026-04-30 (stable domain; gh CLI API is mature)
