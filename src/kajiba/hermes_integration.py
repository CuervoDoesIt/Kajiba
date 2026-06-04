"""Thin adapter layer for Hermes Agent integration.

Wires the KajibaCollector lifecycle hooks into Hermes Agent's event system.
Gracefully no-ops if Hermes Agent is not available, so Kajiba can also be
used standalone for manual record creation.

Expected Hermes Agent hook API:
    The Hermes Agent is expected to provide an event system (agent.events or
    similar) that supports subscribing to the following lifecycle events:

    - 'session_start': Fired when a new agent session begins.
      Payload: {'session_id': str, 'model_config': dict}

    - 'turn_complete': Fired after each conversation turn.
      Payload: {'role': 'human'|'gpt', 'content': str,
                'tool_calls': list[dict]|None, 'token_count': int|None,
                'latency_ms': int|None}

    - 'session_end': Fired when the session ends.
      Payload: {'session_id': str}

    The agent object is expected to have:
    - agent.on(event_name, callback) — subscribe to an event
    - agent.register_command(name, handler) — register a slash command
"""

import logging
from typing import Protocol, runtime_checkable

from kajiba.collector import KajibaCollector

logger = logging.getLogger(__name__)


@runtime_checkable
class HermesAgent(Protocol):
    """Protocol describing the expected Hermes Agent interface."""

    def on(self, event: str, callback: object) -> None:
        """Subscribe to an agent lifecycle event."""
        ...

    def register_command(self, name: str, handler: object) -> None:
        """Register a slash command handler."""
        ...


def register_hooks(agent: object) -> KajibaCollector:
    """Wire KajibaCollector lifecycle hooks into a Hermes Agent.

    Subscribes to session_start, turn_complete, and session_end events,
    and registers /rate and /report slash commands.

    If the agent object does not support the expected interface, this
    function logs a warning and returns a standalone collector instance.

    Args:
        agent: A Hermes Agent instance (or any object matching the
            HermesAgent protocol).

    Returns:
        The KajibaCollector instance (useful for manual export if needed).
    """
    collector = KajibaCollector()

    if not isinstance(agent, HermesAgent):
        logger.warning(
            "Agent does not match expected HermesAgent interface. "
            "Kajiba collector created in standalone mode — "
            "call lifecycle methods manually."
        )
        return collector

    try:
        agent.on("session_start", lambda payload: collector.on_session_start(
            session_id=payload["session_id"],
            model_config=payload["model_config"],
        ))

        agent.on("turn_complete", lambda payload: collector.on_turn_complete(payload))

        agent.on("session_end", lambda payload: collector.on_session_end(
            session_id=payload["session_id"],
        ))

        logger.info("Kajiba collector hooks registered with Hermes Agent")

    except Exception:
        logger.exception(
            "Failed to register Kajiba hooks with agent. "
            "Collector available in standalone mode."
        )

    return collector
