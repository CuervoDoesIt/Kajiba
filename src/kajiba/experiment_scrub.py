"""Experiment-aware PII scrub (EEVAL-02) — the divergent-tail share-boundary transform.

This module is the deliberate inverse of the community pipeline's hardware
anonymization. It redacts only the five caller-supplied free-text surfaces of an
``ExperimentRecord`` while PRESERVING model identity and the full hardware profile
EXACTLY — because those fields are what make an experiment analytically useful.

Design stance (D-05/D-06/D-07/D-09/D-10):
    - REUSES the shared ``scrub_text``/``SCRUB_PATTERNS`` engine verbatim; it never
      forks the regex layer (shared core).
    - Applies that engine to a FIELD ALLOWLIST, not a pattern denylist: only
      ``experiment.task_category``, ``experiment.task_description``,
      ``outcome.local_model_output``, ``outcome.reviewer_critique`` (Optional),
      and each element of ``outcome.lessons_learned`` are scrubbed.
    - PRESERVES ``experiment.experiment_id`` byte-identical: it is load-bearing
      identity (drives the ``exp_<id>.json`` store filename, ``compute_record_id``,
      and the dedup ``submission_hash``), so scrubbing it would break store-load
      and dedup. It is exempt for the same reason as model/hardware identity.
    - DELIBERATELY BYPASSES the community privacy layer — it must NEVER import or
      call any hardware-anonymization / GPU-generalization / VRAM-tiering /
      consent-application helper. Model/hardware identity survives byte-identical.

The actual share-boundary write fires in Phase 15 (D-08 — store raw, scrub at
export). This module provides the scrub primitive only: it returns a scrubbed
copy and never persists or overwrites the raw store.
"""

import logging

from kajiba.scrubber import scrub_text
from kajiba.schema import ExperimentRecord, ScrubLog

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scrub_experiment(record: ExperimentRecord) -> tuple[ExperimentRecord, ScrubLog]:
    """Scrub the free-text surfaces of an experiment, preserving model/hardware.

    Routes only the five caller-supplied free-text fields through the shared
    ``scrub_text`` engine. Model identity (``local_model``, ``reviewer_model``,
    ``model_hash``), the full ``HardwareProfile``, ``experiment_id`` (load-bearing
    identity — see module docstring), and all non-text outcome fields
    (``eval_score``, ``drift_flag``, ``recommended_action``) are left
    byte-identical. Operates on a deep copy so the original record is never
    mutated.

    Args:
        record: The ExperimentRecord to scrub.

    Returns:
        Tuple of (scrubbed ExperimentRecord, ScrubLog with redaction counts).
    """
    # Deep copy via serialization — never mutate the caller's record (D-08).
    data = record.model_dump(mode="json", by_alias=True)

    counts: dict[str, int] = {}
    flagged = 0

    def _apply(text: str) -> str:
        """Scrub one string, folding its stats into the shared accumulators."""
        result = scrub_text(text)
        for cat, cnt in result.stats.items():
            counts[cat] = counts.get(cat, 0) + cnt
        nonlocal flagged
        flagged += len(result.flagged)
        return result.scrubbed_text

    # --- ALLOWLIST ONLY (D-07) — five free-text surfaces ---
    # experiment.task_category, experiment.task_description,
    # outcome.local_model_output, outcome.reviewer_critique (Optional), and each
    # element of outcome.lessons_learned. experiment.experiment_id is preserved
    # byte-identical (load-bearing identity — store filename, record_id hash,
    # dedup submission_hash), exactly like model/hardware identity.
    experiment = data["experiment"]
    outcome = data["outcome"]

    experiment["task_category"] = _apply(experiment["task_category"])
    experiment["task_description"] = _apply(experiment["task_description"])
    outcome["local_model_output"] = _apply(outcome["local_model_output"])

    # reviewer_critique is Optional (Pitfall 2) — only scrub when present.
    if outcome.get("reviewer_critique"):
        outcome["reviewer_critique"] = _apply(outcome["reviewer_critique"])

    # lessons_learned stays a list (per-element scrub, never stringified — Pitfall 1).
    outcome["lessons_learned"] = [
        _apply(lesson) for lesson in outcome.get("lessons_learned", [])
    ]

    # model / hardware / model_hash / experiment_id / scalar outcome fields are
    # intentionally NOT touched here (D-05/D-06). experiment_id in particular is
    # load-bearing identity and must stay byte-stable. No privacy.* call is ever made.

    # Build the redaction-accounting log — mirror scrub_record's category fold
    # (api_keys + hex_tokens collapse into api_keys_redacted; no regex source
    # for potential_names so it stays 0 — Open Q2 RESOLVED).
    scrub_log = ScrubLog(
        file_paths_redacted=counts.get("file_paths", 0),
        api_keys_redacted=counts.get("api_keys", 0) + counts.get("hex_tokens", 0),
        emails_redacted=counts.get("emails", 0),
        network_redacted=counts.get("network", 0),
        phone_redacted=counts.get("phone", 0),
        crypto_redacted=counts.get("crypto", 0),
        connection_strings_redacted=counts.get("connection_strings", 0),
        items_flagged=flagged,
    )

    logger.info("Scrubbed experiment record: %s redaction categories", len(counts))

    scrubbed_record = ExperimentRecord.model_validate(data)
    return scrubbed_record, scrub_log
