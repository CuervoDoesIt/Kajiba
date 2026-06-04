"""Static guard locking the D-07 deletion of hermes_integration.py.

Phase 6 replaces the old Protocol-based hermes_integration module with a real
Hermes plugin package. These tests assert that no source file imports the
deprecated module and that the module is no longer importable. They are RED
until Plan 02 deletes src/kajiba/hermes_integration.py, then flip GREEN and
stay GREEN to prevent regression.
"""

import importlib

import pytest


# ---------------------------------------------------------------------------
# Source-scan guard
# ---------------------------------------------------------------------------


def test_no_source_imports_hermes_integration() -> None:
    """No source file under src/kajiba/ imports hermes_integration."""
    from pathlib import Path

    src_dir = Path(__file__).resolve().parents[1] / "src" / "kajiba"
    offenders: list[str] = []
    for py_file in src_dir.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        if (
            "import hermes_integration" in text
            or "from kajiba.hermes_integration" in text
            or "from .hermes_integration" in text
        ):
            offenders.append(str(py_file))

    assert offenders == [], f"hermes_integration still imported by: {offenders}"


# ---------------------------------------------------------------------------
# Module-absence guard
# ---------------------------------------------------------------------------


def test_hermes_integration_module_absent() -> None:
    """kajiba.hermes_integration is no longer importable (module deleted)."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("kajiba.hermes_integration")
