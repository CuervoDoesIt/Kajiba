# Kajiba (鍛冶場) — Project Specification

## Community data pipeline for open-source local model improvement

*Kajiba — the Japanese word for a forge or smithy. Where raw material is shaped into something stronger.*

**Version:** 0.1.0-draft
**License:** Apache 2.0 (proposed)
**Target integration:** Hermes Agent by NousResearch
**Strategy:** Standalone project → propose upstream after MVP proven

---

## Executive summary

Kajiba is an open-source pipeline that collects, standardizes, scrubs, curates, and distributes real-world usage data from local model deployments running through the Hermes Agent harness. The goal is to close the feedback loop: users running local models generate structured data about what works and what doesn't, and that data flows into a shared repository that the community uses to fine-tune and train the next generation of local models.

Hermes Agent already has trajectory export (ShareGPT format), batch trajectory generation with parallel workers, Atropos RL integration, and 11 tool-call parsers. Kajiba builds the **collection, standardization, privacy, curation, and distribution** layers that sit between individual users and the community training pipeline.

---

## 1. Schema design + data format

### 1.1 Design principles

- **Single record = one task attempt.** A record captures everything about one user-agent interaction from prompt to completion, including all tool calls, intermediate steps, and the outcome.
- **Versioned from day one.** The schema uses semver. Every record carries a `schema_version` field. Consumers can filter by version. Breaking changes bump the major version.
- **Composable layers.** The core trajectory is required. Metadata (hardware, model, timing), outcome signals, and pain point reports are optional extensions. This lets users contribute at whatever granularity they're comfortable with.
- **Compatible with existing formats.** The trajectory layer is a strict superset of ShareGPT format, so existing tooling (Axolotl, LLaMA-Factory, etc.) can consume it without modification.

### 1.2 Top-level record schema

```jsonc
{
  // === REQUIRED FIELDS ===
  "schema_version": "0.1.0",
  "record_id": "kajiba_a1b2c3d4e5f6",        // Deterministic hash of trajectory content
  "record_type": "task_trajectory",           // "task_trajectory" | "pain_point" | "benchmark_run"
  "created_at": "2026-03-29T14:22:00Z",      // ISO 8601 UTC
  "submission_hash": "sha256:abcdef...",      // Content-addressable dedup key

  // === TRAJECTORY (required for task_trajectory) ===
  "trajectory": {
    "format": "sharegpt_extended",            // Always this value for v0.1
    "conversations": [
      {
        "from": "human",
        "value": "Deploy the FastAPI service using Docker"
      },
      {
        "from": "gpt",
        "value": "I'll help you deploy...",
        "tool_calls": [
          {
            "tool_name": "terminal",
            "tool_input": "docker build -t fastapi-app .",
            "tool_output": "Successfully built 3a7f2b1c...",
            "tool_status": "success",           // "success" | "failure" | "timeout" | "error"
            "latency_ms": 4523
          }
        ],
        "token_count": 342,
        "generation_latency_ms": 1823
      }
      // ... additional turns
    ],
    "turn_count": 6,
    "total_tool_calls": 4,
    "successful_tool_calls": 3,
    "failed_tool_calls": 1
  },

  // === MODEL METADATA (optional but strongly encouraged) ===
  "model": {
    "model_name": "Hermes-3-Llama-3.1-8B",
    "model_family": "llama",                  // Normalized family identifier
    "parameter_count": "8B",                  // Human-readable param count
    "quantization": "Q4_K_M",                 // GGUF quant level, or "fp16", "awq", "gptq", etc.
    "context_window": 131072,                 // Max context in tokens
    "context_used": 9230,                     // Tokens used at peak during this task
    "provider": "ollama",                     // "ollama" | "vllm" | "sglang" | "llamacpp" | "openrouter" | "custom"
    "is_local": true,                         // Was inference done on user's hardware?
    "model_hash": "sha256:abc..."             // Optional: hash of model weights file
  },

  // === HARDWARE PROFILE (optional) ===
  "hardware": {
    "gpu_name": "NVIDIA RTX 4090",
    "gpu_vram_gb": 24,
    "gpu_count": 1,
    "cpu_name": "AMD Ryzen 9 7950X",
    "ram_gb": 64,
    "os": "linux",                            // "linux" | "macos" | "wsl2"
    "inference_backend": "ollama",
    "cuda_version": "12.4"
  },

  // === OUTCOME SIGNALS (optional but high value) ===
  "outcome": {
    "user_rating": 4,                         // 1-5 scale
    "outcome_tags": [                         // Controlled vocabulary, multiple allowed
      "task_completed",
      "minor_hallucination"
    ],
    "user_comment": "Got the job done but hallucinated a flag that doesn't exist on docker build",
    "task_category": "devops",                // Free-text task category
    "difficulty_estimate": "medium"           // "trivial" | "easy" | "medium" | "hard" | "expert"
  },

  // === PAIN POINT REPORT (optional, standalone or attached to trajectory) ===
  "pain_points": [
    {
      "category": "tool_call_failure",        // Controlled vocabulary
      "severity": "medium",                   // "low" | "medium" | "high" | "critical"
      "description": "Model attempted to call 'docker_compose' tool which doesn't exist in the current toolset",
      "turn_index": 3,                        // Which turn in the trajectory this occurred
      "reproducible": true
    }
  ],

  // === SUBMISSION METADATA ===
  "submission": {
    "hermes_version": "0.2.0",
    "kajiba_plugin_version": "0.1.0",
    "contributor_id": "anon_hf_abc123",       // Optional pseudonymous HF-derived ID
    "consent_level": "full",                  // "trajectory_only" | "metadata_only" | "full" | "anonymous"
    "pii_scrub_version": "0.1.0",
    "scrub_log": {                            // What was redacted
      "file_paths_redacted": 3,
      "potential_names_redacted": 1,
      "api_keys_redacted": 0
    }
  }
}
```

### 1.3 Controlled vocabularies

#### Outcome tags (v0.1 — extensible)

| Tag | Meaning |
|-----|---------|
| `task_completed` | The user's goal was fully achieved |
| `task_partial` | Goal was partially achieved |
| `task_failed` | Goal was not achieved |
| `hallucination` | Model asserted false information |
| `minor_hallucination` | Small factual error that didn't derail the task |
| `tool_call_correct` | All tool calls were syntactically and semantically correct |
| `tool_call_failed` | One or more tool calls failed due to model error |
| `tool_not_found` | Model tried to call a tool that doesn't exist |
| `wrong_format` | Output was correct but in the wrong format |
| `context_overflow` | Model hit context window limits |
| `slow_response` | Generation was unacceptably slow |
| `perfect` | No issues at all — exemplary interaction |
| `safety_issue` | Model produced harmful or unsafe content |
| `refusal_appropriate` | Model correctly refused an unsafe request |
| `refusal_inappropriate` | Model refused a legitimate request |
| `loop_detected` | Model got stuck in a repetitive loop |
| `instruction_following` | Model followed instructions precisely |
| `instruction_drift` | Model drifted from the original instruction |

#### Pain point categories (v0.1)

| Category | Description |
|----------|-------------|
| `tool_call_failure` | Model generated invalid tool calls |
| `tool_call_wrong_tool` | Model used the wrong tool for the task |
| `hallucination_factual` | Model stated something factually incorrect |
| `hallucination_tool` | Model referenced nonexistent tools/APIs |
| `context_loss` | Model lost track of earlier conversation context |
| `format_error` | Output in wrong structure or format |
| `reasoning_error` | Logical or reasoning mistake |
| `performance_issue` | Unacceptable latency or resource usage |
| `safety_concern` | Harmful, biased, or unsafe output |
| `ux_friction` | Interaction felt awkward or required unnecessary back-and-forth |
| `skill_gap` | Model lacked knowledge for the domain |
| `other` | Doesn't fit other categories (requires description) |

### 1.4 Schema versioning strategy

The schema follows semver with these rules:

- **Patch (0.1.x):** New optional fields, new tags added to controlled vocabularies, documentation changes.
- **Minor (0.x.0):** New optional sections, changes to default values, deprecation of fields (with 2-version grace period).
- **Major (x.0.0):** Removal of fields, changes to required fields, structural reorganization. Only after community RFC process.

Every record is self-describing via `schema_version`. The ingestion API validates against all supported schema versions and normalizes to the latest before storage.

### 1.5 Export format compatibility

The `trajectory.conversations` array is designed so that stripping all fields except `from` and `value` produces valid ShareGPT format. This means:

```python
# Convert Kajiba record → vanilla ShareGPT for Axolotl/LLaMA-Factory
sharegpt_record = {
    "conversations": [
        {"from": turn["from"], "value": turn["value"]}
        for turn in kajiba_record["trajectory"]["conversations"]
    ]
}
```

For DPO pair generation, two records with the same task prompt but different outcome ratings become a preference pair:

```python
# Positive: rating >= 4, tags include task_completed
# Negative: rating <= 2, tags include task_failed or hallucination
dpo_pair = {
    "prompt": shared_initial_prompt,
    "chosen": positive_trajectory_response,
    "rejected": negative_trajectory_response
}
```

---

## 2. Privacy and PII scrubbing architecture

### 2.1 Threat model

The primary threats are:

1. **Accidental PII leakage:** Users submit trajectories containing their names, file paths with usernames, API keys, internal hostnames, project names, or other identifying information embedded in conversation text.
2. **Deanonymization via metadata:** Hardware profiles + timestamps + model configurations could fingerprint individual users even without explicit PII.
3. **Sensitive code/data exposure:** Trajectories involving proprietary code, credentials, or business logic that users didn't intend to share.
4. **Injection via trajectory content:** Malicious actors submitting trajectories containing prompt injections or harmful content aimed at poisoning the training dataset.

### 2.2 Defense layers

#### Layer A: Pre-submission preview (local, mandatory)

Before any data leaves the user's machine, the Kajiba plugin shows a complete preview of what will be submitted. The user must explicitly confirm. This is the first and most important gate.

```
╔══════════════════════════════════════════════════════════╗
║  Kajiba — Submission preview                       ║
╠══════════════════════════════════════════════════════════╣
║  Record type:    task_trajectory                         ║
║  Turns:          6 (4 tool calls)                        ║
║  Model:          Hermes-3-Llama-3.1-8B (Q4_K_M)        ║
║  Your rating:    4/5 — task_completed, minor_hallucin.  ║
║                                                          ║
║  PII scrubbing results:                                  ║
║    ✓ 3 file paths redacted                               ║
║    ✓ 1 potential name redacted                           ║
║    ✓ 0 API keys found                                    ║
║    ⚠ 1 hostname detected — review below                 ║
║                                                          ║
║  [View full record]  [Edit before submit]  [Cancel]      ║
╚══════════════════════════════════════════════════════════╝
```

#### Layer B: Regex-based PII scrubber (local, automated)

The first automated pass uses pattern matching for known PII formats. All matches are replaced with type-tagged placeholders: `[REDACTED_PATH]`, `[REDACTED_KEY]`, etc.

**Pattern categories:**

```python
SCRUB_PATTERNS = {
    # File paths containing usernames
    "file_paths": [
        r"/home/[a-zA-Z0-9_.-]+/",          # Linux home dirs
        r"/Users/[a-zA-Z0-9_.-]+/",          # macOS home dirs
        r"C:\\Users\\[a-zA-Z0-9_.-]+\\",     # Windows paths
        r"~/.+",                               # Tilde-expanded paths
    ],

    # API keys and tokens (common formats)
    "api_keys": [
        r"sk-[a-zA-Z0-9]{32,}",              # OpenAI-style keys
        r"ghp_[a-zA-Z0-9]{36}",              # GitHub PATs
        r"glpat-[a-zA-Z0-9-]{20,}",          # GitLab PATs
        r"AKIA[0-9A-Z]{16}",                 # AWS access key IDs
        r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+",  # JWTs
        r"[a-zA-Z0-9]{40}",                  # Generic 40-char hex tokens (with context)
        r"Bearer\s+[a-zA-Z0-9._-]+",         # Auth headers
        r"token['\"]?\s*[:=]\s*['\"][^'\"]+", # token = "..." patterns
    ],

    # Network identifiers
    "network": [
        r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",  # IPv4 addresses
        r"[a-zA-Z0-9-]+\.(internal|local|corp|lan)\b", # Internal hostnames
        r"[a-zA-Z0-9-]+\.(?:company|org|io)\b",       # Potential org domains (flagged, not auto-redacted)
    ],

    # Email addresses
    "emails": [
        r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
    ],

    # Phone numbers (US/international)
    "phone": [
        r"\b\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    ],

    # SSH keys and certificates
    "crypto": [
        r"-----BEGIN [A-Z ]+-----[\s\S]*?-----END [A-Z ]+-----",
        r"ssh-[a-z0-9]+ AAAA[a-zA-Z0-9+/]+[=]{0,2}",
    ],

    # Database connection strings
    "connection_strings": [
        r"(postgres|mysql|mongodb|redis)://[^\s]+",
        r"Server=[^;]+;Database=[^;]+;",
    ],
}
```

#### Layer C: LLM-based semantic PII scrubber (local, optional but recommended)

The regex pass catches structured PII. The LLM pass catches semantic PII — names mentioned in conversation, project names, company references, and other context-dependent identifying information.

This runs the user's local model (the same one used for the agent) with a focused prompt:

```
You are a PII detection assistant. Analyze the following conversation
and identify any personally identifiable information, including:
- Personal names (first, last, or full)
- Company or organization names
- Project names that could identify the user
- Geographic locations specific enough to identify someone
- Any other information that could be used to identify the contributor

For each item found, respond with:
- The exact text to redact
- The replacement tag (e.g., [PERSON_NAME], [COMPANY], [PROJECT])
- Your confidence (high/medium/low)

Only flag items with medium or high confidence. Do not flag generic
technical terms, tool names, or well-known open-source project names.
```

Items flagged with "high" confidence are auto-redacted. Items with "medium" confidence are highlighted in the preview for user review.

#### Layer D: Metadata anonymization (local, automated)

Hardware and timing metadata can fingerprint users. The scrubber applies:

- **GPU name generalization:** "NVIDIA RTX 4090" stays as-is (common enough), but rare hardware like "NVIDIA A100 80GB SXM" gets generalized to "NVIDIA A100" since fewer people have these.
- **Timestamp jitter:** ±0-30 minutes random offset to prevent correlation.
- **RAM/VRAM rounding:** Rounded to nearest standard tier (8, 16, 24, 32, 48, 64, 96, 128 GB).
- **OS version stripping:** Only the OS family is kept (linux/macos/wsl2), not the kernel version or distro.

#### Layer E: Consent levels

Users choose what to share:

| Level | What's included | What's excluded |
|-------|----------------|-----------------|
| `anonymous` | Trajectory only, no metadata, no contributor ID | Everything else |
| `trajectory_only` | Trajectory + model name + outcome | Hardware, timing, contributor ID |
| `metadata_only` | Outcome signals + pain points + model info + hardware | Actual trajectory text |
| `full` | Everything (after PII scrub) | Nothing (except scrubbed PII) |

The default is `full` with PII scrubbing. Users can change the default in their Hermes config:

```yaml
# ~/.hermes/config.yaml
kajiba:
  consent_level: full          # anonymous | trajectory_only | metadata_only | full
  auto_submit: false           # Never auto-submit; always preview first
  llm_pii_scrub: true          # Run LLM-based scrubber (uses local model)
  scrub_strictness: high       # low | medium | high (high = more aggressive redaction)
```

### 2.3 What is NEVER submitted

Regardless of consent level, the following are always stripped and never leave the machine:

- Raw API keys (detected by regex and redacted before any preview)
- SSH private keys and certificates
- Database connection strings with credentials
- Contents of `.env` files
- Hermes Agent's own configuration (API keys, bot tokens)
- File contents that were read/written during tool execution (only the tool call metadata is captured, not the file payloads)

---

## 3. Quality scoring and curation

### 3.1 Automated quality scoring

Every submitted record receives an automated quality score from 0.0 to 1.0, composed of weighted sub-scores:

#### Sub-score: Trajectory coherence (weight: 0.30)

Measures whether the conversation makes logical sense as a sequence.

```python
def score_coherence(record):
    """
    Checks:
    - Alternating human/gpt turns (no double-human or double-gpt)
    - Tool calls appear only in gpt turns
    - Tool outputs reference tools that were actually called
    - No empty turns (value is non-empty string)
    - Conversation has at least 2 turns
    - Final turn is from gpt (task was attempted)
    """
    score = 1.0
    turns = record["trajectory"]["conversations"]

    if len(turns) < 2:
        return 0.0

    for i, turn in enumerate(turns):
        # Check alternation
        expected_role = "human" if i % 2 == 0 else "gpt"
        if turn["from"] != expected_role:
            score -= 0.15

        # Check non-empty
        if not turn.get("value", "").strip():
            score -= 0.10

        # Check tool call integrity
        if turn.get("tool_calls"):
            if turn["from"] != "gpt":
                score -= 0.20  # Tool calls in human turn = invalid
            for tc in turn["tool_calls"]:
                if not tc.get("tool_name") or not tc.get("tool_status"):
                    score -= 0.05

    if turns[-1]["from"] != "gpt":
        score -= 0.10

    return max(0.0, score)
```

#### Sub-score: Tool call validity (weight: 0.25)

Measures whether tool calls were well-formed and the success/failure tagging is consistent.

```python
def score_tool_validity(record):
    """
    Checks:
    - Tool calls have all required fields (name, input, output, status)
    - Success/failure counts match the actual tool_status values
    - No tool calls with status "success" but empty output
    - No tool calls with unreasonable latency (>300s = suspicious)
    - Tool names are from the known Hermes toolset vocabulary
    """
    trajectory = record["trajectory"]
    tool_calls = []
    for turn in trajectory["conversations"]:
        tool_calls.extend(turn.get("tool_calls", []))

    if not tool_calls:
        return 1.0  # No tool calls = not applicable, full score

    score = 1.0
    actual_success = sum(1 for tc in tool_calls if tc["tool_status"] == "success")
    actual_failure = sum(1 for tc in tool_calls if tc["tool_status"] != "success")

    # Verify reported counts match
    if trajectory.get("successful_tool_calls") != actual_success:
        score -= 0.15
    if trajectory.get("failed_tool_calls") != actual_failure:
        score -= 0.15

    for tc in tool_calls:
        if tc["tool_status"] == "success" and not tc.get("tool_output", "").strip():
            score -= 0.10
        if tc.get("latency_ms", 0) > 300000:
            score -= 0.05

    return max(0.0, score)
```

#### Sub-score: Outcome signal quality (weight: 0.20)

Measures whether the user-provided outcome data is internally consistent.

```python
def score_outcome_quality(record):
    """
    Checks:
    - If rating is 5 and tags include 'task_failed' → inconsistent (-0.3)
    - If rating is 1 and tags include 'perfect' → inconsistent (-0.3)
    - If pain points reference turn_index values that exist → valid
    - If outcome tags are from controlled vocabulary → valid
    - Presence of user_comment adds value (+0.1)
    """
    outcome = record.get("outcome")
    if not outcome:
        return 0.5  # No outcome = neutral, not penalized

    score = 1.0
    rating = outcome.get("user_rating", 3)
    tags = outcome.get("outcome_tags", [])

    # Consistency checks
    if rating >= 4 and "task_failed" in tags:
        score -= 0.30
    if rating <= 2 and "perfect" in tags:
        score -= 0.30
    if rating >= 4 and "hallucination" in tags and "minor_hallucination" not in tags:
        score -= 0.15

    # Bonus for descriptive outcomes
    if outcome.get("user_comment") and len(outcome["user_comment"]) > 20:
        score = min(1.0, score + 0.10)

    return max(0.0, score)
```

#### Sub-score: Information density (weight: 0.15)

Measures whether the trajectory contains enough substance to be useful for training.

```python
def score_information_density(record):
    """
    Checks:
    - Total token count across all turns (min 100 for useful training signal)
    - Ratio of gpt tokens to human tokens (very low = model barely responded)
    - Presence of tool calls adds value (agentic behavior)
    - Conversations with only 2 turns get lower score (less training signal)
    """
    turns = record["trajectory"]["conversations"]
    total_tokens = sum(t.get("token_count", len(t["value"].split())) for t in turns)
    gpt_tokens = sum(
        t.get("token_count", len(t["value"].split()))
        for t in turns if t["from"] == "gpt"
    )
    human_tokens = total_tokens - gpt_tokens

    if total_tokens < 100:
        return 0.2
    if total_tokens < 300:
        return 0.5

    score = 0.7  # Base for adequate length

    # Reward agentic behavior
    if record["trajectory"].get("total_tool_calls", 0) > 0:
        score += 0.15

    # Reward multi-turn interactions
    if record["trajectory"]["turn_count"] >= 4:
        score += 0.10

    # Penalize extreme imbalance
    if human_tokens > 0 and gpt_tokens / human_tokens < 0.5:
        score -= 0.15

    return min(1.0, max(0.0, score))
```

#### Sub-score: Metadata completeness (weight: 0.10)

Rewards records that include model and hardware metadata, which makes the data more useful for analysis.

```python
def score_metadata_completeness(record):
    """Simply counts how many optional sections are present and populated."""
    score = 0.0
    if record.get("model", {}).get("model_name"):
        score += 0.30
    if record.get("model", {}).get("quantization"):
        score += 0.15
    if record.get("model", {}).get("provider"):
        score += 0.10
    if record.get("hardware", {}).get("gpu_name"):
        score += 0.20
    if record.get("outcome", {}).get("user_rating"):
        score += 0.15
    if record.get("pain_points"):
        score += 0.10
    return min(1.0, score)
```

#### Composite score

```python
def compute_quality_score(record):
    weights = {
        "coherence": 0.30,
        "tool_validity": 0.25,
        "outcome_quality": 0.20,
        "information_density": 0.15,
        "metadata_completeness": 0.10,
    }
    sub_scores = {
        "coherence": score_coherence(record),
        "tool_validity": score_tool_validity(record),
        "outcome_quality": score_outcome_quality(record),
        "information_density": score_information_density(record),
        "metadata_completeness": score_metadata_completeness(record),
    }
    composite = sum(sub_scores[k] * weights[k] for k in weights)
    return {
        "composite_score": round(composite, 3),
        "sub_scores": {k: round(v, 3) for k, v in sub_scores.items()},
        "quality_tier": (
            "gold" if composite >= 0.85 else
            "silver" if composite >= 0.65 else
            "bronze" if composite >= 0.45 else
            "review_needed"
        )
    }
```

### 3.2 Quality tiers and their uses

| Tier | Score range | Usage |
|------|-------------|-------|
| **Gold** | ≥ 0.85 | Direct inclusion in SFT training sets. DPO positive examples. Benchmark reference. |
| **Silver** | 0.65 – 0.84 | Included in training sets after community spot-check. DPO candidates. |
| **Bronze** | 0.45 – 0.64 | Available for download but excluded from curated sets. Useful for data mining and analysis. |
| **Review needed** | < 0.45 | Quarantined. Requires manual community review before any use. May indicate data quality issues, adversarial submissions, or edge cases. |

### 3.3 Community curation

#### Voting system

Registered contributors can upvote or downvote individual records in the dataset browser. Votes are weighted by the voter's contribution history:

- New voter: weight 1.0
- Voter with 10+ accepted submissions: weight 1.5
- Voter with 50+ accepted submissions: weight 2.0
- Flagged voter (history of adversarial submissions): weight 0.25

A record's community score is the weighted sum of votes, normalized to [-1.0, 1.0]. Records with community score below -0.5 are auto-quarantined. Records with community score above 0.5 get a boost to their quality tier (bronze → silver, silver → gold).

#### Adversarial submission detection

The pipeline watches for:

- **Bulk submissions** from a single contributor with suspiciously uniform quality scores (bot-generated).
- **Prompt injection** in trajectory text (e.g., "ignore previous instructions" patterns in the human turns).
- **Circular references** where the trajectory is generated by an LLM about LLMs in a way that produces vacuous training signal.
- **Duplicate semantics** where the same task is submitted hundreds of times with trivial variations (padding the dataset).

Detection uses a combination of heuristics and a small classifier trained on known adversarial examples from other open-source datasets.

---

## 4. Atropos RL environment packaging

### 4.1 Background

Hermes Agent includes an integrated RL training pipeline built on Tinker-Atropos. The system has three components: Atropos (trajectory API server), Tinker (training service with LoRA adapters), and Environments (Python classes that define tasks, scoring, and reward functions). Hermes Agent users can already run `rl_list_environments`, `rl_select_environment`, `rl_edit_config`, and `rl_start_training` through the agent's tool interface.

Kajiba's contribution is packaging curated community data INTO new Atropos environments that any Hermes Agent user can install and train on.

### 4.2 Environment generation pipeline

The pipeline takes curated Kajiba records and produces installable Atropos environments:

```
Curated records (gold/silver tier)
        │
        ▼
    Task clustering          ← Group by task_category, tool patterns, difficulty
        │
        ▼
    Environment scaffolding  ← Generate Python environment class per cluster
        │
        ▼
    Reward function derivation ← Convert outcome signals to reward functions
        │
        ▼
    Validation suite         ← Sanity-check environments with test rollouts
        │
        ▼
    Package + publish        ← Hermes skill format + pip-installable package
```

### 4.3 Task clustering

Records are grouped into trainable environment clusters using:

1. **Task category** (from outcome.task_category): devops, coding, research, data_analysis, writing, etc.
2. **Tool signature**: The set of tools used in the trajectory. Records using {terminal, file_system} cluster separately from those using {web_search, browser}.
3. **Difficulty tier**: Records rated "trivial" or "easy" go into beginner environments; "hard" and "expert" into advanced ones.
4. **Outcome polarity**: Gold-tier "perfect" records become reward=1.0 reference trajectories. Low-rated records with specific failure tags become reward=0.0 references.

A cluster needs a minimum of 50 gold/silver records to become a viable environment.

### 4.4 Atropos environment template

Each generated environment follows this structure:

```python
"""
Kajiba Community Environment: DevOps Docker Deployment (Medium)
Generated from 127 curated community trajectories.
Cluster: devops + {terminal, file_system} + medium difficulty
"""

import json
from pathlib import Path
from atropos.environment import Environment, TaskResult


class KajibaDevopsDockerMedium(Environment):
    """
    Tasks involving Docker container building, deployment, and debugging.
    Derived from real user interactions with Hermes Agent.
    """

    ENV_NAME = "kajiba_devops_docker_medium"
    ENV_VERSION = "0.1.0"
    KAJIBA_SCHEMA_VERSION = "0.1.0"
    SOURCE_RECORD_COUNT = 127
    MIN_QUALITY_TIER = "silver"

    def __init__(self, config=None):
        super().__init__(config)
        self.tasks = self._load_tasks()
        self.reference_trajectories = self._load_references()

    def _load_tasks(self):
        """Load task prompts extracted from community trajectories."""
        task_file = Path(__file__).parent / "data" / "tasks.jsonl"
        with open(task_file) as f:
            return [json.loads(line) for line in f]

    def _load_references(self):
        """Load gold-tier reference trajectories for reward computation."""
        ref_file = Path(__file__).parent / "data" / "references.jsonl"
        with open(ref_file) as f:
            return [json.loads(line) for line in f]

    def get_task(self, task_idx: int) -> dict:
        """Return a task prompt for the agent to attempt."""
        task = self.tasks[task_idx % len(self.tasks)]
        return {
            "prompt": task["prompt"],
            "available_tools": task["tool_signature"],
            "max_turns": task.get("max_turns", 10),
            "context": task.get("context", ""),
        }

    def score_trajectory(self, trajectory: list[dict]) -> TaskResult:
        """
        Score an agent's trajectory against community-derived criteria.

        Reward signal components:
        1. Task completion (0.0 or 1.0): Did the agent achieve the goal?
           Derived from outcome tags on reference trajectories.
        2. Tool efficiency (0.0 - 1.0): How many tool calls vs reference?
           Fewer calls for same result = higher reward.
        3. Error avoidance (0.0 - 1.0): Did the agent avoid known failure modes?
           Derived from pain_points on negative reference trajectories.
        """
        completion_score = self._score_completion(trajectory)
        efficiency_score = self._score_efficiency(trajectory)
        error_avoidance_score = self._score_error_avoidance(trajectory)

        composite = (
            0.50 * completion_score +
            0.30 * efficiency_score +
            0.20 * error_avoidance_score
        )

        return TaskResult(
            reward=composite,
            metrics={
                "completion": completion_score,
                "efficiency": efficiency_score,
                "error_avoidance": error_avoidance_score,
            },
            done=True,
        )

    def _score_completion(self, trajectory):
        """
        Use an LLM judge (small, fast model) to evaluate whether the
        trajectory achieved the task goal. Compare against reference
        trajectories' final states.
        """
        # Implementation: prompt a judge model with the task goal and
        # the agent's final output, asking for a binary pass/fail.
        # Fall back to heuristic (tool calls succeeded + output non-empty)
        # if no judge model is available.
        pass

    def _score_efficiency(self, trajectory):
        """
        Compare tool call count against reference trajectory median.
        Reward = 1.0 if <= median, linearly decreasing to 0.0 at 3x median.
        """
        agent_calls = sum(1 for t in trajectory if t.get("tool_calls"))
        ref_median = self._get_reference_tool_call_median()
        if agent_calls <= ref_median:
            return 1.0
        elif agent_calls >= ref_median * 3:
            return 0.0
        else:
            return 1.0 - (agent_calls - ref_median) / (ref_median * 2)

    def _score_error_avoidance(self, trajectory):
        """
        Check if the agent triggered known failure patterns extracted
        from community pain_point reports.
        """
        known_failures = self._get_known_failure_patterns()
        triggered = 0
        for pattern in known_failures:
            if self._pattern_matches(trajectory, pattern):
                triggered += 1
        if not known_failures:
            return 1.0
        return 1.0 - (triggered / len(known_failures))

    @property
    def task_count(self):
        return len(self.tasks)
```

### 4.5 Environment packaging

Each environment is packaged as:

```
kajiba-env-devops-docker-medium/
├── __init__.py
├── environment.py              # The Environment subclass above
├── data/
│   ├── tasks.jsonl             # Task prompts (human turns from trajectories)
│   ├── references.jsonl        # Gold-tier reference trajectories
│   ├── failure_patterns.jsonl  # Known failure modes from pain_point reports
│   └── metadata.json           # Cluster stats, source record IDs, quality distribution
├── tests/
│   ├── test_environment.py     # Validates environment loads and scores correctly
│   └── test_data_integrity.py  # Validates data files match expected schema
├── README.md                   # Environment description, stats, usage instructions
├── pyproject.toml              # pip-installable with [atropos] extra
└── KAJIBA_PROVENANCE.json       # Links back to source record IDs in the HF dataset
```

Distribution channels:

1. **HuggingFace dataset companion:** Each environment release is tagged alongside the dataset version that produced it.
2. **pip install:** `pip install kajiba-env-devops-docker-medium` for standalone use.
3. **Hermes skill:** Published to agentskills.io so Hermes Agent users can install via `hermes skills install kajiba-devops-docker`.

### 4.6 Environment refresh cycle

As new community data flows in, environments are regenerated monthly:

1. Re-cluster all gold/silver records.
2. Diff against previous environment version.
3. If >20% new tasks or >10% changed reference trajectories, publish a new minor version.
4. Old versions remain available for reproducibility.
5. Changelog documents what changed and why.

---

## 5. Local collector plugin architecture

### 5.1 Plugin structure

The Kajiba collector is a Hermes Agent skill that hooks into the session lifecycle:

```
kajiba/
├── kajiba_skill/
│   ├── __init__.py
│   ├── collector.py            # Core data collection logic
│   ├── schema.py               # Record schema definitions + validation
│   ├── scrubber.py             # PII scrubbing (regex + LLM)
│   ├── scorer.py               # Local quality scoring
│   ├── exporter.py             # Export to JSONL, submit to API
│   ├── commands.py             # Slash command handlers (/rate, /report, /kajiba)
│   └── config.py               # Kajiba-specific configuration
├── tests/
│   ├── test_collector.py
│   ├── test_scrubber.py
│   ├── test_scorer.py
│   ├── test_schema.py
│   └── fixtures/               # Sample trajectories for testing
│       ├── gold_trajectory.json
│       ├── pii_trajectory.json
│       └── adversarial_trajectory.json
├── SKILL.md                    # Hermes Agent skill manifest
├── README.md
├── pyproject.toml
└── LICENSE
```

### 5.2 Slash commands

```
/rate [1-5] [tags...]         Rate the current session. Tags from controlled vocabulary.
                               Example: /rate 4 task_completed minor_hallucination

/report [category] [text]     Submit a pain point report.
                               Example: /report tool_call_failure Model tried to use docker_compose tool

/kajiba preview                 Preview what would be submitted for the current session.

/kajiba submit                  Submit the current session (after preview + confirmation).

/kajiba history                 Show past submissions and their status.

/kajiba config                  View/edit Kajiba configuration (consent level, auto-scrub, etc.)

/kajiba export [path]           Export current session as Kajiba-format JSONL to local file.

/kajiba stats                   Show local statistics (submissions count, quality distribution, etc.)
```

### 5.3 Session lifecycle hooks

```python
class KajibaCollector:
    """
    Hooks into Hermes Agent's session lifecycle to capture telemetry.
    Non-intrusive: if Kajiba fails, the agent session continues normally.
    """

    def on_session_start(self, session_id: str, model_config: dict):
        """Capture model metadata at session start."""
        self.current_record = {
            "schema_version": SCHEMA_VERSION,
            "record_type": "task_trajectory",
            "model": self._extract_model_metadata(model_config),
            "hardware": self._detect_hardware(),
            "trajectory": {"conversations": [], "format": "sharegpt_extended"},
        }

    def on_turn_complete(self, turn: dict):
        """Capture each turn as it completes, including tool calls and timing."""
        enriched_turn = {
            "from": turn["role"],  # "human" or "gpt"
            "value": turn["content"],
            "token_count": turn.get("token_count"),
            "generation_latency_ms": turn.get("latency_ms"),
        }
        if turn.get("tool_calls"):
            enriched_turn["tool_calls"] = [
                {
                    "tool_name": tc["name"],
                    "tool_input": tc["input"][:2000],   # Truncate long inputs
                    "tool_output": tc["output"][:2000],  # Truncate long outputs
                    "tool_status": tc["status"],
                    "latency_ms": tc.get("latency_ms"),
                }
                for tc in turn["tool_calls"]
            ]
        self.current_record["trajectory"]["conversations"].append(enriched_turn)

    def on_session_end(self, session_id: str):
        """Finalize record, compute stats, prompt for rating if configured."""
        traj = self.current_record["trajectory"]
        all_tool_calls = [
            tc for turn in traj["conversations"]
            for tc in turn.get("tool_calls", [])
        ]
        traj["turn_count"] = len(traj["conversations"])
        traj["total_tool_calls"] = len(all_tool_calls)
        traj["successful_tool_calls"] = sum(
            1 for tc in all_tool_calls if tc["tool_status"] == "success"
        )
        traj["failed_tool_calls"] = traj["total_tool_calls"] - traj["successful_tool_calls"]

        # Prompt for rating if session had substance
        if traj["turn_count"] >= 2:
            self._prompt_for_rating()

    def on_rate(self, rating: int, tags: list[str], comment: str = ""):
        """Handle /rate command."""
        self.current_record["outcome"] = {
            "user_rating": rating,
            "outcome_tags": tags,
            "user_comment": comment,
        }

    def on_report(self, category: str, description: str, severity: str = "medium"):
        """Handle /report command."""
        if "pain_points" not in self.current_record:
            self.current_record["pain_points"] = []
        self.current_record["pain_points"].append({
            "category": category,
            "severity": severity,
            "description": description,
            "turn_index": len(self.current_record["trajectory"]["conversations"]) - 1,
        })

    def on_submit(self):
        """Handle /kajiba submit — scrub, score, preview, confirm, send."""
        # 1. Scrub PII
        scrubbed, scrub_log = self.scrubber.scrub(self.current_record)
        scrubbed["submission"]["scrub_log"] = scrub_log

        # 2. Score quality
        quality = self.scorer.compute_quality_score(scrubbed)
        scrubbed["quality"] = quality

        # 3. Generate content hash for dedup
        scrubbed["record_id"] = self._generate_record_id(scrubbed)
        scrubbed["submission_hash"] = self._generate_submission_hash(scrubbed)

        # 4. Show preview
        self._show_preview(scrubbed)

        # 5. Wait for confirmation (handled by command loop)
        return scrubbed  # Caller handles confirmation + actual submission
```

### 5.4 MVP data flow (Phase 1 — no server)

For the MVP, there is no ingestion API. The flow is:

1. User runs Hermes Agent normally.
2. Kajiba collector captures session data in the background.
3. User runs `/rate` and optionally `/report`.
4. User runs `/kajiba submit` which:
   a. Scrubs PII locally.
   b. Scores quality locally.
   c. Shows preview.
   d. On confirmation, writes to `~/.hermes/kajiba/outbox/record_<id>.jsonl`.
5. User manually submits to HuggingFace via PR (or a helper script: `kajiba-upload` that uses `huggingface_hub` to create a PR).

Phase 2 replaces step 5 with a direct API call.

---

## 6. Project governance and upstream strategy

### 6.1 Standalone phase

During the standalone phase, the project lives at `github.com/<your-org>/kajiba` with:

- Apache 2.0 license (compatible with Hermes Agent's MIT license)
- Independent release cadence
- Own issue tracker and contributor guidelines
- HuggingFace dataset at `<your-org>/kajiba-community`

### 6.2 Upstream proposal criteria

Propose upstream to NousResearch when:

- MVP is stable and documented (schema v0.1 finalized, collector plugin works)
- At least 500 community records collected with quality distribution data
- At least 1 Atropos environment generated and validated from community data
- Community feedback is positive (GitHub stars, Discord discussion)
- You've engaged with NousResearch team on Discord to socialize the project

### 6.3 Upstream integration path

The ideal integration would be:

- Kajiba collector becomes a built-in Hermes Agent skill (shipped but disabled by default)
- `/rate` and `/report` commands added to Hermes core slash commands
- Schema spec published as part of Hermes Agent docs
- Kajiba environments available via `hermes skills install kajiba-*`
- Dataset hosted under `NousResearch/kajiba-community` on HuggingFace

### 6.4 Community incentives

To bootstrap contributions:

- **Leaderboard:** Top contributors by volume and quality tier on the HF dataset page.
- **Attribution:** Every record includes an optional contributor_id. Contributors who opt in get credit in model cards of models trained on the data.
- **Environment naming:** If your submitted trajectories form the nucleus of an Atropos environment, you're credited in the environment README.
- **Governance participation:** Active contributors get voting rights on schema changes and curation policies.

---

## 7. Roadmap summary

| Phase | Timeline | Deliverables |
|-------|----------|-------------|
| **1 — MVP** | Weeks 1-6 | Schema v0.1, collector plugin, /rate + /report commands, local PII scrubber (regex), local quality scorer, JSONL export, manual HF upload script |
| **2 — Pipeline** | Weeks 7-14 | Ingestion API (FastAPI), automated PII scrubber (regex + LLM), dedup layer, schema validator service, `hermes kajiba submit` command, first public HF dataset release |
| **3 — Curation** | Weeks 15-22 | Quality tier system, community voting, DPO pair generator, adversarial detection, dataset browser (HF Spaces), first Atropos environment from community data |
| **4 — Flywheel** | Weeks 23-30 | Environment refresh pipeline, benchmark suite, leaderboard, contribution incentive system, upstream proposal to NousResearch |
| **5 — Scale** | Ongoing | Multi-model benchmarking, cross-harness schema support, federated collection for privacy-sensitive deployments, model training partnerships |
