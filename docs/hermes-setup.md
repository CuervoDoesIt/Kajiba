# Hermes Agent + Kajiba Plugin Setup Guide

**Status:** Stable
**Target environment:** Windows 11 (native) + Hermes Agent v0.15.x + remote backend (OpenAI / Anthropic)
**Audience:** A developer setting up a local environment to capture Hermes Agent session data with the Kajiba plugin.

This guide takes you from a working Windows machine to a running Hermes Agent v0.15.x install with the Kajiba plugin discovered, **enabled**, and firing its lifecycle hooks. The primary path is **native Windows** (no virtualization layer, no GPU, no local model server): the Kajiba plugin and its hooks need **no GPU and no local model** and fire on **any** backend, including remote OpenAI and Anthropic. The optional **Appendix** at the end of this guide covers a local-inference stack (a Linux virtualization layer + NVIDIA GPU passthrough + a local model server) needed only for local inference or the dashboard `/chat` embedded terminal.

This machine runs `HERMES_HOME=%LOCALAPPDATA%\hermes` (the active Hermes profile directory). Kajiba resolves all of its paths through this same home directory via the shared `get_hermes_home()` resolver (reads `HERMES_HOME`, falls back to `~/.hermes`).

The guide is organized as ordered, checkpoint-gated steps. **Run the "Verification checkpoint" at the end of each step and confirm it passes before moving to the next step.** A silent failure in one layer (for example a discovered-but-disabled plugin) produces confusing failures later. Because the live environment cannot be unit-tested, these per-step checkpoints are how you self-confirm each layer before the live hook-kwargs session in Plan 05.

The six primary native-Windows steps are:

1. Install Hermes Agent v0.15.x (native Windows) — Verification checkpoint: Hermes
2. Editable-install Kajiba — Verification checkpoint: Kajiba import
3. Symlink the plugin into the Hermes discovery `plugins/` directory — Verification checkpoint: symlink
4. Enable the plugin (`hermes plugins enable kajiba`) — Verification checkpoint: enabled
5. Plugin loads and hooks fire — Verification checkpoint: Plugin loads
6. Edit-reload cycle

Unless stated as "in elevated cmd" or "on the Windows host", every command runs in a normal **PowerShell** prompt at the repo root. All commands are copy-pasteable.

<!--
Note on ROADMAP / REQUIREMENTS wording (D-20):
ROADMAP Phase 6 Success Criterion #1 and requirements ENV-01 / ENV-02 still name
the legacy local-inference stack (a Linux virtualization layer + NVIDIA GPU
passthrough + a local model server) and an older Hermes version as the *required*
path. Under the native-Windows-primary contract that wording is stale: the
underlying intent (a documented, verifiable Hermes environment with the plugin
loaded) is now satisfied on native Windows with a remote backend, and the legacy
local-inference stack satisfies only the optional Appendix. This needs a later
/gsd-phase edit to reconcile the SC-1 and ENV-01 / ENV-02 wording. This guide
flags but does NOT edit ROADMAP.md or REQUIREMENTS.md.
-->

> **Note on stale ROADMAP / REQUIREMENTS wording (D-20):** ROADMAP Phase 6 Success Criterion #1 and requirements ENV-01 / ENV-02 still name the legacy local-inference stack (a Linux virtualization layer + GPU passthrough + a local model server) and an older Hermes version as the *required* path. That wording is now stale under native-Windows-primary and needs a later `/gsd-phase` reconciliation. This guide flags it but does not edit those files.

---

## Step 1: Install Hermes Agent v0.15.x (native Windows)

Hermes Agent ships a native Windows install since v0.14.0; no WSL2 is required. Pick one of the official install methods:

- **PowerShell install script** (recommended):

```powershell
iex (irm https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.ps1)
```

- **pip install**, then launch:

```powershell
pip install hermes-agent
hermes
```

- **Hermes Desktop** — the public-preview `.exe` (bundles a recent v0.15.x). Download from the official Hermes release page.

On native Windows the data layout is:

- `%LOCALAPPDATA%\hermes\hermes-agent\` — the git checkout + venv (disposable; recreated on reinstall).
- `%USERPROFILE%\.hermes\` — config / auth / skills / sessions / logs (survives reinstalls) **by default**.
- `HERMES_HOME` overrides the active profile directory. On this machine it is set to `%LOCALAPPDATA%\hermes`, so that is the live profile (holding `config.yaml`, `auth.json`, `sessions`, `skills`, `hooks`, `logs`, `state.db`, and a `kajiba` data directory).

Configure a remote backend (OpenAI or Anthropic) per the Hermes auth flow; no local model is required for plugin/hook verification.

### Verification checkpoint: Hermes

In PowerShell:

```powershell
hermes --version
echo $env:HERMES_HOME
```

Confirm:

- `hermes --version` reports **v0.15.x** (this machine: v0.15.1; current published is v0.15.2 — `hermes update` upgrades).
- The active `HERMES_HOME` is the profile directory you intend to use (this machine: `%LOCALAPPDATA%\hermes`). If `$env:HERMES_HOME` is empty, Hermes uses the default `%USERPROFILE%\.hermes`. Record the value you see — it determines where the plugin symlink goes in Step 3.
- A Hermes session starts and connects to your remote backend without errors.

---

## Step 2: Editable-install Kajiba

When Hermes loads the plugin, the plugin's `from kajiba.collector import KajibaCollector` must resolve against an installed `kajiba` package. Install Kajiba **editable** from the repo root so edits take effect without reinstalling:

```powershell
cd <path-to-repo>\Kajiba
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

The editable install (`pip install -e .`) is **required**. If it is missing or stale (for example after restructuring the package), re-run `pip install -e .`.

> Note: Hermes runs inside its own venv (`%LOCALAPPDATA%\hermes\hermes-agent\venv`). For Hermes to import `kajiba` when it loads the plugin, the `kajiba` package must be importable in the environment Hermes runs under. If Hermes does not share your repo venv, run `pip install -e .` (pointing at the repo root) inside the Hermes venv as well, or install Kajiba into the environment on Hermes's `PYTHONPATH`.

### Verification checkpoint: Kajiba import

```powershell
python --version
python -c "import kajiba; print(kajiba.__version__)"
python -c "from kajiba.plugin import register; print(register)"
```

Confirm:

- `python --version` reports 3.11 or newer.
- `import kajiba` succeeds and prints a version.
- `from kajiba.plugin import register` succeeds and prints the function — the plugin `register(ctx)` entry point is importable.

All three must succeed before proceeding.

---

## Step 3: Symlink the plugin into the Hermes discovery `plugins/` directory

The Kajiba plugin source of truth lives in the repo at `src\kajiba\plugin\` (it contains `plugin.yaml`, `__init__.py` with `register(ctx)`, and `hooks.py`). During development you expose it to Hermes by **symlinking** that directory into the active Hermes profile's `plugins\` discovery directory, so edits in the repo take effect without copying. Because `plugin.yaml` lives **inside** `src\kajiba\plugin\`, the link exposes the manifest to Hermes's discovery scan.

> **Discovery directory:** The exact discovery directory — whether Hermes scans `<HERMES_HOME>\plugins\` or always `%USERPROFILE%\.hermes\plugins\` when `HERMES_HOME` is overridden — is confirmed empirically by inspecting the installed Hermes source in Plan 05 (D-17). Use the directory that Plan 05 resolves. The commands below use a `<plugins-dir>` placeholder; substitute the resolved directory (most likely `%LOCALAPPDATA%\hermes\plugins` on this machine, or `%USERPROFILE%\.hermes\plugins` by default).

Native Windows offers two ways to create the symlink. Either works; the directory link must point `<plugins-dir>\kajiba` at the repo's `src\kajiba\plugin`.

- **PowerShell** (no elevation needed if Developer Mode is enabled):

```powershell
New-Item -ItemType Directory -Force -Path "<plugins-dir>"
New-Item -ItemType SymbolicLink -Path "<plugins-dir>\kajiba" -Target "<path-to-repo>\Kajiba\src\kajiba\plugin"
```

- **Elevated cmd** (Run as Administrator):

```bat
mkdir "<plugins-dir>"
mklink /D "<plugins-dir>\kajiba" "<path-to-repo>\Kajiba\src\kajiba\plugin"
```

**Copy fallback:** If symlink discovery is not followed by Hermes, copy the directory instead:

```powershell
Remove-Item -Recurse -Force "<plugins-dir>\kajiba"   # remove the broken link
Copy-Item -Recurse "<path-to-repo>\Kajiba\src\kajiba\plugin" "<plugins-dir>\kajiba"
```

With a copy you must re-copy after each edit (you lose the live-reload benefit of the symlink). Plan 05 confirms which method Hermes v0.15.x actually follows during live verification; until then, prefer the symlink and fall back to copy only if discovery fails.

### Verification checkpoint: symlink

```powershell
Get-Item "<plugins-dir>\kajiba" | Select-Object Name, LinkType, Target
Test-Path "<plugins-dir>\kajiba\plugin.yaml"
```

Confirm:

- The link (or copied directory) exists at `<plugins-dir>\kajiba`.
- `plugin.yaml` is visible **inside** that directory (proves the manifest is exposed to discovery).

---

## Step 4: Enable the plugin

**This is the easiest step to forget, and it is REQUIRED.** A plugin that Hermes *discovers* is not automatically *loaded* — it must be **enabled** first. A discovered-but-disabled plugin will not load and its `register(ctx)` will never run.

```powershell
hermes plugins enable kajiba
```

### Verification checkpoint: enabled

```powershell
hermes plugins list
```

Confirm `kajiba` appears in the plugins list marked as **enabled**. If it is listed but disabled, re-run `hermes plugins enable kajiba`. If it is not listed at all, return to Step 3 — Hermes is not discovering the plugin directory.

---

## Step 5: Plugin loads and hooks fire

Start a Hermes session with Kajiba debug mode enabled so the plugin announces itself and logs hook activity. Optionally also set Hermes's own discovery debug to see verbose discovery logging on stderr:

```powershell
$env:KAJIBA_DEBUG="1"
$env:HERMES_PLUGINS_DEBUG="1"   # optional: Hermes's own verbose plugin-discovery logging
hermes
```

`HERMES_PLUGINS_DEBUG=1` is **Hermes's own** discovery logging (it shows how Hermes scans, discovers, and enables plugins) and complements Kajiba's `KAJIBA_DEBUG=1` (which logs the kwargs each Kajiba hook receives).

Confirm in the Hermes log / stderr:

- A registration line like `Kajiba registered hooks: on_session_start, post_llm_call, post_tool_call, on_session_end` appears at startup. This proves `register(ctx)` ran and wired all four hooks.
- As you interact with the session, `KAJIBA_DEBUG ...` lines appear when hooks fire, reporting each hook's kwarg names, types, and truncated values.

### Verification checkpoint: Plugin loads

- The `Kajiba registered hooks: ...` registration line is present at startup.
- At least one `KAJIBA_DEBUG ...` hook line appears after a short interaction (a single prompt and response is enough to fire `on_session_start` and `post_llm_call`).

If you do **not** see the registration line, the plugin is discovered/enabled but `register(ctx)` did not run — re-check Step 4 (enabled) and Step 2 (the `kajiba` package is importable in Hermes's environment).

### Security note: KAJIBA_DEBUG and session content

`KAJIBA_DEBUG=1` logs the kwargs each hook receives — including **truncated** previews of hook payloads, which may contain **unscrubbed session content** (prompts, responses, tool output). PII scrubbing happens later in the Kajiba pipeline (the CLI step), **not** in the hooks. Therefore:

- Treat `KAJIBA_DEBUG` logs as sensitive. **Do not share debug logs** (do not paste them into issues, chats, or this repo).
- **Turn debug off for normal use** — leave `KAJIBA_DEBUG` unset unless you are actively confirming hook shapes (`Remove-Item Env:\KAJIBA_DEBUG` to clear it in PowerShell).
- `HERMES_PLUGINS_DEBUG=1` is Hermes's own discovery logging and is generally far less PII-bearing than `KAJIBA_DEBUG`, but still keep all such logs local.

Debug mode is a diagnostic for confirming hook payloads, not a normal-operation setting. (T-06-09.)

---

## Step 6: Edit-reload cycle

With the symlink in place, the development loop is:

1. Edit files under `src\kajiba\plugin\` (for example `hooks.py`) in the repo.
2. **Restart Hermes** to reload the plugin (Hermes loads plugins at startup; there is no hot-reload).
3. Re-run your session (with `KAJIBA_DEBUG=1` while iterating on hook shapes).

Because the symlink points at the repo, your edits are picked up on the next Hermes start with no copy step. If you changed the **package structure or dependencies** (not just plugin code), re-run `pip install -e .` so the editable install stays current, then restart Hermes. (If you used the copy fallback in Step 3, re-copy the directory after each edit.)

---

## Summary checklist (primary native-Windows path)

| Step | Verification checkpoint | Pass condition |
|------|-------------------------|----------------|
| 1 Install Hermes v0.15.x | `hermes --version` + `$env:HERMES_HOME` | Reports v0.15.x; active HERMES_HOME recorded; session connects to remote backend |
| 2 Editable-install Kajiba | `python -c "from kajiba.plugin import register"` | Import succeeds in Hermes's environment |
| 3 Symlink plugin | `Get-Item <plugins-dir>\kajiba` + `plugin.yaml` present | Link (or copy) exists; manifest visible to discovery |
| 4 Enable plugin | `hermes plugins enable kajiba` + `hermes plugins list` | `kajiba` listed and **enabled** (REQUIRED — easy to forget) |
| 5 Plugin loads / hooks fire | `KAJIBA_DEBUG=1 hermes` | `Kajiba registered hooks: ...` at startup; `KAJIBA_DEBUG` line on hook fire |
| 6 Edit-reload | Edit + restart Hermes | Repo edits picked up on next start (no GPU / no Ollama needed) |

Once all six checkpoints pass, the environment is ready for the live hook-kwargs session (Plan 05), which captures the real hook kwargs on a remote backend (no GPU, no Ollama) and records them in `06-HOOK-KWARGS.md` for Phase 7 turn assembly. None of the steps above require WSL2, a GPU, or Ollama — the appendix below is entirely optional.

---

## Appendix: WSL2 + NVIDIA GPU + Ollama (local inference / dashboard terminal only)

This appendix is **OPTIONAL**. You need it **only** for local GPU inference (for example running Ollama on an RTX 4070) or for the Hermes dashboard `/chat` embedded terminal pane, which needs a POSIX PTY and therefore WSL2. **Plugin load and hook verification (the primary path above) require none of this** — the Kajiba hooks fire on any backend, including remote OpenAI / Anthropic, with no GPU and no Ollama.

The WSL2 stack is the original setup path, preserved here verbatim for readers who choose local inference. The old MP-8 / MP-5 / MP-9 troubleshooting is relevant **only** under WSL2 + local Ollama.

Unless stated as "in PowerShell" or "on the Windows host", every command in this appendix runs **inside the WSL2 distro shell**.

### A.1 WSL2 install

In an **elevated PowerShell** (Run as Administrator) on the Windows host:

```powershell
wsl --install
wsl --set-default-version 2
```

Reboot if prompted. After reboot, launch the installed distro (for example Ubuntu) once to create your Linux user.

**Verification checkpoint: WSL2** — on the Windows host, in PowerShell:

```powershell
wsl --status
wsl --list --verbose
```

Confirm `wsl --status` reports the default version as **2**, and `wsl --list --verbose` shows your distro with `VERSION` = `2`. If the distro shows `VERSION 1`, convert it: `wsl --set-version <DistroName> 2`.

You will also want Python 3.11+ available inside WSL2 and the Kajiba repo cloned in the **WSL2 native filesystem** (for example `~/Kajiba`, NOT under `/mnt/c/...`), with `pip install -e .` active inside WSL2.

### A.2 NVIDIA GPU passthrough

WSL2 GPU support works by passing the **Windows** NVIDIA driver through to the Linux guest. You do **not** install a Linux GPU driver inside WSL2.

1. On the **Windows host**, install the latest NVIDIA Windows driver for the RTX 4070 from NVIDIA's official driver download page. This driver includes WSL2 CUDA support.
2. Do **not** install any `nvidia-driver-*` package inside WSL2.

**Verification checkpoint: GPU** — inside the WSL2 distro shell:

```bash
nvidia-smi
```

Confirm the output shows the **RTX 4070** and its **VRAM** (about 8192 MiB). If `nvidia-smi` is not found or shows no device, the Windows driver is missing or out of date — reinstall it and restart WSL2 (`wsl --shutdown` from PowerShell, then reopen the distro).

#### Troubleshooting: CUDA driver stub overwrite (MP-8)

This is the single most damaging GPU pitfall. If you later install the CUDA toolkit and pull in the wrong meta-package, you can **overwrite the WSL2 `libcuda.so` driver stub**. Ollama then silently falls back to CPU inference (roughly 60x slower) with no error — it just runs slowly and `nvidia-smi` shows no VRAM in use.

To avoid this:

- Install **only** the toolkit package, never the driver meta-packages:

```bash
# CORRECT -- toolkit only
sudo apt-get install -y cuda-toolkit-12-4
```

```bash
# WRONG -- these overwrite the WSL2 driver stub, breaking GPU passthrough:
#   sudo apt-get install cuda
#   sudo apt-get install cuda-drivers
```

- After any CUDA install, verify the WSL2 driver stub is still a symlink (and was not replaced by a real file):

```bash
ls -l /usr/lib/wsl/lib/libcuda.so*
```

The `libcuda.so` / `libcuda.so.1` entries should remain symlinks into the WSL2 lib directory. If they were replaced, reinstall the Windows driver and restart WSL2.

- **Keep models and working files in the WSL2 native filesystem** (for example `~/...`), not under `/mnt/c/...`. Cross-filesystem access through `/mnt/c/` is slow and can interact badly with GPU memory-mapped model loads.

(MP-8 -- WSL2 CUDA stub overwrite. This is an env-integrity issue, not a Kajiba code issue.)

### A.3 Ollama install + config

Ollama provides local LLM inference inside WSL2. Hermes Agent talks to Ollama over its HTTP endpoint.

Inside the WSL2 distro shell:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Pull the model used for data collection (Hermes 3 8B):

```bash
ollama pull hermes3:8b
```

#### Ollama configuration: num_ctx override (MP-5)

Ollama defaults the **effective** context window to **2048 tokens** regardless of the context length the model reports. For real sessions this silently truncates long prompts. Set `num_ctx` explicitly.

Per request through the API:

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

Then point Hermes at `hermes3-8b-ctx`. (MP-5 -- Ollama `num_ctx` default truncation.)

#### Ollama configuration: custom endpoint

Hermes connects to Ollama at its HTTP endpoint, by default `http://localhost:11434`. Configure Hermes to use this endpoint (and the `hermes3:8b` / `hermes3-8b-ctx` model). When Hermes and Ollama both run inside WSL2, `localhost` is the correct host.

#### Troubleshooting: Ollama WSL2 network binding (MP-9)

Ollama binds to `127.0.0.1` by default. That is fine when **Hermes and Ollama both run inside WSL2** (the recommended topology). It becomes a problem only if you try to reach Ollama from the Windows host or another network namespace — cross-namespace connections to `127.0.0.1:11434` are refused.

- **Recommended topology:** run Hermes Agent and Ollama **both inside the same WSL2 distro**. No binding changes needed; use `http://localhost:11434`.
- **If you must reach Ollama from the Windows host**, bind Ollama to all interfaces by setting `OLLAMA_HOST` before starting it:

```bash
export OLLAMA_HOST=0.0.0.0:11434
ollama serve
```

Then connect from the Windows host using the WSL2 instance IP (`wsl hostname -I`) on port 11434. Prefer the all-in-WSL2 topology unless you have a specific reason to split them. (MP-9 -- Ollama WSL2 network binding.)

**Verification checkpoint: Ollama** — run a quick inference and confirm it uses the GPU:

```bash
ollama run hermes3:8b "Say hello in one short sentence."
```

In a second WSL2 shell, while that inference is running:

```bash
nvidia-smi
```

Confirm `ollama run` produces text output AND `nvidia-smi` shows **VRAM in use** during inference. If no VRAM is in use, Ollama is on the CPU fallback path — revisit the CUDA stub overwrite troubleshooting (MP-8).

### A.4 Hermes + Kajiba plugin under WSL2

Under WSL2 the Hermes install, editable Kajiba install, plugin symlink, enable, and load steps mirror the primary path above, but run inside the WSL2 distro with Linux paths. The plugin symlink uses `ln -s`:

```bash
cd ~/Kajiba
mkdir -p ~/.hermes/plugins
ln -s "$(pwd)/src/kajiba/plugin" ~/.hermes/plugins/kajiba
hermes plugins enable kajiba
```

Then verify exactly as in the primary path (`hermes --version` reports v0.15.x; `KAJIBA_DEBUG=1 hermes` shows the `Kajiba registered hooks: ...` line). If you run Hermes under a non-default `HERMES_HOME`, create the symlink under that profile's `plugins/` directory instead — a different profile is a separate data namespace (its own staging / outbox).

### A.5 DGX Spark / native aarch64 Linux (no WSL2)

This path was validated end-to-end during the Phase 7 live-capture proof on an **NVIDIA DGX
Spark** (GB10 Grace Blackwell, 128GB unified memory, aarch64, DGX OS). See
`.planning/phases/07-turn-capture-semantic-pii-scrubbing/07-LIVE-CAPTURE.md` for the captured
evidence. On native Linux there is **no WSL2 layer** — `~/.hermes/kajiba/` paths are literal,
plugin discovery uses a normal symlink, and none of the MP-8/MP-9 WSL2 pitfalls apply. The
128GB unified memory means GLiNER (`nvidia/gliner-PII`) and Hermes 3 coexist with no OOM.

**Ollama — user-local install (no sudo):**

```bash
# arm64 tarball extracted to a user dir; no root needed
mkdir -p ~/.local/ollama && cd ~/.local/ollama
# download + extract the official ollama-linux-arm64 tarball here, then:
ln -sfn ~/.local/ollama/bin/ollama ~/bin/ollama        # ensure ~/bin is on PATH
nohup ollama serve >~/ollama.log 2>&1 &
ollama pull hermes3:8b                                   # Q4_0, 8B, 131072 ctx
ollama show hermes3:8b                                   # confirms parameter_size / quantization / family
```

**GB10 GPU offload (Blackwell, compute capability 12.1 / sm_121):** the stock arm64 tarball ships
both `cuda_v12` and `cuda_v13` libraries. The GB10 needs the **`cuda_v13`** path — the DGX OS ships
CUDA 13. Start the server with debug logging to confirm full offload (no source build required):

```bash
OLLAMA_DEBUG=1 ollama serve     # then run one generation and inspect ~/ollama.log
```

Confirm in the log (all three): `verifying if device is supported ... NVIDIA GB10 compute=12.1`,
`load_tensors: offloaded 33/33 layers to GPU`, and runner `library=CUDA` `vram=21.0 GiB` — **not**
"skipping CUDA device" / CPU. `nvidia-smi` should show the `llama-server` child process holding
VRAM during inference; tokens/sec jumps materially (≈51 t/s observed on GB10 vs the CPU fallback).
If a future Ollama build lacks sm_121 kernels, build from source with
`CMAKE_CUDA_ARCHITECTURES=121`, or use an NVIDIA NIM/NGC container that exposes the Ollama API on
`:11434`. **Keep Ollama as the serving backend** — Kajiba's model-metadata capture (CAPT-04)
depends on `ollama.show()`; switching to vLLM/TGI loses that enrichment.

**Point Hermes at local Ollama (the config that actually works on Linux):** use the **OpenAI-compat
`/v1` endpoint with `provider: custom`**, not a plain `provider: ollama`:

```yaml
provider: custom
base_url: http://localhost:11434/v1     # the /v1 suffix is required
default: hermes3:8b
api_key: ""                              # empty; Ollama ignores it
```

On the validated build, `provider: ollama` (or a `base_url` without `/v1`) returned 404 / fell
back to a custom-provider error. Even with `provider: custom`, the captured record's
`model.provider` still comes out as `ollama` — the collector's `_enrich_from_ollama` recognizes the
local backend and calls `ollama.show()` regardless of the Hermes-side label.

**Plugin (Linux native symlink + editable install in the Hermes venv):**

```bash
cd ~/Kajiba
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[llm-scrub]"                              # dev venv: GLiNER LANE-B + capture
ln -sfn "$(pwd)/src/kajiba/plugin" ~/.hermes/plugins/kajiba
hermes plugins enable kajiba                                # REQUIRED — discovered != enabled
# Hermes runs in its own venv; install Kajiba there too (it may have no pip binary — use uv):
uv pip install --python ~/.hermes/hermes-agent/venv/bin/python -e "$(pwd)[llm-scrub]"
```

**Verification checkpoint: DGX live capture** — run one short throwaway session with a tool call,
then:

```bash
ls ~/.hermes/kajiba/staging/        # exactly ONE session_<id>.json (finalize-once)
kajiba preview                       # GLiNER Layer C active; real model metadata in the record
```

Confirm exactly one staging file, a `model` block with non-null `parameter_count` / `quantization`
/ `model_family` / `context_window`, and that `kajiba preview` runs the GLiNER path (not degraded).

**Permissions / autonomy (isolated dev box only):** for hands-off agent runs the DGX setup used
`hermes config set approvals.mode off` and `export HERMES_YOLO_MODE=1` (persisted in `~/.bashrc`).
This is appropriate **only** for an isolated throwaway playground. **Security caveat:** this box
captures sessions for a privacy-first dataset — re-enable `hermes config set security.redact_secrets
true` before any **real** (non-throwaway) capture, and never replicate passwordless-root / yolo /
`curl | sh` autonomy to a machine that handles real user data. Kajiba's CLI scrubbing is the real
safety net; this is defense-in-depth.

### Appendix summary checklist (WSL2 / GPU / Ollama — optional)

| Step | Verification checkpoint | Pass condition |
|------|-------------------------|----------------|
| A.1 WSL2 | `wsl --status` | Default version 2; distro runs |
| A.2 GPU | `nvidia-smi` (in WSL2) | RTX 4070 + VRAM shown |
| A.3 Ollama | `ollama run` + `nvidia-smi` | Output produced AND VRAM in use during inference |
| A.4 Hermes + plugin | `hermes --version` + `KAJIBA_DEBUG=1 hermes` | Reports v0.15.x; `Kajiba registered hooks: ...` in log |
| A.5 DGX / aarch64 | `OLLAMA_DEBUG=1 ollama serve` + `kajiba preview` | `offloaded 33/33 layers to GPU` (cuda_v13); one staging file with live `ollama.show()` metadata; GLiNER Layer C active |
