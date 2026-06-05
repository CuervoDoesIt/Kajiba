"""Hermes plugin entry point for Kajiba.

Targets Hermes Agent v0.15.x. Hermes discovers this package under the resolved
plugins discovery directory (``<HERMES_HOME>/plugins/kajiba/`` -- a dev-only
symlink into ``src/kajiba/plugin/``) and calls ``register(ctx)`` once at startup
to wire Kajiba's session-lifecycle hooks. The plugin must also be enabled
(``hermes plugins enable kajiba``); a discovered-but-disabled plugin will not
load. This replaces the deleted Protocol-based ``hermes_integration.py`` adapter
(D-07): the v0.15.x contract is ``ctx.register_hook(event, callback)``, not
``agent.on(...)`` (anti-pattern MP-1).
"""

import logging

from kajiba.collector import KajibaCollector
from kajiba.plugin.hooks import (
    on_post_llm_call,
    on_post_tool_call,
    on_session_end,
    on_session_start,
    set_collector,
)

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    """Register Kajiba's hooks with the Hermes plugin host.

    Hermes calls this once at startup. It never raises: Hermes disables a plugin
    that crashes during registration, so any failure is caught and logged and
    the plugin simply disables itself (T-06-06).

    Args:
        ctx: The Hermes plugin context exposing
            ``register_hook(event, callback)``.
    """
    try:
        set_collector(KajibaCollector())
        ctx.register_hook("on_session_start", on_session_start)
        ctx.register_hook("post_llm_call", on_post_llm_call)
        ctx.register_hook("post_tool_call", on_post_tool_call)
        ctx.register_hook("on_session_end", on_session_end)
        logger.info(
            "Kajiba registered hooks: %s",
            "on_session_start, post_llm_call, post_tool_call, on_session_end",
        )
    except Exception:
        logger.exception("Kajiba plugin registration failed; plugin disabled")
