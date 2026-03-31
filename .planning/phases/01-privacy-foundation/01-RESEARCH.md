# Phase 1: Privacy Foundation - Research

**Researched:** 2026-03-30
**Domain:** PII scrubbing, consent enforcement, hardware anonymization, regex patterns
**Confidence:** HIGH

## Summary

Phase 1 closes four active privacy violations in the Kajiba pipeline: consent levels exist in the schema but are never enforced, hardware profiles contain fingerprinting-capable data, the IP regex false-positives on version strings, and two spec-mandated scrub patterns (40-char hex tokens, org domains) are missing. All six requirements (PRIV-01 through PRIV-06) are code-only changes to existing Python modules with no external dependencies.

The existing codebase is well-structured for extension. The scrubber module (`src/kajiba/scrubber.py`) uses a clean pattern-category dict that new patterns plug into. The `scrub_record()` function's deep-copy-mutate-validate pattern supports adding consent stripping and metadata anonymization as composable pipeline steps. The ScrubResult/ScrubLog data structures need a `flagged` list for the org domain feature, which Phase 2 will build on for its redaction diff display.

**Primary recommendation:** Build five discrete functions -- `apply_consent_level()`, `anonymize_hardware()`, `jitter_timestamp()`, a context-aware IP filter, and the 40-char hex + org domain patterns -- then wire them into the existing `scrub_record()` / CLI submit/export pipeline. Keep each function pure (input record, output record) for testability.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Consent stripping happens at BOTH submit time and publish time (belt and suspenders). The outbox only contains consent-safe data, and publish verifies again before pushing.
- **D-02:** `apply_consent_level(record, level)` is a pure function that strips fields based on the consent table in the spec (Section 2.2 Layer E). Called in the CLI submit/export paths and in export_record().
- **D-03:** Consent level is read from the record's `submission.consent_level` field, which is set from the user's config at capture time.
- **D-04:** GPU names are generalized to family tier: "NVIDIA GeForce RTX 4090" -> "NVIDIA RTX 40xx" (series-level, hides specific model). Map common GPU families to their series designator.
- **D-05:** RAM and VRAM are rounded to nearest power-of-2 standard tier: 4, 8, 16, 32, 64, 128 GB.
- **D-06:** OS version is stripped entirely -- only the OS family label remains (linux, macos, windows).
- **D-07:** Timestamps are jittered +/-0-30 minutes (random offset per record) to prevent session correlation.
- **D-08:** `anonymize_metadata(record)` is a function that applies all hardware anonymization. Called after PII scrubbing in the scrub pipeline.
- **D-09:** Org domains (.company, .org, .io patterns) are FLAGGED for review, not auto-redacted. Flagged items appear as warnings in `kajiba preview` so the contributor can decide to redact or keep each one before submit.
- **D-10:** The flagging mechanism is extensible -- designed as a "medium-confidence" category that future scrubber layers (e.g., LLM semantic scrubbing in v2) can also use. ScrubResult gets a new `flagged` list alongside `redactions`.
- **D-11:** If a contributor submits without addressing flagged items, they pass through as-is (flagged items are noted in the ScrubLog but not blocked).
- **D-12:** IP address regex fix and 40-char hex token pattern are Claude's discretion. Goal: minimize false positives on version strings while catching real IPs, and catch hex tokens only when context keywords are present.

### Claude's Discretion
- Consent change handling (retroactive vs forward-only for existing outbox records) -- Claude picks the best approach based on implementation complexity.
- IP regex fix approach -- context guards, octet validation, or hybrid.
- 40-char hex token pattern strictness -- context-required vs broad+exclusions.

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PRIV-01 | User's consent level choice is enforced at export time -- fields stripped based on selected level | Consent level table from spec Section 2.2 Layer E; field stripping map for all 4 levels; `apply_consent_level()` pure function pattern |
| PRIV-02 | Hardware profiles are anonymized before export -- GPU names generalized, RAM/VRAM rounded, OS version stripped | GPU family regex map (tested); power-of-2 rounding algorithm; OS label already captured as family-only in collector |
| PRIV-03 | Timestamps are jittered (+/-0-30 min) before export to prevent session correlation | Deterministic jitter via `random.Random(seed)` pattern; seeded from record content for reproducibility |
| PRIV-04 | Generic 40-character hex tokens are scrubbed when preceded by context keywords | Context-required regex pattern (tested); keyword list: key, token, secret, password, apikey, api_key, auth, credential |
| PRIV-05 | Organizational domain names (.company, .org, .io) are flagged for user review (not auto-redacted) | Org domain regex with safe-domain allowlist (tested); new `flagged` list on ScrubResult; preview warning rendering |
| PRIV-06 | IP address regex no longer false-positives on version strings | Hybrid approach: strict octet validation + context-keyword negative lookbehind (tested); handles Python, CUDA, Node, pip version strings |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | >=2.0 (2.11.1 on dev machine) | Schema models, validation | Already used for all Kajiba models |
| click | >=8.0 (8.1.8 on dev machine) | CLI framework | Already used for all CLI commands |
| rich | >=13.0 (13.9.4 on dev machine) | Terminal output, warnings | Already used for preview rendering |
| pytest | >=7.0 (9.0.2 on dev machine) | Test runner | Already configured in pyproject.toml |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| re (stdlib) | n/a | Regex patterns for IP, hex token, org domain | All new scrub patterns |
| random (stdlib) | n/a | Deterministic seeded jitter | Timestamp jitter via `random.Random(seed)` |
| copy (stdlib) | n/a | Deep copy for record mutation | Already imported in scrubber (unused, now needed) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Regex IP validation | `ipaddress` stdlib module | Could validate octets after regex match; heavier but more correct. Not needed -- hybrid regex+context filter is sufficient |
| Power-of-2 rounding | Spec's tier list (8,16,24,32,48,64,96,128) | Decision D-05 overrides spec; power-of-2 is simpler and more privacy-preserving |

**Installation:**
```bash
# No new dependencies needed -- all changes use existing stack + stdlib
pip install -e ".[dev]"
```

## Architecture Patterns

### Recommended Project Structure
```
src/kajiba/
    scrubber.py          # MODIFY: Fix IP regex, add hex token pattern, add org domain flagging
    privacy.py           # NEW: apply_consent_level(), anonymize_hardware(), jitter_timestamp()
    schema.py            # MODIFY: Add flagged_domains field to ScrubLog, add items_flagged count
    cli.py               # MODIFY: Wire consent enforcement into submit/export, show flagged warnings in preview
    collector.py         # MODIFY: Wire anonymize_metadata + consent into export_record()
tests/
    test_privacy.py      # NEW: Tests for consent, anonymization, timestamp jitter
    test_scrubber.py     # MODIFY: Add IP false-positive, hex token, org domain, flagging tests
```

### Pattern 1: Pure Function Pipeline
**What:** Each privacy operation is a pure function: `(KajibaRecord) -> KajibaRecord` or `(KajibaRecord, config) -> KajibaRecord`. Functions compose in a pipeline: scrub -> anonymize -> consent strip.
**When to use:** Every new privacy function.
**Example:**
```python
# Source: Existing pattern in scrubber.py scrub_record()
def apply_consent_level(record: KajibaRecord, level: ConsentLevelType) -> KajibaRecord:
    """Strip fields based on consent level. Returns new record, does not mutate input."""
    data = record.model_dump(mode="json", by_alias=True)
    # ... strip fields based on level ...
    return KajibaRecord.model_validate(data)
```

### Pattern 2: Context-Aware Regex with Post-Filter
**What:** For ambiguous patterns (IP addresses), use a two-phase approach: broad regex match, then context-based filter function.
**When to use:** IP address detection, any pattern with high false-positive risk.
**Example:**
```python
# Match candidate IPs with strict octet validation
IP_CANDIDATE = re.compile(
    r"(?<![.\d])"
    r"(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)"
    r"(?![.\d])"
)

# Filter out version-string false positives
VERSION_PREFIX = re.compile(
    r"(?:python|node|ruby|java|go|perl|php|pip|npm|cuda|version|ver|v\.?|release)\s*$",
    re.IGNORECASE,
)
```

### Pattern 3: Flagging vs Auto-Redaction
**What:** Some detections should warn (flag) rather than auto-redact. ScrubResult carries both `redactions` (auto-applied) and `flagged` (shown to user).
**When to use:** Org domains (PRIV-05), and in future, medium-confidence LLM detections.
**Example:**
```python
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
    scrubbed_text: str
    redactions: list[Redaction] = field(default_factory=list)
    flagged: list[FlaggedItem] = field(default_factory=list)  # NEW
    stats: dict[str, int] = field(default_factory=dict)
```

### Pattern 4: GPU Family Mapping
**What:** Map specific GPU names to series-level designators using ordered regex patterns.
**When to use:** Hardware anonymization (PRIV-02).
**Example:**
```python
GPU_FAMILY_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"NVIDIA\s+(?:GeForce\s+)?RTX\s+40\d{2}(?:\s+(?:Ti|SUPER))?", re.IGNORECASE), "NVIDIA RTX 40xx"),
    (re.compile(r"NVIDIA\s+(?:GeForce\s+)?RTX\s+30\d{2}(?:\s+(?:Ti|SUPER))?", re.IGNORECASE), "NVIDIA RTX 30xx"),
    # ... more patterns
]

def generalize_gpu_name(name: str) -> str:
    for pattern, family in GPU_FAMILY_MAP:
        if pattern.match(name):
            return family
    return "Other GPU"
```

### Anti-Patterns to Avoid
- **Mutating the input record:** Always work on `model_dump()` deep copy, return a new validated record via `model_validate()`. This is the established pattern in `scrub_record()`.
- **Monolithic privacy function:** Don't put consent, anonymization, and scrubbing in one giant function. Keep them as separate composable pure functions.
- **Hardcoding consent field lists:** Use the spec table as the source of truth. Define the field stripping rules as data (dict), not code (if/elif chains).
- **Non-deterministic jitter:** Timestamp jitter must be seeded from record content so the same record always gets the same jitter. Use `random.Random(seed)`, not `random.random()`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| IP octet validation | Custom octet parser | Regex with `25[0-5]\|2[0-4]\d\|[01]?\d\d?` groups | Standard regex pattern, handles all edge cases |
| Pydantic deep copy + validate | Manual dict walking | `model_dump(mode="json", by_alias=True)` + `model_validate()` | Established pattern in codebase, handles aliases correctly |
| Random number seeding | Custom hash-based RNG | `random.Random(seed_string)` | Standard library, deterministic, well-tested |
| Rich warning display | Manual ANSI color codes | `rich.console.Console` + `rich.text.Text` | Already used throughout CLI |

**Key insight:** The entire privacy pipeline builds on existing patterns. The scrubber's category-pattern-placeholder system, the model_dump/validate roundtrip, and the Rich CLI rendering are all established. New code follows these patterns, doesn't invent new ones.

## Common Pitfalls

### Pitfall 1: by_alias=True Required for Serialization Roundtrip
**What goes wrong:** `ConversationTurn.from_` uses `Field(alias="from")`. Without `by_alias=True` in `model_dump()`, the serialized dict has key `from_` instead of `from`, and `model_validate()` fails or creates a malformed record.
**Why it happens:** Python keyword `from` requires the alias pattern. Easy to forget `by_alias=True`.
**How to avoid:** Always use `record.model_dump(mode="json", by_alias=True)` for any roundtrip. The existing `scrub_record()` already does this correctly at line 209.
**Warning signs:** `KeyError: 'from'` or `ValidationError` during `model_validate()`.

### Pitfall 2: Consent Stripping Must Remove Fields Entirely (Not Set to None)
**What goes wrong:** Setting `hardware = None` still includes `"hardware": null` in the JSON output. For `anonymous` consent, hardware should be absent from the exported file entirely.
**Why it happens:** Pydantic's `model_dump()` includes `None` fields by default.
**How to avoid:** Use `model_dump(exclude_none=True)` or `del data["hardware"]` on the dict before validation. For consent stripping, operate on the dict and `del` the keys.
**Warning signs:** Exported JSON has `"hardware": null` when it should be absent.

### Pitfall 3: Regex Pattern Ordering Causes Cascade Corruption
**What goes wrong:** A placeholder from an earlier pattern matches a later pattern. For example, `[REDACTED_IP]` contains dots that could match subsequent patterns.
**Why it happens:** Patterns are applied sequentially. Placeholders become part of the text for subsequent patterns.
**How to avoid:** Test new patterns against ALL existing placeholder strings. The hex token pattern should not match `[REDACTED_...]` tags (it won't, since brackets aren't hex). The org domain pattern should not match placeholder strings (verified: brackets prevent this).
**Warning signs:** Double-redacted output like `[REDACTED_[REDACTED_IP]]`.

### Pitfall 4: IP Regex Change Breaks Existing Tests
**What goes wrong:** The existing `test_ipv4_address` test expects `192.168.1.100` to be redacted. If the new regex is too restrictive, it might fail on valid IPs.
**Why it happens:** The new context-aware filter could accidentally exclude valid IPs.
**How to avoid:** Run the full test suite after changing the IP pattern. Add both positive (real IPs) and negative (version strings) test cases.
**Warning signs:** `test_ipv4_address` fails after regex change.

### Pitfall 5: Consent Stripping Applied Before Scrubbing
**What goes wrong:** If consent is applied first (stripping fields), then scrubbing runs on a partial record and may miss PII in the stripped fields that were already exported elsewhere.
**Why it happens:** Incorrect pipeline ordering.
**How to avoid:** The pipeline order must be: (1) PII scrub, (2) metadata anonymization, (3) consent level stripping. Consent stripping is the last step -- it removes already-clean data.
**Warning signs:** A `trajectory_only` record still has raw GPU names in the model metadata because anonymization ran after consent stripping removed the hardware field.

### Pitfall 6: ScrubResult.flagged vs ScrubLog.items_flagged Mismatch
**What goes wrong:** The ScrubResult (internal dataclass) carries flagged items during processing, but the ScrubLog (Pydantic model in schema) is what gets persisted. If the count is not synced, the stored record misrepresents what happened.
**Why it happens:** ScrubResult is the working structure; ScrubLog is the persistence structure. Two separate classes that must agree.
**How to avoid:** After scrubbing, always set `scrub_log.items_flagged = len(scrub_result.flagged)` explicitly.
**Warning signs:** `items_flagged: 0` in stored record when org domains were detected.

## Code Examples

Verified patterns from the existing codebase:

### Consent Level Field Stripping
```python
# Source: Spec Section 2.2 Layer E consent table
CONSENT_STRIP_MAP = {
    "anonymous": {
        "remove_top_level": ["model", "hardware", "outcome", "pain_points"],
        "remove_submission": ["contributor_id", "hermes_version"],
        "strip_timing": True,
    },
    "trajectory_only": {
        "remove_top_level": ["hardware"],
        "remove_submission": ["contributor_id"],
        "keep_model_fields": ["model_name"],
        "strip_timing": True,
    },
    "metadata_only": {
        "strip_trajectory_text": True,
    },
    "full": {},
}

def apply_consent_level(record: KajibaRecord, level: ConsentLevelType) -> KajibaRecord:
    """Strip fields from record based on consent level."""
    rules = CONSENT_STRIP_MAP.get(level, {})
    if not rules:
        return record  # 'full' -- nothing to strip

    data = record.model_dump(mode="json", by_alias=True)

    for field_name in rules.get("remove_top_level", []):
        data.pop(field_name, None)

    # ... apply other rules ...

    return KajibaRecord.model_validate(data)
```

### Hardware Anonymization Pipeline
```python
# Source: Decision D-04, D-05, D-06, D-07, D-08
STANDARD_RAM_TIERS = [4, 8, 16, 32, 64, 128]

def anonymize_hardware(record: KajibaRecord) -> KajibaRecord:
    """Apply all hardware anonymization steps."""
    data = record.model_dump(mode="json", by_alias=True)
    hw = data.get("hardware")
    if not hw:
        return record

    if hw.get("gpu_name"):
        hw["gpu_name"] = generalize_gpu_name(hw["gpu_name"])
    if hw.get("gpu_vram_gb"):
        hw["gpu_vram_gb"] = round_to_tier(hw["gpu_vram_gb"])
    if hw.get("ram_gb"):
        hw["ram_gb"] = round_to_tier(hw["ram_gb"])
    # OS already captured as family label by collector; strip version if present
    hw.pop("cuda_version", None)

    return KajibaRecord.model_validate(data)
```

### Context-Aware IP Filtering (Hybrid Approach)
```python
# Source: Verified via testing against version string corpus
IP_CANDIDATE = re.compile(
    r"(?<![.\d])"
    r"((?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?))"
    r"(?![.\d])"
)

VERSION_PREFIX = re.compile(
    r"(?:python|node|ruby|java|go|perl|php|pip|npm|cuda|version|ver|v\.?|release)\s*$",
    re.IGNORECASE,
)

def scrub_ips_context_aware(text: str) -> tuple[str, int]:
    """Replace IPs with placeholder, skipping version-string false positives."""
    count = 0
    result = text
    for match in reversed(list(IP_CANDIDATE.finditer(text))):
        prefix = text[max(0, match.start() - 30):match.start()].rstrip()
        if VERSION_PREFIX.search(prefix):
            continue  # skip version string
        result = result[:match.start()] + PLACEHOLDER_IP + result[match.end():]
        count += 1
    return result, count
```

### 40-Char Hex Token Pattern
```python
# Source: Spec Section 2.2 Layer B; verified via testing
HEX_TOKEN_PATTERN = re.compile(
    r"(?:key|token|secret|password|apikey|api_key|auth|credential)"
    r"['\"\s]*[:=]['\"\s]*"
    r"([a-fA-F0-9]{40,})",
    re.IGNORECASE,
)
```

### Org Domain Flagging
```python
# Source: Spec Section 2.2 Layer B; Decision D-09, D-10
ORG_DOMAIN_PATTERN = re.compile(
    r"\b([a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)\.(?:company|org|io)\b"
)

SAFE_DOMAINS = frozenset({
    "github.io", "python.org", "nodejs.org", "apache.org",
    "mozilla.org", "npmjs.org", "readthedocs.org",
    "crates.io", "rubygems.org", "pypi.org", "docker.io",
})

def flag_org_domains(text: str) -> list[FlaggedItem]:
    """Find org domains and return as flagged items (not auto-redacted)."""
    flagged = []
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
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Simple `\b\d{1,3}\.` IP regex | Context-aware hybrid: strict octets + version-keyword filter | This phase | Eliminates false positives on Python/CUDA/Node version strings |
| No 40-char hex detection | Context-required hex pattern | This phase | Catches generic tokens (SHA-1 API keys) while preserving git commit hashes |
| Scrub-only paradigm | Scrub + flag paradigm | This phase | Org domains flagged for review; foundation for LLM medium-confidence items in v2 |
| No consent enforcement | Belt-and-suspenders at submit AND publish | This phase | Closes the most critical privacy breach in the codebase |
| Raw hardware in records | GPU family + RAM tier + OS-only | This phase | Prevents hardware fingerprinting |

**Deprecated/outdated:**
- The current IP regex `\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b` must be replaced entirely, not patched. It cannot be fixed incrementally because the core pattern lacks octet validation.
- The `import copy` in `scrubber.py` line 7 is unused and should be removed as cleanup.

## Open Questions

1. **Consent change retroactivity for existing outbox records**
   - What we know: Decision D-01 says outbox should only contain consent-safe data. If a user changes consent from `full` to `anonymous`, existing outbox records were written at `full` consent.
   - What's unclear: Should existing outbox records be retroactively re-processed? Or is consent change forward-only?
   - Recommendation: Forward-only is simplest and safest. Existing records keep their original consent level. New records use the new consent. If retroactive is desired, add a `kajiba reprocess` command in a future phase. This aligns with Claude's Discretion scope.

2. **OS version already stripped in collector?**
   - What we know: `_detect_hardware()` in `collector.py` already maps to family labels ("linux", "macos", "windows") at line 44-52. The `os` field in `HardwareProfile` stores only the label.
   - What's unclear: Does any code path inject OS version (e.g., kernel version, build number) into the record?
   - Recommendation: Verify that `_detect_hardware()` is the only source. If so, OS version stripping (D-06) is already handled. The `anonymize_hardware()` function should still explicitly verify and enforce the family-only constraint as a defense-in-depth measure.

3. **CPU name anonymization**
   - What we know: Decision D-04 covers GPU names, D-06 covers OS. CPU name (`cpu_name` field) is not mentioned in any decision.
   - What's unclear: Should `cpu_name` be generalized? "AMD Ryzen 9 7950X" is potentially fingerprinting.
   - Recommendation: For Phase 1, leave CPU name as-is (it is not mentioned in requirements PRIV-01 through PRIV-06). Flag as a consideration for a future privacy enhancement. The `anonymize_hardware()` function should have a clear extension point for adding CPU anonymization later.

4. **cuda_version field**
   - What we know: `HardwareProfile.cuda_version` stores the NVIDIA driver version string. This is not mentioned in any decision.
   - What's unclear: Should it be stripped as part of hardware anonymization?
   - Recommendation: Strip `cuda_version` in `anonymize_hardware()` -- it is a version string that adds fingerprinting surface without contributing to fine-tuning utility. The consent level `anonymous` and `trajectory_only` both strip the entire hardware profile anyway, so this only matters for `metadata_only` and `full`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `python -m pytest tests/test_scrubber.py tests/test_privacy.py -x -v` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PRIV-01 | Consent level strips correct fields for all 4 levels | unit | `python -m pytest tests/test_privacy.py::TestConsentEnforcement -x` | Wave 0 |
| PRIV-01 | Anonymous export has no hardware/model/outcome in JSON | unit | `python -m pytest tests/test_privacy.py::TestConsentEnforcement::test_anonymous_strips_all_metadata -x` | Wave 0 |
| PRIV-02 | GPU name generalized to family | unit | `python -m pytest tests/test_privacy.py::TestHardwareAnonymization::test_gpu_generalization -x` | Wave 0 |
| PRIV-02 | RAM/VRAM rounded to power-of-2 tier | unit | `python -m pytest tests/test_privacy.py::TestHardwareAnonymization::test_ram_rounding -x` | Wave 0 |
| PRIV-02 | OS version stripped to family label | unit | `python -m pytest tests/test_privacy.py::TestHardwareAnonymization::test_os_family_only -x` | Wave 0 |
| PRIV-03 | Timestamps jittered within +/-30 min range | unit | `python -m pytest tests/test_privacy.py::TestTimestampJitter -x` | Wave 0 |
| PRIV-03 | Jitter is deterministic (same record, same jitter) | unit | `python -m pytest tests/test_privacy.py::TestTimestampJitter::test_jitter_deterministic -x` | Wave 0 |
| PRIV-04 | 40-char hex with context keyword is scrubbed | unit | `python -m pytest tests/test_scrubber.py::TestHexTokenScrubbing -x` | Wave 0 |
| PRIV-04 | 40-char hex without context keyword is preserved | unit | `python -m pytest tests/test_scrubber.py::TestHexTokenScrubbing::test_git_commit_preserved -x` | Wave 0 |
| PRIV-05 | Org domain flagged (not redacted) in ScrubResult | unit | `python -m pytest tests/test_scrubber.py::TestOrgDomainFlagging -x` | Wave 0 |
| PRIV-05 | Safe domains (github.io, python.org) not flagged | unit | `python -m pytest tests/test_scrubber.py::TestOrgDomainFlagging::test_safe_domains_not_flagged -x` | Wave 0 |
| PRIV-05 | Preview shows flagged domain warnings | unit | `python -m pytest tests/test_cli.py::TestPreviewFlaggedWarnings -x` | Wave 0 |
| PRIV-06 | Version strings not false-positived as IPs | unit | `python -m pytest tests/test_scrubber.py::TestIPFalsePositiveFix -x` | Wave 0 |
| PRIV-06 | Real IP addresses still detected | unit | `python -m pytest tests/test_scrubber.py::TestIPFalsePositiveFix::test_real_ips_still_detected -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_scrubber.py tests/test_privacy.py -x -v`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_privacy.py` -- NEW file covering PRIV-01, PRIV-02, PRIV-03 (consent, anonymization, jitter)
- [ ] `tests/test_scrubber.py` additions -- IP false positive tests, hex token tests, org domain flagging tests (PRIV-04, PRIV-05, PRIV-06)
- [ ] `tests/test_cli.py` additions -- flagged warning display in preview, consent enforcement in submit/export

## Project Constraints (from CLAUDE.md)

- **Tech stack:** Python 3.11+, Pydantic v2, Click, Rich -- no new frameworks
- **Privacy:** Maximum scrubbing by default -- err on the side of over-redacting
- **Local-first:** All processing happens on contributor's machine before data leaves
- **No external services:** Core pipeline must work without API keys or network access
- **Naming:** snake_case for functions/modules, PascalCase for classes, UPPER_SNAKE_CASE for constants
- **Logging:** Use `logging.getLogger(__name__)`, never `print()`, use `%s` formatting in logger calls
- **Type annotations:** Full type annotations on all public functions, use `Optional[X]` not `X | None`
- **Docstrings:** Google-style with Args/Returns/Raises sections
- **Error handling:** Collector wraps all methods in try/except; CLI shows user-friendly messages
- **Serialization:** Always use `model_dump(by_alias=True)` for Pydantic roundtrips
- **Module design:** Each module has single clear responsibility with module-level docstring

## Sources

### Primary (HIGH confidence)
- `docs/kajiba-project-spec.md` Section 2.2 -- PII scrubbing layers (B, C, D, E), consent level table. Authoritative spec for all privacy behavior.
- `src/kajiba/scrubber.py` -- Current regex scrubber implementation. Extension point for new patterns.
- `src/kajiba/schema.py` -- Current ScrubLog, SubmissionMetadata, KajibaRecord models. Extension point for flagged items.
- `src/kajiba/collector.py` -- Hardware detection and export_record() pipeline. Integration point for anonymization.
- `src/kajiba/cli.py` -- Submit/export commands. Integration point for consent enforcement.
- `.planning/codebase/CONCERNS.md` -- Full gap analysis with spec vs implementation table.

### Secondary (MEDIUM confidence)
- `.planning/phases/01-privacy-foundation/01-CONTEXT.md` -- User decisions D-01 through D-12. Authoritative for implementation approach.
- Direct testing of regex patterns against representative inputs (IP, hex tokens, org domains) -- verified behavior matches expectations.

### Tertiary (LOW confidence)
- Web search for IP regex best practices -- general guidance, verified through direct testing.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all changes extend existing modules
- Architecture: HIGH -- all patterns verified against existing codebase and tested via Python
- Pitfalls: HIGH -- identified through code reading and direct testing of edge cases

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable -- all changes are to internal code, no external API dependencies)
