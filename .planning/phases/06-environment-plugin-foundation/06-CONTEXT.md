# Phase 6: Environment + Plugin Foundation - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Set up the WSL2 + Hermes Agent + Ollama development environment with GPU verification, rewrite the Kajiba Hermes integration as a proper plugin directory that Hermes discovers and loads, confirm all 4 hook events fire with real kwargs, and migrate hardcoded `~/.hermes` paths to HERMES_HOME-aware resolution.

</domain>

<decisions>
## Implementation Decisions

### Plugin Location
- **D-01:** Plugin source code lives at `src/kajiba/plugin/` as a subdirectory of the main package. The plugin's `__init__.py` exports `register(ctx)` and imports from the parent `kajiba` package (`from kajiba.collector import KajibaCollector`).
- **D-02:** During development, a symlink from `~/.hermes/plugins/kajiba/` points into `src/kajiba/plugin/`. ENV-03 covers documenting this workflow.

### Setup Documentation
- **D-03:** Environment setup documented as a standalone guide at `docs/hermes-setup.md` with step-by-step instructions and verification checkpoints at each stage (WSL2, GPU passthrough, Ollama, Hermes, Kajiba plugin loading).
- **D-04:** Guide must include troubleshooting for known pitfalls: CUDA driver stub overwrite (install only `cuda-toolkit-12-x`), Ollama `num_ctx` default truncation, Ollama network binding in WSL2.

### Hook Discovery
- **D-05:** Hook discovery is built into the final plugin as a debug mode (`KAJIBA_DEBUG=1` env var). When enabled, the plugin logs all hook kwargs (names, types, values) to stderr/log. This stays as a permanent diagnostic tool, not a throwaway script.
- **D-06:** First task of the phase: deploy plugin with debug mode on, run a short Hermes session, capture the actual kwargs for `on_session_start`, `post_llm_call`, `post_tool_call`, `on_session_end`. Document findings in the phase directory.

### Old Integration
- **D-07:** Delete `src/kajiba/hermes_integration.py` entirely. The `HermesAgent` Protocol and `register_hooks()` function are completely wrong for the real Hermes API. Clean break.
- **D-08:** Tests that currently import from `hermes_integration` will be updated to use `KajibaCollector` directly — the collector is already independently usable without any adapter layer.

### HERMES_HOME Migration
- **D-09:** All hardcoded `~/.hermes` paths in `collector.py`, `cli.py`, `config.py`, and `publisher.py` must be replaced with HERMES_HOME-aware resolution. The `HERMES_HOME` env var (introduced in Hermes v0.6.0) specifies the active profile directory.
- **D-10:** Create a shared path resolution helper (e.g., `get_hermes_home()` in `config.py`) that checks `HERMES_HOME` env var first, falls back to `~/.hermes`. All modules import from this single source.

### Claude's Discretion
- Plugin directory structure details (`plugin.yaml` fields, `__init__.py` scaffolding)
- HERMES_HOME helper implementation approach
- Test migration strategy for `hermes_integration` imports
- Hook registration wiring between Hermes events and `KajibaCollector` methods

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Hermes Plugin API
- `.planning/research/FEATURES.md` — Confirmed Hermes plugin directory structure, `register(ctx)` API, hook event table with payloads
- `.planning/research/ARCHITECTURE.md` — Integration points, collector signature changes, build order
- `.planning/research/PITFALLS.md` — MP-1 (Protocol mismatch), MP-2 (hook kwargs), MP-4 (HERMES_HOME), MP-8 (CUDA stub), MP-9 (Ollama binding)

### Existing Codebase
- `src/kajiba/hermes_integration.py` — File to be deleted (D-07). Read to understand what tests depend on it.
- `src/kajiba/collector.py` — `KajibaCollector` class. Core lifecycle methods stay; `on_session_start` signature may need `model_name` + `platform` kwargs.
- `src/kajiba/config.py` — Hardcoded `~/.hermes` paths at lines 28-29, 89, 123. HERMES_HOME helper should live here.
- `src/kajiba/cli.py` — Hardcoded paths at lines 64-67, 688, 768.
- `src/kajiba/publisher.py` — Hardcoded path at line 38.

### Project Spec
- `docs/kajiba-project-spec.md` — Full pipeline design, schema spec, controlled vocabularies

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `KajibaCollector` class (`collector.py:152`) — Core session lifecycle logic. Methods `on_session_start`, `on_turn_complete`, `on_session_end` map directly to Hermes hook events with minor signature adjustments.
- `_detect_hardware()` (`collector.py:43`) — GPU detection via nvidia-smi. Already works, no changes needed.
- `_extract_model_metadata()` (`collector.py:131`) — Extracts `ModelMetadata` from a dict. Signature needs updating to accept Hermes's `model` string + Ollama metadata instead of `model_config` dict.

### Established Patterns
- Module-level constants for paths: `KAJIBA_BASE`, `STAGING_DIR`, `OUTBOX_DIR` — all need HERMES_HOME migration.
- Fault-tolerant design: all collector methods wrap body in `try/except Exception` with `logger.exception()`.
- Soft dependency pattern: `psutil`, `pyyaml` imported conditionally with graceful fallback.

### Integration Points
- `~/.hermes/plugins/kajiba/` — New plugin directory discovered by Hermes at startup.
- `~/.hermes/config.yaml` — Existing Kajiba config section. Path resolution changes but config structure stays.
- `HERMES_HOME` env var — v0.6.0 profile isolation. Must be respected in both plugin context and CLI context.

</code_context>

<specifics>
## Specific Ideas

- Debug mode (`KAJIBA_DEBUG=1`) should be useful beyond initial discovery — log all hook activity for ongoing troubleshooting.
- Setup guide should have explicit "checkpoint" sections where the user can verify each component works before moving on (WSL2 ✓, GPU ✓, Ollama ✓, Hermes ✓, Plugin loads ✓).
- The symlink dev workflow (ENV-03) should be simple enough to explain in 2-3 commands.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 06-environment-plugin-foundation*
*Context gathered: 2026-04-03*
