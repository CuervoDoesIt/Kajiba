"""Smoke tests for the Kajiba CLI."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from kajiba.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestCLIBasics:
    """Basic CLI smoke tests."""

    def test_version(self, runner: CliRunner) -> None:
        """--version flag should work."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "kajiba" in result.output.lower()

    def test_help(self, runner: CliRunner) -> None:
        """--help should show all commands."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "preview" in result.output
        assert "submit" in result.output
        assert "export" in result.output
        assert "history" in result.output
        assert "stats" in result.output
        assert "config" in result.output


class TestPreviewCommand:
    """Test the preview command."""

    def test_preview_empty_staging(self, runner: CliRunner, tmp_path: Path) -> None:
        """Preview with empty staging should show a message."""
        result = runner.invoke(cli, ["preview"])
        # Should not crash, even if staging is empty
        assert result.exit_code == 0


class TestHistoryCommand:
    """Test the history command."""

    def test_history_empty_outbox(self, runner: CliRunner) -> None:
        """History with empty outbox should show a message."""
        result = runner.invoke(cli, ["history"])
        assert result.exit_code == 0


class TestStatsCommand:
    """Test the stats command."""

    def test_stats_empty_outbox(self, runner: CliRunner) -> None:
        """Stats with empty outbox should show a message."""
        result = runner.invoke(cli, ["stats"])
        assert result.exit_code == 0


class TestConfigCommand:
    """Test the config command."""

    def test_config_shows_defaults(self, runner: CliRunner) -> None:
        """Config should show default settings."""
        result = runner.invoke(cli, ["config"])
        assert result.exit_code == 0
        assert "consent_level" in result.output or "Configuration" in result.output


class TestExportCommand:
    """Test the export command."""

    def test_export_no_staging(self, runner: CliRunner, tmp_path: Path) -> None:
        """Export with no staging data should show a message."""
        export_path = tmp_path / "test_export.jsonl"
        result = runner.invoke(cli, ["export", str(export_path)])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Privacy pipeline integration tests
# ---------------------------------------------------------------------------


def _minimal_record_data(
    conversation_text: str = "Hello, how are you?",
    response_text: str = "I am fine, thank you.",
    hardware: dict = None,
    submission: dict = None,
) -> dict:
    """Build a minimal valid KajibaRecord dict for test fixtures.

    Args:
        conversation_text: Text for the human turn.
        response_text: Text for the gpt turn.
        hardware: Optional hardware dict.
        submission: Optional submission dict.

    Returns:
        Dict suitable for writing as a staging JSON file.
    """
    data = {
        "schema_version": "0.1.0",
        "record_type": "task_trajectory",
        "created_at": "2026-03-29T12:00:00Z",
        "trajectory": {
            "format": "sharegpt_extended",
            "conversations": [
                {"from": "human", "value": conversation_text},
                {"from": "gpt", "value": response_text},
            ],
            "turn_count": 2,
            "total_tool_calls": 0,
            "successful_tool_calls": 0,
            "failed_tool_calls": 0,
        },
    }
    if hardware is not None:
        data["hardware"] = hardware
    if submission is not None:
        data["submission"] = submission
    return data


class TestPreviewFlaggedWarnings:
    """Test that flagged org domains appear as warnings in preview output."""

    def test_org_domain_flagged_in_preview(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Preview with org domain in conversation shows flagged warning."""
        record_data = _minimal_record_data(
            conversation_text="Deploy to acme.io server",
        )
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "session_001.json").write_text(
            json.dumps(record_data), encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        result = runner.invoke(cli, ["preview"])
        assert result.exit_code == 0
        assert "flagged for review" in result.output

    def test_safe_domain_not_flagged(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Preview with safe domain (github.io) shows no flagged warning."""
        record_data = _minimal_record_data(
            conversation_text="Read docs at github.io",
        )
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "session_001.json").write_text(
            json.dumps(record_data), encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        result = runner.invoke(cli, ["preview"])
        assert result.exit_code == 0
        assert "flagged for review" not in result.output

    def test_org_domain_shown_in_warning(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Preview warning includes the specific org domain name."""
        record_data = _minimal_record_data(
            conversation_text="Connect to mycorp.company database",
        )
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "session_001.json").write_text(
            json.dumps(record_data), encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        result = runner.invoke(cli, ["preview"])
        assert result.exit_code == 0
        assert "mycorp.company" in result.output


class TestSubmitConsentEnforcement:
    """Test that consent levels are enforced when writing to outbox."""

    def test_anonymous_consent_strips_hardware(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Submit with consent_level=anonymous strips hardware and model."""
        record_data = _minimal_record_data(
            hardware={
                "gpu_name": "NVIDIA GeForce RTX 4090",
                "ram_gb": 32,
                "os": "linux",
            },
            submission={"consent_level": "anonymous"},
        )
        staging = tmp_path / "staging"
        staging.mkdir()
        outbox = tmp_path / "outbox"
        outbox.mkdir()
        (staging / "session_001.json").write_text(
            json.dumps(record_data), encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.OUTBOX_DIR", outbox)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        result = runner.invoke(cli, ["submit"], input="y\n")
        assert result.exit_code == 0

        # Read the outbox file
        outbox_files = list(outbox.glob("*.jsonl"))
        assert len(outbox_files) == 1
        content = json.loads(outbox_files[0].read_text(encoding="utf-8").strip())
        assert content.get("hardware") is None
        assert content.get("model") is None

    def test_full_consent_keeps_hardware(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Submit with consent_level=full keeps hardware in outbox."""
        record_data = _minimal_record_data(
            hardware={
                "gpu_name": "NVIDIA GeForce RTX 4090",
                "ram_gb": 32,
                "os": "linux",
            },
            submission={"consent_level": "full"},
        )
        staging = tmp_path / "staging"
        staging.mkdir()
        outbox = tmp_path / "outbox"
        outbox.mkdir()
        (staging / "session_001.json").write_text(
            json.dumps(record_data), encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.OUTBOX_DIR", outbox)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        result = runner.invoke(cli, ["submit"], input="y\n")
        assert result.exit_code == 0

        outbox_files = list(outbox.glob("*.jsonl"))
        assert len(outbox_files) == 1
        content = json.loads(outbox_files[0].read_text(encoding="utf-8").strip())
        assert content.get("hardware") is not None


class TestPreviewRedactionSummary:
    """Test that preview shows a redaction summary table."""

    def test_summary_shows_email_count(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Preview a record with an email shows summary row with Emails category."""
        record_data = _minimal_record_data(
            conversation_text="Contact test@example.com for info",
        )
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "session_001.json").write_text(
            json.dumps(record_data), encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        result = runner.invoke(cli, ["preview"])
        assert result.exit_code == 0
        assert "Scrubbing Summary" in result.output
        assert "Emails" in result.output

    def test_summary_shows_multiple_categories(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Preview a record with email and file path shows both categories."""
        record_data = _minimal_record_data(
            conversation_text="Email test@example.com and path /home/user/secret.txt",
        )
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "session_001.json").write_text(
            json.dumps(record_data), encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        result = runner.invoke(cli, ["preview"])
        assert result.exit_code == 0
        assert "Emails" in result.output
        assert "File Paths" in result.output

    def test_no_pii_shows_clean_message(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Preview a record with no PII shows 'No PII detected' message."""
        record_data = _minimal_record_data(
            conversation_text="Hello world",
        )
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "session_001.json").write_text(
            json.dumps(record_data), encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        result = runner.invoke(cli, ["preview"])
        assert result.exit_code == 0
        assert "No PII detected" in result.output


class TestPreviewRedactionDetail:
    """Test that preview --detail shows inline highlighted redactions."""

    def test_detail_shows_redacted_markers(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Preview --detail with email shows REDACTED_EMAIL in output."""
        record_data = _minimal_record_data(
            conversation_text="Contact test@example.com",
        )
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "session_001.json").write_text(
            json.dumps(record_data), encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        result = runner.invoke(cli, ["preview", "--detail"])
        assert result.exit_code == 0
        assert "REDACTED_EMAIL" in result.output

    def test_detail_shows_redacted_path(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Preview --detail with file path shows REDACTED_PATH in output."""
        record_data = _minimal_record_data(
            conversation_text="File at /home/user/secret.txt",
        )
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "session_001.json").write_text(
            json.dumps(record_data), encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        result = runner.invoke(cli, ["preview", "--detail"])
        assert result.exit_code == 0
        assert "REDACTED_PATH" in result.output

    def test_no_detail_hides_inline_section(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Preview without --detail does not show Inline Redactions heading."""
        record_data = _minimal_record_data(
            conversation_text="Contact test@example.com",
        )
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "session_001.json").write_text(
            json.dumps(record_data), encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        result = runner.invoke(cli, ["preview"])
        assert result.exit_code == 0
        assert "Inline Redactions" not in result.output


class TestExportPrivacyPipeline:
    """Test that export applies hardware anonymization."""

    def test_export_anonymizes_gpu(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Export should anonymize GPU name to family-level."""
        record_data = _minimal_record_data(
            hardware={
                "gpu_name": "NVIDIA GeForce RTX 4090",
                "gpu_vram_gb": 24,
                "ram_gb": 13,
                "os": "linux",
            },
        )
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "session_001.json").write_text(
            json.dumps(record_data), encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        export_path = tmp_path / "export.jsonl"
        result = runner.invoke(cli, ["export", str(export_path)])
        assert result.exit_code == 0

        content = json.loads(export_path.read_text(encoding="utf-8").strip())
        hw = content.get("hardware", {})
        # GPU should be family-level, not exact model
        assert hw.get("gpu_name") == "NVIDIA RTX 40xx"
        # RAM should be rounded up (13 -> 16)
        assert hw.get("ram_gb") == 16
        # VRAM should be rounded up (24 -> 32)
        assert hw.get("gpu_vram_gb") == 32


# ---------------------------------------------------------------------------
# Quality persistence tests
# ---------------------------------------------------------------------------


class TestSubmitQualityPersistence:
    """Test that submit persists quality metadata in outbox records."""

    def test_submit_writes_quality_to_outbox(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """After submit, the outbox JSONL contains a quality key with all fields."""
        record_data = _minimal_record_data()
        staging = tmp_path / "staging"
        staging.mkdir()
        outbox = tmp_path / "outbox"
        outbox.mkdir()
        (staging / "session_001.json").write_text(
            json.dumps(record_data), encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.OUTBOX_DIR", outbox)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        result = runner.invoke(cli, ["submit"], input="y\n")
        assert result.exit_code == 0

        outbox_files = list(outbox.glob("*.jsonl"))
        assert len(outbox_files) == 1
        content = json.loads(outbox_files[0].read_text(encoding="utf-8").strip())

        # Quality key must exist
        quality = content.get("quality")
        assert quality is not None, "quality key missing from outbox record"
        assert "quality_tier" in quality
        assert "composite_score" in quality
        assert "sub_scores" in quality
        assert "scored_at" in quality

        # composite_score must be a valid float between 0.0 and 1.0
        assert 0.0 <= quality["composite_score"] <= 1.0

        # sub_scores must contain all 5 dimensions
        expected_dims = {
            "coherence", "tool_validity", "outcome_quality",
            "information_density", "metadata_completeness",
        }
        assert set(quality["sub_scores"].keys()) == expected_dims


class TestHistoryStoredQuality:
    """Test that history reads stored quality without recomputation."""

    def test_history_uses_stored_quality_tier(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """History with an outbox record containing quality.quality_tier displays it."""
        record_data = _minimal_record_data()
        record_data["record_id"] = "kajiba_test123456"
        record_data["quality"] = {
            "quality_tier": "gold",
            "composite_score": 0.9,
            "sub_scores": {
                "coherence": 0.95,
                "tool_validity": 1.0,
                "outcome_quality": 0.85,
                "information_density": 0.8,
                "metadata_completeness": 0.7,
            },
            "scored_at": "2026-03-29T12:00:00Z",
        }

        outbox = tmp_path / "outbox"
        outbox.mkdir()
        (outbox / "record_test.jsonl").write_text(
            json.dumps(record_data) + "\n", encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.OUTBOX_DIR", outbox)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        result = runner.invoke(cli, ["history"])
        assert result.exit_code == 0
        assert "gold" in result.output

    def test_history_fallback_for_old_records(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """History with an old record missing quality field falls back to recomputation."""
        record_data = _minimal_record_data()
        record_data["record_id"] = "kajiba_oldrecord12"
        # No quality key -- old record

        outbox = tmp_path / "outbox"
        outbox.mkdir()
        (outbox / "record_old.jsonl").write_text(
            json.dumps(record_data) + "\n", encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.OUTBOX_DIR", outbox)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        result = runner.invoke(cli, ["history"])
        assert result.exit_code == 0
        # Should show a tier (from recomputation), not crash
        # The tier for a minimal record is typically "bronze" or "review_needed"
        assert any(tier in result.output for tier in ["gold", "silver", "bronze", "review_needed"])


class TestExportAnnotations:
    """Test that user annotations survive through the export pipeline."""

    def test_submit_preserves_outcome_and_pain_points(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Staged record with outcome + pain_points retains them in outbox after submit."""
        record_data = _minimal_record_data()
        record_data["outcome"] = {
            "user_rating": 4,
            "outcome_tags": ["task_completed"],
        }
        record_data["pain_points"] = [
            {
                "category": "tool_call_failure",
                "description": "Broken tool call",
                "severity": "medium",
            },
        ]

        staging = tmp_path / "staging"
        staging.mkdir()
        outbox = tmp_path / "outbox"
        outbox.mkdir()
        (staging / "session_001.json").write_text(
            json.dumps(record_data), encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.OUTBOX_DIR", outbox)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        result = runner.invoke(cli, ["submit"], input="y\n")
        assert result.exit_code == 0

        outbox_files = list(outbox.glob("*.jsonl"))
        assert len(outbox_files) == 1
        content = json.loads(outbox_files[0].read_text(encoding="utf-8").strip())

        # Outcome must survive
        assert content.get("outcome") is not None
        assert content["outcome"]["user_rating"] == 4
        assert "task_completed" in content["outcome"]["outcome_tags"]

        # Pain points must survive
        assert content.get("pain_points") is not None
        assert len(content["pain_points"]) >= 1
        assert content["pain_points"][0]["category"] == "tool_call_failure"

        # Quality must also be present alongside annotations
        assert content.get("quality") is not None


# ---------------------------------------------------------------------------
# Rate command tests
# ---------------------------------------------------------------------------


class TestRateCommand:
    """Test the kajiba rate command."""

    def test_rate_with_score_and_tags(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Rate with --score and --tags saves outcome to staging file."""
        record_data = _minimal_record_data()
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "session_001.json").write_text(
            json.dumps(record_data), encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        result = runner.invoke(cli, ["rate", "--score", "4", "--tags", "task_completed"])
        assert result.exit_code == 0
        assert "Rating saved" in result.output

        # Re-read the staging file and verify outcome
        content = json.loads((staging / "session_001.json").read_text(encoding="utf-8"))
        assert content["outcome"]["user_rating"] == 4
        assert content["outcome"]["outcome_tags"] == ["task_completed"]

    def test_rate_with_score_only(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Rate with --score only saves outcome with empty tags."""
        record_data = _minimal_record_data()
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "session_001.json").write_text(
            json.dumps(record_data), encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        result = runner.invoke(cli, ["rate", "--score", "3", "--tags", ""])
        assert result.exit_code == 0

        content = json.loads((staging / "session_001.json").read_text(encoding="utf-8"))
        assert content["outcome"]["user_rating"] == 3
        assert content["outcome"]["outcome_tags"] == []

    def test_rate_with_comment(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Rate with --comment saves user_comment."""
        record_data = _minimal_record_data()
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "session_001.json").write_text(
            json.dumps(record_data), encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        result = runner.invoke(
            cli,
            ["rate", "--score", "4", "--tags", "task_completed", "--comment", "Good session"],
        )
        assert result.exit_code == 0

        content = json.loads((staging / "session_001.json").read_text(encoding="utf-8"))
        assert content["outcome"]["user_comment"] == "Good session"

    def test_rate_no_staging(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Rate with empty staging shows 'No sessions found'."""
        staging = tmp_path / "staging"
        staging.mkdir()

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        result = runner.invoke(cli, ["rate", "--score", "4"])
        assert result.exit_code == 0
        assert "No sessions found" in result.output

    def test_rate_appears_in_help(self, runner: CliRunner) -> None:
        """Rate command should appear in kajiba --help."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "rate" in result.output

    def test_rate_saves_to_staging(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Rate a record, then load it fresh from disk — outcome persists."""
        record_data = _minimal_record_data()
        staging = tmp_path / "staging"
        staging.mkdir()
        staging_file = staging / "session_001.json"
        staging_file.write_text(json.dumps(record_data), encoding="utf-8")

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        runner.invoke(cli, ["rate", "--score", "5", "--tags", "perfect"])

        # Load fresh from disk
        from kajiba.schema import validate_record
        fresh = validate_record(json.loads(staging_file.read_text(encoding="utf-8")))
        assert fresh.outcome is not None
        assert fresh.outcome.user_rating == 5
        assert "perfect" in fresh.outcome.outcome_tags

    def test_rate_then_submit_preserves_both(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Rate a staged record, then submit — outbox has outcome + quality."""
        record_data = _minimal_record_data()
        staging = tmp_path / "staging"
        staging.mkdir()
        outbox = tmp_path / "outbox"
        outbox.mkdir()
        (staging / "session_001.json").write_text(
            json.dumps(record_data), encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.OUTBOX_DIR", outbox)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        # Rate first
        runner.invoke(cli, ["rate", "--score", "4", "--tags", "task_completed"])

        # Submit (confirm with y)
        result = runner.invoke(cli, ["submit"], input="y\n")
        assert result.exit_code == 0

        outbox_files = list(outbox.glob("*.jsonl"))
        assert len(outbox_files) == 1
        content = json.loads(outbox_files[0].read_text(encoding="utf-8").strip())

        # Outcome from rate
        assert content.get("outcome") is not None
        assert content["outcome"]["user_rating"] == 4

        # Quality from submit
        assert content.get("quality") is not None
