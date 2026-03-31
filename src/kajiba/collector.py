"""Session capture engine for Kajiba.

Implements the session lifecycle collector from Section 5 of the spec.
Hooks into Hermes Agent's session lifecycle to capture telemetry
non-intrusively.
"""

import logging
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from kajiba.schema import (
    SCHEMA_VERSION,
    ConversationTurn,
    HardwareProfile,
    KajibaRecord,
    ModelMetadata,
    OutcomeSignals,
    PainPoint,
    PainPointCategoryType,
    SeverityType,
    SubmissionMetadata,
    ToolCall,
    Trajectory,
)
from kajiba.privacy import anonymize_hardware, apply_consent_level, jitter_timestamp
from kajiba.scorer import compute_quality_score
from kajiba.scrubber import scrub_record

logger = logging.getLogger(__name__)


def _detect_hardware() -> HardwareProfile:
    """Detect the current hardware profile.

    Detects OS, GPU (via nvidia-smi), and RAM. Gracefully handles
    absence of GPU or detection failures.

    Returns:
        HardwareProfile with whatever information could be gathered.
    """
    os_name = platform.system().lower()
    if os_name == "darwin":
        os_label = "macos"
    elif os_name == "linux":
        os_label = "linux"
    elif os_name == "windows":
        os_label = "windows"
    else:
        os_label = os_name

    gpu_name: Optional[str] = None
    gpu_vram_gb: Optional[int] = None
    gpu_count: Optional[int] = None
    cuda_version: Optional[str] = None

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            gpu_count = len(lines)
            first_gpu = lines[0].split(",")
            if len(first_gpu) >= 1:
                gpu_name = first_gpu[0].strip()
            if len(first_gpu) >= 2:
                try:
                    vram_mb = float(first_gpu[1].strip())
                    gpu_vram_gb = round(vram_mb / 1024)
                except (ValueError, IndexError):
                    pass

        cuda_result = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if cuda_result.returncode == 0 and cuda_result.stdout.strip():
            cuda_version = cuda_result.stdout.strip().split("\n")[0].strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        logger.debug("nvidia-smi not available; skipping GPU detection")

    ram_gb: Optional[int] = None
    try:
        import psutil
        ram_gb = round(psutil.virtual_memory().total / (1024 ** 3))
    except ImportError:
        if os_label == "linux":
            try:
                meminfo = Path("/proc/meminfo").read_text()
                for line in meminfo.split("\n"):
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        ram_gb = round(kb / (1024 * 1024))
                        break
            except (OSError, ValueError):
                pass

    cpu_name: Optional[str] = None
    try:
        cpu_name = platform.processor() or None
    except Exception:
        pass

    return HardwareProfile(
        gpu_name=gpu_name,
        gpu_vram_gb=gpu_vram_gb,
        gpu_count=gpu_count,
        cpu_name=cpu_name,
        ram_gb=ram_gb,
        os=os_label,
        cuda_version=cuda_version,
    )


def _extract_model_metadata(model_config: dict) -> ModelMetadata:
    """Extract model metadata from a Hermes Agent model config dict.

    Args:
        model_config: Dictionary from Hermes Agent's model configuration.

    Returns:
        ModelMetadata populated from the config.
    """
    return ModelMetadata(
        model_name=model_config.get("model_name", "unknown"),
        model_family=model_config.get("model_family"),
        parameter_count=model_config.get("parameter_count"),
        quantization=model_config.get("quantization"),
        context_window=model_config.get("context_window"),
        provider=model_config.get("provider"),
        is_local=model_config.get("is_local"),
        model_hash=model_config.get("model_hash"),
    )


class KajibaCollector:
    """Session lifecycle collector for Kajiba.

    Hooks into Hermes Agent's session lifecycle to capture telemetry.
    Non-intrusive: if Kajiba fails, the agent session continues normally.
    All errors are logged but never raised to the caller.

    Usage:
        collector = KajibaCollector()
        collector.on_session_start(session_id="abc", model_config={...})
        collector.on_turn_complete(turn={...})
        collector.on_session_end(session_id="abc")
        record = collector.export_record()
    """

    def __init__(self) -> None:
        self.current_record: Optional[dict] = None
        self._session_id: Optional[str] = None
        self._conversations: list[ConversationTurn] = []
        self._pain_points: list[PainPoint] = []
        self._outcome: Optional[OutcomeSignals] = None
        self._model_metadata: Optional[ModelMetadata] = None
        self._hardware: Optional[HardwareProfile] = None
        self._created_at: Optional[datetime] = None

    def on_session_start(self, session_id: str, model_config: dict) -> None:
        """Capture model metadata and hardware at session start.

        Args:
            session_id: Unique identifier for the session.
            model_config: Dictionary from Hermes Agent's model configuration.
        """
        try:
            self._session_id = session_id
            self._conversations = []
            self._pain_points = []
            self._outcome = None
            self._created_at = datetime.now(UTC)
            self._model_metadata = _extract_model_metadata(model_config)
            self._hardware = _detect_hardware()
            logger.info("Kajiba collector started for session %s", session_id)
        except Exception:
            logger.exception("Error in on_session_start")

    def on_turn_complete(self, turn: dict) -> None:
        """Capture a completed turn with tool call metadata.

        Args:
            turn: Dictionary with keys: role ("human"/"gpt"), content (str),
                  and optionally tool_calls (list), token_count (int),
                  latency_ms (int).
        """
        try:
            tool_calls = None
            if turn.get("tool_calls"):
                tool_calls = [
                    ToolCall(
                        tool_name=tc["name"],
                        tool_input=tc.get("input", "")[:2000],
                        tool_output=tc.get("output", "")[:2000],
                        tool_status=tc.get("status", "success"),
                        latency_ms=tc.get("latency_ms"),
                    )
                    for tc in turn["tool_calls"]
                ]

            conversation_turn = ConversationTurn(
                **{"from": turn["role"]},
                value=turn["content"],
                tool_calls=tool_calls,
                token_count=turn.get("token_count"),
                generation_latency_ms=turn.get("latency_ms"),
            )
            self._conversations.append(conversation_turn)
        except Exception:
            logger.exception("Error in on_turn_complete")

    def on_session_end(self, session_id: str) -> None:
        """Finalize record and compute trajectory stats.

        Args:
            session_id: The session identifier (for validation).
        """
        try:
            if self._session_id != session_id:
                logger.warning(
                    "Session ID mismatch: expected %s, got %s",
                    self._session_id, session_id,
                )
            logger.info(
                "Kajiba collector ended for session %s (%d turns)",
                session_id, len(self._conversations),
            )
        except Exception:
            logger.exception("Error in on_session_end")

    def on_rate(self, rating: int, tags: list[str], comment: str = "") -> None:
        """Handle /rate command.

        Args:
            rating: User rating 1-5.
            tags: List of outcome tags from controlled vocabulary.
            comment: Optional free-text comment.
        """
        try:
            self._outcome = OutcomeSignals(
                user_rating=rating,
                outcome_tags=tags,
                user_comment=comment or None,
            )
        except Exception:
            logger.exception("Error in on_rate")

    def on_report(
        self,
        category: PainPointCategoryType,
        description: str,
        severity: SeverityType = "medium",
    ) -> None:
        """Handle /report command.

        Args:
            category: Pain point category from controlled vocabulary.
            description: Free-text description of the pain point.
            severity: Severity level (low/medium/high/critical).
        """
        try:
            turn_index = len(self._conversations) - 1 if self._conversations else 0
            self._pain_points.append(PainPoint(
                category=category,
                severity=severity,
                description=description,
                turn_index=turn_index,
            ))
        except Exception:
            logger.exception("Error in on_report")

    def _build_record(self) -> KajibaRecord:
        """Build a KajibaRecord from collected data.

        Returns:
            The assembled KajibaRecord (not yet scrubbed or scored).
        """
        all_tool_calls = [
            tc
            for turn in self._conversations
            if turn.tool_calls
            for tc in turn.tool_calls
        ]
        turn_count = len(self._conversations)
        total_tool_calls = len(all_tool_calls)
        successful_tool_calls = sum(
            1 for tc in all_tool_calls if tc.tool_status == "success"
        )
        failed_tool_calls = total_tool_calls - successful_tool_calls

        trajectory = Trajectory(
            format="sharegpt_extended",
            conversations=self._conversations,
            turn_count=turn_count,
            total_tool_calls=total_tool_calls,
            successful_tool_calls=successful_tool_calls,
            failed_tool_calls=failed_tool_calls,
        )

        return KajibaRecord(
            schema_version=SCHEMA_VERSION,
            record_type="task_trajectory",
            created_at=self._created_at or datetime.now(UTC),
            trajectory=trajectory,
            model=self._model_metadata,
            hardware=self._hardware,
            outcome=self._outcome,
            pain_points=self._pain_points if self._pain_points else None,
            submission=SubmissionMetadata(),
        )

    def export_record(self) -> KajibaRecord:
        """Export the collected session data as a privacy-processed KajibaRecord.

        Applies the full privacy pipeline: scrub -> anonymize -> jitter ->
        consent strip, then computes deterministic IDs.

        Returns:
            The finalized KajibaRecord ready for submission.
        """
        try:
            record = self._build_record()

            # Step 1: PII scrub (must be first — scrubs all fields before any are stripped)
            scrubbed, scrub_log = scrub_record(record)

            # Step 2: Hardware anonymization (after scrub, before consent strip)
            anonymized = anonymize_hardware(scrubbed)

            # Step 3: Timestamp jitter
            jittered = jitter_timestamp(anonymized)

            # Step 4: Consent enforcement (last — strips already-clean data)
            consent_level = "full"
            if record.submission and record.submission.consent_level:
                consent_level = record.submission.consent_level
            final = apply_consent_level(jittered, consent_level)

            # Attach scrub log
            if final.submission is None:
                final.submission = SubmissionMetadata()
            final.submission.scrub_log = scrub_log

            # Compute IDs
            final.compute_record_id()
            final.compute_submission_hash()

            return final
        except Exception:
            logger.exception("Failed to export record")
            raise
