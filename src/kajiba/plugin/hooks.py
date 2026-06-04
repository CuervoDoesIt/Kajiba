"""Hermes hook handlers for the Kajiba plugin.

Each handler accepts ``**kwargs`` (forward-compat; avoids a silent ``TypeError``
that Hermes would swallow -- MP-2) and dispatches to the module-level
``KajibaCollector``. When ``KAJIBA_DEBUG=1``, every handler logs the name, type,
and a truncated value of each kwarg it receives -- the empirical-discovery
mechanism (D-05, CAPT-01) that the Plan 05 live session uses to capture the
ground-truth hook payload shapes that unblock Phase 7.

Scope note (Phase 6): ``on_session_start`` / ``on_session_end`` drive real
collector state; ``on_post_llm_call`` / ``on_post_tool_call`` are debug-log-only
capture stubs -- ConversationTurn / ToolCall assembly is deferred to Phase 7
because the turn-hook kwarg shapes are [ASSUMED] until Plan 05 confirms them.
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
    """Debug-log a Hermes post-LLM-call event (capture-only stub).

    Phase 6 logs the kwargs only; turn assembly is deferred to Phase 7 because
    the kwarg shape is [ASSUMED] until Plan 05 captures it live.

    Args:
        **kwargs: The raw post-LLM-call payload (all tolerated; MP-2).
    """
    try:
        _log_kwargs("on_post_llm_call", {}, kwargs)
    except Exception:
        logger.exception("Error in on_post_llm_call hook")


def on_post_tool_call(**kwargs) -> None:
    """Debug-log a Hermes post-tool-call event (capture-only stub).

    Phase 6 logs the kwargs only; tool-call assembly is deferred to Phase 7
    because the kwarg shape is [ASSUMED] until Plan 05 captures it live.

    Args:
        **kwargs: The raw post-tool-call payload (all tolerated; MP-2).
    """
    try:
        _log_kwargs("on_post_tool_call", {}, kwargs)
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
