# Kajiba Dual-Use Roadmap: Coding Sessions + Model Experiment Logging

**Status:** Draft  
**Created:** 2026-06-03  
**Owner:** CuervoDoesIt  
**Related Projects:** AEON-7 model deployments, Hermes local model orchestration practice project

---

## 1. Executive Summary

Kajiba was originally designed as a privacy-first, model-agnostic pipeline for collecting real-world AI-assisted coding sessions to create high-quality fine-tuning datasets. 

This roadmap proposes evolving Kajiba into a **dual-use system** that continues to serve its original purpose while also becoming the canonical structured logging layer for **local model experimentation and evaluation**.

The new capability will allow systematic capture of:
- Local model outputs on specific tasks
- Reviewer model critiques (e.g. Grok reviewing Nemotron/Qwen/Gemma outputs)
- Quality assessments and drift detection
- Lessons learned that can later inform routing logic, prompt engineering, or fine-tuning data

The goal is to make Kajiba the single source of truth for both "production coding data" and "experimental model behavior data."

---

## 2. Dual-Use Vision

| Dimension                    | Original Use Case                          | New Use Case (Experiment Logging)                  | Overlap / Shared Needs                     |
|-----------------------------|--------------------------------------------|----------------------------------------------------|--------------------------------------------|
| Primary Data                | Developer + AI coding trajectories         | Local model outputs + reviewer critiques           | Structured turns, tool calls, metadata     |
| Goal                        | High-quality fine-tuning data              | Traceable model evaluation + lessons learned       | Quality scoring, PII scrubbing             |
| Record Type                 | Coding session                             | Model experiment / evaluation run                  | Common base schema                         |
| Reviewer Involvement        | Minimal                                    | Heavy (Grok as overseer)                           | Optional reviewer fields                   |
| Time Sensitivity            | Real-time collection                       | Deliberate, review-heavy                           | Same pipeline                              |
| Output Consumers            | Fine-tuning datasets                       | Routing logic, model comparison, drift tracking    | Both benefit from rich metadata            |

---

## 3. Current State Analysis

### Strengths
- Excellent Pydantic v2 schema foundation (`KajibaRecord`, `ConversationTurn`, `ToolCall`, etc.)
- Strong PII scrubbing layer
- Hermes integration already exists (`hermes_integration.py`)
- Clean separation of concerns (collector, scrubber, scorer, cli)
- Hardware and model metadata already captured

### Gaps for Experiment Logging
- No native concept of "experiment" or "evaluation run"
- No fields for reviewer model, critique, or lessons learned
- Quality scoring is currently tuned for coding sessions, not model output evaluation
- No clear way to tag or filter "experiment" records vs "production" records
- CLI is oriented around session collection, not experiment logging

---

## 4. Proposed Changes (Detailed)

### 4.1 Schema Extensions

#### New Record Type: `ExperimentRecord`

We should introduce a new top-level record type (or a subtype) alongside `KajibaRecord`.

**Suggested new fields** (add to `src/kajiba/schema.py`):

```python
class ExperimentMetadata(BaseModel):
    experiment_id: str
    experiment_type: Literal["model_evaluation", "routing_test", "quality_drift", "prompt_ablation"]
    local_model: ModelMetadata
    reviewer_model: Optional[ModelMetadata] = None
    task_category: str  # e.g. "game_dev", "code_generation", "creative_writing"
    task_description: str
    started_at: datetime
    completed_at: Optional[datetime]

class ExperimentOutcome(BaseModel):
    local_model_output: str
    reviewer_critique: Optional[str] = None
    quality_score: float
    drift_detected: bool
    lessons_learned: list[str]
    recommended_action: Optional[str]  # "use_as_is", "needs_fine_tune", "route_to_grok", etc.
```

We may also want to extend `ConversationTurn` with an optional `reviewer_turn` field.

### 4.2 New CLI Commands (Proposed)

- `kajiba experiment start`
- `kajiba experiment log`
- `kajiba experiment review` (for Grok to add critiques)
- `kajiba experiment list --type evaluation`
- `kajiba export --format experiment-dataset`

### 4.3 Data Flow Changes

1. **Collection Phase** — Allow both normal sessions and experiment records to flow through the same collector.
2. **Scrubber** — Keep aggressive PII scrubbing, but make some fields (like model names and hardware) optionally less redacted for experiment records.
3. **Scorer** — Create a second scoring path or extend the existing scorer to handle experiment-specific quality signals.
4. **Staging/Review** — Add a dedicated review workflow for experiment records (especially when a reviewer model has already provided critique).

### 4.4 Tagging & Filtering Strategy

Introduce a top-level `record_kind` field:

- `record_kind: "coding_session"` (original use)
- `record_kind: "model_experiment"` (new use)

This allows clean separation while keeping a single pipeline.

---

## 5. Implementation Roadmap

### Phase 1: Schema & Core Types (High Priority)
- Add `ExperimentMetadata` and `ExperimentOutcome` models
- Add `record_kind` discriminator
- Update `KajibaRecord` to support both kinds

### Phase 2: CLI & Collection Layer
- Implement `kajiba experiment` command group
- Create experiment logging flow that can be called programmatically or via CLI

### Phase 3: Review & Critique Layer
- Support attaching reviewer critiques (especially from Grok)
- Add `lessons_learned` collection interface

### Phase 4: Export & Downstream Use
- Export formats suitable for both fine-tuning and experiment analysis
- Possibly a lightweight dashboard or query interface for experiment records

### Phase 5: Integration with Practice Project
- Make the Nemotron/Qwen/Gemma testing workflow write directly into Kajiba experiment records

---

## 6. Open Questions

1. Should experiment records live in the same database/filesystem structure as coding sessions, or should there be a separate namespace?
2. How much of the existing scrubbing logic should be reused vs extended for experiment data?
3. Do we want to support multi-turn experiment conversations (local model ↔ Grok reviewer)?
4. Should `lessons_learned` be free-form text or structured (e.g. categories like "coherence", "creativity", "hallucination")?

---

## 7. Success Metrics

- Ability to run a full Nemotron evaluation session and have it automatically logged as a structured experiment record
- Clear separation between coding session data and experiment data when exporting
- Reviewer critiques (from Grok) are captured alongside local model outputs
- Lessons learned are queryable and usable for future routing decisions

---

**Next Actions for the secondary Hermes instance:**
- Review this document
- Propose concrete schema changes (with code diffs if possible)
- Implement Phase 1 changes
- Report back with progress and any blockers

---

This document is intentionally verbose and structured so it can serve as the primary reference for the parallel Kajiba work.