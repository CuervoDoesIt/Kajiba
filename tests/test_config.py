"""Tests for the Kajiba config module.

Covers config read/write, validation schema, tier comparison,
activity logging, and pending notification display.
"""

import json
from pathlib import Path
from typing import Optional

import pytest

yaml = pytest.importorskip("yaml")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect Path.home() to a temp directory for config isolation."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def config_path(fake_home: Path) -> Path:
    """Return the expected config file path under the fake home."""
    return fake_home / ".hermes" / "config.yaml"


@pytest.fixture
def fake_activity_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ACTIVITY_LOG to a temp file."""
    activity_log = tmp_path / "kajiba" / "activity.jsonl"
    monkeypatch.setattr("kajiba.config.ACTIVITY_LOG", activity_log)
    return activity_log


# ---------------------------------------------------------------------------
# _load_config_value tests
# ---------------------------------------------------------------------------


class TestLoadConfigValue:
    """Tests for _load_config_value."""

    def test_returns_default_when_no_config_file(self, fake_home: Path) -> None:
        """Returns default when ~/.hermes/config.yaml does not exist."""
        from kajiba.config import _load_config_value

        result = _load_config_value("consent_level", "full")
        assert result == "full"

    def test_reads_value_from_yaml(self, fake_home: Path, config_path: Path) -> None:
        """Reads value from YAML when config file exists under kajiba section."""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            yaml.safe_dump({"kajiba": {"consent_level": "anonymous"}}),
            encoding="utf-8",
        )

        from kajiba.config import _load_config_value

        result = _load_config_value("consent_level", "full")
        assert result == "anonymous"

    def test_returns_default_when_yaml_not_importable(
        self, fake_home: Path, config_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Returns default when PyYAML is not importable."""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            yaml.safe_dump({"kajiba": {"consent_level": "anonymous"}}),
            encoding="utf-8",
        )

        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError("mocked")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        from kajiba.config import _load_config_value

        result = _load_config_value("consent_level", "full")
        assert result == "full"


# ---------------------------------------------------------------------------
# _save_config_value tests
# ---------------------------------------------------------------------------


class TestSaveConfigValue:
    """Tests for _save_config_value."""

    def test_writes_value_to_yaml(self, fake_home: Path, config_path: Path) -> None:
        """Writes value to ~/.hermes/config.yaml under kajiba section."""
        from kajiba.config import _save_config_value

        _save_config_value("consent_level", "anonymous")

        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert data["kajiba"]["consent_level"] == "anonymous"

    def test_creates_config_file_if_missing(self, fake_home: Path, config_path: Path) -> None:
        """Creates config file if it does not exist."""
        assert not config_path.exists()

        from kajiba.config import _save_config_value

        _save_config_value("consent_level", "full")
        assert config_path.exists()

    def test_preserves_existing_non_kajiba_keys(
        self, fake_home: Path, config_path: Path,
    ) -> None:
        """Preserves existing non-kajiba config keys."""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            yaml.safe_dump({"other_app": {"key": "value"}, "kajiba": {"old": "val"}}),
            encoding="utf-8",
        )

        from kajiba.config import _save_config_value

        _save_config_value("consent_level", "anonymous")

        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert data["other_app"]["key"] == "value"
        assert data["kajiba"]["consent_level"] == "anonymous"
        assert data["kajiba"]["old"] == "val"

    def test_coerces_true_false_to_booleans(
        self, fake_home: Path, config_path: Path,
    ) -> None:
        """Coerces 'true'/'false' strings to booleans."""
        from kajiba.config import _save_config_value

        _save_config_value("auto_submit", "true")
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert data["kajiba"]["auto_submit"] is True

        _save_config_value("auto_submit", "false")
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert data["kajiba"]["auto_submit"] is False

    def test_coerces_digit_strings_to_integers(
        self, fake_home: Path, config_path: Path,
    ) -> None:
        """Coerces digit strings to integers."""
        from kajiba.config import _save_config_value

        _save_config_value("auto_submit_interval", "30")
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert data["kajiba"]["auto_submit_interval"] == 30

    def test_raises_click_exception_when_yaml_missing(
        self, fake_home: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Raises ClickException when PyYAML is missing."""
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError("mocked")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        import click
        from kajiba.config import _save_config_value

        with pytest.raises(click.exceptions.ClickException, match="PyYAML"):
            _save_config_value("consent_level", "full")


# ---------------------------------------------------------------------------
# tier_meets_threshold tests
# ---------------------------------------------------------------------------


class TestTierMeetsThreshold:
    """Tests for tier_meets_threshold."""

    def test_gold_meets_silver(self) -> None:
        """Gold meets a silver threshold."""
        from kajiba.config import tier_meets_threshold

        assert tier_meets_threshold("gold", "silver") is True

    def test_bronze_does_not_meet_gold(self) -> None:
        """Bronze does not meet a gold threshold."""
        from kajiba.config import tier_meets_threshold

        assert tier_meets_threshold("bronze", "gold") is False

    def test_silver_meets_silver(self) -> None:
        """Equal tier meets threshold."""
        from kajiba.config import tier_meets_threshold

        assert tier_meets_threshold("silver", "silver") is True

    def test_unknown_tier_does_not_meet(self) -> None:
        """Unknown tier does not meet threshold."""
        from kajiba.config import tier_meets_threshold

        assert tier_meets_threshold("unknown_tier", "silver") is False


# ---------------------------------------------------------------------------
# VALID_CONFIG_KEYS tests
# ---------------------------------------------------------------------------


class TestValidConfigKeys:
    """Tests for VALID_CONFIG_KEYS constant."""

    def test_contains_required_keys(self) -> None:
        """Contains contribution_mode, min_quality_tier, consent_level, auto_submit_interval."""
        from kajiba.config import VALID_CONFIG_KEYS

        assert "contribution_mode" in VALID_CONFIG_KEYS
        assert "min_quality_tier" in VALID_CONFIG_KEYS
        assert "consent_level" in VALID_CONFIG_KEYS
        assert "auto_submit_interval" in VALID_CONFIG_KEYS

    def test_contribution_mode_choices(self) -> None:
        """contribution_mode choices are ad-hoc and continuous."""
        from kajiba.config import VALID_CONFIG_KEYS

        assert VALID_CONFIG_KEYS["contribution_mode"]["choices"] == ["ad-hoc", "continuous"]


# ---------------------------------------------------------------------------
# _log_activity tests
# ---------------------------------------------------------------------------


class TestLogActivity:
    """Tests for _log_activity."""

    def test_writes_json_line_to_activity_log(
        self, fake_activity_log: Path,
    ) -> None:
        """Writes JSON line with action, record_id, quality_tier, timestamp keys."""
        from kajiba.config import _log_activity

        _log_activity("auto_submitted", "abc123", "gold")

        assert fake_activity_log.exists()
        line = json.loads(fake_activity_log.read_text(encoding="utf-8").strip())
        assert line["action"] == "auto_submitted"
        assert line["record_id"] == "abc123"
        assert line["quality_tier"] == "gold"
        assert "timestamp" in line


# ---------------------------------------------------------------------------
# _show_pending_notifications tests
# ---------------------------------------------------------------------------


class TestShowPendingNotifications:
    """Tests for _show_pending_notifications."""

    def test_returns_formatted_parts(self, fake_activity_log: Path) -> None:
        """Returns formatted parts for auto_submitted and queued_for_review entries."""
        fake_activity_log.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            json.dumps({"action": "auto_submitted", "record_id": "r1", "quality_tier": "gold", "timestamp": "t1"}),
            json.dumps({"action": "auto_submitted", "record_id": "r2", "quality_tier": "silver", "timestamp": "t2"}),
            json.dumps({"action": "queued_for_review", "record_id": "r3", "quality_tier": "bronze", "timestamp": "t3"}),
        ]
        fake_activity_log.write_text("\n".join(lines) + "\n", encoding="utf-8")

        from kajiba.config import _show_pending_notifications

        result = _show_pending_notifications()
        assert result is not None
        assert "2 record(s) auto-submitted" in result
        assert "1 queued for review" in result

    def test_deletes_activity_log_after_reading(self, fake_activity_log: Path) -> None:
        """Deletes activity log after reading."""
        fake_activity_log.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            json.dumps({"action": "auto_submitted", "record_id": "r1", "quality_tier": "gold", "timestamp": "t1"}),
        ]
        fake_activity_log.write_text("\n".join(lines) + "\n", encoding="utf-8")

        from kajiba.config import _show_pending_notifications

        _show_pending_notifications()
        assert not fake_activity_log.exists()


# ---------------------------------------------------------------------------
# _submit_record tests
# ---------------------------------------------------------------------------


class TestSubmitRecord:
    """Tests for _submit_record helper extracted in cli.py."""

    def test_submit_record_writes_to_outbox(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_submit_record applies full pipeline and writes to outbox."""
        outbox = tmp_path / "outbox"
        outbox.mkdir()
        monkeypatch.setattr("kajiba.cli.OUTBOX_DIR", outbox)
        monkeypatch.setattr("kajiba.cli.KAJIBA_BASE", tmp_path)
        monkeypatch.setattr("kajiba.cli.STAGING_DIR", tmp_path / "staging")
        (tmp_path / "staging").mkdir()

        from kajiba.schema import validate_record
        from kajiba.scrubber import scrub_record
        from kajiba.cli import _submit_record

        record_data = {
            "schema_version": "0.1.0",
            "record_type": "task_trajectory",
            "created_at": "2026-03-29T12:00:00Z",
            "trajectory": {
                "format": "sharegpt_extended",
                "conversations": [
                    {"from": "human", "value": "Hello"},
                    {"from": "gpt", "value": "Hi there"},
                ],
                "turn_count": 2,
                "total_tool_calls": 0,
                "successful_tool_calls": 0,
                "failed_tool_calls": 0,
            },
        }
        record = validate_record(record_data)
        scrubbed, scrub_log = scrub_record(record)

        outbox_file, quality_result = _submit_record(record, scrubbed, scrub_log)

        assert outbox_file.exists()
        assert outbox_file.parent == outbox
        assert quality_result.quality_tier in ("gold", "silver", "bronze", "review_needed")

        # Verify written content is valid JSON
        content = json.loads(outbox_file.read_text(encoding="utf-8").strip())
        assert "record_id" in content
        assert "quality" in content
