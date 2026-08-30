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


class LifeArea(StrEnum):
    PROFESSIONAL = "professional"
    LEARNING = "learning"
    BRIEFING = "briefing"
    NUTRITION = "nutrition"
    FITNESS = "fitness"
    WELLBEING = "wellbeing"
    OPERATIONS = "operations"


class LifeAreaOption(BaseModel):
    id: LifeArea
    title: str
    description: str
    agent_id: AgentId


class OnboardingSelection(BaseModel):
    tenant_id: str
    selected_areas: list[LifeArea]
    completed_at: datetime = Field(default_factory=utc_now)


class GoalStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    AWAITING_REVIEW = "awaiting_review"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class TargetType(StrEnum):
    AT_LEAST = "at_least"
    AT_MOST = "at_most"
    EXACT = "exact"
    RANGE = "range"


class TrackingCadence(StrEnum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    END_OF_CYCLE = "end_of_cycle"


class MilestoneKind(StrEnum):
    USER_COMMITMENT = "user_commitment"
    AGENT_DELIVERY = "agent_delivery"


class GoalMetric(BaseModel):
    key: str
    label: str
    unit: str
    target_type: TargetType
    target_value: float | None = None
    minimum_value: float | None = None
    maximum_value: float | None = None
    cadence: TrackingCadence


class GoalMilestone(BaseModel):
    title: str
    success_criteria: str
    due_at: datetime
    kind: MilestoneKind = MilestoneKind.USER_COMMITMENT
    capture_knowledge: bool = False


class GoalRoutine(BaseModel):
    title: str
    cadence: TrackingCadence
    target_count: float
    unit: str = "completion"
    minimum_success: str
    preferred_time: str | None = None


class GoalContractCreate(BaseModel):
    tenant_id: str
    domain: LifeArea
    owner_agent: AgentId
    title: str
    motivation: str
    success_definition: str
    start_at: datetime
    review_at: datetime
    metrics: list[GoalMetric]
    milestones: list[GoalMilestone] = Field(default_factory=list)
    routines: list[GoalRoutine] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    evidence_policy: str = "user_confirmation"
    review_cadence: TrackingCadence = TrackingCadence.END_OF_CYCLE


class GoalContract(GoalContractCreate):
    id: str
    series_id: str
    previous_cycle_id: str | None = None
    cycle_number: int = 1
    version: int = 1
    status: GoalStatus = GoalStatus.DRAFT
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class GoalAmendmentCreate(BaseModel):
    tenant_id: str
    reason: str
    changes: dict[str, Any]


class GoalAmendment(GoalAmendmentCreate):
    id: str
    goal_id: str
    from_version: int
    to_version: int
    effective_at: datetime = Field(default_factory=utc_now)


class PromptResponseType(StrEnum):
    BOOLEAN = "boolean"
    NUMBER = "number"
    TEXT = "text"
    REFLECTION = "reflection"


class TrackingPrompt(BaseModel):
    id: str
    cadence: TrackingCadence
    prompt: str
    response_type: PromptResponseType
    metric_key: str | None = None
    preferred_time: str | None = None
    due_at: datetime | None = None
    agent_id: AgentId | None = None
    active: bool = True


class TrackingProtocol(BaseModel):
    id: str
    tenant_id: str
    goal_id: str
    goal_version: int
    prompts: list[TrackingPrompt]
    generated_by: AgentId = AgentId.OPERATIONS_MANAGER
    approved: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class TrackingProtocolApproval(BaseModel):
    tenant_id: str
    approved: bool = True


class TrackingProtocolUpdate(BaseModel):
    tenant_id: str
    prompts: list[TrackingPrompt]


class GoalActivationResult(BaseModel):
    goal: GoalContract
    proposed_tracking_protocol: TrackingProtocol


class GoalCycleStats(BaseModel):
    commitments_total: int
    commitments_done: int
    completion_rate: float
    by_status: dict[str, int]
    metric_totals: dict[str, float]


class GoalReviewPacket(BaseModel):
    goal: GoalContract
    statistics: GoalCycleStats
    reflection_questions: list[str]
    specialist_agent: AgentId
    status: str = "awaiting_user_review"


class GoalRenewalCreate(BaseModel):
    tenant_id: str
    start_at: datetime
    review_at: datetime
    changes: dict[str, Any] = Field(default_factory=dict)


class CheckInStatus(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    RESPONDED = "responded"
    SKIPPED = "skipped"


class ScheduledCheckIn(BaseModel):
    id: str
    tenant_id: str
    goal_id: str
    protocol_id: str
    prompt_id: str
    agent_id: AgentId
    prompt: str
    due_at: datetime
    status: CheckInStatus = CheckInStatus.PENDING
    created_at: datetime = Field(default_factory=utc_now)


class CheckInStatusUpdate(BaseModel):
    tenant_id: str
    status: CheckInStatus


class ConversationRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class PlanningSessionStatus(StrEnum):
    DISCOVERY = "discovery"
    DRAFT_READY = "draft_ready"
    FINALIZED = "finalized"


class PlanningMessage(BaseModel):
    role: ConversationRole
    content: str
    created_at: datetime = Field(default_factory=utc_now)


class GoalPlanningSessionCreate(BaseModel):
    tenant_id: str
    area: LifeArea


class GoalPlanningSession(BaseModel):
    id: str
    tenant_id: str
    area: LifeArea
    agent_id: AgentId
    status: PlanningSessionStatus = PlanningSessionStatus.DISCOVERY
    messages: list[PlanningMessage] = Field(default_factory=list)
    goal_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PlanningMessageCreate(BaseModel):
    tenant_id: str
    message: str


class PlanningTurn(BaseModel):
    session: GoalPlanningSession
    response: AgentOutput


class GoalPlanningFinalize(BaseModel):
    tenant_id: str
    goal: GoalContractCreate


class KnowledgeRecordCreate(BaseModel):
    tenant_id: str
    goal_id: str | None = None
    studied_at: datetime = Field(default_factory=utc_now)
    source_title: str
    topic: str
    expected_scope: str
    user_summary: str
    probe_questions: list[str] = Field(default_factory=list)
    probe_answers: list[str] = Field(default_factory=list)
    interview_recall: str
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class KnowledgeRecord(KnowledgeRecordCreate):
    id: str
    confirmed: bool = False
    created_at: datetime = Field(default_factory=utc_now)


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
