---
phase: 06-environment-plugin-foundation
plan: 04
subsystem: docs
tags: [wave-4, docs, hermes-setup, wsl2, gpu, ollama, env-01, env-02, env-03]
requires:
  - "Plan 03: src/kajiba/plugin/ package (plugin.yaml + register(ctx) + KAJIBA_DEBUG hooks) — the symlink target and the registration line the Plugin-loads checkpoint observes"
  - "Plan 02: get_hermes_home() HERMES_HOME resolver — the guide's HERMES_HOME profile-isolation notes describe its runtime behavior"
provides:
  - "docs/hermes-setup.md: end-to-end WSL2/GPU/Ollama/Hermes v0.6.0/plugin setup guide (ENV-01/02/03, D-03/D-04)"
  - "Five per-stage verification checkpoints (WSL2, GPU, Ollama, Hermes, Plugin loads) a developer self-confirms before proceeding"
  - "2-3 command symlink dev workflow (ln -s src/kajiba/plugin -> ~/.hermes/plugins/kajiba) with copy fallback"
  - "Troubleshooting for MP-8 (CUDA stub overwrite), MP-5 (num_ctx truncation), MP-9 (Ollama WSL2 binding)"
affects:
  - "Plan 05 (live session) — this guide is the script the human checkpoint follows to install/verify the env, then run the KAJIBA_DEBUG discovery session"
  - "Phase 7 live capture — depends on the env this guide builds being functional (GPU inference, plugin loaded)"
tech-stack:
  added: []
  patterns:
    - "Checkpoint-gated install guide: each stage ends in a 'Verification checkpoint' the dev runs before the next stage"
    - "No-emoji Markdown docs (## / ### headers, fenced bash/yaml/powershell blocks) per CLAUDE.md"
key-files:
  created:
    - docs/hermes-setup.md
  modified: []
decisions:
  - "Used the word 'Verification checkpoint' for every stage gate (not the CONTEXT.md ✓ glyphs) to honor CLAUDE.md no-emoji conventions while keeping the user's checkpoint-section structure from CONTEXT.md."
  - "Symlink workflow documents a copy-not-symlink fallback inline (RESEARCH Q3/A3) so the guide is correct whichever discovery behavior Plan 05 confirms — symlink is presented as the default, copy as the fallback when no registration line appears."
  - "CUDA toolkit example pins cuda-toolkit-12-4 (a concrete 12.x point release) rather than a bare cuda-toolkit-12, satisfying the plan's 'cuda-toolkit-12' token requirement while showing a copy-pasteable command; WRONG meta-packages (cuda / cuda-drivers) shown as commented anti-examples per MP-8."
metrics:
  duration: ~2m
  completed: 2026-06-04
---

# Phase 6 Plan 04: Hermes Setup Guide Summary

Wrote `docs/hermes-setup.md` (D-03): a standalone, checkpoint-driven guide taking a developer from a bare Windows 11 machine to a working WSL2 + NVIDIA GPU passthrough + Ollama + Hermes Agent v0.6.0 environment with the Kajiba plugin loaded (ENV-01/02), documenting the 2-3 command symlink dev workflow (ENV-03), and baking the three known pitfalls in as troubleshooting sections (D-04). The guide is the developer-facing deliverable for ENV-01/02/03 and the script the human checkpoint in Plan 05 executes to stand up the env before the live `KAJIBA_DEBUG=1` hook-discovery session.

## What Was Built

**Task 1 — `docs/hermes-setup.md` (commit 875246f, 316 lines)**

Seven ordered sections, the five middle ones each ending in an explicit "Verification checkpoint":

- **Stage 0 Prerequisites** — Windows 11, RTX 4070 (8GB), Python 3.11+, repo cloned in the WSL2 **native FS** (not `/mnt/c/`), and the required `pip install -e .` editable install (so the plugin's `from kajiba.collector import KajibaCollector` resolves when Hermes loads it). Checkpoint: `python -c "from kajiba.plugin import register"` succeeds.
- **Stage 1 WSL2** — `wsl --install` / `--set-default-version 2` (elevated PowerShell). Checkpoint: `wsl --status` shows default version 2; `--list --verbose` shows the distro at VERSION 2.
- **Stage 2 NVIDIA GPU passthrough** — install the **Windows** NVIDIA driver (NOT a Linux driver in WSL2). Checkpoint: `nvidia-smi` in WSL2 shows the RTX 4070 + ~8192 MiB. **Troubleshooting CUDA driver stub overwrite (MP-8):** install only `cuda-toolkit-12-4`, never `cuda`/`cuda-drivers` (shown as commented WRONG examples); verify `/usr/lib/wsl/lib/libcuda.so*` stays a symlink; keep models on the WSL2 native FS.
- **Stage 3 Ollama install + config (ENV-02)** — install script, `ollama pull hermes3:8b`; **num_ctx override (MP-5)** via API `options.num_ctx` AND a Modelfile (`PARAMETER num_ctx 8192` → `ollama create`); custom endpoint (`http://localhost:11434`). **Troubleshooting Ollama WSL2 binding (MP-9):** default `127.0.0.1` bind — recommend Hermes+Ollama both in WSL2, else `export OLLAMA_HOST=0.0.0.0:11434`. Checkpoint: `ollama run` produces output AND `nvidia-smi` shows VRAM in use **during** inference (rules out CPU fallback).
- **Stage 4 Hermes Agent v0.6.0** — install via the Hermes install script (not pip). Documents **HERMES_HOME** profile isolation and that Kajiba resolves all paths through `get_hermes_home()` (forward-links the Stage 5 symlink target to the active profile). Checkpoint: `hermes --version` = v0.6.0; `echo ${HERMES_HOME:-$HOME/.hermes}`; session starts.
- **Stage 5 Kajiba plugin (ENV-03)** — the symlink dev workflow in 3 commands (`cd` repo, `mkdir -p ~/.hermes/plugins`, `ln -s "$(pwd)/src/kajiba/plugin" ~/.hermes/plugins/kajiba`); notes `plugin.yaml` lives inside the linked dir. Checkpoint "Plugin loads": `KAJIBA_DEBUG=1 hermes`, observe `Kajiba registered hooks: ...` at startup and `KAJIBA_DEBUG ...` lines on hook fire; **copy-not-symlink fallback** documented for the case Hermes does not follow symlinks during discovery (Q3/A3). **Security note:** `KAJIBA_DEBUG=1` logs truncated hook payloads that may contain unscrubbed session content (PII) — do not share debug logs; debug off for normal use (T-06-09).
- **Stage 6 Edit-reload cycle** — edit under `src/kajiba/plugin/`, restart Hermes to reload; re-run `pip install -e .` only on structure/dep changes.

Closes with a summary checklist table mapping each stage to its checkpoint and pass condition.

## Verification Results

- Plan automated check (`docs/hermes-setup.md` contains all of `WSL2`, `nvidia-smi`, `cuda-toolkit-12`, `num_ctx`, `OLLAMA_HOST`, `HERMES_HOME`, `ln -s`, `register` AND ≥ 120 lines) → **MISSING: [] ; LINES: 316 ; VERIFY PASS**.
- Each of the five stages (WSL2, GPU, Ollama, Hermes, Plugin) has an explicit "Verification checkpoint" subsection.
- Symlink workflow is 3 commands targeting `~/.hermes/plugins/kajiba` → `src/kajiba/plugin` (`ln -s`).
- Troubleshooting sections present for MP-8 (CUDA stub), MP-5 (num_ctx), MP-9 (Ollama binding).
- No emojis in the doc (CLAUDE.md); checkpoint gates use the word "Verification checkpoint".

## Requirements Satisfied

- **ENV-01** — Documented WSL2 + NVIDIA GPU passthrough + Hermes v0.6.0 + Ollama setup with per-stage verification checkpoints.
- **ENV-02** — Ollama configuration documented: `num_ctx` override (API + Modelfile), `hermes3:8b` pull, custom endpoint.
- **ENV-03** — 2-3 command symlink dev workflow linking `src/kajiba/plugin` into `~/.hermes/plugins/kajiba`, with copy fallback.

## Threat Mitigations Applied

- **T-06-09** (Info disclosure — guide omitting the KAJIBA_DEBUG PII-in-logs warning): explicit Security note in Stage 5 states debug logs may contain unscrubbed (truncated) session content, must not be shared, and debug stays off for normal use.
- **T-06-10** (Tampering — CUDA meta-package overwriting the WSL2 driver stub, MP-8): CUDA troubleshooting instructs installing only `cuda-toolkit-12-4` and verifying `libcuda.so` stays a symlink.
- **T-06-SC** (system-component installs — WSL2/Ollama/Hermes/CUDA toolkit): accept disposition; all installed via official vendor channels documented in the guide, not registry packages. No slopcheck applicable.

## Deviations from Plan

None — plan executed exactly as written. Rules 1–4 not triggered. Documented choices (see frontmatter `decisions`): used the words "Verification checkpoint" instead of the CONTEXT.md ✓ glyphs (CLAUDE.md no-emoji), and documented the copy-not-symlink fallback inline so the guide is correct under either Hermes discovery behavior pending Plan 05.

## Self-Check: PASSED

- docs/hermes-setup.md — FOUND (316 lines)
- commit 875246f — FOUND
