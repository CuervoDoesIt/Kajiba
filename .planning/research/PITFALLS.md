# Pitfalls Research

**Domain:** Community AI Training Data Pipeline — v1.1 Hermes Plugin + LLM Scrubbing + Fine-Tuning
**Researched:** 2026-04-02
**Confidence:** HIGH (Hermes plugin API fetched from official docs; Ollama/WSL2 pitfalls corroborated by multiple independent sources; QLoRA pitfalls from Unsloth official docs + community issues)

---

## v1.1 Milestone Pitfalls

These pitfalls are specific to the v1.1 work: rewriting the Protocol-based Hermes integration as a real plugin, implementing LLM-based PII scrubbing via a local model, and validating the end-to-end pipeline with a QLoRA fine-tune experiment.

---

### MP-1: Protocol Adapter vs Plugin Directory — Silent Data Loss on Rewrite

**What goes wrong:**
The existing `hermes_integration.py` uses a `HermesAgent` Protocol class wired by external injection. The real Hermes plugin system uses `~/.hermes/plugins/<name>/__init__.py` with a `register(ctx)` function. These are two completely different wiring models. If the rewrite keeps any logic from the Protocol approach — passing an agent object into Kajiba — the plugin will not receive events. `register(ctx)` is called once at startup with a `ctx` object; the agent is never passed in. Any code that stores `self._agent` and calls `self._agent.on()` will silently do nothing, because `ctx` has no `.on()` method. The plugin appears to load but captures zero turns.

**Why it happens:**
Developers carrying mental models from the old design assume the new API accepts a similar agent reference. The Protocol approach felt complete (it compiled, the mock tests passed) so the rewrite path is treated as "minor plumbing" rather than a full behavioral change.

**How to avoid:**
Treat the rewrite as a greenfield module, not a refactor. Delete `hermes_integration.py` and start a new `~/.hermes/plugins/kajiba/` directory. The only connection point is `ctx.register_hook(event_name, callback)`. All six lifecycle events (`on_session_start`, `on_session_end`, `pre_llm_call`, `post_llm_call`, `pre_tool_call`, `post_tool_call`) must be registered in `register(ctx)`. Test by running Hermes and checking that `on_session_start` fires — before writing any data capture logic.

**Warning signs:**
- Plugin loads with no errors but no staging files appear after a session
- Tests are mocking a `HermesAgent` Protocol object, not calling `register(ctx)` with a real or stub `ctx`
- `register_hooks(agent)` still exists in the codebase after the migration

**Phase to address:** Phase 1 of v1.1 milestone — environment setup and plugin scaffold. Verify hook firing before any data capture work.

---

### MP-2: Hook Argument Mismatch Crashes Turn Capture Silently

**What goes wrong:**
Hermes hook callbacks receive different argument sets per event. `on_session_start` receives `session_id, model, platform`. `post_llm_call` receives `session_id, user_message, assistant_response, conversation_history, model, platform`. `post_tool_call` receives `tool_name, args, result, task_id`. A callback that does not accept `**kwargs` will raise `TypeError` when Hermes passes a new argument in a future version, or when calling with an argument set the developer did not anticipate. Hook crashes are isolated — Hermes logs and skips them — so the data pipeline fails silently with no user-visible error.

**Why it happens:**
Developers write tightly-typed function signatures because it looks cleaner and IDEs provide better completion. The spec says `**kwargs` is required for forward compatibility but this looks like boilerplate to skip.

**How to avoid:**
Every hook callback must accept `**kwargs` as its final parameter. This is the official API contract per Hermes docs. Additionally, at startup validation, log which hooks successfully registered so silent skip failures are visible: `logger.info("Kajiba registered hooks: %s", [event for event in registered_events])`. Add a test that calls each callback with an unexpected extra kwarg and verifies no exception propagates.

**Warning signs:**
- Hook callbacks defined without `**kwargs`
- No startup log confirming hook registration
- `on_session_start` fires but `post_llm_call` produces no turns (TypeError on mismatched args)

**Phase to address:** Phase 1 of v1.1 — plugin scaffold. Write the callback signatures before any data capture logic.

---

### MP-3: `pre_llm_call` Context Injection Corrupts Session Data

**What goes wrong:**
`pre_llm_call` is a special hook: it can return `{"context": "..."}` to inject ephemeral system prompt content for that turn. If the Kajiba plugin returns anything from this hook — even accidentally, by having a function that doesn't explicitly `return None` — Hermes will treat the return value as context injection and insert it into the conversation. This corrupts both the live session (the model gets unexpected system context) and the captured data (the conversation_history in subsequent hooks will include the injected content).

**Why it happens:**
Python functions return `None` implicitly, which is safe. The problem occurs when a developer adds a `return` statement to `pre_llm_call` for any reason — returning a status dict, returning early with an empty string — and accidentally matches the injection signature.

**How to avoid:**
The Kajiba plugin should never return anything from `pre_llm_call`. Make this explicit: add a comment `# IMPORTANT: Do not return from this hook. Returning any value injects content into the conversation.` and add a test that verifies the `pre_llm_call` callback returns `None`.

**Warning signs:**
- Unexpected system context appearing in conversation history
- `pre_llm_call` callback has any `return` statement
- Session quality scores drop unexpectedly (injected content distorts coherence scoring)

**Phase to address:** Phase 1 of v1.1 — plugin scaffold, before any pre_llm_call logic is added.

---

### MP-4: HERMES_HOME Profile Isolation Breaks Hardcoded `~/.hermes/kajiba/` Paths

**What goes wrong:**
Kajiba's CLI and collector hardcode `Path.home() / ".hermes" / "kajiba"` as the data directory. In Hermes v0.6.0, the `HERMES_HOME` environment variable was introduced and profiles now use isolated directories (each profile gets its own HERMES_HOME subtree). When a user runs Hermes under a non-default profile, `HERMES_HOME` is set to something like `~/.hermes/profiles/work/`. Kajiba ignores this variable and writes to `~/.hermes/kajiba/`, which is outside the active profile's home. The session data is written to the wrong location and the user cannot find it when they run `kajiba preview`.

Additionally, within the plugin, Hermes provides `get_hermes_home()` for programmatic path access. Using `Path.home() / ".hermes"` instead of `get_hermes_home()` is explicitly documented as wrong.

**Why it happens:**
The path was hardcoded when Hermes had a single fixed home. Profile support was added in v0.5.0 and HERMES_HOME-awareness became required in v0.6.0. Existing code predates this.

**How to avoid:**
In the plugin code, use `get_hermes_home()` from Hermes internals to construct all data paths. In the CLI (which runs outside the plugin context), read `HERMES_HOME` from the environment with fallback to `~/.hermes`. The base data directory should be `get_hermes_home() / "kajiba"` inside the plugin and `Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / "kajiba"` in the CLI. Add tests that set `HERMES_HOME` to a temp directory and verify all file operations land there.

**Warning signs:**
- Staging files appear in `~/.hermes/kajiba/` instead of the active profile's directory
- `kajiba preview` shows no sessions after collecting with a non-default profile
- The string `".hermes"` is hardcoded in CLI or collector code rather than reading the environment

**Phase to address:** Phase 1 of v1.1 — environment setup. Fix before first real session collection.

---

### MP-5: Ollama Context Window Misreport Silently Truncates Long Sessions

**What goes wrong:**
Ollama reports `context_length` as the model's maximum supported context, not the context currently in use. The actual effective context defaults to 2048 tokens unless explicitly set via `num_ctx`. A Hermes coding session with multiple tool call outputs (stack traces, file reads) easily exceeds 2048 tokens. When Kajiba sends these sessions to the local LLM scrubber, Ollama silently truncates the input, and the scrubber sees only the first ~1500 words of the conversation. Names and project identifiers in the tail of the session escape detection.

This was confirmed as a documented known behavior: "the 'context length' value shown displays the maximum context window size the model can support, not what's currently being used."

**Why it happens:**
Developers check Ollama's API response for context length, see a large number (131072 for Llama 3.2), assume they are fine, and never set `num_ctx`. The truncation is silent — the model responds to the truncated input as if it were complete.

**How to avoid:**
Always set `num_ctx` explicitly in the Ollama API call. For PII scrubbing of a Kajiba session, count the tokens in the session text first (use a simple whitespace tokenizer as a proxy: `len(text.split()) * 1.3`). If the estimated token count exceeds a safe threshold, chunk the session into overlapping windows and scrub each chunk. Never rely on Ollama's reported context length to infer actual behavior. Recommended: set `num_ctx: 8192` explicitly, which fits comfortably in 8GB VRAM for 3B models.

**Warning signs:**
- LLM scrubber results are inconsistent for long sessions vs short sessions
- Names appear in the second half of a session's conversation but not in scrubber output
- The Ollama client call does not include `num_ctx` in the options dict

**Phase to address:** Phase 2 of v1.1 — LLM scrubber implementation. Set `num_ctx` in the first API call, add a session length check before calling.

---

### MP-6: LLM PII Scrubber False Positives Corrupt Code Content

**What goes wrong:**
A small LLM used for semantic PII detection (3B class models) has imperfect context discrimination. It misidentifies variable names (`user`, `admin`, `customer`), Python class names (`PersonFactory`, `UserService`), function names in stack traces, and log output as PII. When these are redacted, the resulting dataset record is semantically broken — the model trained on it learns that Python identifiers are personal names, or that stack traces should contain `[REDACTED_NAME]` placeholders. Research confirms "low precision, characterized by a high rate of false positives, can lead to unnecessary replacement of non-PII entities, which can disrupt the semantic integrity of the dataset."

**Why it happens:**
Developers optimizing for privacy recall (catching everything) over precision (only catching real PII) set the LLM's detection threshold too low. The model sees `user = User.objects.get(id=1)` and flags `User` as a personal name because it is capitalized and appears in a human-sounding context.

**How to avoid:**
Implement a two-pass verification architecture: first pass detects candidates, second pass verifies each candidate in context. Use a system prompt that explicitly tells the model to distinguish between: (a) code identifiers that happen to contain common names (`UserService`, `PersonFactory`), (b) string literals containing names (`"John Smith"`, `"Acme Corp"`) which are PII, and (c) technical terms (`username`, `admin`) which are not PII. Only auto-redact high-confidence matches. Flag medium-confidence matches for contributor review in the HITL step rather than auto-redacting. Track false positive rate by testing against a fixture with known non-PII technical content.

**Warning signs:**
- Code variable names like `user`, `admin`, `customer` appear as `[REDACTED_NAME]` in preview
- Stack traces contain redaction placeholders mid-expression
- Quality scores for technical sessions drop unexpectedly after LLM scrubbing

**Phase to address:** Phase 2 of v1.1 — LLM scrubber. Build the two-pass verifier before any automatic redaction runs on real data.

---

### MP-7: Local LLM Scrubbing Blocks the Kajiba Hook Callback Thread

**What goes wrong:**
Hook callbacks in Hermes plugins are called synchronously in the agent's event loop. If `post_llm_call` triggers a local Ollama inference call to scrub the just-captured turn, it blocks the Hermes event loop for 2–15 seconds (inference time for a 3B model on RTX 4070 doing a full-session scrub). The user experiences their agent freezing after every response. If the Ollama call times out, the hook raises an exception. Hermes isolates hook crashes, so the turn data is never captured.

**Why it happens:**
The scrubbing step feels natural to put in `post_llm_call` because the turn data is freshest there. Developers don't account for the inference latency of a local model vs a fast regex operation.

**How to avoid:**
Never call Ollama synchronously from a hook callback. Collect raw turn data in hooks (fast, in-memory only) and defer all LLM scrubbing to `on_session_end` or, better, to the CLI's `kajiba preview` / `kajiba submit` commands. The plugin's job is capture only — scrubbing happens when the user explicitly reviews the session. This matches the existing design intent: the collector stores raw data and the pipeline processes it separately. The LLM scrubber belongs in `scrubber_llm.py` and is called from the CLI, not from the hook.

**Warning signs:**
- Ollama client import in `hermes_integration.py` or the plugin's `__init__.py`
- Any `ollama.chat()` or `requests.post()` call inside a hook callback
- Users report Hermes "freezing" after each response

**Phase to address:** Phase 2 of v1.1 — LLM scrubber. Enforce the capture-in-hook, scrub-in-CLI architectural separation before implementing any inference calls.

---

### MP-8: WSL2 CUDA Driver Overwrite Breaks Ollama GPU Acceleration

**What goes wrong:**
When setting up the WSL2 environment for Hermes + Ollama, installing the CUDA Toolkit inside WSL2 using the standard `cuda` or `cuda-drivers` meta-packages overwrites the NVIDIA GPU stub (`libcuda.so`) that WSL2 provides from the Windows host driver. After this overwrite, `nvidia-smi` stops working inside WSL2, Ollama falls back to CPU-only inference, and the RTX 4070's 8GB VRAM goes unused. Inference that should take 2 seconds takes 120 seconds. The failure is not obvious — Ollama starts normally and responds, just at 60x slower speed.

**Why it happens:**
The WSL2 CUDA setup requires installing only `cuda-toolkit-12-x` (or equivalent), never the full `cuda` or `cuda-drivers` packages. This is a non-obvious requirement that contradicts normal CUDA installation instructions. First-time WSL2 users follow generic CUDA install guides that do not account for the WSL2 stub architecture.

**How to avoid:**
Follow the NVIDIA WSL2 CUDA user guide exactly. Install `cuda-toolkit-12-x` only — no `cuda-drivers`. Verify the GPU stub is intact: `ls -la /usr/lib/x86_64-linux-gnu/libcuda.so` should be a symlink, not a real file. After Ollama install, run `ollama run llama3.2:3b` and immediately check `nvidia-smi` in a second terminal to confirm VRAM is being used. If VRAM shows 0 usage, the stub was overwritten. Recovery: uninstall all CUDA packages, reinstall the WSL2-specific toolkit only.

Additionally, keep all models and working data inside WSL2's native filesystem (`~/` or `/home/user/`) — not under `/mnt/c/`. The 9P protocol used for Windows drive mounts is 3-5x slower than WSL2's native ext4 and causes severe model loading latency.

**Warning signs:**
- `nvidia-smi` inside WSL2 reports "No devices found" or fails entirely
- Ollama inference speed is measurably slower than expected (check tokens/second vs published 40+ t/s for Q4 7B)
- `/usr/lib/x86_64-linux-gnu/libcuda.so` exists as a real file rather than a symlink
- Ollama models stored under `/mnt/c/Users/...`

**Phase to address:** Phase 1 of v1.1 — WSL2 + Hermes + Ollama environment setup. Validate GPU acceleration on day 1. Never proceed to collection phases without confirmed GPU inference.

---

### MP-9: Ollama Network Binding Blocks Hermes-to-Ollama Communication in WSL2

**What goes wrong:**
Ollama inside WSL2 binds to `127.0.0.1:11434` by default. When Hermes Agent runs inside WSL2 and calls Ollama, this works. But if Hermes Agent runs on the Windows host (not in WSL2) and tries to reach Ollama in WSL2 at `localhost:11434`, the connection is refused. Windows `localhost` does not automatically route to WSL2's loopback. Similarly, if either component is containerized, triple-NAT (WSL2 + Docker + container) makes `localhost` resolution completely wrong.

**Why it happens:**
Developers assume `localhost` is universal. WSL2's network isolation means Windows and WSL2 have separate loopback interfaces.

**How to avoid:**
Run both Hermes Agent and Ollama inside WSL2 for the development environment. Set `OLLAMA_HOST=0.0.0.0:11434` in the WSL2 environment so Ollama binds to all interfaces, making it reachable from the Windows host at `http://[WSL2-IP]:11434`. Document the exact network topology in the environment setup guide so contributors who reproduce the setup don't hit this on first run.

**Warning signs:**
- Ollama calls fail with `Connection refused` from Hermes
- `OLLAMA_HOST` environment variable is not set
- Hermes and Ollama are running in different network namespaces (one on Windows host, one in WSL2)

**Phase to address:** Phase 1 of v1.1 — environment setup. Add a network connectivity smoke test to the setup validation checklist.

---

### MP-10: Kajiba's ShareGPT-Extended Format Is Not Directly Ingestible by Training Frameworks

**What goes wrong:**
Kajiba records use a `sharegpt_extended` format type with non-standard fields: `record_id`, `hardware_profile`, `quality_metadata`, `submission_metadata`, `pain_points`, `outcome_signals`. Training frameworks (Unsloth, Axolotl, LlamaFactory) expect either vanilla ShareGPT (`conversations` list with `from`/`value` keys) or ChatML format. When a consumer downloads Kajiba records and feeds them directly to Unsloth, training fails with a `KeyError: 'instruction'` or `KeyError: 'conversations'` error, or the framework silently ingests only the conversation turns and ignores all metadata.

Kajiba's `KajibaRecord.to_sharegpt()` method exists to strip to vanilla ShareGPT, but consumers who download JSONL from the dataset repository may not know they need to call this method first.

**Why it happens:**
The extended format is correct for Kajiba's pipeline purposes (capturing rich context). The problem is the gap between what Kajiba publishes and what training frameworks consume. Consumers assume the format is training-ready as-is.

**How to avoid:**
The published dataset should include two separate JSONL variants per shard: (1) full Kajiba records for pipeline consumers, and (2) vanilla ShareGPT strips for training consumers. Alternatively, publish conversion scripts alongside the dataset. Document clearly in the catalog README that `kajiba_full.jsonl` requires pre-processing and that `sharegpt.jsonl` is the training-ready form. The `kajiba download` command should accept a `--format sharegpt` flag that applies `to_sharegpt()` on download.

**Warning signs:**
- No training-ready format variant in the published dataset
- `kajiba download` has no format conversion flag
- The dataset README does not mention pre-processing requirements
- Consumer reports a `KeyError` when loading Kajiba data into their training framework

**Phase to address:** Phase 3 of v1.1 — end-to-end validation including the fine-tune experiment. Discover and fix before declaring the pipeline "validated."

---

### MP-11: QLoRA Fine-Tune on 8GB VRAM Requires Exact Configuration — Defaults Cause OOM

**What goes wrong:**
The RTX 4070 has 8GB VRAM. A Llama 3.2 3B model in 4-bit quantization uses approximately 2GB for weights. That sounds comfortable. But the training overhead — gradient checkpoints, optimizer states, KV cache for the training context window, activation buffers — pushes peak VRAM to 7–9GB at default settings. With default `per_device_train_batch_size=2`, `gradient_accumulation_steps=4`, and `max_seq_length=2048`, the training job OOMs 2–3 minutes in, after the initial model load appears successful.

**Why it happens:**
The model load succeeds and the first few steps run, creating a false signal that training will complete. VRAM usage spikes during the forward pass of longer sequences in the batch. With a small dataset and variable sequence lengths, early batches may all be short (fitting in VRAM) while later batches contain the long sessions that cause OOM.

**How to avoid:**
Use these specific settings for RTX 4070 8GB with Llama 3.2 3B:
- `per_device_train_batch_size=1`
- `gradient_accumulation_steps=8` (maintains effective batch of 8)
- `max_seq_length=2048`
- `optim="paged_adamw_8bit"` (paged optimizers move optimizer states to CPU on spike)
- `fp16=True` (not bf16 for RTX 4070 Ampere-generation)
- Unsloth's `load_in_4bit=True` with NF4 quantization

Run `nvidia-smi dmon -s m` in a second terminal to monitor peak VRAM during the first 50 steps. If peak exceeds 7.5GB, reduce `max_seq_length` to 1024. Start from the Instruct model variant (not Base) — it requires less data to produce useful fine-tuning results.

**Warning signs:**
- Training job completes model load but OOMs at step 3–10
- `per_device_train_batch_size > 1` with 8GB VRAM
- `optim="adamw_torch"` instead of a paged optimizer
- No VRAM monitoring during first training run

**Phase to address:** Phase 4 of v1.1 — QLoRA fine-tune experiment. Establish the working configuration before collecting more than minimal data.

---

### MP-12: Chat Template Mismatch Between Kajiba's ShareGPT and Llama 3.2's Expected Format

**What goes wrong:**
Llama 3.2 3B Instruct expects conversations in the `<|start_header_id|>` / `<|end_header_id|>` / `<|eot_id|>` format (Llama 3 chat template). Kajiba's `to_sharegpt()` output uses the vanilla ShareGPT `from`/`value` structure. When this is fed directly to Unsloth or LlamaFactory without applying the chat template, the model trains on raw `{"from": "human", "value": "..."}` JSON strings instead of properly formatted conversation turns. The resulting fine-tuned model is trained on format garbage and produces format garbage at inference.

**Why it happens:**
Training frameworks document "supports ShareGPT format" but that means "we will apply the appropriate chat template automatically" — which requires configuring which template to use. The documentation assumes users know to call `standardize_sharegpt()` and set `chat_template="llama-3"` explicitly. Kajiba's format is close enough to standard ShareGPT that no error is raised — the mismatch is silent.

**How to avoid:**
In Unsloth: call `standardize_sharegpt(dataset)` on the Kajiba-converted data, then set `tokenizer.chat_template` to the Llama 3 template explicitly. In LlamaFactory: set `template: llama3` in the training config. Always inspect 3–5 examples of tokenized training text (use `tokenizer.decode(input_ids[0])`) before running training to verify the `<|start_header_id|>` markers are present. The absence of these markers is the tell — training will still start but the model will learn the wrong format.

**Warning signs:**
- Tokenized training examples show raw JSON strings instead of `<|start_header_id|>user<|end_header_id|>...`
- Training loss is unusually low from epoch 1 (the model is memorizing JSON format, not learning conversation patterns)
- `standardize_sharegpt()` is not called in the training script

**Phase to address:** Phase 4 of v1.1 — QLoRA fine-tune experiment. Add a pre-training data inspection step to the experiment checklist.

---

### MP-13: HITL Review Workflow Built as an Afterthought Breaks Pipeline Atomicity

**What goes wrong:**
HITL is added to the pipeline by inserting `input()` prompts between pipeline steps. The result is a fragile script that cannot be interrupted, resumed, or run non-interactively. If the contributor closes the terminal mid-review, the session is lost — the record was partially processed (regex-scrubbed but not LLM-scrubbed, or LLM-scrubbed but not scored). The next run starts over from the beginning. With 10+ sessions to review, this becomes frustrating enough that contributors skip the review step entirely.

**Why it happens:**
HITL is treated as a "pause for user input" problem rather than a "pipeline state persistence" problem. The interactive prompt is the easiest implementation but has zero durability.

**How to avoid:**
Persist pipeline stage as explicit state in the staging file. Each record should carry a `pipeline_stage` field with values like `captured`, `regex_scrubbed`, `llm_reviewed`, `scored`, `approved`. The HITL review step reads from `pipeline_stage == "llm_reviewed"` records, shows them, accepts input, and updates `pipeline_stage` to `approved` or `rejected`. If the user exits, re-running `kajiba review` resumes from where it left off. This is a 5-field addition to the schema and a loop replacement in the CLI, but the difference in usability is significant.

**Warning signs:**
- HITL review is a single-pass script with no resume capability
- Interrupted reviews result in records stuck in an intermediate state with no way to recover
- The staging file format has no `pipeline_stage` or equivalent field

**Phase to address:** Phase 3 of v1.1 — HITL session collection. Design the state machine before writing any interactive prompts.

---

## Phase 1 MVP Pitfalls (Preserved from v1.0 Research)

The following pitfalls were identified during v1.0 development and remain relevant. They are preserved here for completeness; see the original research for full detail.

---

### CP-1: Regex Scrubbing Creates a False Sense of Complete PII Protection

**What goes wrong:**
A regex scrubber passes all tests, ships, and contributors begin submitting real session data. The pipeline scrubs paths, API keys, emails, and IPs. But a session like "Tell John at Acme Corp to deploy the Whisperforge project on the staging box" passes through completely untouched. Real names, employer names, and project names — the most identifying information in a coding session — are invisible to regex. Researchers found that regex-only approaches achieve roughly 65% recall on PII, meaning up to 35% of sensitive content escapes. Community trust, once broken by a PII leak incident, is extremely difficult to rebuild.

**Why it happens:**
Regex matches form, not meaning. It cannot distinguish a random alphanumeric string from a colleague's name or your company's internal project name. Teams ship the regex layer because it works well on structured PII (emails, IPs, API keys) and mistake "tests pass" for "privacy is solved."

The current codebase (`scrubber_llm.py`) has this stub: `raise NotImplementedError`. The spec calls for an LLM-based semantic layer. This gap is the single largest privacy risk in Kajiba.

**How to avoid:**
Implement the two-pass pipeline as specced: regex first (fast, deterministic), LLM semantic pass second (catches names, orgs, projects). The LLM pass must run locally — no API calls — using Ollama against the contributor's local model. Auto-redact high-confidence matches, flag medium-confidence for contributor review in the preview step. Never publish a record without both passes completing.

**Warning signs:**
- Sessions containing first names pass preview without any redactions
- Contributor usernames or company names appear in exported JSONL
- Test suite only covers structured PII (emails, IPs, keys) with no semantic PII tests
- The `[llm-scrub]` optional dependency group in `pyproject.toml` has no packages listed

**Phase to address:** Phase 2 of v1.1 milestone — LLM scrubber implementation. This must ship before any real contributor data is accepted.

---

### CP-2: Consent Level Declared But Never Enforced — Silent Privacy Breach

**What goes wrong:**
A contributor configures `consent_level: anonymous`, reasonably expecting that their conversation text will not leave their machine. The pipeline accepts the setting, stores it in the schema, and then exports every field anyway — because `export_record()` and the `submit` command ignore the field entirely.

**Why it happens:**
The schema field was added to represent intent. The enforcement logic was deferred and never revisited.

**How to avoid:**
Implement `apply_consent_level(record, level)` that strips fields according to the consent matrix before any data is written to disk or transmitted. Call it as the last step in `export_record()` and in the `submit` command.

**Warning signs:**
- `consent_level` field exists in schema but no function references it at export time
- `submit` command produces identical output regardless of consent level configured

**Phase to address:** Phase 2 of v1.1 or whichever phase introduces real contributor data collection.

---

### CP-3: Metadata Fingerprinting — Hardware Profiles Uniquely Identify Contributors

**What goes wrong:**
A contributor with uncommon hardware submits a session. The hardware profile records the exact GPU model, precise RAM, and exact submission timestamp. This combination is likely unique worldwide.

**How to avoid:**
Round VRAM and RAM to standard tiers. Apply timestamp jitter of ±0-30 minutes. Generalize rare GPU names to category strings. Strip OS minor version.

**Phase to address:** Same as CP-2.

---

### CP-4: Dataset Poisoning via Unvalidated Community Contributions

**What goes wrong:**
An adversary submits crafted session data containing a backdoor trigger. Research demonstrates as few as 250 malicious documents can successfully backdoor LLMs.

**How to avoid:**
PR-based contribution (not direct push). Submission rate limiting. Content hash deduplication. See full CP-4 entry in original research for detail.

**Phase to address:** GitHub repo design phase. The PR-based submission model is the structural defense.

---

### CP-5: IP Regex False Positives Corrupt Technical Content

**What goes wrong:**
The IP regex matches Python version strings (`3.11.0.0`), CUDA versions, and library version numbers, replacing them with `[REDACTED_IP]`.

**How to avoid:**
Add negative lookbehind/lookahead for version-string contexts. Add tests for false positives.

**Phase to address:** Regression exists. Fix in Phase 1 of v1.1 before collecting real data.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Scrub in hook callback (synchronous) | Simple code | Blocks Hermes event loop; freezes agent | Never |
| Use `~/.hermes` hardcoded path | Zero config | Breaks under HERMES_HOME profiles | Never (fix in v1.1 Phase 1) |
| Auto-redact all LLM detections | Maximum privacy | Corrupts code content; breaks fine-tuning | Never without confidence threshold |
| Skip `**kwargs` in hook callbacks | Cleaner signatures | Silent breakage on Hermes updates | Never (required by API contract) |
| Store quality score in memory only | Fast iteration | Lost on restart; inconsistent history | MVP only — must persist before any data collection |
| Single-pass HITL (no resume) | Fast to implement | Lost work on interruption | MVP / first test only |
| Use `num_ctx` default in Ollama | Zero config | Silent context truncation on long sessions | Never for PII scrubbing |
| Train on unsanitized Kajiba JSONL | Skip conversion step | Framework errors or silent format mismatch | Never |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Hermes plugin `register(ctx)` | Calling `ctx.on(event, cb)` (Protocol API) | `ctx.register_hook(event_name, callback)` — completely different method |
| Hermes `post_tool_call` | Accessing `result` as Python dict | `result` is a JSON string — call `json.loads(result)` before use |
| Ollama Python SDK | Calling `ollama.chat()` without `options={"num_ctx": N}` | Always set `num_ctx` explicitly; default is 2048 regardless of model capacity |
| Ollama in WSL2 | Installing `cuda` or `cuda-drivers` meta-package | Install `cuda-toolkit-12-x` only; never the meta-package that includes drivers |
| Kajiba JSONL to Unsloth | Feeding `sharegpt_extended` JSONL directly | Call `to_sharegpt()` first, then `standardize_sharegpt()`, then set `chat_template` |
| LlamaFactory with Kajiba data | No template config | Set `template: llama3` in training YAML; verify tokenized output before training |
| HERMES_HOME profiles | `Path.home() / ".hermes"` hardcoded | Use `get_hermes_home()` inside plugin; read `HERMES_HOME` env var in CLI |
| `pre_llm_call` hook | Returning a dict for any reason | Must return `None` explicitly; any non-None return injects context into the session |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Synchronous Ollama call in hook | Hermes freezes 2-15s per turn | Move all inference to CLI review step | Every session with LLM scrubbing enabled |
| Large context (`num_ctx=128000`) with 3B model on 8GB | OOM crash, model unloads | Use `num_ctx=8192` max for scrubbing tasks | Any session longer than ~6000 tokens at default |
| Default Ollama parallel slots (4 concurrent) | Multiple models loaded, VRAM exhausted | Set `OLLAMA_MAX_LOADED_MODELS=1` for 8GB VRAM | When Hermes and Kajiba both use Ollama simultaneously |
| Training batch size > 1 on 8GB with 3B model | OOM at step 3-10 | `batch_size=1, gradient_accumulation=8, paged_adamw_8bit` | RTX 4070 8GB consistently |
| Models stored on `/mnt/c/` in WSL2 | 3-5x slower model loading | Store all models in WSL2 native filesystem | Immediately noticeable on first model pull |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| LLM scrubber prompt contains raw session text without role separation | Prompt injection: session content manipulates scrubber behavior | Use structured JSON input format; never embed raw session text in system prompt |
| Logging full `ScrubResult.original` values | PII appears in log files | Store category + hash only; never log matched text |
| Ollama bound to `0.0.0.0` permanently in production | Any process on the machine can call the inference endpoint | Use `0.0.0.0` only for cross-WSL2 connectivity; restrict to localhost for production use |
| HITL approval stored only in memory | Contributor approves session, process crashes, re-review required | Persist `pipeline_stage` to disk on every state transition |

---

## "Looks Done But Isn't" Checklist

### Plugin Integration
- [ ] **Hook registration** — `register(ctx)` exists in `__init__.py`. Does `hermes plugins list` show kajiba as loaded? Does `on_session_start` actually fire on a new session?
- [ ] **Hook argument safety** — All callbacks have `**kwargs`. Tested with an extra unknown kwarg?
- [ ] **HERMES_HOME awareness** — Plugin uses `get_hermes_home()`. CLI reads `HERMES_HOME` env var. Tested with a non-default `HERMES_HOME`?
- [ ] **`pre_llm_call` safety** — Callback returns `None` explicitly. No accidental context injection?

### LLM Scrubber
- [ ] **Context window** — `num_ctx` explicitly set in every Ollama API call. Not relying on default?
- [ ] **False positive rate** — Tested against a fixture containing Python code with `user`, `admin`, `customer` variable names. Are these not redacted?
- [ ] **Blocking prevention** — No Ollama calls inside hook callbacks. Scrubbing deferred to CLI review step?
- [ ] **Chunking for long sessions** — Sessions exceeding 6000 tokens are chunked before scrubbing?

### Fine-Tune Experiment
- [ ] **Format conversion** — Training data went through `to_sharegpt()` and `standardize_sharegpt()` before training?
- [ ] **Chat template** — Tokenized training examples contain `<|start_header_id|>` markers?
- [ ] **VRAM config** — `batch_size=1`, `paged_adamw_8bit`, `max_seq_length<=2048` for 8GB?
- [ ] **Peak VRAM monitored** — `nvidia-smi dmon` run during first 50 training steps?

### Environment
- [ ] **GPU acceleration confirmed** — `nvidia-smi` works inside WSL2. VRAM used during Ollama inference?
- [ ] **CUDA toolkit type** — Only `cuda-toolkit-12-x` installed. Not `cuda` or `cuda-drivers` meta-package?
- [ ] **Ollama binding** — `OLLAMA_HOST=0.0.0.0:11434` set if cross-WSL2 access needed?
- [ ] **File location** — All models and data inside WSL2 native filesystem, not `/mnt/c/`?

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| CUDA stub overwritten | MEDIUM | Uninstall all CUDA packages; reinstall `cuda-toolkit-12-x` only; verify stub restored with `ls -la /usr/lib/x86_64-linux-gnu/libcuda.so` |
| Hook callback registered wrong API | LOW | Replace `ctx.on()` with `ctx.register_hook()`; restart Hermes; verify events fire |
| HERMES_HOME path mismatch | LOW | Add `HERMES_HOME` env var support; migrate existing staging files to new path |
| LLM scrubber causing high false positives | MEDIUM | Raise confidence threshold; add code identifier exclusion list to system prompt; re-review affected sessions |
| Training OOM on step 3-10 | LOW | Reduce `max_seq_length` to 1024; switch to `paged_adamw_8bit`; restart training from scratch |
| Chat template mismatch discovered after training | HIGH | Retokenize dataset with correct template; full retraining required — no partial fix |
| PII leak discovered in published dataset | HIGH | Take dataset offline; re-scrub with improved LLM scrubber; notify contributors; document incident; re-publish |

---

## Pitfall-to-Phase Mapping

| Pitfall | Phase | Verification |
|---------|-------|--------------|
| MP-1: Protocol vs plugin wiring | v1.1 Phase 1 | `on_session_start` fires in live Hermes session |
| MP-2: Hook argument mismatch | v1.1 Phase 1 | All callbacks have `**kwargs`; tested with unknown kwarg |
| MP-3: `pre_llm_call` context injection | v1.1 Phase 1 | Callback returns `None`; no injected context in session history |
| MP-4: HERMES_HOME path breakage | v1.1 Phase 1 | Test with `HERMES_HOME=/tmp/test` — data lands in `/tmp/test/kajiba/` |
| MP-5: Ollama context truncation | v1.1 Phase 2 | All Ollama calls include explicit `num_ctx`; long session scrubs match short session accuracy |
| MP-6: LLM scrubber false positives | v1.1 Phase 2 | Fixture with Python code variables — none redacted as PII |
| MP-7: Blocking hook callback | v1.1 Phase 2 | No Ollama imports in plugin code; scrubbing only in CLI |
| MP-8: WSL2 CUDA stub overwrite | v1.1 Phase 1 | `nvidia-smi` works in WSL2; VRAM in use during inference |
| MP-9: Ollama network binding | v1.1 Phase 1 | Hermes can reach Ollama; `OLLAMA_HOST` documented |
| MP-10: Kajiba format incompatibility | v1.1 Phase 4 | Training framework loads data without KeyError; no raw JSON in tokenized examples |
| MP-11: QLoRA OOM on 8GB | v1.1 Phase 4 | Training completes 1 epoch without OOM; peak VRAM < 7.5GB |
| MP-12: Chat template mismatch | v1.1 Phase 4 | Tokenized examples contain `<|start_header_id|>` markers |
| MP-13: HITL workflow fragility | v1.1 Phase 3 | Interrupted review resumes from correct stage on restart |
| CP-1: Regex-only scrubbing | v1.1 Phase 2 | Semantic PII test fixture: names/orgs caught by LLM pass |
| CP-2: Consent level unenforced | v1.1 Phase 2 | `anonymous` export contains no conversation text |
| CP-5: IP regex false positives | v1.1 Phase 1 | Python version strings not redacted in preview |

---

## Sources

### Hermes Agent Plugin API
- [Build a Hermes Plugin | Hermes Agent docs](https://hermes-agent.nousresearch.com/docs/guides/build-a-hermes-plugin/) — Hook events, ctx methods, plugin.yaml structure, handler gotchas (HIGH confidence — official docs)
- [Hermes Agent v0.6.0 Release Notes](https://github.com/NousResearch/hermes-agent/blob/main/RELEASE_v0.6.0.md) — HERMES_HOME change, `get_hermes_home()` requirement (HIGH confidence — official release notes)
- [FAQ & Troubleshooting | Hermes Agent](https://hermes-agent.nousresearch.com/docs/reference/faq/) — Provider pitfalls, Ollama context length misreport (HIGH confidence — official docs)
- [Issue #3505 — gateway message queue data loss](https://github.com/NousResearch/hermes-agent/issues/3505) — Turn capture race condition (MEDIUM confidence — open issue, no fix merged)

### WSL2 + Ollama + GPU
- [CUDA on WSL User Guide — NVIDIA](https://docs.nvidia.com/cuda/wsl-user-guide/index.html) — Driver installation requirements, stub architecture (HIGH confidence — official NVIDIA docs)
- [Enable NVIDIA CUDA on WSL 2 — Microsoft Learn](https://learn.microsoft.com/en-us/windows/ai/directml/gpu-cuda-in-wsl) — Windows-side driver requirements (HIGH confidence — official Microsoft docs)
- [WSL2 + Ollama on Windows: Complete Setup Guide | InsiderLLM](https://insiderllm.com/guides/wsl2-ollama-windows-setup-guide/) — File system performance, network binding (MEDIUM confidence — community guide)
- [Ollama Hardware Support](https://docs.ollama.com/gpu) — GPU layer offloading, VRAM requirements (HIGH confidence — official Ollama docs)
- [Ollama Context Length docs](https://docs.ollama.com/context-length) — `num_ctx` vs reported context length (HIGH confidence — official docs)
- [Issue #10829 — OLLAMA_CONTEXT_LENGTH ignored](https://github.com/ollama/ollama/issues/10829) — Context length bug confirmation (MEDIUM confidence — open issue)

### QLoRA Fine-Tuning
- [Fine-tuning LLMs Guide | Unsloth Documentation](https://unsloth.ai/docs/get-started/fine-tuning-llms-guide) — OOM prevention, chat template requirements (HIGH confidence — official Unsloth docs)
- [Chat Templates | Unsloth Documentation](https://docs.unsloth.ai/basics/chat-templates) — Llama 3 template requirements (HIGH confidence — official docs)
- [LoRA & QLoRA Best Practices | QuarkAndCode](https://medium.com/@QuarkAndCode/lora-qlora-llm-fine-tuning-best-practices-setup-pitfalls-c8147d34a6fd) — Training configuration pitfalls (MEDIUM confidence — community article)
- [Databricks: Finetune Llama-3.2-3B with Unsloth](https://docs.databricks.com/aws/en/machine-learning/ai-runtime/examples/tutorials/sgc-finetune-llama-unsloth) — Confirmed 8GB VRAM configuration (MEDIUM confidence — official Databricks docs)

### PII Detection
- [LLM Gateway for PII Detection | HuggingFace Cookbook](https://huggingface.co/learn/cookbook/llm_gateway_pii_detection) — False positive/negative analysis (MEDIUM confidence — official HuggingFace)
- [Hybrid Methods for Multilingual PII Detection — arxiv](https://arxiv.org/pdf/2510.07551) — Recall drop without regex (HIGH confidence — peer-reviewed)
- [Smarter PII Handling in LLMs | FirstSource](https://www.firstsource.com/insights/blogs/when-privacy-meets-performance-smarter-way-handle-pii-llms) — Precision vs recall tradeoff in code contexts (MEDIUM confidence — industry article)

### HITL
- [Human-in-the-Loop Best Practices & Common Pitfalls | Parseur](https://parseur.com/blog/hitl-best-practices) — Afterthought anti-pattern, state persistence requirements (MEDIUM confidence — industry article)

---
*Pitfalls research for: Kajiba v1.1 — Hermes Plugin Integration, LLM PII Scrubbing, QLoRA Fine-Tuning*
*Researched: 2026-04-02*
