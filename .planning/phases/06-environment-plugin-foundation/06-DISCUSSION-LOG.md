# Phase 6: Environment + Plugin Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

This phase was discussed twice: **Round 1** (2026-04-03, original) and **Round 2**
(2026-06-05, re-plan after Hermes v0.6.0 → v0.15.x + native Windows). Round 2 supersedes
the stale parts of Round 1; both are preserved for audit.

---

# Round 1 — Original discussion

**Date:** 2026-04-03
**Phase:** 06-environment-plugin-foundation
**Areas discussed:** Plugin location, Setup guide, Hook discovery, Old integration

---

## Plugin Location

| Option | Description | Selected |
|--------|-------------|----------|
| src/kajiba/plugin/ | Subdirectory inside the existing package — stays cohesive, pip install can expose it via entry point, symlink the subdir to ~/.hermes/plugins/kajiba/ | ✓ |
| hermes-plugin/ | Separate top-level directory alongside src/ — clear separation, easy to copy/symlink wholesale, but split from the main package | |
| You decide | Claude picks the most practical approach based on how pip entry points and Hermes plugin discovery work | |

**User's choice:** src/kajiba/plugin/
**Notes:** Keeps everything in one package. Plugin's __init__.py exports register(ctx) and imports from parent kajiba package.

---

## Setup Guide

| Option | Description | Selected |
|--------|-------------|----------|
| docs/hermes-setup.md | Standalone guide with step-by-step instructions, verification checkpoints at each stage, and troubleshooting section | ✓ |
| Makefile + doc | Makefile targets (make setup-wsl, make setup-ollama, make setup-hermes) with a companion guide | |
| You decide | Claude picks whatever gets the job done clearly | |

**User's choice:** docs/hermes-setup.md
**Notes:** Standalone doc with verification checkpoints at each stage.

---

## Hook Discovery

| Option | Description | Selected |
|--------|-------------|----------|
| Debug mode in plugin | Build a KAJIBA_DEBUG=1 mode into the final plugin that logs all hook kwargs. Discovery work becomes a permanent diagnostic tool. | ✓ |
| Throwaway script | Quick standalone script to dump hook kwargs to a file. Once confirmed, delete and write the real plugin. | |
| You decide | Claude picks whichever gets discovery done fastest | |

**User's choice:** Debug mode in plugin
**Notes:** KAJIBA_DEBUG=1 stays as a permanent diagnostic tool for troubleshooting integration issues.

---

## Old Integration

| Option | Description | Selected |
|--------|-------------|----------|
| Delete and start fresh | Remove hermes_integration.py entirely. New plugin lives in src/kajiba/plugin/. Tests use KajibaCollector directly. | ✓ |
| Keep as adapter | Refactor into thin adapter for non-Hermes use cases. Tests keep using it. | |
| You decide | Claude picks based on what tests actually need | |

**User's choice:** Delete and start fresh
**Notes:** Clean break. KajibaCollector is already directly usable without any adapter layer.

---

## Claude's Discretion (Round 1)

- Plugin directory structure details (plugin.yaml fields, __init__.py scaffolding)
- HERMES_HOME helper implementation approach
- Test migration strategy for hermes_integration imports
- Hook registration wiring between Hermes events and KajibaCollector methods

## Deferred Ideas (Round 1)

None — discussion stayed within phase scope.

---

# Round 2 — Re-plan (Hermes v0.6.0 → v0.15.x + native Windows)

**Date:** 2026-06-05
**Areas discussed:** Platform & version target, Setup guide (rewrite vs supersede), Hook verification (06-05) scope, Plugin enable + discovery dir
**Trigger:** Hermes shipped native Windows and jumped to v0.15.x; dev machine runs v0.15.1 natively; hook kwargs now officially documented. Waves 1–4 (06-01..06-04) verified still-correct except the WSL2-centric setup guide. See `06-REPLAN-RESEARCH.md`.

---

## Context handling (entry gate)

| Option | Description | Selected |
|--------|-------------|----------|
| Update it (re-plan) | Re-discuss stale areas, rewrite CONTEXT.md to v0.15.x / native Windows, replan 06-04/06-05 | ✓ |
| View it first | Show existing CONTEXT.md + re-plan research, then decide | |
| Skip discussion | Leave CONTEXT.md as-is, go straight to replanning | |

**User's choice:** Update it (re-plan)

---

## Platform & version target

| Option | Description | Selected |
|--------|-------------|----------|
| Native primary, WSL2 appendix | Native Windows = primary documented path; WSL2/GPU/Ollama → optional appendix; bump v0.6.0 → v0.15.x everywhere | ✓ |
| Native only, defer WSL2/Ollama | Strip WSL2/GPU/Ollama from this phase entirely; revisit local inference in Phase 7/9 | |
| Keep WSL2 co-equal | Document native Windows + WSL2 as two equal primary paths | |

**User's choice:** Native primary, WSL2 appendix
**Notes:** Keeps the RTX 4070 path available for Phase 7 (GLiNER) / Phase 9 (QLoRA) without making local inference a Phase 6 gate. Hook/plugin verification needs no GPU or Ollama. → CONTEXT D-11/D-12.

---

## Setup guide — rewrite vs supersede

| Option | Description | Selected |
|--------|-------------|----------|
| Corrective in-place rewrite | Restructure docs/hermes-setup.md to native-primary, WSL2 as appendix; preserve path + history; fold in `hermes plugins enable` + `HERMES_PLUGINS_DEBUG` | ✓ |
| Supersede with new guide | Fresh native-Windows guide; deprecate/archive the old one | |
| Minimal patch on top | Add a native quickstart section above the existing WSL2 stages | |

**User's choice:** Corrective in-place rewrite
**Notes:** Preserves git history; CUDA-stub / Ollama-num_ctx / Ollama-WSL2-binding troubleshooting moves into the optional WSL2 appendix. → CONTEXT D-13/D-14 (D-04 revised).

---

## Hook verification (06-05) scope

| Option | Description | Selected |
|--------|-------------|----------|
| Live session via KAJIBA_DEBUG | ~15-min live v0.15.1 session (remote backend, no GPU/Ollama), capture real kwargs → 06-HOOK-KWARGS.md, tag [DOCUMENTED v0.15.x] + [VERIFIED] | ✓ |
| Live + inspect installed source | Live run plus reading installed Hermes source to cross-check signatures | |
| Documentation only | Transcribe documented kwargs, tag [DOCUMENTED v0.15.x], no live run | |

**User's choice:** Live session via KAJIBA_DEBUG
**Notes:** Matches HITL/empirical-verification stance; closes the old "no formal payload schema published" blocker. Original premise (multi-hour WSL2 build to discover undocumented kwargs) is obsolete. → CONTEXT D-15/D-16/D-21.

---

## Plugin enable + discovery dir

| Option | Description | Selected |
|--------|-------------|----------|
| Resolve via installed source, then document | Inspect installed Hermes source to settle <HERMES_HOME>/plugins/ vs ~/.hermes/plugins/; set symlink target; promote plugin.yaml [ASSUMED]→[CONFIRMED]; add `hermes plugins enable` as required step | ✓ |
| Document both dirs defensively | Guide lists both candidate locations with a 'verify which' note | |
| Assume <HERMES_HOME>/plugins/ | Proceed with profile-relative dir without source confirmation | |

**User's choice:** Resolve via installed source, then document
**Notes:** Under this machine's overridden `HERMES_HOME=%LOCALAPPDATA%\hermes`, the discovery dir determines the D-02 symlink target. `hermes plugins enable kajiba` is required (discovered-but-disabled plugins don't load). → CONTEXT D-17/D-18/D-19.

---

## Claude's Discretion (Round 2)

- Traceability bookkeeping — reconciling PLUG-02/PLUG-03/CAPT-01 partial/complete marks during planning.
- Native-primary vs WSL2-appendix section split and checkpoint wording in the guide.
- The specific short task run during the ~15-min live verification session.
- Whether to refresh `[ASSUMED]` / v0.6.0 wording in inline docstrings beyond `plugin.yaml`.

## Flagged for follow-up (outside discuss-phase scope)

- **ENV-01 / ENV-02 / ROADMAP Success Criterion #1** name WSL2 / GPU passthrough / Ollama / v0.6.0 as required — now stale under native-Windows-primary. Update wording via `/gsd-phase` so "done" reflects the new reality. Captured as CONTEXT D-20 (not edited here — no direct ROADMAP/REQUIREMENTS writes from discuss-phase).

## Deferred Ideas (Round 2)

None new — discussion stayed within phase scope.

### Reviewed Todos (not folded)

- `2026-06-04-fix-experiment-relog-dedup-cr01.md` (CR-01 + Phase 11 review warnings) — v1.2 experiment-store/CLI work, unrelated to the plugin-foundation re-plan. Weak keyword match only; deferred.
