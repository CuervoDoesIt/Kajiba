# Phase 6: Environment + Plugin Foundation - Context

**Gathered:** 2026-04-03
**Revised:** 2026-06-05 (re-plan — Hermes v0.6.0 → v0.15.x + native Windows)
**Status:** Ready for planning (re-plan of 06-04/06-05)

> **Re-plan note:** Waves 1–4 (06-01..06-04) executed against the original WSL2 +
> Ollama + Hermes v0.6.0 assumption. The ecosystem (and the dev machine) moved to
> **Hermes v0.15.x with native Windows**, and hook kwargs are now officially
> documented. This revision retargets the phase. Decisions tagged **[DONE]** are
> already built and verified-still-correct; **[RE-SCOPED]** / **[NEW]** drive the
> replan of 06-04 (guide rewrite) and 06-05 (live hook verify). Full research input:
> `.planning/phases/06-environment-plugin-foundation/06-REPLAN-RESEARCH.md`.

<domain>
## Phase Boundary

Hermes Agent discovers, loads, and **enables** the Kajiba plugin, and the four
lifecycle hooks (`on_session_start`, `post_llm_call`, `post_tool_call`,
`on_session_end`) fire confirmed on a live session — targeting **native Windows +
Hermes Agent v0.15.x + remote backends** (OpenAI/Anthropic). Kajiba paths resolve
under HERMES_HOME profile isolation, the old Protocol adapter is replaced by a real
`src/kajiba/plugin/` package, and a symlink dev workflow supports rapid edit-reload.

WSL2 + NVIDIA GPU passthrough + Ollama are an **optional appendix** (needed only for
the dashboard `/chat` embedded terminal, which requires a POSIX PTY, or for local
inference). Plugin load and hook verification require **no GPU and no Ollama** —
hooks fire on any backend.

The phase *goal* is unchanged and platform-agnostic; only the assumed implementation
(WSL2 / Ollama / v0.6.0) shifted.

</domain>

<decisions>
## Implementation Decisions

### Platform & Version Target [NEW]
- **D-11:** Native Windows is the **documented primary path**. WSL2 + GPU + Ollama
  move to an **optional appendix** (dashboard terminal / local inference only). The
  RTX 4070 path stays available for Phase 7 (GLiNER) and Phase 9 (QLoRA) but is **not**
  a Phase 6 gate. Hook/plugin verification runs on a remote backend with no GPU/Ollama.
- **D-12:** Bump all `v0.6.0` references → **`v0.15.x`** across `docs/hermes-setup.md`,
  the `plugin.yaml` header comment, and plugin docstrings (`plugin/__init__.py`,
  `plugin/hooks.py`). Dev machine runs v0.15.1; current published is v0.15.2 — write
  the target as `v0.15.x`.

### Setup Guide — `docs/hermes-setup.md` [RE-SCOPED; supersedes D-03/D-04 framing]
- **D-13:** **Corrective in-place rewrite** of `docs/hermes-setup.md` → native-Windows
  primary, with WSL2/GPU/Ollama demoted to an optional appendix. **Preserve the file
  path and git history** (do not create a separate superseding file). Keep the
  checkpoint-gated structure, but the primary checkpoints become: install Hermes
  (native) → install/`pip install -e .` Kajiba → symlink plugin → **enable** plugin →
  plugin loads → hooks fire.
- **D-14:** Fold the new v0.15.x operational steps into the guide **and** the 06-05
  verification:
  - `hermes plugins enable kajiba` — REQUIRED; a discovered-but-disabled plugin won't load.
  - `HERMES_PLUGINS_DEBUG=1` — Hermes's own verbose discovery logging (stderr),
    complements Kajiba's `KAJIBA_DEBUG=1`.
  - Retain the existing `KAJIBA_DEBUG` "PII in logs" security note.
- **D-04 (revised):** The original CUDA-stub-overwrite / Ollama `num_ctx` / Ollama-WSL2
  binding troubleshooting **stays**, but **moves into the optional WSL2 appendix** —
  it is only relevant when a reader chooses WSL2 + local Ollama (pitfalls MP-8/MP-5/MP-9).

### Hook Verification — 06-05 [RE-SCOPED]
- **D-15:** Re-scope 06-05 from "multi-hour WSL2 build to *discover undocumented*
  kwargs" → "**native-Windows confirm of documented kwargs**." Run a **~15-min live
  Hermes v0.15.1 session on a remote backend** (no GPU/Ollama) with `KAJIBA_DEBUG=1`,
  capturing the actual fired kwargs for all four hooks.
- **D-16:** Output `06-HOOK-KWARGS.md` tags each hook's kwargs **`[DOCUMENTED v0.15.x]`**
  (from official docs — signature table already in `06-REPLAN-RESEARCH.md §3`) plus
  **`[VERIFIED]`** when confirmed in the live session. This permanently closes the old
  "no formal payload schema published" blocker.

### Plugin Load & Discovery Directory [NEW]
- **D-17:** Resolve the discovery directory **empirically** by inspecting the installed
  Hermes source (`%LOCALAPPDATA%\hermes\hermes-agent`): does discovery scan
  `<HERMES_HOME>/plugins/` or always `~/.hermes/plugins/` when HERMES_HOME is overridden
  (this machine: `HERMES_HOME=%LOCALAPPDATA%\hermes`)? The confirmed directory sets the
  **D-02 symlink target**. (Live kwargs verification is via session per D-15; this is a
  targeted source check for the dir question — not a full source-based kwargs derivation.)
- **D-18:** Promote `plugin.yaml` field tags **`[ASSUMED]` → `[CONFIRMED v0.15.x]`** once
  the live load + source check confirm the manifest schema. Fields already match the
  documented schema (`name`, `version`, `description`, `provides_hooks`, `provides_tools`
  per `06-REPLAN-RESEARCH.md §3`); this is a confidence promotion, not a field change.
- **D-19:** `hermes plugins enable kajiba` is a **required load step** in both the guide
  (D-14) and the 06-05 verification — without it the plugin is discovered but inert.

### Requirements / Roadmap Reconciliation [NEW — flagged, not edited here]
- **D-20:** ENV-01, ENV-02, and ROADMAP Phase 6 **Success Criterion #1** name
  WSL2 / GPU passthrough / Ollama / v0.6.0 as the *required* path — now stale. The
  underlying intent (a documented, verifiable Hermes env + plugin load) is satisfied via
  native Windows; WSL2/Ollama satisfy the optional appendix. **FLAGGED:** update the
  ENV-01/02 + SC-1 wording via `/gsd-phase` so "done" reflects native-Windows-primary.
  Not edited from discuss-phase (out of scope; no direct ROADMAP/REQUIREMENTS writes).
- **D-21:** CAPT-01 ("logging-only stub to *empirically confirm hook kwargs against live
  Hermes v0.6.0*") is **reinterpreted** as "confirm the **documented v0.15.x** kwargs via
  a live session" (D-15/D-16). Same artifact, current contract.

### Carried Forward — already built and verified-still-correct
- **D-01 [DONE]:** Plugin source lives at `src/kajiba/plugin/` as a subpackage; its
  `__init__.py` exposes `register(ctx)` and imports `from kajiba.collector import
  KajibaCollector`. Built in 06-03 (`__init__.py`, `hooks.py`, `plugin.yaml`).
- **D-02 [DONE→target TBD]:** Dev symlink from the discovery `plugins/<...>/kajiba/` dir
  into `src/kajiba/plugin/`. The exact discovery dir is finalized by **D-17**.
- **D-05 [DONE]:** `KAJIBA_DEBUG=1` debug mode logs all hook kwargs (name/type/repr[:120])
  to stderr/log as a permanent diagnostic. Built in 06-03.
- **D-07 [DONE]:** `src/kajiba/hermes_integration.py` deleted (06-02). Clean break from the
  wrong Protocol/`register_hooks()` adapter.
- **D-08 [DONE]:** Tests use `KajibaCollector` directly; static guard test asserts
  `hermes_integration` stays deleted.
- **D-09 [DONE]:** All hardcoded `~/.hermes` paths replaced with HERMES_HOME-aware
  resolution across `config.py`, `collector.py`, `cli.py`, `publisher.py`,
  `experiment_store.py` (06-02). Confirmed **more** correct on native Windows.
- **D-10 [DONE]:** `get_hermes_home()` in `config.py` is the single resolver (reads
  `HERMES_HOME` env first, falls back to `~/.hermes`). Constant-vs-lazy split preserves
  ~30 monkeypatch sites. `on_session_start` signature adapted to
  `(session_id, model_config=None, *, model_name=None, platform=None)`.

### Claude's Discretion
- Traceability bookkeeping — reconciling PLUG-02/PLUG-03/CAPT-01 partial/complete marks
  during planning (the code/tests already satisfy the structural requirements).
- Exact native-primary vs WSL2-appendix section split and checkpoint wording in the guide.
- The specific short task to run during the ~15-min live verification session.
- Whether to also refresh `[ASSUMED]`/v0.6.0 wording in inline docstrings beyond `plugin.yaml`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Re-plan Input (READ FIRST)
- `.planning/phases/06-environment-plugin-foundation/06-REPLAN-RESEARCH.md` — **THE
  authoritative re-plan input.** §3 = documented v0.15.x hook signature table + plugin
  contract; §4 = native-Windows facts; §5 = open decisions (now resolved in this CONTEXT).

### Hermes v0.15.x Official Docs
- Plugin guide: <https://hermes-agent.nousresearch.com/docs/guides/build-a-hermes-plugin/>
  — `register(ctx)`, `ctx.register_hook`, documented hook signatures, `plugin.yaml` fields,
  `hermes plugins enable`, `HERMES_PLUGINS_DEBUG`.
- Native Windows: <https://hermes-agent.nousresearch.com/docs/user-guide/windows-native>
  — data layout, HERMES_HOME on Windows, the dashboard-terminal-only WSL2 limitation.
- Installation: <https://hermes-agent.nousresearch.com/docs/getting-started/installation>
- Releases (v0.13–v0.15.2): <https://github.com/NousResearch/hermes-agent/releases>

### Existing Codebase (built in Waves 1–4)
- `src/kajiba/plugin/__init__.py` — `register(ctx)` entry point + 4 hook wiring (06-03).
- `src/kajiba/plugin/hooks.py` — `**kwargs`-tolerant handlers dispatching to `KajibaCollector`;
  `KAJIBA_DEBUG` logging.
- `src/kajiba/plugin/plugin.yaml` — manifest; `[ASSUMED]` tags + v0.6.0 comment to update (D-12/D-18).
- `src/kajiba/config.py` — `get_hermes_home()` single resolver (06-02).
- `src/kajiba/collector.py` — `KajibaCollector`; adapted `on_session_start` signature (06-02).
- `docs/hermes-setup.md` — **to be rewritten in place** (D-13); currently WSL2/Ollama/v0.6.0-centric.

### Older Research (now partially superseded — read with the re-plan lens)
- `.planning/research/FEATURES.md`, `ARCHITECTURE.md` — original plugin/integration research.
- `.planning/research/PITFALLS.md` — MP-1/MP-2/MP-4 still relevant; **MP-5/MP-8/MP-9 are
  WSL2-only and now optional-appendix material**.

### Project Spec
- `docs/kajiba-project-spec.md` — full pipeline design, schema, controlled vocabularies.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable / Already-Built Assets
- `src/kajiba/plugin/` package — `register(ctx)` + 4 hooks + `KAJIBA_DEBUG` (06-03).
  Handler signatures already match the documented v0.15.x kwargs (`06-REPLAN-RESEARCH §3`).
- `get_hermes_home()` (`config.py`) — HERMES_HOME-first resolver; honored identically on
  native Windows (the `~/.hermes` fallback never triggers on this machine).
- `KajibaCollector` (`collector.py`) — lifecycle methods map to hook events;
  `on_session_start(session_id, model_config=None, *, model_name=None, platform=None)`
  correctly maps documented hook `model`→`model_name`, `platform` through.
- `_detect_hardware()` / `_extract_model_metadata()` — unchanged; hardware capture works,
  but is **not exercised** by Phase 6 verification (remote backend, no GPU read required).

### Established Patterns
- Fault-tolerant hooks: every handler wraps its body and never propagates to Hermes.
- Soft-dependency pattern (`psutil`, `pyyaml`) — graceful fallback when absent.
- Constant-vs-lazy path split preserving monkeypatch sites (from 06-02).

### Integration Points (native Windows)
- `HERMES_HOME = %LOCALAPPDATA%\hermes` (this machine) — live profile dir holding
  `config.yaml`, `auth.json`, `sessions`, `skills`, `hooks`, `logs`, `state.db`, `kajiba/`.
- Discovery `plugins/` dir — **does not exist yet**; created on plugin install. Exact
  location (`<HERMES_HOME>/plugins/` vs `~/.hermes/plugins/`) resolved by D-17.
- Installed Hermes source for the D-17 check:
  `%LOCALAPPDATA%\hermes\hermes-agent` (venv `Scripts\hermes.exe`, Python 3.11.15).
- Backends: remote OpenAI sub + Anthropic key (no local Ollama installed/on PATH).

</code_context>

<specifics>
## Specific Ideas

- This machine: **Hermes Agent v0.15.1 (2026.5.29), native Windows**, no WSL2, no Ollama.
  Verification must assume this exact setup (remote backend, ~15 min, no GPU).
- The native-primary guide should keep the "verification checkpoint at each stage" feel,
  but the *stages* collapse to install→editable-install→symlink→enable→load→hooks-fire.
- `06-HOOK-KWARGS.md` should be the single living record of the real hook contract, dual-tagged
  `[DOCUMENTED v0.15.x]` + `[VERIFIED]`, so Phase 7 turn-capture builds on confirmed payloads.
- `hermes plugins enable` is the easiest step to forget — call it out explicitly in both
  the guide and the verification checklist.

</specifics>

<deferred>
## Deferred Ideas

None new — discussion stayed within the phase domain (retargeting how Phase 6 is
delivered, not adding capability).

### Reviewed Todos (not folded)
- **`2026-06-04-fix-experiment-relog-dedup-cr01.md`** — "Fix experiment re-log dedup data
  loss (CR-01) + Phase 11 review warnings." Matched on weak keyword overlap only; it is
  v1.2 experiment-store/CLI work, unrelated to the v1.1 plugin-foundation re-plan.
  Deferred to its own task / Phase 11 follow-up.

</deferred>

---

*Phase: 06-environment-plugin-foundation*
*Context gathered: 2026-04-03 · Re-plan revision: 2026-06-05*
