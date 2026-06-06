---
title: Phase 7 Live-Capture Proof (07-06 / D-02 Hard Gate)
phase: 07-turn-capture-semantic-pii-scrubbing
plan: 06
status: complete
requirements_proven: [CAPT-04, PRIV-01, PRIV-03]
machine: DGX Spark (NVIDIA GB10 Grace Blackwell, 128GB unified memory, aarch64, DGX OS)
hermes_version: v0.15.1
captured_sessions:
  - 20260605_184953_e52b56  # original CPU-backed proof
  - 20260605_192518_ea3f16  # GPU-backed proof (full GB10 offload)
synthesized_from:
  - 07-DGX-LIVE-CAPTURE.md
  - 07-DGX-EVIDENCE.md
date: 2026-06-05
---

# Phase 7 — Live-Capture Proof (D-02 Hard Gate)

This is the canonical D-02 artifact for plan 07-06: proof on **real hardware and real
data** that the Phase 7 capture + semantic-scrubbing pipeline works end to end. It
synthesizes the on-machine execution recorded in `07-DGX-EVIDENCE.md` and the agent
handoff in `07-DGX-LIVE-CAPTURE.md`. All content here is **PII-safe** — shapes, counts,
IDs, rates, and metadata only; no real prompt/response/file content.

The live runs happened on the **DGX Spark** (not the Windows RTX 4070 dev box) — see
`07-DGX-HANDOFF.md` for why the proof was relocated there (128GB unified memory removes
the GLiNER OOM hedges, Linux `~/.hermes/kajiba/` matches the project's path conventions,
and it is the machine that hosts the Loop-B vision).

## What was proven

| Success criterion | Result |
|-------------------|--------|
| SC#3 / CAPT-04 — real `ollama.show()` model metadata captured on a live local-Ollama Hermes 3 8B Q4 session | ✅ Proven (both sessions) |
| PRIV-01 — `nvidia/gliner-PII` loads end-to-end and Layer C runs on real captured prose | ✅ Proven |
| PRIV-03 — D-06 calibration hard gate (zero auto-redacts on known-safe code) | ✅ `CALIBRATION_FP_RATE=0.0000` on the real model |
| Finalize-once — exactly one staging file per session | ✅ Confirmed live (closes Assumption A3) |
| No schema change | ✅ `git diff --quiet src/kajiba/schema.py` |

## Environment

- **Machine:** DGX Spark — NVIDIA GB10 Grace Blackwell, 128GB unified memory, aarch64, DGX OS.
- **Hermes:** v0.15.1, Kajiba plugin installed editable in the Hermes venv and symlinked into
  `~/.hermes/plugins/kajiba` (Linux native symlink — the Windows COPY workaround from
  06-HOOK-KWARGS finding 7 does **not** apply on Linux).
- **Inference backend:** local **Ollama** 0.30.6 (`hermes3:8b`, Q4_0). Hermes pointed at it via
  `provider: custom` + `base_url: http://localhost:11434/v1` (the OpenAI-compat endpoint; a plain
  `provider: ollama` config 404'd on this build — see docs/hermes-setup.md A.5).
- **Semantic layer:** `[llm-scrub]` extra installed (torch 2.12.0+cu130 aarch64, gliner,
  transformers, ollama); `nvidia/gliner-PII` weights cached; loaded on CUDA, no OOM.

## The live capture (GPU-backed session 20260605_192518_ea3f16)

A short throwaway Hermes 3 8B session (non-sensitive 2D-cyberpunk game-dev prototype theme,
with an explicit `terminal` tool invocation) was captured through the promoted Kajiba plugin
hooks. The staging directory was cleaned immediately before the run so the finalize-once count
could be verified unambiguously.

- **Session ID:** `20260605_192518_ea3f16`
- **Staging file:** exactly **one** — `~/.hermes/kajiba/staging/session_20260605_192518_ea3f16.json` (2355 bytes)
- **Trajectory shape:** 2 turns (paired human+gpt), 1 tool call (1 success, 0 failed)

### D-02 core proof — real model metadata (from `ollama.show()` via the collector)

```json
"model": {
  "model_name": "hermes3:8b",
  "provider": "ollama",
  "parameter_count": "8.0B",
  "quantization": "Q4_0",
  "model_family": "llama",
  "context_window": 131072
}
```

All four target fields — `parameter_count`, `quantization`, `model_family`, `context_window` —
are **non-null and sourced live** from `ollama.show()`, matching `ollama show hermes3:8b`. This is
the mocked path from 07-03 now proven against a real local model.

**Notable robustness finding:** Hermes was configured as `provider: custom` (OpenAI-compat
endpoint), yet the captured record's `provider` is `ollama`. The collector's `_enrich_from_ollama`
correctly **recognized the local Ollama backend and called `ollama.show()`** regardless of the
label Hermes reported — exactly the CAPT-04 behavior intended, and proven resilient to the
custom-provider config.

### `kajiba preview` on the live record — GLiNER Layer C active

- Quality tier **silver**, composite score **0.755**
- 2 turns, 1 tool call (1 success), model `hermes3:8b` (Q4_0)
- **GLiNER Layer C ran live** on the captured prose (13 model files fetched; onnxruntime DRM
  warning non-blocking).
- Scrubbing surfaced **1 low-confidence flag for review** (not auto-redacted):
  `cyberpunk GPU prototype — GLiNER project (confidence 0.52)` — triggered by throwaway prompt
  wording ("GPU prototype"), **not** real PII. The `0.4–0.7` flag band is the expected behavior
  here; nothing crossed the `≥0.7` auto-redact threshold, and no real names/secrets were present.

This satisfies the must-have "kajiba preview on the live record shows GLiNER redactions/flags
(Layer C runs on real data)": Layer C executed on the real record and a flag surfaced in the
flagged-for-review panel.

## D-06 calibration hard gate (PRIV-03) — confirmed on the real model

LANE-B was never executed on the Windows dev box (the `[llm-scrub]` extra is uninstalled there,
so it always skipped). The DGX is the first machine to run it against a real GLiNER model, which
surfaced a latent assertion bug in the test (it asserted `auto_redact == []`, wrongly forbidding
redaction of the fixture's seeded true-positive names). The fix (commit `ef64e88`) retargets the
assertion at `false_positives` — the actual D-06 intent. Re-run after pulling the fix:

```
python -m pytest tests/test_scrubber_semantic.py -k "detect or calibration" -x -s
→ TestDetect PASSED, TestCalibration PASSED
→ CALIBRATION_FP_RATE=0.0000 flag_band=0
```

**Zero of the 16 known-safe code identifiers were auto-redacted** at score ≥0.7 on the real model.
The two `≥0.7` detections in the fixture were the seeded genuine names (`Margaret Chen` /
`Aldebaran Robotics`), which GLiNER is *supposed* to catch. The privacy guarantee holds on real
hardware.

## Bonus — GB10 GPU offload (not required by 07-06)

Beyond the plan, Ollama was brought onto the GB10 GPU. The stock arm64 tarball (v0.30.6) ships
both `cuda_v12` and `cuda_v13` libraries; with `OLLAMA_DEBUG=1` it verified the GB10
(compute capability 12.1) and selected the **`cuda_v13`** path — no source build needed.

- `load_tensors: offloaded 33/33 layers to GPU`
- `CUDA0 model buffer size = 4155.99 MiB`; `KV buffer size = 16384.00 MiB`
- runner `library=CUDA`, `vram=21.0 GiB`
- ~**51.1 tokens/sec** (30 tokens / 0.59s) on the GPU path

The capture pipeline is identical whether Ollama runs on CPU or GPU (metadata is the same); the
GPU offload simply makes the Loop-B / real-usage path performant on the DGX. The recipe is
recorded in `docs/hermes-setup.md` A.5. A Docker `--gpus all` path was blocked by docker-socket
permissions and abandoned (the host binary path already worked).

## Must-haves verification (against 07-06-PLAN.md)

| Must-have (truth) | Status | Evidence |
|-------------------|--------|----------|
| Real local-Ollama Hermes session captured into exactly one staging record | ✅ | `session_20260605_192518_ea3f16.json`, single file after a cleaned staging dir |
| Record carries non-null `parameter_count`/`quantization`/`model_family`/`context_window` from `ollama.show()` | ✅ | Model block above (8.0B / Q4_0 / llama / 131072) |
| `kajiba preview` on the live record shows GLiNER Layer C running on real data | ✅ | silver 0.755, Layer C active, 1 flag@0.52 surfaced |
| Staging JSON archived as the phase artifact (PII-safe) | ✅ | This document + `07-DGX-EVIDENCE.md` |
| `key_links`: live session → `session_<id>.json` | ✅ | matches `session_.*\.json` |
| `key_links`: `ollama.show()` → `ModelMetadata.parameter_count`/`quantization` | ✅ | `parameter_count` present and non-null |

## Provenance (commits on master)

- `3796e99` — initial CPU-backed live capture (session `20260605_184953_e52b56`) + permissions notes
- `ef64e88` — D-06 calibration test assertion fix (Windows orchestrator)
- `c29f8e9` — GPU-usage run + calibration re-confirmation (session `20260605_192518_ea3f16`)
- `ef1249c` — DGX → Windows execution handoff (`07-DGX-LIVE-CAPTURE.md`)

## Follow-ups (not blocking Phase 7)

- **GB10 Ollama performance** is now solved via the prebuilt `cuda_v13` path; if a future Ollama
  release regresses arm64 Blackwell support, the source-build (`CMAKE_CUDA_ARCHITECTURES=121`) or
  NVIDIA NIM container paths are the fallbacks. Relevant to Loop-B / Phase 14 real-usage capture.
- **Security on the DGX:** `security.redact_secrets` was set `false` and YOLO/approvals loosened
  for the throwaway playground. Re-enable `security.redact_secrets true` before any **real**
  (non-throwaway) capture for the dataset — Kajiba's CLI scrubbing is the safety net, but
  defense-in-depth matters on the capture machine.

## PII discipline

This artifact and its sources record only shapes, counts, IDs, rates, log excerpts, and preview
summaries. No real prompts, responses, tool content, or secrets were transcribed (per T-06-11 /
T-07-15). The single GLiNER flag was on throwaway test wording and was left for review, not
auto-redacted.
