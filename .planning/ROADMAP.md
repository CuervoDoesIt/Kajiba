# Roadmap: Kajiba

## Milestones

- ✅ **v1.0 MVP** -- Phases 1-5 (shipped 2026-04-02)
- 🚧 **v1.1 Hermes Pipeline Validation** -- Phases 6-9 (in progress)
- 🚧 **v1.2 Experiment Logging (Dual-Use)** -- Phases 10-15 (parallel to v1.1)

## Phases

<details>
<summary>v1.0 MVP (Phases 1-5) -- SHIPPED 2026-04-02</summary>

- [x] Phase 1: Privacy Foundation (3/3 plans) -- completed 2026-03-31
- [x] Phase 2: Data Quality & Transparency (3/3 plans) -- completed 2026-03-31
- [x] Phase 3: Dataset Publishing (2/2 plans) -- completed 2026-03-31
- [x] Phase 4: Contribution Modes (3/3 plans) -- completed 2026-04-01
- [x] Phase 5: Consumer Experience (2/2 plans) -- completed 2026-04-02

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

### v1.1 Hermes Pipeline Validation (In Progress)

**Milestone Goal:** Prove the end-to-end pipeline works with the real Hermes Agent -- collect actual session data, walk it through scrub/score/publish, and fine-tune a local model with the result.

- [x] **Phase 6: Environment + Plugin Foundation** - Working Hermes dev environment and plugin scaffold that receives hook events
 (completed 2026-06-05)
- [ ] **Phase 7: Turn Capture + Semantic PII Scrubbing** - Real session data flowing through capture and semantic privacy layers
- [ ] **Phase 8: HITL Validation + Pipeline Integration** - Manual review workflow and end-to-end pipeline smoke test on real data
- [ ] **Phase 9: Fine-Tune Experiment** - QLoRA fine-tune of a local 3B model on Kajiba-collected data as milestone gate

### v1.2 Experiment Logging (Dual-Use) — Parallel to v1.1

**Milestone Goal:** Add a first-class, private experiment/eval-logging capability — capture local-model outputs, reviewer-model critiques, eval scoring, and quality drift — reusing Kajiba's schema/scrub core but with its own scorer, private store, and analysis export (no community publish). Runs in parallel with v1.1; only live capture (Phase 14) depends on v1.1 Phase 6–7.

- [x] **Phase 10: Experiment Schema Foundation** - `ExperimentRecord` on a shared base + `record_kind` discriminator, back-compatible with existing records (completed 2026-06-03)
- [x] **Phase 11: Experiment Logging & Private Store** - `kajiba experiment` CLI + programmatic logging into a private local namespace (completed 2026-06-04)
- [x] **Phase 12: Eval Scoring & Scrub Tuning** - eval-specific scorer and experiment-aware scrubbing (completed 2026-06-04)
- [x] **Phase 13: Reviewer Critique & Drift** - critique attachment, queryable `lessons_learned`, quality-drift detection (completed 2026-06-04)
- [ ] **Phase 14: Live Experiment Capture** - capture eval runs from live Hermes sessions via shared hooks (depends on Phase 6–7)
- [ ] **Phase 15: Analysis Export & Practice-Project Integration** - analysis export format + Nemotron/Qwen/Gemma workflow writes directly to experiment records

## Phase Details

### Phase 6: Environment + Plugin Foundation

**Goal**: Hermes Agent discovers and loads Kajiba as a plugin, and hook events fire confirmed on a live session
**Depends on**: Phase 5 (v1.0 complete)
**Requirements**: ENV-01, ENV-02, ENV-03, PLUG-01, PLUG-02, PLUG-03, CAPT-01
**Success Criteria** (what must be TRUE):

  1. Developer can follow a setup guide to get WSL2 + Hermes Agent v0.6.0 + Ollama running with GPU acceleration verified
  2. Hermes Agent discovers and loads the Kajiba plugin from the plugin directory on startup
  3. Running a Hermes session causes `on_session_start`, `post_llm_call`, `post_tool_call`, and `on_session_end` hooks to fire and log their kwargs
  4. All Kajiba file paths resolve correctly under HERMES_HOME profile isolation (not hardcoded `~/.hermes`)
  5. Developer can symlink the Kajiba plugin directory into Hermes for a rapid edit-reload development cycle

**Plans**: 5 plans

**Wave 1**

- [x] 06-01-PLAN.md — Wave 0 test scaffolds: get_hermes_home cases, test_plugin (stub ctx/register/kwargs/debug), static hermes_integration guard (PLUG-03/PLUG-02/CAPT-01)

**Wave 2** *(blocked on 06-01)*

- [x] 06-02-PLAN.md — HERMES_HOME path migration across 5 modules (parity-safe) + delete hermes_integration.py + collector signature adapt (PLUG-03) — completed 2026-06-04

**Wave 3** *(blocked on 06-02 — needs new collector signature + get_hermes_home)*

- [x] 06-03-PLAN.md — Plugin package: register(ctx) + 4 hooks + KAJIBA_DEBUG discovery mode + plugin.yaml (PLUG-01/PLUG-02/CAPT-01)

**Wave 4** *(blocked on 06-03)*

- [x] 06-04-PLAN.md — docs/hermes-setup.md re-plan: native-Windows v0.15.x primary path + hermes plugins enable + HERMES_PLUGINS_DEBUG; WSL2/GPU/Ollama demoted to optional appendix; v0.6.0->v0.15.x reconciliation across guide + plugin source (ENV-01/ENV-02/ENV-03) — completed 2026-06-05 (corrective in-place rewrite)

**Wave 5** *(live, human-verify; blocked on 06-03 + 06-04)*

- [x] 06-05-PLAN.md — re-plan: native-Windows live confirm of documented v0.15.x hook kwargs (remote backend, hermes plugins enable + KAJIBA_DEBUG) → 06-HOOK-KWARGS.md; resolve discovery dir; promote plugin.yaml to [CONFIRMED v0.15.x] (ENV-01/02/03, PLUG-01/02, CAPT-01) — completed 2026-06-05 (live v0.15.1, all 4 hooks fired)

### Phase 7: Turn Capture + Semantic PII Scrubbing

**Goal**: Real Hermes session data is captured into KajibaRecord objects and scrubbed by both regex and semantic PII layers
**Depends on**: Phase 6
**Requirements**: CAPT-02, CAPT-03, CAPT-04, PRIV-01, PRIV-02, PRIV-03, PRIV-04
**Success Criteria** (what must be TRUE):

  1. User and assistant turns from a live Hermes session are captured as ConversationTurn objects with correct role attribution
  2. Tool calls from `post_tool_call` events are attached to the correct assistant turn via the pending turn buffer
  3. Model metadata (parameter count, quantization, family, context length) is captured from Ollama and stored in ModelMetadata
  4. Running `kajiba preview` on a captured session shows GLiNER-detected personal names, company names, and project names redacted (not just regex patterns)
  5. Entities with confidence between 0.4 and 0.7 are flagged for human review rather than auto-redacted

**Plans**: 6 plans

**Wave 1** *(parallel — disjoint files)*

- [ ] 07-01-PLAN.md — Wave 0 capture scaffolds (RED: paired-turn/tool-buffer/session-end-once/ollama/remote-degrade) + [llm-scrub] extra (CAPT-02/03/04, PRIV-04)
- [ ] 07-02-PLAN.md — Wave 0 semantic scaffolds (RED: bands/asymmetric/calibration/soft-import) + code_content_pii.json fixture (PRIV-01/02/03)

**Wave 2** *(parallel — blocked on Wave 1; disjoint files)*

- [ ] 07-03-PLAN.md — Promote capture: paired-turn + tool buffer (ok→success), ollama metadata + remote degrade, finalize-once session-end, promoted hooks (CAPT-02/03/04)
- [ ] 07-04-PLAN.md — GLiNER scrubber_semantic: nvidia/gliner-PII detector, D-05 bands, D-07 asymmetric coverage, D-06 calibration gate, retire scrubber_llm stub (PRIV-01/02/03)

**Wave 3** *(blocked on 07-04 — cli.py)*

- [ ] 07-05-PLAN.md — CLI Layer-C wiring: shared helper across scrub_record sites, semantic flags into the existing preview panel, graceful degrade (PRIV-01/02/04)

**Wave 4** *(live, human-action; blocked on 07-03 + 07-04 + 07-05)*

- [ ] 07-06-PLAN.md — D-02 live local-Ollama capture run (Hermes 3 8B Q4): real ollama.show() metadata + live GLiNER preview → 07-LIVE-CAPTURE.md artifact (CAPT-04, PRIV-01)

### Phase 8: HITL Validation + Pipeline Integration

**Goal**: A developer can manually walk a real captured session through every pipeline step and verify correctness at each stage
**Depends on**: Phase 7
**Requirements**: VAL-01, VAL-02, VAL-03, PLUG-04, PLUG-05
**Success Criteria** (what must be TRUE):

  1. Developer can view the raw pre-scrub captured record via `kajiba preview --raw` or `kajiba inspect` for comparison against the scrubbed version
  2. Staging records track their `pipeline_stage` (captured/scrubbed/reviewed/scored/approved) so a review session can be resumed without re-processing
  3. A real Hermes session has been collected, scrubbed, scored, reviewed, published, and downloaded successfully end-to-end
  4. Kajiba plugin is installable via `pip install kajiba[hermes]` without manual file copying

**Plans**: TBD

### Phase 9: Fine-Tune Experiment

**Goal**: Kajiba-collected and published data successfully fine-tunes a local 3B model, proving the full pipeline loop
**Depends on**: Phase 8
**Requirements**: VAL-04
**Success Criteria** (what must be TRUE):

  1. Published Kajiba records are downloadable via `kajiba download` and convertible to training format via `to_sharegpt()`
  2. QLoRA fine-tune of Llama 3.2 3B completes on the collected data using RTX 4070 8GB without OOM
  3. A documented fine-tuning guide (`docs/fine-tuning-guide.md`) exists with reproducible steps for the full collect-to-train workflow

**Plans**: TBD

### Phase 10: Experiment Schema Foundation

**Goal**: A separate `ExperimentRecord` type exists on a shared base with a `record_kind` discriminator, and all existing records keep working
**Depends on**: None — v1.1-independent (recommended starting point for the v1.2 track)
**Requirements**: ESCH-01, ESCH-02, ESCH-03, ESCH-04
**Success Criteria** (what must be TRUE):

  1. A `record_kind` field distinguishes coding-session and model-experiment records and defaults to `coding_session` for records that omit it
  2. `KajibaRecord` and `ExperimentRecord` share a common base model holding model metadata, hardware profile, scrub log, and IDs
  3. An `ExperimentRecord` can be constructed with experiment metadata and outcome fields and round-trips through JSON serialization/validation
  4. All existing staged/outbox `KajibaRecord` JSON files load without error and produce identical record/submission IDs to before the refactor**Plans**: 3 plans

**Wave 1**

- [x] 10-01-PLAN.md — Capture pre-refactor golden ID baseline (ESCH-04 tripwire) — completed 2026-06-03

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 10-02-PLAN.md — Refactor schema.py: RecordBase + ExperimentRecord family + load_record (ESCH-01/02/03/05) — completed 2026-06-03 (golden hashes byte-identical, ESCH-04 confirmed)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 10-03-PLAN.md — Back-compat + experiment test suites (ESCH-01..05) — completed 2026-06-03 (264 passed / 2 pre-existing skips; golden tripwire green for all 5 fixtures)

### Phase 11: Experiment Logging & Private Store

**Goal**: A developer can log an eval run — by CLI or script — into a private local store separate from coding sessions
**Depends on**: Phase 10
**Requirements**: ELOG-01, ELOG-02, ELOG-03
**Success Criteria** (what must be TRUE):

  1. Running a `kajiba experiment` CLI command records an experiment run as an `ExperimentRecord` without a live Hermes session
  2. An external script can create and persist an `ExperimentRecord` via a programmatic entry point
  3. Experiment records are written to a private namespace distinct from coding-session staging/outbox and never appear in publish/browse/download output

**Plans**: 3 plans
**Wave 1**

- [x] 11-01-PLAN.md — Experiment store foundation: log_experiment/build_experiment_record, EXPERIMENTS_DIR + re-exports (ELOG-02, ELOG-03 structural) — 3 tasks, 270 passed/2 skipped, 0 regressions

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 11-02-PLAN.md — kajiba experiment CLI group: log (--from/flags/interactive) + list (ELOG-01) — 2 tasks, 274 passed/2 skipped, 0 regressions

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 11-03-PLAN.md — Publish exclusion guard + D-14 regression + full-suite gate (ELOG-03 active) — 3 tasks, 276 passed/2 skipped, 0 regressions

### Phase 12: Eval Scoring & Scrub Tuning

**Goal**: Experiment records are scored by eval-appropriate signals and scrubbed without losing model/hardware context
**Depends on**: Phase 10 (can run in parallel with Phase 11)
**Requirements**: EEVAL-01, EEVAL-02
**Success Criteria** (what must be TRUE):

  1. An eval-specific scorer assigns a quality result to an `ExperimentRecord` using signals appropriate to model-output evaluation (not coding-trajectory coherence)
  2. Scrubbing an `ExperimentRecord` redacts personal/PII data while preserving the model-identity and hardware fields needed for analysis

**Plans**: 4 plans

**Wave 1**

- [x] 12-01-PLAN.md — Wave 0 test foundation: 3 experiment fixtures (complete/thin/pii) + RED scaffolds for eval scorer & experiment scrub (EEVAL-01/02)

**Wave 2** *(blocked on Wave 1 completion; 12-02 ∥ 12-03 parallel — no file overlap)*

- [x] 12-02-PLAN.md — eval_scorer.py: compute_eval_confidence + EvalConfidenceResult, complete/partial/thin bands (EEVAL-01)
- [x] 12-03-PLAN.md — experiment_scrub.py: field-allowlist scrub reusing scrub_text, preserve model_hash/hardware byte-identical (EEVAL-02)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 12-04-PLAN.md — CLI wiring: experiment score/scrub subcommands + list Confidence column + __init__ re-exports + integration tests (EEVAL-01/02) — 2 tasks, 289 passed/2 skipped, 0 regressions

### Phase 13: Reviewer Critique & Drift

**Goal**: Reviewer critiques, lessons learned, and quality drift can be attached to and computed for experiment records
**Depends on**: Phase 11, Phase 12
**Requirements**: EREV-01, EREV-02, EREV-03
**Success Criteria** (what must be TRUE):

  1. A reviewer (human or model, e.g. Grok) can attach a critique to an existing experiment record via `kajiba experiment review`
  2. `lessons_learned` can be recorded in a queryable form (structured categories and/or free text) and read back
  3. Quality drift across repeated runs of the same model+task is computed and surfaced as a flag on the record

**Plans**: 5 plans

**Wave 1**

- [x] 13-01-PLAN.md — Wave 0 test scaffolds: update_experiment + compute_drift unit tests + review/lessons/drift/WR CLI tests (RED) (EREV-01/02/03)

**Wave 2** *(blocked on 13-01; 13-02 ∥ 13-03 parallel — no file overlap)*

- [x] 13-02-PLAN.md — update_experiment() in-place overwrite write path + tightened D-13 guard (CR-01, WR-04)
- [x] 13-03-PLAN.md — experiment_drift.py: compute_drift + DRIFT_THRESHOLD pure compute (EREV-03)

**Wave 3** *(blocked on 13-02 + 13-03)*

- [x] 13-04-PLAN.md — CLI review + lessons commands + shared helpers + __init__ re-exports + WR-01/02/03 fixes (EREV-01/02)

**Wave 4** *(blocked on 13-04 — cli.py overlap)*

- [x] 13-05-PLAN.md — CLI drift command (persist + idempotent clear) + experiment list enrichment + phase gate (EREV-03/02)

### Phase 14: Live Experiment Capture

**Goal**: An eval run inside a live Hermes session is captured automatically as an `ExperimentRecord`
**Depends on**: Phase 10, **v1.1 Phase 6 & Phase 7** (shared plugin + turn capture) — cross-milestone dependency
**Requirements**: ECAP-01
**Success Criteria** (what must be TRUE):

  1. Running an evaluation inside a live Hermes session produces an `ExperimentRecord` via the shared plugin hooks
  2. A live-captured experiment record carries the same metadata/outcome structure as a deliberately-logged one

**Plans**: TBD

### Phase 15: Analysis Export & Practice-Project Integration

**Goal**: Experiment data is exportable for analysis and the practice project writes runs directly into Kajiba
**Depends on**: Phase 11, Phase 13 (Phase 14 only for live-captured runs)
**Requirements**: EEXP-01, EEXP-02
**Success Criteria** (what must be TRUE):

  1. User can export experiment records in an analysis-oriented format distinct from the community fine-tuning export
  2. The Nemotron/Qwen/Gemma practice-project workflow writes its evaluation runs directly into Kajiba experiment records end-to-end

**Plans**: TBD

## Progress

**Execution Order:**

Two parallel tracks share a foundation. Execute by dependency, not strict numeric order:

- **v1.1 (coding pipeline):** 6 -> 7 -> 8 -> 9
- **v1.2 (experiment logging):** 10 -> (11 ∥ 12) -> 13 -> 15; and 14 after {10, v1.1 Phase 6, v1.1 Phase 7}
- **Shared foundation:** Phases 6–7 serve both coding-session capture and v1.2 live capture (Phase 14).
- **Recommended start for v1.2:** Phase 10 (schema foundation) — fully independent of v1.1.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Privacy Foundation | v1.0 | 3/3 | Complete | 2026-03-31 |
| 2. Data Quality & Transparency | v1.0 | 3/3 | Complete | 2026-03-31 |
| 3. Dataset Publishing | v1.0 | 2/2 | Complete | 2026-03-31 |
| 4. Contribution Modes | v1.0 | 3/3 | Complete | 2026-04-01 |
| 5. Consumer Experience | v1.0 | 2/2 | Complete | 2026-04-02 |
| 6. Environment + Plugin Foundation | v1.1 | 5/5 | Complete    | 2026-06-05 |
| 7. Turn Capture + Semantic PII Scrubbing | v1.1 | 0/0 | Not started | - |
| 8. HITL Validation + Pipeline Integration | v1.1 | 0/0 | Not started | - |
| 9. Fine-Tune Experiment | v1.1 | 0/0 | Not started | - |
| 10. Experiment Schema Foundation | v1.2 | 3/3 | Complete    | 2026-06-03 |
| 11. Experiment Logging & Private Store | v1.2 | 3/3 | Complete    | 2026-06-04 |
| 12. Eval Scoring & Scrub Tuning | v1.2 | 4/4 | Complete    | 2026-06-04 |
| 13. Reviewer Critique & Drift | v1.2 | 5/5 | Complete    | 2026-06-04 |
| 14. Live Experiment Capture | v1.2 | 0/0 | Not started | - |
| 15. Analysis Export & Practice-Project Integration | v1.2 | 0/0 | Not started | - |
