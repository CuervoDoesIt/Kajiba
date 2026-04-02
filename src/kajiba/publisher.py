"""Dataset publishing logic for the Kajiba community pipeline.

This module contains all pure business logic for dataset file layout,
sharding, catalog generation, README generation, deletion tracking,
and the GitHubOps wrapper class that isolates all gh/git CLI
interactions behind a mockable interface.

Functions in this module are used by the ``kajiba publish`` and
``kajiba delete`` CLI commands to write records into the correct
directory structure, update the catalog index, regenerate the dataset
card, and interact with GitHub via the ``gh`` CLI.
"""

import hashlib
import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from kajiba.schema import SCHEMA_VERSION

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_NUM_SHARDS = 256
"""Number of shards used for deterministic record distribution."""

DEFAULT_DATASET_REPO = "CuervoDoesIt/kajiba-dataset"
"""Default upstream dataset repository on GitHub."""

CLONE_DIR = Path.home() / ".hermes" / "kajiba" / "dataset-clone"
"""Persistent clone location for the dataset fork."""


# ---------------------------------------------------------------------------
# GhResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class GhResult:
    """Result of a gh or git CLI command.

    Attributes:
        success: Whether the command returned exit code 0.
        stdout: Standard output from the command.
        stderr: Standard error from the command.
        returncode: Exit code (-1 for FileNotFoundError, -2 for timeout).
    """

    success: bool
    stdout: str
    stderr: str
    returncode: int


# ---------------------------------------------------------------------------
# GitHubOps class
# ---------------------------------------------------------------------------


class GitHubOps:
    """Wrapper around gh and git CLI commands for dataset publishing.

    All GitHub and git operations are isolated here so they can be
    mocked in tests. Every method returns a ``GhResult`` with structured
    success/failure information.

    Example::

        ops = GitHubOps("CuervoDoesIt/kajiba-dataset")
        auth = ops.check_auth()
        if not auth.success:
            print("Please run: gh auth login")
    """

    def __init__(self, upstream_repo: str, timeout: int = 120) -> None:
        """Initialize GitHubOps.

        Args:
            upstream_repo: The upstream dataset repository (e.g. "owner/repo").
            timeout: Timeout in seconds for subprocess commands.
        """
        self._upstream = upstream_repo
        self._timeout = timeout

    def _run_gh(self, args: list[str]) -> GhResult:
        """Run a gh CLI command and return a structured result.

        Args:
            args: Arguments to pass after ``gh`` (e.g. ["auth", "status"]).

        Returns:
            GhResult with success, stdout, stderr, and returncode.
        """
        try:
            result = subprocess.run(
                ["gh"] + args,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
            return GhResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
            )
        except FileNotFoundError:
            return GhResult(
                success=False,
                stdout="",
                stderr="gh CLI not found. Install from https://cli.github.com/",
                returncode=-1,
            )
        except subprocess.TimeoutExpired:
            return GhResult(
                success=False,
                stdout="",
                stderr="Command timed out",
                returncode=-2,
            )

    def _run_git(self, args: list[str], cwd: Optional[str] = None) -> GhResult:
        """Run a git CLI command and return a structured result.

        Args:
            args: Arguments to pass after ``git`` (e.g. ["clone", url]).
            cwd: Optional working directory for the command.

        Returns:
            GhResult with success, stdout, stderr, and returncode.
        """
        try:
            result = subprocess.run(
                ["git"] + args,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=cwd,
            )
            return GhResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
            )
        except FileNotFoundError:
            return GhResult(
                success=False,
                stdout="",
                stderr="git CLI not found",
                returncode=-1,
            )
        except subprocess.TimeoutExpired:
            return GhResult(
                success=False,
                stdout="",
                stderr="Command timed out",
                returncode=-2,
            )

    def check_auth(self) -> GhResult:
        """Check if the user is authenticated with gh.

        Returns:
            GhResult from ``gh auth status``.
        """
        return self._run_gh(["auth", "status"])

    def fork_repo(self) -> GhResult:
        """Fork the upstream dataset repository (idempotent).

        Returns:
            GhResult from ``gh repo fork --clone=false``.
        """
        return self._run_gh(["repo", "fork", self._upstream, "--clone=false"])

    def clone_fork(self, dest: str, fork_url: str) -> GhResult:
        """Clone a fork to a local directory.

        Args:
            dest: Destination directory path.
            fork_url: URL of the forked repository.

        Returns:
            GhResult from ``git clone``.
        """
        return self._run_git(["clone", fork_url, dest])

    def pull_latest(self, repo_dir: str) -> GhResult:
        """Fetch and reset to origin/main in the local clone.

        Args:
            repo_dir: Path to the local repository clone.

        Returns:
            GhResult from the last command (git reset).
        """
        fetch_result = self._run_git(["fetch", "origin"], cwd=repo_dir)
        if not fetch_result.success:
            return fetch_result
        return self._run_git(["reset", "--hard", "origin/main"], cwd=repo_dir)

    def create_branch(self, repo_dir: str, branch_name: str) -> GhResult:
        """Create and checkout a new branch.

        Args:
            repo_dir: Path to the local repository clone.
            branch_name: Name of the new branch.

        Returns:
            GhResult from ``git checkout -b``.
        """
        return self._run_git(["checkout", "-b", branch_name], cwd=repo_dir)

    def commit_all(self, repo_dir: str, message: str) -> GhResult:
        """Stage all changes and commit.

        Args:
            repo_dir: Path to the local repository clone.
            message: Commit message.

        Returns:
            GhResult from ``git commit``.
        """
        add_result = self._run_git(["add", "."], cwd=repo_dir)
        if not add_result.success:
            return add_result
        return self._run_git(["commit", "-m", message], cwd=repo_dir)

    def push_branch(self, repo_dir: str, branch_name: str) -> GhResult:
        """Push a branch to origin.

        Args:
            repo_dir: Path to the local repository clone.
            branch_name: Name of the branch to push.

        Returns:
            GhResult from ``git push -u origin``.
        """
        return self._run_git(["push", "-u", "origin", branch_name], cwd=repo_dir)

    def create_pr(self, title: str, body: str, head: str, base: str = "main") -> GhResult:
        """Create a pull request against the upstream repository.

        Args:
            title: PR title.
            body: PR body (markdown).
            head: Head branch (e.g. "user:branch-name").
            base: Base branch (default "main").

        Returns:
            GhResult from ``gh pr create``.
        """
        return self._run_gh([
            "pr", "create",
            "--repo", self._upstream,
            "--title", title,
            "--body", body,
            "--head", head,
            "--base", base,
        ])

    def get_username(self) -> GhResult:
        """Get the authenticated GitHub username.

        Returns:
            GhResult from ``gh api user`` with login in stdout.
        """
        return self._run_gh(["api", "user", "-q", ".login"])


# ---------------------------------------------------------------------------
# Pure functions — file layout and sharding
# ---------------------------------------------------------------------------


def normalize_model_name(name: str) -> str:
    """Normalize a model name to a filesystem-safe slug.

    Lowercases, replaces non-alphanumeric characters (except existing
    hyphens) with hyphens, collapses multiple hyphens, and strips
    leading/trailing hyphens.

    Args:
        name: The raw model name (e.g. "Claude 3.5 Sonnet").

    Returns:
        Filesystem-safe slug (e.g. "claude-3-5-sonnet").
    """
    slug = name.strip().lower()
    # Replace whitespace, dots, and underscores with hyphens
    slug = re.sub(r"[\s._]+", "-", slug)
    # Remove all remaining non-alphanumeric, non-hyphen characters
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    # Collapse multiple hyphens
    slug = re.sub(r"-{2,}", "-", slug)
    # Strip leading/trailing hyphens
    slug = slug.strip("-")
    return slug


def compute_shard_key(record_id: str, num_shards: int = DEFAULT_NUM_SHARDS) -> str:
    """Compute a deterministic shard filename for a record ID.

    Uses SHA-256 of the record_id. The first 2 hex characters are
    converted to an integer modulo ``num_shards`` to pick the shard.

    Args:
        record_id: The record's unique identifier.
        num_shards: Number of shards to distribute across (default 256).

    Returns:
        Shard filename like ``shard_a3.jsonl``.
    """
    digest = hashlib.sha256(record_id.encode("utf-8")).hexdigest()
    shard_num = int(digest[:2], 16) % num_shards
    return f"shard_{shard_num:02x}.jsonl"


def compute_record_path(
    model_name: Optional[str],
    quality_tier: Optional[str],
    record_id: str,
) -> str:
    """Compute the relative file path for a record in the dataset repo.

    Uses forward slashes for cross-platform compatibility (not pathlib).

    Args:
        model_name: The model name (or None for "unknown").
        quality_tier: The quality tier (or None for "review_needed").
        record_id: The record's unique identifier (for shard computation).

    Returns:
        Relative path like ``data/gpt-4o/gold/shard_a3.jsonl``.
    """
    model_dir = normalize_model_name(model_name) if model_name else "unknown"
    if not model_dir:
        model_dir = "unknown"
    tier = quality_tier if quality_tier else "review_needed"
    shard_file = compute_shard_key(record_id)
    return f"data/{model_dir}/{tier}/{shard_file}"


def write_records_to_shards(repo_root: Path, records: list[dict]) -> int:
    """Write record dicts to the appropriate shard files under repo_root.

    For each record: extracts model_name and quality_tier, computes the
    relative path, creates directories, checks for duplicate record_ids,
    and appends the record as a JSON line. Records without a record_id
    are skipped.

    Args:
        repo_root: Root directory of the dataset repository clone.
        records: List of record dictionaries to write.

    Returns:
        Number of records actually written (excludes skipped/dedup).
    """
    written = 0
    for record in records:
        record_id = record.get("record_id")
        if not record_id:
            logger.warning("Skipping record without record_id")
            continue

        model_name = None
        model_data = record.get("model")
        if model_data and isinstance(model_data, dict):
            model_name = model_data.get("model_name")

        quality_tier = None
        quality_data = record.get("quality")
        if quality_data and isinstance(quality_data, dict):
            quality_tier = quality_data.get("quality_tier")

        rel_path = compute_record_path(model_name, quality_tier, record_id)
        # Use Path for filesystem operations (split on forward slashes for cross-platform)
        abs_path = repo_root / Path(*rel_path.split("/"))
        abs_path.parent.mkdir(parents=True, exist_ok=True)

        # Check for duplicate record_id in existing shard
        existing_ids: set[str] = set()
        if abs_path.exists():
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                existing_record = json.loads(line)
                                existing_id = existing_record.get("record_id")
                                if existing_id:
                                    existing_ids.add(existing_id)
                            except json.JSONDecodeError:
                                continue
            except OSError:
                logger.warning("Could not read existing shard %s", abs_path)

        if record_id in existing_ids:
            logger.debug("Skipping duplicate record_id %s in %s", record_id, rel_path)
            continue

        # Append record as JSON line
        with open(abs_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        written += 1

    return written


# ---------------------------------------------------------------------------
# Catalog generation
# ---------------------------------------------------------------------------


def generate_catalog(repo_root: Path) -> dict:
    """Scan the data/ directory tree and produce a catalog dict.

    The catalog contains per-model and per-tier statistics including
    record counts, average quality scores, hardware distribution,
    shard lists, and file sizes.

    Args:
        repo_root: Root directory of the dataset repository clone.

    Returns:
        Catalog dictionary suitable for writing as catalog.json.
    """
    data_dir = repo_root / "data"
    models: dict = {}
    quality_distribution: dict[str, int] = {
        "gold": 0,
        "silver": 0,
        "bronze": 0,
        "review_needed": 0,
    }
    total_records = 0
    total_size_bytes = 0

    if data_dir.exists() and data_dir.is_dir():
        for model_dir in sorted(data_dir.iterdir()):
            if not model_dir.is_dir():
                continue
            model_slug = model_dir.name
            model_info: dict = {
                "display_name": model_slug,
                "tiers": {},
                "total_records": 0,
                "hardware_distribution": {},
                "parameter_counts": [],
                "quantizations": [],
                "context_windows": [],
            }

            for tier_dir in sorted(model_dir.iterdir()):
                if not tier_dir.is_dir():
                    continue
                tier_name = tier_dir.name
                tier_info: dict = {
                    "record_count": 0,
                    "avg_quality_score": 0.0,
                    "shards": [],
                    "total_size_bytes": 0,
                    "last_updated": None,
                }
                quality_scores: list[float] = []

                for shard_file in sorted(tier_dir.glob("shard_*.jsonl")):
                    if not shard_file.is_file():
                        continue
                    tier_info["shards"].append(shard_file.name)
                    file_size = shard_file.stat().st_size
                    tier_info["total_size_bytes"] += file_size
                    total_size_bytes += file_size

                    # Track last modified time
                    mtime = datetime.fromtimestamp(
                        shard_file.stat().st_mtime, tz=UTC,
                    ).isoformat()
                    if tier_info["last_updated"] is None or mtime > tier_info["last_updated"]:
                        tier_info["last_updated"] = mtime

                    # Read records from shard
                    try:
                        with open(shard_file, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue
                                try:
                                    rec = json.loads(line)
                                except json.JSONDecodeError:
                                    continue
                                tier_info["record_count"] += 1
                                total_records += 1
                                model_info["total_records"] += 1

                                # Quality score
                                q = rec.get("quality")
                                if q and isinstance(q, dict):
                                    cs = q.get("composite_score")
                                    if cs is not None:
                                        quality_scores.append(float(cs))

                                # Hardware distribution
                                hw = rec.get("hardware")
                                if hw and isinstance(hw, dict):
                                    gpu = hw.get("gpu_name")
                                    if gpu:
                                        model_info["hardware_distribution"][gpu] = (
                                            model_info["hardware_distribution"].get(gpu, 0) + 1
                                        )

                                # Update display_name from first record with model metadata
                                m = rec.get("model")
                                if m and isinstance(m, dict):
                                    mn = m.get("model_name")
                                    if mn and model_info["display_name"] == model_slug:
                                        model_info["display_name"] = mn

                                    # Model metadata enrichment (CONS-02)
                                    pc = m.get("parameter_count")
                                    if pc and pc not in model_info["parameter_counts"]:
                                        model_info["parameter_counts"].append(pc)
                                    qt = m.get("quantization")
                                    if qt and qt not in model_info["quantizations"]:
                                        model_info["quantizations"].append(qt)
                                    cw = m.get("context_window")
                                    if cw and cw not in model_info["context_windows"]:
                                        model_info["context_windows"].append(cw)

                    except OSError:
                        logger.warning("Could not read shard %s", shard_file)

                # Compute average quality score
                if quality_scores:
                    tier_info["avg_quality_score"] = round(
                        sum(quality_scores) / len(quality_scores), 4,
                    )

                # Update quality distribution
                tier_count = tier_info["record_count"]
                if tier_name in quality_distribution:
                    quality_distribution[tier_name] += tier_count
                else:
                    quality_distribution[tier_name] = tier_count

                model_info["tiers"][tier_name] = tier_info

            if model_info["total_records"] > 0:
                models[model_slug] = model_info

    # Count deletions
    deletions_count = 0
    deletions_file = repo_root / "deletions.jsonl"
    if deletions_file.exists():
        try:
            with open(deletions_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        deletions_count += 1
        except OSError:
            logger.warning("Could not read deletions.jsonl")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "total_records": total_records,
        "total_size_bytes": total_size_bytes,
        "models": models,
        "quality_distribution": quality_distribution,
        "deletions_count": deletions_count,
    }


# ---------------------------------------------------------------------------
# README generation
# ---------------------------------------------------------------------------


def generate_readme(catalog: dict) -> str:
    """Generate a dataset README.md from catalog data.

    Uses f-string interpolation (no Jinja2). Static sections cover the
    license, privacy, and usage. Dynamic sections include statistics,
    quality distribution, and model coverage tables.

    Args:
        catalog: Catalog dictionary from ``generate_catalog()``.

    Returns:
        Markdown string for the dataset README.md.
    """
    total_records = catalog.get("total_records", 0)
    models = catalog.get("models", {})
    num_models = len(models)
    generated_at = catalog.get("generated_at", "unknown")
    quality_dist = catalog.get("quality_distribution", {})
    deletions_count = catalog.get("deletions_count", 0)

    # Build quality distribution table rows
    quality_rows = ""
    for tier in ["gold", "silver", "bronze", "review_needed"]:
        count = quality_dist.get(tier, 0)
        pct = f"{count / total_records * 100:.1f}" if total_records > 0 else "0.0"
        quality_rows += f"| {tier} | {count} | {pct}% |\n"

    # Build model coverage table rows
    model_rows = ""
    for slug, info in sorted(models.items()):
        display = info.get("display_name", slug)
        model_total = info.get("total_records", 0)
        # Compute average score across tiers
        scores = []
        top_tier = "review_needed"
        tier_priority = {"gold": 4, "silver": 3, "bronze": 2, "review_needed": 1}
        for tier_name, tier_info in info.get("tiers", {}).items():
            avg = tier_info.get("avg_quality_score", 0)
            if avg > 0:
                scores.append(avg)
            if tier_priority.get(tier_name, 0) > tier_priority.get(top_tier, 0):
                top_tier = tier_name
        avg_score = f"{sum(scores) / len(scores):.2f}" if scores else "N/A"
        model_rows += f"| {display} | {model_total} | {avg_score} | {top_tier} |\n"

    readme = f"""# Kajiba Community Dataset

A community-contributed dataset of real-world AI-assisted coding sessions for local model fine-tuning.

## License

This dataset is released under the **Apache 2.0** license. See [LICENSE](LICENSE) for details.

## About

Kajiba is an open-source, model-agnostic data pipeline that collects AI-assisted coding session data -- prompts, responses, tool calls, model configurations, and hardware profiles -- contributed by developers to accelerate local model fine-tuning.

Every record in this dataset has been:
- **PII-scrubbed** using regex-based pattern matching (file paths, API keys, emails, etc.)
- **Consent-verified** at both submit and publish time
- **Quality-scored** with a composite score from 5 weighted sub-dimensions
- **Hardware-anonymized** (GPU generalized to family, RAM/VRAM rounded, OS family-only)

## Privacy & Scrubbing

All records pass through a multi-layer privacy pipeline before reaching this repository:

1. **Regex scrubbing** -- 7 pattern categories (paths, keys, network, emails, phone, crypto, connection strings)
2. **Consent enforcement** -- fields stripped based on contributor's consent level
3. **Hardware anonymization** -- GPU family-level, power-of-2 RAM/VRAM, OS family-only
4. **Timestamp jitter** -- +/-30 minutes to prevent temporal fingerprinting

Contributors can request deletion of any record at any time.

<!-- AUTO-GENERATED -->

## Dataset Statistics

| Metric | Value |
|--------|-------|
| Total Records | {total_records} |
| Models | {num_models} |
| Deletions | {deletions_count} |
| Last Updated | {generated_at} |

## Quality Distribution

| Tier | Count | Percentage |
|------|-------|------------|
{quality_rows.rstrip()}

## Model Coverage

| Model | Records | Avg Score | Top Tier |
|-------|---------|-----------|----------|
{model_rows.rstrip()}

<!-- END AUTO-GENERATED -->

## How to Use

### Browse

Explore the `data/` directory organized by model and quality tier:

```
data/
  gpt-4o/
    gold/
      shard_00.jsonl
      shard_01.jsonl
    silver/
      ...
  claude-3-5-sonnet/
    gold/
      ...
```

### Download a Subset

Download specific model/tier combinations:

```bash
# Clone just the gold-tier GPT-4o records
git clone --filter=blob:none --sparse https://github.com/CuervoDoesIt/kajiba-dataset.git
cd kajiba-dataset
git sparse-checkout set data/gpt-4o/gold
```

### Load Records

```python
import json

with open("data/gpt-4o/gold/shard_00.jsonl") as f:
    for line in f:
        record = json.loads(line)
        # Use record["trajectory"]["conversations"] for training
```

## Deletions

Deleted records are tracked in `deletions.jsonl`. When loading data, filter out any `record_id` that appears in the deletions file. Records are not physically removed from shard files to maintain git history integrity.

## Contributing

Install Kajiba and publish your session data:

```bash
pip install kajiba
kajiba publish
```

See the [Kajiba repository](https://github.com/CuervoDoesIt/Kajiba) for full documentation.

---

*This README is auto-generated by Kajiba v{SCHEMA_VERSION}.*
"""
    return readme


# ---------------------------------------------------------------------------
# Deletion tracking
# ---------------------------------------------------------------------------


def create_deletion_entry(record_id: str, reason: str = "contributor_request") -> str:
    """Create a JSONL line for the deletions index.

    Args:
        record_id: The ID of the record to delete.
        reason: Reason for deletion (default "contributor_request").

    Returns:
        JSON string with record_id, deleted_at (ISO), and reason.
    """
    return json.dumps(
        {
            "record_id": record_id,
            "deleted_at": datetime.now(UTC).isoformat(),
            "reason": reason,
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# PR template functions
# ---------------------------------------------------------------------------


def build_publish_pr_title(record_count: int, model_names: list[str]) -> str:
    """Build a PR title for a publish submission.

    Args:
        record_count: Number of records being published.
        model_names: List of model names in the submission.

    Returns:
        PR title string capped at 5 model names.
    """
    unique_models = sorted(set(model_names))[:5]
    models_str = ", ".join(unique_models)
    return f"kajiba: add {record_count} record(s) [{models_str}]"


def build_publish_pr_body(
    record_count: int,
    model_names: list[str],
    tier_names: list[str],
    version: str,
) -> str:
    """Build a PR body for a publish submission.

    Args:
        record_count: Number of records being published.
        model_names: List of model names in the submission.
        tier_names: List of quality tiers in the submission.
        version: Kajiba version string.

    Returns:
        Markdown body for the PR.
    """
    unique_models = sorted(set(model_names))
    unique_tiers = sorted(set(tier_names))

    return f"""## Records Added

- **Count:** {record_count}
- **Models:** {", ".join(unique_models)}
- **Quality Tiers:** {", ".join(unique_tiers)}

## Catalog Updated

The `catalog.json` and `README.md` have been regenerated to reflect the new records.

## Consent Verification

All records have been re-verified against their consent level at publish time.
Fields have been stripped according to each contributor's consent preferences.

## Privacy Pipeline

All records passed through the full Kajiba privacy pipeline:
- Regex PII scrubbing (7 pattern categories)
- Consent-level field stripping
- Hardware anonymization (GPU family, RAM rounding, OS family)
- Timestamp jitter (+/-30 min)

---

*Generated by Kajiba v{version}*
"""


def build_deletion_pr_title(record_id: str) -> str:
    """Build a PR title for a deletion request.

    Args:
        record_id: The ID of the record to delete.

    Returns:
        PR title string.
    """
    return f"kajiba: delete record {record_id}"


def build_deletion_pr_body(record_id: str, version: str) -> str:
    """Build a PR body for a deletion request.

    Args:
        record_id: The ID of the record to delete.
        version: Kajiba version string.

    Returns:
        Markdown body for the deletion PR.
    """
    return f"""## Deletion Request

- **Record ID:** {record_id}
- **Reason:** Contributor-initiated deletion request

## What This Does

Appends the record ID to `deletions.jsonl`. The record is **not** physically
removed from shard files. Consumers are expected to filter out deleted record
IDs when loading data.

## Privacy

This deletion request was initiated by the contributor via `kajiba delete`.
Per the Kajiba privacy policy, deletion requests are processed without
identity verification to maximize privacy.

---

*Generated by Kajiba v{version}*
"""
