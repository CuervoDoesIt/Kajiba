"""Regex-based PII scrubber for Kajiba records.

Implements Layer B from the Kajiba spec: pattern matching for known PII
formats with type-tagged placeholder replacement.
"""

import copy
import logging
import re
from dataclasses import dataclass, field

from kajiba.schema import KajibaRecord, ScrubLog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Placeholder tags
# ---------------------------------------------------------------------------

PLACEHOLDER_PATH = "[REDACTED_PATH]"
PLACEHOLDER_KEY = "[REDACTED_KEY]"
PLACEHOLDER_EMAIL = "[REDACTED_EMAIL]"
PLACEHOLDER_IP = "[REDACTED_IP]"
PLACEHOLDER_PHONE = "[REDACTED_PHONE]"
PLACEHOLDER_CERT = "[REDACTED_CERT]"
PLACEHOLDER_CONNSTR = "[REDACTED_CONNSTR]"
PLACEHOLDER_HOSTNAME = "[REDACTED_HOSTNAME]"
PLACEHOLDER_HEX_TOKEN = "[REDACTED_HEX_TOKEN]"

# ---------------------------------------------------------------------------
# Context-aware IP detection (PRIV-06)
# ---------------------------------------------------------------------------

IP_CANDIDATE = re.compile(
    r"(?<![.\d])"
    r"((?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?))"
    r"(?![.\d])"
)

VERSION_PREFIX = re.compile(
    r"(?:python|node|ruby|java|go|perl|php|pip|npm|cuda|version|ver|v\.?|release)\s*$",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Org domain flagging (PRIV-05)
# ---------------------------------------------------------------------------

ORG_DOMAIN_PATTERN = re.compile(
    r"\b([a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)\.(?:company|org|io)\b"
)

SAFE_DOMAINS = frozenset({
    "github.io", "python.org", "nodejs.org", "apache.org",
    "mozilla.org", "npmjs.org", "readthedocs.org",
    "crates.io", "rubygems.org", "pypi.org", "docker.io",
})

# ---------------------------------------------------------------------------
# Pattern categories
# ---------------------------------------------------------------------------

SCRUB_PATTERNS: dict[str, list[tuple[re.Pattern[str], str]]] = {
    "file_paths": [
        (re.compile(r"/home/[a-zA-Z0-9_.-]+/\S*"), PLACEHOLDER_PATH),
        (re.compile(r"/Users/[a-zA-Z0-9_.-]+/\S*"), PLACEHOLDER_PATH),
        (re.compile(r"C:\\Users\\[a-zA-Z0-9_.-]+\\\S*"), PLACEHOLDER_PATH),
        (re.compile(r"~/\S+"), PLACEHOLDER_PATH),
    ],
    "api_keys": [
        (re.compile(r"sk-[a-zA-Z0-9]{32,}"), PLACEHOLDER_KEY),
        (re.compile(r"ghp_[a-zA-Z0-9]{36}"), PLACEHOLDER_KEY),
        (re.compile(r"glpat-[a-zA-Z0-9\-]{20,}"), PLACEHOLDER_KEY),
        (re.compile(r"AKIA[0-9A-Z]{16}"), PLACEHOLDER_KEY),
        (re.compile(
            r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"
        ), PLACEHOLDER_KEY),
        (re.compile(r"Bearer\s+[a-zA-Z0-9._-]+"), PLACEHOLDER_KEY),
        (re.compile(r"""token['\"]?\s*[:=]\s*['\"][^'\"]+['\"]"""), PLACEHOLDER_KEY),
    ],
    "network": [
        # IP addresses handled by _scrub_ips_context_aware() below
        (re.compile(
            r"[a-zA-Z0-9-]+\.(internal|local|corp|lan)\b"
        ), PLACEHOLDER_HOSTNAME),
    ],
    "hex_tokens": [
        (re.compile(
            r"(?:key|token|secret|password|apikey|api_key|auth|credential)"
            r"['\"\s]*[:=]['\"\s]*"
            r"([a-fA-F0-9]{40,})",
            re.IGNORECASE,
        ), PLACEHOLDER_HEX_TOKEN),
    ],
    "emails": [
        (re.compile(
            r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"
        ), PLACEHOLDER_EMAIL),
    ],
    "phone": [
        (re.compile(
            r"\b\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
        ), PLACEHOLDER_PHONE),
    ],
    "crypto": [
        (re.compile(
            r"-----BEGIN [A-Z ]+-----[\s\S]*?-----END [A-Z ]+-----"
        ), PLACEHOLDER_CERT),
        (re.compile(
            r"ssh-[a-z0-9]+ AAAA[a-zA-Z0-9+/]+[=]{0,2}"
        ), PLACEHOLDER_CERT),
    ],
    "connection_strings": [
        (re.compile(
            r"(postgres|mysql|mongodb|redis)://[^\s]+"
        ), PLACEHOLDER_CONNSTR),
        (re.compile(r"Server=[^;]+;Database=[^;]+;"), PLACEHOLDER_CONNSTR),
    ],
}

# Categories map to ScrubLog field names
CATEGORY_TO_LOG_FIELD: dict[str, str] = {
    "file_paths": "file_paths_redacted",
    "api_keys": "api_keys_redacted",
    "network": "network_redacted",
    "emails": "emails_redacted",
    "phone": "phone_redacted",
    "crypto": "crypto_redacted",
    "connection_strings": "connection_strings_redacted",
    "hex_tokens": "api_keys_redacted",
}


# ---------------------------------------------------------------------------
# ScrubResult
# ---------------------------------------------------------------------------


@dataclass
class Redaction:
    """A single redaction that was applied."""

    original: str
    replacement: str
    category: str
    start: int
    end: int


@dataclass
class FlaggedItem:
    """An item flagged for user review, not auto-redacted."""

    text: str
    category: str
    reason: str
    start: int
    end: int


@dataclass
class ScrubResult:
    """Result of scrubbing a single text string."""

    scrubbed_text: str
    redactions: list[Redaction] = field(default_factory=list)
    flagged: list[FlaggedItem] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Context-aware helpers
# ---------------------------------------------------------------------------


def _scrub_ips_context_aware(text: str) -> tuple[str, list[Redaction], int]:
    """Replace IPs with placeholder, skipping version-string false positives.

    Returns:
        Tuple of (scrubbed text, list of Redaction objects, redaction count).
    """
    redactions: list[Redaction] = []
    count = 0
    result = text
    for match in reversed(list(IP_CANDIDATE.finditer(text))):
        prefix = text[max(0, match.start() - 30):match.start()].rstrip()
        if VERSION_PREFIX.search(prefix):
            continue
        redactions.append(Redaction(
            original=match.group(),
            replacement=PLACEHOLDER_IP,
            category="network",
            start=match.start(),
            end=match.end(),
        ))
        result = result[:match.start()] + PLACEHOLDER_IP + result[match.end():]
        count += 1
    return result, redactions, count


def flag_org_domains(text: str) -> list[FlaggedItem]:
    """Find org domains and return as flagged items (not auto-redacted).

    Args:
        text: The input text to scan.

    Returns:
        List of FlaggedItem for each non-safe org domain found.
    """
    flagged: list[FlaggedItem] = []
    for match in ORG_DOMAIN_PATTERN.finditer(text):
        domain = match.group(0)
        if domain.lower() not in SAFE_DOMAINS:
            flagged.append(FlaggedItem(
                text=domain,
                category="org_domain",
                reason=f"Potential organizational domain: {domain}",
                start=match.start(),
                end=match.end(),
            ))
    return flagged


# ---------------------------------------------------------------------------
# Core scrubbing functions
# ---------------------------------------------------------------------------


def scrub_text(text: str) -> ScrubResult:
    """Scrub PII from a single text string.

    Applies all regex pattern categories and replaces matches with
    typed placeholder tags.

    Args:
        text: The input text to scrub.

    Returns:
        ScrubResult with the scrubbed text, list of redactions, and
        per-category counts.
    """
    if not text:
        return ScrubResult(scrubbed_text=text)

    redactions: list[Redaction] = []
    stats: dict[str, int] = {}
    result_text = text

    for category, patterns in SCRUB_PATTERNS.items():
        category_count = 0
        for pattern, placeholder in patterns:
            matches = list(pattern.finditer(result_text))
            if matches:
                for match in reversed(matches):
                    redactions.append(Redaction(
                        original=match.group(),
                        replacement=placeholder,
                        category=category,
                        start=match.start(),
                        end=match.end(),
                    ))
                    category_count += 1
                result_text = pattern.sub(placeholder, result_text)
        if category_count > 0:
            stats[category] = stats.get(category, 0) + category_count

    # Context-aware IP scrubbing (PRIV-06)
    result_text, ip_redactions, ip_count = _scrub_ips_context_aware(result_text)
    if ip_count > 0:
        redactions.extend(ip_redactions)
        stats["network"] = stats.get("network", 0) + ip_count

    # Org domain flagging (PRIV-05) — after all redactions, scan for flagged items
    flagged_items = flag_org_domains(result_text)

    return ScrubResult(
        scrubbed_text=result_text,
        redactions=redactions,
        flagged=flagged_items,
        stats=stats,
    )


def _scrub_string_fields_in_turn(turn_data: dict) -> tuple[dict[str, int], int]:
    """Scrub string fields in a conversation turn dict, mutating in-place.

    Returns:
        Tuple of (per-category redaction counts, flagged item count).
    """
    counts: dict[str, int] = {}
    flagged_count = 0

    # Scrub the turn value
    if turn_data.get("value"):
        result = scrub_text(turn_data["value"])
        turn_data["value"] = result.scrubbed_text
        for cat, cnt in result.stats.items():
            counts[cat] = counts.get(cat, 0) + cnt
        flagged_count += len(result.flagged)

    # Scrub tool call fields
    for tc in turn_data.get("tool_calls") or []:
        for field_name in ("tool_input", "tool_output"):
            if tc.get(field_name):
                result = scrub_text(tc[field_name])
                tc[field_name] = result.scrubbed_text
                for cat, cnt in result.stats.items():
                    counts[cat] = counts.get(cat, 0) + cnt
                flagged_count += len(result.flagged)

    return counts, flagged_count


def scrub_record(record: KajibaRecord) -> tuple[KajibaRecord, ScrubLog]:
    """Deep-walk a KajibaRecord and scrub all string fields in the trajectory.

    Scrubs conversation values, tool inputs/outputs, pain point descriptions,
    and user comments. Leaves metadata fields (model, hardware, submission) intact.

    Args:
        record: The KajibaRecord to scrub.

    Returns:
        Tuple of (scrubbed KajibaRecord, ScrubLog with redaction counts).
    """
    # Work on a deep copy to avoid mutating the original
    data = record.model_dump(by_alias=True)
    total_counts: dict[str, int] = {}
    total_flagged = 0

    # Scrub trajectory conversations
    for turn in data.get("trajectory", {}).get("conversations", []):
        counts, flagged_count = _scrub_string_fields_in_turn(turn)
        for cat, cnt in counts.items():
            total_counts[cat] = total_counts.get(cat, 0) + cnt
        total_flagged += flagged_count

    # Scrub pain point descriptions
    for pp in data.get("pain_points", []) or []:
        if pp.get("description"):
            result = scrub_text(pp["description"])
            pp["description"] = result.scrubbed_text
            for cat, cnt in result.stats.items():
                total_counts[cat] = total_counts.get(cat, 0) + cnt
            total_flagged += len(result.flagged)

    # Scrub outcome user_comment
    outcome = data.get("outcome")
    if outcome and outcome.get("user_comment"):
        result = scrub_text(outcome["user_comment"])
        outcome["user_comment"] = result.scrubbed_text
        for cat, cnt in result.stats.items():
            total_counts[cat] = total_counts.get(cat, 0) + cnt
        total_flagged += len(result.flagged)

    # Build scrub log
    scrub_log = ScrubLog(
        file_paths_redacted=total_counts.get("file_paths", 0),
        api_keys_redacted=total_counts.get("api_keys", 0) + total_counts.get("hex_tokens", 0),
        emails_redacted=total_counts.get("emails", 0),
        network_redacted=total_counts.get("network", 0),
        phone_redacted=total_counts.get("phone", 0),
        crypto_redacted=total_counts.get("crypto", 0),
        connection_strings_redacted=total_counts.get("connection_strings", 0),
        items_flagged=total_flagged,
    )

    # Reconstruct the record from scrubbed data
    scrubbed_record = KajibaRecord.model_validate(data)
    return scrubbed_record, scrub_log
