"""DEPRECATED — superseded by :mod:`kajiba.scrubber_semantic`.

The original LLM-prompting stub (Layer C via a generative ``model_fn`` returning
string-confidence buckets) has been retired. The semantic PII layer is now a real
GLiNER detector in :mod:`kajiba.scrubber_semantic`, which buckets float-scored
spans into the locked D-05 confidence bands and applies D-07 asymmetric coverage.

This module is kept only so legacy import paths do not hard-break. It re-exports
the new entry points and raises a clear deprecation message if the old
string-confidence ``scrub_semantic(text, model_fn)`` API is called.
"""

import logging

# Re-export the new semantic-scrub surface so legacy imports keep resolving.
from kajiba.scrubber_semantic import (  # noqa: F401
    GLINER_MODEL_ID,
    SemanticScrubUnavailable,
    classify_band,
    detect_entities,
    scrub_record_semantic,
)

logger = logging.getLogger(__name__)


def scrub_semantic(*args, **kwargs):
    """Removed: the LLM-prompting semantic scrubber no longer exists.

    Raises:
        SemanticScrubUnavailable: Always. Use
            :func:`kajiba.scrubber_semantic.scrub_record_semantic` (GLiNER-based,
            float-scored confidence bands) instead of the old
            ``scrub_semantic(text, model_fn)`` string-confidence interface.
    """
    raise SemanticScrubUnavailable(
        "kajiba.scrubber_llm.scrub_semantic has been retired. The semantic PII "
        "layer is now GLiNER-based — use "
        "kajiba.scrubber_semantic.scrub_record_semantic instead."
    )
