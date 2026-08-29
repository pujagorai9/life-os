from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

from life_os.agent_catalog import list_agents
from life_os.analytics import build_progress_summary
from life_os.config import load_profile
from life_os.lifecycle import (
    AREA_OPTIONS,
    activate_goal,
    due_goal_reviews,
    finalize_planning_session,
    generate_tracking_protocol,
    prepare_goal_review,
    schedule_protocol,
    start_planning_session,
)
from life_os.models import (
    AgentDefinition,
    AgentOutput,
    ChatRequest,
    Commitment,
    CommitmentCreate,
    CommitmentStatus,
    CheckInStatusUpdate,
    GoalActivationResult,
    GoalAmendment,
    GoalAmendmentCreate,
    GoalContract,
    GoalContractCreate,
    GoalPlanningFinalize,
    GoalPlanningSession,
    GoalPlanningSessionCreate,
    GoalRenewalCreate,
    GoalReviewPacket,
    GoalStatus,
    LifeAreaOption,
    Memory,
    MemoryCreate,
    OnboardingSelection,
    PlanningMessage,
    PlanningMessageCreate,
    PlanningSessionStatus,
    PlanningTurn,
    ConversationRole,
    ProgressEvent,
    ProgressEventCreate,
    ProgressSummary,
    ScheduledCheckIn,
    TrackingProtocol,
    TrackingProtocolApproval,
    TrackingProtocolUpdate,
    utc_now,
)
from life_os.orchestrator import LifeOS
from life_os.store import LifeOSStore


def create_app(database: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="Life OS", version="0.2.0")
    store = LifeOSStore(database or os.getenv("LIFE_OS_DATABASE", "life_os.db"))
    runtime = LifeOS(store=store, profile=load_profile())

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/agents", response_model=list[AgentDefinition])
    def agents() -> list[AgentDefinition]:
        return list_agents()

    @app.get("/v1/onboarding/options", response_model=list[LifeAreaOption])
    def onboarding_options() -> list[LifeAreaOption]:
        return list(AREA_OPTIONS)

    @app.put("/v1/onboarding/selection", response_model=OnboardingSelection)
    def save_onboarding_selection(request: OnboardingSelection) -> OnboardingSelection:
        return store.save_onboarding_selection(request)

    @app.get("/v1/onboarding/selection", response_model=OnboardingSelection)
    def onboarding_selection(tenant_id: str = Query(...)) -> OnboardingSelection:
        selection = store.get_onboarding_selection(tenant_id)
        if selection is None:
            raise HTTPException(status_code=404, detail="Onboarding selection not found")
        return selection

    @app.post("/v1/chat", response_model=AgentOutput)
    def chat(request: ChatRequest) -> AgentOutput:
        return runtime.chat(request)

    @app.post("/v1/planning-sessions", response_model=GoalPlanningSession)
    def create_planning_session(
        request: GoalPlanningSessionCreate,
    ) -> GoalPlanningSession:
        try:
            return start_planning_session(store, request.tenant_id, request.area)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/v1/planning-sessions", response_model=list[GoalPlanningSession])
    def planning_sessions(tenant_id: str = Query(...)) -> list[GoalPlanningSession]:
        return store.list_planning_sessions(tenant_id)

    @app.get("/v1/planning-sessions/{session_id}", response_model=GoalPlanningSession)
    def planning_session(
        session_id: str, tenant_id: str = Query(...)
    ) -> GoalPlanningSession:
        try:
            return store.get_planning_session(tenant_id, session_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/v1/planning-sessions/{session_id}/messages", response_model=PlanningTurn)
    def planning_message(session_id: str, request: PlanningMessageCreate) -> PlanningTurn:
        try:
            session = store.get_planning_session(request.tenant_id, session_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        if session.status == PlanningSessionStatus.FINALIZED:
            raise HTTPException(status_code=422, detail="Planning session is finalized")
        session.messages.append(
            PlanningMessage(role=ConversationRole.USER, content=request.message)
        )
        transcript = "\n".join(
            f"{message.role}: {message.content}" for message in session.messages[-20:]
        )
        response = runtime.chat(
            ChatRequest(
                tenant_id=request.tenant_id,
                agent_id=session.agent_id,
                message=(
                    "Continue this Goal Contract planning conversation. Ask only the most "
                    "useful next questions, suggest concrete targets, and do not claim the "
                    "goal is approved. The contract still needs exact metrics, recurring "
                    "actions, evidence, constraints, a start date, and a review date.\n\n"
                    f"Conversation so far:\n{transcript}"
                ),
            )
        )
        assistant_text = response.summary
        if response.questions:
            assistant_text += "\n" + "\n".join(response.questions)
        session.messages.append(
            PlanningMessage(role=ConversationRole.ASSISTANT, content=assistant_text)
        )
        session.updated_at = utc_now()
        store.save_planning_session(session)
        return PlanningTurn(session=session, response=response)

    @app.post("/v1/planning-sessions/{session_id}/finalize", response_model=GoalContract)
    def finalize_goal_plan(
        session_id: str, request: GoalPlanningFinalize
    ) -> GoalContract:
        try:
            _, goal_contract = finalize_planning_session(
                store, request.tenant_id, session_id, request.goal
            )
            return goal_contract
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/v1/goals", response_model=GoalContract)
    def create_goal(request: GoalContractCreate) -> GoalContract:
        if request.review_at <= request.start_at:
            raise HTTPException(status_code=422, detail="review_at must be after start_at")
        return store.create_goal(request)

    @app.get("/v1/goals", response_model=list[GoalContract])
    def goals(
        tenant_id: str = Query(...), status: GoalStatus | None = Query(None)
    ) -> list[GoalContract]:
        return store.list_goals(tenant_id, status)

    @app.get("/v1/goals/{goal_id}", response_model=GoalContract)
    def goal(goal_id: str, tenant_id: str = Query(...)) -> GoalContract:
        try:
            return store.get_goal(tenant_id, goal_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/v1/goals/{goal_id}/approve", response_model=GoalActivationResult)
    def approve_goal(goal_id: str, tenant_id: str = Query(...)) -> GoalActivationResult:
        try:
            goal_contract, protocol = activate_goal(store, tenant_id, goal_id)
            return GoalActivationResult(
                goal=goal_contract, proposed_tracking_protocol=protocol
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/v1/goals/{goal_id}/amendments", response_model=GoalContract)
    def amend_goal(goal_id: str, request: GoalAmendmentCreate) -> GoalContract:
        try:
            revised, _ = store.amend_goal(request.tenant_id, goal_id, request)
            store.save_tracking_protocol(generate_tracking_protocol(revised))
            return revised
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/v1/goals/{goal_id}/amendments", response_model=list[GoalAmendment])
    def goal_amendments(goal_id: str, tenant_id: str = Query(...)) -> list[GoalAmendment]:
        return store.list_goal_amendments(tenant_id, goal_id)

    @app.patch("/v1/goals/{goal_id}/status", response_model=GoalContract)
    def update_goal_status(
        goal_id: str,
        tenant_id: str = Query(...),
        status: GoalStatus = Query(...),
    ) -> GoalContract:
        try:
            return store.set_goal_status(tenant_id, goal_id, status)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/v1/goals/{goal_id}/tracking-protocol", response_model=TrackingProtocol)
    def tracking_protocol(goal_id: str, tenant_id: str = Query(...)) -> TrackingProtocol:
        try:
            return store.get_tracking_protocol(tenant_id, goal_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.put("/v1/goals/{goal_id}/tracking-protocol", response_model=TrackingProtocol)
    def replace_tracking_protocol(
        goal_id: str, request: TrackingProtocolUpdate
    ) -> TrackingProtocol:
        try:
            goal_contract = store.get_goal(request.tenant_id, goal_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        protocol = TrackingProtocol(
            id=str(uuid.uuid4()),
            tenant_id=request.tenant_id,
            goal_id=goal_id,
            goal_version=goal_contract.version,
            prompts=request.prompts,
        )
        return store.save_tracking_protocol(protocol)

    @app.post("/v1/goals/{goal_id}/tracking-protocol/approval", response_model=TrackingProtocol)
    def approve_tracking_protocol(
        goal_id: str, request: TrackingProtocolApproval
    ) -> TrackingProtocol:
        try:
            protocol = store.set_tracking_protocol_approval(
                request.tenant_id, goal_id, request.approved
            )
            if request.approved:
                goal_contract = store.get_goal(request.tenant_id, goal_id)
                store.replace_pending_check_ins(
                    request.tenant_id,
                    goal_id,
                    schedule_protocol(goal_contract, protocol),
                )
            return protocol
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/v1/check-ins/due", response_model=list[ScheduledCheckIn])
    def due_check_ins(
        tenant_id: str = Query(...),
        as_of: datetime | None = Query(None),
        limit: int = Query(100, ge=1, le=500),
    ) -> list[ScheduledCheckIn]:
        return store.due_check_ins(tenant_id, as_of or utc_now(), limit)

    @app.patch("/v1/check-ins/{check_in_id}", response_model=ScheduledCheckIn)
    def update_check_in(
        check_in_id: str, request: CheckInStatusUpdate
    ) -> ScheduledCheckIn:
        try:
            return store.update_check_in_status(
                request.tenant_id, check_in_id, request.status
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/v1/reviews/due", response_model=list[GoalContract])
    def due_reviews(
        tenant_id: str = Query(...), as_of: datetime | None = Query(None)
    ) -> list[GoalContract]:
        return due_goal_reviews(store, tenant_id, as_of)

    @app.post("/v1/goals/{goal_id}/review", response_model=GoalReviewPacket)
    def review_goal(goal_id: str, tenant_id: str = Query(...)) -> GoalReviewPacket:
        try:
            return prepare_goal_review(store, tenant_id, goal_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/v1/goals/{goal_id}/renew", response_model=GoalContract)
    def renew_goal(goal_id: str, request: GoalRenewalCreate) -> GoalContract:
        try:
            existing = store.get_goal(request.tenant_id, goal_id)
            if existing.status != GoalStatus.AWAITING_REVIEW:
                raise ValueError("Goal must be awaiting review before renewal")
            renewed = store.renew_goal(
                request.tenant_id,
                goal_id,
                request.start_at,
                request.review_at,
                request.changes,
            )
            store.set_goal_status(request.tenant_id, goal_id, GoalStatus.COMPLETED)
            return renewed
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/v1/commitments", response_model=Commitment)
    def create_commitment(request: CommitmentCreate) -> Commitment:
        return store.create_commitment(request)

    @app.patch("/v1/commitments/{commitment_id}", response_model=Commitment)
    def update_commitment(
        commitment_id: str,
        tenant_id: str = Query(...),
        status: CommitmentStatus = Query(...),
    ) -> Commitment:
        try:
            return store.update_commitment_status(tenant_id, commitment_id, status)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/v1/events", response_model=ProgressEvent)
    def create_event(request: ProgressEventCreate) -> ProgressEvent:
        return store.create_event(request)

    @app.get("/v1/progress", response_model=ProgressSummary)
    def progress(tenant_id: str = Query(...)) -> ProgressSummary:
        return build_progress_summary(store, tenant_id)

    @app.post("/v1/memories", response_model=Memory)
    def propose_memory(request: MemoryCreate) -> Memory:
        return store.propose_memory(request)

    @app.post("/v1/memories/{memory_id}/confirm", response_model=Memory)
    def confirm_memory(memory_id: str, tenant_id: str = Query(...)) -> Memory:
        try:
            return store.confirm_memory(tenant_id, memory_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    return app


app = create_app()
