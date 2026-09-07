from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
import os
import re
import secrets
import uuid
from contextlib import asynccontextmanager, suppress
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse

from life_os.agent_catalog import list_agents
from life_os.analytics import build_progress_summary
from life_os.config import load_profile
from life_os.lifecycle import (
    AREA_OPTIONS,
    activate_goal,
    continue_onboarding_after_goal,
    due_goal_reviews,
    finalize_planning_session,
    generate_tracking_protocol,
    prepare_goal_review,
    schedule_protocol,
    start_planning_session,
)
from life_os.models import (
    AgentDefinition,
    AgentId,
    AgentOutput,
    AppointmentSyncDocument,
    AppointmentSyncItem,
    AppleHealthDailyImport,
    AppleHealthImportResult,
    BriefingDocument,
    BriefingDocumentCreate,
    ChatRequest,
    Commitment,
    CommitmentCreate,
    CommitmentStatus,
    CheckInPhoto,
    CheckInStatusUpdate,
    ConversationRole,
    ExpenseRecord,
    FinanceDailyReport,
    FinanceEmailAccount,
    FinanceEmailResultCreate,
    GoalActivationResult,
    GoalAmendment,
    GoalAmendmentCreate,
    GoalContract,
    GoalContractCreate,
    GoalPlanningFinalize,
    GoalPlanningCompletion,
    GoalPlanningSession,
    GoalPlanningSessionCreate,
    GoalRenewalCreate,
    GoalReviewPacket,
    GoalStatus,
    LifeAreaOption,
    KnowledgeRecord,
    KnowledgeRecordCreate,
    Memory,
    MemoryCreate,
    NutritionAnalysisRequest,
    NutritionConversationRequest,
    NutritionConversationResult,
    OnboardingSelection,
    PlanningMessage,
    PlanningMessageCreate,
    PlanningSessionStatus,
    PlanningTurn,
    PhotoAnalysis,
    PhotoAnalysisStatus,
    ProgressEvent,
    ProgressEventCreate,
    ProgressSummary,
    PushSubscription,
    PushSubscriptionCreate,
    PushSubscriptionDelete,
    ScheduledCheckIn,
    TrackingProtocol,
    TrackingProtocolApproval,
    TrackingProtocolUpdate,
    utc_now,
)
from life_os.orchestrator import LifeOS
from life_os.photo_analysis import (
    analyze_check_in_photo,
    analyze_nutrition_description,
    analyze_nutrition_input,
)
from life_os.store import LifeOSStore
from life_os.apple_health import import_apple_health_daily
from life_os.notifications import notifications_configured, send_due_notifications


MAX_PHOTO_BYTES = 12 * 1024 * 1024
PHOTO_AGENTS = {
    AgentId.NUTRITION_COACH,
    AgentId.FITNESS_COACH,
    AgentId.KNOWLEDGE_GURU,
    AgentId.CAREER_COACH,
}


def _authorize_private_api(request: Request) -> None:
    """Require the shared server-to-server token when cloud auth is enabled."""
    expected = os.getenv("LIFE_OS_API_TOKEN", "").strip()
    if not expected:
        return
    supplied = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if not supplied or not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid Life OS API token")


def _validated_image_type(image: bytes, declared_type: str) -> tuple[str, str]:
    media_type = declared_type.split(";", 1)[0].strip().lower()
    signatures = {
        "image/jpeg": ("jpg", image.startswith(b"\xff\xd8\xff")),
        "image/png": ("png", image.startswith(b"\x89PNG\r\n\x1a\n")),
        "image/webp": (
            "webp",
            len(image) >= 12 and image.startswith(b"RIFF") and image[8:12] == b"WEBP",
        ),
        "image/heic": (
            "heic",
            len(image) >= 12
            and image[4:8] == b"ftyp"
            and image[8:12] in {b"heic", b"heix", b"hevc"},
        ),
        "image/heif": (
            "heif",
            len(image) >= 12 and image[4:8] == b"ftyp" and image[8:12] in {b"heif", b"mif1"},
        ),
    }
    extension, valid = signatures.get(media_type, ("", False))
    if not valid:
        raise ValueError("Upload a valid JPEG, PNG, WebP, HEIC, or HEIF image")
    return media_type, extension


def _health_ingest_token() -> str:
    token_path = Path(
        os.getenv(
            "LIFE_OS_HEALTH_INGEST_TOKEN_PATH",
            "private/apple-health-ingest-token.txt",
        )
    )
    try:
        return token_path.read_text().strip()
    except OSError as error:
        raise HTTPException(
            status_code=503,
            detail="Apple Health ingestion has not been configured",
        ) from error


def _authorize_health_ingest(authorization: str | None) -> None:
    expected = _health_ingest_token()
    supplied = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not supplied or not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid ingestion token")


def create_app(
    database: str | Path | None = None,
    briefings_dir: str | Path | None = None,
    appointment_ledger_path: str | Path | None = None,
    gmail_accounts_path: str | Path | None = None,
) -> FastAPI:
    store = LifeOSStore(database or os.getenv("LIFE_OS_DATABASE", "life_os.db"))
    profile = load_profile()
    runtime = LifeOS(store=store, profile=profile)
    private_briefings = Path(
        briefings_dir or os.getenv("LIFE_OS_BRIEFINGS_DIR", "private/briefings")
    )
    appointment_ledger = Path(
        appointment_ledger_path
        or os.getenv(
            "LIFE_OS_APPOINTMENT_LEDGER", "private/appointment-ledger.json"
        )
    )
    gmail_accounts = Path(
        gmail_accounts_path
        or os.getenv("LIFE_OS_GMAIL_ACCOUNTS", "private/gmail-accounts.json")
    )
    try:
        user_timezone = ZoneInfo(
            os.getenv("LIFE_OS_TIMEZONE", profile.user.timezone)
        )
    except ZoneInfoNotFoundError:
        user_timezone = ZoneInfo("UTC")

    async def notification_worker() -> None:
        while True:
            await asyncio.to_thread(send_due_notifications, store, utc_now())
            await asyncio.sleep(30)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        notification_task: asyncio.Task[None] | None = None
        if notifications_configured():
            notification_task = asyncio.create_task(notification_worker())
        try:
            yield
        finally:
            if notification_task:
                notification_task.cancel()
                with suppress(asyncio.CancelledError):
                    await notification_task

    app = FastAPI(title="Life OS", version="0.5.0", lifespan=lifespan)

    @app.middleware("http")
    async def private_api_auth(request: Request, call_next):
        # Health checks remain accessible to the hosting platform. Apple Health
        # ingestion has its own narrowly scoped bearer token.
        public_integration_path = request.url.path.startswith(
            "/v1/integrations/apple-health/"
        ) or request.url.path == "/v1/integrations/whoop/callback"
        if request.url.path != "/health" and not public_integration_path:
            try:
                _authorize_private_api(request)
            except HTTPException as error:
                return Response(
                    content=json.dumps({"detail": error.detail}),
                    status_code=error.status_code,
                    media_type="application/json",
                )
        return await call_next(request)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/integrations/whoop/status")
    def whoop_status() -> dict[str, object]:
        from life_os.connectors.whoop import WhoopConnector

        try:
            return WhoopConnector.from_environment().token_status()
        except ValueError:
            return {
                "configured": False,
                "connected": False,
                "scope": [],
                "has_refresh_token": False,
            }

    @app.post("/v1/integrations/whoop/authorize")
    def authorize_whoop() -> dict[str, str]:
        from life_os.connectors.whoop import WhoopConnector

        try:
            authorization = WhoopConnector.from_environment().begin_authorization()
        except ValueError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        return {"url": authorization.url}

    @app.get("/v1/integrations/whoop/callback")
    def whoop_callback(
        code: str = Query(""),
        state: str = Query(""),
        error: str = Query(""),
    ) -> RedirectResponse:
        from life_os.connectors.whoop import WhoopConnector

        if error:
            raise HTTPException(
                status_code=400, detail=f"WHOOP authorization was declined: {error}"
            )
        if not code or not state:
            raise HTTPException(
                status_code=400, detail="WHOOP did not return an authorization code"
            )
        try:
            WhoopConnector.from_environment().exchange_code(code, state)
        except (ValueError, RuntimeError, httpx.HTTPError) as exchange_error:
            raise HTTPException(
                status_code=400, detail=str(exchange_error)
            ) from exchange_error
        return_url = os.getenv("WHOOP_RETURN_URL", "").strip()
        if not return_url.startswith("https://"):
            raise HTTPException(
                status_code=500, detail="WHOOP_RETURN_URL is not configured"
            )
        separator = "&" if "?" in return_url else "?"
        return RedirectResponse(
            f"{return_url}{separator}whoop=connected", status_code=303
        )

    @app.post("/v1/integrations/whoop/sync")
    def sync_whoop(
        tenant_id: str = Query(...), days: int = Query(7, ge=1, le=31)
    ) -> dict[str, object]:
        from life_os.connectors.whoop import WhoopConnector
        from life_os.whoop_sync import sync_whoop_daily

        end_date = datetime.now(user_timezone).date()
        start_date = end_date - timedelta(days=days - 1)
        try:
            return sync_whoop_daily(
                store,
                WhoopConnector.from_environment(),
                tenant_id,
                start_date,
                end_date,
            )
        except ValueError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=502, detail="WHOOP could not be reached"
            ) from error

    @app.get("/v1/agents", response_model=list[AgentDefinition])
    def agents() -> list[AgentDefinition]:
        return list_agents()

    @app.post("/v1/finance/email-results", response_model=ExpenseRecord | None)
    def save_finance_email_result(
        request: FinanceEmailResultCreate,
    ) -> ExpenseRecord | None:
        return store.save_finance_email_result(request)

    @app.get("/v1/finance/daily/{day}", response_model=FinanceDailyReport)
    def finance_daily_report(
        day: date, tenant_id: str = Query(...)
    ) -> FinanceDailyReport:
        return store.finance_daily_report(tenant_id, day, user_timezone)

    @app.get("/v1/finance/accounts", response_model=list[FinanceEmailAccount])
    def finance_accounts(tenant_id: str = Query(...)) -> list[FinanceEmailAccount]:
        if not tenant_id.strip():
            raise HTTPException(status_code=422, detail="tenant_id is required")
        from life_os.connectors.google_gmail import list_gmail_accounts

        try:
            return [
                FinanceEmailAccount.model_validate(item)
                for item in list_gmail_accounts(gmail_accounts)
            ]
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise HTTPException(
                status_code=503, detail="Finance email connections could not be read"
            ) from error

    @app.get("/v1/briefings/{day}", response_model=BriefingDocument)
    def briefing(day: date, tenant_id: str = Query(...)) -> BriefingDocument:
        if not tenant_id.strip():
            raise HTTPException(status_code=422, detail="tenant_id is required")
        try:
            return store.get_briefing(tenant_id, day)
        except KeyError:
            pass
        # Legacy local briefings remain readable while new cloud briefings are
        # stored in the tenant-scoped database.
        candidates = sorted(private_briefings.glob(f"{day.isoformat()}*.md"))
        if not candidates:
            raise HTTPException(status_code=404, detail="Briefing is not available yet")
        source = candidates[-1]
        try:
            markdown = source.read_text(encoding="utf-8")
        except OSError as error:
            raise HTTPException(
                status_code=503, detail="Briefing could not be opened"
            ) from error
        if len(markdown.encode("utf-8")) > 512 * 1024:
            raise HTTPException(status_code=413, detail="Briefing is too large")
        first_line = markdown.splitlines()[0].strip() if markdown else ""
        title = first_line.removeprefix("# ").strip() or f"Briefing — {day}"
        return BriefingDocument(
            day=day,
            title=title,
            markdown=markdown,
            source_file=source.name,
        )

    @app.post("/v1/briefings", response_model=BriefingDocument)
    def save_briefing(request: BriefingDocumentCreate) -> BriefingDocument:
        return store.save_briefing(request)

    @app.get(
        "/v1/appointment-syncs/{day}", response_model=AppointmentSyncDocument
    )
    def appointment_sync(
        day: date, tenant_id: str = Query(...)
    ) -> AppointmentSyncDocument:
        if not tenant_id.strip():
            raise HTTPException(status_code=422, detail="tenant_id is required")
        try:
            raw = appointment_ledger.read_text(encoding="utf-8")
            ledger = json.loads(raw)
        except FileNotFoundError as error:
            raise HTTPException(
                status_code=404, detail="Appointment sync is not available yet"
            ) from error
        except (OSError, json.JSONDecodeError) as error:
            raise HTTPException(
                status_code=503, detail="Appointment sync could not be opened"
            ) from error

        def parse_instant(value: object) -> datetime | None:
            if not isinstance(value, str) or not value.strip():
                return None
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None

        entries = [
            entry
            for entry in ledger.get("entries", [])
            if isinstance(entry, dict)
            and (instant := parse_instant(entry.get("processed_at"))) is not None
            and instant.astimezone(user_timezone).date() == day
        ]
        ledger_processed_at = parse_instant(ledger.get("processed_at"))
        run_matches_day = bool(
            ledger_processed_at
            and ledger_processed_at.astimezone(user_timezone).date() == day
        )
        if not entries and not run_matches_day:
            raise HTTPException(
                status_code=404, detail="Appointment sync is not available for this day"
            )
        processed_at = ledger_processed_at or max(
            parse_instant(entry.get("processed_at")) for entry in entries
        )
        assert processed_at is not None

        exception_summaries = {
            item.get("gmail_message_id"): str(item.get("summary", "")).strip()
            for item in ledger.get("exceptions", [])
            if isinstance(item, dict)
        }
        items: list[AppointmentSyncItem] = []
        created = updated = cancelled = matched = 0
        for entry in entries:
            action_key = str(entry.get("action", "")).casefold()
            outcome_key = str(entry.get("outcome", "")).casefold()
            is_exception = "exception" in outcome_key or "failed" in outcome_key
            if "create" in action_key or "created" in outcome_key:
                created += 1
                action = "Created calendar event"
            elif "cancel" in action_key or "cancelled" in outcome_key:
                cancelled += 1
                action = "Cancelled calendar event"
            elif "update" in action_key or "reschedul" in action_key:
                updated += 1
                action = "Updated calendar event"
            elif "match" in action_key or "existing" in outcome_key:
                matched += 1
                action = "Matched existing event"
            else:
                action = "Reviewed appointment"

            fingerprint = str(entry.get("event_fingerprint", ""))
            event_date: date | None = None
            event_time: str | None = None
            match = re.search(r"-(\d{4})-(\d{2})-(\d{2})-(\d{4})$", fingerprint)
            if match:
                try:
                    event_date = date(
                        int(match.group(1)), int(match.group(2)), int(match.group(3))
                    )
                    clock = datetime.strptime(match.group(4), "%H%M")
                    event_time = clock.strftime("%-I:%M %p")
                except ValueError:
                    event_date = None
                    event_time = None

            summary = exception_summaries.get(entry.get("gmail_message_id"), "")
            if not summary:
                summary = str(entry.get("outcome", "Reviewed successfully"))
                summary = summary.replace("_", " ").strip().capitalize()
            items.append(
                AppointmentSyncItem(
                    action=action,
                    outcome=str(entry.get("outcome", "unknown")),
                    summary=summary,
                    event_date=event_date,
                    event_time=event_time,
                    exception=is_exception,
                )
            )

        return AppointmentSyncDocument(
            day=day,
            processed_at=processed_at,
            cutoff_at=parse_instant(ledger.get("current_cutoff_inclusive")),
            emails_processed=len(entries),
            events_created=created,
            events_updated=updated,
            events_cancelled=cancelled,
            existing_events_matched=matched,
            items=items,
        )

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

    @app.post(
        "/v1/planning-sessions/{session_id}/finalize",
        response_model=GoalPlanningCompletion,
    )
    def finalize_goal_plan(
        session_id: str, request: GoalPlanningFinalize
    ) -> GoalPlanningCompletion:
        try:
            session, goal_contract = finalize_planning_session(
                store, request.tenant_id, session_id, request.goal
            )
            return continue_onboarding_after_goal(
                store, request.tenant_id, session, goal_contract
            )
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

    @app.get("/v1/check-ins", response_model=list[ScheduledCheckIn])
    def check_ins(
        tenant_id: str = Query(...),
        start_at: datetime = Query(...),
        end_at: datetime = Query(...),
        limit: int = Query(500, ge=1, le=1000),
    ) -> list[ScheduledCheckIn]:
        if end_at < start_at:
            raise HTTPException(status_code=422, detail="end_at must not precede start_at")
        return store.list_check_ins(tenant_id, start_at, end_at, limit)

    @app.patch("/v1/check-ins/{check_in_id}", response_model=ScheduledCheckIn)
    def update_check_in(
        check_in_id: str, request: CheckInStatusUpdate
    ) -> ScheduledCheckIn:
        try:
            return store.update_check_in_status(
                request.tenant_id, check_in_id, request.status, request.outcome
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/v1/check-ins/{check_in_id}/photos", response_model=CheckInPhoto)
    async def upload_check_in_photo(
        check_in_id: str,
        request: Request,
        tenant_id: str = Query(...),
        analyze: bool = Query(False),
    ) -> CheckInPhoto:
        try:
            check_in = store.get_check_in(tenant_id, check_in_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        if check_in.agent_id not in PHOTO_AGENTS:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Photos are enabled only for Nutrition Coach, Fitness Coach, "
                    "Knowledge Guru, and Career Coach tasks"
                ),
            )
        declared_size = request.headers.get("content-length")
        if declared_size and int(declared_size) > MAX_PHOTO_BYTES:
            raise HTTPException(status_code=413, detail="Photo must be 12 MB or smaller")
        image = await request.body()
        if not image:
            raise HTTPException(status_code=422, detail="Photo is empty")
        if len(image) > MAX_PHOTO_BYTES:
            raise HTTPException(status_code=413, detail="Photo must be 12 MB or smaller")
        try:
            media_type, extension = _validated_image_type(
                image, request.headers.get("content-type", "")
            )
        except ValueError as error:
            raise HTTPException(status_code=415, detail=str(error)) from error

        analysis = None
        analysis_status = PhotoAnalysisStatus.NOT_REQUESTED
        if analyze:
            try:
                analysis = analyze_check_in_photo(
                    agent_id=check_in.agent_id,
                    prompt=check_in.prompt,
                    media_type=media_type,
                    image=image,
                )
                analysis_status = (
                    PhotoAnalysisStatus.COMPLETED
                    if analysis
                    else PhotoAnalysisStatus.UNAVAILABLE
                )
            except (httpx.HTTPError, ValueError, json.JSONDecodeError):
                analysis_status = PhotoAnalysisStatus.UNAVAILABLE

        photo_id = str(uuid.uuid4())
        tenant_segment = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()[:16]
        photo = CheckInPhoto(
            id=photo_id,
            tenant_id=tenant_id,
            check_in_id=check_in_id,
            agent_id=check_in.agent_id,
            storage_key=f"{tenant_segment}/{photo_id}.{extension}",
            media_type=media_type,
            size_bytes=len(image),
            sha256=hashlib.sha256(image).hexdigest(),
            analysis_status=analysis_status,
            analysis=analysis,
        )
        return store.save_check_in_photo(photo, image, extension)

    @app.post(
        "/v1/check-ins/{check_in_id}/photos/{photo_id}/analyze",
        response_model=CheckInPhoto,
    )
    def reanalyze_check_in_photo(
        check_in_id: str, photo_id: str, tenant_id: str = Query(...)
    ) -> CheckInPhoto:
        try:
            check_in = store.get_check_in(tenant_id, check_in_id)
            photo = store.get_check_in_photo(tenant_id, check_in_id, photo_id)
            image = store.read_check_in_photo(photo)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except (OSError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        try:
            analysis = analyze_check_in_photo(
                agent_id=check_in.agent_id,
                prompt=check_in.prompt,
                media_type=photo.media_type,
                image=image,
            )
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise HTTPException(
                status_code=502, detail="Photo analysis is temporarily unavailable"
            ) from error
        if analysis is None:
            raise HTTPException(status_code=503, detail="Photo analysis is not configured")
        return store.update_check_in_photo_analysis(photo, analysis)

    @app.post(
        "/v1/check-ins/{check_in_id}/nutrition-analysis",
        response_model=PhotoAnalysis,
    )
    def analyze_nutrition(
        check_in_id: str, request: NutritionAnalysisRequest
    ) -> PhotoAnalysis:
        try:
            check_in = store.get_check_in(request.tenant_id, check_in_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        if check_in.agent_id != AgentId.NUTRITION_COACH:
            raise HTTPException(
                status_code=422,
                detail="Nutrition analysis is enabled only for Nutrition Coach tasks",
            )
        try:
            analysis = analyze_nutrition_description(
                prompt=check_in.prompt, description=request.description
            )
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise HTTPException(
                status_code=502, detail="Nutrition analysis is temporarily unavailable"
            ) from error
        if analysis is None:
            raise HTTPException(
                status_code=503, detail="Nutrition analysis is not configured"
            )
        return analysis

    @app.post(
        "/v1/check-ins/{check_in_id}/nutrition-conversation",
        response_model=NutritionConversationResult,
    )
    def analyze_nutrition_conversation(
        check_in_id: str, request: NutritionConversationRequest
    ) -> NutritionConversationResult:
        try:
            check_in = store.get_check_in(request.tenant_id, check_in_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        if check_in.agent_id != AgentId.NUTRITION_COACH:
            raise HTTPException(
                status_code=422,
                detail="Nutrition conversation is enabled only for Nutrition Coach tasks",
            )

        validated_images: list[tuple[str, str, bytes]] = []
        for input_image in request.images:
            try:
                image = base64.b64decode(input_image.data, validate=True)
            except (binascii.Error, ValueError) as error:
                raise HTTPException(
                    status_code=422, detail="One of the meal images is invalid"
                ) from error
            if len(image) > MAX_PHOTO_BYTES:
                raise HTTPException(
                    status_code=413, detail="Each photo must be 12 MB or smaller"
                )
            try:
                media_type, extension = _validated_image_type(
                    image, input_image.media_type
                )
            except ValueError as error:
                raise HTTPException(status_code=415, detail=str(error)) from error
            if media_type not in {"image/jpeg", "image/png", "image/webp"}:
                raise HTTPException(
                    status_code=415,
                    detail="Meal analysis supports JPEG, PNG, and WebP images",
                )
            validated_images.append((media_type, extension, image))

        try:
            analysis = analyze_nutrition_input(
                prompt=check_in.prompt,
                description=request.description,
                images=[(media_type, image) for media_type, _, image in validated_images],
            )
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
            raise HTTPException(
                status_code=502, detail="Nutrition analysis is temporarily unavailable"
            ) from error
        if analysis is None:
            raise HTTPException(
                status_code=503, detail="Nutrition analysis is not configured"
            )

        tenant_segment = hashlib.sha256(
            request.tenant_id.encode("utf-8")
        ).hexdigest()[:16]
        photos: list[CheckInPhoto] = []
        for media_type, extension, image in validated_images:
            photo_id = str(uuid.uuid4())
            photo = CheckInPhoto(
                id=photo_id,
                tenant_id=request.tenant_id,
                check_in_id=check_in_id,
                agent_id=check_in.agent_id,
                storage_key=f"{tenant_segment}/{photo_id}.{extension}",
                media_type=media_type,
                size_bytes=len(image),
                sha256=hashlib.sha256(image).hexdigest(),
                analysis_status=PhotoAnalysisStatus.COMPLETED,
                analysis=analysis,
            )
            photos.append(store.save_check_in_photo(photo, image, extension))
        return NutritionConversationResult(photos=photos, analysis=analysis)

    @app.get(
        "/v1/check-ins/{check_in_id}/photos", response_model=list[CheckInPhoto]
    )
    def check_in_photos(
        check_in_id: str, tenant_id: str = Query(...)
    ) -> list[CheckInPhoto]:
        try:
            store.get_check_in(tenant_id, check_in_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return store.list_check_in_photos(tenant_id, check_in_id)

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
        if request.metric in {"pumping_ml", "pumping_minutes"}:
            event, _ = store.upsert_event_by_occurrence(request)
            return event
        return store.create_event(request)

    @app.get("/v1/notifications/config")
    def notification_config() -> dict[str, str | bool]:
        return {
            "configured": notifications_configured(),
            "public_key": os.getenv("LIFE_OS_VAPID_PUBLIC_KEY", "").strip(),
        }

    @app.post("/v1/notifications/subscriptions", response_model=PushSubscription)
    def save_push_subscription(
        request: PushSubscriptionCreate,
    ) -> PushSubscription:
        if not notifications_configured():
            raise HTTPException(status_code=503, detail="Notifications are not configured")
        return store.upsert_push_subscription(request)

    @app.delete("/v1/notifications/subscriptions", status_code=204)
    def delete_push_subscription(request: PushSubscriptionDelete) -> Response:
        store.delete_push_subscription(request.tenant_id, request.endpoint)
        return Response(status_code=204)

    @app.post(
        "/v1/integrations/apple-health/import",
        response_model=AppleHealthImportResult,
    )
    def import_apple_health(
        request: AppleHealthDailyImport,
        authorization: str | None = Header(default=None),
    ) -> AppleHealthImportResult:
        _authorize_health_ingest(authorization)
        return import_apple_health_daily(store, request)

    @app.post(
        "/v1/integrations/apple-health/shortcut",
        response_model=AppleHealthImportResult,
    )
    def import_apple_health_shortcut(
        tenant_id: str = Query(...),
        day: str = Query(...),
        timezone_name: str = Query(..., alias="timezone"),
        exercise_minutes: str | None = Query(default=None),
        stand_minutes: str | None = Query(default=None),
        active_energy_kcal: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ) -> AppleHealthImportResult:
        _authorize_health_ingest(authorization)
        payload = AppleHealthDailyImport.model_validate(
            {
                "tenant_id": tenant_id,
                "day": day,
                "timezone": timezone_name,
                "exercise_minutes": exercise_minutes,
                "stand_minutes": stand_minutes,
                "active_energy_kcal": active_energy_kcal,
            }
        )
        return import_apple_health_daily(store, payload)

    @app.get("/v1/events", response_model=list[ProgressEvent])
    def events(
        tenant_id: str = Query(...),
        metric: str | None = Query(None),
        limit: int = Query(100, ge=1, le=1000),
    ) -> list[ProgressEvent]:
        recorded = store.list_events(tenant_id)
        if metric is not None:
            recorded = [event for event in recorded if event.metric == metric]
        return recorded[:limit]

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

    @app.post("/v1/knowledge-records", response_model=KnowledgeRecord)
    def propose_knowledge_record(request: KnowledgeRecordCreate) -> KnowledgeRecord:
        return store.propose_knowledge_record(request)

    @app.post(
        "/v1/knowledge-records/{record_id}/confirm", response_model=KnowledgeRecord
    )
    def confirm_knowledge_record(
        record_id: str, tenant_id: str = Query(...)
    ) -> KnowledgeRecord:
        try:
            return store.confirm_knowledge_record(tenant_id, record_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/v1/knowledge-records", response_model=list[KnowledgeRecord])
    def knowledge_records(
        tenant_id: str = Query(...),
        query: str = Query(""),
        source_title: str | None = Query(None),
        limit: int = Query(20, ge=1, le=100),
    ) -> list[KnowledgeRecord]:
        return store.search_knowledge_records(
            tenant_id, query=query, source_title=source_title, limit=limit
        )

    return app


app = create_app()
