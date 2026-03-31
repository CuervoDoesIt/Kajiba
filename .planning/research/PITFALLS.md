# Pitfalls Research

**Domain:** Community AI Training Data Pipeline
**Researched:** 2026-03-30
**Confidence:** HIGH (multiple independent sources; findings corroborated by codebase evidence in CONCERNS.md)

---

## Critical Pitfalls

### CP-1: Regex Scrubbing Creates a False Sense of Complete PII Protection

**What goes wrong:**
A regex scrubber passes all tests, ships, and contributors begin submitting real session data. The pipeline scrubs paths, API keys, emails, and IPs. But a session like "Tell John at Acme Corp to deploy the Whisperforge project on the staging box" passes through completely untouched. Real names, employer names, and project names — the most identifying information in a coding session — are invisible to regex. Researchers found that regex-only approaches achieve roughly 65% recall on PII, meaning up to 35% of sensitive content escapes. Community trust, once broken by a PII leak incident, is extremely difficult to rebuild.

**Why it happens:**
Regex matches form, not meaning. It cannot distinguish a random alphanumeric string from a colleague's name or your company's internal project name. Teams ship the regex layer because it works well on structured PII (emails, IPs, API keys) and mistake "tests pass" for "privacy is solved."

The current codebase (`scrubber_llm.py`) has this stub: `raise NotImplementedError`. The spec calls for an LLM-based semantic layer. This gap is the single largest privacy risk in Kajiba.

**How to avoid:**
Implement the two-pass pipeline as specced: regex first (fast, deterministic), LLM semantic pass second (catches names, orgs, projects). The LLM pass must run locally — no API calls — using Ollama or llama.cpp against the contributor's local model. Auto-redact high-confidence matches, flag medium-confidence for contributor review in the preview step. Never publish a record without both passes completing.

**Warning signs:**
- Sessions containing first names pass preview without any redactions
- Contributor usernames or company names appear in exported JSONL
- Test suite only covers structured PII (emails, IPs, keys) with no semantic PII tests
- The `[llm-scrub]` optional dependency group in `pyproject.toml` has no packages listed

**Phase to address:** First milestone that touches the scrubber. This must ship before any real contributor data is accepted. Do not accept external contributions with the semantic scrubber still a stub.

---

### CP-2: Consent Level Declared But Never Enforced — Silent Privacy Breach

**What goes wrong:**
A contributor configures `consent_level: anonymous`, reasonably expecting that their conversation text will not leave their machine. The pipeline accepts the setting, stores it in the schema, and then exports every field anyway — because `export_record()` and the `submit` command ignore the field entirely. The contributor believes they are protected. They are not.

This is not a hypothetical future risk. The CONCERNS.md confirms it: "Users who set `consent_level: anonymous` will unknowingly have all their data exported, violating their privacy preference."

**Why it happens:**
The schema field was added to represent intent. The enforcement logic — stripping fields based on consent level at export time — was deferred and never revisited. This is the classic "schema as documentation" antipattern: the field name implies behavior that no code implements.

**How to avoid:**
Implement `apply_consent_level(record, level)` that strips fields according to the consent matrix in the spec (Section 2.2 Layer E) before any data is written to disk or transmitted. Call it as the last step in `export_record()` and in the `submit` command. Add tests that assert specific fields are absent in the output for each consent level. Make the function a hard gate, not an optional enhancement.

**Warning signs:**
- `consent_level` field exists in schema but no function in the codebase references it at export time
- `submit` command produces identical output regardless of what consent level is configured
- No test asserts that `trajectory` text is absent from an `anonymous`-level export

**Phase to address:** Same milestone as CP-1. Consent enforcement and semantic scrubbing are both privacy gates. Neither should ship without the other.

---

### CP-3: Metadata Fingerprinting — Hardware Profiles Uniquely Identify Contributors

**What goes wrong:**
A contributor with an NVIDIA A100 80GB SXM in a home lab submits a session. The hardware profile records "NVIDIA A100 80GB SXM", 80 GB VRAM, 128 GB RAM, precise submission timestamp. This combination of rare hardware plus timestamp is likely unique worldwide. Even without any PII in the conversation text, the contributor is identifiable from the metadata alone.

Research on side-channel and inference attacks confirms that hardware profiles combined with timing signals create statistically distinct fingerprints. A 2025 USENIX paper demonstrated hardware cache side-channels enabling user identification on LLM inference systems.

**Why it happens:**
Hardware profiles are valuable for dataset consumers (they need to know what hardware produced the data). The value is real. But the raw hardware data — exact GPU model, precise RAM, exact timestamps — is more granular than necessary and creates unique identifiers. The spec's Layer D anonymization (GPU generalization, timestamp jitter, RAM rounding) was designed to solve this but was never implemented.

**How to avoid:**
Implement metadata anonymization as a required pass in the pipeline, not an optional one:
- Round VRAM and RAM to standard tiers (16, 24, 32, 48, 64, 80 GB for VRAM; 16, 32, 64, 128, 256 GB for RAM)
- Apply timestamp jitter of ±0-30 minutes (configurable)
- Generalize rare GPU names to category strings ("NVIDIA A-series datacenter GPU" for A100-class hardware)
- Strip OS minor version (report "Windows 11" not "10.0.26200")

Err toward more rounding, not less. Dataset consumers need hardware class, not exact hardware spec.

**Warning signs:**
- Exported records contain exact GPU model strings for datacenter-class or workstation hardware
- Timestamps in exported data are precise to the second or millisecond
- RAM/VRAM values are exact numbers rather than rounded tiers
- No `anonymize_metadata()` function exists anywhere in the codebase

**Phase to address:** Metadata anonymization milestone. Block before any community-facing release.

---

### CP-4: Dataset Poisoning via Unvalidated Community Contributions

**What goes wrong:**
An adversary submits carefully crafted session data containing a backdoor trigger: a specific phrase that, when the fine-tuned model sees it, produces attacker-controlled output. Research from Anthropic, the UK AI Security Institute, and The Alan Turing Institute demonstrated that as few as 250 malicious documents can successfully backdoor LLMs ranging from 600 million to 13 billion parameters. Backdoor injection is not a theoretical risk — it has been demonstrated in real code-adjacent fine-tuning (GitHub code repositories poisoned to affect a DeepSeek fine-tune in January 2025).

**Why it happens:**
Community pipelines optimize for contributor friction (low friction = more data). Validation focuses on format correctness and PII scrubbing, not on semantic integrity of the content. Adversaries contribute gradually, building reputation before injecting poison. Since the quality scorer evaluates coherence and tool validity — not semantic safety — poisoned records can score gold tier.

**How to avoid:**
- Require content hashing and deduplication at ingestion (content-addressable IDs are already implemented — use them to detect near-duplicate variants of the same suspicious content)
- Implement submission rate limiting per contributor identity (even anonymous contributors should be rate-limited by session fingerprint)
- Add a "suspicious pattern" flag pass before accepting records — detect repetition of rare trigger-like phrases across multiple submissions from the same source
- For the GitHub repo destination: use pull-request-based contribution (do not accept direct pushes) so maintainers see all submissions before they enter the dataset
- Document clearly in contributor guides that records are reviewed before merging

**Warning signs:**
- Same unusual phrase appears in unrelated sessions from different contributors
- A contributor submits an unusually high volume of gold-tier records in a short window
- Quality scores are consistently perfect (a sign of synthetic, not real, data)
- Direct push access to the dataset repository is enabled

**Phase to address:** GitHub repo design phase. The PR-based submission model is the structural defense. Add semantic content checks in the same phase as quality scoring improvements.

---

### CP-5: IP Regex False Positives Corrupt Technical Content

**What goes wrong:**
A developer submits a Python debugging session. The tool output includes `Python 3.11.0.0`, `CUDA 12.2.1.0`, and dependency versions like `pydantic 2.6.4`. The IP regex `\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b` matches all of these. The scrubber replaces them with `[REDACTED_IP]`. The exported record now contains corrupted, nonsensical content that cannot be used for fine-tuning (the model learns that Python versions are IP addresses).

The CONCERNS.md confirms this is an existing, unmitigated bug with no current tests for false positives.

**Why it happens:**
The pattern is valid for real IPs but over-broad. "Four octets" is not a sufficient discriminator for an IP address versus a version number. The scrubber was built incrementally and test cases were added for the success cases (real IPs get redacted) without adding failure cases (version numbers should not get redacted).

**How to avoid:**
Add negative lookbehind/lookahead patterns for common version-string contexts: preceded by `version`, `v`, `python`, `cuda`, `release`, or followed by common version suffixes. Apply RFC 5737 exclusions (192.0.2.x, 198.51.100.x, 203.0.113.x documentation ranges). Add test cases specifically for false positives — every version-number-like string you can think of. Same treatment for the phone regex (10-digit sequences like ticket IDs and error codes).

**Warning signs:**
- Version strings in tool outputs appear as `[REDACTED_IP]` in preview
- Quality scores for sessions with rich technical output drop unexpectedly (scrubber corrupted the content)
- Test suite has no tests named "test_no_false_positive" or similar

**Phase to address:** Regex hardening milestone. This is a correctness bug, not just a coverage gap. It degrades training data quality for every contributor using Python, CUDA, or library versioning in their sessions.

---

## Technical Debt Patterns

### TD-1: `ScrubResult` Name Collision Will Block Two-Pass Pipeline Implementation

When the LLM semantic scrubber is implemented, `scrubber.py` and `scrubber_llm.py` both define `ScrubResult` with different field shapes. The first import wins; the second silently shadows or errors. The two-pass pipeline that combines regex and semantic results cannot be cleanly assembled without first resolving this collision.

**Prevention:** Rename now, before the LLM scrubber is implemented. Use `RegexScrubResult` and `SemanticScrubResult`. Define a combined `ScrubResult` in `schema.py` with both result types as optional fields.

**Phase to address:** First task in the LLM scrubber implementation phase.

---

### TD-2: Consent Level is Schema-Only — Deferred Enforcement Accumulates Risk

The `consent_level` field has been in the schema since v0.1. Every day it exists without enforcement, there is a risk that a contributor configures it, believes it works, and submits data expecting privacy they are not receiving. This is not just tech debt — it is an active misrepresentation to users.

**Prevention:** Treat consent enforcement as blocking, not nice-to-have. It must ship in the same release as any community-facing contributor documentation.

**Phase to address:** Privacy hardening milestone (same as CP-2).

---

### TD-3: Outbox as Unbounded File Directory Will Break at Scale

`history` and `stats` commands glob all JSONL files and load all records into memory. At 1000+ submissions this is a memory and latency problem. At 10,000+ it becomes a practical blocker.

**Prevention:** Store `quality_tier` and `composite_score` in the submission metadata at submit time (the CONCERNS.md already identifies this). Add an index file or SQLite-backed manifest for the outbox. Implement pagination for `history` before users encounter the limit.

**Phase to address:** Dataset catalog / browsability milestone. This becomes critical exactly when the pipeline starts working well and volume increases.

---

### TD-4: Quality Score Re-Computation on Every Read

`history` and `stats` recompute all five sub-scores per record on every invocation. This is O(records × sub-scorers) on a CLI command that users will run frequently. It also means historical records get re-scored with any updated scoring logic, silently changing tier assignments without the contributor knowing.

**Prevention:** Store the quality tier and composite score at submit time. Never recompute for display purposes. If scoring logic changes between versions, re-score explicitly with a migration command.

**Phase to address:** Same as TD-3.

---

## Integration Gotchas

### IG-1: Hermes Hardcoded Path Blocks Model-Agnostic Vision

`KAJIBA_BASE = Path.home() / ".hermes" / "kajiba"` is hardcoded in the CLI. Any developer not using Hermes Agent cannot use Kajiba standalone without their data going into a Hermes-namespaced directory that may not exist. The model-agnostic requirement (current active requirement) directly conflicts with this hardcoded path.

**Prevention:** Add `KAJIBA_DATA_DIR` environment variable support with the current Hermes path as default. Add a `--data-dir` global CLI flag. Every test should use a temp directory, not the real `~/.hermes/kajiba/` path.

**Phase to address:** Model-agnostic decoupling milestone. This is the first thing to fix when decoupling from Hermes.

---

### IG-2: Hermes Integration Has Zero Test Coverage

`hermes_integration.py` is the primary data ingestion path for the target platform and has no tests. A regression in `register_hooks()` silently breaks data collection for all Hermes Agent users. There is no mock `HermesAgent` in the test suite.

**Prevention:** Create a `MockHermesAgent` fixture that implements the protocol. Test both conforming (valid Hermes agent) and non-conforming (missing methods) agents. Verify that hooks fire in the correct lifecycle order, that fallback to standalone mode activates on non-conforming agents, and that event errors do not propagate to the host process.

**Phase to address:** First milestone that adds any Hermes-facing functionality. Cannot defer past that point.

---

### IG-3: PyYAML and psutil Are Invisible Optional Dependencies

`pyyaml` is used by the `config` command but not declared. `psutil` is used by hardware detection but not declared. Both silently fall back without warning the user. Hardware quality scores will be consistently lower on macOS and Windows without `psutil`. Contributor config is silently ignored without `pyyaml`.

**Prevention:** Add both to the appropriate dependency groups (`pyyaml` to core or `config` extra; `psutil` to a `hardware` extra). At minimum, emit a clear warning that names the missing package and the `pip install kajiba[hardware]` command to fix it. Do not silently degrade.

**Phase to address:** Dependency hygiene pass. This is a contributor UX issue that erodes trust in the tool.

---

## Performance Traps

### PT-1: Regex Scrubber Scans Full Text Once Per Pattern (Redundant Passes)

`scrub_text()` runs `pattern.finditer()` to collect matches and then runs `pattern.sub()` to perform replacements — two full scans per pattern, for all patterns, on all text. For large tool outputs (code files, stack traces), this is slow. For the upcoming two-pass pipeline (regex + LLM), a slow regex pass blocks the LLM pass.

**Prevention:** Collect all match spans from all patterns in a single pass using a combined union regex or `re.Scanner`. Sort spans by position, merge overlapping ranges, perform a single replacement pass. This transforms O(patterns × text) into O(text + patterns). Use unique non-matchable placeholder formats (`<<KAJIBA:TYPE:N>>`) to prevent cross-pattern cascade matches.

**Phase to address:** Scrubber refactor milestone.

---

### PT-2: nvidia-smi Called Twice Per Session Start

Two subprocess calls to `nvidia-smi` with 10-second timeouts each. On slow systems (timeout path), this adds up to 20 seconds of blocking at session start. Hardware detection should be a one-time cost.

**Prevention:** Combine into a single `nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits` call. Cache the result at the process level — hardware does not change during a session.

**Phase to address:** Low priority. Fix opportunistically during hardware profile enhancement work.

---

## Security Mistakes

### SM-1: Redaction Objects Store Original PII Text

`Redaction.original` holds the matched text (the actual PII). `ScrubResult` carries a list of these. If a future caller logs, persists, or caches `ScrubResult` objects — a natural thing to do for debugging the scrubber — the original PII is exposed in logs.

**Prevention:** Do not store the original matched text. Store the field type and a truncated/hashed indicator. If debugging requires seeing what was redacted, gate that behind an explicit debug flag that is off by default and logged with a security warning.

**Phase to address:** Scrubber refactor. Add a `# SECURITY: never persist or transmit Redaction.original` comment as a short-term mitigation.

---

### SM-2: Staging Directory Reads Arbitrary Files Without Sandboxing

`_load_latest_staging()` reads JSON files from `~/.hermes/kajiba/staging/` without validating that the file is within the expected directory (symlink attack), checking file size before reading, or validating file ownership. A malicious process with write access to that directory could place oversized or malformed JSON there.

**Prevention:** Resolve symlinks and verify the resolved path is within the staging directory before reading. Add a maximum file size check (reject files over 10 MB). These are one-line additions with significant hardening value.

**Phase to address:** Security hardening pass.

---

### SM-3: 40-Character Hex Token Pattern Missing — Generic API Keys Pass Through

The spec explicitly requires a `r"[a-zA-Z0-9]{40}"` pattern (with context guards) for generic hex tokens. It is intentionally omitted from the implementation. Older-format API keys, some OAuth tokens, and certain secret formats that do not match other patterns will pass through unredacted.

**Prevention:** Implement with context guards: require the match to be preceded by `key=`, `token=`, `secret=`, `api_key=`, `authorization:` or similar context within 30 characters. Test against SHA-1 git commit hashes (which must NOT be redacted) and against real API key formats that should be redacted.

**Phase to address:** Regex coverage completion milestone.

---

## UX Pitfalls

### UP-1: Contributors Cannot Inspect What Was Scrubbed Before Submission

The preview command shows the scrubbed record but does not show what was redacted. A contributor who wants to verify that their company name was caught (or that their Python version wasn't incorrectly caught) has no way to see the diff between raw and scrubbed content.

This is a trust-building mechanism, not just a UX nicety. Contributors who can see exactly what was redacted will trust the scrubber more and adopt continuous mode sooner.

**Prevention:** Add a diff view to the preview command that shows redaction spans with their category tags. Show `[personal_name: "John"]` and `[company: "Acme Corp"]` — but do not show the original values by default (see SM-1). Show the count by category: "3 personal names, 1 company name, 2 API keys redacted."

**Phase to address:** Preview/UX refinement milestone.

---

### UP-2: Consent Level Options Are Not Explained at Configuration Time

The `consent_level` field has four options (`anonymous`, `trajectory_only`, `metadata_only`, `full`) but nowhere in the CLI is there a plain-language explanation of what each option strips. A contributor choosing `anonymous` may not realize it strips the conversation text entirely, making the record much less useful for fine-tuning.

**Prevention:** Add help text to the config command that explains each consent level's tradeoffs. Show the contributor what fields will be included/excluded for their current setting in the `preview` command. Make the choice informed, not a guess.

**Phase to address:** Consent enforcement milestone (same milestone as implementing the enforcement, so users get the explanation at the same time the feature works).

---

### UP-3: Continuous Mode Silently Submits Without Any Confirmation Mechanism

The `auto_submit` config option is referenced in SKILL.md but not implemented. When it is implemented, a naive implementation will silently submit every session without giving the contributor any visibility. Contributors who enable continuous mode and later review the dataset may discover records they would have edited.

**Prevention:** Even in continuous mode, write a summary log entry for each submission (session ID, quality tier, redaction count, consent level applied). Add a `kajiba history --since 1d` command that surfaces recent automatic submissions so contributors can audit them. Never make data submission truly invisible.

**Phase to address:** Continuous/auto-submit mode milestone.

---

## "Looks Done But Isn't" Checklist

These are features where the appearance of completeness masks a gap. Review each before declaring a phase done.

- [ ] **Consent level** — Field in schema. Is `apply_consent_level()` called in BOTH `export_record()` AND the `submit` CLI command?
- [ ] **LLM scrubber** — Module exists. Does `scrub_semantic()` do anything other than raise `NotImplementedError`?
- [ ] **Metadata anonymization** — Spec lists 4 steps. Are all 4 implemented (GPU generalization, timestamp jitter, RAM rounding, OS version stripping)?
- [ ] **Regex coverage** — 7 pattern categories pass tests. Are the 40-char hex token and org domain patterns included?
- [ ] **Hardware detection** — `detect_hardware()` runs. Does it return a complete profile on macOS and Windows (not just Linux)?
- [ ] **Quality tier persistence** — `compute_quality_score()` runs. Is the tier stored in the record at submit time (not recomputed on every read)?
- [ ] **Hermes integration tests** — `register_hooks()` exists. Is there a mock agent test that verifies hooks fire in the correct order?
- [ ] **Scrubber cascade** — Individual PII patterns pass. Is there a test where one placeholder text would match another pattern?
- [ ] **GitHub contribution flow** — Records can be exported to JSONL. Is there a PR-based submission mechanism (not direct push) to prevent poisoning?
- [ ] **`ScrubResult` collision** — Both modules define the class. Are they renamed before the two-pass pipeline is assembled?

---

## Recovery Strategies

### If a PII Leak Is Discovered Post-Publication

1. Take the dataset offline immediately (revoke public access to the GitHub repo or HuggingFace dataset)
2. Audit all records using the improved scrubber against the leaked category
3. Notify affected contributors (those whose sessions contained the leaked PII type) — this requires contributor contact info or a community channel
4. Re-scrub and re-publish the cleaned subset
5. Document the incident and the fix in the public changelog
6. **Do not silently patch and re-publish** — the community will notice version changes without explanation and trust will drop further than if you had been transparent

Lesson: The hardest part of PII leak recovery is discovery. Implement scrubber regression tests that run against a sample of the published dataset periodically.

---

### If Dataset Poisoning Is Suspected

1. Identify the suspicious records by content fingerprint (hash) and contributor session ID
2. Quarantine (do not delete immediately) — you need evidence for analysis
3. Run the suspected trigger phrase against a model fine-tuned on the clean-minus-suspect dataset vs the full dataset
4. If backdoor confirmed: remove affected records, retrain the community checkpoint, announce
5. Implement contributor rate limiting and PR review requirements before the repository is restored to public write access

---

### If Git Repository Grows Beyond Manageable Size

Once a GitHub repository exceeds 5 GB, performance degrades noticeably (slower clones, push rejections). Recovery is painful (git history rewrite, force push, re-cloning for all contributors).

Prevention is the only practical strategy: partition the dataset into versioned releases (v0.1/, v0.2/ directories or branches), set a max per-partition size limit, and transition to HuggingFace datasets before hitting the GitHub limit.

Trigger migration to HuggingFace when the dataset repository exceeds 2 GB — do not wait for GitHub to complain.

---

## Pitfall-to-Phase Mapping

| Pitfall | Risk Level | Must Fix Before | Phase Category |
|---------|-----------|-----------------|----------------|
| CP-1: Regex-only scrubbing passes semantic PII | CRITICAL | Any community-facing release | Privacy / LLM Scrubber |
| CP-2: Consent level not enforced | CRITICAL | Any community-facing release | Privacy / Consent |
| CP-3: Hardware metadata fingerprinting | HIGH | Community-facing release | Privacy / Anonymization |
| CP-4: Dataset poisoning via contributions | HIGH | GitHub repo goes live | Contribution flow / Dataset integrity |
| CP-5: IP regex false positives corrupt content | HIGH | Regression is already present | Regex hardening |
| SM-1: Redaction objects store original PII | MEDIUM | Scrubber refactor | Security / Scrubber |
| SM-2: Staging directory symlink risk | MEDIUM | Security hardening pass | Security |
| SM-3: 40-char hex token pattern missing | MEDIUM | Regex coverage completion | Regex hardening |
| TD-1: ScrubResult name collision | HIGH | LLM scrubber implementation | Tech debt / Before two-pass |
| TD-2: Consent level schema-only | CRITICAL | Same as CP-2 | Privacy / Consent |
| TD-3: Outbox unbounded directory | MEDIUM | High volume usage | Scalability |
| TD-4: Quality score re-computed on read | LOW | Catalog milestone | Performance |
| IG-1: Hermes path hardcoded | HIGH | Model-agnostic milestone | Architecture |
| IG-2: Hermes integration untested | HIGH | Next Hermes-facing feature | Testing |
| IG-3: Silent dependency degradation | MEDIUM | Contributor UX milestone | Dependencies |
| PT-1: Regex double-scan | LOW | Scrubber refactor | Performance |
| PT-2: nvidia-smi called twice | LOW | Hardware profile milestone | Performance |
| UP-1: No redaction diff in preview | MEDIUM | Contributor trust building | UX |
| UP-2: Consent level unexplained in CLI | MEDIUM | Consent enforcement | UX |
| UP-3: Continuous mode fully silent | MEDIUM | auto_submit implementation | UX |

---

## Sources

- Truffle Security: AI training dataset leaks thousands of live API keys and passwords — [Computing.co.uk](https://www.computing.co.uk/news/2025/security/ai-training-dataset-leaks-api-keys-and-passwords)
- Microsoft Research: Analyzing Leakage of Personally Identifiable Information in Language Models — [arxiv.org/abs/2302.00539](https://arxiv.org/abs/2302.00539)
- Secludy: Fine-tuning LLMs on Sensitive Data Lead to 19% PII Leakage — [medium.com/secludy](https://medium.com/secludy/fine-tuning-llm-on-sensitive-data-lead-to-19-pii-leakage-ee712d8e5821)
- Private AI: The Hidden PII Detection Crisis — [private-ai.com](https://www.private-ai.com/en/blog/hidden-pii-detection)
- Anonym.legal: The False Positive Problem — Presidio 22.7% precision on person names — [anonym.legal](https://anonym.legal/blog/presidio-false-positive-legal-healthcare-cost-2024)
- Elastic: Using NLP and Pattern Matching to Detect, Assess, and Redact PII in Logs — [elastic.co](https://www.elastic.co/observability-labs/blog/pii-ner-regex-assess-redact-part-2)
- Lakera: Introduction to Data Poisoning — [lakera.ai](https://www.lakera.ai/blog/training-data-poisoning)
- ICLR 2025: Persistent Pre-Training Poisoning of LLMs — [proceedings.iclr.cc](https://proceedings.iclr.cc/paper_files/paper/2025/file/4dade38eae8c007f3a564b8ea820664a-Paper-Conference.pdf)
- NIST AI 100-2e 2025: Adversarial Machine Learning Taxonomy — [nvlpubs.nist.gov](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-2e2025.pdf)
- Data Provenance Initiative: Consent in Crisis — The Rapid Decline of the AI Data Commons — [arxiv.org/abs/2407.14933](https://arxiv.org/pdf/2407.14933)
- USENIX Security 2025: Unveiling Hardware Cache Side-Channels in Local LLMs — [usenix.org](https://www.usenix.org/system/files/usenixsecurity25-gao-zibo.pdf)
- GitHub Docs: Repository Limits — [docs.github.com](https://docs.github.com/en/repositories/creating-and-managing-repositories/repository-limits)
- GitHub Docs: About Large Files on GitHub — [docs.github.com](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)
- James O'Claire: GitHub LFS is Basically Paid Only (2024) — [jamesoclaire.com](https://jamesoclaire.com/2024/12/06/github-large-file-storage-git-lfs-is-basically-paid-only/)
- Label Your Data: Data Versioning ML Best Practices 2026 — [labelyourdata.com](https://labelyourdata.com/articles/machine-learning/data-versioning)
- DVC: Git LFS and DVC Ultimate Guide — [medium.com/@pablojusue](https://medium.com/@pablojusue/git-lfs-and-dvc-the-ultimate-guide-to-managing-large-artifacts-in-mlops-c1c926e6c5f4)
- ActiveState: Predictions for Open Source in 2026: Maintainer Burnout — [activestate.com](https://www.activestate.com/blog/predictions-for-open-source-in-2026-ai-innovation-maintainer-burnout-and-the-compliance-crunch/)
- SecurePrivacy: Consent Management for AI Training Data — [secureprivacy.ai](https://secureprivacy.ai/blog/consent-management-for-ai-training-data)
- arxiv: Detecting and Preventing Data Poisoning Attacks on AI Models (2025) — [arxiv.org/abs/2503.09302](https://arxiv.org/abs/2503.09302)
- D:/Kajiba/.planning/codebase/CONCERNS.md — Primary source for codebase-specific pitfall evidence
