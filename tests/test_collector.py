"""Tests for the session collector."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kajiba.collector import KajibaCollector, _detect_hardware
from kajiba.schema import SCHEMA_VERSION, validate_record


class TestCollectorLifecycle:
    """Test the full collector lifecycle."""

    def test_full_session_lifecycle(self) -> None:
        """Simulate a multi-turn session with tool calls."""
        collector = KajibaCollector()

        # Start session
        collector.on_session_start(
            session_id="test-session-001",
            model_config={
                "model_name": "Hermes-3-Llama-3.1-8B",
                "model_family": "llama",
                "quantization": "Q4_K_M",
                "provider": "ollama",
                "is_local": True,
            },
        )

        # Turn 1: human
        collector.on_turn_complete({
            "role": "human",
            "content": "Deploy the FastAPI service using Docker.",
        })

        # Turn 2: gpt with tool calls
        collector.on_turn_complete({
            "role": "gpt",
            "content": "I'll help you deploy. Let me check the project.",
            "tool_calls": [
                {
                    "name": "terminal",
                    "input": "ls -la /app/",
                    "output": "total 32\n-rw-r--r-- main.py",
                    "status": "success",
                    "latency_ms": 120,
                },
            ],
            "token_count": 45,
            "latency_ms": 1200,
        })

        # Turn 3: human
        collector.on_turn_complete({
            "role": "human",
            "content": "Great, now build the Docker image.",
        })

        # Turn 4: gpt with tool call (failed)
        collector.on_turn_complete({
            "role": "gpt",
            "content": "Building the Docker image now.",
            "tool_calls": [
                {
                    "name": "terminal",
                    "input": "docker build -t app .",
                    "output": "Error: Dockerfile not found",
                    "status": "failure",
                    "latency_ms": 500,
                },
            ],
            "token_count": 30,
            "latency_ms": 900,
        })

        # End session
        collector.on_session_end(session_id="test-session-001")

        # Rate the session
        collector.on_rate(
            rating=3,
            tags=["task_partial", "tool_call_failed"],
            comment="Docker build failed due to missing Dockerfile.",
        )

        # Report a pain point
        collector.on_report(
            category="tool_call_failure",
            description="Docker build attempted before Dockerfile was created.",
            severity="medium",
        )

        # Export the record
        record = collector.export_record()

        # Verify the record structure
        assert record.schema_version == SCHEMA_VERSION
        assert record.record_type == "task_trajectory"
        assert record.trajectory.turn_count == 4
        assert record.trajectory.total_tool_calls == 2
        assert record.trajectory.successful_tool_calls == 1
        assert record.trajectory.failed_tool_calls == 1

        # Verify model metadata
        assert record.model is not None
        assert record.model.model_name == "Hermes-3-Llama-3.1-8B"
        assert record.model.provider == "ollama"

        # Verify outcome
        assert record.outcome is not None
        assert record.outcome.user_rating == 3
        assert "task_partial" in record.outcome.outcome_tags

        # Verify pain points
        assert record.pain_points is not None
        assert len(record.pain_points) == 1
        assert record.pain_points[0].category == "tool_call_failure"

        # Verify IDs were computed
        assert record.record_id is not None
        assert record.record_id.startswith("kajiba_")
        assert record.submission_hash is not None
        assert record.submission_hash.startswith("sha256:")

        # Verify scrub log
        assert record.submission is not None
        assert record.submission.scrub_log is not None

    def test_minimal_session(self) -> None:
        """Minimal session with just 2 turns."""
        collector = KajibaCollector()
        collector.on_session_start("s2", {"model_name": "test-model"})
        collector.on_turn_complete({"role": "human", "content": "Hello"})
        collector.on_turn_complete({"role": "gpt", "content": "Hi there!"})
        collector.on_session_end("s2")

        record = collector.export_record()
        assert record.trajectory.turn_count == 2
        assert record.trajectory.total_tool_calls == 0

    def test_session_without_rating(self) -> None:
        """Session without rating should still export successfully."""
        collector = KajibaCollector()
        collector.on_session_start("s3", {"model_name": "test-model"})
        collector.on_turn_complete({"role": "human", "content": "What is 2+2?"})
        collector.on_turn_complete({"role": "gpt", "content": "2+2 equals 4."})
        collector.on_session_end("s3")

        record = collector.export_record()
        assert record.outcome is None

    def test_multiple_pain_points(self) -> None:
        """Multiple pain points should all be captured."""
        collector = KajibaCollector()
        collector.on_session_start("s4", {"model_name": "test-model"})
        collector.on_turn_complete({"role": "human", "content": "Do something"})
        collector.on_turn_complete({"role": "gpt", "content": "Done."})
        collector.on_session_end("s4")

        collector.on_report("tool_call_failure", "First issue", "high")
        collector.on_report("hallucination_factual", "Second issue", "low")

        record = collector.export_record()
        assert record.pain_points is not None
        assert len(record.pain_points) == 2


class TestHardwareDetection:
    """Test hardware detection."""

    def test_hardware_detection_no_crash(self) -> None:
        """Hardware detection should not crash on any system."""
        hw = _detect_hardware()
        assert hw is not None
        assert hw.os is not None
        assert hw.os in ("linux", "macos", "windows") or isinstance(hw.os, str)

    def test_hardware_profile_fields(self) -> None:
        """Hardware profile should have expected fields."""
        hw = _detect_hardware()
        # These are Optional so they may be None, but the attributes must exist
        assert hasattr(hw, "gpu_name")
        assert hasattr(hw, "gpu_vram_gb")
        assert hasattr(hw, "ram_gb")
        assert hasattr(hw, "cpu_name")
        assert hasattr(hw, "os")


class TestCollectorFaultTolerance:
    """Test that the collector is fault-tolerant."""

    def test_turn_complete_with_bad_data(self) -> None:
        """on_turn_complete should not crash on bad data."""
        collector = KajibaCollector()
        collector.on_session_start("s5", {"model_name": "test"})
        # Missing required 'role' key — should log error, not crash
        collector.on_turn_complete({"content": "missing role"})
        # The collector should still be functional after the error
        collector.on_turn_complete({"role": "human", "content": "Valid turn"})
        collector.on_turn_complete({"role": "gpt", "content": "Valid response"})
        collector.on_session_end("s5")
        record = collector.export_record()
        # Should have 2 valid turns (the bad one was skipped)
        assert record.trajectory.turn_count == 2

    def test_session_id_mismatch_warning(self) -> None:
        """Mismatched session IDs should log a warning, not crash."""
        collector = KajibaCollector()
        collector.on_session_start("session-A", {"model_name": "test"})
        collector.on_turn_complete({"role": "human", "content": "Hello"})
        collector.on_turn_complete({"role": "gpt", "content": "Hi"})
        # End with a different session ID — should warn but not crash
        collector.on_session_end("session-B")


# ---------------------------------------------------------------------------
# Helpers for continuous mode tests
# ---------------------------------------------------------------------------


def _run_full_lifecycle(collector: KajibaCollector, session_id: str = "test-sess") -> None:
    """Run a full collector lifecycle with 2 turns (human + gpt with tool call)."""
    collector.on_session_start(
        session_id=session_id,
        model_config={
            "model_name": "Hermes-3-Llama-3.1-8B",
            "model_family": "llama",
            "quantization": "Q4_K_M",
            "provider": "ollama",
            "is_local": True,
        },
    )
    collector.on_turn_complete({
        "role": "human",
        "content": "Deploy the FastAPI service using Docker.",
    })
    collector.on_turn_complete({
        "role": "gpt",
        "content": "I'll help you deploy. Let me check the project structure first.",
        "tool_calls": [
            {
                "name": "terminal",
                "input": "ls -la /app/",
                "output": "total 32\n-rw-r--r-- main.py",
                "status": "success",
                "latency_ms": 120,
            },
        ],
        "token_count": 45,
        "latency_ms": 1200,
    })
    collector.on_rate(rating=4, tags=["task_completed"])
    collector.on_session_end(session_id=session_id)


class TestContinuousMode:
    """Tests for continuous mode auto-submit in on_session_end."""

    def test_adhoc_mode_saves_to_staging_not_outbox(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ad-hoc mode (default): on_session_end saves record to staging, NOT outbox."""
        import kajiba.collector as collector_mod

        staging = tmp_path / "staging"
        outbox = tmp_path / "outbox"
        monkeypatch.setattr(collector_mod, "STAGING_DIR", staging)
        monkeypatch.setattr(collector_mod, "OUTBOX_DIR", outbox)
        monkeypatch.setattr(
            collector_mod, "_load_config_value",
            lambda key, default: "ad-hoc" if key == "contribution_mode" else default,
        )
        activity_calls: list[tuple] = []
        monkeypatch.setattr(
            collector_mod, "_log_activity",
            lambda action, rid, tier: activity_calls.append((action, rid, tier)),
        )

        collector = KajibaCollector()
        _run_full_lifecycle(collector)

        assert staging.exists()
        staging_files = list(staging.glob("*.json"))
        assert len(staging_files) == 1
        assert not outbox.exists() or len(list(outbox.glob("*"))) == 0

    def test_continuous_mode_gold_record_goes_to_outbox(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Continuous mode with qualifying record: auto-submits to outbox."""
        import kajiba.collector as collector_mod

        staging = tmp_path / "staging"
        outbox = tmp_path / "outbox"
        monkeypatch.setattr(collector_mod, "STAGING_DIR", staging)
        monkeypatch.setattr(collector_mod, "OUTBOX_DIR", outbox)

        def mock_config(key: str, default: str) -> str:
            if key == "contribution_mode":
                return "continuous"
            if key == "min_quality_tier":
                return "silver"
            return default

        monkeypatch.setattr(collector_mod, "_load_config_value", mock_config)
        activity_calls: list[tuple] = []
        monkeypatch.setattr(
            collector_mod, "_log_activity",
            lambda action, rid, tier: activity_calls.append((action, rid, tier)),
        )

        collector = KajibaCollector()
        _run_full_lifecycle(collector)

        # Outbox should have a record
        assert outbox.exists()
        outbox_files = list(outbox.glob("*"))
        assert len(outbox_files) == 1
        # Staging should be empty (or not exist)
        assert not staging.exists() or len(list(staging.glob("*"))) == 0

    def test_continuous_mode_below_threshold_goes_to_staging(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Continuous mode with below-threshold record: saves to staging."""
        import kajiba.collector as collector_mod

        staging = tmp_path / "staging"
        outbox = tmp_path / "outbox"
        monkeypatch.setattr(collector_mod, "STAGING_DIR", staging)
        monkeypatch.setattr(collector_mod, "OUTBOX_DIR", outbox)

        def mock_config(key: str, default: str) -> str:
            if key == "contribution_mode":
                return "continuous"
            if key == "min_quality_tier":
                return "gold"  # Set threshold to gold
            return default

        monkeypatch.setattr(collector_mod, "_load_config_value", mock_config)

        # Force a low quality score by mocking compute_quality_score
        from kajiba.scorer import QualityResult

        monkeypatch.setattr(
            collector_mod, "compute_quality_score",
            lambda record: QualityResult(
                composite_score=0.3,
                sub_scores={"coherence": 0.3, "tool_validity": 0.3, "outcome_quality": 0.3,
                            "information_density": 0.3, "metadata_completeness": 0.3},
                quality_tier="review_needed",
            ),
        )
        activity_calls: list[tuple] = []
        monkeypatch.setattr(
            collector_mod, "_log_activity",
            lambda action, rid, tier: activity_calls.append((action, rid, tier)),
        )

        collector = KajibaCollector()
        _run_full_lifecycle(collector)

        # Staging should have the record
        assert staging.exists()
        staging_files = list(staging.glob("*.json"))
        assert len(staging_files) == 1
        # Outbox should be empty
        assert not outbox.exists() or len(list(outbox.glob("*"))) == 0

    def test_continuous_mode_auto_submit_applies_full_pipeline(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Auto-submitted records have record_id, submission_hash, scrub_log, quality."""
        import kajiba.collector as collector_mod

        staging = tmp_path / "staging"
        outbox = tmp_path / "outbox"
        monkeypatch.setattr(collector_mod, "STAGING_DIR", staging)
        monkeypatch.setattr(collector_mod, "OUTBOX_DIR", outbox)

        def mock_config(key: str, default: str) -> str:
            if key == "contribution_mode":
                return "continuous"
            if key == "min_quality_tier":
                return "bronze"
            return default

        monkeypatch.setattr(collector_mod, "_load_config_value", mock_config)
        monkeypatch.setattr(
            collector_mod, "_log_activity", lambda action, rid, tier: None,
        )

        collector = KajibaCollector()
        _run_full_lifecycle(collector)

        outbox_files = list(outbox.glob("*"))
        assert len(outbox_files) == 1
        data = json.loads(outbox_files[0].read_text(encoding="utf-8"))

        assert data.get("record_id") is not None
        assert data["record_id"].startswith("kajiba_")
        assert data.get("submission_hash") is not None
        assert data["submission_hash"].startswith("sha256:")
        assert data.get("quality") is not None
        assert "quality_tier" in data["quality"]
        assert "composite_score" in data["quality"]
        assert data.get("submission") is not None
        assert data["submission"].get("scrub_log") is not None

    def test_continuous_mode_logs_auto_submitted_activity(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Continuous mode logs 'auto_submitted' when record meets threshold."""
        import kajiba.collector as collector_mod

        staging = tmp_path / "staging"
        outbox = tmp_path / "outbox"
        monkeypatch.setattr(collector_mod, "STAGING_DIR", staging)
        monkeypatch.setattr(collector_mod, "OUTBOX_DIR", outbox)

        def mock_config(key: str, default: str) -> str:
            if key == "contribution_mode":
                return "continuous"
            if key == "min_quality_tier":
                return "bronze"
            return default

        monkeypatch.setattr(collector_mod, "_load_config_value", mock_config)
        activity_calls: list[tuple] = []
        monkeypatch.setattr(
            collector_mod, "_log_activity",
            lambda action, rid, tier: activity_calls.append((action, rid, tier)),
        )

        collector = KajibaCollector()
        _run_full_lifecycle(collector)

        assert len(activity_calls) == 1
        assert activity_calls[0][0] == "auto_submitted"

    def test_continuous_mode_logs_queued_for_review_activity(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Continuous mode logs 'queued_for_review' when below threshold."""
        import kajiba.collector as collector_mod

        staging = tmp_path / "staging"
        outbox = tmp_path / "outbox"
        monkeypatch.setattr(collector_mod, "STAGING_DIR", staging)
        monkeypatch.setattr(collector_mod, "OUTBOX_DIR", outbox)

        def mock_config(key: str, default: str) -> str:
            if key == "contribution_mode":
                return "continuous"
            if key == "min_quality_tier":
                return "gold"
            return default

        monkeypatch.setattr(collector_mod, "_load_config_value", mock_config)

        from kajiba.scorer import QualityResult

        monkeypatch.setattr(
            collector_mod, "compute_quality_score",
            lambda record: QualityResult(
                composite_score=0.3,
                sub_scores={"coherence": 0.3, "tool_validity": 0.3, "outcome_quality": 0.3,
                            "information_density": 0.3, "metadata_completeness": 0.3},
                quality_tier="review_needed",
            ),
        )
        activity_calls: list[tuple] = []
        monkeypatch.setattr(
            collector_mod, "_log_activity",
            lambda action, rid, tier: activity_calls.append((action, rid, tier)),
        )

        collector = KajibaCollector()
        _run_full_lifecycle(collector)

        assert len(activity_calls) == 1
        assert activity_calls[0][0] == "queued_for_review"

    def test_continuous_mode_bronze_threshold_accepts_bronze(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With min_quality_tier=bronze, a bronze record is auto-submitted."""
        import kajiba.collector as collector_mod

        staging = tmp_path / "staging"
        outbox = tmp_path / "outbox"
        monkeypatch.setattr(collector_mod, "STAGING_DIR", staging)
        monkeypatch.setattr(collector_mod, "OUTBOX_DIR", outbox)

        def mock_config(key: str, default: str) -> str:
            if key == "contribution_mode":
                return "continuous"
            if key == "min_quality_tier":
                return "bronze"
            return default

        monkeypatch.setattr(collector_mod, "_load_config_value", mock_config)

        from kajiba.scorer import QualityResult

        monkeypatch.setattr(
            collector_mod, "compute_quality_score",
            lambda record: QualityResult(
                composite_score=0.5,
                sub_scores={"coherence": 0.5, "tool_validity": 0.5, "outcome_quality": 0.5,
                            "information_density": 0.5, "metadata_completeness": 0.5},
                quality_tier="bronze",
            ),
        )
        activity_calls: list[tuple] = []
        monkeypatch.setattr(
            collector_mod, "_log_activity",
            lambda action, rid, tier: activity_calls.append((action, rid, tier)),
        )

        collector = KajibaCollector()
        _run_full_lifecycle(collector)

        assert outbox.exists()
        assert len(list(outbox.glob("*"))) == 1
        assert activity_calls[0][0] == "auto_submitted"

    def test_fault_tolerance_scrub_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If scrub_record raises, on_session_end catches it and does not crash."""
        import kajiba.collector as collector_mod

        staging = tmp_path / "staging"
        outbox = tmp_path / "outbox"
        monkeypatch.setattr(collector_mod, "STAGING_DIR", staging)
        monkeypatch.setattr(collector_mod, "OUTBOX_DIR", outbox)

        def mock_config(key: str, default: str) -> str:
            if key == "contribution_mode":
                return "continuous"
            return default

        monkeypatch.setattr(collector_mod, "_load_config_value", mock_config)
        monkeypatch.setattr(
            collector_mod, "_log_activity", lambda action, rid, tier: None,
        )

        def exploding_scrub(record):
            raise RuntimeError("Scrub exploded!")

        monkeypatch.setattr(collector_mod, "scrub_record", exploding_scrub)

        collector = KajibaCollector()
        # This should NOT raise
        _run_full_lifecycle(collector)

    def test_fault_tolerance_save_to_staging_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If _save_to_staging raises (e.g., disk full), on_session_end catches it."""
        import kajiba.collector as collector_mod

        monkeypatch.setattr(
            collector_mod, "_load_config_value",
            lambda key, default: "ad-hoc" if key == "contribution_mode" else default,
        )
        monkeypatch.setattr(
            collector_mod, "_log_activity", lambda action, rid, tier: None,
        )
        # Monkeypatch STAGING_DIR to a non-writable path
        monkeypatch.setattr(collector_mod, "STAGING_DIR", Path("/nonexistent/readonly/path"))

        collector = KajibaCollector()
        # This should NOT raise
        _run_full_lifecycle(collector)


class TestSaveToStaging:
    """Tests for the _save_to_staging helper method."""

    def test_save_to_staging_creates_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_save_to_staging writes a valid JSON file to the staging directory."""
        import kajiba.collector as collector_mod

        staging = tmp_path / "staging"
        monkeypatch.setattr(collector_mod, "STAGING_DIR", staging)

        collector = KajibaCollector()
        collector.on_session_start("stg-001", {"model_name": "test-model"})
        collector.on_turn_complete({"role": "human", "content": "Hello"})
        collector.on_turn_complete({"role": "gpt", "content": "Hi there!"})

        collector._save_to_staging()

        assert staging.exists()
        files = list(staging.glob("*.json"))
        assert len(files) == 1
        assert "stg-001" in files[0].name

        data = json.loads(files[0].read_text(encoding="utf-8"))
        assert data["trajectory"]["turn_count"] == 2

    def test_save_to_staging_round_trip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Staging file can be loaded back via validate_record (round-trip)."""
        import kajiba.collector as collector_mod

        staging = tmp_path / "staging"
        monkeypatch.setattr(collector_mod, "STAGING_DIR", staging)

        collector = KajibaCollector()
        collector.on_session_start("stg-002", {"model_name": "test-model"})
        collector.on_turn_complete({"role": "human", "content": "What is 2+2?"})
        collector.on_turn_complete({"role": "gpt", "content": "4."})

        collector._save_to_staging()

        files = list(staging.glob("*.json"))
        data = json.loads(files[0].read_text(encoding="utf-8"))
        record = validate_record(data)
        assert record.trajectory.turn_count == 2
        assert record.schema_version == SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Phase 7 RED capture scaffolds (CAPT-02/03/04)
#
# These tests pin the not-yet-built paired-turn / tool-buffer / turn-scoped
# session-end / ollama-metadata / remote-degrade capture surface ahead of the
# 07-03 implementation. They reference collector methods and behaviors that do
# NOT yet exist, so they fail at collection or assertion (RED). The kwarg names
# below are the live-verified Hermes v0.15.x payload contract from
# 06-HOOK-KWARGS.md. The four CRITICAL CORRECTIONS are encoded as executable
# assertions:
#   - Correction 2: tool status "ok" -> "success"
#   - Correction 3: turn-scoped on_session_end writes EXACTLY ONE staging file
#   - Correction 4: a populated conversation_history must NOT double-count turns
# Selectors (07-VALIDATION map): llm_turn, tool_buffer, session_end_once,
# ollama_metadata, remote_degrade.
# ---------------------------------------------------------------------------


# Live-verified turn_id format: "<session>:<task>:<8hex>" (06-HOOK-KWARGS Hook 2)
_TURN_ID = "sess-7:sess-7:0cd552b7"


def _start_llm_session(
    collector: KajibaCollector, session_id: str = "sess-7", model: str = "test-model",
) -> None:
    """Start a session the way the promoted post_llm_call path will."""
    collector.on_session_start(session_id=session_id, model_name=model, platform="cli")


class TestPairedTurnCapture:
    """CAPT-02: one post_llm_call -> exactly one human turn + one gpt turn."""

    def test_llm_turn_appends_paired_human_and_gpt(self) -> None:
        """One on_llm_turn call appends exactly one human then one gpt turn."""
        collector = KajibaCollector()
        _start_llm_session(collector)

        # The new paired-turn entry point (does NOT exist yet -> RED).
        collector.on_llm_turn(
            user_message="Deploy the FastAPI service using Docker.",
            assistant_response="I'll help you deploy. Let me check the project.",
            turn_id=_TURN_ID,
        )

        turns = collector._conversations
        assert len(turns) == 2
        assert turns[0].from_ == "human"
        assert turns[0].value == "Deploy the FastAPI service using Docker."
        assert turns[1].from_ == "gpt"
        assert turns[1].value == "I'll help you deploy. Let me check the project."

    def test_llm_turn_history_does_not_double_count(self) -> None:
        """A populated conversation_history must NOT add extra turns (Correction 4)."""
        collector = KajibaCollector()
        _start_llm_session(collector)

        history = [
            {"role": "human", "content": "earlier prompt"},
            {"role": "gpt", "content": "earlier reply"},
        ]
        # Even with prior history supplied, exactly one human+gpt pair is appended.
        collector.on_llm_turn(
            user_message="new prompt",
            assistant_response="new reply",
            turn_id=_TURN_ID,
            conversation_history=history,
        )

        assert len(collector._conversations) == 2


class TestToolBufferCapture:
    """CAPT-03: tool events buffered by turn_id, status ok->success, dedup, parse."""

    def test_tool_buffer_status_ok_maps_to_success(self) -> None:
        """status='ok' produces a ToolCall with tool_status == 'success' (Correction 2)."""
        collector = KajibaCollector()
        _start_llm_session(collector)

        collector.on_tool_call(
            tool_name="read_file",
            args={"path": "/app/main.py"},
            result='{"content": "print(1)"}',
            tool_call_id="call_abc123",
            turn_id=_TURN_ID,
            status="ok",
        )
        collector.on_llm_turn(
            user_message="read the file",
            assistant_response="done",
            turn_id=_TURN_ID,
        )

        gpt_turn = collector._conversations[1]
        assert gpt_turn.from_ == "gpt"
        assert gpt_turn.tool_calls is not None
        assert len(gpt_turn.tool_calls) == 1
        assert gpt_turn.tool_calls[0].tool_status == "success"

    def test_tool_buffer_dedups_on_tool_call_id(self) -> None:
        """A duplicate tool_call_id is deduped to a single ToolCall."""
        collector = KajibaCollector()
        _start_llm_session(collector)

        for _ in range(2):
            collector.on_tool_call(
                tool_name="read_file",
                args={"path": "/app/main.py"},
                result='{"content": "x"}',
                tool_call_id="call_dup",
                turn_id=_TURN_ID,
                status="ok",
            )
        collector.on_llm_turn(
            user_message="q",
            assistant_response="a",
            turn_id=_TURN_ID,
        )

        gpt_turn = collector._conversations[1]
        assert gpt_turn.tool_calls is not None
        assert len(gpt_turn.tool_calls) == 1

    def test_tool_buffer_parses_result_and_serializes_args(self) -> None:
        """result (JSON str) is parsed; args (dict) is serialized into tool_input."""
        collector = KajibaCollector()
        _start_llm_session(collector)

        collector.on_tool_call(
            tool_name="read_file",
            args={"path": "/app/main.py"},
            result='{"content": "hello world"}',
            tool_call_id="call_parse",
            turn_id=_TURN_ID,
            status="ok",
        )
        collector.on_llm_turn(
            user_message="q",
            assistant_response="a",
            turn_id=_TURN_ID,
        )

        tc = collector._conversations[1].tool_calls[0]
        # args dict serialized into tool_input (round-trips back to the dict).
        assert json.loads(tc.tool_input) == {"path": "/app/main.py"}
        # result JSON string parsed before storage (the inner content survives).
        assert "hello world" in tc.tool_output


class TestSessionEndOnce:
    """CAPT-03: turn-scoped on_session_end writes EXACTLY ONE staging file."""

    def test_session_end_once_writes_single_staging_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """N on_session_end firings -> exactly ONE staging file (Correction 3)."""
        import kajiba.collector as collector_mod

        staging = tmp_path / "staging"
        monkeypatch.setattr(collector_mod, "STAGING_DIR", staging)
        monkeypatch.setattr(
            collector_mod, "_load_config_value",
            lambda key, default: "ad-hoc" if key == "contribution_mode" else default,
        )

        collector = KajibaCollector()
        _start_llm_session(collector)
        collector.on_llm_turn(
            user_message="first", assistant_response="r1", turn_id=_TURN_ID,
        )

        # Hermes fires on_session_end after EACH run_conversation turn (finding 2).
        collector.on_session_end(session_id="sess-7")
        collector.on_llm_turn(
            user_message="second", assistant_response="r2", turn_id=_TURN_ID,
        )
        collector.on_session_end(session_id="sess-7")
        collector.on_session_end(session_id="sess-7")

        files = list(staging.glob("*.json"))
        # EXACTLY ONE file per session, not one-per-end-event.
        assert len(files) == 1

    def test_session_end_once_reflects_full_trajectory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The single staging file reflects the full accumulated trajectory (no reset)."""
        import kajiba.collector as collector_mod

        staging = tmp_path / "staging"
        monkeypatch.setattr(collector_mod, "STAGING_DIR", staging)
        monkeypatch.setattr(
            collector_mod, "_load_config_value",
            lambda key, default: "ad-hoc" if key == "contribution_mode" else default,
        )

        collector = KajibaCollector()
        _start_llm_session(collector)
        collector.on_llm_turn(
            user_message="first", assistant_response="r1", turn_id=_TURN_ID,
        )
        collector.on_session_end(session_id="sess-7")
        collector.on_llm_turn(
            user_message="second", assistant_response="r2", turn_id=_TURN_ID,
        )
        collector.on_session_end(session_id="sess-7")

        files = list(staging.glob("*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text(encoding="utf-8"))
        # turn_count GREW to 4 (2 paired turns); it did not reset to the last turn.
        assert data["trajectory"]["turn_count"] == 4


class TestOllamaMetadata:
    """CAPT-04: ollama.show() mapped into ModelMetadata (mocked)."""

    def test_ollama_metadata_populates_model_fields(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With ollama.show() mocked, captured ModelMetadata carries non-null fields."""
        import sys
        import types

        fake_ollama = types.ModuleType("ollama")

        def _show(model_name: str) -> dict:
            return {
                "details": {
                    "parameter_size": "8.0B",
                    "quantization_level": "Q4_0",
                    "family": "llama",
                },
                "model_info": {"llama.context_length": 8192},
                "digest": "sha256:abc123",
            }

        fake_ollama.show = _show
        monkeypatch.setitem(sys.modules, "ollama", fake_ollama)

        collector = KajibaCollector()
        # New ollama-enrichment entry point (does NOT exist yet -> RED).
        collector.on_session_start(
            session_id="sess-ollama",
            model_name="hermes3:8b",
            platform="cli",
            provider="ollama",
        )

        meta = collector._model_metadata
        assert meta is not None
        assert meta.parameter_count == "8.0B"
        assert meta.quantization == "Q4_0"
        assert meta.model_family == "llama"
        assert meta.context_window == 8192
        assert meta.model_hash is not None


class TestRemoteDegrade:
    """CAPT-04: remote backend with no ollama -> slug inference, params None (D-03)."""

    def test_remote_degrade_leaves_params_none_no_raise(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A remote model with ollama absent yields is_local False and None params."""
        import sys

        # Simulate ollama being unavailable / raising.
        monkeypatch.setitem(sys.modules, "ollama", None)

        collector = KajibaCollector()
        # Remote slug (e.g. an Anthropic/openrouter model) -> no exception.
        collector.on_session_start(
            session_id="sess-remote",
            model_name="anthropic/claude-opus-4-8",
            platform="cli",
        )

        meta = collector._model_metadata
        assert meta is not None
        assert meta.is_local is False
        # Slug-inferred provider/model_family present...
        assert meta.provider is not None
        assert meta.model_family is not None
        # ...but param/quant/hash left None (remote degradation, D-03).
        assert meta.parameter_count is None
        assert meta.quantization is None
        assert meta.model_hash is None
        # Hardware inference_backend recorded (D-03).
        assert collector._hardware is not None
        assert collector._hardware.inference_backend is not None
