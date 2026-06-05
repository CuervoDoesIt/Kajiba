"""GLiNER-based semantic PII scrubber (Layer C).

Implements the semantic privacy layer from the Kajiba spec: a generalist NER
(GLiNER, ``nvidia/gliner-PII``) detects context-dependent identifying names —
persons, companies, organizations, projects, and locations — that the regex
layer (``kajiba.scrubber``, Layer B) cannot catch.

This module composes AFTER the regex scrub (D-11) on a deep copy of the record,
reusing the existing :class:`kajiba.scrubber.FlaggedItem` container (D-08) so
that flags flow into the existing preview channel (wired in 07-05).

Locked decisions encoded here:

* **D-04** — controlled label set: ``person``, ``company``, ``organization``,
  ``project``, ``location``.
* **D-05** — confidence bands: ``score >= 0.7`` auto-redact, ``0.4 <= score < 0.7``
  flag for human review, ``score < 0.4`` ignore.
* **D-06** — calibration hard gate: zero auto-redacts on known-safe code identifiers.
* **D-07** — asymmetric coverage: ``ConversationTurn.value`` may auto-redact AND
  flag; ``tool_input`` / ``tool_output`` produce FLAGS ONLY and never mutate text.
* **D-09** — within-run model singleton (GLiNER loads once per CLI invocation).
* **PRIV-04 / D-10** — soft import: importing this module never requires the
  ``[llm-scrub]`` extra; the model path raises :class:`SemanticScrubUnavailable`
  (never a raw ``ModuleNotFoundError``) when gliner/torch are absent.

GLiNER and torch are heavy ML dependencies behind the ``[llm-scrub]`` extra and
are soft-imported INSIDE functions only — the core package stays import-clean and
offline.
"""

import logging
from typing import Optional

from kajiba.schema import KajibaRecord

# FlaggedItem is reused from the regex scrubber (D-08) — do NOT redefine it here.
from kajiba.scrubber import FlaggedItem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Capital ``PII`` (Correction 1 / Pitfall 3). The lowercase repo id 404s on
# Hugging Face, so this literal must never be lowercased.
GLINER_MODEL_ID = "nvidia/gliner-PII"

# D-04 controlled label set passed to GLiNER's ``predict_entities``.
LABELS = ["person", "company", "organization", "project", "location"]

# D-05 confidence bands.
REDACT_THRESHOLD = 0.7
FLAG_THRESHOLD = 0.4

# Per-label redaction placeholders. Person names get a distinct tag; every other
# label folds into the generic name tag. The literals match the ``scrubber.py``
# ``[REDACTED_*]`` convention so the existing ``\[REDACTED_\w+\]`` highlight regex
# catches them in the preview panel.
PLACEHOLDER_PERSON = "[REDACTED_PERSON]"
PLACEHOLDER_NAME = "[REDACTED_NAME]"

# Within-run model singleton (D-09). ``None`` until the first detection call.
_MODEL = None


# ---------------------------------------------------------------------------
# Soft-dependency error
# ---------------------------------------------------------------------------


class SemanticScrubUnavailable(Exception):
    """Raised when the semantic scrub model path is invoked without ``[llm-scrub]``.

    The core package imports cleanly without gliner/torch; only the actual model
    load/inference path requires the extra. Callers (e.g. ``kajiba preview``,
    wired in 07-05) catch this to degrade gracefully.
    """


# ---------------------------------------------------------------------------
# Band classification (pure logic, no model)
# ---------------------------------------------------------------------------


def classify_band(score: float) -> str:
    """Bucket a confidence score into a D-05 band.

    Args:
        score: A GLiNER span confidence in ``[0.0, 1.0]``.

    Returns:
        ``"redact"`` for ``score >= 0.7``, ``"flag"`` for ``0.4 <= score < 0.7``,
        ``"ignore"`` for ``score < 0.4``.
    """
    if score >= REDACT_THRESHOLD:
        return "redact"
    if score >= FLAG_THRESHOLD:
        return "flag"
    return "ignore"


def partition_spans(spans: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split spans into ``(redactions, flags)`` by the D-05 float bands.

    Spans in the ignore band (``score < 0.4``) are dropped from both lists. This
    is a pure helper — it does not load or call the model.

    Args:
        spans: GLiNER span dicts, each ``{start, end, text, label, score}``.

    Returns:
        A ``(redactions, flags)`` tuple of span-dict lists.
    """
    redactions: list[dict] = []
    flags: list[dict] = []
    for span in spans:
        band = classify_band(span["score"])
        if band == "redact":
            redactions.append(span)
        elif band == "flag":
            flags.append(span)
    return redactions, flags


# ---------------------------------------------------------------------------
# Model access (soft-imported singleton)
# ---------------------------------------------------------------------------


def _get_model():
    """Return the within-run GLiNER singleton, loading it on first call.

    gliner and torch are soft-imported inside this function (mirroring the
    ``psutil`` block in ``collector.py``) so the core package never requires the
    ``[llm-scrub]`` extra at import time. The capital-PII model is loaded onto
    CUDA when available, otherwise CPU, and cached in the module-level ``_MODEL``
    for the remainder of the process (D-09).

    Returns:
        The loaded ``GLiNER`` model instance.

    Raises:
        SemanticScrubUnavailable: If gliner/torch are not installed.
    """
    global _MODEL
    if _MODEL is not None:
        return _MODEL

    try:
        from gliner import GLiNER
        import torch
    except ImportError as exc:
        raise SemanticScrubUnavailable(
            "The semantic PII scrubber requires the [llm-scrub] extra "
            "(gliner, torch). Install it with: pip install kajiba[llm-scrub]"
        ) from exc

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Loading GLiNER model %s on %s", GLINER_MODEL_ID, device)
    _MODEL = GLiNER.from_pretrained(GLINER_MODEL_ID).to(device)
    return _MODEL


def detect_entities(text: str, threshold: float = FLAG_THRESHOLD) -> list[dict]:
    """Detect semantic PII spans in ``text`` with a single GLiNER inference pass.

    Runs ONE inference at the flag floor (``threshold=0.4`` by default, Pattern 5
    threshold strategy) so both the redact and flag bands are covered by one call.
    Returns an empty list for empty input without touching the model.

    Args:
        text: The text to scan for semantic PII.
        threshold: The minimum confidence GLiNER returns spans for. Defaults to
            the D-05 flag floor so the caller buckets via :func:`classify_band`.

    Returns:
        A list of span dicts, each ``{start, end, text, label, score}``.

    Raises:
        SemanticScrubUnavailable: If the ``[llm-scrub]`` extra is absent.
    """
    if not text:
        return []
    model = _get_model()
    return model.predict_entities(text, LABELS, threshold=threshold)


def _placeholder_for_label(label: str) -> str:
    """Return the ``[REDACTED_*]`` placeholder for a GLiNER label.

    Person spans get ``[REDACTED_PERSON]``; every other label folds into the
    generic ``[REDACTED_NAME]`` tag.
    """
    return PLACEHOLDER_PERSON if label == "person" else PLACEHOLDER_NAME
