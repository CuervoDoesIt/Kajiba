"""Tests for the Kajiba Hermes plugin entry point and hook handlers.

Covers register(ctx) hook wiring, **kwargs forward-compat tolerance (MP-2),
and KAJIBA_DEBUG kwarg logging. These tests are RED until Plan 03 creates the
kajiba.plugin package; imports of register/handlers are deferred into the test
bodies so this module still collects cleanly beforehand.
"""

import logging

import pytest


# ---------------------------------------------------------------------------
# Stub ctx fixture
# ---------------------------------------------------------------------------


class StubCtx:
    """Minimal stand-in for the Hermes plugin context.

    Records every register_hook(event, callback) call into a dict so tests can
    assert which hook events the plugin wires up.
    """

    def __init__(self) -> None:
        self.hooks: dict = {}

    def register_hook(self, event: str, callback) -> None:
        """Record a hook registration (event -> callback)."""
        self.hooks[event] = callback


@pytest.fixture
def stub_ctx() -> StubCtx:
    """Return a fresh StubCtx for each test."""
    return StubCtx()


# ---------------------------------------------------------------------------
# register(ctx) wiring tests
# ---------------------------------------------------------------------------


class TestRegister:
    """Tests for kajiba.plugin.register."""

    def test_register_hooks(self, stub_ctx: StubCtx) -> None:
        """register(ctx) registers all four Hermes lifecycle hook events."""
        from kajiba.plugin import register

        register(stub_ctx)

        assert "on_session_start" in stub_ctx.hooks
        assert "post_llm_call" in stub_ctx.hooks
        assert "post_tool_call" in stub_ctx.hooks
        assert "on_session_end" in stub_ctx.hooks


# ---------------------------------------------------------------------------
# **kwargs forward-compat tolerance (MP-2)
# ---------------------------------------------------------------------------


class TestKwargTolerance:
    """Tests that handlers accept unexpected kwargs without raising (MP-2)."""

    def test_handlers_accept_extra_kwarg(self) -> None:
        """Each handler tolerates an unexpected extra kwarg (no exception)."""
        from kajiba.plugin.hooks import (
            on_post_llm_call,
            on_post_tool_call,
            on_session_end,
            on_session_start,
        )

        # An unexpected "surprise" kwarg must be swallowed, not crash the host.
        on_session_start(session_id="x", surprise="z")
        on_post_llm_call(session_id="x", surprise="z")
        on_post_tool_call(session_id="x", surprise="z")
        on_session_end(session_id="x", surprise="z")


# ---------------------------------------------------------------------------
# KAJIBA_DEBUG logging
# ---------------------------------------------------------------------------


class TestDebugLogging:
    """Tests for KAJIBA_DEBUG kwarg logging in the hook handlers."""

    def test_debug_logging(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """With _DEBUG patched on, a handler logs a KAJIBA_DEBUG warning record."""
        from kajiba.plugin import hooks

        # _DEBUG is read at import time, so patch the module attribute directly
        # rather than relying on setenv-after-import.
        monkeypatch.setattr("kajiba.plugin.hooks._DEBUG", True)

        with caplog.at_level(logging.WARNING, logger=hooks.__name__):
            hooks.on_session_start(session_id="x")

        assert any("KAJIBA_DEBUG" in record.getMessage() for record in caplog.records)


# ---------------------------------------------------------------------------
# Phase 7 RED hook-dispatch scaffolds
#
# These tests assert the PROMOTED on_post_llm_call / on_post_tool_call hooks
# DISPATCH to the collector (Phase 6 left them debug-log-only). They reference
# collector methods that do not yet exist (on_llm_turn / on_tool_call), so they
# fail RED. Kwarg names are verbatim from 06-HOOK-KWARGS.md (Hook 2 / Hook 3).
# Selectors (validation map): post_llm, post_tool, dispatch, fault.
# ---------------------------------------------------------------------------


class _SpyCollector:
    """A spy collector that records dispatched paired-turn / tool calls."""

    def __init__(self) -> None:
        self.llm_turn_calls: list[dict] = []
        self.tool_calls: list[dict] = []

    def on_llm_turn(self, **kwargs) -> None:
        self.llm_turn_calls.append(kwargs)

    def on_tool_call(self, **kwargs) -> None:
        self.tool_calls.append(kwargs)


class _ExplodingCollector:
    """A collector whose dispatch methods raise (fault-tolerance probe)."""

    def on_llm_turn(self, **kwargs) -> None:
        raise RuntimeError("on_llm_turn exploded")

    def on_tool_call(self, **kwargs) -> None:
        raise RuntimeError("on_tool_call exploded")


# Live-verified kwarg payloads (06-HOOK-KWARGS Hook 2 / Hook 3).
_POST_LLM_KWARGS = {
    "session_id": "sess-7",
    "user_message": "<user prompt text>",
    "assistant_response": "<assistant reply text>",
    "conversation_history": [{"role": "human", "content": "prior"}],
    "model": "nvidia/nemotron-3-ultra:free",
    "platform": "cli",
    "task_id": "sess-7",
    "turn_id": "sess-7:sess-7:0cd552b7",
    "telemetry_schema_version": "hermes.observer.v1",
}

_POST_TOOL_KWARGS = {
    "tool_name": "read_file",
    "args": {"path": "/app/main.py"},
    "result": '{"content": "<file text>"}',
    "task_id": "sess-7",
    "duration_ms": 5141,
    "session_id": "sess-7",
    "tool_call_id": "call_3ee741469cfa45b69e1b1d9f",
    "turn_id": "sess-7:sess-7:0cd552b7",
    "status": "ok",
    "telemetry_schema_version": "hermes.observer.v1",
}


class TestHookDispatch:
    """Promoted turn/tool hooks dispatch to the collector (not debug-log only)."""

    def test_post_llm_call_dispatches_to_collector(self) -> None:
        """on_post_llm_call invokes collector.on_llm_turn with extracted kwargs."""
        from kajiba.plugin import hooks

        spy = _SpyCollector()
        hooks.set_collector(spy)
        try:
            hooks.on_post_llm_call(**_POST_LLM_KWARGS)
        finally:
            hooks.set_collector(None)

        assert len(spy.llm_turn_calls) == 1
        call = spy.llm_turn_calls[0]
        assert call["user_message"] == "<user prompt text>"
        assert call["assistant_response"] == "<assistant reply text>"
        assert call["turn_id"] == "sess-7:sess-7:0cd552b7"

    def test_post_tool_call_dispatches_to_collector(self) -> None:
        """on_post_tool_call invokes collector.on_tool_call with extracted kwargs."""
        from kajiba.plugin import hooks

        spy = _SpyCollector()
        hooks.set_collector(spy)
        try:
            hooks.on_post_tool_call(**_POST_TOOL_KWARGS)
        finally:
            hooks.set_collector(None)

        assert len(spy.tool_calls) == 1
        call = spy.tool_calls[0]
        assert call["tool_name"] == "read_file"
        assert call["args"] == {"path": "/app/main.py"}
        assert call["result"] == '{"content": "<file text>"}'
        assert call["tool_call_id"] == "call_3ee741469cfa45b69e1b1d9f"
        assert call["turn_id"] == "sess-7:sess-7:0cd552b7"
        assert call["status"] == "ok"


class TestHookFaultTolerance:
    """A raising collector method must NOT propagate out of the hook (Hermes safe)."""

    def test_post_llm_call_fault_does_not_propagate(self) -> None:
        """on_post_llm_call swallows a raising collector.on_llm_turn."""
        from kajiba.plugin import hooks

        hooks.set_collector(_ExplodingCollector())
        try:
            # Must NOT raise — Hermes is never disrupted.
            hooks.on_post_llm_call(**_POST_LLM_KWARGS)
        finally:
            hooks.set_collector(None)

    def test_post_tool_call_fault_does_not_propagate(self) -> None:
        """on_post_tool_call swallows a raising collector.on_tool_call."""
        from kajiba.plugin import hooks

        hooks.set_collector(_ExplodingCollector())
        try:
            hooks.on_post_tool_call(**_POST_TOOL_KWARGS)
        finally:
            hooks.set_collector(None)
