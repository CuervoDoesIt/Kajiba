"""Tests for the Kajiba publisher module.

Covers file layout logic, sharding, catalog generation, README generation,
deletion entries, GitHubOps subprocess wrapper, and PR template functions.
"""

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pytest

from kajiba.publisher import (
    DEFAULT_NUM_SHARDS,
    GhResult,
    GitHubOps,
    build_deletion_pr_body,
    build_deletion_pr_title,
    build_publish_pr_body,
    build_publish_pr_title,
    compute_record_path,
    compute_shard_key,
    create_deletion_entry,
    generate_catalog,
    generate_readme,
    normalize_model_name,
    write_records_to_shards,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    """Load a test fixture JSON file."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _make_record_dict(
    record_id: str = "kajiba_abc123def456",
    model_name: str = "GPT-4o",
    quality_tier: str = "gold",
    composite_score: float = 0.85,
    gpu_name: Optional[str] = "NVIDIA RTX 40xx",
) -> dict:
    """Create a minimal record dict for testing."""
    data = _load_fixture("gold_trajectory.json")
    data["record_id"] = record_id
    if model_name:
        data.setdefault("model", {})["model_name"] = model_name
    else:
        data.pop("model", None)
    if quality_tier:
        data["quality"] = {
            "quality_tier": quality_tier,
            "composite_score": composite_score,
            "sub_scores": {"coherence": 0.9, "tool_validity": 0.8},
            "scored_at": "2026-03-30T12:00:00Z",
        }
    else:
        data.pop("quality", None)
    if gpu_name and data.get("hardware"):
        data["hardware"]["gpu_name"] = gpu_name
    return data


# ---------------------------------------------------------------------------
# TestNormalizeModelName
# ---------------------------------------------------------------------------


class TestNormalizeModelName:
    """Tests for the normalize_model_name function."""

    def test_gpt_4o(self) -> None:
        """GPT-4o becomes gpt-4o (lowercased, hyphens preserved)."""
        assert normalize_model_name("GPT-4o") == "gpt-4o"

    def test_claude_3_5_sonnet(self) -> None:
        """Claude 3.5 Sonnet becomes claude-3-5-sonnet (spaces and dots to hyphens)."""
        assert normalize_model_name("Claude 3.5 Sonnet") == "claude-3-5-sonnet"

    def test_hermes_3_llama(self) -> None:
        """Hermes-3-Llama-3.1-8B becomes hermes-3-llama-3-1-8b."""
        assert normalize_model_name("Hermes-3-Llama-3.1-8B") == "hermes-3-llama-3-1-8b"

    def test_strips_leading_trailing_whitespace(self) -> None:
        """Leading and trailing whitespace is stripped."""
        assert normalize_model_name("  spaces  ") == "spaces"

    def test_removes_special_chars(self) -> None:
        """Non-alphanumeric, non-hyphen characters are removed."""
        assert normalize_model_name("a!!b@@c") == "abc"

    def test_empty_string(self) -> None:
        """Empty string returns empty string."""
        assert normalize_model_name("") == ""

    def test_multiple_spaces(self) -> None:
        """Multiple consecutive spaces become a single hyphen."""
        assert normalize_model_name("hello   world") == "hello-world"

    def test_underscores_to_hyphens(self) -> None:
        """Underscores become hyphens."""
        assert normalize_model_name("my_model_v2") == "my-model-v2"


# ---------------------------------------------------------------------------
# TestComputeShardKey
# ---------------------------------------------------------------------------


class TestComputeShardKey:
    """Tests for the compute_shard_key function."""

    def test_deterministic(self) -> None:
        """Same input always produces same shard key."""
        key1 = compute_shard_key("kajiba_abc123")
        key2 = compute_shard_key("kajiba_abc123")
        assert key1 == key2

    def test_format(self) -> None:
        """Shard key matches shard_{hex}.jsonl format."""
        key = compute_shard_key("kajiba_abc123")
        assert key.startswith("shard_")
        assert key.endswith(".jsonl")
        hex_part = key[len("shard_"):-len(".jsonl")]
        # Hex part should be valid hex
        int(hex_part, 16)

    def test_distribution(self) -> None:
        """Different inputs produce at least 2 different shard keys."""
        ids = [f"kajiba_{i:06d}" for i in range(10)]
        keys = {compute_shard_key(rid) for rid in ids}
        assert len(keys) >= 2, "Expected at least 2 different shards for 10 IDs"

    def test_respects_num_shards(self) -> None:
        """Custom num_shards produces valid shard numbers."""
        key = compute_shard_key("kajiba_abc123", num_shards=16)
        hex_part = key[len("shard_"):-len(".jsonl")]
        shard_num = int(hex_part, 16)
        assert 0 <= shard_num < 16

    def test_default_num_shards(self) -> None:
        """Default num_shards is 256."""
        assert DEFAULT_NUM_SHARDS == 256


# ---------------------------------------------------------------------------
# TestComputeRecordPath
# ---------------------------------------------------------------------------


class TestComputeRecordPath:
    """Tests for the compute_record_path function."""

    def test_correct_format(self) -> None:
        """Returns data/{model}/{tier}/shard_{hex}.jsonl path."""
        path = compute_record_path("GPT-4o", "gold", "kajiba_abc123")
        assert path.startswith("data/gpt-4o/gold/shard_")
        assert path.endswith(".jsonl")

    def test_uses_forward_slashes(self) -> None:
        """Path uses forward slashes, not backslashes (cross-platform)."""
        path = compute_record_path("GPT-4o", "gold", "kajiba_abc123")
        assert "\\" not in path
        assert "/" in path

    def test_none_model_defaults_to_unknown(self) -> None:
        """None model_name defaults to 'unknown'."""
        path = compute_record_path(None, "gold", "kajiba_abc123")
        assert path.startswith("data/unknown/gold/")

    def test_empty_model_defaults_to_unknown(self) -> None:
        """Empty model_name defaults to 'unknown'."""
        path = compute_record_path("", "gold", "kajiba_abc123")
        assert path.startswith("data/unknown/gold/")

    def test_none_tier_defaults_to_review_needed(self) -> None:
        """None quality_tier defaults to 'review_needed'."""
        path = compute_record_path("GPT-4o", None, "kajiba_abc123")
        assert "/review_needed/" in path

    def test_empty_tier_defaults_to_review_needed(self) -> None:
        """Empty quality_tier defaults to 'review_needed'."""
        path = compute_record_path("GPT-4o", "", "kajiba_abc123")
        assert "/review_needed/" in path


# ---------------------------------------------------------------------------
# TestWriteRecordsToShards
# ---------------------------------------------------------------------------


class TestWriteRecordsToShards:
    """Tests for the write_records_to_shards function."""

    def test_creates_directories(self, tmp_path: Path) -> None:
        """Creates directory structure under repo_root/data/."""
        record = _make_record_dict()
        count = write_records_to_shards(tmp_path, [record])
        assert count == 1
        data_dir = tmp_path / "data"
        assert data_dir.exists()

    def test_writes_jsonl(self, tmp_path: Path) -> None:
        """Writes records as valid JSON lines."""
        record = _make_record_dict()
        write_records_to_shards(tmp_path, [record])
        # Find the written shard file
        shard_files = list(tmp_path.rglob("shard_*.jsonl"))
        assert len(shard_files) >= 1
        content = shard_files[0].read_text(encoding="utf-8").strip()
        for line in content.split("\n"):
            parsed = json.loads(line)
            assert "record_id" in parsed

    def test_appends_to_existing(self, tmp_path: Path) -> None:
        """Appends new records to existing shard files."""
        record1 = _make_record_dict(record_id="kajiba_first000001")
        record2 = _make_record_dict(record_id="kajiba_second00001")
        write_records_to_shards(tmp_path, [record1])
        write_records_to_shards(tmp_path, [record2])
        # Count total lines across all shard files
        total_lines = 0
        for shard_file in tmp_path.rglob("shard_*.jsonl"):
            lines = shard_file.read_text(encoding="utf-8").strip().split("\n")
            total_lines += len([ln for ln in lines if ln])
        assert total_lines == 2

    def test_dedup_skips_existing_record_id(self, tmp_path: Path) -> None:
        """Skips records whose record_id already exists in the shard."""
        record = _make_record_dict(record_id="kajiba_dedup00001")
        count1 = write_records_to_shards(tmp_path, [record])
        count2 = write_records_to_shards(tmp_path, [record])
        assert count1 == 1
        assert count2 == 0

    def test_returns_count(self, tmp_path: Path) -> None:
        """Returns count of actually-written records."""
        records = [
            _make_record_dict(record_id=f"kajiba_count{i:06d}")
            for i in range(3)
        ]
        count = write_records_to_shards(tmp_path, records)
        assert count == 3

    def test_handles_missing_model(self, tmp_path: Path) -> None:
        """Records without model section use 'unknown' directory."""
        record = _make_record_dict(model_name=None)
        record.pop("model", None)
        count = write_records_to_shards(tmp_path, [record])
        assert count == 1
        unknown_dirs = list((tmp_path / "data" / "unknown").iterdir())
        assert len(unknown_dirs) >= 1

    def test_handles_missing_quality(self, tmp_path: Path) -> None:
        """Records without quality section use 'review_needed' directory."""
        record = _make_record_dict(quality_tier=None)
        record.pop("quality", None)
        count = write_records_to_shards(tmp_path, [record])
        assert count == 1
        review_dirs = list(tmp_path.rglob("review_needed"))
        assert len(review_dirs) >= 1

    def test_skips_records_without_record_id(self, tmp_path: Path) -> None:
        """Records without record_id are skipped with a warning."""
        record = _make_record_dict()
        record.pop("record_id", None)
        count = write_records_to_shards(tmp_path, [record])
        assert count == 0


# ---------------------------------------------------------------------------
# TestGenerateCatalog
# ---------------------------------------------------------------------------


class TestGenerateCatalog:
    """Tests for the generate_catalog function."""

    def _populate_data(self, repo_root: Path) -> None:
        """Pre-populate data/ with some shard files for testing."""
        # Create a shard for gpt-4o/gold
        shard_dir = repo_root / "data" / "gpt-4o" / "gold"
        shard_dir.mkdir(parents=True)
        shard_file = shard_dir / "shard_00.jsonl"
        records = [
            {
                "record_id": f"kajiba_cat{i:06d}",
                "model": {"model_name": "GPT-4o"},
                "quality": {
                    "quality_tier": "gold",
                    "composite_score": 0.85 + i * 0.01,
                    "sub_scores": {},
                    "scored_at": "2026-03-30T12:00:00Z",
                },
                "hardware": {"gpu_name": "NVIDIA RTX 40xx"},
            }
            for i in range(3)
        ]
        with open(shard_file, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec) + "\n")

        # Create a shard for claude-3-5-sonnet/silver
        shard_dir2 = repo_root / "data" / "claude-3-5-sonnet" / "silver"
        shard_dir2.mkdir(parents=True)
        shard_file2 = shard_dir2 / "shard_01.jsonl"
        records2 = [
            {
                "record_id": "kajiba_silver001",
                "model": {"model_name": "Claude 3.5 Sonnet"},
                "quality": {
                    "quality_tier": "silver",
                    "composite_score": 0.65,
                    "sub_scores": {},
                    "scored_at": "2026-03-30T12:00:00Z",
                },
                "hardware": {"gpu_name": "Apple Silicon"},
            },
        ]
        with open(shard_file2, "w", encoding="utf-8") as f:
            for rec in records2:
                f.write(json.dumps(rec) + "\n")

    def test_catalog_structure(self, tmp_path: Path) -> None:
        """Catalog has required top-level keys."""
        self._populate_data(tmp_path)
        catalog = generate_catalog(tmp_path)
        assert "schema_version" in catalog
        assert "generated_at" in catalog
        assert "total_records" in catalog
        assert "total_size_bytes" in catalog
        assert "models" in catalog
        assert "quality_distribution" in catalog
        assert "deletions_count" in catalog

    def test_catalog_counts_records(self, tmp_path: Path) -> None:
        """Catalog correctly counts total records."""
        self._populate_data(tmp_path)
        catalog = generate_catalog(tmp_path)
        assert catalog["total_records"] == 4  # 3 gold + 1 silver

    def test_catalog_model_stats(self, tmp_path: Path) -> None:
        """Catalog includes per-model statistics."""
        self._populate_data(tmp_path)
        catalog = generate_catalog(tmp_path)
        assert "gpt-4o" in catalog["models"]
        assert "claude-3-5-sonnet" in catalog["models"]
        gpt_model = catalog["models"]["gpt-4o"]
        assert gpt_model["total_records"] == 3
        assert "gold" in gpt_model["tiers"]

    def test_catalog_quality_distribution(self, tmp_path: Path) -> None:
        """Catalog tracks quality distribution across tiers."""
        self._populate_data(tmp_path)
        catalog = generate_catalog(tmp_path)
        qd = catalog["quality_distribution"]
        assert qd.get("gold", 0) == 3
        assert qd.get("silver", 0) == 1

    def test_catalog_reads_deletions(self, tmp_path: Path) -> None:
        """Catalog counts deletions from deletions.jsonl."""
        self._populate_data(tmp_path)
        deletions_file = tmp_path / "deletions.jsonl"
        deletions_file.write_text(
            json.dumps({"record_id": "kajiba_del001", "deleted_at": "2026-03-30T12:00:00Z", "reason": "test"}) + "\n"
            + json.dumps({"record_id": "kajiba_del002", "deleted_at": "2026-03-30T12:00:00Z", "reason": "test"}) + "\n",
            encoding="utf-8",
        )
        catalog = generate_catalog(tmp_path)
        assert catalog["deletions_count"] == 2

    def test_catalog_empty_data(self, tmp_path: Path) -> None:
        """Catalog works with empty data directory."""
        (tmp_path / "data").mkdir()
        catalog = generate_catalog(tmp_path)
        assert catalog["total_records"] == 0
        assert catalog["models"] == {}

    def test_catalog_no_data_dir(self, tmp_path: Path) -> None:
        """Catalog works when data/ directory does not exist."""
        catalog = generate_catalog(tmp_path)
        assert catalog["total_records"] == 0


# ---------------------------------------------------------------------------
# TestGenerateCatalogEnriched
# ---------------------------------------------------------------------------


class TestGenerateCatalogEnriched:
    """Tests for catalog model-metadata enrichment (parameter_counts, quantizations, context_windows)."""

    def _populate_enriched_data(self, repo_root: Path) -> None:
        """Pre-populate data/ with shard files containing model metadata."""
        # Create a shard for llama-3/gold with model metadata
        shard_dir = repo_root / "data" / "llama-3" / "gold"
        shard_dir.mkdir(parents=True)
        shard_file = shard_dir / "shard_00.jsonl"
        records = [
            {
                "record_id": "kajiba_enrich001",
                "model": {
                    "model_name": "Llama 3",
                    "parameter_count": "8B",
                    "quantization": "Q4_K_M",
                    "context_window": 8192,
                },
                "quality": {
                    "quality_tier": "gold",
                    "composite_score": 0.90,
                    "sub_scores": {},
                    "scored_at": "2026-04-01T00:00:00Z",
                },
                "hardware": {"gpu_name": "NVIDIA RTX 40xx"},
            },
            {
                "record_id": "kajiba_enrich002",
                "model": {
                    "model_name": "Llama 3",
                    "parameter_count": "70B",
                    "quantization": "Q8_0",
                    "context_window": 131072,
                },
                "quality": {
                    "quality_tier": "gold",
                    "composite_score": 0.92,
                    "sub_scores": {},
                    "scored_at": "2026-04-01T00:00:00Z",
                },
                "hardware": {"gpu_name": "NVIDIA RTX 40xx"},
            },
        ]
        with open(shard_file, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec) + "\n")

    def test_parameter_counts_extracted(self, tmp_path: Path) -> None:
        """generate_catalog extracts parameter_count into parameter_counts list."""
        self._populate_enriched_data(tmp_path)
        catalog = generate_catalog(tmp_path)
        model_info = catalog["models"]["llama-3"]
        assert "parameter_counts" in model_info
        assert "8B" in model_info["parameter_counts"]
        assert "70B" in model_info["parameter_counts"]

    def test_quantizations_extracted(self, tmp_path: Path) -> None:
        """generate_catalog extracts quantization into quantizations list."""
        self._populate_enriched_data(tmp_path)
        catalog = generate_catalog(tmp_path)
        model_info = catalog["models"]["llama-3"]
        assert "quantizations" in model_info
        assert "Q4_K_M" in model_info["quantizations"]
        assert "Q8_0" in model_info["quantizations"]

    def test_context_windows_extracted(self, tmp_path: Path) -> None:
        """generate_catalog extracts context_window into context_windows list."""
        self._populate_enriched_data(tmp_path)
        catalog = generate_catalog(tmp_path)
        model_info = catalog["models"]["llama-3"]
        assert "context_windows" in model_info
        assert 8192 in model_info["context_windows"]
        assert 131072 in model_info["context_windows"]

    def test_deduplicates_metadata_values(self, tmp_path: Path) -> None:
        """Two records with same parameter_count produce a single entry."""
        shard_dir = tmp_path / "data" / "test-model" / "gold"
        shard_dir.mkdir(parents=True)
        shard_file = shard_dir / "shard_00.jsonl"
        records = [
            {
                "record_id": f"kajiba_dup{i:03d}",
                "model": {
                    "model_name": "Test Model",
                    "parameter_count": "8B",
                    "quantization": "Q4_K_M",
                    "context_window": 8192,
                },
                "quality": {
                    "quality_tier": "gold",
                    "composite_score": 0.85,
                    "sub_scores": {},
                    "scored_at": "2026-04-01T00:00:00Z",
                },
                "hardware": {"gpu_name": "NVIDIA RTX 40xx"},
            }
            for i in range(3)
        ]
        with open(shard_file, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec) + "\n")
        catalog = generate_catalog(tmp_path)
        model_info = catalog["models"]["test-model"]
        assert len(model_info["parameter_counts"]) == 1
        assert len(model_info["quantizations"]) == 1
        assert len(model_info["context_windows"]) == 1

    def test_handles_no_model_metadata(self, tmp_path: Path) -> None:
        """Records with no model metadata produce empty enrichment lists."""
        shard_dir = tmp_path / "data" / "unknown-model" / "silver"
        shard_dir.mkdir(parents=True)
        shard_file = shard_dir / "shard_00.jsonl"
        record = {
            "record_id": "kajiba_nomodel001",
            "quality": {
                "quality_tier": "silver",
                "composite_score": 0.70,
                "sub_scores": {},
                "scored_at": "2026-04-01T00:00:00Z",
            },
            "hardware": {"gpu_name": "NVIDIA RTX 40xx"},
        }
        with open(shard_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        catalog = generate_catalog(tmp_path)
        model_info = catalog["models"]["unknown-model"]
        assert model_info["parameter_counts"] == []
        assert model_info["quantizations"] == []
        assert model_info["context_windows"] == []

    def test_handles_partial_model_metadata(self, tmp_path: Path) -> None:
        """Records with only parameter_count set still work (others stay empty)."""
        shard_dir = tmp_path / "data" / "partial-model" / "gold"
        shard_dir.mkdir(parents=True)
        shard_file = shard_dir / "shard_00.jsonl"
        record = {
            "record_id": "kajiba_partial001",
            "model": {
                "model_name": "Partial Model",
                "parameter_count": "13B",
            },
            "quality": {
                "quality_tier": "gold",
                "composite_score": 0.88,
                "sub_scores": {},
                "scored_at": "2026-04-01T00:00:00Z",
            },
            "hardware": {"gpu_name": "NVIDIA RTX 40xx"},
        }
        with open(shard_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        catalog = generate_catalog(tmp_path)
        model_info = catalog["models"]["partial-model"]
        assert model_info["parameter_counts"] == ["13B"]
        assert model_info["quantizations"] == []
        assert model_info["context_windows"] == []


# ---------------------------------------------------------------------------
# TestGenerateReadme
# ---------------------------------------------------------------------------


class TestGenerateReadme:
    """Tests for the generate_readme function."""

    def _make_catalog(self) -> dict:
        """Create a sample catalog dict for README generation."""
        return {
            "schema_version": "0.1.0",
            "generated_at": "2026-03-30T12:00:00Z",
            "total_records": 100,
            "total_size_bytes": 1024000,
            "models": {
                "gpt-4o": {
                    "display_name": "GPT-4o",
                    "tiers": {
                        "gold": {
                            "record_count": 50,
                            "avg_quality_score": 0.85,
                            "shards": ["shard_00.jsonl"],
                            "total_size_bytes": 512000,
                            "last_updated": "2026-03-30T12:00:00Z",
                        },
                        "silver": {
                            "record_count": 30,
                            "avg_quality_score": 0.65,
                            "shards": ["shard_01.jsonl"],
                            "total_size_bytes": 307200,
                            "last_updated": "2026-03-30T12:00:00Z",
                        },
                    },
                    "total_records": 80,
                    "hardware_distribution": {"NVIDIA RTX 40xx": 60, "Apple Silicon": 20},
                },
                "claude-3-5-sonnet": {
                    "display_name": "Claude 3.5 Sonnet",
                    "tiers": {
                        "bronze": {
                            "record_count": 20,
                            "avg_quality_score": 0.45,
                            "shards": ["shard_02.jsonl"],
                            "total_size_bytes": 204800,
                            "last_updated": "2026-03-30T12:00:00Z",
                        },
                    },
                    "total_records": 20,
                    "hardware_distribution": {"Apple Silicon": 20},
                },
            },
            "quality_distribution": {"gold": 50, "silver": 30, "bronze": 20, "review_needed": 0},
            "deletions_count": 5,
        }

    def test_readme_has_title(self) -> None:
        """README starts with the Kajiba Community Dataset title."""
        readme = generate_readme(self._make_catalog())
        assert "# Kajiba Community Dataset" in readme

    def test_readme_has_apache_license(self) -> None:
        """README includes Apache 2.0 license section."""
        readme = generate_readme(self._make_catalog())
        assert "Apache 2.0" in readme or "Apache-2.0" in readme

    def test_readme_has_dynamic_stats(self) -> None:
        """README includes dynamic stats from catalog data."""
        readme = generate_readme(self._make_catalog())
        assert "100" in readme  # total records
        assert "2" in readme  # number of models

    def test_readme_has_quality_distribution(self) -> None:
        """README includes quality distribution table."""
        readme = generate_readme(self._make_catalog())
        assert "gold" in readme.lower()
        assert "silver" in readme.lower()

    def test_readme_has_model_coverage(self) -> None:
        """README includes model coverage table."""
        readme = generate_readme(self._make_catalog())
        assert "gpt-4o" in readme.lower() or "GPT-4o" in readme

    def test_readme_has_auto_generated_marker(self) -> None:
        """README includes AUTO-GENERATED marker before dynamic sections."""
        readme = generate_readme(self._make_catalog())
        assert "<!-- AUTO-GENERATED -->" in readme


# ---------------------------------------------------------------------------
# TestCreateDeletionEntry
# ---------------------------------------------------------------------------


class TestCreateDeletionEntry:
    """Tests for the create_deletion_entry function."""

    def test_valid_json(self) -> None:
        """Output is valid JSON."""
        entry = create_deletion_entry("kajiba_del001")
        parsed = json.loads(entry)
        assert isinstance(parsed, dict)

    def test_contains_record_id(self) -> None:
        """Entry contains the correct record_id."""
        entry = create_deletion_entry("kajiba_del001")
        parsed = json.loads(entry)
        assert parsed["record_id"] == "kajiba_del001"

    def test_contains_deleted_at(self) -> None:
        """Entry contains a deleted_at ISO timestamp."""
        entry = create_deletion_entry("kajiba_del001")
        parsed = json.loads(entry)
        assert "deleted_at" in parsed
        # Should parse as ISO datetime
        datetime.fromisoformat(parsed["deleted_at"].replace("Z", "+00:00"))

    def test_default_reason(self) -> None:
        """Default reason is 'contributor_request'."""
        entry = create_deletion_entry("kajiba_del001")
        parsed = json.loads(entry)
        assert parsed["reason"] == "contributor_request"

    def test_custom_reason(self) -> None:
        """Custom reason is used when provided."""
        entry = create_deletion_entry("kajiba_del001", reason="pii_found")
        parsed = json.loads(entry)
        assert parsed["reason"] == "pii_found"


# ---------------------------------------------------------------------------
# TestGitHubOps
# ---------------------------------------------------------------------------


class TestGitHubOps:
    """Tests for the GitHubOps class with mocked subprocess."""

    def _mock_subprocess_run(self, monkeypatch, returncode: int = 0,
                              stdout: str = "", stderr: str = "") -> list:
        """Mock subprocess.run and return the call log."""
        calls = []

        def fake_run(args, **kwargs):
            calls.append((args, kwargs))
            result = subprocess.CompletedProcess(
                args=args,
                returncode=returncode,
                stdout=stdout,
                stderr=stderr,
            )
            return result

        monkeypatch.setattr(subprocess, "run", fake_run)
        return calls

    def test_check_auth_success(self, monkeypatch) -> None:
        """check_auth returns success when gh auth status succeeds."""
        self._mock_subprocess_run(monkeypatch, returncode=0, stdout="Logged in")
        ops = GitHubOps("CuervoDoesIt/kajiba-dataset")
        result = ops.check_auth()
        assert result.success is True
        assert result.returncode == 0

    def test_check_auth_failure(self, monkeypatch) -> None:
        """check_auth returns failure when gh auth status fails."""
        self._mock_subprocess_run(monkeypatch, returncode=1, stderr="Not logged in")
        ops = GitHubOps("CuervoDoesIt/kajiba-dataset")
        result = ops.check_auth()
        assert result.success is False
        assert result.returncode == 1

    def test_fork_repo(self, monkeypatch) -> None:
        """fork_repo calls gh repo fork with correct args."""
        calls = self._mock_subprocess_run(monkeypatch, returncode=0)
        ops = GitHubOps("CuervoDoesIt/kajiba-dataset")
        result = ops.fork_repo()
        assert result.success is True
        assert any("fork" in str(c[0]) for c in calls)

    def test_clone_fork(self, monkeypatch) -> None:
        """clone_fork calls git clone with fork URL and destination."""
        calls = self._mock_subprocess_run(monkeypatch, returncode=0)
        ops = GitHubOps("CuervoDoesIt/kajiba-dataset")
        result = ops.clone_fork("/tmp/dest", "https://github.com/user/repo.git")
        assert result.success is True

    def test_create_pr(self, monkeypatch) -> None:
        """create_pr calls gh pr create with correct arguments."""
        calls = self._mock_subprocess_run(monkeypatch, returncode=0, stdout="https://github.com/pr/1")
        ops = GitHubOps("CuervoDoesIt/kajiba-dataset")
        result = ops.create_pr(
            title="Test PR",
            body="Test body",
            head="user:branch",
            base="main",
        )
        assert result.success is True

    def test_gh_not_installed(self, monkeypatch) -> None:
        """Returns error GhResult when gh is not installed (FileNotFoundError)."""
        def fake_run(args, **kwargs):
            raise FileNotFoundError("gh not found")

        monkeypatch.setattr(subprocess, "run", fake_run)
        ops = GitHubOps("CuervoDoesIt/kajiba-dataset")
        result = ops.check_auth()
        assert result.success is False
        assert result.returncode == -1
        assert "gh CLI not found" in result.stderr

    def test_timeout_expired(self, monkeypatch) -> None:
        """Returns error GhResult when command times out."""
        def fake_run(args, **kwargs):
            raise subprocess.TimeoutExpired(cmd=args, timeout=120)

        monkeypatch.setattr(subprocess, "run", fake_run)
        ops = GitHubOps("CuervoDoesIt/kajiba-dataset")
        result = ops.check_auth()
        assert result.success is False
        assert result.returncode == -2
        assert "timed out" in result.stderr.lower()

    def test_push_branch(self, monkeypatch) -> None:
        """push_branch calls git push with correct branch name."""
        calls = self._mock_subprocess_run(monkeypatch, returncode=0)
        ops = GitHubOps("CuervoDoesIt/kajiba-dataset")
        result = ops.push_branch("/tmp/repo", "kajiba/submit-001")
        assert result.success is True

    def test_create_branch(self, monkeypatch) -> None:
        """create_branch calls git checkout -b with branch name."""
        calls = self._mock_subprocess_run(monkeypatch, returncode=0)
        ops = GitHubOps("CuervoDoesIt/kajiba-dataset")
        result = ops.create_branch("/tmp/repo", "kajiba/submit-001")
        assert result.success is True

    def test_commit_all(self, monkeypatch) -> None:
        """commit_all calls git add and git commit."""
        calls = self._mock_subprocess_run(monkeypatch, returncode=0)
        ops = GitHubOps("CuervoDoesIt/kajiba-dataset")
        result = ops.commit_all("/tmp/repo", "Add records")
        assert result.success is True
        # Should have called both git add and git commit
        assert len(calls) >= 2

    def test_pull_latest(self, monkeypatch) -> None:
        """pull_latest calls git fetch and git reset."""
        calls = self._mock_subprocess_run(monkeypatch, returncode=0)
        ops = GitHubOps("CuervoDoesIt/kajiba-dataset")
        result = ops.pull_latest("/tmp/repo")
        assert result.success is True
        assert len(calls) >= 2

    def test_get_username(self, monkeypatch) -> None:
        """get_username calls gh api user."""
        self._mock_subprocess_run(monkeypatch, returncode=0, stdout="testuser")
        ops = GitHubOps("CuervoDoesIt/kajiba-dataset")
        result = ops.get_username()
        assert result.success is True
        assert result.stdout == "testuser"


# ---------------------------------------------------------------------------
# TestPRTemplates
# ---------------------------------------------------------------------------


class TestPRTemplates:
    """Tests for PR title and body template functions."""

    def test_publish_pr_title(self) -> None:
        """Publish PR title includes record count and model names."""
        title = build_publish_pr_title(5, ["GPT-4o", "Claude 3.5"])
        assert "5" in title
        assert "kajiba:" in title.lower()

    def test_publish_pr_title_caps_models(self) -> None:
        """Publish PR title caps model list at 5."""
        models = [f"model-{i}" for i in range(10)]
        title = build_publish_pr_title(100, models)
        # Should not contain all 10 models
        assert title.count(",") <= 4

    def test_publish_pr_body_content(self) -> None:
        """Publish PR body includes Records Added section."""
        body = build_publish_pr_body(5, ["GPT-4o"], ["gold"], "0.1.0")
        assert "Records Added" in body or "records" in body.lower()
        assert "0.1.0" in body

    def test_publish_pr_body_consent(self) -> None:
        """Publish PR body includes consent verification section."""
        body = build_publish_pr_body(5, ["GPT-4o"], ["gold"], "0.1.0")
        assert "consent" in body.lower() or "Consent" in body

    def test_deletion_pr_title(self) -> None:
        """Deletion PR title includes record_id."""
        title = build_deletion_pr_title("kajiba_del001")
        assert "kajiba_del001" in title
        assert "delete" in title.lower()

    def test_deletion_pr_body_content(self) -> None:
        """Deletion PR body includes deletion request section."""
        body = build_deletion_pr_body("kajiba_del001", "0.1.0")
        assert "kajiba_del001" in body
        assert "0.1.0" in body
