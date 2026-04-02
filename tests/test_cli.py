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


# ---------------------------------------------------------------------------
# Report command tests
# ---------------------------------------------------------------------------


class TestReportCommand:
    """Test the kajiba report command."""

    def test_report_with_all_flags(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Report with all flags saves pain point to staging file."""
        record_data = _minimal_record_data()
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "session_001.json").write_text(
            json.dumps(record_data), encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        result = runner.invoke(cli, [
            "report",
            "--category", "tool_call_failure",
            "--description", "Tool crashed",
            "--severity", "high",
        ])
        assert result.exit_code == 0
        assert "Pain point reported" in result.output

        content = json.loads((staging / "session_001.json").read_text(encoding="utf-8"))
        assert len(content["pain_points"]) == 1
        pp = content["pain_points"][0]
        assert pp["category"] == "tool_call_failure"
        assert pp["description"] == "Tool crashed"
        assert pp["severity"] == "high"

    def test_report_appends_to_existing(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Report appends to existing pain_points, does not overwrite."""
        record_data = _minimal_record_data()
        record_data["pain_points"] = [
            {
                "category": "hallucination_factual",
                "description": "Made up a function",
                "severity": "medium",
            },
        ]
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "session_001.json").write_text(
            json.dumps(record_data), encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        result = runner.invoke(cli, [
            "report",
            "--category", "tool_call_failure",
            "--description", "Tool crashed",
            "--severity", "high",
        ])
        assert result.exit_code == 0

        content = json.loads((staging / "session_001.json").read_text(encoding="utf-8"))
        assert len(content["pain_points"]) == 2
        assert content["pain_points"][0]["category"] == "hallucination_factual"
        assert content["pain_points"][1]["category"] == "tool_call_failure"

    def test_report_no_staging(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Report with empty staging shows 'No sessions found'."""
        staging = tmp_path / "staging"
        staging.mkdir()

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        result = runner.invoke(cli, [
            "report",
            "--category", "tool_call_failure",
            "--description", "Test",
            "--severity", "medium",
        ])
        assert result.exit_code == 0
        assert "No sessions found" in result.output

    def test_report_appears_in_help(self, runner: CliRunner) -> None:
        """Report command should appear in kajiba --help."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "report" in result.output

    def test_report_saves_to_staging(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Report a pain point, load file fresh, verify it persists."""
        record_data = _minimal_record_data()
        staging = tmp_path / "staging"
        staging.mkdir()
        staging_file = staging / "session_001.json"
        staging_file.write_text(json.dumps(record_data), encoding="utf-8")

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        runner.invoke(cli, [
            "report",
            "--category", "context_loss",
            "--description", "Lost context",
            "--severity", "low",
        ])

        from kajiba.schema import validate_record
        fresh = validate_record(json.loads(staging_file.read_text(encoding="utf-8")))
        assert fresh.pain_points is not None
        assert len(fresh.pain_points) == 1
        assert fresh.pain_points[0].category == "context_loss"


# ---------------------------------------------------------------------------
# Merged quality panel tests
# ---------------------------------------------------------------------------


class TestPreviewMergedQualityPanel:
    """Test that preview shows merged quality + annotation panel."""

    def test_preview_shows_user_rating(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Preview of a rated record shows user_rating in output."""
        record_data = _minimal_record_data()
        record_data["outcome"] = {
            "user_rating": 4,
            "outcome_tags": ["task_completed"],
        }
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "session_001.json").write_text(
            json.dumps(record_data), encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        result = runner.invoke(cli, ["preview"])
        assert result.exit_code == 0
        assert "4/5" in result.output

    def test_preview_shows_pain_point(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Preview of a record with pain_points shows category in output."""
        record_data = _minimal_record_data()
        record_data["pain_points"] = [
            {
                "category": "tool_call_failure",
                "description": "Broken",
                "severity": "medium",
            },
        ]
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "session_001.json").write_text(
            json.dumps(record_data), encoding="utf-8",
        )

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        result = runner.invoke(cli, ["preview"])
        assert result.exit_code == 0
        assert "Pain Points" in result.output
        assert "tool_call_failure" in result.output


class TestFullAnnotationPipeline:
    """Test rate + report + submit end-to-end pipeline."""

    def test_submit_preserves_rate_and_report(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Rate, report, then submit — outbox has outcome, pain_points, and quality."""
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

        # Rate
        runner.invoke(cli, ["rate", "--score", "4", "--tags", "task_completed"])

        # Report
        runner.invoke(cli, [
            "report",
            "--category", "tool_call_failure",
            "--description", "Tool was slow",
            "--severity", "low",
        ])

        # Submit
        result = runner.invoke(cli, ["submit"], input="y\n")
        assert result.exit_code == 0

        outbox_files = list(outbox.glob("*.jsonl"))
        assert len(outbox_files) == 1
        content = json.loads(outbox_files[0].read_text(encoding="utf-8").strip())

        # Outcome from rate
        assert content.get("outcome") is not None
        assert content["outcome"]["user_rating"] == 4

        # Pain points from report
        assert content.get("pain_points") is not None
        assert len(content["pain_points"]) >= 1
        assert content["pain_points"][0]["category"] == "tool_call_failure"

        # Quality from submit
        assert content.get("quality") is not None
        assert "quality_tier" in content["quality"]


# ---------------------------------------------------------------------------
# Publish command tests
# ---------------------------------------------------------------------------


def _make_outbox_record() -> dict:
    """Build a minimal valid record dict for publish/delete test fixtures.

    Returns:
        Dict suitable for writing as an outbox JSONL line.
    """
    return {
        "schema_version": "0.1.0",
        "record_type": "task_trajectory",
        "record_id": "kajiba_abc123456789",
        "created_at": "2026-03-29T12:00:00Z",
        "trajectory": {
            "format": "sharegpt_extended",
            "conversations": [
                {"from": "human", "value": "Hello world"},
                {"from": "gpt", "value": "Hi there!"},
            ],
            "turn_count": 2,
            "total_tool_calls": 0,
            "successful_tool_calls": 0,
            "failed_tool_calls": 0,
        },
        "model": {
            "model_name": "test-model",
        },
        "quality": {
            "quality_tier": "bronze",
            "composite_score": 0.5,
            "sub_scores": {
                "coherence": 0.5,
                "tool_validity": 0.5,
                "outcome_quality": 0.5,
                "information_density": 0.5,
                "metadata_completeness": 0.5,
            },
            "scored_at": "2026-03-29T12:00:00Z",
        },
        "submission": {
            "consent_level": "full",
        },
    }


class TestPublishCommand:
    """Test the kajiba publish command."""

    def test_publish_no_outbox_records(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Publish with empty outbox should show 'No records to publish'."""
        from unittest.mock import MagicMock
        from kajiba.publisher import GhResult

        outbox_dir = tmp_path / "outbox"
        outbox_dir.mkdir()
        monkeypatch.setattr("kajiba.cli.OUTBOX_DIR", outbox_dir)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        # Mock GitHubOps so auth passes
        mock_gh = MagicMock()
        mock_gh.check_auth.return_value = GhResult(
            success=True, stdout="", stderr="", returncode=0,
        )
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)

        result = runner.invoke(cli, ["publish"])
        assert result.exit_code == 1
        assert "No records to publish" in result.output

    def test_publish_gh_not_installed(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Publish when gh CLI is not installed should show clear error."""
        from unittest.mock import MagicMock
        from kajiba.publisher import GhResult

        mock_gh = MagicMock()
        mock_gh.check_auth.return_value = GhResult(
            success=False,
            stdout="",
            stderr="gh CLI not found. Install from https://cli.github.com/",
            returncode=-1,
        )
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)

        result = runner.invoke(cli, ["publish"])
        assert result.exit_code == 1
        assert "gh CLI not found" in result.output

    def test_publish_gh_not_authenticated(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Publish when gh is not authenticated should show auth error."""
        from unittest.mock import MagicMock
        from kajiba.publisher import GhResult

        mock_gh = MagicMock()
        mock_gh.check_auth.return_value = GhResult(
            success=False,
            stdout="",
            stderr="You are not logged into any GitHub hosts.",
            returncode=1,
        )
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)

        result = runner.invoke(cli, ["publish"])
        assert result.exit_code == 1
        assert "Not authenticated" in result.output

    def test_publish_dry_run(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Publish --dry-run should show summary without creating a PR."""
        from unittest.mock import MagicMock
        from kajiba.publisher import GhResult

        # Set up outbox with a fixture record
        outbox_dir = tmp_path / "outbox"
        outbox_dir.mkdir()
        monkeypatch.setattr("kajiba.cli.OUTBOX_DIR", outbox_dir)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        record_data = _make_outbox_record()
        outbox_file = outbox_dir / "record_test.jsonl"
        outbox_file.write_text(
            json.dumps(record_data) + "\n", encoding="utf-8",
        )

        # Mock GitHubOps
        mock_gh = MagicMock()
        mock_gh.check_auth.return_value = GhResult(
            success=True, stdout="", stderr="", returncode=0,
        )
        mock_gh.get_username.return_value = GhResult(
            success=True, stdout="testuser\n", stderr="", returncode=0,
        )
        mock_gh.fork_repo.return_value = GhResult(
            success=True, stdout="", stderr="", returncode=0,
        )
        mock_gh.pull_latest.return_value = GhResult(
            success=True, stdout="", stderr="", returncode=0,
        )
        mock_gh.create_branch.return_value = GhResult(
            success=True, stdout="", stderr="", returncode=0,
        )
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)

        # Set CLONE_DIR to a temp directory with .git so pull_latest path is used
        clone_dir = tmp_path / "dataset-clone"
        clone_dir.mkdir()
        (clone_dir / ".git").mkdir()
        monkeypatch.setattr("kajiba.cli.CLONE_DIR", clone_dir)

        result = runner.invoke(cli, ["publish", "--dry-run"])
        assert result.exit_code == 0
        assert "Dry Run" in result.output or "Dry run" in result.output
        mock_gh.create_pr.assert_not_called()

    def test_publish_help(self, runner: CliRunner) -> None:
        """Publish --help should show --repo and --dry-run options."""
        result = runner.invoke(cli, ["publish", "--help"])
        assert result.exit_code == 0
        assert "--repo" in result.output
        assert "--dry-run" in result.output


# ---------------------------------------------------------------------------
# Delete command tests
# ---------------------------------------------------------------------------


class TestDeleteCommand:
    """Test the kajiba delete command."""

    def test_delete_no_record_id(self, runner: CliRunner) -> None:
        """Delete without record_id argument should show error or usage."""
        result = runner.invoke(cli, ["delete"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output or "RECORD_ID" in result.output

    def test_delete_gh_not_installed(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Delete when gh CLI is not installed should show clear error."""
        from unittest.mock import MagicMock
        from kajiba.publisher import GhResult

        mock_gh = MagicMock()
        mock_gh.check_auth.return_value = GhResult(
            success=False,
            stdout="",
            stderr="gh CLI not found. Install from https://cli.github.com/",
            returncode=-1,
        )
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)

        result = runner.invoke(cli, ["delete", "kajiba_abc123"])
        assert result.exit_code == 1
        assert "gh CLI not found" in result.output

    def test_delete_help(self, runner: CliRunner) -> None:
        """Delete --help should show RECORD_ID argument and --reason option."""
        result = runner.invoke(cli, ["delete", "--help"])
        assert result.exit_code == 0
        assert "RECORD_ID" in result.output
        assert "--reason" in result.output


# ---------------------------------------------------------------------------
# Config subcommands tests (Task 2)
# ---------------------------------------------------------------------------

yaml = pytest.importorskip("yaml")


class TestConfigSubcommands:
    """Tests for the restructured config command with set/get/show subcommands."""

    def test_bare_config_shows_table(self, runner: CliRunner) -> None:
        """Bare `kajiba config` still shows config table (backward compat)."""
        result = runner.invoke(cli, ["config"])
        assert result.exit_code == 0
        assert "Configuration" in result.output

    def test_config_show_has_source_column(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`kajiba config show` shows table with Source column."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = runner.invoke(cli, ["config", "show"])
        assert result.exit_code == 0
        assert "Source" in result.output

    def test_config_show_source_indicates_default(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Config show Source column shows 'default' for hardcoded defaults."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = runner.invoke(cli, ["config", "show"])
        assert result.exit_code == 0
        assert "default" in result.output

    def test_config_show_source_indicates_config(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Config show Source column shows 'config' for values from config.yaml."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        config_path = tmp_path / ".hermes" / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            yaml.safe_dump({"kajiba": {"consent_level": "anonymous"}}),
            encoding="utf-8",
        )
        result = runner.invoke(cli, ["config", "show"])
        assert result.exit_code == 0
        assert "config" in result.output

    def test_config_set_valid_choice(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`kajiba config set contribution_mode continuous` persists and prints green."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = runner.invoke(cli, ["config", "set", "contribution_mode", "continuous"])
        assert result.exit_code == 0
        assert "Set contribution_mode = continuous" in result.output

    def test_config_set_min_quality_tier(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`kajiba config set min_quality_tier gold` persists value."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = runner.invoke(cli, ["config", "set", "min_quality_tier", "gold"])
        assert result.exit_code == 0
        assert "Set min_quality_tier = gold" in result.output

    def test_config_set_invalid_choice(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`kajiba config set min_quality_tier platinum` prints error."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = runner.invoke(cli, ["config", "set", "min_quality_tier", "platinum"])
        assert result.exit_code == 0
        assert "Invalid value for min_quality_tier" in result.output
        assert "gold, silver, bronze" in result.output

    def test_config_set_unknown_key(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`kajiba config set unknown_key foo` prints error."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = runner.invoke(cli, ["config", "set", "unknown_key", "foo"])
        assert result.exit_code == 0
        assert "Unknown config key: unknown_key" in result.output

    def test_config_get_after_set(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`kajiba config get contribution_mode` returns value after set."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        runner.invoke(cli, ["config", "set", "contribution_mode", "continuous"])
        result = runner.invoke(cli, ["config", "get", "contribution_mode"])
        assert result.exit_code == 0
        assert "contribution_mode = continuous" in result.output

    def test_config_get_default_value(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`kajiba config get min_quality_tier` shows default with (default) suffix."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = runner.invoke(cli, ["config", "get", "min_quality_tier"])
        assert result.exit_code == 0
        assert "min_quality_tier = silver" in result.output
        assert "default" in result.output

    def test_config_get_unknown_key(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`kajiba config get unknown_key` prints error."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = runner.invoke(cli, ["config", "get", "unknown_key"])
        assert result.exit_code == 0
        assert "Unknown config key: unknown_key" in result.output

    def test_config_set_integer_value(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`kajiba config set auto_submit_interval 30` stores integer 30."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = runner.invoke(cli, ["config", "set", "auto_submit_interval", "30"])
        assert result.exit_code == 0
        assert "Set auto_submit_interval = 30" in result.output

    def test_config_set_boolean_value(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`kajiba config set auto_submit true` stores boolean True."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = runner.invoke(cli, ["config", "set", "auto_submit", "true"])
        assert result.exit_code == 0
        assert "Set auto_submit = true" in result.output


# ---------------------------------------------------------------------------
# Review command tests (Plan 02)
# ---------------------------------------------------------------------------


class TestReviewCommand:
    """Test the kajiba review command."""

    def test_review_empty_staging(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Review with no staged records prints empty-state message."""
        staging = tmp_path / "staging"
        staging.mkdir()

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        result = runner.invoke(cli, ["review"])
        assert result.exit_code == 0
        assert "No records in staging to review." in result.output

    def test_review_approve_moves_to_outbox(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Review with one record, approve -> record moves to outbox, staging deleted."""
        record_data = _minimal_record_data()
        staging = tmp_path / "staging"
        staging.mkdir()
        outbox = tmp_path / "outbox"
        outbox.mkdir()
        staging_file = staging / "session_001.json"
        staging_file.write_text(json.dumps(record_data), encoding="utf-8")

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.OUTBOX_DIR", outbox)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        result = runner.invoke(cli, ["review"], input="approve\n")
        assert result.exit_code == 0
        assert "Approved and submitted" in result.output

        # Outbox should have a file
        outbox_files = list(outbox.glob("*.jsonl"))
        assert len(outbox_files) == 1

        # Staging file should be deleted
        assert not staging_file.exists()

    def test_review_reject_removes_from_staging(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Review with one record, reject -> staging file deleted."""
        record_data = _minimal_record_data()
        staging = tmp_path / "staging"
        staging.mkdir()
        outbox = tmp_path / "outbox"
        outbox.mkdir()
        staging_file = staging / "session_001.json"
        staging_file.write_text(json.dumps(record_data), encoding="utf-8")

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.OUTBOX_DIR", outbox)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        result = runner.invoke(cli, ["review"], input="reject\n")
        assert result.exit_code == 0
        assert "Record rejected and removed from staging." in result.output

        # Staging file should be deleted
        assert not staging_file.exists()

        # Outbox should be empty (rejected, not submitted)
        outbox_files = list(outbox.glob("*.jsonl"))
        assert len(outbox_files) == 0

    def test_review_skip_preserves_staging(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Review with one record, skip -> staging file preserved."""
        record_data = _minimal_record_data()
        staging = tmp_path / "staging"
        staging.mkdir()
        outbox = tmp_path / "outbox"
        outbox.mkdir()
        staging_file = staging / "session_001.json"
        staging_file.write_text(json.dumps(record_data), encoding="utf-8")

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.OUTBOX_DIR", outbox)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        result = runner.invoke(cli, ["review"], input="skip\n")
        assert result.exit_code == 0
        assert "Skipped." in result.output

        # Staging file should still exist
        assert staging_file.exists()

    def test_review_quit_with_summary(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Review with two records, approve then quit -> first submitted, second untouched."""
        staging = tmp_path / "staging"
        staging.mkdir()
        outbox = tmp_path / "outbox"
        outbox.mkdir()

        record_data_1 = _minimal_record_data(conversation_text="First session")
        record_data_2 = _minimal_record_data(conversation_text="Second session")
        staging_1 = staging / "session_001.json"
        staging_2 = staging / "session_002.json"
        staging_1.write_text(json.dumps(record_data_1), encoding="utf-8")
        staging_2.write_text(json.dumps(record_data_2), encoding="utf-8")

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.OUTBOX_DIR", outbox)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        result = runner.invoke(cli, ["review"], input="approve\nquit\n")
        assert result.exit_code == 0
        assert "1 approved" in result.output
        assert "0 rejected" in result.output
        assert "0 skipped" in result.output

    def test_review_summary_line(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Review summary shows 'Review complete: N approved, N rejected, N skipped'."""
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

        result = runner.invoke(cli, ["review"], input="skip\n")
        assert result.exit_code == 0
        assert "Review complete:" in result.output

    def test_review_approve_calls_submit_record(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Review approve creates an outbox file (proves _submit_record was called)."""
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

        result = runner.invoke(cli, ["review"], input="approve\n")
        assert result.exit_code == 0

        # Outbox file exists => _submit_record was called
        outbox_files = list(outbox.glob("*.jsonl"))
        assert len(outbox_files) == 1

    def test_review_submit_error_preserves_staging(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If _submit_record raises during approve, staging file is NOT deleted."""
        from unittest.mock import patch

        record_data = _minimal_record_data()
        staging = tmp_path / "staging"
        staging.mkdir()
        outbox = tmp_path / "outbox"
        outbox.mkdir()
        staging_file = staging / "session_001.json"
        staging_file.write_text(json.dumps(record_data), encoding="utf-8")

        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.OUTBOX_DIR", outbox)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        with patch("kajiba.cli._submit_record", side_effect=RuntimeError("disk full")):
            result = runner.invoke(cli, ["review"], input="approve\n")

        assert result.exit_code == 0
        # Staging file must still exist (data loss prevention)
        assert staging_file.exists()
        assert "Error submitting record" in result.output


# ---------------------------------------------------------------------------
# Activity notification tests (Plan 02)
# ---------------------------------------------------------------------------


class TestActivityNotification:
    """Test that activity notifications appear at start of CLI output."""

    def test_notification_shown_when_activity_exists(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Activity notification appears when activity.jsonl has entries."""
        import kajiba.config as config_mod

        # Set up activity log with an entry
        activity_log = tmp_path / "activity.jsonl"
        activity_log.write_text(
            '{"action": "auto_submitted", "record_id": "test123", '
            '"quality_tier": "silver", "timestamp": "2026-04-01T00:00:00Z"}\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(config_mod, "ACTIVITY_LOG", activity_log)

        # Also set staging so review shows empty-state
        staging = tmp_path / "staging"
        staging.mkdir()
        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        result = runner.invoke(cli, ["review"])
        assert result.exit_code == 0
        assert "auto-submitted" in result.output

    def test_notification_cleared_after_display(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Activity log file is deleted after notification is shown."""
        import kajiba.config as config_mod

        activity_log = tmp_path / "activity.jsonl"
        activity_log.write_text(
            '{"action": "auto_submitted", "record_id": "test123", '
            '"quality_tier": "silver", "timestamp": "2026-04-01T00:00:00Z"}\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(config_mod, "ACTIVITY_LOG", activity_log)

        staging = tmp_path / "staging"
        staging.mkdir()
        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        runner.invoke(cli, ["review"])
        # Activity log should be deleted after display
        assert not activity_log.exists()

    def test_no_notification_when_no_activity(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """No notification appears when activity.jsonl is missing."""
        import kajiba.config as config_mod

        activity_log = tmp_path / "activity.jsonl"
        # Do not create the file
        monkeypatch.setattr(config_mod, "ACTIVITY_LOG", activity_log)

        staging = tmp_path / "staging"
        staging.mkdir()
        monkeypatch.setattr("kajiba.cli.STAGING_DIR", staging)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)

        result = runner.invoke(cli, ["review"])
        assert result.exit_code == 0
        assert "auto-submitted" not in result.output


# ---------------------------------------------------------------------------
# Browse command tests
# ---------------------------------------------------------------------------


def _load_enriched_catalog() -> str:
    """Load the enriched_catalog.json fixture and return as a JSON string."""
    fixture_path = Path(__file__).parent / "fixtures" / "enriched_catalog.json"
    return fixture_path.read_text(encoding="utf-8")


def _make_mock_gh_ops_for_browse(
    catalog_json: str = "",
    success: bool = True,
    returncode: int = 0,
    stderr: str = "",
):
    """Create a mock GitHubOps that returns catalog_json from get_file_contents."""
    from unittest.mock import MagicMock
    from kajiba.publisher import GhResult

    mock_ops = MagicMock()
    mock_ops.check_auth.return_value = GhResult(
        success=True, stdout="", stderr="", returncode=0,
    )
    mock_ops.get_file_contents.return_value = GhResult(
        success=success,
        stdout=catalog_json if success else "",
        stderr=stderr,
        returncode=returncode,
    )
    return mock_ops


class TestBrowseCommand:
    """Test the kajiba browse command."""

    def test_browse_summary_table(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """browse with no filters renders summary table with model names, tiers, totals (D-01)."""
        catalog_json = _load_enriched_catalog()
        mock_gh = _make_mock_gh_ops_for_browse(catalog_json=catalog_json)
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)

        result = runner.invoke(cli, ["browse"])
        assert result.exit_code == 0
        assert "Kajiba Dataset Catalog" in result.output
        assert "Llama 3" in result.output
        assert "GPT-4o" in result.output
        assert "2 model(s)" in result.output

    def test_browse_model_drilldown(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """browse --model llama-3 renders metadata panel with params, quant, ctx (D-02)."""
        catalog_json = _load_enriched_catalog()
        mock_gh = _make_mock_gh_ops_for_browse(catalog_json=catalog_json)
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)

        result = runner.invoke(cli, ["browse", "--model", "llama-3"])
        assert result.exit_code == 0
        assert "Model Metadata" in result.output
        assert "8B" in result.output
        assert "70B" in result.output
        assert "Q4_K_M" in result.output
        assert "Tier Breakdown" in result.output

    def test_browse_tier_filter(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """browse --tier gold shows summary table narrowed to gold entries (D-03)."""
        catalog_json = _load_enriched_catalog()
        mock_gh = _make_mock_gh_ops_for_browse(catalog_json=catalog_json)
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)

        result = runner.invoke(cli, ["browse", "--tier", "gold"])
        assert result.exit_code == 0
        assert "Kajiba Dataset Catalog" in result.output

    def test_browse_model_and_tier_filter(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """browse --model llama-3 --tier gold renders drill-down for only gold (D-03+D-10)."""
        catalog_json = _load_enriched_catalog()
        mock_gh = _make_mock_gh_ops_for_browse(catalog_json=catalog_json)
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)

        result = runner.invoke(cli, ["browse", "--model", "llama-3", "--tier", "gold"])
        assert result.exit_code == 0
        assert "Model Metadata" in result.output
        assert "Tier Breakdown" in result.output

    def test_browse_empty_catalog(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """browse on empty catalog shows 'No records published yet' (D-04)."""
        empty_catalog = json.dumps({"models": {}, "total_records": 0, "total_size_bytes": 0})
        mock_gh = _make_mock_gh_ops_for_browse(catalog_json=empty_catalog)
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)

        result = runner.invoke(cli, ["browse"])
        assert result.exit_code == 0
        assert "No records published yet" in result.output
        assert "kajiba publish" in result.output

    def test_browse_catalog_fetch_failure(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """browse on catalog fetch failure shows error with auth hint (D-04)."""
        mock_gh = _make_mock_gh_ops_for_browse(
            success=False, returncode=1, stderr="HTTP 403: Resource not accessible",
        )
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)

        result = runner.invoke(cli, ["browse"])
        assert result.exit_code == 1
        assert "Could not fetch catalog" in result.output
        assert "gh auth status" in result.output

    def test_browse_no_match(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """browse --model nonexistent shows available models/tiers (D-11)."""
        catalog_json = _load_enriched_catalog()
        mock_gh = _make_mock_gh_ops_for_browse(catalog_json=catalog_json)
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)

        result = runner.invoke(cli, ["browse", "--model", "nonexistent"])
        assert result.exit_code == 0
        assert "No records match" in result.output
        assert "llama-3" in result.output or "gpt-4o" in result.output

    def test_browse_missing_metadata(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """browse --model shows '---' for missing parameter_counts (D-08)."""
        catalog_json = _load_enriched_catalog()
        mock_gh = _make_mock_gh_ops_for_browse(catalog_json=catalog_json)
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)

        # GPT-4o has empty parameter_counts and quantizations
        result = runner.invoke(cli, ["browse", "--model", "gpt-4o"])
        assert result.exit_code == 0
        assert "---" in result.output

    def test_browse_gh_not_found(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """browse when gh CLI not found (returncode -1) shows install URL (Pitfall 3)."""
        mock_gh = _make_mock_gh_ops_for_browse(
            success=False, returncode=-1, stderr="gh CLI not found",
        )
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)

        result = runner.invoke(cli, ["browse"])
        assert result.exit_code == 1
        assert "gh CLI not found" in result.output
        assert "https://cli.github.com/" in result.output


# ---------------------------------------------------------------------------
# Download command tests
# ---------------------------------------------------------------------------


def _make_mock_gh_ops_for_download(
    catalog_json: str = "",
    shard_contents: dict = None,
    failed_shards: set = None,
):
    """Create a mock GitHubOps for download tests.

    Args:
        catalog_json: JSON string for catalog.json response.
        shard_contents: Dict mapping shard path to content string.
        failed_shards: Set of shard paths that should fail.
    """
    from unittest.mock import MagicMock
    from kajiba.publisher import GhResult

    if shard_contents is None:
        shard_contents = {}
    if failed_shards is None:
        failed_shards = set()

    mock_ops = MagicMock()
    mock_ops.check_auth.return_value = GhResult(
        success=True, stdout="", stderr="", returncode=0,
    )

    def _get_file_contents(path: str, raw: bool = False):
        if path == "catalog.json":
            return GhResult(
                success=True, stdout=catalog_json, stderr="", returncode=0,
            )
        if path in failed_shards:
            return GhResult(
                success=False, stdout="", stderr="Not Found", returncode=1,
            )
        content = shard_contents.get(path, '{"record_id": "test"}\n')
        return GhResult(
            success=True, stdout=content, stderr="", returncode=0,
        )

    mock_ops.get_file_contents.side_effect = _get_file_contents
    return mock_ops


class TestDownloadCommand:
    """Test the kajiba download command."""

    def test_download_with_filters(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """download --model llama-3 --tier gold fetches matching shards to output dir."""
        catalog_json = _load_enriched_catalog()
        shard_data = '{"record_id": "r1"}\n{"record_id": "r2"}\n'
        mock_gh = _make_mock_gh_ops_for_download(
            catalog_json=catalog_json,
            shard_contents={
                "data/llama-3/gold/shard_a3.jsonl": shard_data,
                "data/llama-3/gold/shard_f7.jsonl": shard_data,
            },
        )
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)
        monkeypatch.setattr("kajiba.cli.DOWNLOADS_DIR", tmp_path)

        result = runner.invoke(cli, [
            "download", "--model", "llama-3", "--tier", "gold",
            "--output", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "Downloaded" in result.output
        # Verify files exist in model/tier directory structure
        shard_a3 = tmp_path / "data" / "llama-3" / "gold" / "shard_a3.jsonl"
        shard_f7 = tmp_path / "data" / "llama-3" / "gold" / "shard_f7.jsonl"
        assert shard_a3.exists()
        assert shard_f7.exists()

    def test_download_unfiltered_abort(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """download without filters shows confirmation prompt, aborts on N (D-12)."""
        catalog_json = _load_enriched_catalog()
        mock_gh = _make_mock_gh_ops_for_download(catalog_json=catalog_json)
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)

        result = runner.invoke(cli, ["download"], input="N\n")
        assert result.exit_code == 0
        assert "This will download all" in result.output
        assert "Downloaded" not in result.output

    def test_download_unfiltered_confirm(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """download without filters proceeds when user confirms y."""
        catalog_json = _load_enriched_catalog()
        mock_gh = _make_mock_gh_ops_for_download(catalog_json=catalog_json)
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)
        monkeypatch.setattr("kajiba.cli.DOWNLOADS_DIR", tmp_path)

        result = runner.invoke(cli, ["download", "--output", str(tmp_path)], input="y\n")
        assert result.exit_code == 0
        assert "Downloaded" in result.output

    def test_download_filtered_skips_confirmation(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """download with --model skips confirmation (filter = intent demonstrated)."""
        catalog_json = _load_enriched_catalog()
        mock_gh = _make_mock_gh_ops_for_download(catalog_json=catalog_json)
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)
        monkeypatch.setattr("kajiba.cli.DOWNLOADS_DIR", tmp_path)

        result = runner.invoke(cli, [
            "download", "--model", "llama-3", "--tier", "gold",
            "--output", str(tmp_path),
        ])
        assert result.exit_code == 0
        # No confirmation prompt expected
        assert "This will download all" not in result.output
        assert "Downloaded" in result.output

    def test_download_no_match(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """download with no catalog match shows no-match feedback (D-11)."""
        catalog_json = _load_enriched_catalog()
        mock_gh = _make_mock_gh_ops_for_download(catalog_json=catalog_json)
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)

        result = runner.invoke(cli, ["download", "--model", "nonexistent"])
        assert result.exit_code == 0
        assert "No records match" in result.output

    def test_download_skip_existing(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """download skips files that already exist at the destination."""
        catalog_json = _load_enriched_catalog()
        mock_gh = _make_mock_gh_ops_for_download(catalog_json=catalog_json)
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)

        # Pre-create one shard file
        existing = tmp_path / "data" / "llama-3" / "gold" / "shard_a3.jsonl"
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text("existing content\n", encoding="utf-8")

        result = runner.invoke(cli, [
            "download", "--model", "llama-3", "--tier", "gold",
            "--output", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "Skipped" in result.output
        # Existing file should not be overwritten
        assert existing.read_text(encoding="utf-8") == "existing content\n"

    def test_download_completion_summary(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """download shows completion summary with shard/record/size counts (D-07)."""
        catalog_json = _load_enriched_catalog()
        shard_data = '{"record_id": "r1"}\n{"record_id": "r2"}\n'
        mock_gh = _make_mock_gh_ops_for_download(
            catalog_json=catalog_json,
            shard_contents={
                "data/llama-3/gold/shard_a3.jsonl": shard_data,
                "data/llama-3/gold/shard_f7.jsonl": shard_data,
            },
        )
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)

        result = runner.invoke(cli, [
            "download", "--model", "llama-3", "--tier", "gold",
            "--output", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "Downloaded 2 shard(s)" in result.output
        assert "4 record(s)" in result.output

    def test_download_custom_output(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """download --output /custom/path writes to the custom path."""
        catalog_json = _load_enriched_catalog()
        mock_gh = _make_mock_gh_ops_for_download(catalog_json=catalog_json)
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)

        custom_dir = tmp_path / "custom_output"
        result = runner.invoke(cli, [
            "download", "--model", "llama-3", "--tier", "gold",
            "--output", str(custom_dir),
        ])
        assert result.exit_code == 0
        assert "Downloaded" in result.output
        assert str(custom_dir) in result.output

    def test_download_gh_not_found(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """download when gh CLI not found shows install URL."""
        from unittest.mock import MagicMock
        from kajiba.publisher import GhResult

        mock_gh = MagicMock()
        mock_gh.get_file_contents.return_value = GhResult(
            success=False, stdout="", stderr="gh CLI not found", returncode=-1,
        )
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)

        result = runner.invoke(cli, ["download", "--model", "test"])
        assert result.exit_code == 1
        assert "gh CLI not found" in result.output
        assert "https://cli.github.com/" in result.output

    def test_download_shard_failure_continues(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """download continues when individual shard fetch fails, reports failure."""
        catalog_json = _load_enriched_catalog()
        shard_data = '{"record_id": "r1"}\n'
        mock_gh = _make_mock_gh_ops_for_download(
            catalog_json=catalog_json,
            shard_contents={
                "data/llama-3/gold/shard_f7.jsonl": shard_data,
            },
            failed_shards={"data/llama-3/gold/shard_a3.jsonl"},
        )
        monkeypatch.setattr("kajiba.cli.GitHubOps", lambda *a, **kw: mock_gh)

        result = runner.invoke(cli, [
            "download", "--model", "llama-3", "--tier", "gold",
            "--output", str(tmp_path),
        ])
        assert result.exit_code == 0
        assert "Failed to download" in result.output
        assert "Downloaded 1 shard(s)" in result.output
        # Verify the successful shard was still written
        successful = tmp_path / "data" / "llama-3" / "gold" / "shard_f7.jsonl"
        assert successful.exists()
