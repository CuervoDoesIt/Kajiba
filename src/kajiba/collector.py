"""Session capture engine for Kajiba.

Implements the session lifecycle collector from Section 5 of the spec.
Hooks into Hermes Agent's session lifecycle to capture telemetry
non-intrusively.
"""

import json
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
    QualityMetadata,
    SeverityType,
    SubmissionMetadata,
    ToolCall,
    Trajectory,
)
from kajiba.config import (
    _load_config_value,
    _log_activity,
    get_hermes_home,
    tier_meets_threshold,
)
from kajiba.privacy import anonymize_hardware, apply_consent_level, jitter_timestamp
from kajiba.scorer import compute_quality_score
from kajiba.scrubber import scrub_record

logger = logging.getLogger(__name__)

KAJIBA_BASE = get_hermes_home() / "kajiba"
STAGING_DIR = KAJIBA_BASE / "staging"
OUTBOX_DIR = KAJIBA_BASE / "outbox"


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


# Telemetry schema version carried by Hermes v0.15.x hook payloads. Recorded for
# forward-compat; ModelMetadata has no dedicated field, so it is folded into the
# free-text ``inference_backend`` is NOT used for it — see note in
# _build_metadata_and_hardware where it is appended to model_name provenance.
TELEMETRY_SCHEMA_VERSION = "hermes.observer.v1"

# Providers recognized by the schema literal (ProviderType). Anything else (e.g.
# a remote Anthropic backend) maps to "custom" while the real backend name is
# preserved verbatim in HardwareProfile.inference_backend (Correction 5).
_KNOWN_PROVIDERS = ("ollama", "vllm", "sglang", "llamacpp", "openrouter", "custom")


def _enrich_from_ollama(model_name: str) -> dict:
    """Enrich model metadata from a local ``ollama.show()`` call.

    Soft-imports ``ollama`` (mirroring the ``psutil`` block in
    ``_detect_hardware``) so the core package stays import-clean offline. Wraps
    the ``ollama.show()`` service call in its own ``try/except`` so a missing or
    unreachable Ollama server never raises (D-01). Handles both dict-like and
    object-like responses (Assumption A1).

    Args:
        model_name: The model slug to look up (e.g. ``"hermes3:8b"``).

    Returns:
        A dict with ``parameter_count``/``quantization``/``model_family``/
        ``context_window``/``model_hash`` keys, or an empty dict when Ollama is
        absent, unreachable, or returns no usable fields.
    """
    try:
        import ollama
    except ImportError:
        return {}
    try:
        resp = ollama.show(model_name)
    except Exception:
        logger.debug("ollama.show(%s) failed; degrading to slug inference", model_name)
        return {}

    details = resp.get("details", {}) if isinstance(resp, dict) else getattr(resp, "details", {})
    details = details or {}
    info = resp.get("model_info", {}) if isinstance(resp, dict) else getattr(resp, "modelinfo", {})
    info = info or {}
    context_window = next(
        (v for k, v in info.items() if str(k).endswith(".context_length")), None
    )
    digest = resp.get("digest") if isinstance(resp, dict) else getattr(resp, "digest", None)

    def _get(obj: object, key: str) -> Optional[str]:
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    return {
        "parameter_count": _get(details, "parameter_size"),
        "quantization": _get(details, "quantization_level"),
        "model_family": _get(details, "family"),
        "context_window": context_window,
        "model_hash": digest,
    }


def _infer_provider_and_family(model_name: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Light slug inference for a remote model (no fabrication, D-03).

    Parses a ``provider/model`` slug into a schema-valid ``provider`` literal,
    a ``model_family``, and the real backend name for
    ``HardwareProfile.inference_backend``. A backend not present in the schema
    literal (e.g. ``anthropic``) maps ``provider="custom"`` while the real
    backend is preserved in ``inference_backend`` (Correction 5; no schema
    change).

    Args:
        model_name: The model slug (e.g. ``"anthropic/claude-opus-4-8"``).

    Returns:
        ``(provider, model_family, inference_backend)`` — any element may be
        None when it cannot be inferred.
    """
    if not model_name:
        return None, None, None
    if "/" in model_name:
        prefix, _, rest = model_name.partition("/")
        backend = prefix.lower()
        provider = backend if backend in _KNOWN_PROVIDERS else "custom"
        # model_family: leading alphabetic stem of the model portion.
        stem = rest.split(":")[0].split("-")[0] or rest
        return provider, stem or None, backend
    # Bare name with no provider prefix — family is the leading stem.
    stem = model_name.split(":")[0].split("-")[0] or model_name
    return None, stem or None, None


def _build_metadata_and_hardware(
    model_config: dict,
) -> tuple[ModelMetadata, HardwareProfile]:
    """Assemble ModelMetadata + HardwareProfile, enriching per backend (CAPT-04).

    Always sets ``model_name``/``provider``/``platform``/``is_local`` from the
    config (D-01). Detects a local Ollama session (explicit ``provider="ollama"``
    or a bare slug with no provider prefix) and enriches via ``ollama.show()``;
    otherwise degrades to light slug inference and records the real backend in
    ``HardwareProfile.inference_backend`` (D-03). Never raises.

    Args:
        model_config: Flat dict with at least ``model_name`` and optionally
            ``provider``/``platform``.

    Returns:
        A ``(ModelMetadata, HardwareProfile)`` pair.
    """
    hardware = _detect_hardware()
    model_name = model_config.get("model_name") or "unknown"
    provider = model_config.get("provider")
    has_provider_prefix = "/" in model_name

    # Detect local Ollama: explicit provider, or a bare slug (no provider prefix).
    is_ollama_local = provider == "ollama" or (
        provider is None and not has_provider_prefix and model_name != "unknown"
    )

    if is_ollama_local:
        enriched = _enrich_from_ollama(model_name)
        metadata = ModelMetadata(
            model_name=model_name,
            model_family=enriched.get("model_family"),
            parameter_count=enriched.get("parameter_count"),
            quantization=enriched.get("quantization"),
            context_window=enriched.get("context_window"),
            provider="ollama",
            is_local=True,
            model_hash=enriched.get("model_hash"),
        )
        hardware.inference_backend = "ollama"
        return metadata, hardware

    # Remote backend: slug inference only, params left None (D-03).
    inferred_provider, model_family, backend = _infer_provider_and_family(model_name)
    final_provider = provider if provider in _KNOWN_PROVIDERS else inferred_provider
    metadata = ModelMetadata(
        model_name=model_name,
        model_family=model_family,
        parameter_count=None,
        quantization=None,
        context_window=None,
        provider=final_provider,
        is_local=False,
        model_hash=None,
    )
    hardware.inference_backend = backend or provider or model_config.get("platform")
    return metadata, hardware


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
        # Tool events arrive keyed by turn_id and may precede or follow the
        # paired-turn event they belong to; buffer them until the gpt turn for
        # that turn_id exists (CAPT-03). Maps turn_id -> list[ToolCall].
        self._pending_tools: dict[str, list[ToolCall]] = {}
        # Maps turn_id -> index of its gpt ConversationTurn in _conversations,
        # so late-arriving tools can attach to the already-appended turn.
        self._gpt_turn_index: dict[str, int] = {}
        self._last_gpt_turn_id: Optional[str] = None
        # Dedup guard for tool events keyed by tool_call_id.
        self._seen_tool_call_ids: set[str] = set()
        # Once-flag guarding continuous-mode auto-submit against per-turn
        # on_session_end firings (Correction 3).
        self._finalized: bool = False

    def on_session_start(
        self,
        session_id: str,
        model_config: Optional[dict] = None,
        *,
        model_name: Optional[str] = None,
        platform: Optional[str] = None,
        provider: Optional[str] = None,
        **_: object,
    ) -> None:
        """Capture model metadata and hardware at session start.

        Backwards-compatible with the legacy positional-dict call
        (``on_session_start(session_id, model_config)``) while also accepting
        the Hermes v0.15.x plugin hook kwargs ``model_name``/``platform``/
        ``provider``. When ``model_config`` is not supplied, a minimal dict is
        built from the keyword args so ``_extract_model_metadata`` always
        receives a dict. Note that ``platform`` (e.g. ``"cli"``) does NOT map to
        the ``provider`` field — it is the Hermes interface, not the inference
        backend; ``provider`` is supplied explicitly or slug-inferred.

        Model metadata is enriched at start: a local Ollama model is enriched
        via ``ollama.show()``; a remote slug degrades to light slug inference
        (CAPT-04). All enrichment is fault-tolerant — a missing or unreachable
        Ollama never raises.

        Args:
            session_id: Unique identifier for the session.
            model_config: Optional dict from Hermes Agent's model configuration.
            model_name: Optional model name from the plugin hook (keyword-only).
            platform: Optional Hermes interface from the plugin hook
                (keyword-only); stored as the platform, NOT the provider.
            provider: Optional inference provider/backend from the plugin hook
                (keyword-only); used to detect a local Ollama session.
            **_: Any additional, unexpected kwargs (tolerated; MP-2).
        """
        try:
            if model_config is None and model_name is not None:
                model_config = {
                    "model_name": model_name,
                    "provider": provider,
                    "platform": platform,
                }
            if model_config is None:
                model_config = {}
            self._session_id = session_id
            self._conversations = []
            self._pain_points = []
            self._outcome = None
            self._pending_tools = {}
            self._gpt_turn_index = {}
            self._last_gpt_turn_id = None
            self._seen_tool_call_ids = set()
            self._finalized = False
            self._created_at = datetime.now(UTC)
            self._model_metadata, self._hardware = _build_metadata_and_hardware(
                model_config
            )
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

    def on_llm_turn(
        self,
        *,
        user_message: str = "",
        assistant_response: str = "",
        turn_id: Optional[str] = None,
        **_: object,
    ) -> None:
        """Capture one Hermes post-LLM-call as a paired human + gpt turn (CAPT-02).

        Appends exactly one ``human`` ConversationTurn (value=``user_message``)
        followed by one ``gpt`` ConversationTurn (value=``assistant_response``),
        per RESEARCH Pattern 1. Any ``conversation_history`` kwarg is accepted
        for ordering/dedup context ONLY and is never re-ingested as turns, so a
        populated history does not double-count (Correction 4). Flushes any
        tools already buffered under ``turn_id`` onto the gpt turn. Fault-
        tolerant: never raises; no scrubbing here (scrub is a CLI step).

        Args:
            user_message: The user prompt text for this turn (keyword-only).
            assistant_response: The assistant reply text (keyword-only).
            turn_id: The Hermes turn identifier used to attach tools
                (keyword-only).
            **_: Any additional kwargs (e.g. ``conversation_history``,
                ``session_id``, ``model``) — tolerated, never re-ingested.
        """
        try:
            human_turn = ConversationTurn(**{"from": "human"}, value=user_message)
            self._conversations.append(human_turn)

            gpt_turn = ConversationTurn(**{"from": "gpt"}, value=assistant_response)
            self._conversations.append(gpt_turn)
            gpt_index = len(self._conversations) - 1

            if turn_id is not None:
                self._gpt_turn_index[turn_id] = gpt_index
                self._last_gpt_turn_id = turn_id
                buffered = self._pending_tools.pop(turn_id, None)
                if buffered:
                    existing = gpt_turn.tool_calls or []
                    gpt_turn.tool_calls = existing + buffered
        except Exception:
            logger.exception("Error in on_llm_turn")

    def on_tool_call(
        self,
        *,
        tool_name: str = "",
        args: Optional[dict] = None,
        result: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        turn_id: Optional[str] = None,
        status: Optional[str] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None,
        **_: object,
    ) -> None:
        """Ingest one Hermes post-tool-call into a ToolCall (CAPT-03).

        Maps the Hermes ``status`` to a ``ToolStatusType``: an error
        (``error_type``/``error_message`` present) maps to ``"timeout"`` when
        the error indicates a timeout, else ``"error"``; otherwise
        ``status="ok"`` maps EXACTLY to ``"success"`` (Correction 2 — raw
        ``"ok"`` is never stored). The JSON-string ``result`` is parsed with a
        try/except fallback to the raw string (finding 3) and truncated; the
        already-dict ``args`` is serialized into ``tool_input`` via
        ``json.dumps``. Deduped by ``tool_call_id``. Attaches to the gpt turn
        for ``turn_id`` if it already exists, else buffers under ``turn_id``
        (covers tool-before-turn and tool-after-turn orderings). Fault-tolerant.

        Args:
            tool_name: The invoked tool name (keyword-only).
            args: The tool input arguments dict (keyword-only).
            result: The tool result as a JSON string (keyword-only).
            tool_call_id: Unique id used for dedup (keyword-only).
            turn_id: The turn this tool belongs to (keyword-only).
            status: The Hermes tool status, e.g. ``"ok"`` (keyword-only).
            error_type: Optional error class name (keyword-only).
            error_message: Optional error message (keyword-only).
            duration_ms: Optional tool latency in ms (keyword-only).
            **_: Any additional kwargs (tolerated; MP-2).
        """
        try:
            if tool_call_id is not None and tool_call_id in self._seen_tool_call_ids:
                return
            if tool_call_id is not None:
                self._seen_tool_call_ids.add(tool_call_id)

            tool_status = self._map_tool_status(status, error_type, error_message)

            tool_output = ""
            if result is not None:
                try:
                    parsed = json.loads(result)
                    tool_output = (
                        parsed if isinstance(parsed, str) else json.dumps(parsed)
                    )
                except (ValueError, TypeError):
                    tool_output = result
                tool_output = tool_output[:2000]

            tool_input = ""
            if args is not None:
                try:
                    tool_input = json.dumps(args)[:2000]
                except (TypeError, ValueError):
                    tool_input = str(args)[:2000]

            tool_call = ToolCall(
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output=tool_output,
                tool_status=tool_status,
                latency_ms=duration_ms,
            )

            gpt_index = (
                self._gpt_turn_index.get(turn_id) if turn_id is not None else None
            )
            if gpt_index is not None and 0 <= gpt_index < len(self._conversations):
                gpt_turn = self._conversations[gpt_index]
                gpt_turn.tool_calls = (gpt_turn.tool_calls or []) + [tool_call]
            else:
                key = turn_id if turn_id is not None else self._last_gpt_turn_id or ""
                self._pending_tools.setdefault(key, []).append(tool_call)
        except Exception:
            logger.exception("Error in on_tool_call")

    @staticmethod
    def _map_tool_status(
        status: Optional[str],
        error_type: Optional[str],
        error_message: Optional[str],
    ) -> str:
        """Map a Hermes tool status to a schema ``ToolStatusType`` (Correction 2).

        Args:
            status: The raw Hermes status (e.g. ``"ok"``).
            error_type: Optional error class name.
            error_message: Optional error message.

        Returns:
            One of ``"success"``/``"error"``/``"timeout"``/``"failure"``. Hermes
            ``"ok"`` maps to ``"success"``; raw ``"ok"`` is never returned.
        """
        if error_type or error_message:
            blob = f"{error_type or ''} {error_message or ''}".lower()
            if "timeout" in blob or "timed out" in blob:
                return "timeout"
            return "error"
        if status == "ok" or status == "success":
            return "success"
        if status == "timeout":
            return "timeout"
        if status in ("error", "failure"):
            return status
        # Unknown/absent status with no error signal — treat as success.
        return "success"

    def on_session_end(self, session_id: str) -> None:
        """Finalize record and optionally auto-submit in continuous mode.

        In ad-hoc mode (default), saves the record to staging for manual review.
        In continuous mode, computes quality score and auto-submits if the record
        meets the configured minimum quality tier. Below-threshold records are
        saved to staging.

        All operations are fault-tolerant: errors are logged but never raised
        to the caller.

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

            # Check contribution mode (per D-04, D-07)
            contribution_mode = _load_config_value("contribution_mode", "ad-hoc")
            if contribution_mode != "continuous":
                # Ad-hoc mode: idempotent overwrite of session_{id}.json. Hermes
                # fires on_session_end after EACH turn (finding 2); N firings
                # accumulate the trajectory and rewrite the SAME file, yielding
                # exactly ONE staging file per session (Correction 3).
                self._save_to_staging()
                return

            # --- Continuous mode auto-submit (D-04) ---
            # Guard against per-turn firings: submit at most once per session.
            if self._finalized:
                return
            self._finalized = True
            record = self._build_record()
            scrubbed, scrub_log = scrub_record(record)
            anonymized = anonymize_hardware(scrubbed)
            quality = compute_quality_score(anonymized)

            min_tier = _load_config_value("min_quality_tier", "silver")
            if tier_meets_threshold(quality.quality_tier, min_tier):
                # Auto-submit: apply full privacy pipeline
                jittered = jitter_timestamp(anonymized)

                consent_level = "full"
                if record.submission and record.submission.consent_level:
                    consent_level = record.submission.consent_level
                final = apply_consent_level(jittered, consent_level)

                if final.submission is None:
                    final.submission = SubmissionMetadata()
                final.submission.scrub_log = scrub_log

                final.quality = QualityMetadata(
                    quality_tier=quality.quality_tier,
                    composite_score=quality.composite_score,
                    sub_scores=quality.sub_scores,
                    scored_at=datetime.now(UTC),
                )

                final.compute_record_id()
                final.compute_submission_hash()

                OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
                outbox_file = OUTBOX_DIR / f"record_{final.record_id}.jsonl"
                record_json = final.model_dump(mode="json", by_alias=True)
                outbox_file.write_text(
                    json.dumps(record_json, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )

                _log_activity("auto_submitted", final.record_id or "", quality.quality_tier)
                logger.info("Auto-submitted record (tier: %s)", quality.quality_tier)
            else:
                # Below threshold: save to staging for manual review (D-09)
                self._save_to_staging()
                _log_activity("queued_for_review", self._session_id or "", quality.quality_tier)
                logger.info(
                    "Record queued for review (tier: %s, min: %s)",
                    quality.quality_tier, min_tier,
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

    def _build_trajectory(self) -> Trajectory:
        """Assemble a Trajectory from the buffered conversation turns.

        Shared sub-assembly for both the coding finalize path (``_build_record``)
        and the experiment finalize path. Tallies tool-call counts from the
        per-turn ``tool_calls`` and constructs the ``sharegpt_extended``
        Trajectory over ``self._conversations``.

        Returns:
            The assembled Trajectory over the current conversation turns.
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

        return Trajectory(
            format="sharegpt_extended",
            conversations=self._conversations,
            turn_count=turn_count,
            total_tool_calls=total_tool_calls,
            successful_tool_calls=successful_tool_calls,
            failed_tool_calls=failed_tool_calls,
        )

    def _build_record(self) -> KajibaRecord:
        """Build a KajibaRecord from collected data.

        Returns:
            The assembled KajibaRecord (not yet scrubbed or scored).
        """
        trajectory = self._build_trajectory()

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

    def _save_to_staging(self) -> None:
        """Save the current session data to a staging file.

        Builds the record from collected data and writes it to the staging
        directory as a JSON file. Does NOT apply any privacy processing --
        that happens at submit/export time.
        """
        record = self._build_record()
        STAGING_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"session_{self._session_id or 'unknown'}.json"
        staging_file = STAGING_DIR / filename
        record_json = record.model_dump(mode="json", by_alias=True)
        staging_file.write_text(
            json.dumps(record_json, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        logger.info("Saved session to staging: %s", staging_file)

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
