# Roadmap: Kajiba

## Milestones

- ✅ **v1.0 MVP** -- Phases 1-5 (shipped 2026-04-02)
- 🚧 **v1.1 Hermes Pipeline Validation** -- Phases 6-9 (in progress)

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

- [ ] **Phase 6: Environment + Plugin Foundation** - Working Hermes dev environment and plugin scaffold that receives hook events
- [ ] **Phase 7: Turn Capture + Semantic PII Scrubbing** - Real session data flowing through capture and semantic privacy layers
- [ ] **Phase 8: HITL Validation + Pipeline Integration** - Manual review workflow and end-to-end pipeline smoke test on real data
- [ ] **Phase 9: Fine-Tune Experiment** - QLoRA fine-tune of a local 3B model on Kajiba-collected data as milestone gate

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
**Plans**: TBD

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
**Plans**: TBD

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

## Progress

**Execution Order:**
Phases execute in numeric order: 6 -> 7 -> 8 -> 9

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Privacy Foundation | v1.0 | 3/3 | Complete | 2026-03-31 |
| 2. Data Quality & Transparency | v1.0 | 3/3 | Complete | 2026-03-31 |
| 3. Dataset Publishing | v1.0 | 2/2 | Complete | 2026-03-31 |
| 4. Contribution Modes | v1.0 | 3/3 | Complete | 2026-04-01 |
| 5. Consumer Experience | v1.0 | 2/2 | Complete | 2026-04-02 |
| 6. Environment + Plugin Foundation | v1.1 | 0/0 | Not started | - |
| 7. Turn Capture + Semantic PII Scrubbing | v1.1 | 0/0 | Not started | - |
| 8. HITL Validation + Pipeline Integration | v1.1 | 0/0 | Not started | - |
| 9. Fine-Tune Experiment | v1.1 | 0/0 | Not started | - |
