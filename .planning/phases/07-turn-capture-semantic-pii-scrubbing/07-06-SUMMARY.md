---
phase: 07-turn-capture-semantic-pii-scrubbing
plan: 06
subsystem: validation
tags: [live-capture, d-02, ollama, gliner, calibration, dgx-spark, gb10, checkpoint]

requires:
  - phase: 07-03
    provides: "Real turn/tool capture + _enrich_from_ollama + finalize-once on_session_end"
  - phase: 07-04
    provides: "GLiNER Layer C (nvidia/gliner-PII) semantic scrubber + LANE-B calibration test"
  - phase: 07-05
    provides: "kajiba preview wired to run Layer C on the captured record"
provides:
  - "D-02 live-capture proof on real hardware: 07-LIVE-CAPTURE.md (canonical artifact)"
  - "Real ollama.show() metadata captured into a live staging record (CAPT-04 proven)"
  - "GLiNER LANE-B calibration hard gate green on the real model (CALIBRATION_FP_RATE=0.0000)"
  - "docs/hermes-setup.md A.5 — aarch64/DGX Linux local-Ollama + GB10 GPU offload + provider:custom recipe"
affects: [phase-14-live-capture, privacy-pipeline, hermes-setup-docs]

tech-stack:
  added: []
  patterns:
    - "Cross-machine checkpoint execution: Windows orchestrator + DGX Spark Hermes agent over git (origin/master) as the message bus"
    - "Live-data hard gate: a LANE-B model-dependent test that only runs where [llm-scrub] is installed (the DGX), surfacing bugs invisible to the skip-on-Windows suite"

key-files:
  created:
    - .planning/phases/07-turn-capture-semantic-pii-scrubbing/07-LIVE-CAPTURE.md
    - .planning/phases/07-turn-capture-semantic-pii-scrubbing/07-DGX-HANDOFF.md
    - .planning/phases/07-turn-capture-semantic-pii-scrubbing/07-DGX-EVIDENCE.md
    - .planning/phases/07-turn-capture-semantic-pii-scrubbing/07-DGX-LIVE-CAPTURE.md
  modified:
    - tests/test_scrubber_semantic.py
    - docs/hermes-setup.md

key-decisions:
  - "Relocated the D-02 live proof from the Windows RTX 4070 (8GB) to the DGX Spark (GB10, 128GB unified, aarch64) — removes the GLiNER OOM/CPU-fallback hedges and matches the project's ~/.hermes/kajiba/ Unix paths"
  - "Fixed the D-06 calibration assertion (auto_redact == [] -> false_positives == []); the DGX was the first machine to ever run LANE-B against a real model, exposing a latent test bug that the skip-on-Windows suite hid"
  - "Kept Ollama as the serving backend on the DGX (not vLLM/TGI) so _enrich_from_ollama / ollama.show() metadata capture keeps working"

patterns-established:
  - "git-as-message-bus handoff: orchestrator writes a HANDOFF.md + agent prompt, the remote agent appends an EVIDENCE.md and pushes, orchestrator synthesizes the canonical artifact — keeps both contexts lean and PII-safe"
  - "PII-safe live evidence: capture shapes/counts/IDs/rates/log-excerpts/preview summaries only, never real prompt/response content (T-06-11 / T-07-15)"

requirements-completed: [CAPT-04, PRIV-01, PRIV-03]

duration: cross-machine (checkpoint plan; multi-session)
completed: 2026-06-05
---

# Phase 07 Plan 06: Live-Capture Proof (D-02 Hard Gate) Summary

**The Phase 7 capture + semantic-scrubbing pipeline is proven on real hardware and real data: a live local-Ollama Hermes 3 8B Q4 session was captured into exactly one staging record with non-null `ollama.show()` metadata, GLiNER Layer C ran live in `kajiba preview`, and the D-06 calibration hard gate is green (FP rate 0.0000) on the real `nvidia/gliner-PII` model — with bonus full GB10 GPU offload.**

This was the phase's only `autonomous: false` plan (a human-action checkpoint), executed **cross-machine**: the Windows orchestrator (Claude Code) handled planning/synthesis/closeout, and a Hermes agent on the **DGX Spark** performed the install, calibration, and live capture that Claude cannot do via CLI/API. `origin/master` was the message bus.

## What was delivered

- **Task 1 (auto, on DGX):** `[llm-scrub]` installed in both the dev venv and the Hermes venv (torch 2.12.0+cu130 aarch64, gliner, transformers, ollama); `nvidia/gliner-PII` loaded on CUDA (no OOM on 128GB unified). LANE-B `detect` PASSED; LANE-B `calibration` confirmed **`CALIBRATION_FP_RATE=0.0000`** after the assertion fix (below).
- **Task 2 (human-action checkpoint, on DGX):** Ollama 0.30.6 installed user-local (no sudo), `hermes3:8b` pulled (Q4_0, 131072 ctx), Hermes v0.15.1 pointed at local Ollama via `provider: custom` + `http://localhost:11434/v1`, plugin symlinked + enabled. One short throwaway tool-using session captured: **session `20260605_192518_ea3f16`**, exactly one staging file, real metadata, GLiNER Layer C active in preview. A GPU-backed re-run achieved **33/33-layer GB10 offload** via the prebuilt `cuda_v13` path (~21 GiB VRAM, ~51 t/s).
- **Task 3 (auto, on Windows):** wrote the canonical **`07-LIVE-CAPTURE.md`** D-02 artifact and added **`docs/hermes-setup.md` A.5** (aarch64/DGX Linux + GB10 GPU offload + the working `provider: custom` recipe + permissions/security guidance).

## Live capture — the D-02 proof

Captured `model` block (live from `ollama.show()` via the collector), session `20260605_192518_ea3f16`:

```json
"model": { "model_name": "hermes3:8b", "provider": "ollama", "parameter_count": "8.0B",
           "quantization": "Q4_0", "model_family": "llama", "context_window": 131072 }
```

All four target fields non-null and live. `kajiba preview`: silver tier (0.755), 2 turns, 1 tool call, GLiNER Layer C ran and surfaced one `0.52` flag on throwaway wording (no real PII). Exactly one staging file (finalize-once verified live → closes Assumption A3). A robustness win: the record's `provider` is `ollama` even though Hermes was configured `provider: custom` — `_enrich_from_ollama` recognized the local backend on its own.

## Task Commits

1. **D-06 calibration assertion fix** — `ef64e88` (fix)
2. **DGX initial live capture + permissions evidence** — `3796e99` (test, DGX)
3. **DGX GPU-usage run + calibration re-confirmation** — `c29f8e9` (test, DGX)
4. **DGX → Windows execution handoff** — `ef1249c` (docs, DGX)
5. **Closeout: 07-LIVE-CAPTURE.md + docs/hermes-setup.md A.5 + this summary** — (this commit)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] D-06 calibration test asserted the wrong set (`auto_redact == []`)**

- **Found during:** Task 1 on the DGX — the first-ever real-model execution of the LANE-B `calibration` test (the `[llm-scrub]` extra is uninstalled on Windows, so this assert had **never run**; the suite reported "green" because the test always skipped).
- **Issue:** the test concatenated every turn value — including the fixture's seeded true-positive names (`Margaret Chen` / `Aldebaran Robotics`) — and asserted `auto_redact == []`. That wrongly forbids GLiNER from redacting *anything* ≥0.7, including the genuine PII it is supposed to catch. The measured false-positive rate on the 16 known-safe code identifiers was already `0.0000`.
- **Fix:** retargeted the assertion at `false_positives` (auto-redacts whose text is in `KNOWN_SAFE_TOKENS`) — the actual D-06 intent — with a comment explaining why true positives must not trip the gate. Pure test-correctness change; **no production code touched**.
- **Verification:** re-run on the DGX → `TestDetect` + `TestCalibration` PASS, `CALIBRATION_FP_RATE=0.0000`.
- **Commit:** `ef64e88`

## Known Stubs

None. `scrubber_llm.py` was already retired in 07-04. The semantic + capture paths are fully wired and now proven on live data.

## Threat Surface

- **T-07-15 (info disclosure on live capture):** mitigated — throwaway non-sensitive prompts; all recorded evidence is shapes/metadata only (T-06-11); staging stayed local under `HERMES_HOME`.
- **T-07-16 (model supply chain):** `nvidia/gliner-PII` (capital-PII id) + `hermes3:8b` pulled from official sources.
- **Noted for the operator (not a Phase 7 defect):** the DGX run set `security.redact_secrets false` + YOLO/approvals off for the isolated playground. `07-LIVE-CAPTURE.md` and `docs/hermes-setup.md` A.5 both flag: re-enable secret redaction before any real (non-throwaway) capture.

## Verification

- LANE-B on real model (DGX): `pytest -k "detect or calibration"` → 2 passed, `CALIBRATION_FP_RATE=0.0000`.
- Windows suite unaffected: `tests/test_scrubber_semantic.py` collects; LANE-A 8 pass, LANE-B 2 skip (gliner absent).
- `git diff --quiet src/kajiba/schema.py` — schema untouched.
- Live record: one `session_20260605_192518_ea3f16.json`, non-null `parameter_count`/`quantization`/`model_family`/`context_window`, GLiNER Layer C active in `kajiba preview`.

## Success Criteria

- **SC#3 / CAPT-04:** real `ollama.show()` model metadata captured into `ModelMetadata` via a live Hermes 3 8B Q4 session (D-02). ✓
- **PRIV-01:** `nvidia/gliner-PII` loads end-to-end and Layer C runs on real captured prose. ✓
- **PRIV-03:** D-06 calibration hard gate green on the real model (FP 0.0000). ✓
- D-02 phase-gate artifact archived; finalize-once proven live; no schema change. ✓

## Self-Check: PASSED

- `07-06-SUMMARY.md` — FOUND
- `07-LIVE-CAPTURE.md` — FOUND
- `docs/hermes-setup.md` A.5 — FOUND
- `tests/test_scrubber_semantic.py` calibration fix — FOUND (commit `ef64e88`)
