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
