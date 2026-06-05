# Phase 6 — Re-plan Research Input

> **Status:** Phase 6 PAUSED at the 06-05 checkpoint pending a re-plan.
> **Trigger:** At the Wave 5 (06-05) live-verification checkpoint, the developer flagged that Hermes Agent shipped a **native Windows install** since planning. Investigation confirmed a much larger shift: the phase targeted **v0.6.0** but the ecosystem (and this machine) is now on **v0.15.x**.
> **Purpose of this file:** Preserve the research done during the paused execute-phase run so `/gsd-discuss-phase 6` (or replan) can re-scope without re-discovering. This file is *input to the re-plan*, not a change to any committed plan/code/summary.
> **Captured:** 2026-06-04

---

## 1. What is already DONE and committed (do not redo blindly)

Waves 1–4 executed and committed; each verified against the **current** v0.15.x docs and found still-correct:

| Plan | What it did | Status vs. v0.15.x reality |
|------|-------------|----------------------------|
| 06-01 | Wave-0 RED test scaffolds (config / plugin / deletion-guard) | Valid. Tests assert the plugin contract that still holds. |
| 06-02 | `get_hermes_home()` migration, delete `hermes_integration.py`, adapt `on_session_start` | Valid — arguably *more* correct now (HERMES_HOME confirmed honored on native Windows). |
| 06-03 | `src/kajiba/plugin/` package: `register(ctx)` + 4 hooks + `plugin.yaml` + `KAJIBA_DEBUG` | API confirmed by current docs. Handler signatures match documented kwargs. |
| 06-04 | `docs/hermes-setup.md` WSL2/GPU/Ollama setup guide | **STALE** — WSL2/CUDA/Ollama-centric; needs native-Windows rewrite. |

**Only 06-05 remains incomplete.** Its original premise (multi-hour WSL2 build to *empirically discover undocumented hook kwargs*) is largely **obsolete**: native Windows removes WSL2, and the hook kwargs are now officially documented.

---

## 2. Installed reality on THIS machine (developer's Windows 11 box)

- **Hermes Agent v0.15.1 (2026.5.29)**, native Windows — `C:\Users\jsala\AppData\Local\hermes\hermes-agent\venv\Scripts\hermes.exe`, Python 3.11.15, OpenAI SDK 2.24.0. (`hermes` reports "185 commits behind — run 'hermes update'"; current published is v0.15.2.)
- **No WSL2 involved.** Native install.
- **`HERMES_HOME = C:\Users\jsala\AppData\Local\hermes`** (the active profile dir — holds `config.yaml`, `auth.json`, `sessions`, `skills`, `hooks`, `logs`, `state.db`, plus a `kajiba` data dir). `get_hermes_home()` reads HERMES_HOME first, so it resolves correctly; the `~/.hermes` fallback never triggers here.
- **Ollama NOT installed / not on PATH.** The developer uses remote backends (OpenAI sub + Anthropic key). **Implication:** verifying the plugin/hooks needs NO local GPU/Ollama — hooks fire on any backend.
- No `plugins/` dir exists yet under HERMES_HOME (would be created when installing the Kajiba plugin).
- **Open item:** when HERMES_HOME is overridden, does discovery scan `<HERMES_HOME>/plugins/` or always `~/.hermes/plugins/`? The installed source at `...\hermes-agent` can settle this definitively.

---

## 3. Current Hermes plugin contract (v0.15.x official docs — ground truth)

Source: <https://hermes-agent.nousresearch.com/docs/guides/build-a-hermes-plugin/>

- **Entry point unchanged:** `def register(ctx):` — called once at startup.
- **`ctx` now exposes far more** than hooks: `register_tool`, `register_hook`, `register_cli_command`, `register_command` (slash), `register_platform`, `register_memory_provider`, `register_context_engine`, `register_image_gen_provider`, `register_skill`, `dispatch_tool`. (Kajiba only needs `register_hook`.)
- **Hook registration unchanged:** `ctx.register_hook(event_name, callback)`. All callbacks should accept `**kwargs`.
- **Documented lifecycle hooks + signatures** (the `[ASSUMED]` table from 06-RESEARCH is now resolved):

  | Hook | Documented parameters |
  |------|----------------------|
  | `pre_tool_call` | `tool_name: str, args: dict, task_id: str` |
  | `post_tool_call` | `tool_name: str, args: dict, result: str, task_id: str, duration_ms: int` |
  | `pre_llm_call` | `session_id: str, user_message: str, conversation_history: list, is_first_turn: bool, model: str, platform: str` |
  | `post_llm_call` | `session_id: str, user_message: str, assistant_response: str, conversation_history: list, model: str, platform: str` |
  | `on_session_start` | `session_id: str, model: str, platform: str` |
  | `on_session_end` | `session_id: str, completed: bool, interrupted: bool, model: str, platform: str` |
  | `on_session_finalize` | `session_id: str \| None, platform: str` |
  | `on_session_reset` | `session_id: str, platform: str` |

  - `pre_llm_call` returning `{"context": ...}` (or a plain string) injects text into the current turn — relevant if Kajiba ever wants to inject.
  - `post_tool_call.result` is typed **`str`** → resolves the old "Pitfall 7: is result a JSON string?" question.
- **Discovery:** still directory-based `~/.hermes/plugins/<name>/` (flat, or one category level deep) with `plugin.yaml` + `__init__.py` exposing `register(ctx)`. **AND** pip entry-points now supported: `[project.entry-points."hermes_agent.plugins"]` (this is the Phase 8 / PLUG-04 path).
- **`plugin.yaml` fields:** `name`, `version`, `description`, `provides_tools`, `provides_hooks`; optional `author`, `requires_env` (rich form with name/description/url/secret), `kind` (`model-provider` / `platform` / `backend`). Our manifest matches.
- **NEW operational steps the guide/verify must include:**
  - Plugins must be **enabled**: `hermes plugins enable <name>` (a discovered-but-disabled plugin won't load).
  - Hermes has its own discovery debug: **`HERMES_PLUGINS_DEBUG=1`** (verbose discovery logs on stderr) — complements our `KAJIBA_DEBUG=1`.

### Code reconciliation (06-03 vs. documented contract)
- `on_session_start(session_id, model, platform, **kwargs)` → matches verbatim; correctly maps hook `model` → collector `model_name`. ✓
- `on_session_end(session_id, **kwargs)` → absorbs documented `completed`/`interrupted`/`model`/`platform`. ✓ (Phase 7 may want `completed`/`interrupted` for outcome signals.)
- `on_post_llm_call(**kwargs)` / `on_post_tool_call(**kwargs)` → debug-log only; turn/tool assembly correctly deferred to Phase 7. ✓
- `plugin.yaml` `provides_hooks` lists the 4 hooks; `provides_tools: []`. Valid. ✓

---

## 4. Native Windows facts (vs. the WSL2 assumption)

Sources: <https://hermes-agent.nousresearch.com/docs/user-guide/windows-native>, <https://hermes-agent.nousresearch.com/docs/getting-started/installation>

- Native Windows is real since **v0.14.0** (2026.5.16). Install: PowerShell one-liner `iex (irm https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.ps1)`, or `pip install hermes-agent && hermes`, or the Hermes Desktop `.exe` (public preview, 2026-06-02, bundles v0.15.2).
- Data layout on native Windows:
  - `%LOCALAPPDATA%\hermes\hermes-agent\` — git checkout + venv (disposable).
  - `%USERPROFILE%\.hermes\` — config/auth/skills/sessions/logs (survives reinstalls) **by default**… but this developer has **`HERMES_HOME` overridden to `%LOCALAPPDATA%\hermes`**, so that's their live profile.
  - `HERMES_HOME` env var honored identically to Linux.
- **Only native-vs-WSL2 limitation:** the dashboard `/chat` embedded terminal pane (needs a POSIX PTY). Everything else — plugins, hooks, inference via Ollama/LM Studio/llama-server/remote — runs natively.
- The old WSL2 pitfalls (CUDA driver stub overwrite MP-8, Ollama `num_ctx` truncation MP-5, Ollama WSL2 binding MP-9) are **not relevant to the native path** and only matter if someone *chooses* WSL2 + local Ollama.

---

## 5. Open decisions for the re-plan (`/gsd-discuss-phase 6`)

1. **Primary platform:** make native Windows the documented primary path (WSL2 → optional appendix, needed only for the dashboard terminal). Confirm scope of GPU/Ollama content (move to optional, since hooks don't need it).
2. **Version target:** bump references `v0.6.0` → `v0.15.x` across phase docs, `plugin.yaml` comment, and `hooks.py`/`__init__.py` docstrings (currently say `[ASSUMED]` / v0.6.0).
3. **06-04 guide:** it "completed" but is stale. Re-plan should decide: corrective rewrite plan vs. supersede.
4. **06-05 scope:** re-scope from "WSL2 build to discover undocumented kwargs" to "native-Windows confirm of documented kwargs." Sub-decisions: (a) live run vs. installed-source inspection vs. both; (b) `06-HOOK-KWARGS.md` tag = `[DOCUMENTED v0.15.x]` + optional `[VERIFIED]` from a live session. Hooks can be confirmed in ~15 min on the installed v0.15.1 with no GPU/Ollama.
5. **Discovery dir under overridden HERMES_HOME:** resolve `<HERMES_HOME>/plugins/` vs `~/.hermes/plugins/` (inspect installed source).
6. **`hermes plugins enable` + `HERMES_PLUGINS_DEBUG`:** fold into the guide and verification steps.
7. **Requirements still pending** (carried from waves): PLUG-03/PLUG-02/CAPT-01 marked partial in places; reconcile traceability during re-plan.

## 6. Sources
- Hermes plugin guide: <https://hermes-agent.nousresearch.com/docs/guides/build-a-hermes-plugin/>
- Native Windows guide: <https://hermes-agent.nousresearch.com/docs/user-guide/windows-native>
- Installation: <https://hermes-agent.nousresearch.com/docs/getting-started/installation>
- Releases (v0.13–v0.15.2): <https://github.com/NousResearch/hermes-agent/releases>
- Hermes Desktop (native GUI, 2026-06-02): MarkTechPost / digitalapplied coverage
