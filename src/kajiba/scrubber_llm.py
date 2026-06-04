"""LLM-based semantic PII scrubber — stub for future implementation.

This module implements Layer C from the Kajiba spec: using the user's local
model to detect semantic PII that regex patterns miss, such as personal names,
company names, project names, and context-dependent identifying information.

The LLM scrubber will:
1. Send each conversation turn to the local model with a focused PII detection prompt.
2. Parse the model's response for identified PII items with confidence levels.
3. Auto-redact high-confidence items and flag medium-confidence items for user review.

This requires the [llm-scrub] extra and a running local model.
"""

import logging
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class SemanticRedaction:
    """A single semantic PII detection."""

    original_text: str
    replacement_tag: str
    confidence: str  # "high", "medium", "low"
    category: str  # "person_name", "company", "project", "location"


@dataclass
class ScrubResult:
    """Result of semantic PII scrubbing."""

    scrubbed_text: str
    redactions: list[SemanticRedaction] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)


def scrub_semantic(text: str, model_fn: Callable[[str], str]) -> ScrubResult:
    """Scrub semantic PII from text using an LLM.

    Uses the provided model function to analyze text for context-dependent
    PII that regex patterns cannot catch: personal names, company names,
    project names, and geographic locations specific enough to identify
    an individual.

    The model_fn should accept a prompt string and return the model's
    response string. It is expected to be a local model call (e.g., via
    Ollama or llama.cpp).

    Args:
        text: The input text to analyze for semantic PII.
        model_fn: A callable that sends a prompt to the local model
            and returns the response. Signature: (str) -> str.

    Returns:
        ScrubResult with scrubbed text, detected redactions, and stats.

    Raises:
        NotImplementedError: This is a stub. The LLM-based semantic
            scrubber will be implemented in a future version. Install
            the [llm-scrub] extra and check back for updates.
    """
    raise NotImplementedError(
        "The LLM-based semantic PII scrubber is not yet implemented. "
        "This feature is planned for a future release. "
        "For now, use the regex-based scrubber (kajiba.scrubber.scrub_text) "
        "which handles structured PII patterns. "
        "Install kajiba[llm-scrub] to get updates when this feature lands."
    )
