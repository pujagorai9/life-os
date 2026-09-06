from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


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
    CHIEF_FINANCE_OFFICER = "chief_finance_officer"


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

    @field_validator("due_at", mode="before")
    @classmethod
    def normalize_relative_due_at(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        normalized = value.strip().casefold()
        if normalized == "now":
            return datetime.now().astimezone()
        if normalized == "today":
            local_now = datetime.now().astimezone()
            return local_now.replace(hour=23, minute=59, second=59, microsecond=0)
        return value


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
    FINANCE = "finance"


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
    kind: MilestoneKind = MilestoneKind.USER_COMMITMENT


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
    kind: MilestoneKind = MilestoneKind.USER_COMMITMENT
    input_required: bool | None = None
    active: bool = True

    @model_validator(mode="after")
    def infer_legacy_agent_delivery(self) -> TrackingPrompt:
        """Keep older saved protocols safe after delivery kinds were introduced."""
        if self.prompt.lstrip().startswith("Prepare and deliver:"):
            self.kind = MilestoneKind.AGENT_DELIVERY
        return self


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


class CheckInOutcome(StrEnum):
    DONE = "done"
    PARTIAL = "partial"


class ScheduledCheckIn(BaseModel):
    id: str
    tenant_id: str
    goal_id: str
    protocol_id: str
    prompt_id: str
    agent_id: AgentId
    prompt: str
    due_at: datetime
    kind: MilestoneKind = MilestoneKind.USER_COMMITMENT
    input_required: bool | None = None
    status: CheckInStatus = CheckInStatus.PENDING
    outcome: CheckInOutcome | None = None
    completed_at: datetime | None = None
    status_updated_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def infer_legacy_agent_delivery(self) -> ScheduledCheckIn:
        """Recognize automatic deliveries already stored before this field existed."""
        if self.prompt.lstrip().startswith("Prepare and deliver:"):
            self.kind = MilestoneKind.AGENT_DELIVERY
        return self


class CheckInStatusUpdate(BaseModel):
    tenant_id: str
    status: CheckInStatus
    outcome: CheckInOutcome | None = None


class PhotoAnalysis(BaseModel):
    summary: str
    observations: list[str] = Field(default_factory=list)
    estimated_calories: float | None = None
    estimated_protein_g: float | None = None
    estimated_carbohydrates_g: float | None = None
    estimated_fat_g: float | None = None
    estimated_fiber_g: float | None = None
    estimated_calcium_mg: float | None = None
    confidence: float = Field(ge=0, le=1)
    caveats: list[str] = Field(default_factory=list)


class NutritionAnalysisRequest(BaseModel):
    tenant_id: str
    description: str = Field(min_length=1, max_length=2000)


class NutritionInputImage(BaseModel):
    media_type: str
    data: str = Field(min_length=1)


class NutritionConversationRequest(BaseModel):
    tenant_id: str
    description: str = Field(default="", max_length=4000)
    images: list[NutritionInputImage] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def require_text_or_image(self) -> NutritionConversationRequest:
        if not self.description.strip() and not self.images:
            raise ValueError("Add a description or at least one meal image")
        return self


class PhotoAnalysisStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    COMPLETED = "completed"
    UNAVAILABLE = "unavailable"


class CheckInPhoto(BaseModel):
    id: str
    tenant_id: str
    check_in_id: str
    agent_id: AgentId
    storage_key: str
    media_type: str
    size_bytes: int
    sha256: str
    analysis_status: PhotoAnalysisStatus = PhotoAnalysisStatus.NOT_REQUESTED
    analysis: PhotoAnalysis | None = None
    created_at: datetime = Field(default_factory=utc_now)


class NutritionConversationResult(BaseModel):
    photos: list[CheckInPhoto]
    analysis: PhotoAnalysis


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


class GoalPlanningCompletion(BaseModel):
    goal: GoalContract
    completed_session: GoalPlanningSession
    chief_of_staff_message: str
    next_session: GoalPlanningSession | None = None
    remaining_areas: list[LifeArea] = Field(default_factory=list)
    onboarding_complete: bool = False


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


class BriefingDocument(BaseModel):
    day: date
    title: str
    markdown: str
    source_file: str


class AppointmentSyncItem(BaseModel):
    action: str
    outcome: str
    summary: str
    event_date: date | None = None
    event_time: str | None = None
    exception: bool = False


class AppointmentSyncDocument(BaseModel):
    day: date
    processed_at: datetime
    cutoff_at: datetime | None = None
    emails_processed: int
    events_created: int
    events_updated: int
    events_cancelled: int
    existing_events_matched: int
    items: list[AppointmentSyncItem] = Field(default_factory=list)


class FinanceEmailResultCreate(BaseModel):
    tenant_id: str
    source_message_id: str
    source_account_id: str = "primary"
    source_account_email: str | None = None
    household_member: str | None = None
    message_at: datetime
    outcome: str
    merchant: str | None = None
    category: str | None = None
    amount: float | None = Field(default=None, ge=0)
    currency: str | None = None
    transaction_at: datetime | None = None
    confidence: float = Field(default=1, ge=0, le=1)
    summary: str | None = None

    @model_validator(mode="after")
    def validate_transaction_fields(self) -> FinanceEmailResultCreate:
        allowed = {"purchase", "refund", "not_purchase", "ambiguous"}
        if self.outcome not in allowed:
            raise ValueError(f"outcome must be one of {sorted(allowed)}")
        if self.outcome in {"purchase", "refund"}:
            if not self.merchant or not self.category:
                raise ValueError("purchase and refund results require merchant and category")
            if self.amount is None or not self.currency or self.transaction_at is None:
                raise ValueError(
                    "purchase and refund results require amount, currency, and transaction_at"
                )
        return self


class ExpenseRecord(BaseModel):
    id: str
    tenant_id: str
    source_message_id: str
    source_account_id: str = "primary"
    source_account_email: str | None = None
    household_member: str | None = None
    transaction_at: datetime
    merchant: str
    category: str
    amount: float = Field(ge=0)
    currency: str
    kind: str = "purchase"
    confidence: float = Field(ge=0, le=1)
    created_at: datetime = Field(default_factory=utc_now)


class FinanceCategoryTotal(BaseModel):
    category: str
    amount: float


class FinanceCurrencySummary(BaseModel):
    currency: str
    total_spent: float
    total_refunded: float
    net_spent: float
    categories: list[FinanceCategoryTotal] = Field(default_factory=list)


class FinanceDailyReport(BaseModel):
    day: date
    purchase_count: int
    processed_email_count: int
    summaries: list[FinanceCurrencySummary] = Field(default_factory=list)
    transactions: list[ExpenseRecord] = Field(default_factory=list)


class FinanceEmailAccount(BaseModel):
    account_id: str
    email: str
    member_name: str
    connected_at: datetime
    scopes: list[str] = Field(default_factory=list)


class AppleHealthWorkout(BaseModel):
    workout_id: str | None = None
    activity_type: str = Field(min_length=1, max_length=120)
    started_at: datetime
    duration_minutes: float = Field(ge=0)
    active_energy_kcal: float | None = Field(default=None, ge=0)


class AppleHealthDailyImport(BaseModel):
    tenant_id: str
    day: date
    timezone: str = Field(min_length=1, max_length=100)
    active_energy_kcal: float | None = Field(default=None, ge=0)
    move_goal_kcal: float | None = Field(default=None, gt=0)
    exercise_minutes: float | None = Field(default=None, ge=0)
    exercise_goal_minutes: float = Field(default=30, gt=0)
    stand_hours: float | None = Field(default=None, ge=0)
    stand_minutes: float | None = Field(default=None, ge=0)
    stand_goal_hours: float = Field(default=12, gt=0)
    cardio_minutes: float | None = Field(default=None, ge=0)
    strength_minutes: float | None = Field(default=None, ge=0)
    workouts: list[AppleHealthWorkout] = Field(default_factory=list, max_length=100)

    @field_validator("day", mode="before")
    @classmethod
    def normalize_shortcuts_date(cls, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str) and "T" in value:
            return value[:10]
        return value

    @field_validator(
        "active_energy_kcal",
        "move_goal_kcal",
        "exercise_minutes",
        "exercise_goal_minutes",
        "stand_hours",
        "stand_minutes",
        "stand_goal_hours",
        "cardio_minutes",
        "strength_minutes",
        mode="before",
    )
    @classmethod
    def normalize_shortcuts_measurement(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", value)
        return float(match.group(0).replace(",", "")) if match else value


class AppleHealthImportResult(BaseModel):
    accepted: bool = True
    created_events: int
    updated_events: int
    unchanged_events: int
    imported_metrics: list[str]


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
