# Phase 6: Environment + Plugin Foundation - Pattern Map

**Mapped:** 2026-06-04
**Files analyzed:** 11 (3 new code, 1 new test, 1 new doc, 5 modified code, 1 modified test)
**Analogs found:** 10 / 11 (the env doc has a weak/style-only analog)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| NEW `src/kajiba/plugin/__init__.py` | provider/registration | event-driven | `src/kajiba/hermes_integration.py` (WRONG-style) + `collector.py` fault tolerance | role-match (anti-pattern reference) |
| NEW `src/kajiba/plugin/hooks.py` | handler/adapter | event-driven | `src/kajiba/collector.py` lifecycle methods | exact |
| NEW `src/kajiba/plugin/plugin.yaml` | config/manifest | n/a | RESEARCH.md Code Examples (no codebase analog) | no analog |
| MODIFY `src/kajiba/config.py` | config/utility | transform | own existing constants + soft-import pattern | exact (in-file) |
| MODIFY `src/kajiba/collector.py` | service | event-driven | own `on_session_start` / `_extract_model_metadata` | exact (in-file) |
| MODIFY `src/kajiba/cli.py` | controller | request-response | own path constants | exact (in-file) |
| MODIFY `src/kajiba/publisher.py` | service | file-I/O | own `CLONE_DIR` constant | exact (in-file) |
| MODIFY `src/kajiba/experiment_store.py` | store | CRUD | own `EXPERIMENTS_DIR` constant (parity-pinned) | exact (in-file) |
| DELETE `src/kajiba/hermes_integration.py` | — | — | — | — |
| NEW `tests/test_plugin.py` | test | event-driven | `tests/test_collector.py` + `tests/test_config.py` fixtures | role-match |
| MODIFY `tests/test_config.py` | test | transform | own existing `fake_home`/`monkeypatch` fixtures | exact (in-file) |
| NEW `docs/hermes-setup.md` | doc | n/a | existing `docs/*.md` style | style-only |

## Shared Patterns (apply to ALL new/modified code files)

These come from CLAUDE.md and are confirmed live in every analog read this session:

- **Module docstring** — every module opens with a `"""..."""` describing its role in the Kajiba spec (see `collector.py:1-6`, `config.py:1-5`, `hermes_integration.py:1-25`).
- **Logger** — `logger = logging.getLogger(__name__)` at module top (`collector.py:36`, `config.py:15`, `hermes_integration.py:32`).
- **Lazy `%s` logging** — never f-strings in logger calls: `logger.info("Kajiba collector started for session %s", session_id)` (`collector.py:192`). `logger.exception("Error in on_session_start")` (`collector.py:194`).
- **Typing** — `from typing import Optional`; use `Optional[X]` NOT `X | None`; modern generics `list[...]`, `dict[str, int]` (`collector.py:14,62-65,170`, `config.py:11,21`).
- **Double quotes** everywhere; trailing commas on multi-line structures (`collector.py:120-128`).
- **UPPER_SNAKE_CASE module constants** (`KAJIBA_BASE`, `STAGING_DIR`, `EXPERIMENTS_DIR`, `CLONE_DIR`).
- **Google docstrings** with `Args:` / `Returns:` / `Raises:` (`config.py:79-88`, `collector.py:178-183`).
- **Section dividers** — `# ----...----` rule + label (`config.py:17-19`, `cli.py:70-72`).
- **Fault tolerance** — wrap handler/registration bodies in `try/except Exception:` + `logger.exception(...)`; NEVER raise into Hermes (`collector.py:184-194`, `hermes_integration.py:88-93`).
- **Soft-dependency import** — conditional import inside function with graceful fallback (`config.py:92-101`, `collector.py:100-102`).

---

## Pattern Assignments

### `src/kajiba/plugin/__init__.py` (provider, event-driven)

**Analog:** `src/kajiba/hermes_integration.py` (deleted file — use as the WRONG shape to AVOID) + fault-tolerance from `collector.py`.

**WRONG pattern to NOT copy** (`hermes_integration.py:75-84`) — the old `agent.on(event, lambda payload: ...)` Protocol style. The new API is `ctx.register_hook("event", handler)`. Do not carry `HermesAgent` Protocol or `register_hooks(agent)` over (D-07, anti-pattern MP-1).

**Imports pattern** (copy module-docstring + import style from `hermes_integration.py:1-32`, adapt names):
```python
"""Hermes plugin entry point for Kajiba.

Hermes discovers this package under ~/.hermes/plugins/kajiba/ and calls
register(ctx) once at startup to wire session-lifecycle hooks.
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
```

**Registration pattern** (fault-tolerant wrapper from `collector.py:184-194` applied to RESEARCH.md Pattern 1):
```python
def register(ctx) -> None:
    """Register Kajiba hooks with the Hermes plugin host.

    Hermes calls this once at startup. Never raises: Hermes disables a
    plugin that crashes during registration.

    Args:
        ctx: Hermes plugin context exposing register_hook(event, callback).
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
```

---

### `src/kajiba/plugin/hooks.py` (handler, event-driven)

**Analog:** `src/kajiba/collector.py` lifecycle methods (`on_session_start` 177-194, `on_turn_complete` 196-227) — same try/except + `logger.exception` shape, ported to module-level functions.

**Module-level singleton + setter** (mirrors collector instance-state style):
```python
"""Hermes hook handlers for the Kajiba plugin.

Each handler accepts **kwargs (forward-compat; avoids silent TypeError that
Hermes swallows — MP-2) and dispatches to the module-level KajibaCollector.
When KAJIBA_DEBUG=1, every handler logs the name/type/value of all kwargs.
"""

import logging
import os
from typing import Optional

from kajiba.collector import KajibaCollector

logger = logging.getLogger(__name__)

_collector: Optional[KajibaCollector] = None
_DEBUG = os.environ.get("KAJIBA_DEBUG") == "1"


def set_collector(collector: KajibaCollector) -> None:
    """Install the active collector singleton (called once by register)."""
    global _collector
    _collector = collector
```

**Debug-logging helper** (CLAUDE.md `%s` lazy logging mandatory; truncate for PII — RESEARCH.md Pattern 3):
```python
def _log_kwargs(hook_name: str, named: dict, extra: dict) -> None:
    """Log kwarg names/types/values (truncated) when KAJIBA_DEBUG=1."""
    if not _DEBUG:
        return
    for k, v in {**named, **extra}.items():
        logger.warning(
            "KAJIBA_DEBUG %s kwarg %s: type=%s value=%s",
            hook_name, k, type(v).__name__, repr(v)[:120],
        )
```

**Handler pattern** (try/except fault tolerance from `collector.py:184-194`; `**kwargs` mandatory MP-2):
```python
def on_session_start(session_id=None, model=None, platform=None, **kwargs) -> None:
    """Dispatch Hermes session-start to the collector."""
    _log_kwargs("on_session_start",
                {"session_id": session_id, "model": model, "platform": platform},
                kwargs)
    try:
        if _collector is not None:
            _collector.on_session_start(
                session_id=session_id, model_name=model, platform=platform)
    except Exception:
        logger.exception("Error in on_session_start hook")
```
Replicate this exact skeleton for `on_post_llm_call`, `on_post_tool_call`, `on_session_end` (Phase 6: turn hooks are debug-log + minimal stub only — turn assembly is Phase 7).

---

### `src/kajiba/config.py` (config/utility, transform) — ADD `get_hermes_home()`

**Analog:** in-file. Existing constant `KAJIBA_BASE` (config.py:28), soft-import (config.py:92-101), Google docstring (config.py:79-88).

**New helper** (place after Constants divider, config.py:17-19 style):
```python
import os  # add to existing import block

def get_hermes_home() -> Path:
    """Resolve the active Hermes home directory.

    Checks the HERMES_HOME environment variable first (Hermes v0.6.0
    profile isolation); falls back to ``~/.hermes`` when unset.

    Returns:
        Path to the active Hermes home directory.
    """
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    return Path.home() / ".hermes"
```

**Migration target** (config.py:28, :89, :123). Decide constant-vs-lazy (RESEARCH Q2) consistently across all 5 files. Current literal `Path.home() / ".hermes" / "kajiba"` (config.py:28) and `Path.home() / ".hermes" / "config.yaml"` (config.py:89, 123) route through `get_hermes_home()`. Note tests use `monkeypatch.setattr(Path, "home", ...)` (test_config.py:24) — lazy/function eval is safest for that.

---

### `src/kajiba/collector.py` (service, event-driven) — signature adaptation + path migration

**Analog:** in-file. `on_session_start` (collector.py:177-194), `_extract_model_metadata` (collector.py:131-149).

**Backwards-compatible signature** (existing tests call positionally with dict — test_collector.py:21-30; MUST keep working):
```python
def on_session_start(
    self,
    session_id: str,
    model_config: Optional[dict] = None,
    *,
    model_name: Optional[str] = None,
    platform: Optional[str] = None,
) -> None:
    try:
        if model_config is None and model_name is not None:
            model_config = {"model_name": model_name, "provider": platform}
        # ... existing body collector.py:185-192 unchanged ...
    except Exception:
        logger.exception("Error in on_session_start")
```
`_extract_model_metadata(model_config: dict)` (collector.py:131-149) stays as-is — full Ollama enrichment is Phase 7. **Path migration:** `KAJIBA_BASE` (collector.py:38) → `get_hermes_home() / "kajiba"` via `from kajiba.config import get_hermes_home`.

---

### `src/kajiba/cli.py` (controller) — path migration only

**Analog:** in-file constants (cli.py:74-78). Migrate `KAJIBA_BASE` (:74), `DOWNLOADS_DIR` (:78), config.yaml paths (:852, :932), help text (:2163 cosmetic). `EXPERIMENTS_DIR` (cli.py:77) must stay equal to `experiment_store.EXPERIMENTS_DIR` (parity test). Import `get_hermes_home` from `kajiba.config`.

---

### `src/kajiba/publisher.py` (service, file-I/O) — path migration only

**Analog:** in-file. `CLONE_DIR = Path.home() / ".hermes" / "kajiba" / "dataset-clone"` (publisher.py:38) → `get_hermes_home() / "kajiba" / "dataset-clone"`. Keep the attached `"""docstring"""` constant-doc style (publisher.py:32-39).

---

### `src/kajiba/experiment_store.py` (store, CRUD) — path migration, PARITY-PINNED

**Analog:** in-file. `EXPERIMENTS_DIR` (experiment_store.py:50) → `get_hermes_home() / "kajiba" / "experiments"`. CRITICAL: `tests/test_experiment_store.py::test_experiments_dir_matches_cli` asserts `cli.EXPERIMENTS_DIR.resolve() == experiment_store.EXPERIMENTS_DIR.resolve()`. Migrate BOTH sides identically (both call `get_hermes_home()`). Update the explanatory comment block (experiment_store.py:44-49) to reference the helper. Module stays Click-free (do not import `kajiba.cli`).

---

### `tests/test_plugin.py` (test, event-driven) — NEW

**Analog:** `tests/test_collector.py` (class-per-feature, direct instantiation) + `tests/test_config.py` fixtures (`fake_home`/`monkeypatch`, test_config.py:21-39).

**Stub ctx fixture** (records register_hook calls):
```python
import pytest

class StubCtx:
    def __init__(self) -> None:
        self.hooks: dict = {}
    def register_hook(self, event: str, callback) -> None:
        self.hooks[event] = callback

@pytest.fixture
def stub_ctx() -> StubCtx:
    return StubCtx()
```
Cover: `test_register_hooks` (4 hooks registered), `test_handlers_accept_extra_kwarg` (MP-2 tolerance — call handler with unexpected kwarg, no raise), `test_debug_logging` (use `caplog` + `monkeypatch.setenv("KAJIBA_DEBUG", "1")`; note `_DEBUG` is read at import — reload module or patch the module attr).

---

### `tests/test_config.py` (test, transform) — ADD get_hermes_home cases

**Analog:** in-file `fake_home` fixture (test_config.py:21-25), class-per-function structure (test_config.py:47).

```python
class TestGetHermesHome:
    def test_returns_env_var_when_set(self, monkeypatch, tmp_path) -> None:
        from kajiba.config import get_hermes_home
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        assert get_hermes_home() == tmp_path

    def test_falls_back_to_home_when_unset(self, fake_home, monkeypatch) -> None:
        from kajiba.config import get_hermes_home
        monkeypatch.delenv("HERMES_HOME", raising=False)
        assert get_hermes_home() == fake_home / ".hermes"
```

---

### `docs/hermes-setup.md` (doc) — NEW

**Analog:** existing `docs/*.md` files (style only). Use `##`/`###` headers with checkpoint sections (WSL2 / GPU / Ollama / Hermes / Plugin) and fenced `bash`/`yaml` blocks. Include the symlink workflow (RESEARCH.md Symlink Dev Workflow) and MP-8/MP-9/MP-5 troubleshooting (D-04).

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/kajiba/plugin/plugin.yaml` | config/manifest | n/a | No YAML manifest exists in the codebase. Use RESEARCH.md Code Examples manifest (fields `[ASSUMED]` until live load). |

## Metadata

**Analog search scope:** `src/kajiba/`, `tests/`
**Files read this session:** collector.py (1-230), config.py (full), hermes_integration.py (full), experiment_store.py (40-54), publisher.py (30-41), cli.py (70-81), test_config.py (1-60), test_collector.py (1-50)
**Pattern extraction date:** 2026-06-04
