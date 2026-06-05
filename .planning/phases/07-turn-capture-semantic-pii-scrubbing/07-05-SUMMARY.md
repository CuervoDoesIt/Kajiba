---
phase: 07-turn-capture-semantic-pii-scrubbing
plan: 05
subsystem: privacy
tags: [gliner, semantic-pii, cli, click, rich, scrubbing, layer-c]

requires:
  - phase: 07-04
    provides: "kajiba.scrubber_semantic.scrub_record_semantic + SemanticScrubUnavailable (GLiNER Layer C with soft-import degrade)"
  - phase: 07-02
    provides: "FlaggedItem reason format + semantic-scrub test surface"
provides:
  - "Shared _apply_semantic_layer helper composing Layer C after Layer B at every scrub_record call site"
  - "GLiNER semantic redactions + 0.4-0.7 flags surfaced in the existing kajiba preview flagged panel (D-08)"
  - "Graceful degrade: kajiba preview/submit/export/review never crash when [llm-scrub] is absent (PRIV-04)"
  - "Scoped PyYAML importorskip so the full test_cli.py suite collects (unmasked ~80 previously-skipped CLI tests)"
affects: [phase-08-resumable-review, cli, privacy-pipeline]

tech-stack:
  added: []
  patterns:
    - "Single shared Layer-C composition helper reused across 4 CLI scrub sites (no per-site duplication)"
    - "try/except SemanticScrubUnavailable degrade boundary at the CLI layer (soft-dep tolerance)"

key-files:
  created: []
  modified:
    - src/kajiba/cli.py
    - tests/test_cli.py

key-decisions:
  - "Export/review/submit route through the same _apply_semantic_layer so semantic name redactions apply before any record leaves the machine (T-07-12), not just in preview"
  - "Fixed a pre-existing module-level importorskip(yaml) that silently skipped the entire test_cli.py file; scoped the PyYAML gate to only TestConfigSubcommands"

patterns-established:
  - "Layer composition at the CLI boundary: regex scrub -> _apply_semantic_layer -> anonymize/jitter/consent, with semantic flags folded into the existing _render_preview(flagged_items=...) channel"
  - "Model-free CLI tests for ML-gated behavior: monkeypatch kajiba.cli.scrub_record_semantic to a stub so the flagged-panel + degrade paths run in the core suite without gliner/torch"

requirements-completed: [PRIV-01, PRIV-02, PRIV-04]

duration: 5min
completed: 2026-06-05
---

# Phase 07 Plan 05: CLI Layer-C Wiring Summary

**GLiNER semantic name redactions and 0.4-0.7 confidence flags now surface in `kajiba preview` through a single shared composition helper wired into preview/submit/export/review, degrading gracefully to regex-only when the `[llm-scrub]` extra is absent.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-06-05T21:46:09Z
- **Completed:** 2026-06-05T21:50:43Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `_apply_semantic_layer(scrubbed_record, regex_flagged, scrub_log)` — runs `scrub_record_semantic` inside `try/except SemanticScrubUnavailable`, sets `ScrubLog.potential_names_redacted`, increments `ScrubLog.items_flagged`, and returns the regex + semantic flag list so the SAME `_render_preview(flagged_items=...)` panel surfaces both (D-08, no new render surface).
- Wired the helper into all 4 flag-rendering `scrub_record` call sites: `preview`, `submit`, `export`, `review` — so Layer C composes after Layer B consistently (D-11). Export/submit/review apply semantic redactions to the record that flows downstream, closing T-07-12 (redact before the record can leave the machine).
- Graceful degrade verified: with `[llm-scrub]` absent the helper catches `SemanticScrubUnavailable` and falls back to regex-only — `kajiba preview` exits 0 (T-07-13).
- Added model-free `TestSemanticFlaggedPanel` tests: a stubbed semantic flag appears in the panel with `GLiNER company (confidence 0.55)` reason; a `SemanticScrubUnavailable`-raising stub still exits 0.

## Task Commits

1. **Task 1+2 (RED): failing flagged-panel + degrade tests; scope yaml skip** — `961aa94` (test)
2. **Task 1 (GREEN): shared helper + wire Layer C into 4 CLI sites** — `99758a2` (feat)

**Plan metadata:** (final docs commit)

_Tasks 1 and 2 share the same source surface (the shared helper + its tests); they landed as one RED test commit followed by one GREEN feat commit rather than four separate commits._

## Files Created/Modified

- `src/kajiba/cli.py` — added `_apply_semantic_layer` helper + `from kajiba.scrubber_semantic import (SemanticScrubUnavailable, scrub_record_semantic)`; invoked the helper at the preview/submit/export/review scrub sites.
- `tests/test_cli.py` — added `TestSemanticFlaggedPanel` (model-free surfacing + degrade tests); scoped the module-level `importorskip("yaml")` to a class-level `skipif` on `TestConfigSubcommands`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Module-level `importorskip("yaml")` silently skipped the entire `test_cli.py` file**

- **Found during:** Task 1 (RED) — the new `flagged_panel` test was being reported as "1 skipped / 0 collected" rather than failing.
- **Issue:** `test_cli.py` line ~1352 had a bare module-level `yaml = pytest.importorskip("yaml")`. Because `importorskip` at module scope skips the WHOLE module on failure, the absence of PyYAML (a soft dependency, not installed here) silently skipped every CLI test — including the 07-05 semantic flagged-panel tests this plan must make GREEN. The acceptance criterion `pytest tests/test_cli.py -k "flagged_panel" PASSES` was structurally impossible to satisfy.
- **Fix:** Replaced the module-level `importorskip` with a guarded `try/except ImportError` (`_yaml`) and a class-level `@pytest.mark.skipif(_yaml is None, ...)` on `TestConfigSubcommands` (the only class that reads/writes `~/.hermes/config.yaml`). All other CLI tests now collect and run.
- **Impact:** Unmasked ~80 previously-silently-skipped CLI tests — all pass. Full suite went from 348 passed / 4 skipped to 430 passed / 16 skipped (the extra 16 skips are the now-explicit per-test PyYAML + LANE-B GLiNER skips; the net new passing tests were already written but never executed).
- **Files modified:** `tests/test_cli.py`
- **Commit:** `961aa94`

## Threat Surface

T-07-12 (info disclosure on submit/export) and T-07-13 (DoS via missing extra) from the plan's threat register are both mitigated by this wiring: the shared helper applies semantic redactions on the submit/export/review paths (not just preview), and the `SemanticScrubUnavailable` catch keeps `kajiba preview` running when `[llm-scrub]` is absent. No new security-relevant surface introduced beyond the planned threat model.

## Known Stubs

None. The semantic redaction path is fully wired; the only "no-op" behavior is the intentional graceful degrade when `[llm-scrub]` is not installed (PRIV-04 / D-10), which is by design and surfaced separately at the CLI boundary.

## Verification

- `python -m pytest tests/test_cli.py -k "flagged_panel"` — 1 passed.
- `python -m pytest tests/test_cli.py -k "flagged_panel or preview"` — 14 passed.
- `python -m pytest` (full suite) — 430 passed / 16 skipped (PyYAML soft-dep + LANE-B GLiNER), 0 regressions.
- `python -c "from kajiba import cli"` — imports clean without `[llm-scrub]`.
- Grep: `_apply_semantic_layer(` invoked at 4 scrub sites (preview/submit/export/review); no `pipeline_stage` field added (D-09).

## Success Criteria

- **SC#4:** `kajiba preview` shows GLiNER-detected names redacted (Layer C composes after regex via the shared helper; semantic redactions flow into the rendered record). ✓ (observable when `[llm-scrub]` present; degrades cleanly otherwise)
- **SC#5:** 0.4-0.7 entities surface in the flagged-for-review panel with `GLiNER {label} (confidence {X.XX})` label + confidence (D-08). ✓ (asserted by the model-free `flagged_panel` test)
- Layer C applied consistently across all 4 scrub sites; graceful degrade without the extra; no Phase 8 scope (no `pipeline_stage`, no resumable review). ✓

## Self-Check: PASSED

- `07-05-SUMMARY.md` — FOUND
- `src/kajiba/cli.py` — FOUND
- Commit `961aa94` (test RED) — FOUND
- Commit `99758a2` (feat GREEN) — FOUND
