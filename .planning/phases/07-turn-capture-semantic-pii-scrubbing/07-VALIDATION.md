---
phase: 7
slug: turn-capture-semantic-pii-scrubbing
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-05
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `07-RESEARCH.md` § Validation Architecture. Task IDs are assigned
> by gsd-planner; this draft maps by requirement until plans exist.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=7.0 + pytest-cov |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `testpaths=["tests"]`, `addopts="-v"`) |
| **Quick run command** | `python -m pytest tests/test_scrubber_semantic.py tests/test_collector.py -x` |
| **Full suite command** | `python -m pytest` |
| **Estimated runtime** | ~30–60s core (GLiNER detect/calibration tests skipped without `[llm-scrub]`) |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_scrubber_semantic.py tests/test_collector.py -x`
- **After every plan wave:** Run `python -m pytest`
- **Before `/gsd-verify-work`:** Full suite green **AND** the D-02 live local-Ollama capture run (Hermes 3 8B Q4) has produced a staging record with real `parameter_count`/`quantization`.
- **Max feedback latency:** ~60 seconds (core suite)

---

## Per-Requirement Verification Map

> Task IDs (`07-NN-MM`) filled in by the planner; this draft keys on requirement.

| Requirement | Behavior | Test Type | Automated Command | File Exists |
|-------------|----------|-----------|-------------------|-------------|
| CAPT-02 | one `post_llm_call` → human+gpt turns; no double-count from `conversation_history` | unit | `python -m pytest tests/test_collector.py -k llm_turn -x` | ❌ W0 (extend) |
| CAPT-03 | tool buffered by `turn_id`, dedup on `tool_call_id`, `result` JSON parsed, `status` ok→success | unit | `python -m pytest tests/test_collector.py -k tool_buffer -x` | ❌ W0 |
| CAPT-03 | turn-scoped `on_session_end` → exactly ONE staging file per session | unit | `python -m pytest tests/test_collector.py -k session_end_once -x` | ❌ W0 |
| CAPT-04 | `ollama.show()` mapped into `ModelMetadata` (mocked) | unit | `python -m pytest tests/test_collector.py -k ollama_metadata -x` | ❌ W0 |
| CAPT-04 | remote degradation: no ollama → slug inference, params `None` (D-03) | unit | `python -m pytest tests/test_collector.py -k remote_degrade -x` | ❌ W0 |
| CAPT-04 | **LIVE (D-02):** real local-Ollama run (Hermes 3 8B Q4) populates real param/quant | manual | documented walkthrough + captured staging JSON artifact | ❌ manual |
| PRIV-01 | GLiNER loads `nvidia/gliner-PII`; detects person/company/project/location | integration | `python -m pytest tests/test_scrubber_semantic.py -k detect -x` (needs `[llm-scrub]`) | ❌ W0 |
| PRIV-02 | band logic: ≥0.7 redact, 0.4–0.7 flag, <0.4 ignore (mock scores) | unit | `python -m pytest tests/test_scrubber_semantic.py -k bands -x` | ❌ W0 |
| PRIV-03 | **CALIBRATION GATE (D-06):** zero auto-redact ≥0.7 on code fixture; record FP rate | integration | `python -m pytest tests/test_scrubber_semantic.py -k calibration -x` | ❌ W0 |
| PRIV-02 / D-07 | asymmetric: tool fields FLAG-only, never auto-redacted | unit | `python -m pytest tests/test_scrubber_semantic.py -k asymmetric -x` | ❌ W0 |
| PRIV-04 | soft-import: core imports clean without `[llm-scrub]`; preview degrades gracefully | unit | `python -m pytest tests/test_scrubber_semantic.py -k soft_import -x` | ❌ W0 |
| SC#5 / D-08 | flagged entities surface in preview panel (text + label + confidence) | unit | `python -m pytest tests/test_cli.py -k flagged_panel -x` | ❌ W0 (extend) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky — all currently ⬜ pending.*

---

## Wave 0 Requirements

- [ ] `tests/fixtures/code_content_pii.json` — D-06 calibration fixture: known-safe identifiers (`import pandas as pd`, `const App = () => <React.Fragment/>`, `def compute_quality_score(record):`, variable/library names) plus a few real names to prove true-positive detection still fires.
- [ ] `tests/test_scrubber_semantic.py` — bands, asymmetric coverage (D-07), calibration gate (D-06), soft-import fallback. Guard GLiNER-dependent tests with `pytest.importorskip("gliner")` so the core suite stays green without the extra.
- [ ] `tests/test_collector.py` extensions — paired-turn mapping (CAPT-02), tool buffer/dedup (CAPT-03), turn-scoped session-end-once, ollama metadata (mocked) + remote degradation.
- [ ] `tests/test_cli.py` / `tests/test_plugin.py` extensions — flagged-panel surfacing (D-08); hooks invoke the collector (not just debug-log).
- [ ] Install lane: `pip install kajiba[llm-scrub]` for the GLiNER-dependent tests + the D-02 Ollama install/pull (Hermes 3 8B Q4).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live local-Ollama capture populates real `parameter_count` / `quantization` | CAPT-04 (D-02) | Requires Ollama installed + Hermes 3 8B Q4 pulled + a live Hermes session; can't be mocked and still prove SC#3 TRUE on real data | Install Ollama, `ollama pull` Hermes 3 8B Q4, run a Hermes session through the plugin, then `kajiba preview` — confirm staging JSON has non-null `parameter_count`/`quantization`/`model_family`/`context_window`. Archive the staging JSON as the phase artifact. |
| GLiNER first-load model download from Hugging Face | PRIV-01 | Network + ~570M model download; not part of the offline core suite | Run the `detect`/`calibration` tests once in a `[llm-scrub]`-installed lane; confirm `nvidia/gliner-PII` resolves (capital `PII` — lowercase 404s). |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (fixtures + new test files above)
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s (core suite)
- [ ] D-02 live local-Ollama run completed and artifact archived
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
