# Phase 14: Live Experiment Capture - Research

**Researched:** 2026-06-06
**Domain:** Integration / cross-milestone bridge (Hermes v0.15.x plugin hooks → v1.2 experiment store). No new schema, no new persistence module.
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Env-var / config opt-in. The shared plugin reads a flag (`KAJIBA_EXPERIMENT=1`) at `on_session_start` and routes the whole session to experiment capture. Flag absent ⇒ **exactly today's coding-session capture, unchanged** (no regression). Trigger must NOT depend on a Hermes command/slash-command surface; plugin registers ONLY the four confirmed v0.15.x hooks (`on_session_start`, `post_llm_call`, `post_tool_call`, `on_session_end`). Inference from session metadata was rejected (misclassification = privacy risk).
- **D-02:** Whole opted-in session = one eval run = one `ExperimentRecord`. No in-session segment markers.
- **D-03:** `local_model_output` = the final assistant response. Full conversation preserved in `trajectory` (D-06). NOTE: this field feeds `compute_record_id()` → finalize-once concern.
- **D-04:** `task_description` = the first user turn. `task_category` and `experiment_type` come from optional env vars with defaults (suggested: category `"coding"`, type `"model_evaluation"` — must be a valid `EXPERIMENT_TYPES` value). Planner picks exact env-var names; keep them in the `KAJIBA_EXPERIMENT*` namespace.
- **D-05:** `eval_score` = documented placeholder `0.0` at capture (captured-but-unscored, NOT "scored zero"). Real score filled later via `kajiba experiment score`/`review`. Schema is frozen — `eval_score` is required and cannot be made nullable.
- **D-06:** Populate `ExperimentRecord.trajectory` with the full captured session (the optional field designed for exactly this).
- **D-07:** Mode flag on the existing `KajibaCollector` — shared buffering, divergent finalize. `on_session_start` sets `self._experiment_mode` from the trigger; turn/tool buffering identical to coding path. Experiment finalize builds an `ExperimentRecord` via Phase 11's `build_experiment_record` and writes via `log_experiment()` → `EXPERIMENTS_DIR`, fully bypassing staging/outbox/continuous auto-submit. Rejected: capture-as-`KajibaRecord`-then-convert (privacy risk); separate `ExperimentCollector` (more refactor than one requirement warrants).
- **D-08 (derived):** In experiment mode the collector must never touch `STAGING_DIR`/`OUTBOX_DIR` or the `contribution_mode == "continuous"` auto-submit branch. Only write target is `EXPERIMENTS_DIR` via `log_experiment()`.
- **D-09:** Store raw at capture; scrub/score/review/drift all run later via existing CLI subcommands. Hard rule: **scrub is a CLI step, never in a hook.** Rejected: auto-scrub at finalize.
- **D-10:** Reviewer model is NOT in the live loop; `reviewer_model`/`reviewer_critique` stay `None` at capture.

### Claude's Discretion (researcher/planner to resolve — captured below, not re-asked)
- **Finalize-once for experiments (CORRECTNESS — must solve):** see `## Common Pitfalls` Pitfall 1 and `## Architecture Patterns` Pattern 2. `on_session_end` is turn-scoped (fires after every `run_conversation` turn AND at CLI exit). `local_model_output` changes each turn and feeds `compute_record_id()` → naive per-turn writes emit N different `exp_<id>.json` files.
- **`experiment_id` derivation for a live run:** recommend `live_<session_id>` scheme (see Pattern 2). This is what makes the content-addressed ID stable across turns.
- **`local_model` metadata reuse:** reuse `self._model_metadata` (assembled via `_extract_model_metadata`/`_enrich_from_ollama`/`_build_metadata_and_hardware`) directly as `ExperimentMetadata.local_model`. See `## Architecture Patterns` Pattern 3.
- **Remote model under "eval mode":** `local_model` may hold a remote model (`is_local=false`); acceptable, do not block capture on locality.
- **Exact env-var names + defaults** and where the flag is read/stored on the collector. See `## Architecture Patterns` Pattern 1.

### Deferred Ideas (OUT OF SCOPE)
- Auto-scoring/scrubbing at capture (D-09 rule conflict) — manual post-capture step.
- In-session eval segmentation (multiple eval records per session) — needs a verified in-session boundary signal.
- Practice-project / analysis-export integration supplying a real `eval_score` at write time → **Phase 15** (EEXP-01/02).
- Reviewer-model critique, `lessons_learned`, drift detection → **Phase 13** (shipped; run after capture).
- Eval scoring + experiment-aware scrub → **Phase 12** (shipped; run after capture as CLI steps).
- Any new community-publish path — experiments stay private/no-publish (locked).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ECAP-01 | An eval run performed inside a live Hermes session is captured into an `ExperimentRecord` through the shared plugin hooks (depends on v1.1 Phase 6–7). | Integration points fully mapped: trigger flag in `on_session_start` (Pattern 1), shared turn/tool buffer reused unchanged, divergent finalize in `on_session_end` (Pattern 2), `self._model_metadata` → `ExperimentMetadata.local_model` (Pattern 3), `build_experiment_record`+`log_experiment` write path verified (Pattern 4). Finalize-once mechanism solved (Pitfall 1). No-regression mechanism verified (Pitfall 2). |
</phase_requirements>

## Summary

Phase 14 is a pure integration/bridge phase: it joins the v1.1 live-capture machinery (plugin + `KajibaCollector` turn/tool buffer) to the v1.2 experiment store (`build_experiment_record` + `log_experiment` → `EXPERIMENTS_DIR`). **Zero new schema, zero new persistence module.** The entire deliverable is (a) a mode flag set in `on_session_start` from an env var, (b) a divergent finalize branch in `on_session_end` that builds an `ExperimentRecord` instead of a `KajibaRecord`, and (c) a finalize-once mechanism so the turn-scoped `on_session_end` does not emit N files.

The single load-bearing correctness item is **finalize-once for a content-addressed record.** The coding path sidesteps this two ways: ad-hoc mode writes a *fixed* filename `session_{id}.json` and overwrites it on every per-turn `on_session_end` firing; continuous mode uses a `self._finalized` boolean guard. The experiment path cannot rely on a fixed filename because `ExperimentRecord.compute_record_id()` hashes `local_model_output` (the final assistant response, D-03), which **changes every turn** — so per-turn writes would produce a different `exp_<hash>.json` each turn. The recommended fix combines both existing techniques: derive a session-stable `experiment_id` (`live_<session_id>`), set `started_at` once at session start, capture `task_description` (first user turn) once, and re-finalize on every `on_session_end` writing through the in-place overwrite path keyed on those stable fields — OR (simpler and matching the spirit of the coding `_finalized` guard) accumulate across turns and write exactly once. Both are detailed below; the recommended approach is **re-finalize-every-end via `update_experiment` with a session-stable identity** because it survives a hard CLI exit where a "final end" event may never arrive distinctly.

SC#2 (structural parity with `kajiba experiment log`) is satisfied **by construction**: live capture routes through the same `build_experiment_record` / `log_experiment` functions the deliberate CLI path uses, so the on-disk structure is identical by definition. The only systematic differences are a populated `trajectory` and the `0.0` placeholder score — both intended.

**Primary recommendation:** Add `self._experiment_mode` (+ `self._experiment_type`/`self._task_category` read from env at `on_session_start`), branch `on_session_end` to an experiment finalize that builds via `build_experiment_record(... model=self._model_metadata, hardware=self._hardware, trajectory=<built Trajectory>)` and writes via `log_experiment`/`update_experiment` to `EXPERIMENTS_DIR`, keyed on a session-stable `experiment_id = f"live_{session_id}"`. Leave the coding path byte-for-byte unchanged when the flag is absent.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Eval-mode trigger detection | Collector (`on_session_start`) | Plugin hooks (pass-through) | Env var read at session start is the single authoritative branch point (D-01); plugin hooks remain dumb dispatchers. |
| Turn/tool buffering | Collector (`on_llm_turn`/`on_tool_call`) | — | Shared, identical for both kinds (D-07); no branching here. |
| Field mapping (turns → experiment fields) | Collector finalize branch | Schema (`build_experiment_record`) | Collector knows the buffered turns; the convenience constructor assembles the nested model. |
| Experiment persistence | `experiment_store` (`log_experiment`/`update_experiment`) | Collector (caller) | Single write path already owns `EXPERIMENTS_DIR`, the structural guard, and identity computation. |
| Finalize-once dedup | Collector + `experiment_store` content-addressing | — | Stable identity (collector) + content-addressed filename (store) together yield one file per session. |
| Scrub / score / review / drift | CLI subcommands (post-capture) | — | Hard rule: never in a hook (D-09); all already shipped (Phases 12–13). |

## Standard Stack

No new dependencies. This phase uses only existing project modules and the already-installed stack (Python 3.11+, Pydantic v2, Click, Rich).

### Core (existing modules touched)
| Module | Purpose | Why Standard |
|--------|---------|--------------|
| `src/kajiba/collector.py` | Add `self._experiment_mode` flag + divergent finalize branch | The single shared collector per D-07 ("shared core, divergent tail") |
| `src/kajiba/experiment_store.py` | Reuse `build_experiment_record` + `log_experiment`/`update_experiment` | The single experiment write path (Phase 11 D-08); guarantees SC#2 parity |
| `src/kajiba/schema.py` | Read-only: `ExperimentRecord`, `ExperimentMetadata`, `ExperimentOutcome`, `Trajectory`, `EXPERIMENT_TYPES`, `compute_record_id` | Frozen schema — construct, never modify |
| `src/kajiba/plugin/hooks.py` | Likely no change (dispatchers already forward all four hooks) | Branch belongs in collector, not hooks |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Mode flag on `KajibaCollector` (D-07) | Separate `ExperimentCollector` over a shared base | Cleaner separation but more refactor than one requirement (ECAP-01) warrants; rejected in CONTEXT D-07. |
| Build `ExperimentRecord` directly at finalize (D-07) | Capture as `KajibaRecord` then convert | A coding record would briefly land in `staging` (community path) → privacy risk; rejected in D-07. |
| `update_experiment` re-finalize each end (recommended) | `self._finalized` boolean + write-once on a single "final" end event | Requires a reliable distinct "final end" signal, which v0.15.x does NOT provide (see Pitfall 1 / Open Question 1). |

**Installation:** None — no packages added.

## Package Legitimacy Audit

Not applicable — Phase 14 installs no external packages. (Confirmed: the only imports needed are existing `kajiba.*` modules and stdlib `os`/`datetime`.)

## Architecture Patterns

### System Architecture Diagram

```
Hermes v0.15.x session (KAJIBA_EXPERIMENT=1 set in env)
        │
        ▼
 on_session_start(session_id, model, platform)        ── plugin/hooks.py (unchanged dispatcher)
        │        reads KAJIBA_EXPERIMENT* env vars
        ▼
 KajibaCollector.on_session_start
        ├─ self._experiment_mode = (os.environ.get("KAJIBA_EXPERIMENT") == "1")
        ├─ self._experiment_type = env or "model_evaluation"
        ├─ self._task_category  = env or "coding"
        ├─ self._created_at = now (== started_at for the experiment)
        └─ self._model_metadata, self._hardware = _build_metadata_and_hardware(...)
        │
        ▼   (per turn — SHARED, identical to coding path)
 post_llm_call ─► on_llm_turn  ─► append human + gpt ConversationTurn
 post_tool_call ─► on_tool_call ─► attach ToolCall to gpt turn (turn_id buffer)
        │
        ▼   (fires after EVERY turn AND at CLI exit — TURN-SCOPED)
 on_session_end(session_id)
        │
        ├── if self._experiment_mode:                ◄── DIVERGENT TAIL (new)
        │      build Trajectory from self._conversations
        │      task_description = first human turn value
        │      local_model_output = last gpt turn value   (changes each turn!)
        │      rec = build_experiment_record(
        │              experiment_id = f"live_{session_id}",   (STABLE across turns)
        │              experiment_type = self._experiment_type,
        │              task_category   = self._task_category,
        │              task_description = <first user turn>,
        │              local_model_name = self._model_metadata.model_name,
        │              local_model_output = <last assistant turn>,
        │              eval_score = 0.0,
        │              started_at = self._created_at,
        │              model = self._model_metadata,    (via **extra → rich local_model override, see Pattern 3)
        │              hardware = self._hardware,
        │              trajectory = <built Trajectory>)
        │      update_experiment(rec, EXPERIMENTS_DIR)   (in-place overwrite by content ID)
        │      return   ── NEVER touches STAGING_DIR/OUTBOX_DIR/auto-submit (D-08)
        │
        └── else:  existing coding path (UNCHANGED — staging / continuous auto-submit)
```

### Recommended Project Structure
No structural change. All edits land in `src/kajiba/collector.py` (the mode flag + finalize branch). `experiment_store.py` and `schema.py` are consumed read-only. `plugin/hooks.py` and `plugin/__init__.py` likely unchanged (the env read happens in the collector, not the hook).

### Pattern 1: Env-var trigger read at session start
**What:** Read the opt-in flag and the optional type/category knobs from the environment in `on_session_start`, store on the collector.
**When to use:** Always — this is the only branch point (D-01).
**Recommended env-var names (planner's final call, keep `KAJIBA_EXPERIMENT*` namespace):**
- `KAJIBA_EXPERIMENT` — `"1"` enables experiment mode (mirrors the existing `KAJIBA_DEBUG == "1"` idiom in `plugin/hooks.py` line 36).
- `KAJIBA_EXPERIMENT_TYPE` — default `"model_evaluation"` (must be in `EXPERIMENT_TYPES = ("model_evaluation", "routing_test", "quality_drift", "prompt_ablation")`).
- `KAJIBA_EXPERIMENT_CATEGORY` — default `"coding"` (free-form `str`).

```python
# Source: pattern mirrors existing KAJIBA_DEBUG read in src/kajiba/plugin/hooks.py:36
# In KajibaCollector.on_session_start, inside the try block, alongside the existing resets:
import os
from kajiba.schema import EXPERIMENT_TYPES  # tuple for runtime validation

self._experiment_mode = os.environ.get("KAJIBA_EXPERIMENT") == "1"
exp_type = os.environ.get("KAJIBA_EXPERIMENT_TYPE", "model_evaluation")
self._experiment_type = exp_type if exp_type in EXPERIMENT_TYPES else "model_evaluation"
self._task_category = os.environ.get("KAJIBA_EXPERIMENT_CATEGORY", "coding")
```
**Note on read timing:** `plugin/hooks.py` reads `KAJIBA_DEBUG` ONCE at import time (module attribute `_DEBUG`). For `KAJIBA_EXPERIMENT`, read it **at `on_session_start` call time**, not import time — the flag is per-session, and reading at start lets the same loaded plugin handle both coding and experiment sessions across the Hermes process lifetime. [VERIFIED: codebase — `hooks.py:36` shows the import-time pattern; deviating here is intentional and correct for per-session semantics.]

### Pattern 2: Finalize-once for a content-addressed experiment record (THE correctness item)
**What:** Produce exactly one `exp_<id>.json` per opted-in session despite `on_session_end` firing after every turn.
**Why naive fails:** `ExperimentRecord.compute_record_id()` (schema.py:445-467) hashes `experiment_id`, `task_description`, `local_model_name`, `local_model_output`, `started_at`. Four of these can be made session-stable; **`local_model_output` (last gpt turn, D-03) changes every turn**, so a fresh `log_experiment` per turn yields a different filename each turn → N files. [VERIFIED: codebase schema.py:454-466.]

**Recommended mechanism — session-stable identity + in-place overwrite (`update_experiment`):**
1. `experiment_id = f"live_{session_id}"` — stable across turns.
2. `started_at = self._created_at` — set once in `on_session_start`, never re-read.
3. `task_description = <first human turn value>` — stable (the first turn never changes once captured).
4. On **every** `on_session_end` firing: rebuild the record with the *current* last-gpt-turn as `local_model_output`, then call `update_experiment(rec, EXPERIMENTS_DIR)`.

`update_experiment` (experiment_store.py:133-223) **intentionally always overwrites** (no `dest.exists()` early-return — it closed CR-01). Each turn's `on_session_end` writes a slightly different `exp_<hash>.json` (because the hash includes `local_model_output`), so this alone would *still* leave multiple files. **Therefore combine with the `self._finalized`-style discipline:** track the previously-written path and delete/replace it, OR — cleaner — only write on the LAST end. Two viable concrete designs:

- **Design A (write-once, mirrors `_finalized`):** keep a `self._finalized` guard for experiment mode too, but you need a "final end" signal. v0.15.x does NOT cleanly distinguish per-turn end from CLI-exit end (Open Question 1). So Design A risks never finalizing on a hard exit, or finalizing too early. **Not recommended alone.**

- **Design B (recommended — accumulate + overwrite-latest, self-cleaning):** On each end, compute the new record + its content ID. If a previous experiment file from THIS session exists at a different path, remove it, then write the new one. Track `self._last_experiment_path`. Net effect: exactly one file, always reflecting the latest (= final) turn, robust to a missing distinct final-end event. Pseudocode:

```python
# Source: synthesizes coding-path _finalized guard (collector.py:640-642) +
#         experiment_store.update_experiment overwrite semantics (experiment_store.py:207)
def _finalize_experiment(self, session_id: str) -> None:
    if not self._conversations:
        return  # nothing captured yet (end fired before any turn)
    rec = self._build_experiment_record(session_id)   # uses current last-gpt turn
    new_path = EXPERIMENTS_DIR / f"exp_{rec.record_id}.json"  # rec id already computed by build/log
    # Remove the prior file from THIS session if the content ID changed across turns.
    if self._last_experiment_path and self._last_experiment_path != new_path:
        self._last_experiment_path.unlink(missing_ok=True)
    log_experiment(rec, EXPERIMENTS_DIR)   # or update_experiment for overwrite-safety
    self._last_experiment_path = new_path
```
**Design B is the recommendation.** It needs one new instance attribute `self._last_experiment_path: Optional[Path] = None` (reset in `on_session_start`). It is the experiment analog of the coding ad-hoc path's "rewrite the SAME file" trick (collector.py:631-635), adapted for a content-addressed filename that legitimately moves as the final output accumulates.

**Simplification to confirm with planner:** if `experiment_id` and `started_at` and `task_description` are stable, the ONLY moving part of the ID is `local_model_output`. If the planner instead fixes `local_model_output` to the first gpt turn (NOT D-03) the filename would be stable and Design A becomes trivial — but D-03 explicitly locks `local_model_output` = FINAL assistant response, so Design B (self-cleaning latest) is required to honor D-03.

### Pattern 3: Reuse rich `self._model_metadata` as `ExperimentMetadata.local_model`
**What:** Inject the already-assembled `ModelMetadata` (param count / quantization / family / context window for local Ollama, or slug-inferred for remote) into the experiment record.
**Landmine:** `build_experiment_record(...)` constructs `local_model=ModelMetadata(model_name=local_model_name)` — a **scalar-name-only** metadata object (experiment_store.py:274). Passing the rich object requires care:

- `build_experiment_record` accepts `**extra` that is forwarded to the `ExperimentRecord(...)` constructor (experiment_store.py:283). `**extra` sets **top-level** `RecordBase` fields (`model`, `hardware`, `trajectory`) — NOT the nested `experiment.local_model`. So `model=self._model_metadata` populates `ExperimentRecord.model` (the RecordBase field), while `experiment.local_model` stays the thin scalar version. The deliberate `kajiba experiment log` path has the same thin `experiment.local_model`, so **structural parity (SC#2) holds either way.**
- **Decision for planner:** to put the RICH metadata where analysis expects it (`experiment.local_model`), do NOT use `build_experiment_record`'s scalar `local_model_name`; instead construct the nested model directly, OR post-construct override. Recommended: build the record then set `rec.experiment.local_model = self._model_metadata` before computing IDs — but `local_model.model_name` feeds `compute_record_id`, so ensure `self._model_metadata.model_name` is non-empty (it defaults to `"unknown"` via `_extract_model_metadata`, collector.py:146). Pass BOTH `model=self._model_metadata` (RecordBase) and `hardware=self._hardware` via `**extra` for full runtime context.
- Remote-degrade is acceptable: `is_local=false` with `parameter_count=None` is valid (D-03 of Phase 7; CONTEXT "Remote model under eval mode"). Do not block capture on locality.

```python
# Source: experiment_store.py:231-284 (build_experiment_record signature + **extra forwarding)
rec = build_experiment_record(
    experiment_id=f"live_{session_id}",
    experiment_type=self._experiment_type,
    task_category=self._task_category,
    task_description=first_user_turn,
    local_model_name=(self._model_metadata.model_name if self._model_metadata else "unknown"),
    local_model_output=last_assistant_turn,
    eval_score=0.0,                       # D-05 placeholder
    started_at=self._created_at,          # stable identity input
    model=self._model_metadata,           # **extra → RecordBase.model (rich runtime context)
    hardware=self._hardware,              # **extra → RecordBase.hardware
    trajectory=built_trajectory,          # **extra → ExperimentRecord.trajectory (D-06)
)
# Optional: promote rich metadata into experiment.local_model for analysis tooling.
if self._model_metadata:
    rec.experiment.local_model = self._model_metadata
```

### Pattern 4: Build the `Trajectory` from buffered turns
**What:** Reuse the same `Trajectory` assembly the coding path uses (collector.py:741-761) for `ExperimentRecord.trajectory` (D-06).
**Detail:** `ExperimentRecord.trajectory` is `Optional[Trajectory]` (schema.py:443) and `ExperimentRecord` has **no** `validate_turn_count`/`validate_tool_call_counts` validators (those live only on `KajibaRecord`, schema.py:301-323). So the trajectory is free-form for experiments — but reusing the coding `_build_record` trajectory block (count + tool tallies) costs nothing and keeps one assembly path. Extract that block into a small `_build_trajectory()` helper both paths call, to avoid duplication.

### Anti-Patterns to Avoid
- **Scrubbing or scoring in the finalize hook.** Hard rule (D-09): store raw, scrub later via CLI. The coding path does NOT scrub at staging either (`_save_to_staging` comment, collector.py:779).
- **Touching `STAGING_DIR`/`OUTBOX_DIR`/continuous auto-submit in experiment mode** (D-08). Branch BEFORE the `contribution_mode` read in `on_session_end`.
- **Reading the env var at import time** for the experiment flag (per-session semantics require call-time read — see Pattern 1 note).
- **Using `log_experiment` (skip-on-exists) for the per-turn finalize without removing the stale file.** Skip-on-exists (experiment_store.py:111) plus a moving content ID leaves orphan files. Use Design B's self-cleaning unlink, or `update_experiment` plus stale-path removal.
- **Adding a new model or store module.** CONTEXT "Specific Ideas": if the planner finds itself adding a model or store, that's a smell.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Experiment persistence + identity | A new write function | `experiment_store.log_experiment` / `update_experiment` | Owns `EXPERIMENTS_DIR`, the D-13 structural guard, atomic temp-file write, and ID computation. Reusing it = SC#2 parity for free. |
| `ExperimentRecord` assembly | Manual nested-model construction | `build_experiment_record(**fields)` | Validates on construction (D-08); same constructor `kajiba experiment log` uses → guaranteed structural parity. |
| Model metadata capture | Re-detect at finalize | `self._model_metadata` / `self._hardware` (already assembled in `on_session_start`) | CAPT-04 already does Ollama enrichment + remote slug inference, fault-tolerantly. |
| Trajectory tallies | Recount tool calls inline | Reuse coding `_build_record` trajectory block (extract helper) | One assembly path; identical shape to coding records. |
| Finalize-once guard | A brand-new locking scheme | Adapt `self._finalized` discipline + content-addressed overwrite (Pattern 2 Design B) | The coding path already solved per-turn-end idempotency two ways; reuse the pattern. |

**Key insight:** This phase is "wire existing parts together." Every capability already exists in a shipped module. The only genuinely new code is the mode flag, the finalize branch, and the self-cleaning finalize-once for a content-addressed filename.

## Runtime State Inventory

> Phase 14 is a code-integration phase (new branch in existing collector), NOT a rename/refactor/migration. This section is included only to record that no runtime-state migration is required.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — experiments are NEW files written to `EXPERIMENTS_DIR`; no existing data is renamed or migrated. | None — verified by reading experiment_store.py (write-only, content-addressed). |
| Live service config | None — the plugin registers the SAME four hooks already registered (plugin/__init__.py:40-43); no new hook registration, no Hermes config change. | None — verified by reading plugin/__init__.py. |
| OS-registered state | None — env vars are read at runtime, not OS-registered. | None. |
| Secrets/env vars | NEW env vars introduced (`KAJIBA_EXPERIMENT`, `KAJIBA_EXPERIMENT_TYPE`, `KAJIBA_EXPERIMENT_CATEGORY`) — read-only at session start; no secret storage. | Document the env vars (Pattern 1) so the user knows how to opt in. |
| Build artifacts / installed packages | None — no `pyproject.toml` change, no new dependency, no entry-point change. | None — verified: no package added (see Package Legitimacy Audit). |

**Nothing requires data migration.** The only behavioral change is gated entirely behind `KAJIBA_EXPERIMENT=1`; with the flag absent, capture is byte-for-byte today's coding path (no-regression, see Pitfall 2).

## Common Pitfalls

### Pitfall 1: Turn-scoped `on_session_end` emits N experiment files (THE landmine)
**What goes wrong:** `on_session_end` fires after every `run_conversation` turn AND at CLI exit (06-HOOK-KWARGS.md finding 2, line 135-137). Because `local_model_output` feeds the content-addressed `compute_record_id`, a per-turn `log_experiment` writes a different `exp_<hash>.json` each turn → many files for one session.
**Why it happens:** v0.15.x has no single session-final event; the coding path hides this by (ad-hoc) overwriting a fixed filename or (continuous) a `self._finalized` boolean. A content-addressed filename legitimately moves as the final output accumulates, so neither trick alone suffices.
**How to avoid:** Pattern 2 Design B — session-stable `experiment_id`/`started_at`/`task_description`, and on each end remove the prior session file if the content ID changed, then write the latest. Net: exactly one file reflecting the final turn.
**Warning signs:** Test "opted-in session → exactly one ExperimentRecord" fails with a count > 1; multiple `exp_*.json` files differing only in the assistant-output suffix.

### Pitfall 2: Regression in the coding path when the flag is absent
**What goes wrong:** Refactoring `on_session_end` to add the experiment branch accidentally changes the coding staging/auto-submit behavior.
**Why it happens:** The experiment branch must be added *before* the `contribution_mode` read (collector.py:629) and must `return` cleanly; an early `return` or a moved line could alter the coding flow.
**How to avoid:** Guard the ENTIRE experiment finalize behind `if self._experiment_mode:` at the very top of the `on_session_end` try block, with an unconditional `return` inside it. Below that, the existing coding code is untouched. Add a test asserting flag-absent capture writes to `STAGING_DIR` exactly as today and never to `EXPERIMENTS_DIR`.
**Warning signs:** `test_collector.py` existing lifecycle tests change behavior; a `session_*.json` no longer appears in staging.

### Pitfall 3: Empty `local_model_output` / `task_description` on a zero-turn or interrupted session
**What goes wrong:** If `on_session_end` fires before any `post_llm_call` (e.g., immediate CLI exit, or an interrupted first turn with no `post_llm_call`), `self._conversations` is empty → no first user turn, no last assistant turn → `build_experiment_record` gets empty strings (valid `str`, but a meaningless record), or an IndexError if you index `[0]`/`[-1]` unguarded.
**Why it happens:** Per 06-HOOK-KWARGS.md, an interrupted turn fires `on_session_end` with `interrupted=True` and may not have fired `post_llm_call`.
**How to avoid:** Guard the experiment finalize with `if not self._conversations: return` (Pattern 2 Design B already does this). Derive `task_description` from the first `human` turn and `local_model_output` from the last `gpt` turn defensively (search the list, don't assume positions).
**Warning signs:** IndexError in logs; an `exp_*.json` with empty `local_model_output`.

### Pitfall 4: Mutating record fields after ID computation without re-validation
**What goes wrong:** Setting `rec.experiment.local_model = self._model_metadata` (Pattern 3) after `build_experiment_record` validated the record can desync if you then rely on the already-computed ID. The models lack `validate_assignment` (experiment_store.py:194-198 note "Pitfall 3").
**How to avoid:** Set `local_model` BEFORE calling `log_experiment`/`update_experiment` (which compute IDs at write time, experiment_store.py:106-107 / 203-204). `update_experiment` re-validates via `model_validate` before writing (experiment_store.py:196), so prefer it if you mutate post-construction.
**Warning signs:** `record_id` doesn't match the on-disk filename; a stale `local_model` in the persisted JSON.

## Code Examples

### Building the experiment record from buffered turns (finalize branch)
```python
# Source: synthesizes collector.py:735-773 (_build_record trajectory block) +
#         experiment_store.py:231-284 (build_experiment_record) — verified against current source.
def _build_experiment_record(self, session_id: str) -> "ExperimentRecord":
    # First human turn → task_description; last gpt turn → local_model_output (D-03/D-04).
    first_user = next((t.value for t in self._conversations if t.from_ == "human"), "")
    last_gpt = next((t.value for t in reversed(self._conversations) if t.from_ == "gpt"), "")
    trajectory = self._build_trajectory()  # extract from existing _build_record block
    rec = build_experiment_record(
        experiment_id=f"live_{session_id}",
        experiment_type=self._experiment_type,
        task_category=self._task_category,
        task_description=first_user,
        local_model_name=(self._model_metadata.model_name if self._model_metadata else "unknown"),
        local_model_output=last_gpt,
        eval_score=0.0,                      # D-05 documented placeholder
        started_at=self._created_at,         # stable identity input across turns
        model=self._model_metadata,          # RecordBase.model (rich runtime context)
        hardware=self._hardware,             # RecordBase.hardware
        trajectory=trajectory,               # ExperimentRecord.trajectory (D-06)
    )
    if self._model_metadata:
        rec.experiment.local_model = self._model_metadata   # rich metadata for analysis
    return rec
```

### Branching `on_session_end` (no-regression guard at the top)
```python
# Source: collector.py:603-642 (current on_session_end) — insert the branch FIRST.
def on_session_end(self, session_id: str) -> None:
    try:
        if self._session_id != session_id:
            logger.warning("Session ID mismatch: expected %s, got %s",
                           self._session_id, session_id)
        if self._experiment_mode:                       # NEW: divergent tail (D-07/D-08)
            self._finalize_experiment(session_id)       # NEVER touches staging/outbox
            return
        # ----- existing coding path below, UNCHANGED -----
        contribution_mode = _load_config_value("contribution_mode", "ad-hoc")
        ...
    except Exception:
        logger.exception("Error in on_session_end")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `on_session_end` assumed session-final | Turn-scoped: fires per `run_conversation` turn + CLI exit | Hermes v0.15.x (06-HOOK-KWARGS.md finding 2) | Drives the finalize-once requirement; already handled in coding path, must be re-solved for content-addressed experiment IDs. |
| `log_experiment` skip-on-exists (CR-01 data loss) | `update_experiment` in-place overwrite | Phase 13 | Live finalize should use the overwrite-safe path (or self-cleaning unlink) to avoid orphan files. |

**Deprecated/outdated:**
- The Protocol-based `hermes_integration.py` adapter was removed in Phase 6; the live contract is `ctx.register_hook(event, callback)` (plugin/__init__.py). Do not reference `agent.on(...)`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Exact env-var names (`KAJIBA_EXPERIMENT`, `KAJIBA_EXPERIMENT_TYPE`, `KAJIBA_EXPERIMENT_CATEGORY`) — CONTEXT delegates the exact names to the planner; these follow the `KAJIBA_DEBUG`/`KAJIBA_EXPERIMENT*` idiom. | Pattern 1 | Low — naming only; behavior unaffected. Planner finalizes. |
| A2 | `experiment_id = f"live_{session_id}"` scheme — CONTEXT calls this "likely"/"planner's call". | Pattern 2 | Low — any session-stable scheme works; this one is traceable. |
| A3 | v0.15.x provides no signal to distinguish a per-turn `on_session_end` from the true CLI-exit end. Based on 06-HOOK-KWARGS.md finding 2 (which says both surface here) and the absence of any distinguishing kwarg in the on_session_end table (only `completed`/`interrupted`, which are per-turn). | Open Question 1, Pitfall 1 | Medium — if a distinct final-end signal DOES exist, Design A (write-once) becomes simpler. Design B is safe regardless. |
| A4 | `plugin/hooks.py` needs no change (collector reads env at start). The hook already forwards `on_session_start`/`on_session_end`. | Standard Stack | Low — if the planner prefers reading env in the hook, that also works; collector-side is cleaner. |

## Open Questions

1. **Is there any kwarg on `on_session_end` that distinguishes the final CLI-exit firing from per-turn firings?**
   - What we know: 06-HOOK-KWARGS.md table for `on_session_end` lists `session_id`, `completed`, `interrupted`, `model`, `platform`, `task_id`, `turn_id`, `telemetry_schema_version`. `completed`/`interrupted` are per-turn outcome flags, not session-final markers (finding 2 explicitly says both turn boundaries and final teardown surface here).
   - What's unclear: Whether the LAST firing has a uniquely identifiable value (e.g., absent `turn_id`, or a different `task_id`). Not verifiable from the artifact alone.
   - Recommendation: Use Pattern 2 Design B (self-cleaning overwrite-latest), which does NOT depend on identifying the final end. If the planner wants to confirm, a `KAJIBA_DEBUG=1` live capture of a multi-turn-then-exit session would show whether the final firing differs — but Design B makes this optional, not blocking.

2. **Should `plugin/hooks.py` forward an `experiment` flag, or should the collector read env directly?**
   - What we know: `hooks.py` reads `KAJIBA_DEBUG` itself; the collector reads config via `_load_config_value`. Either layer can read the env.
   - Recommendation: Read in `KajibaCollector.on_session_start` (Pattern 1) — keeps the single branch point on the collector per D-07, leaves hooks as dumb dispatchers, and requires zero hook changes.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | ✓ | 3.13.3 (>=3.11 required) | — |
| Pydantic v2 | Schema construction | ✓ | >=2.0 | — |
| `kajiba.experiment_store` | Write path | ✓ | in-repo (Phase 11) | — |
| `kajiba.schema` ExperimentRecord family | Record construction | ✓ | in-repo (Phase 10) | — |
| Hermes Agent v0.15.x | Live capture proof (manual) | ✓ (dev machine, native Windows) | v0.15.1 | Unit tests mock the collector directly — live Hermes not required for automated validation. |
| Ollama | Rich local metadata (CAPT-04) | Optional | — | Remote-degrade path (`is_local=false`) is acceptable per CONTEXT; capture not blocked. |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** Ollama (remote-degrade is explicitly acceptable for eval mode).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=7.0 (+ pytest-cov >=4.0) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `addopts = "-v"`) |
| Quick run command | `python -m pytest tests/test_collector.py -x -q` |
| Full suite command | `python -m pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ECAP-01 | Opted-in session → exactly ONE `ExperimentRecord` in `EXPERIMENTS_DIR` (finalize-once across N turn-scoped `on_session_end` firings) | unit | `pytest tests/test_collector.py::TestExperimentCapture::test_opted_in_session_writes_one_record -x` | ❌ Wave 0 |
| ECAP-01 | Flag absent → unchanged coding capture (writes `session_*.json` to `STAGING_DIR`, NEVER touches `EXPERIMENTS_DIR`) — no regression | unit | `pytest tests/test_collector.py::TestExperimentCapture::test_flag_absent_unchanged_coding_path -x` | ❌ Wave 0 |
| ECAP-01 | Structural parity: live-captured record has same model/metadata/outcome structure as `kajiba experiment log` output | unit | `pytest tests/test_collector.py::TestExperimentCapture::test_structural_parity_with_deliberate_log -x` | ❌ Wave 0 |
| ECAP-01 | Field mapping: `task_description`==first user turn, `local_model_output`==last gpt turn, `eval_score`==0.0, `experiment.local_model`==captured metadata, `trajectory` populated | unit | `pytest tests/test_collector.py::TestExperimentCapture::test_field_mapping -x` | ❌ Wave 0 |
| ECAP-01 | Experiment mode never writes to `STAGING_DIR`/`OUTBOX_DIR` even in continuous contribution_mode (D-08) | unit | `pytest tests/test_collector.py::TestExperimentCapture::test_no_staging_or_outbox_in_experiment_mode -x` | ❌ Wave 0 |
| ECAP-01 | Defensive: zero-turn / interrupted session → no malformed record written (Pitfall 3) | unit | `pytest tests/test_collector.py::TestExperimentCapture::test_zero_turn_session_writes_nothing -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_collector.py -x -q`
- **Per wave merge:** `python -m pytest -q` (full suite — must include `test_experiment_store.py`, `test_experiment_exclusion.py`, `test_schema_experiment.py` to confirm no regression in the experiment store/guards)
- **Phase gate:** Full suite green before `/gsd-verify-work`. Plus one manual `KAJIBA_EXPERIMENT=1` live Hermes session producing exactly one `exp_*.json` (SC#1 live proof).

### Wave 0 Gaps
- [ ] New test class `TestExperimentCapture` in `tests/test_collector.py` — covers all six ECAP-01 rows above. Use `monkeypatch.setenv("KAJIBA_EXPERIMENT", "1")` and `monkeypatch.setattr` for `EXPERIMENTS_DIR`/`STAGING_DIR` to `tmp_path` (mirror the isolation pattern in `tests/test_experiment_store.py`).
- [ ] Shared fixture: a helper that drives the collector through `on_session_start` → N×(`on_llm_turn` + `on_session_end`) to simulate the turn-scoped firing (the exact finalize-once scenario). Existing `test_collector.py` already drives full lifecycles (lines 16-70) — extend that idiom.
- [ ] Parity assertion helper: build a record via `build_experiment_record` directly (the deliberate-log shape) and assert the live-captured record's `model_dump(by_alias=True)` keys/structure match (allowing `trajectory` populated + `eval_score==0.0`).
- Framework install: none — pytest already present.

## Security Domain

> `security_enforcement` is not set in config.json. The dominant security concern here is the project's locked **privacy** constraint, treated below.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth surface in a local pipeline. |
| V3 Session Management | no | "Session" here is a Hermes capture session, not an auth session. |
| V4 Access Control | yes | Structural privacy guard: experiment records must NEVER reach `STAGING_DIR`/`OUTBOX_DIR` (publish path). Enforced by `experiment_store` D-13 guard + D-08 collector constraint. |
| V5 Input Validation | yes | All records validated by Pydantic on construction (`build_experiment_record`, `update_experiment` re-validate). |
| V6 Cryptography | no | SHA-256 content-addressing is identity, not security crypto; already in frozen schema. |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Private experiment data leaks into the community publish path | Information Disclosure | D-08 (collector never touches staging/outbox in experiment mode) + D-13 structural guard in `experiment_store` (refuses to write outside `EXPERIMENTS_DIR`) + Phase 11 `record_kind=="model_experiment"` publish-refusal backstop. Regression test (Phase 11 D-14) already proves exclusion. |
| Raw PII captured at finalize (no scrub in hook) | Information Disclosure | D-09: store raw, scrub via `kajiba experiment scrub` CLI step later. The store is local/private (no network), so raw-at-rest is acceptable until the CLI scrub runs — same as coding staging. |
| A hook exception disrupts the Hermes host session | Denial of Service (host) | Fault-tolerant hooks: every collector method wraps its body in try/except and never propagates (collector.py pattern). Keep this on the experiment finalize. |

## Sources

### Primary (HIGH confidence)
- `src/kajiba/collector.py` — `KajibaCollector`, `on_session_start`/`on_session_end`, `_build_record`, `_build_metadata_and_hardware`, `self._finalized` guard, ad-hoc fixed-filename overwrite (lines 325-833).
- `src/kajiba/experiment_store.py` — `log_experiment` (skip-on-exists), `update_experiment` (overwrite), `build_experiment_record` (**extra forwarding), `EXPERIMENTS_DIR`, D-13 structural guard (lines 1-284).
- `src/kajiba/schema.py` — `RecordBase`, `ExperimentRecord`/`ExperimentMetadata`/`ExperimentOutcome`, `Trajectory`, `EXPERIMENT_TYPES`, `compute_record_id`/`compute_submission_hash` for experiments (lines 265-492).
- `src/kajiba/plugin/hooks.py` + `plugin/__init__.py` — four registered hooks, `KAJIBA_DEBUG` env idiom, dispatcher shape (hooks.py:1-160, __init__.py:27-49).
- `src/kajiba/cli.py` — `experiment log` deliberate path (the SC#2 parity target), `EXPERIMENTS_DIR` constant (lines 1062-1196).
- `.planning/phases/06-environment-plugin-foundation/06-HOOK-KWARGS.md` — turn-scoped `on_session_end` (finding 2), full v0.15.x kwarg contract.
- `.planning/phases/14-live-experiment-capture/14-CONTEXT.md` — locked decisions D-01..D-10 + Claude's Discretion.
- `.planning/phases/11-experiment-logging-private-store/11-CONTEXT.md` + `07-CONTEXT.md` — write-path and finalize-once-discipline lineage.

### Secondary (MEDIUM confidence)
- `tests/test_collector.py`, `tests/test_experiment_store.py` (read for test idioms / isolation patterns).

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all modules read directly; zero new packages.
- Architecture / integration points: HIGH — exact function signatures, instance attributes, and call sites verified against current source.
- Finalize-once mechanism: HIGH on the problem and Design B solution; MEDIUM on whether a simpler write-once is possible (gated on Open Question 1, which Design B makes non-blocking).
- Pitfalls: HIGH — each traced to a specific source line.

**Research date:** 2026-06-06
**Valid until:** 2026-07-06 (stable — internal codebase, no fast-moving external deps; re-verify if Hermes hook contract changes beyond v0.15.x).
