"""Hermes hook handlers for the Kajiba plugin.

Targets Hermes Agent v0.15.x. Each handler accepts ``**kwargs`` (forward-compat;
avoids a silent ``TypeError`` that Hermes would swallow -- MP-2) and dispatches
to the module-level ``KajibaCollector``. The v0.15.x lifecycle hook signatures
are documented (see 06-REPLAN-RESEARCH section 3); the ``**kwargs`` tolerance
keeps the handlers robust to additional documented kwargs. When
``KAJIBA_DEBUG=1``, every handler logs the name, type, and a truncated value of
each kwarg it receives -- the diagnostic mechanism (D-05, CAPT-01) that the
Plan 05 live v0.15.x session uses to confirm the documented hook payload shapes
that unblock Phase 7.

Scope note (Phase 7): all four handlers now drive real collector state.
``on_post_llm_call`` dispatches the user/assistant pair to the collector's
paired-turn capture (CAPT-02) and ``on_post_tool_call`` dispatches tool events
to the collector's turn-keyed tool ingest (CAPT-03). The kwarg names are the
live-verified Hermes v0.15.x payload contract from 06-HOOK-KWARGS.md. Each
handler keeps the ``KAJIBA_DEBUG`` log line and the fault-tolerant try/except +
``if _collector is not None`` shell so a raising collector never disrupts
Hermes. No scrubbing happens in hooks (scrub is a CLI step).
"""

import logging
import os
from typing import Optional

from kajiba.collector import KajibaCollector

logger = logging.getLogger(__name__)

# Module-level collector singleton, installed once by register(ctx).
_collector: Optional[KajibaCollector] = None

# Read once at import time; tests patch this attribute directly rather than
# relying on setenv-after-import.
_DEBUG = os.environ.get("KAJIBA_DEBUG") == "1"


def set_collector(collector: KajibaCollector) -> None:
    """Install the active collector singleton (called once by register)."""
    global _collector
    _collector = collector


def _log_kwargs(hook_name: str, named: dict, extra: dict) -> None:
    """Log kwarg names/types/values (truncated) when KAJIBA_DEBUG=1.

    Args:
        hook_name: The hook whose payload is being logged.
        named: The explicitly-declared kwargs (name -> value).
        extra: The unexpected kwargs caught by ``**kwargs``.
    """
    if not _DEBUG:
        return
    for k, v in {**named, **extra}.items():
        # Truncate the repr to 120 chars: hook payloads carry raw prompts and
        # responses with PII before any scrub runs, so full bodies are never
        # logged (T-06-07). %s lazy logging is mandatory (CLAUDE.md).
        logger.warning(
            "KAJIBA_DEBUG %s kwarg %s: type=%s value=%s",
            hook_name,
            k,
            type(v).__name__,
            repr(v)[:120],
        )


def on_session_start(session_id=None, model=None, platform=None, **kwargs) -> None:
    """Dispatch a Hermes session-start event to the collector.

    Args:
        session_id: The Hermes session identifier ([ASSUMED] kwarg name).
        model: The model name/identity for this session ([ASSUMED]).
        platform: The provider/platform for this session ([ASSUMED]).
        **kwargs: Any additional, unexpected kwargs (tolerated; MP-2).
    """
    try:
        _log_kwargs(
            "on_session_start",
            {"session_id": session_id, "model": model, "platform": platform},
            kwargs,
        )
        if _collector is not None:
            _collector.on_session_start(
                session_id=session_id, model_name=model, platform=platform
            )
    except Exception:
        logger.exception("Error in on_session_start hook")


def on_post_llm_call(**kwargs) -> None:
    """Dispatch a Hermes post-LLM-call event to the collector (CAPT-02).

    Keeps the ``KAJIBA_DEBUG`` log line, then extracts the live-verified
    payload kwargs (``user_message``/``assistant_response``/``turn_id`` plus
    session/model context) and invokes the collector's paired-turn capture when
    a collector is installed. ``kwargs.get(...)`` tolerates missing/extra kwargs
    (MP-2); a raising collector is swallowed so Hermes is never disrupted.

    Args:
        **kwargs: The raw post-LLM-call payload (all tolerated; MP-2).
    """
    try:
        _log_kwargs("on_post_llm_call", {}, kwargs)
        if _collector is not None:
            _collector.on_llm_turn(
                user_message=kwargs.get("user_message", ""),
                assistant_response=kwargs.get("assistant_response", ""),
                turn_id=kwargs.get("turn_id"),
                conversation_history=kwargs.get("conversation_history"),
                session_id=kwargs.get("session_id"),
                model=kwargs.get("model"),
            )
    except Exception:
        logger.exception("Error in on_post_llm_call hook")


def on_post_tool_call(**kwargs) -> None:
    """Dispatch a Hermes post-tool-call event to the collector (CAPT-03).

    Keeps the ``KAJIBA_DEBUG`` log line, then extracts the live-verified tool
    payload kwargs and invokes the collector's tool-ingest method when a
    collector is installed. ``kwargs.get(...)`` tolerates missing/extra kwargs
    (MP-2); a raising collector is swallowed so Hermes is never disrupted.

    Args:
        **kwargs: The raw post-tool-call payload (all tolerated; MP-2).
    """
    try:
        _log_kwargs("on_post_tool_call", {}, kwargs)
        if _collector is not None:
            _collector.on_tool_call(
                tool_name=kwargs.get("tool_name", ""),
                args=kwargs.get("args"),
                result=kwargs.get("result"),
                tool_call_id=kwargs.get("tool_call_id"),
                turn_id=kwargs.get("turn_id"),
                status=kwargs.get("status"),
                error_type=kwargs.get("error_type"),
                error_message=kwargs.get("error_message"),
                duration_ms=kwargs.get("duration_ms"),
            )
    except Exception:
        logger.exception("Error in on_post_tool_call hook")


def on_session_end(session_id=None, **kwargs) -> None:
    """Dispatch a Hermes session-end event to the collector.

    Args:
        session_id: The Hermes session identifier ([ASSUMED] kwarg name).
        **kwargs: Any additional, unexpected kwargs (tolerated; MP-2).
    """
    try:
        _log_kwargs("on_session_end", {"session_id": session_id}, kwargs)
        if _collector is not None:
            _collector.on_session_end(session_id=session_id)
    except Exception:
        logger.exception("Error in on_session_end hook")
