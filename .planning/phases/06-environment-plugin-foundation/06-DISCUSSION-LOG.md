# Phase 6: Environment + Plugin Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

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

## Claude's Discretion

- Plugin directory structure details (plugin.yaml fields, __init__.py scaffolding)
- HERMES_HOME helper implementation approach
- Test migration strategy for hermes_integration imports
- Hook registration wiring between Hermes events and KajibaCollector methods

## Deferred Ideas

None — discussion stayed within phase scope.
