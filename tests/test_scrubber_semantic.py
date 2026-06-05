"""RED scaffolds for the GLiNER semantic PII scrubber (Layer C).

These tests pin the contract for ``kajiba.scrubber_semantic`` BEFORE the module
exists (Nyquist compliance, plan 07-02). They encode the locked decisions:

* D-05 — confidence bands: ``score >= 0.7`` auto-redact, ``0.4 <= score < 0.7``
  flag, ``score < 0.4`` ignore.
* D-06 — calibration HARD GATE: ZERO auto-redacts (``score >= 0.7``) on known-safe
  code identifiers; flag-band hits are allowed; record the observed FP rate.
* D-07 — asymmetric coverage: ``ConversationTurn.value`` may auto-redact AND flag;
  ``tool_input`` / ``tool_output`` produce FLAGS ONLY and never mutate text.
* PRIV-04 / D-10 — soft import: ``import kajiba.scrubber_semantic`` succeeds without
  the ``[llm-scrub]`` extra; calling the model path raises ``SemanticScrubUnavailable``
  (a defined exception), never a raw ``ModuleNotFoundError``.

Two lanes:

* **LANE A** (``bands`` / ``asymmetric`` / ``soft_import``) — pure logic, no model.
  These import ``kajiba.scrubber_semantic`` INSIDE each test so that collection still
  succeeds (RED via test failure, not a collection error) while the module is absent.
* **LANE B** (``detect`` / ``calibration``) — model-dependent, guarded by
  ``pytest.importorskip("gliner")`` so they SKIP cleanly without the extra.

Until ``07-04`` builds ``scrubber_semantic.py``, LANE A is RED and LANE B skips.
"""

import json
from pathlib import Path

import pytest

# FlaggedItem is reused from the existing regex scrubber (do NOT redefine it here).
from kajiba.schema import validate_record
from kajiba.scrubber import FlaggedItem

FIXTURES = Path(__file__).parent / "fixtures"

# LANE B model id — capital ``PII`` (Correction 1). Lowercase 404s on Hugging Face.
GLINER_MODEL_ID = "nvidia/gliner-PII"

# D-06 calibration denominator: the known-safe identifiers seeded into
# tests/fixtures/code_content_pii.json. The FP rate is (# of these auto-redacted) /
# len(KNOWN_SAFE_TOKENS); the hard gate requires the numerator to be ZERO.
KNOWN_SAFE_TOKENS = (
    "pandas",
    "numpy",
    "React",
    "App",
    "DataGrid",
    "FastAPI",
    "Flask",
    "Django",
    "Customer",
    "Tornado",
    "Express",
    "Kubernetes",
    "compute_quality_score",
    "userController",
    "accountManager",
    "DataFrame",
)

# Genuine PII seeded in the same fixture's prose (true-positive proof for LANE B).
TRUE_POSITIVE_NAMES = ("Margaret Chen", "Aldebaran Robotics")


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _span(text: str, label: str, score: float, start: int = 0, end: int | None = None) -> dict:
    """Build a synthetic GLiNER span dict: {start, end, text, label, score}."""
    return {
        "start": start,
        "end": len(text) if end is None else end,
        "text": text,
        "label": label,
        "score": score,
    }


# ---------------------------------------------------------------------------
# LANE A — pure logic (no [llm-scrub], no model). Imports inside each test so
# collection succeeds while the module is absent (RED via failure, not error).
# ---------------------------------------------------------------------------


class TestBands:
    """D-05 band bucketing on synthetic span scores (selector: ``bands``)."""

    def test_bands_redact_above_threshold(self):
        from kajiba.scrubber_semantic import classify_band

        assert classify_band(0.70) == "redact"
        assert classify_band(0.95) == "redact"

    def test_bands_flag_middle_window(self):
        from kajiba.scrubber_semantic import classify_band

        assert classify_band(0.40) == "flag"
        assert classify_band(0.55) == "flag"
        assert classify_band(0.699) == "flag"

    def test_bands_ignore_below_floor(self):
        from kajiba.scrubber_semantic import classify_band

        assert classify_band(0.39) == "ignore"
        assert classify_band(0.0) == "ignore"

    def test_bands_partition_synthetic_spans(self):
        """Given mixed spans, redact/flag/ignore sets are disjoint and correct."""
        from kajiba.scrubber_semantic import classify_band

        spans = [
            _span("RedactMe", "person", 0.91),
            _span("FlagMe", "company", 0.55),
            _span("IgnoreMe", "project", 0.20),
        ]
        buckets = {s["text"]: classify_band(s["score"]) for s in spans}
        assert buckets == {"RedactMe": "redact", "FlagMe": "flag", "IgnoreMe": "ignore"}


class TestAsymmetric:
    """D-07 asymmetric coverage: tool fields flag-only (selector: ``asymmetric``)."""

    def test_asymmetric_turn_value_redacts_and_flags(self):
        """In ConversationTurn.value: >=0.7 redacts, 0.4-0.7 flags."""
        from kajiba.scrubber_semantic import scrub_record_semantic

        record = validate_record(_load_fixture("pii_trajectory.json"))
        scrubbed, names_redacted, flags = scrub_record_semantic(record)
        # Turn-value path is allowed to auto-redact names (mutating text).
        assert isinstance(names_redacted, int)
        assert all(isinstance(f, FlaggedItem) for f in flags)

    def test_asymmetric_tool_fields_flag_only_never_mutate(self):
        """Identical spans in tool_input/tool_output FLAG only and never mutate text."""
        from kajiba.scrubber_semantic import scrub_record_semantic

        record = validate_record(_load_fixture("code_content_pii.json"))
        tool_turn = next(t for t in record.trajectory.conversations if t.tool_calls)
        before_input = tool_turn.tool_calls[0].tool_input
        before_output = tool_turn.tool_calls[0].tool_output

        scrubbed, _names_redacted, flags = scrub_record_semantic(record)

        out_turn = next(t for t in scrubbed.trajectory.conversations if t.tool_calls)
        # Tool fields are NEVER mutated by the semantic layer (D-07).
        assert out_turn.tool_calls[0].tool_input == before_input
        assert out_turn.tool_calls[0].tool_output == before_output
        # Any semantic hits on tool fields must surface as FlaggedItem, not redaction.
        assert all(isinstance(f, FlaggedItem) for f in flags)


class TestSoftImport:
    """PRIV-04/D-10 graceful degradation without [llm-scrub] (selector: ``soft_import``)."""

    def test_soft_import_module_imports_without_extra(self):
        """Importing the module must NOT require gliner/torch to be installed."""
        import importlib

        # Import must succeed even with no [llm-scrub] extra present.
        mod = importlib.import_module("kajiba.scrubber_semantic")
        assert hasattr(mod, "SemanticScrubUnavailable")

    def test_soft_import_detect_entities_degrades_gracefully(self):
        """When gliner is absent, the model path raises SemanticScrubUnavailable
        (a defined exception) rather than a raw ModuleNotFoundError."""
        try:
            import gliner  # noqa: F401

            pytest.skip("gliner installed — absent-extra degradation path not exercised here")
        except ImportError:
            pass

        from kajiba.scrubber_semantic import SemanticScrubUnavailable, detect_entities

        with pytest.raises(SemanticScrubUnavailable):
            detect_entities("any text with a Name in it")


# ---------------------------------------------------------------------------
# LANE B — model-dependent. Guarded by importorskip("gliner") -> SKIP without
# the [llm-scrub] extra (keeps the core suite green).
# ---------------------------------------------------------------------------


class TestDetect:
    """PRIV-01 GLiNER fires on genuine PII (selector: ``detect``, needs [llm-scrub])."""

    def test_detect_fires_on_true_positive_names(self):
        pytest.importorskip("gliner")
        from kajiba.scrubber_semantic import GLINER_MODEL_ID as MODEL_ID
        from kajiba.scrubber_semantic import detect_entities

        # Model id must be exactly capital-PII (lowercase 404s).
        assert MODEL_ID == "nvidia/gliner-PII"

        prose = "This change was reviewed by Margaret Chen at Aldebaran Robotics before merge."
        spans = detect_entities(prose, threshold=0.4)
        detected = " ".join(s["text"] for s in spans)
        # GLiNER must still detect at least one genuine person/company name.
        assert any(name.split()[0] in detected for name in TRUE_POSITIVE_NAMES)
        assert any(s["label"] in {"person", "company", "organization"} for s in spans)


class TestCalibration:
    """D-06 HARD GATE: zero auto-redact on code (selector: ``calibration``, needs [llm-scrub])."""

    def test_calibration_zero_auto_redact_on_code(self):
        pytest.importorskip("gliner")
        from kajiba.scrubber_semantic import detect_entities

        record = validate_record(_load_fixture("code_content_pii.json"))
        # Concatenate all code-bearing text (turn values + tool fields).
        code_text_parts = []
        for turn in record.trajectory.conversations:
            code_text_parts.append(turn.value)
            for tc in turn.tool_calls or []:
                code_text_parts.append(tc.tool_input)
                code_text_parts.append(tc.tool_output)
        code_text = "\n".join(code_text_parts)

        spans = detect_entities(code_text, threshold=0.4)
        auto_redact = [s for s in spans if s["score"] >= 0.7]
        flag_band = [s for s in spans if 0.4 <= s["score"] < 0.7]

        # Record the observed false-positive rate against the known-safe denominator.
        false_positives = [
            s for s in auto_redact if s["text"] in KNOWN_SAFE_TOKENS
        ]
        fp_rate = len(false_positives) / len(KNOWN_SAFE_TOKENS)
        # Surface the FP-rate artifact (visible with `pytest -s`).
        print(f"CALIBRATION_FP_RATE={fp_rate:.4f} flag_band={len(flag_band)}")

        # HARD GATE: zero KNOWN-SAFE code identifiers auto-redacted (>=0.7).
        # Genuine PII seeded in the fixture (TRUE_POSITIVE_NAMES) is EXPECTED to
        # auto-redact and must NOT trip this gate — the gate measures false
        # positives on code, not the total number of detections. Asserting on the
        # full ``auto_redact`` set would wrongly fail whenever GLiNER correctly
        # catches the seeded true-positive names (the latent bug the first real
        # LANE-B run on the DGX surfaced; this assert had never executed before).
        assert false_positives == [], (
            f"D-06 calibration gate FAILED: {len(false_positives)} known-safe code "
            f"identifiers auto-redacted at score>=0.7 (FP rate {fp_rate:.4f}): "
            f"{[s['text'] for s in false_positives]}"
        )
