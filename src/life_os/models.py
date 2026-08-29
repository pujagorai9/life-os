from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentId(StrEnum):
    CHIEF_OF_STAFF = "chief_of_staff"
    CAREER_COACH = "career_coach"
    KNOWLEDGE_GURU = "knowledge_guru"
    BRIEFING_INTERN = "briefing_intern"
    NUTRITION_COACH = "nutrition_coach"
    FITNESS_COACH = "fitness_coach"
    INNER_WELLBEING_GURU = "inner_wellbeing_guru"
    OPERATIONS_MANAGER = "operations_manager"
    CHIEF_ACCOUNTABILITY_OFFICER = "chief_accountability_officer"
    HEAD_OF_PERFORMANCE_ANALYTICS = "head_of_performance_analytics"
    CHIEF_ARCHIVIST = "chief_archivist"


class AgentDefinition(BaseModel):
    id: AgentId
    name: str
    domain: str
    purpose: str
    instructions: str
    can_propose_external_actions: bool = False
    private_by_default: bool = False


class ProposedAction(BaseModel):
    title: str
    domain: str
    reason: str | None = None
    due_at: datetime | None = None
    requires_approval: bool = True


class AgentOutput(BaseModel):
    agent_id: AgentId
    summary: str
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CommitmentStatus(StrEnum):
    PLANNED = "planned"
    DONE = "done"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    RESCHEDULED = "rescheduled"


class CommitmentCreate(BaseModel):
    tenant_id: str
    domain: str
    title: str
    minimum_success: str
    due_at: datetime | None = None
    goal_id: str | None = None
    evidence_policy: str = "user_confirmation"
    reminder_policy: str = "default"


class Commitment(CommitmentCreate):
    id: str
    status: CommitmentStatus = CommitmentStatus.PLANNED
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ProgressEventCreate(BaseModel):
    tenant_id: str
    domain: str
    metric: str
    value: float
    unit: str
    source: str
    confidence: float = Field(ge=0, le=1)
    occurred_at: datetime = Field(default_factory=utc_now)
    goal_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProgressEvent(ProgressEventCreate):
    id: str


class MemoryCreate(BaseModel):
    tenant_id: str
    domain: str
    fact: str
    source: str
    confidence: float = Field(ge=0, le=1)
    expires_at: datetime | None = None


class Memory(MemoryCreate):
    id: str
    confirmed: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class Goal(BaseModel):
    id: str
    domain: str
    title: str
    status: str = "active"


class SourceConfig(BaseModel):
    id: str
    kind: str
    access: str
    enabled: bool = True


class UserPreferences(BaseModel):
    display_name: str = "CEO"
    timezone: str = "UTC"
    quiet_hours_start: str = "21:00"
    quiet_hours_end: str = "07:00"


class PrivacyPreferences(BaseModel):
    share_journal_content: bool = False
    share_health_details_across_domains: bool = False
    allow_external_actions_without_approval: bool = False


class Profile(BaseModel):
    user: UserPreferences = Field(default_factory=UserPreferences)
    privacy: PrivacyPreferences = Field(default_factory=PrivacyPreferences)
    enabled_agents: list[AgentId] = Field(default_factory=lambda: list(AgentId))
    goals: list[Goal] = Field(default_factory=list)
    sources: list[SourceConfig] = Field(default_factory=list)


class ChatRequest(BaseModel):
    tenant_id: str
    message: str
    agent_id: AgentId | None = None


class ProgressSummary(BaseModel):
    tenant_id: str
    commitments_total: int
    commitments_done: int
    completion_rate: float
    by_status: dict[str, int]
    event_totals: dict[str, float]
