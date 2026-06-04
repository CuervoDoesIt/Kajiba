# Hermes Agent + Kajiba Plugin Setup Guide

**Status:** Stable
**Target environment:** Windows 11 host + WSL2 + NVIDIA RTX 4070 (8GB) + Ollama + Hermes Agent v0.6.0
**Audience:** A developer setting up a local environment to capture Hermes Agent session data with the Kajiba plugin.

This guide takes you from a bare Windows machine to a working WSL2 + NVIDIA GPU passthrough + Ollama + Hermes Agent v0.6.0 environment with the Kajiba plugin loaded. It is organized as ordered, checkpoint-gated stages. **Run the "Verification checkpoint" at the end of each stage and confirm it passes before moving to the next stage.** If a checkpoint fails, see the troubleshooting subsection for that stage before continuing — a silent failure in one layer (for example a CUDA stub overwrite forcing CPU inference) produces confusing failures three stages later.

The five gated stages are:

1. WSL2 install (Verification checkpoint: WSL2)
2. NVIDIA GPU passthrough (Verification checkpoint: GPU)
3. Ollama install + config (Verification checkpoint: Ollama)
4. Hermes Agent v0.6.0 install (Verification checkpoint: Hermes)
5. Kajiba plugin via symlink (Verification checkpoint: Plugin loads)

All commands are copy-pasteable. Unless stated as "in PowerShell" or "on the Windows host", every command runs **inside the WSL2 distro shell**.

---

## Stage 0: Prerequisites

Before starting, you need:

- **Windows 11** (host OS).
- **NVIDIA RTX 4070 (8GB)** or equivalent CUDA-capable GPU.
- **Python 3.11+** available inside WSL2 (the Kajiba code targets 3.11+; 3.13 is fine).
- **The Kajiba repository cloned inside the WSL2 native filesystem** (for example `~/Kajiba`, NOT under `/mnt/c/...` — see the CUDA troubleshooting note about keeping working files on the WSL2 native FS).
- **An active editable install of Kajiba** inside WSL2:

```bash
cd ~/Kajiba
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

The editable install (`pip install -e .`) is **required**: when Hermes loads the plugin, the plugin's `from kajiba.collector import KajibaCollector` must resolve against the installed `kajiba` package. If the editable install is missing or stale (for example after restructuring the package), re-run `pip install -e .`.

### Verification checkpoint: Prerequisites

```bash
python --version            # expect 3.11 or newer
python -c "import kajiba; print(kajiba.__version__)"   # imports cleanly
python -c "from kajiba.plugin import register; print(register)"  # plugin entry point importable
```

All three must succeed before proceeding.

---

## Stage 1: WSL2 install

Hermes Agent and Ollama run inside WSL2 on Windows. Install WSL2 and a Linux distribution.

In an **elevated PowerShell** (Run as Administrator) on the Windows host:

```powershell
wsl --install
wsl --set-default-version 2
```

Reboot if prompted. After reboot, launch the installed distro (for example Ubuntu) once to create your Linux user.

### Verification checkpoint: WSL2

On the Windows host, in PowerShell:

```powershell
wsl --status
wsl --list --verbose
```

Confirm:

- `wsl --status` reports the default version as **2**.
- `wsl --list --verbose` shows your distro with `VERSION` column = `2` and `STATE` = `Running` (or `Stopped`).
- Opening the distro shell drops you into a Linux prompt.

If the distro shows `VERSION 1`, convert it: `wsl --set-version <DistroName> 2`.

---

## Stage 2: NVIDIA GPU passthrough

WSL2 GPU support works by passing the **Windows** NVIDIA driver through to the Linux guest. You do **not** install a Linux GPU driver inside WSL2.

1. On the **Windows host**, install the latest NVIDIA Windows driver for the RTX 4070 from NVIDIA's official driver download page. This driver includes WSL2 CUDA support.
2. Do **not** install any `nvidia-driver-*` package inside WSL2.

### Verification checkpoint: GPU

Inside the WSL2 distro shell:

```bash
nvidia-smi
```

Confirm the output shows the **RTX 4070** and its **VRAM** (about 8192 MiB). If `nvidia-smi` is not found or shows no device, the Windows driver is missing or out of date — reinstall the Windows NVIDIA driver and restart WSL2 (`wsl --shutdown` from PowerShell, then reopen the distro).

### Troubleshooting: CUDA driver stub overwrite (MP-8)

This is the single most damaging GPU pitfall. If you later install the CUDA toolkit (needed for some workloads) and pull in the wrong meta-package, you can **overwrite the WSL2 `libcuda.so` driver stub**. Ollama then silently falls back to CPU inference (roughly 60x slower) with no error — it just runs slowly and `nvidia-smi` shows no VRAM in use.

To avoid this:

- Install **only** the toolkit package, never the driver meta-packages:

```bash
# CORRECT — toolkit only
sudo apt-get install -y cuda-toolkit-12-4
```

```bash
# WRONG — these overwrite the WSL2 driver stub, breaking GPU passthrough:
#   sudo apt-get install cuda
#   sudo apt-get install cuda-drivers
```

- After any CUDA install, verify the WSL2 driver stub is still a symlink (and was not replaced by a real file):

```bash
ls -l /usr/lib/wsl/lib/libcuda.so*
```

The `libcuda.so` / `libcuda.so.1` entries should remain symlinks into the WSL2 lib directory. If they were replaced, reinstall the Windows driver and restart WSL2.

- **Keep models and working files in the WSL2 native filesystem** (for example `~/...`), not under `/mnt/c/...`. Cross-filesystem access through `/mnt/c/` is slow and can interact badly with GPU memory-mapped model loads.

(MP-8 — WSL2 CUDA stub overwrite. This is an env-integrity issue, not a Kajiba code issue.)

---

## Stage 3: Ollama install + config (ENV-02)

Ollama provides local LLM inference inside WSL2. Hermes Agent talks to Ollama over its HTTP endpoint.

Inside the WSL2 distro shell:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Pull the model used for data collection (Hermes 3 8B):

```bash
ollama pull hermes3:8b
```

### Ollama configuration: num_ctx override (MP-5)

Ollama defaults the **effective** context window to **2048 tokens** regardless of the context length the model reports. For real sessions this silently truncates long prompts. Set `num_ctx` explicitly.

You can set it per request through the API:

```bash
curl http://localhost:11434/api/generate -d '{
  "model": "hermes3:8b",
  "prompt": "Hello",
  "options": { "num_ctx": 8192 }
}'
```

Or bake it into a custom model via a Modelfile so every call uses the larger window:

```bash
cat > Modelfile <<'EOF'
FROM hermes3:8b
PARAMETER num_ctx 8192
EOF
ollama create hermes3-8b-ctx -f Modelfile
```

Then point Hermes at `hermes3-8b-ctx`. (MP-5 — Ollama `num_ctx` default truncation. The actual scrubbing/quality use of long context is Phase 7; for setup you only need the override documented and applied.)

### Ollama configuration: custom endpoint

Hermes connects to Ollama at its HTTP endpoint, by default `http://localhost:11434`. Configure Hermes to use this endpoint (and the `hermes3:8b` / `hermes3-8b-ctx` model) per the Hermes model configuration in Stage 4. When Hermes and Ollama both run inside WSL2, `localhost` is the correct host.

### Troubleshooting: Ollama WSL2 network binding (MP-9)

Ollama binds to `127.0.0.1` by default. That is fine when **Hermes and Ollama both run inside WSL2** (the recommended topology). It becomes a problem only if you try to reach Ollama from the Windows host or from another network namespace — cross-namespace connections to `127.0.0.1:11434` are refused.

- **Recommended topology:** run Hermes Agent and Ollama **both inside the same WSL2 distro**. No binding changes needed; use `http://localhost:11434`.
- **If you must reach Ollama from the Windows host**, bind Ollama to all interfaces by setting `OLLAMA_HOST` before starting it:

```bash
export OLLAMA_HOST=0.0.0.0:11434
ollama serve
```

Then connect from the Windows host using the WSL2 instance IP (`wsl hostname -I`) on port 11434. Prefer the all-in-WSL2 topology unless you have a specific reason to split them. (MP-9 — Ollama WSL2 network binding.)

### Verification checkpoint: Ollama

Run a quick inference and confirm it uses the GPU:

```bash
ollama run hermes3:8b "Say hello in one short sentence."
```

In a second WSL2 shell, while that inference is running:

```bash
nvidia-smi
```

Confirm:

- `ollama run` produces text output.
- `nvidia-smi` shows **VRAM in use** (a `python`/`ollama` process consuming GPU memory) **during** inference.

If `nvidia-smi` shows no VRAM in use during inference, Ollama is on the CPU fallback path — revisit the CUDA stub overwrite troubleshooting in Stage 2 (MP-8).

---

## Stage 4: Hermes Agent v0.6.0 install

Install Hermes Agent v0.6.0 via the official Hermes install script — **not** via `pip` (Hermes is a system component installed through its vendor channel, like WSL2 and Ollama, not a Python registry package).

Inside the WSL2 distro shell, follow the official Hermes Agent v0.6.0 install instructions (install script). Confirm you are installing **v0.6.0** specifically, since this guide depends on its plugin contract and on `HERMES_HOME` profile isolation.

### HERMES_HOME profile isolation

Hermes v0.6.0 introduced **profile isolation** via the `HERMES_HOME` environment variable. `HERMES_HOME` points at the active Hermes profile directory; when it is unset, Hermes (and Kajiba) fall back to the default `~/.hermes`.

Kajiba resolves **all** of its paths — staging, outbox, plugin discovery, config — through this same home directory (via the shared `get_hermes_home()` resolver, which reads `HERMES_HOME` and falls back to `~/.hermes`). This matters for the plugin in Stage 5: the symlink target `~/.hermes/plugins/kajiba` assumes the **default** profile. If you run Hermes under a non-default `HERMES_HOME`, create the symlink under **that** profile's `plugins/` directory instead, and be aware that a different profile is a separate data namespace (its own staging/outbox), so previously collected records under `~/.hermes` will not appear.

### Verification checkpoint: Hermes

Inside the WSL2 distro shell:

```bash
hermes --version          # confirm v0.6.0
echo "${HERMES_HOME:-$HOME/.hermes}"   # shows the active Hermes home (default ~/.hermes if HERMES_HOME unset)
```

Start a Hermes session and confirm it launches and connects to Ollama. Confirm:

- Hermes reports **v0.6.0**.
- The active home directory printed above is the one you intend to use (it determines where the plugin symlink goes in Stage 5).
- A Hermes session starts without connection errors to the Ollama endpoint.

---

## Stage 5: Kajiba plugin (symlink dev workflow, ENV-03)

The Kajiba plugin source of truth lives in the repo at `src/kajiba/plugin/` (it contains `plugin.yaml`, `__init__.py` with `register(ctx)`, and `hooks.py`). During development you expose it to Hermes by **symlinking** it into the active Hermes profile's `plugins/` directory, so edits in the repo take effect without copying.

From the repo root in WSL2 (with `pip install -e .` already active), the workflow is 2-3 commands:

```bash
cd ~/Kajiba
mkdir -p ~/.hermes/plugins
ln -s "$(pwd)/src/kajiba/plugin" ~/.hermes/plugins/kajiba
```

This points `~/.hermes/plugins/kajiba` -> `src/kajiba/plugin`. Because `plugin.yaml` lives **inside** `src/kajiba/plugin/`, the symlink exposes the manifest to Hermes's plugin discovery scan. (If you run under a non-default `HERMES_HOME`, replace `~/.hermes` above with that profile directory.)

### Verification checkpoint: Plugin loads

Start a Hermes session with Kajiba debug mode enabled so the plugin announces itself and logs hook activity:

```bash
KAJIBA_DEBUG=1 hermes
```

Confirm in the Hermes log / stderr:

- A registration line like `Kajiba registered hooks: on_session_start, post_llm_call, post_tool_call, on_session_end` appears at startup (proves `register(ctx)` ran and wired all four hooks).
- As you interact with the session, `KAJIBA_DEBUG ...` lines appear when hooks fire, reporting each hook's kwarg names, types, and truncated values.

If you do **not** see the registration line, Hermes may not be following the symlink during plugin discovery. As a fallback, copy the directory instead of symlinking:

```bash
rm ~/.hermes/plugins/kajiba          # remove the broken symlink
cp -r ~/Kajiba/src/kajiba/plugin ~/.hermes/plugins/kajiba
```

With a copy you must re-copy after each edit (you lose the live-reload benefit of the symlink). The developer confirms which method (symlink vs copy) Hermes v0.6.0 actually supports during the live verification in Plan 05; until then, prefer the symlink and fall back to copy only if discovery fails.

### Security note: KAJIBA_DEBUG and session content

`KAJIBA_DEBUG=1` logs the kwargs each hook receives — including **truncated** previews of hook payloads, which may contain **unscrubbed session content** (prompts, responses, tool output). PII scrubbing happens later in the Kajiba pipeline (the CLI step), **not** in the hooks. Therefore:

- Treat `KAJIBA_DEBUG` logs as sensitive. **Do not share debug logs** (do not paste them into issues, chats, or this repo).
- **Turn debug off for normal use** — leave `KAJIBA_DEBUG` unset unless you are actively discovering hook shapes.

Debug mode is a diagnostic for confirming hook payloads, not a normal-operation setting.

---

## Stage 6: Edit-reload cycle

With the symlink in place, the development loop is:

1. Edit files under `src/kajiba/plugin/` (for example `hooks.py`) in the repo.
2. **Restart Hermes** to reload the plugin (Hermes loads plugins at startup; there is no hot-reload).
3. Re-run your session (with `KAJIBA_DEBUG=1` while iterating on hook shapes).

Because the symlink points at the repo, your edits are picked up on the next Hermes start with no copy step. If you changed the package structure or dependencies (not just plugin code), re-run `pip install -e .` so the editable install stays current, then restart Hermes.

---

## Summary checklist

| Stage | Verification checkpoint | Pass condition |
|-------|-------------------------|----------------|
| 0 Prerequisites | Python + kajiba import | `python -c "from kajiba.plugin import register"` succeeds |
| 1 WSL2 | `wsl --status` | Default version 2; distro runs |
| 2 GPU | `nvidia-smi` (in WSL2) | RTX 4070 + VRAM shown |
| 3 Ollama | `ollama run` + `nvidia-smi` | Output produced AND VRAM in use during inference |
| 4 Hermes | `hermes --version` + session | Reports v0.6.0; session starts |
| 5 Plugin loads | `KAJIBA_DEBUG=1 hermes` | `Kajiba registered hooks: ...` in log; debug lines on hook fire |

Once all checkpoints pass, the environment is ready for the live hook-discovery session (Plan 05), which captures the real hook kwargs and records them for Phase 7 turn assembly.
