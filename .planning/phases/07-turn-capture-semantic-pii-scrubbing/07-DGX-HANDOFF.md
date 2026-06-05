---
title: Phase 7 — 07-06 Live-Capture Handoff (DGX Spark)
phase: 07-turn-capture-semantic-pii-scrubbing
plan: 06
status: handoff
machine: DGX Spark (GB10 Grace Blackwell, 128GB unified, Ubuntu/DGX OS, aarch64)
created: 2026-06-05
author: Claude Code (orchestrator, Windows dev box)
consumes: 07-06-PLAN.md, 07-RESEARCH.md, 07-VALIDATION.md, 06-HOOK-KWARGS.md, docs/hermes-setup.md
produces: 07-LIVE-CAPTURE.md (written by Claude Code from the evidence you report back)
---

# Phase 7 / Plan 07-06 — Live-Capture Proof on the DGX Spark

## Why this document exists

Phase 7 ("turn capture + semantic PII scrubbing") is **code-complete and green**: Waves 1–3
delivered real turn/tool capture (07-03), the GLiNER Layer-C semantic scrubber (07-04), and the
CLI wiring (07-05). The full unit suite is **430 passed / 16 skipped** on the Windows dev box.

Plan 07-06 is the only thing left: **prove Success Criterion #3 on REAL data** (the D-02 hard
gate). That means running one real local-Ollama Hermes session through the Kajiba plugin and
confirming the captured record carries genuine model metadata from `ollama.show()` and that
GLiNER runs on the real captured prose. **Claude cannot do this** — it needs a human on a machine
with Ollama + a live Hermes session.

We relocated this proof from the Windows RTX 4070 (8GB) to the **DGX Spark** on purpose: 128GB
unified memory removes every OOM hedge in the plan, the model metadata is richer, and the DGX's
Linux `~/.hermes/kajiba/` paths match the project's assumptions exactly.

## What's already true (do NOT redo)

- All Phase 7 source code is on `master` and pushed to `origin` (`CuervoDoesIt/Kajiba`).
- `[llm-scrub]` extra is **declared** in `pyproject.toml` (gliner / torch / transformers / ollama)
  but **not installed** anywhere yet — that's Task 1 below.
- `src/kajiba/scrubber_semantic.py` exists and soft-imports GLiNER; the module imports cleanly
  WITHOUT the extra and degrades via `SemanticScrubUnavailable`.
- The collector finalizes **exactly one** staging file per session (finalize-once, 07-03).
- The CLI (`kajiba preview`) runs Layer C when available and degrades gracefully when not.

## Environment notes (DGX / Linux / aarch64 — differs from the Windows plan text)

- **Plugin discovery is simpler on Linux.** The native-Windows COPY workflow (06-HOOK-KWARGS
  finding 7) does NOT apply. Use a normal editable install / Hermes plugin enable.
- **The hook-kwargs contract is platform-independent.** 06-HOOK-KWARGS.md describes Hermes's
  event payload shapes — those hold on Linux too. Trust that doc for kwarg names.
- **aarch64 packages:** DGX OS ships CUDA-for-ARM. PyTorch has aarch64+CUDA wheels; gliner rides
  on transformers; Ollama has first-class ARM64 Linux builds. No OOM math to worry about (128GB).
- **HERMES_HOME:** on Linux this is `~/.hermes`; staging lands in `~/.hermes/kajiba/staging/`.

---

## Task 1 (automatable) — install the extra + prove the GLiNER calibration gate

Goal: install `[llm-scrub]` into BOTH the Hermes venv (where the Kajiba plugin lives) and a dev
venv, then prove the **D-06 calibration hard gate** on the real `nvidia/gliner-PII` model.

1. Clone + dev venv (in the blank `Kajiba` folder you opened):
   ```bash
   git clone https://github.com/CuervoDoesIt/Kajiba.git .
   python3.11 -m venv .venv && source .venv/bin/activate
   pip install -e ".[llm-scrub]"
   ```
2. Smoke test (must print a torch version and `True`/`False` for CUDA without error):
   ```bash
   python -c "import gliner, torch, transformers, ollama; print('extra ok', torch.__version__, torch.cuda.is_available())"
   ```
3. Load the model ONCE (capital-PII repo id — **`nvidia/gliner-PII`**, Correction 1; a lowercase
   typo resolves to a different/squatted repo). This triggers a one-time ~1.5–2.4GB HF download:
   ```bash
   python -c "from gliner import GLiNER; GLiNER.from_pretrained('nvidia/gliner-PII'); print('model ok')"
   ```
4. Run the LANE-B tests — the **D-06 hard gate** (zero auto-redacts ≥0.7 on the code fixture):
   ```bash
   python -m pytest tests/test_scrubber_semantic.py -k "detect or calibration" -x
   ```
   These must PASS now that gliner is installed. Record the observed false-positive rate.
5. Also install `[llm-scrub]` into the **Hermes venv** (where the Kajiba plugin is installed
   editable) so the live session and `kajiba preview` can use Layer C.

**Acceptance:** smoke test exits 0; `nvidia/gliner-PII` loads (no 404); LANE-B detect+calibration
PASS on the real model. Do NOT swap the model — PRIV-01 names the NVIDIA model; a swap needs
explicit user approval.

---

## Task 2 (human-action, blocking) — the live local-Ollama Hermes capture

This is the actual D-02 proof. Use **throwaway, non-sensitive** prompts (the in-progress 2D
cyberpunk game-dev project is a fine subject as long as no real secrets/PII appear).

1. Install Ollama and confirm: `ollama --version`.
2. Pull the model: `ollama pull` the **Hermes 3 8B Q4** tag; confirm with `ollama list`.
3. Confirm metadata is available: `ollama show <model>` returns `parameter_size`,
   `quantization_level`, `family`, and a digest.
4. Point Hermes v0.15.1 at the local Ollama backend (see `docs/hermes-setup.md` Ollama appendix);
   ensure the Kajiba plugin is enabled (`hermes plugins enable kajiba`).
5. Run ONE short session — a few turns, **at least one tool call**.
6. After the session, verify in `~/.hermes/kajiba/staging/`:
   - **EXACTLY ONE** `session_<id>.json` exists (finalize-once, Correction 3).
   - Its `model` block has non-null `parameter_count`, `quantization`, `model_family`,
     `context_window` (sourced from `ollama.show()`).
7. Run `kajiba preview` on that record; confirm Layer C runs (GLiNER redactions and/or a flagged
   panel appear — the GLiNER path is active, not degraded).

---

## Task 3 (Claude writes this) — the resume signal

When Task 2 is done, **report back to Claude Code** with:

1. The `model` block excerpt from the staging JSON showing real `parameter_count` / `quantization`
   / `model_family` / `context_window`.
2. A one-line note on the `kajiba preview` GLiNER result (e.g. "3 names redacted, 1 flagged" or
   "no PII found, GLiNER path active").
3. Confirmation that **exactly one** staging file was produced.
4. The LANE-B calibration FP rate from Task 1.
5. Anything that deviated from the mocked path (e.g. `ollama.show()` return shape differing from
   the plan's Assumption A1) — note it; it may route to a small gap-closure fix.

**PII discipline (T-06-11 / T-07-15):** report record *shapes and metadata*, NOT real prompt or
response content. Synthesize/placeholder any example text. Staging stays local-only.

Claude will then write `07-LIVE-CAPTURE.md` (the D-02 phase-gate artifact), touch up the
`docs/hermes-setup.md` Ollama appendix if needed, mark 07-06 complete, and run phase verification.

---

## Quick reference — acceptance for the whole plan

- [ ] `[llm-scrub]` installed in Hermes venv + dev venv; `nvidia/gliner-PII` loads
- [ ] LANE-B detect + calibration PASS on real model (D-06 gate green; FP rate recorded)
- [ ] Exactly one `session_<id>.json` from a real local-Ollama Hermes 3 8B Q4 session
- [ ] That record's `model` block has real `parameter_count` / `quantization` / `model_family` / `context_window`
- [ ] `kajiba preview` shows Layer C running on the live record
- [ ] Evidence reported back to Claude Code (shapes/metadata only — no real content)

Requirements proven by this plan: **CAPT-04, PRIV-01, PRIV-03** (the LANE-B-gated calibration).
