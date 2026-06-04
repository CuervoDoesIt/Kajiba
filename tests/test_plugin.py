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
