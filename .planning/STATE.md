---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Experiment Logging
status: executing
stopped_at: Phase 7 context gathered
last_updated: "2026-06-05T21:10:47.182Z"
last_activity: 2026-06-05 -- Phase 07 execution started
progress:
  total_phases: 10
  completed_phases: 4
  total_plans: 27
  completed_plans: 20
  percent: 40
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-02)

**Core value:** Real-world AI session data, tagged with full runtime context, flowing into a community dataset that accelerates local model fine-tuning for everyone.
**Current focus:** Phase 07 — turn-capture-semantic-pii-scrubbing
**Active milestone:** v1.2 Experiment Logging (Dual-Use), Phases 10-15 — Phases 10-12 complete (audited 2026-06-04, see `.planning/v1.2-MILESTONE-AUDIT.md`); next up Phase 13.
**Parallel milestone:** v1.1 Hermes Pipeline Validation, Phases 6-9 — Phase 6 complete (verified 2026-06-05); Phase 7 next. Shared foundation Phases 6-7 gate v1.2 Phase 14 live capture (Phase 6 dependency now cleared).

## Current Position

Phase: 07 (turn-capture-semantic-pii-scrubbing) — EXECUTING
Plan: 1 of 6
Status: Executing Phase 07
Last activity: 2026-06-05 -- Phase 07 execution started

Progress: [██████████] 100% (5/5 plans)

## Performance Metrics

**Velocity:**

- Total plans completed: 33 (v1.0)
- Average duration: --
- Total execution time: --

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1-5 (v1.0) | 13/13 | -- | -- |
| 10 | 3 | - | - |
| 11 | 3 | - | - |
| 12 | 4 | - | - |
| 13 | 5 | - | - |
| 06 | 5 | - | - |

**Recent Trend:**

- Last 5 plans: --
- Trend: Starting new milestone

*Updated after each plan completion*
| Phase 12 P01 | 6m | 2 tasks | 5 files |
| Phase 12 P02 | 6m | 1 task | 1 file |
| Phase 12 P03 | 5m | 1 task | 1 file |
| Phase 12 P04 | 10m | 2 tasks | 3 files |
| Phase 13 P01 | 18m | 3 tasks | 3 files |
| Phase 13 P02 | 12m | 1 task | 2 files |
| Phase 13 P03 | 9m | 1 tasks | 1 files |
| Phase 13 P04 | 14m | 2 tasks | 2 files |
| Phase 13 P05 | 14m | 2 tasks | 2 files |
| Phase 06 P01 | 3m | 3 tasks | 3 files |
| Phase 06 P02 | 13m | 3 tasks | 8 files |
| Phase 06 P03 | 6m | 2 tasks | 3 files |
| Phase 06 P04 | 2m | 1 tasks | 1 files |
| Phase 06 P04 (re-plan) | 4m | 2 tasks | 4 files |
| Phase 06 P05 | 2m | 2 tasks | 2 files |

## Accumulated Context

### Decisions

- Hermes 3 8B Q4 for data collection, Llama 3.2 3B for fine-tuning target
- HITL-heavy approach -- manual verification at every pipeline step
- GLiNER for semantic PII scrubbing (not Presidio/spaCy or generative LLM prompting)
- WSL2 required on Windows for Hermes Agent
- Plugin rewrite is greenfield (current Protocol-based integration is wrong)
- Scrubbing deferred to CLI step, never in hook callbacks (avoid blocking Hermes event loop)
- Dual-use decided 2026-06-03 (`/gsd-explore`): experiment/eval logging → parallel v1.2 milestone (Phases 10-15), separate `ExperimentRecord` on shared base, private/no-publish, shared core + divergent tail. v1.1 left intact; Phases 6-7 are shared foundation for v1.2 live capture (Phase 14).
- 10-01: ESCH-04 golden baseline (`tests/fixtures/golden_ids.json`) captured from pre-refactor schema over the 5 `*_trajectory.json` fixtures and committed BEFORE any schema edit; `enriched_catalog.json` excluded (no trajectory). Stored as committed JSON (not hardcoded constants); `minimal_trajectory.json` → `kajiba_c2eac32fcdc4`. `schema.py` untouched.
- 10-02: Extracted `RecordBase`; reparented `KajibaRecord(RecordBase)` with hash methods frozen — all 5 golden record_id/submission_hash byte-identical (ESCH-04 confirmed). Added `ExperimentRecord` family + `load_record()` manual factory (no discriminated union). `SCHEMA_VERSION` bumped 0.1.0→0.2.0. Experiment-id format LOCKED: `kajiba_exp_<12hex>` over experiment-identity payload with `started_at.isoformat()`. `validate_record`/`ConversationTurn` unchanged. ESCH-01/02/03/05 done.
- 11-01: Built the experiment-store persistence foundation. New `src/kajiba/experiment_store.py` (Click-free, single-responsibility, D-05) owns the only write path: `log_experiment(record, store_dir)` computes identity via the frozen Phase 10 methods, writes one flat `exp_<record_id>.json` atomically (`tempfile.mkstemp` + `os.replace`, cleanup on `BaseException`), dedups skip-with-notice (D-01/D-02), and enforces a D-13 structural guard (`store_dir.resolve().name != "experiments"` → ValueError). `build_experiment_record(**fields)` is a keyword-only constructor (D-06). `EXPERIMENTS_DIR = KAJIBA_BASE / "experiments"` added to `cli.py` + `_ensure_dirs()` (D-03, no new `~/.hermes` literal); package re-exports added to `__init__.py` (D-07). Decision: `store_dir` is an argument (not a constant baked into the store) so the module stays Click-free and test-isolatable. ELOG-02 complete; ELOG-03 structural half done (active publish guard still pending 11-03). Full suite 270 passed / 2 pre-existing skips, 0 regressions. Commits: test 0b57f65, feat 0be30da, feat 1255a07.
- 11-02: Added the `kajiba experiment` CLI surface (ELOG-01). New `experiment` Click group with `log` + `list`. `experiment log` has three input modes — `--from FILE` (load JSON, apply scalar overrides to the raw dict BEFORE validation per D-11, validate via `load_record` NOT `validate_record` per Pitfall 1, reject non-`model_experiment` with `click.ClickException`), scalar flags (`--score`/`--type`/`--task-category`/`--local-model` → `build_experiment_record`), and an interactive Rich fallback (prompts experiment_id/task_category/task_description/eval_score/experiment_type/local_model.model_name/local_model_output — minimal nested field only, Pitfall 3). All three modes funnel through `log_experiment(rec, EXPERIMENTS_DIR)` (D-08, CLI never writes the file). `experiment list` globs `exp_*.json` into a Rich table read-back. Decision: interactive prompt order locked to match the scripted-input test; list uses lightweight `json.loads` (data already validated at log time). Full suite 274 passed / 2 pre-existing skips, 0 regressions. Commits: test f7c7b91, feat 4b2dc5f.
- 11-03: Closed the active half of ELOG-03 (publish exclusion guard + D-14 regression). `publish` Step 4 loop now skips any outbox record whose raw-dict `record_kind == "model_experiment"` BEFORE `validate_record` (Pitfall 1 / T-11-10), printing `Skipping experiment record (never published): <name>` and `continue` — defense in depth over the structural `OUTBOX_DIR`/`EXPERIMENTS_DIR` split from 11-01 (T-11-08, D-13). `submit` gained a defensive `model_experiment` `click.ClickException` (T-11-09, Assumption A2 — structurally unreachable today, single guard not dead branching). New `tests/test_experiment_exclusion.py`: `test_publish_skips_experiment` (misplaced experiment in outbox skipped, network-free via a `GitHubOps` stub whose `check_auth` passes so the guard loop is reached but no PR opens) + `test_experiment_absent_from_community_paths` (D-14: real `log_experiment` write proven absent from outbox glob, byte-identical on disk, never in publish output). Full suite 276 passed / 2 pre-existing yaml-soft-dep skips, 0 regressions. ELOG-03 fully satisfied. Phase 11 ready for /gsd-verify-work (phase header owned by orchestrator). Commits: test c43d63f, feat 5610028.
- 10-03: Authored `tests/test_schema_backcompat.py` (parametrized golden-ID tripwire over all 5 fixtures + legacy-load + record_kind default + base inheritance + load dispatch) and `tests/test_schema_experiment.py` (round-trip equality + vocab rejection + recommended_action=None + lessons_learned=[] + eval_score bounds). Schema untouched (`git diff --quiet src/kajiba/schema.py` exits 0). Full suite: 264 passed, 2 PRE-EXISTING skips (yaml soft-dep not installed in test_cli.py/test_config.py), 0 failures. All ESCH-01..05 now covered by passing automated tests. Phase 10 COMPLETE. (Note: 10-VALIDATION.md `wave_0_complete`/`nyquist_compliant` flip deferred to verify-work.)
- [Phase ?]: 12-01: Wave 0 test foundation — 3 experiment fixtures (complete/thin/pii) + 2 RED scaffolds (8 contract tests). thin fixture required-fields-only so Plan 02 thin-band contract holds; pii fixture has real 64-hex model_hash + GPU name as byte-identical preservation targets. ScrubLog imported from kajiba.schema. RED confirmed (missing kajiba.eval_scorer/experiment_scrub only); pre-existing suite 276 passed, 0 regressions. Commits: 3a75662, e102686.
- 12-02: Implemented `src/kajiba/eval_scorer.py` (EEVAL-01) — `compute_eval_confidence(ExperimentRecord) -> EvalConfidenceResult` completeness/confidence lens (D-01, compute-on-read D-03, advisory D-04). New single-responsibility module mirroring `scorer.py`'s shape, NOT bolted onto it (D-09). LOCKED contract honored verbatim: WEIGHTS sum 1.0 (output_present .30 / reviewer_critique .20 / model_metadata .20 / hardware_present .10 / lessons_learned .10 / outcome_signals .10), COMPLETE_THRESHOLD=0.80, PARTIAL_THRESHOLD=0.50. `_score_outcome_signals` scores ONLY recommended_action+completed_at (each 0.5) and gives NO credit for eval_score being in range (Pitfall 4) → required-fields-only thin fixture scores 0.0 there, composite ≈0.367 < 0.50 → band `thin`. Bands complete/partial/thin strictly disjoint from community tiers (D-02); portable no-vocab scan green. `TypeError` guard via `isinstance` rejects KajibaRecord (experiment-only lens). No schema mutation; test_eval_scorer.py 4/4 GREEN; full suite (ignoring test_experiment_scrub.py, RED until 12-03) 280 passed / 2 pre-existing skips, 0 regressions. Decision: removed literal community-tier words from the module docstring (the no-vocab scan only strips #-comment lines) — cosmetic, no behavior change. Commit: feat 07f0ab8.

- 12-03: Implemented `src/kajiba/experiment_scrub.py` (EEVAL-02) — `scrub_experiment(ExperimentRecord) -> (ExperimentRecord, ScrubLog)`, the divergent-tail share-boundary scrub. Reuses `scrub_text`/`SCRUB_PATTERNS` verbatim (no fork, D-09) on a FIELD ALLOWLIST: `experiment.task_description`, `outcome.local_model_output`, `outcome.reviewer_critique` (Optional-guarded, Pitfall 2), per-element `outcome.lessons_learned` (list shape preserved, Pitfall 1). Model/hardware/model_hash/reviewer_model/scalar-outcome fields preserved byte-identical (D-05/D-06); envelope-mirrors `scrub_record` (model_dump→mutate copy→model_validate, D-08 store-raw upheld). ScrubLog folds api_keys+hex_tokens, potential_names=0 (Open Q2 RESOLVED). NEVER imports/calls `kajiba.privacy` — portable no-coupling source scan green. Decision: docstring describes the privacy SKIP boundary in prose (no literal helper names) so the source scan passes. test_experiment_scrub.py 4/4 GREEN; full suite 284 passed / 2 pre-existing skips, 0 regressions. Commit: feat c166de6.

- 12-04: Wired EEVAL-01/02 into the user-facing CLI + package surface (the only plan touching shared cli.py/__init__.py). New `_load_experiment(record_id)` store-load helper enforces T-12-10 (resolved-parent path-traversal guard, `path.resolve().parent == EXPERIMENTS_DIR.resolve()`) and T-12-11 (`load_record` + `isinstance(ExperimentRecord)` → clean ClickException, no traceback). `experiment score <id>` renders a compute-on-read confidence breakdown (per-check sub-scores + composite + complete/partial/thin band) plus a SEPARATE panel surfacing answer-quality `eval_score` distinctly from record confidence (Pitfall 4, D-03 never persists). `experiment scrub <id> [--out FILE]` previews a redaction-count table + scrubbed free text, or writes a scrubbed COPY to `--out` — NEVER overwrites the raw `exp_<id>.json` (D-08, T-12-12). `experiment list` gained a distinct "Confidence" column alongside the preserved "Score" (eval_score) column (T-12-13). Re-exported `compute_eval_confidence` + `scrub_experiment` from `kajiba/__init__.py` (A3). Decision: scrub PII assertion keys on the email (`[REDACTED_EMAIL]`) the shared scrubber reliably handles; discovered a pre-existing community-scrubber gap (`sk-[a-zA-Z0-9]{32,}` misses `sk-live-` hyphenated keys) — logged to `deferred-items.md`, NOT fixed (D-09 forbids forking the shared regex layer; out of scope for the integration plan). 5 new CLI tests (reuse `_isolate_store` verbatim, Pitfall 3); full suite 289 passed / 2 pre-existing skips, 0 regressions. Phase 12 all 4 plans complete. Commits: feat b70ba48, test 944527d.
- [Phase ?]: 13-01: Landed all Wave 0 RED scaffolds for Phase 13. update_experiment locked to EQUAL guard (accept store_dir==expected_base; reject otherwise; default base = experiment_store.EXPERIMENTS_DIR at call time). 3 pre-existing log_experiment tests migrated to expected_base=store (RED now via TypeError, GREEN post-13-02). New test_experiment_drift.py (7 pure compute_drift tests). CLI review/lessons/drift + _parse_lesson + WR-01/02/03 RED; _isolate_store also isolates experiment_store.EXPERIMENTS_DIR (raising=False until 13-02). EXPERIMENTS_DIR parity test guards literal drift. schema.py untouched; pre-existing suite green, 0 regressions.

- 13-02 (TDD GREEN, EREV-01/02/03): Added `update_experiment(record, store_dir, *, expected_base=None) -> Path` to experiment_store.py — the in-place overwrite write path (CR-01 closed, D-03). It OMITS log_experiment's `dest.exists()` early-return so corrections always overwrite, re-validates after mutation (`ExperimentRecord.model_validate(model_dump(...))`, Pitfall 3 — models lack validate_assignment), computes identity via frozen Phase 10 methods (identity excludes outcome → filename byte-stable, D-01), and writes atomically (mkstemp + os.replace + BaseException cleanup, verbatim from log_experiment). Added `EXPERIMENTS_DIR = Path.home()/".hermes"/"kajiba"/"experiments"` module constant (stdlib Path only, NO cli import — Click-free; mirrors cli.py:70; parity test guards drift). WR-04: replaced the old leaf-name guard (`resolved.name != "experiments"`) with the EQUAL predicate (`store_dir.resolve() == expected_base.resolve()`) on BOTH log_experiment (now with keyword-only `expected_base` param) and update_experiment; `expected_base` defaults None → resolved to EXPERIMENTS_DIR IN-BODY at call time (monkeypatchable, never def-time bound). DECISION: log_experiment keeps dedup-skip for identical re-logs; CR-01 closed by routing corrections through update_experiment (D-03/A5). DEVIATION (Rule 1): pre-existing test_experiment_exclusion `_isolate_dirs` broke under the tightened guard (patched only cli.EXPERIMENTS_DIR, not experiment_store.EXPERIMENTS_DIR) — added the store-module monkeypatch, matching 13-01's `_isolate_store` pattern. test_experiment_store.py 11/11 GREEN (4 new update + 3 migrated log + parity + refuses-outbox + base); schema.py untouched (git diff --quiet exit 0); full suite 296 passed / 2 pre-existing skips, 0 regressions (remaining reds are 13-03 drift module + 13-04/05 CLI subcommands, RED by design). Commit: feat 299c5ec.
- 13-04 (TDD GREEN, EREV-01/02 + WR-01/02/03): Added `kajiba experiment review` (--critique/--from/--reviewer-model/--action via click.Choice(RECOMMENDED_ACTIONS)) and `kajiba experiment lessons` (--add repeatable/--category; add/read/cross-record-query modes) to cli.py. New cli.py helpers: `_mutate_experiment` (CLI single write funnel → update_experiment, D-03/CR-01), `_parse_lesson` (first-colon str.partition, lowercased category, `uncategorized` fallback, colons-in-text preserved), `_read_critique_input` (--critique > --from .txt/.json > offline stdin paste). UNCATEGORIZED constant added. `__init__.py` re-exports update_experiment + compute_drift (cli.py compute_drift import deferred to 13-05). WR-03: json.loads wrapped → "Malformed JSON"; WR-01: partial scalar flags raise friendly error naming missing flags; WR-02: missing record_kind + incomplete fragments → friendly ClickException (no ValidationError leak). DEVIATION (Rule 1): plan specified setdefault("record_kind","model_experiment") for WR-02 but locked test_missing_record_kind_friendly asserts exit!=0 for a fragment missing record_kind — switched to an explicit pre-load guard raising a friendly error (test authoritative over plan idiom). 17 newly green → full suite 320 passed / 2 skipped, ONLY the 2 13-05 drift CLI tests remain RED by design, 0 regressions; schema.py untouched (git diff --quiet exit 0). Commits: feat 868099f, feat 3cae4c7.
- [Phase ?]: 13-03 (TDD GREEN, EREV-03): Added src/kajiba/experiment_drift.py — pure Click-free stdlib compute_drift(records, threshold=DRIFT_THRESHOLD)->dict[str,bool] mirroring eval_scorer's shape but verdict PERSISTED by caller (D-02, vs compute-on-read). Groups by (local_model.model_name, task_category); flags both directions (D-14) beyond DRIFT_THRESHOLD=0.15 (flag-only, no config read); <2-run guard before any mean() call; verdict spans ALL record_ids for idempotent set/clear (D-15). DEVIATION (Rule 1): plan/RESEARCH specified leave-one-out baseline but it flagged non-outlier peers, contradicting locked 13-01 tests — switched to WHOLE-GROUP mean (A1/Discretion #4 delegate baseline choice). 7/7 drift tests GREEN; schema.py untouched; full suite 303 passed (+7 vs 296), 19 fails all confined to test_cli_experiment.py (13-04/05 CLI subcommands, RED by design), 0 regressions. Commit: feat 2bd3530.

- 13-05 (TDD GREEN, EREV-03/02): Added `kajiba experiment drift` to cli.py — globs the store via new `_load_all_experiments` (per-file `try/except continue`, Pitfall 6), runs `compute_drift`, and idempotently SETs/CLEARs `outcome.drift_flag` through the single `_mutate_experiment` → `update_experiment` funnel (D-15; only records whose on-disk flag DIFFERS from the verdict are rewritten — no disk churn). `--threshold` overrides `DRIFT_THRESHOLD`; `--id` scopes the scan AND the writes to the target record's WHOLE `(model_name, task_category)` group (locked Open Question 2), leaving other groups untouched. Added the cli.py `from kajiba.experiment_drift import DRIFT_THRESHOLD, compute_drift` import (first use, owned here; 13-04 added only the `__init__.py` re-export). Enriched `experiment list` with `Lessons` (count) + `Drift` (⚠) columns read from the RAW dict with the per-file guard preserved. DEVIATION (Rule 1): switched `compute_drift` baseline from 13-03's whole-group MEAN to NEAREST-IN-GROUP-NEIGHBOR distance — the locked 13-01 CLI tests fail under mean/median because a `[0.90,0.90,0.40]` group's mean (0.733) flags the consistent 0.90 runs, and a balanced two-cluster group (four 0.90s + three ~0.40s) cannot clear via mean/median; nearest-neighbor (a run drifts only with NO peer within threshold, both directions D-14) satisfies all 7 unit + 2 CLI tests. Phase gate: full suite 322 passed / 2 pre-existing skips, 0 regressions; `git diff --quiet src/kajiba/schema.py` exit 0. Phase 13 COMPLETE — ready for /gsd-verify-work. Commits: feat 4742cee, feat 62194c5.
- [Phase ?]: 06-01: Wave 0 RED scaffolds for Phase 6 — TestGetHermesHome (test_config.py), test_plugin.py (StubCtx + register/kwargs/debug), test_no_hermes_integration.py (D-07 static guard). All RED only on not-yet-built symbols (get_hermes_home, kajiba.plugin) or the not-yet-deleted module; full suite collects exit 0. PyYAML temporarily installed only to observe acceptance, then removed (importorskip untouched).

- 06-02 (PLUG-03, D-07/08/09/10): Added `kajiba.config.get_hermes_home()` — the single HERMES_HOME resolver (reads os.environ every call, falls back to `~/.hermes`). Migrated all five modules (config/collector/cli/publisher/experiment_store) to route paths through it via the LOCKED constant-vs-lazy split: module-level KAJIBA_BASE/EXPERIMENTS_DIR/DOWNLOADS_DIR/CLONE_DIR stay constants (preserving ~30 monkeypatch sites), config.yaml read/write goes lazy in-body. experiment_store.EXPERIMENTS_DIR derives from get_hermes_home() (stays Click-free, NO cli import; parity test green because both use the same helper). collector.on_session_start now `(session_id, model_config=None, *, model_name=None, platform=None)` — legacy positional dict still works, omitted dict builds `{model_name, provider: platform}`, all-None builds `{}` (D-08). DELETED src/kajiba/hermes_integration.py (D-07); CLAUDE.md repointed to src/kajiba/plugin/ register(ctx). DEVIATION (Rule 1): dev machine's real HERMES_HOME leaked its profile config.yaml (`min_quality_tier: gold`) into pre-existing config tests that patched only Path.home — added `delenv("HERMES_HOME")` to the test_config.py fake_home fixture and an autouse fixture to test_cli.py TestConfigSubcommands (strengthens temp-home isolation, no assertion weakened). Baseline restored: 324 passed / 2 pre-existing yaml skips, 3 RED-by-design test_plugin.py (Plan 03 target), 0 regressions. Commits: feat ea5e958, feat 0026091, chore 5059003, fix f5acbf7.
- [Phase ?]: 06-03 (PLUG-01/02, CAPT-01 code half): Built greenfield src/kajiba/plugin/ package replacing deleted hermes_integration.py. register(ctx) wires four hooks via ctx.register_hook fault-tolerantly; **kwargs-tolerant handlers (MP-2) dispatch to unchanged KajibaCollector; KAJIBA_DEBUG=1 logs kwarg name/type/repr[:120] (T-06-07) as Plan 05's live-discovery mechanism. Turn hooks debug-log only (Phase 7 boundary). plugin.yaml fields [ASSUMED] until Plan 05. 3 Plan 01 RED plugin tests GREEN; full suite 327 passed / 2 pre-existing skips, 0 regressions. Commits: c4b26d8, 60adf3b.
- [Phase ?]: 06-04: Wrote docs/hermes-setup.md — checkpoint-gated WSL2/GPU/Ollama/Hermes v0.6.0/plugin setup guide (ENV-01/02/03, D-03/D-04). Five per-stage verification checkpoints; 3-command symlink dev workflow (ln -s src/kajiba/plugin into ~/.hermes/plugins/kajiba) with copy fallback; troubleshooting for MP-8 CUDA stub overwrite, MP-5 num_ctx truncation, MP-9 Ollama WSL2 binding; KAJIBA_DEBUG PII-in-logs security note (T-06-09). Commit: docs 875246f. [SUPERSEDED 2026-06-05 by the re-plan rewrite below; original summary archived to 06-04-SUMMARY.superseded-wsl2-v0.6.md]

- 06-04 (re-plan, D-11/D-12/D-13/D-14/D-04-revised/D-20): Corrective IN-PLACE rewrite of docs/hermes-setup.md from WSL2/v0.6.0 to native-Windows-primary Hermes v0.15.x + remote backend (414 lines, no emojis, no residual v0.6.0). Six checkpoint-gated primary steps (install Hermes v0.15.x / editable-install Kajiba / symlink into resolved discovery plugins dir / `hermes plugins enable kajiba` REQUIRED / plugin loads + hooks fire / edit-reload); HERMES_PLUGINS_DEBUG=1 folded in alongside retained KAJIBA_DEBUG PII note (T-06-09); WSL2+GPU+Ollama+MP-8/MP-5/MP-9 relocated verbatim to an OPTIONAL Appendix; D-20 flag for stale ROADMAP SC-1/ENV-01/ENV-02 wording (NOT edited). Version-reconciled plugin.yaml header comment + plugin/__init__.py + plugin/hooks.py docstrings to v0.15.x (manifest tags stay [ASSUMED]; [CONFIRMED] promotion is 06-05/D-18). DEVIATION (Rule 3): reworded intro + D-20 note to keep literal WSL2/v0.6.0 strings only inside the Appendix (satisfies appendix-before-WSL2 ordering + no-v0.6.0-outside-appendix). tests/test_plugin.py 3/3 green. Commits: docs a34e165 (plugin source), docs af7e15b (guide rewrite).

- 06-05 (live verification, D-15/D-16/D-17/D-18/D-19/D-21, ENV-01/02/03 + PLUG-01/02 + CAPT-01): Live Hermes v0.15.1 native-Windows session (id 20260605_111446_5a978c) on a REMOTE backend (nvidia/nemotron-3-ultra:free via OpenRouter; earlier same-build run used claude-opus-4-8 — no GPU/Ollama) with KAJIBA_DEBUG=1 fired all four hooks; startup line `Kajiba registered hooks: on_session_start, post_llm_call, post_tool_call, on_session_end` confirmed register(ctx) ran. Wrote 06-HOOK-KWARGS.md — per-hook kwarg tables dual-tagged [DOCUMENTED v0.15.x] + [VERIFIED] (undocumented extras [VERIFIED]-only), 8 cross-cutting findings, Phase 7 implications (CAPT-02/03 mapping); synthetic PII placeholders (T-06-11). KEY FINDINGS: telemetry_schema_version="hermes.observer.v1" on ALL four hooks; on_session_end is TURN-SCOPED (per run_conversation, not session-final); post_tool_call.result is a JSON str while args is a dict; rich correlation ids task_id/turn_id ("<session>:<task>:<8hex>")/tool_call_id/api_request_id; D-17 discovery dir = <HERMES_HOME>/plugins/ i.e. %LOCALAPPDATA%\hermes\plugins\ (confirmed via installed source AND `hermes plugins list` source=user); D-19 `hermes plugins enable kajiba` REQUIRED (inert until enabled); ENV-03 native-Windows symlink FAILED (admin required, Dev Mode off) → COPY fallback used; plugin installed editable into the Hermes venv (%LOCALAPPDATA%\hermes\hermes-agent\venv, kajiba 0.2.0) not the repo .venv. Promoted plugin.yaml header [ASSUMED] → [CONFIRMED v0.15.x] (D-18, comment-only). hooks.py [ASSUMED] docstrings left for Phase 7 (out of scope). tests/test_plugin.py 3/3 green. No deviations. Phase 6 all 5 plans complete — ready for /gsd-verify-work. Commits: docs e401885 (06-HOOK-KWARGS.md), docs 3b13724 (plugin.yaml promotion), docs ec27472 (summary).

### Pending Todos

None.

### Blockers/Concerns

- RESOLVED 2026-06-05 (06-05): Hermes hook kwargs verified live on v0.15.1 — all four hooks' payloads recorded dual-tagged in 06-HOOK-KWARGS.md. The "no formal payload schema published" blocker is permanently closed (D-16/D-21).
- GLiNER false positive rate on code content needs calibration in Phase 7
- WSL2 CUDA driver stub overwrite risk -- install only cuda-toolkit, not cuda meta-package (WSL2-only; native-Windows is now the primary path)

## Session Continuity

Last session: 2026-06-05T16:45:47.491Z
Stopped at: Phase 7 context gathered
Resume file: .planning/phases/07-turn-capture-semantic-pii-scrubbing/07-CONTEXT.md
