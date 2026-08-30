from __future__ import annotations

import uuid
import calendar
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from life_os.models import (
    AgentId,
    CommitmentStatus,
    GoalContract,
    GoalContractCreate,
    GoalCycleStats,
    GoalReviewPacket,
    GoalPlanningCompletion,
    GoalPlanningSession,
    GoalStatus,
    LifeArea,
    LifeAreaOption,
    MilestoneKind,
    PlanningMessage,
    ConversationRole,
    PlanningSessionStatus,
    PromptResponseType,
    ScheduledCheckIn,
    TrackingCadence,
    TrackingPrompt,
    TrackingProtocol,
    utc_now,
)
from life_os.store import LifeOSStore


AREA_OPTIONS: tuple[LifeAreaOption, ...] = (
    LifeAreaOption(
        id=LifeArea.PROFESSIONAL,
        title="Career & Professional Growth",
        description="Work outcomes, career changes, relationships, and professional brand.",
        agent_id=AgentId.CAREER_COACH,
    ),
    LifeAreaOption(
        id=LifeArea.LEARNING,
        title="Learning & Skill Building",
        description="Durable knowledge, mastery, practice, and new capabilities.",
        agent_id=AgentId.KNOWLEDGE_GURU,
    ),
    LifeAreaOption(
        id=LifeArea.BRIEFING,
        title="News & Industry Briefings",
        description="Recent developments, approved sources, reading, and situational awareness.",
        agent_id=AgentId.BRIEFING_INTERN,
    ),
    LifeAreaOption(
        id=LifeArea.NUTRITION,
        title="Food & Nutrition",
        description="Meal plans, eating routines, calories, and user-selected nutrient targets.",
        agent_id=AgentId.NUTRITION_COACH,
    ),
    LifeAreaOption(
        id=LifeArea.FITNESS,
        title="Fitness & Recovery",
        description="Movement, workouts, sleep, physical capability, and recovery.",
        agent_id=AgentId.FITNESS_COACH,
    ),
    LifeAreaOption(
        id=LifeArea.WELLBEING,
        title="Inner Wellbeing",
        description="Reflection, mindset, gratitude, meditation, and intentional practices.",
        agent_id=AgentId.INNER_WELLBEING_GURU,
    ),
    LifeAreaOption(
        id=LifeArea.OPERATIONS,
        title="Life & Family Operations",
        description="Relationships, caregiving, pets, household routines, travel, and appointments.",
        agent_id=AgentId.OPERATIONS_MANAGER,
    ),
)

AREA_OWNER = {option.id: option.agent_id for option in AREA_OPTIONS}

INITIAL_GOAL_QUESTIONS: dict[LifeArea, str] = {
    LifeArea.PROFESSIONAL: (
        "What would you like to work on in your professional life? For example, "
        "you might be searching for a job, planning your next promotion, working "
        "on a professional or personal project, or building your professional brand. "
        "You can also choose something else."
    ),
    LifeArea.LEARNING: "What would you like to understand or become demonstrably capable of doing?",
    LifeArea.BRIEFING: "Which topics, sources, and recent developments should your briefings cover?",
    LifeArea.NUTRITION: "What exact nutrition outcome or meal plan would you like to establish?",
    LifeArea.FITNESS: "What exact fitness, movement, sleep, or recovery result would you like to achieve?",
    LifeArea.WELLBEING: "What inner wellbeing practice or result would you like to support?",
    LifeArea.OPERATIONS: "What life or family responsibility would you like to coordinate reliably?",
}


def start_planning_session(
    store: LifeOSStore, tenant_id: str, area: LifeArea
) -> GoalPlanningSession:
    selection = store.get_onboarding_selection(tenant_id)
    if selection and area not in selection.selected_areas:
        raise ValueError("This life area is not enabled for the user")
    now = utc_now()
    session = GoalPlanningSession(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        area=area,
        agent_id=AREA_OWNER[area],
        messages=[
            PlanningMessage(
                role=ConversationRole.ASSISTANT,
                content=INITIAL_GOAL_QUESTIONS[area],
            )
        ],
        created_at=now,
        updated_at=now,
    )
    return store.save_planning_session(session)


def finalize_planning_session(
    store: LifeOSStore,
    tenant_id: str,
    session_id: str,
    request: GoalContractCreate,
) -> tuple[GoalPlanningSession, GoalContract]:
    session = store.get_planning_session(tenant_id, session_id)
    if request.tenant_id != tenant_id:
        raise ValueError("Tenant mismatch")
    if request.domain != session.area or request.owner_agent != session.agent_id:
        raise ValueError("Goal domain and owner must match the planning session")
    goal = store.create_goal(request)
    session.goal_id = goal.id
    session.status = PlanningSessionStatus.FINALIZED
    session.updated_at = utc_now()
    store.save_planning_session(session)
    return session, goal


def continue_onboarding_after_goal(
    store: LifeOSStore,
    tenant_id: str,
    completed_session: GoalPlanningSession,
    goal: GoalContract,
) -> GoalPlanningCompletion:
    """Return control to the Chief of Staff and open the next selected area."""
    selection = store.get_onboarding_selection(tenant_id)
    if selection is None:
        return GoalPlanningCompletion(
            goal=goal,
            completed_session=completed_session,
            chief_of_staff_message=(
                "Chief of Staff: This goal has been saved as a draft and is ready for "
                "your review. Choose another life area whenever you are ready to continue."
            ),
            onboarding_complete=True,
        )

    sessions = store.list_planning_sessions(tenant_id)
    configured_areas = {
        session.area
        for session in sessions
        if session.status == PlanningSessionStatus.FINALIZED
    }
    remaining_areas = [
        area for area in selection.selected_areas if area not in configured_areas
    ]
    if not remaining_areas:
        return GoalPlanningCompletion(
            goal=goal,
            completed_session=completed_session,
            chief_of_staff_message=(
                "Chief of Staff: This goal has been saved as a draft. Every selected "
                "life area now has a configured goal. Next, review and approve each "
                "Goal Contract and its tracking protocol."
            ),
            onboarding_complete=True,
        )

    next_area = remaining_areas[0]
    next_session = next(
        (
            session
            for session in sessions
            if session.area == next_area
            and session.status != PlanningSessionStatus.FINALIZED
        ),
        None,
    )
    if next_session is None:
        next_session = start_planning_session(store, tenant_id, next_area)

    next_option = next(option for option in AREA_OPTIONS if option.id == next_area)
    handoff = (
        f"Chief of Staff: Your {completed_session.area.value} goal has been saved as "
        f"a draft. Next, let's configure {next_option.title} with its specialist."
    )
    if not next_session.messages or next_session.messages[0].content != handoff:
        next_session.messages.insert(
            0,
            PlanningMessage(role=ConversationRole.ASSISTANT, content=handoff),
        )
        next_session.updated_at = utc_now()
        store.save_planning_session(next_session)

    return GoalPlanningCompletion(
        goal=goal,
        completed_session=completed_session,
        chief_of_staff_message=handoff,
        next_session=next_session,
        remaining_areas=remaining_areas,
        onboarding_complete=False,
    )


def validate_goal_contract(goal: GoalContract) -> None:
    if goal.owner_agent != AREA_OWNER[goal.domain]:
        raise ValueError(f"{goal.domain} goals must be owned by {AREA_OWNER[goal.domain]}")
    if goal.review_at <= goal.start_at:
        raise ValueError("review_at must be after start_at")
    if not goal.metrics:
        raise ValueError("At least one exact success metric is required")
    for metric in goal.metrics:
        if metric.target_type == "range":
            if metric.minimum_value is None or metric.maximum_value is None:
                raise ValueError(f"Metric {metric.key} requires minimum_value and maximum_value")
            if metric.minimum_value > metric.maximum_value:
                raise ValueError(f"Metric {metric.key} has an invalid range")
        elif metric.target_value is None:
            raise ValueError(f"Metric {metric.key} requires target_value")


def generate_tracking_protocol(goal: GoalContract) -> TrackingProtocol:
    prompts: list[TrackingPrompt] = []
    for milestone in goal.milestones:
        if goal.domain == LifeArea.LEARNING:
            milestone_prompt = (
                f"Today you were supposed to study or complete: {milestone.title}. "
                f"Expected scope: {milestone.success_criteria} First, summarize what "
                "you learned from each assigned source separately. I will then probe "
                "your understanding of each concept, help create an interview-recall "
                "summary, and propose separate Archivist knowledge records for your "
                "confirmation."
            )
            milestone_agent = AgentId.CHIEF_ARCHIVIST
        elif milestone.kind == MilestoneKind.AGENT_DELIVERY:
            milestone_prompt = (
                f"Prepare and deliver: {milestone.title}. "
                f"Delivery requirements: {milestone.success_criteria} Do not ask the "
                "user to report whether they completed this delivery. After delivering "
                "it, ask only for concise usefulness, relevance, or correction feedback."
            )
            milestone_agent = goal.owner_agent
        else:
            archive_handoff = (
                " This work may produce durable, reusable knowledge. If it did, "
                "offer a Chief Archivist handoff. Preview the proposed record and "
                "save it only after the user confirms it. Do not archive routine "
                "completion status."
                if milestone.capture_knowledge
                else ""
            )
            milestone_prompt = (
                f"Today you committed to: {milestone.title}. "
                f"Expected scope: {milestone.success_criteria} What did you complete, "
                "what evidence do you have, what blocked you, and what is the next action?"
                f"{archive_handoff}"
            )
            milestone_agent = goal.owner_agent
        prompts.append(
            TrackingPrompt(
                id=str(uuid.uuid4()),
                cadence=TrackingCadence.ONCE,
                prompt=milestone_prompt,
                response_type=PromptResponseType.REFLECTION,
                due_at=milestone.due_at,
                agent_id=milestone_agent,
            )
        )
    for routine in goal.routines:
        prompts.append(
            TrackingPrompt(
                id=str(uuid.uuid4()),
                cadence=routine.cadence,
                prompt=(
                    f"Did you complete '{routine.title}'? "
                    f"Minimum success: {routine.minimum_success}"
                ),
                response_type=PromptResponseType.BOOLEAN,
                preferred_time=routine.preferred_time,
            )
        )
    for metric in goal.metrics:
        prompts.append(
            TrackingPrompt(
                id=str(uuid.uuid4()),
                cadence=metric.cadence,
                prompt=f"What was your {metric.label.lower()} in {metric.unit}?",
                response_type=PromptResponseType.NUMBER,
                metric_key=metric.key,
            )
        )
    prompts.append(
        TrackingPrompt(
            id=str(uuid.uuid4()),
            cadence=TrackingCadence.END_OF_CYCLE,
            prompt="How did this commitment cycle feel, and what helped or hindered you?",
            response_type=PromptResponseType.REFLECTION,
        )
    )
    return TrackingProtocol(
        id=str(uuid.uuid4()),
        tenant_id=goal.tenant_id,
        goal_id=goal.id,
        goal_version=goal.version,
        prompts=prompts,
    )


def activate_goal(store: LifeOSStore, tenant_id: str, goal_id: str) -> tuple[GoalContract, TrackingProtocol]:
    goal = store.get_goal(tenant_id, goal_id)
    if goal.status != GoalStatus.DRAFT:
        raise ValueError("Only draft goals can be approved")
    selection = store.get_onboarding_selection(tenant_id)
    if selection and goal.domain not in selection.selected_areas:
        raise ValueError("This life area is not enabled for the user")
    validate_goal_contract(goal)
    goal = store.set_goal_status(tenant_id, goal_id, GoalStatus.ACTIVE)
    protocol = store.save_tracking_protocol(generate_tracking_protocol(goal))
    return goal, protocol


def prepare_goal_review(store: LifeOSStore, tenant_id: str, goal_id: str) -> GoalReviewPacket:
    goal = store.get_goal(tenant_id, goal_id)
    commitments = [item for item in store.list_commitments(tenant_id) if item.goal_id == goal.id]
    events = [item for item in store.list_events(tenant_id) if item.goal_id == goal.id]
    status_counts = Counter(str(item.status) for item in commitments)
    done = status_counts[CommitmentStatus.DONE]
    metric_totals: dict[str, float] = defaultdict(float)
    for event in events:
        metric_totals[f"{event.metric}.{event.unit}"] += event.value
    if goal.status == GoalStatus.ACTIVE:
        goal = store.set_goal_status(tenant_id, goal_id, GoalStatus.AWAITING_REVIEW)
    return GoalReviewPacket(
        goal=goal,
        statistics=GoalCycleStats(
            commitments_total=len(commitments),
            commitments_done=done,
            completion_rate=done / len(commitments) if commitments else 0,
            by_status=dict(status_counts),
            metric_totals=dict(metric_totals),
        ),
        reflection_questions=[
            "How did this commitment cycle feel?",
            "What worked well?",
            "What made the plan difficult to follow?",
            "Was this goal still meaningful and realistic?",
            "Would you like to continue, adjust, replace, pause, or complete it?",
        ],
        specialist_agent=goal.owner_agent,
    )


def due_goal_reviews(
    store: LifeOSStore, tenant_id: str, as_of: datetime | None = None
) -> list[GoalContract]:
    cutoff = as_of or utc_now()
    return [
        goal
        for goal in store.list_goals(tenant_id, GoalStatus.ACTIVE)
        if goal.review_at <= cutoff
    ]


def schedule_protocol(goal: GoalContract, protocol: TrackingProtocol) -> list[ScheduledCheckIn]:
    check_ins: list[ScheduledCheckIn] = []
    for prompt in protocol.prompts:
        if not prompt.active:
            continue
        if prompt.cadence == TrackingCadence.ONCE:
            if prompt.due_at is None:
                raise ValueError("One-time tracking prompts require due_at")
            occurrences = [prompt.due_at]
        elif prompt.cadence == TrackingCadence.END_OF_CYCLE:
            occurrences = [goal.review_at]
        else:
            first = _first_recurring_due_at(
                goal.start_at, goal.review_at, prompt.cadence, prompt.preferred_time
            )
            if first < goal.start_at:
                first = _next_occurrence(first, prompt.cadence)
            occurrences = []
            occurrence = first
            while occurrence <= goal.review_at and len(occurrences) < 5000:
                occurrences.append(occurrence)
                occurrence = _next_occurrence(occurrence, prompt.cadence)
        check_ins.extend(
            ScheduledCheckIn(
                id=str(uuid.uuid4()),
                tenant_id=goal.tenant_id,
                goal_id=goal.id,
                protocol_id=protocol.id,
                prompt_id=prompt.id,
                agent_id=prompt.agent_id or goal.owner_agent,
                prompt=prompt.prompt,
                due_at=due_at,
            )
            for due_at in occurrences
        )
    return check_ins


def _first_recurring_due_at(
    start_at: datetime,
    review_at: datetime,
    cadence: TrackingCadence,
    preferred_time: str | None,
) -> datetime:
    first = _with_preferred_time(start_at, preferred_time)
    if cadence == TrackingCadence.DAILY:
        return first
    if cadence == TrackingCadence.WEEKLY:
        return min(first + timedelta(days=6), review_at)
    if cadence == TrackingCadence.MONTHLY:
        return min(_add_months(first, 1) - timedelta(days=1), review_at)
    if cadence == TrackingCadence.QUARTERLY:
        return min(_add_months(first, 3) - timedelta(days=1), review_at)
    if cadence == TrackingCadence.YEARLY:
        return min(_add_months(first, 12) - timedelta(days=1), review_at)
    raise ValueError(f"Unsupported recurring cadence: {cadence}")


def _with_preferred_time(value: datetime, preferred_time: str | None) -> datetime:
    if not preferred_time:
        return value
    try:
        hour, minute = (int(part) for part in preferred_time.split(":"))
        return value.replace(hour=hour, minute=minute, second=0, microsecond=0)
    except (TypeError, ValueError):
        raise ValueError("preferred_time must use HH:MM format") from None


def _next_occurrence(value: datetime, cadence: TrackingCadence) -> datetime:
    if cadence == TrackingCadence.DAILY:
        return value + timedelta(days=1)
    if cadence == TrackingCadence.WEEKLY:
        return value + timedelta(days=7)
    if cadence == TrackingCadence.MONTHLY:
        return _add_months(value, 1)
    if cadence == TrackingCadence.QUARTERLY:
        return _add_months(value, 3)
    if cadence == TrackingCadence.YEARLY:
        return _add_months(value, 12)
    raise ValueError(f"Unsupported recurring cadence: {cadence}")


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)
