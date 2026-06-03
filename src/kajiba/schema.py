"""Kajiba record schema — Pydantic v2 models for the community data pipeline.

This module defines the complete record schema from the Kajiba specification.
Every field, controlled vocabulary term, and validation rule is implemented here.
"""

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "0.2.0"

# Controlled vocabularies — both as tuples (iterable) and Literal unions (type-safe)

OUTCOME_TAGS = (
    "task_completed",
    "task_partial",
    "task_failed",
    "hallucination",
    "minor_hallucination",
    "tool_call_correct",
    "tool_call_failed",
    "tool_not_found",
    "wrong_format",
    "context_overflow",
    "slow_response",
    "perfect",
    "safety_issue",
    "refusal_appropriate",
    "refusal_inappropriate",
    "loop_detected",
    "instruction_following",
    "instruction_drift",
)

OutcomeTagType = Literal[
    "task_completed",
    "task_partial",
    "task_failed",
    "hallucination",
    "minor_hallucination",
    "tool_call_correct",
    "tool_call_failed",
    "tool_not_found",
    "wrong_format",
    "context_overflow",
    "slow_response",
    "perfect",
    "safety_issue",
    "refusal_appropriate",
    "refusal_inappropriate",
    "loop_detected",
    "instruction_following",
    "instruction_drift",
]

PAIN_POINT_CATEGORIES = (
    "tool_call_failure",
    "tool_call_wrong_tool",
    "hallucination_factual",
    "hallucination_tool",
    "context_loss",
    "format_error",
    "reasoning_error",
    "performance_issue",
    "safety_concern",
    "ux_friction",
    "skill_gap",
    "other",
)

PainPointCategoryType = Literal[
    "tool_call_failure",
    "tool_call_wrong_tool",
    "hallucination_factual",
    "hallucination_tool",
    "context_loss",
    "format_error",
    "reasoning_error",
    "performance_issue",
    "safety_concern",
    "ux_friction",
    "skill_gap",
    "other",
]

SeverityType = Literal["low", "medium", "high", "critical"]

ConsentLevelType = Literal["trajectory_only", "metadata_only", "full", "anonymous"]

ToolStatusType = Literal["success", "failure", "timeout", "error"]

DifficultyEstimateType = Literal["trivial", "easy", "medium", "hard", "expert"]

RecordTypeType = Literal["task_trajectory", "pain_point", "benchmark_run"]

ProviderType = Literal["ollama", "vllm", "sglang", "llamacpp", "openrouter", "custom"]

TurnRoleType = Literal["human", "gpt"]

RECORD_KINDS = ("coding_session", "model_experiment")
RecordKindType = Literal["coding_session", "model_experiment"]

EXPERIMENT_TYPES = ("model_evaluation", "routing_test", "quality_drift", "prompt_ablation")
ExperimentTypeType = Literal["model_evaluation", "routing_test", "quality_drift", "prompt_ablation"]

RECOMMENDED_ACTIONS = ("use_as_is", "needs_fine_tune", "route_to_reviewer", "discard")
RecommendedActionType = Literal["use_as_is", "needs_fine_tune", "route_to_reviewer", "discard"]

# ---------------------------------------------------------------------------
# Nested models
# ---------------------------------------------------------------------------


class ToolCall(BaseModel):
    """A single tool invocation within a conversation turn."""

    tool_name: str
    tool_input: str = ""
    tool_output: str = ""
    tool_status: ToolStatusType
    latency_ms: Optional[int] = None


class ConversationTurn(BaseModel):
    """A single turn in the conversation trajectory."""

    from_: TurnRoleType = Field(alias="from")
    value: str
    tool_calls: Optional[list[ToolCall]] = None
    token_count: Optional[int] = None
    generation_latency_ms: Optional[int] = None

    model_config = {"populate_by_name": True}


class Trajectory(BaseModel):
    """The conversation trajectory — core of every task_trajectory record."""

    format: str = "sharegpt_extended"
    conversations: list[ConversationTurn]
    turn_count: int = 0
    total_tool_calls: int = 0
    successful_tool_calls: int = 0
    failed_tool_calls: int = 0

    @field_validator("conversations")
    @classmethod
    def conversations_not_empty(cls, v: list[ConversationTurn]) -> list[ConversationTurn]:
        """Trajectory must have at least one turn."""
        if not v:
            raise ValueError("conversations must not be empty")
        return v


class ModelMetadata(BaseModel):
    """Metadata about the model used for inference."""

    model_name: str
    model_family: Optional[str] = None
    parameter_count: Optional[str] = None
    quantization: Optional[str] = None
    context_window: Optional[int] = None
    context_used: Optional[int] = None
    provider: Optional[ProviderType] = None
    is_local: Optional[bool] = None
    model_hash: Optional[str] = None


class HardwareProfile(BaseModel):
    """Hardware profile of the machine running inference."""

    gpu_name: Optional[str] = None
    gpu_vram_gb: Optional[int] = None
    gpu_count: Optional[int] = None
    cpu_name: Optional[str] = None
    ram_gb: Optional[int] = None
    os: Optional[str] = None
    inference_backend: Optional[str] = None
    cuda_version: Optional[str] = None


class OutcomeSignals(BaseModel):
    """User-provided outcome signals for the session."""

    user_rating: int = Field(ge=1, le=5)
    outcome_tags: list[OutcomeTagType] = Field(default_factory=list)
    user_comment: Optional[str] = None
    task_category: Optional[str] = None
    difficulty_estimate: Optional[DifficultyEstimateType] = None

    @field_validator("outcome_tags")
    @classmethod
    def validate_outcome_tags(cls, v: list[str]) -> list[str]:
        """All outcome tags must come from the controlled vocabulary."""
        for tag in v:
            if tag not in OUTCOME_TAGS:
                raise ValueError(f"Unknown outcome tag: {tag!r}. Must be one of {OUTCOME_TAGS}")
        return v


class PainPoint(BaseModel):
    """A reported pain point during the session."""

    category: PainPointCategoryType
    severity: SeverityType = "medium"
    description: str
    turn_index: Optional[int] = None
    reproducible: Optional[bool] = None


class ScrubLog(BaseModel):
    """Log of what was redacted during PII scrubbing."""

    file_paths_redacted: int = 0
    potential_names_redacted: int = 0
    api_keys_redacted: int = 0
    emails_redacted: int = 0
    network_redacted: int = 0
    phone_redacted: int = 0
    crypto_redacted: int = 0
    connection_strings_redacted: int = 0
    items_flagged: int = 0


class QualityMetadata(BaseModel):
    """Stored quality assessment for a record.

    Persisted at submit time so history/stats can read scores
    without recomputation.
    """

    quality_tier: str  # "gold", "silver", "bronze", "review_needed"
    composite_score: float = Field(ge=0.0, le=1.0)
    sub_scores: dict[str, float]
    scored_at: datetime


class SubmissionMetadata(BaseModel):
    """Metadata about the submission itself."""

    hermes_version: Optional[str] = None
    kajiba_plugin_version: str = SCHEMA_VERSION
    contributor_id: Optional[str] = None
    consent_level: ConsentLevelType = "full"
    pii_scrub_version: str = SCHEMA_VERSION
    scrub_log: Optional[ScrubLog] = None


# ---------------------------------------------------------------------------
# Top-level record
# ---------------------------------------------------------------------------


class RecordBase(BaseModel):
    """Shared base for every top-level Kajiba record kind.

    Holds the identity, versioning, and runtime-context fields common to
    both coding-session records (KajibaRecord) and model-experiment records
    (ExperimentRecord). The record_kind discriminator defaults to
    "coding_session" so legacy dicts that omit it remain valid.
    """

    schema_version: str = SCHEMA_VERSION
    record_id: Optional[str] = None
    submission_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    record_kind: RecordKindType = "coding_session"
    model: Optional[ModelMetadata] = None
    hardware: Optional[HardwareProfile] = None
    submission: Optional[SubmissionMetadata] = None

    model_config = {"populate_by_name": True}


class KajibaRecord(RecordBase):
    """Top-level Kajiba record — one task attempt, fully described.

    This is the primary data unit in the Kajiba pipeline. Every record
    captures everything about one user-agent interaction from prompt
    to completion. Identity, versioning, and runtime-context fields are
    inherited from RecordBase.
    """

    record_type: RecordTypeType = "task_trajectory"
    trajectory: Trajectory
    outcome: Optional[OutcomeSignals] = None
    pain_points: Optional[list[PainPoint]] = None
    quality: Optional[QualityMetadata] = None

    @model_validator(mode="after")
    def validate_turn_count(self) -> "KajibaRecord":
        """turn_count must match the actual number of conversations."""
        actual = len(self.trajectory.conversations)
        if self.trajectory.turn_count != 0 and self.trajectory.turn_count != actual:
            raise ValueError(
                f"turn_count ({self.trajectory.turn_count}) does not match "
                f"actual conversation count ({actual})"
            )
        return self

    @model_validator(mode="after")
    def validate_tool_call_counts(self) -> "KajibaRecord":
        """successful + failed tool calls must equal total."""
        traj = self.trajectory
        if traj.total_tool_calls != 0 or traj.successful_tool_calls != 0 or traj.failed_tool_calls != 0:
            if traj.successful_tool_calls + traj.failed_tool_calls != traj.total_tool_calls:
                raise ValueError(
                    f"successful_tool_calls ({traj.successful_tool_calls}) + "
                    f"failed_tool_calls ({traj.failed_tool_calls}) != "
                    f"total_tool_calls ({traj.total_tool_calls})"
                )
        return self

    def to_sharegpt(self) -> dict:
        """Strip the record down to vanilla ShareGPT format.

        Returns:
            Dict with a 'conversations' key containing list of
            {'from': role, 'value': text} dicts.
        """
        return {
            "conversations": [
                {"from": turn.from_, "value": turn.value}
                for turn in self.trajectory.conversations
            ]
        }

    def to_dpo_candidate(self) -> dict:
        """Return the prompt + response for DPO pairing.

        Returns:
            Dict with 'prompt' (first human turn) and 'response'
            (concatenated gpt turns).
        """
        prompt = ""
        responses: list[str] = []
        for turn in self.trajectory.conversations:
            if turn.from_ == "human" and not prompt:
                prompt = turn.value
            elif turn.from_ == "gpt":
                responses.append(turn.value)
        return {
            "prompt": prompt,
            "response": "\n".join(responses),
        }

    def compute_record_id(self) -> str:
        """Generate a deterministic SHA-256 hash from the trajectory content.

        The record_id is a content-addressable identifier: same trajectory
        content always produces the same ID.

        Returns:
            String in the format 'kajiba_<first 12 hex chars>'.
        """
        content = json.dumps(
            [
                {"from": t.from_, "value": t.value}
                for t in self.trajectory.conversations
            ],
            sort_keys=True,
            ensure_ascii=True,
        )
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        self.record_id = f"kajiba_{digest[:12]}"
        return self.record_id

    def compute_submission_hash(self) -> str:
        """Compute a content-addressable dedup key for the full record.

        Includes trajectory content, model info, and outcome signals
        to detect duplicate submissions.

        Returns:
            String in the format 'sha256:<hex digest>'.
        """
        parts = {
            "trajectory": [
                {"from": t.from_, "value": t.value}
                for t in self.trajectory.conversations
            ],
            "model_name": self.model.model_name if self.model else None,
            "rating": self.outcome.user_rating if self.outcome else None,
            "tags": sorted(self.outcome.outcome_tags) if self.outcome else None,
        }
        content = json.dumps(parts, sort_keys=True, ensure_ascii=True)
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        self.submission_hash = f"sha256:{digest}"
        return self.submission_hash


# ---------------------------------------------------------------------------
# Experiment record family
# ---------------------------------------------------------------------------


class ExperimentMetadata(BaseModel):
    """Identity metadata for a model-experiment record."""

    experiment_id: str
    experiment_type: ExperimentTypeType
    local_model: ModelMetadata
    reviewer_model: Optional[ModelMetadata] = None
    task_category: str
    task_description: str
    started_at: datetime
    completed_at: Optional[datetime] = None


class ExperimentOutcome(BaseModel):
    """Flat outcome signals for a model-experiment record."""

    local_model_output: str
    reviewer_critique: Optional[str] = None
    eval_score: float = Field(ge=0.0, le=1.0)
    drift_flag: bool = False
    lessons_learned: list[str] = Field(default_factory=list)
    recommended_action: Optional[RecommendedActionType] = None


class ExperimentRecord(RecordBase):
    """Top-level model-experiment record — one local-model evaluation attempt.

    Used by the dual-use eval-logging milestone. Carries richer model and
    hardware metadata than community records and is private/no-publish.
    Inherits identity, versioning, and runtime-context fields from RecordBase.
    """

    record_kind: RecordKindType = "model_experiment"
    experiment: ExperimentMetadata
    outcome: ExperimentOutcome
    trajectory: Optional[Trajectory] = None

    def compute_record_id(self) -> str:
        """Generate a deterministic SHA-256 hash from the experiment identity.

        The record_id is content-addressable over the experiment-identity
        payload: same experiment identity always produces the same ID.

        Returns:
            String in the format 'kajiba_exp_<first 12 hex chars>'.
        """
        content = json.dumps(
            {
                "experiment_id": self.experiment.experiment_id,
                "task_description": self.experiment.task_description,
                "local_model_name": self.experiment.local_model.model_name,
                "local_model_output": self.outcome.local_model_output,
                "started_at": self.experiment.started_at.isoformat(),
            },
            sort_keys=True,
            ensure_ascii=True,
        )
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        self.record_id = f"kajiba_exp_{digest[:12]}"
        return self.record_id

    def compute_submission_hash(self) -> str:
        """Compute a content-addressable local-dedup key for the experiment.

        Hashes the same experiment-identity payload as compute_record_id().
        Purpose is local de-duplication only — experiment records never
        publish to the community dataset.

        Returns:
            String in the format 'sha256:<hex digest>'.
        """
        content = json.dumps(
            {
                "experiment_id": self.experiment.experiment_id,
                "task_description": self.experiment.task_description,
                "local_model_name": self.experiment.local_model.model_name,
                "local_model_output": self.outcome.local_model_output,
                "started_at": self.experiment.started_at.isoformat(),
            },
            sort_keys=True,
            ensure_ascii=True,
        )
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        self.submission_hash = f"sha256:{digest}"
        return self.submission_hash


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_record(data: dict) -> KajibaRecord:
    """Parse raw JSON data into a validated KajibaRecord.

    Args:
        data: Dictionary of record data (e.g. from json.loads).

    Returns:
        A validated KajibaRecord instance.

    Raises:
        pydantic.ValidationError: If the data fails schema validation.
    """
    return KajibaRecord.model_validate(data)


def load_record(data: dict) -> Union[KajibaRecord, ExperimentRecord]:
    """Dispatch raw JSON data to the correct record model by record_kind.

    Reads ``record_kind`` and routes to the matching model. Legacy dicts
    that omit ``record_kind`` default to ``coding_session`` (a KajibaRecord),
    preserving back-compat without a discriminated union.

    Args:
        data: Dictionary of record data (e.g. from json.loads).

    Returns:
        An ExperimentRecord for ``model_experiment`` data, otherwise a
        validated KajibaRecord.

    Raises:
        pydantic.ValidationError: If the data fails schema validation.
    """
    kind = data.get("record_kind", "coding_session")
    if kind == "model_experiment":
        return ExperimentRecord.model_validate(data)
    return KajibaRecord.model_validate(data)
