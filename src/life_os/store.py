from __future__ import annotations

import json
import os
import sqlite3
import uuid
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path

from life_os.models import (
    Commitment,
    CommitmentCreate,
    CommitmentStatus,
    CheckInStatus,
    CheckInOutcome,
    CheckInPhoto,
    ExpenseRecord,
    FinanceCategoryTotal,
    FinanceCurrencySummary,
    FinanceDailyReport,
    FinanceEmailResultCreate,
    PhotoAnalysis,
    PhotoAnalysisStatus,
    GoalAmendment,
    GoalAmendmentCreate,
    GoalContract,
    GoalContractCreate,
    GoalPlanningSession,
    GoalStatus,
    Memory,
    MemoryCreate,
    KnowledgeRecord,
    KnowledgeRecordCreate,
    OnboardingSelection,
    ProgressEvent,
    ProgressEventCreate,
    ScheduledCheckIn,
    TrackingProtocol,
    utc_now,
)


class LifeOSStore:
    def __init__(self, path: str | Path = "life_os.db") -> None:
        self.path = str(path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS commitments (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    title TEXT NOT NULL,
                    minimum_success TEXT NOT NULL,
                    due_at TEXT,
                    goal_id TEXT,
                    evidence_policy TEXT NOT NULL,
                    reminder_policy TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_commitments_tenant
                    ON commitments (tenant_id, status);

                CREATE TABLE IF NOT EXISTS progress_events (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    value REAL NOT NULL,
                    unit TEXT NOT NULL,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    occurred_at TEXT NOT NULL,
                    goal_id TEXT,
                    metadata TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_tenant
                    ON progress_events (tenant_id, occurred_at);

                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    fact TEXT NOT NULL,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    expires_at TEXT,
                    confirmed INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memories_tenant
                    ON memories (tenant_id, domain, confirmed);

                CREATE TABLE IF NOT EXISTS onboarding_selections (
                    tenant_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS goals (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    series_id TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    owner_agent TEXT NOT NULL,
                    status TEXT NOT NULL,
                    cycle_number INTEGER NOT NULL,
                    version INTEGER NOT NULL,
                    review_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_goals_tenant
                    ON goals (tenant_id, status, review_at);
                CREATE INDEX IF NOT EXISTS idx_goals_series
                    ON goals (tenant_id, series_id, cycle_number);

                CREATE TABLE IF NOT EXISTS goal_amendments (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    goal_id TEXT NOT NULL,
                    effective_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_goal_amendments
                    ON goal_amendments (tenant_id, goal_id, effective_at);

                CREATE TABLE IF NOT EXISTS tracking_protocols (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    goal_id TEXT NOT NULL,
                    goal_version INTEGER NOT NULL,
                    approved INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tracking_protocols
                    ON tracking_protocols (tenant_id, goal_id, created_at);

                CREATE TABLE IF NOT EXISTS scheduled_check_ins (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    goal_id TEXT NOT NULL,
                    protocol_id TEXT NOT NULL,
                    due_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_check_ins_due
                    ON scheduled_check_ins (tenant_id, status, due_at);

                CREATE TABLE IF NOT EXISTS check_in_photos (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    check_in_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_check_in_photos
                    ON check_in_photos (tenant_id, check_in_id, created_at);

                CREATE TABLE IF NOT EXISTS goal_planning_sessions (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    area TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_planning_sessions
                    ON goal_planning_sessions (tenant_id, status, updated_at);

                CREATE TABLE IF NOT EXISTS knowledge_records (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    goal_id TEXT,
                    source_title TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    studied_at TEXT NOT NULL,
                    confirmed INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_knowledge_records
                    ON knowledge_records (tenant_id, confirmed, studied_at);

                CREATE TABLE IF NOT EXISTS finance_email_results (
                    tenant_id TEXT NOT NULL,
                    source_message_id TEXT NOT NULL,
                    message_at TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    processed_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, source_message_id)
                );
                CREATE INDEX IF NOT EXISTS idx_finance_email_results_time
                    ON finance_email_results (tenant_id, message_at);

                CREATE TABLE IF NOT EXISTS expense_records (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    source_message_id TEXT NOT NULL,
                    transaction_at TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    category TEXT NOT NULL,
                    amount REAL NOT NULL,
                    kind TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_expense_source_message
                    ON expense_records (tenant_id, source_message_id);
                CREATE INDEX IF NOT EXISTS idx_expense_records_time
                    ON expense_records (tenant_id, transaction_at);
                """
            )

    def save_finance_email_result(
        self, request: FinanceEmailResultCreate
    ) -> ExpenseRecord | None:
        processed_at = utc_now()
        expense: ExpenseRecord | None = None
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO finance_email_results
                   (tenant_id, source_message_id, message_at, outcome, payload, processed_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(tenant_id, source_message_id) DO UPDATE SET
                     message_at = excluded.message_at,
                     outcome = excluded.outcome,
                     payload = excluded.payload,
                     processed_at = excluded.processed_at""",
                (
                    request.tenant_id,
                    request.source_message_id,
                    _iso(request.message_at),
                    request.outcome,
                    _json(request),
                    _iso(processed_at),
                ),
            )
            if request.outcome not in {"purchase", "refund"}:
                connection.execute(
                    """DELETE FROM expense_records
                       WHERE tenant_id = ? AND source_message_id = ?""",
                    (request.tenant_id, request.source_message_id),
                )
                return None

            prior = connection.execute(
                """SELECT id, created_at FROM expense_records
                   WHERE tenant_id = ? AND source_message_id = ?""",
                (request.tenant_id, request.source_message_id),
            ).fetchone()
            expense = ExpenseRecord(
                id=prior["id"] if prior else str(uuid.uuid4()),
                tenant_id=request.tenant_id,
                source_message_id=request.source_message_id,
                source_account_id=request.source_account_id,
                source_account_email=request.source_account_email,
                household_member=request.household_member,
                transaction_at=request.transaction_at,
                merchant=request.merchant.strip(),
                category=request.category.strip().lower().replace(" ", "_"),
                amount=request.amount,
                currency=request.currency.strip().upper(),
                kind=request.outcome,
                confidence=request.confidence,
                created_at=(
                    datetime.fromisoformat(prior["created_at"])
                    if prior
                    else processed_at
                ),
            )
            connection.execute(
                """INSERT INTO expense_records
                   (id, tenant_id, source_message_id, transaction_at, currency,
                    category, amount, kind, payload, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(tenant_id, source_message_id) DO UPDATE SET
                     transaction_at = excluded.transaction_at,
                     currency = excluded.currency,
                     category = excluded.category,
                     amount = excluded.amount,
                     kind = excluded.kind,
                     payload = excluded.payload""",
                (
                    expense.id,
                    expense.tenant_id,
                    expense.source_message_id,
                    _iso(expense.transaction_at),
                    expense.currency,
                    expense.category,
                    expense.amount,
                    expense.kind,
                    _json(expense),
                    _iso(expense.created_at),
                ),
            )
        return expense

    def finance_daily_report(
        self, tenant_id: str, day: date, timezone
    ) -> FinanceDailyReport:
        with self._connect() as connection:
            expense_rows = connection.execute(
                """SELECT payload FROM expense_records
                   WHERE tenant_id = ? ORDER BY transaction_at""",
                (tenant_id,),
            ).fetchall()
            email_rows = connection.execute(
                """SELECT message_at FROM finance_email_results
                   WHERE tenant_id = ?""",
                (tenant_id,),
            ).fetchall()
        expenses = [
            ExpenseRecord.model_validate_json(row["payload"])
            for row in expense_rows
            if datetime.fromisoformat(
                json.loads(row["payload"])["transaction_at"]
            ).astimezone(timezone).date()
            == day
        ]
        processed_count = sum(
            datetime.fromisoformat(row["message_at"]).astimezone(timezone).date()
            == day
            for row in email_rows
        )
        grouped: dict[str, dict[str, object]] = {}
        for expense in expenses:
            bucket = grouped.setdefault(
                expense.currency,
                {"spent": 0.0, "refunded": 0.0, "categories": {}},
            )
            amount_key = "refunded" if expense.kind == "refund" else "spent"
            bucket[amount_key] = float(bucket[amount_key]) + expense.amount
            signed = -expense.amount if expense.kind == "refund" else expense.amount
            categories = bucket["categories"]
            categories[expense.category] = categories.get(expense.category, 0.0) + signed
        summaries = [
            FinanceCurrencySummary(
                currency=currency,
                total_spent=round(float(values["spent"]), 2),
                total_refunded=round(float(values["refunded"]), 2),
                net_spent=round(
                    float(values["spent"]) - float(values["refunded"]), 2
                ),
                categories=[
                    FinanceCategoryTotal(category=category, amount=round(amount, 2))
                    for category, amount in sorted(
                        values["categories"].items(), key=lambda item: -item[1]
                    )
                ],
            )
            for currency, values in sorted(grouped.items())
        ]
        return FinanceDailyReport(
            day=day,
            purchase_count=sum(expense.kind == "purchase" for expense in expenses),
            processed_email_count=processed_count,
            summaries=summaries,
            transactions=expenses,
        )

    def propose_knowledge_record(self, request: KnowledgeRecordCreate) -> KnowledgeRecord:
        record = KnowledgeRecord(id=str(uuid.uuid4()), **request.model_dump())
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO knowledge_records
                   (id, tenant_id, goal_id, source_title, topic, studied_at,
                    confirmed, payload, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.id,
                    record.tenant_id,
                    record.goal_id,
                    record.source_title,
                    record.topic,
                    _iso(record.studied_at),
                    int(record.confirmed),
                    _json(record),
                    _iso(record.created_at),
                ),
            )
        return record

    def confirm_knowledge_record(
        self, tenant_id: str, record_id: str
    ) -> KnowledgeRecord:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT payload FROM knowledge_records
                   WHERE tenant_id = ? AND id = ?""",
                (tenant_id, record_id),
            ).fetchone()
            if row is None:
                raise KeyError("Knowledge record not found")
            record = KnowledgeRecord.model_validate_json(row["payload"])
            record.confirmed = True
            connection.execute(
                """UPDATE knowledge_records SET confirmed = 1, payload = ?
                   WHERE tenant_id = ? AND id = ?""",
                (_json(record), tenant_id, record_id),
            )
        return record

    def search_knowledge_records(
        self,
        tenant_id: str,
        query: str = "",
        source_title: str | None = None,
        limit: int = 20,
    ) -> list[KnowledgeRecord]:
        sql = "SELECT payload FROM knowledge_records WHERE tenant_id = ? AND confirmed = 1"
        values: list[object] = [tenant_id]
        if source_title:
            sql += " AND lower(source_title) = lower(?)"
            values.append(source_title)
        sql += " ORDER BY studied_at DESC"
        with self._connect() as connection:
            rows = connection.execute(sql, values).fetchall()
        records = [KnowledgeRecord.model_validate_json(row["payload"]) for row in rows]
        tokens = {token for token in query.casefold().split() if len(token) >= 3}
        if not tokens:
            return records[:limit]

        def score(record: KnowledgeRecord) -> int:
            searchable = " ".join(
                [
                    record.source_title,
                    record.topic,
                    record.expected_scope,
                    record.user_summary,
                    record.interview_recall,
                    *record.strengths,
                    *record.gaps,
                    *record.tags,
                ]
            ).casefold()
            return sum(token in searchable for token in tokens)

        ranked = sorted(
            ((score(record), record) for record in records),
            key=lambda item: (item[0], item[1].studied_at),
            reverse=True,
        )
        return [record for relevance, record in ranked if relevance > 0][:limit]

    def save_planning_session(self, session: GoalPlanningSession) -> GoalPlanningSession:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO goal_planning_sessions
                   (id, tenant_id, area, status, payload, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET status = excluded.status,
                     payload = excluded.payload, updated_at = excluded.updated_at
                   WHERE goal_planning_sessions.tenant_id = excluded.tenant_id""",
                (
                    session.id,
                    session.tenant_id,
                    session.area,
                    session.status,
                    _json(session),
                    _iso(session.created_at),
                    _iso(session.updated_at),
                ),
            )
        return session

    def get_planning_session(self, tenant_id: str, session_id: str) -> GoalPlanningSession:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT payload FROM goal_planning_sessions
                   WHERE tenant_id = ? AND id = ?""",
                (tenant_id, session_id),
            ).fetchone()
        if row is None:
            raise KeyError("Planning session not found")
        return GoalPlanningSession.model_validate_json(row["payload"])

    def list_planning_sessions(self, tenant_id: str) -> list[GoalPlanningSession]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT payload FROM goal_planning_sessions
                   WHERE tenant_id = ? ORDER BY updated_at DESC""",
                (tenant_id,),
            ).fetchall()
        return [GoalPlanningSession.model_validate_json(row["payload"]) for row in rows]

    def save_onboarding_selection(self, selection: OnboardingSelection) -> OnboardingSelection:
        payload = _json(selection)
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO onboarding_selections (tenant_id, payload, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(tenant_id) DO UPDATE SET
                     payload = excluded.payload, updated_at = excluded.updated_at""",
                (selection.tenant_id, payload, _iso(selection.completed_at)),
            )
        return selection

    def get_onboarding_selection(self, tenant_id: str) -> OnboardingSelection | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM onboarding_selections WHERE tenant_id = ?", (tenant_id,)
            ).fetchone()
        return OnboardingSelection.model_validate_json(row["payload"]) if row else None

    def create_goal(self, request: GoalContractCreate) -> GoalContract:
        now = utc_now()
        goal_id = str(uuid.uuid4())
        goal = GoalContract(
            id=goal_id,
            series_id=goal_id,
            **request.model_dump(),
            created_at=now,
            updated_at=now,
        )
        self._insert_goal(goal)
        return goal

    def _insert_goal(self, goal: GoalContract) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO goals
                   (id, tenant_id, series_id, domain, owner_agent, status,
                    cycle_number, version, review_at, payload, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    goal.id,
                    goal.tenant_id,
                    goal.series_id,
                    goal.domain,
                    goal.owner_agent,
                    goal.status,
                    goal.cycle_number,
                    goal.version,
                    _iso(goal.review_at),
                    _json(goal),
                    _iso(goal.created_at),
                    _iso(goal.updated_at),
                ),
            )

    def get_goal(self, tenant_id: str, goal_id: str) -> GoalContract:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM goals WHERE tenant_id = ? AND id = ?",
                (tenant_id, goal_id),
            ).fetchone()
        if row is None:
            raise KeyError("Goal not found")
        return GoalContract.model_validate_json(row["payload"])

    def list_goals(self, tenant_id: str, status: GoalStatus | None = None) -> list[GoalContract]:
        query = "SELECT payload FROM goals WHERE tenant_id = ?"
        values: list[object] = [tenant_id]
        if status is not None:
            query += " AND status = ?"
            values.append(status)
        query += " ORDER BY created_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [GoalContract.model_validate_json(row["payload"]) for row in rows]

    def set_goal_status(
        self, tenant_id: str, goal_id: str, status: GoalStatus
    ) -> GoalContract:
        goal = self.get_goal(tenant_id, goal_id)
        goal.status = status
        goal.updated_at = utc_now()
        self._update_goal(goal)
        return goal

    def amend_goal(
        self, tenant_id: str, goal_id: str, request: GoalAmendmentCreate
    ) -> tuple[GoalContract, GoalAmendment]:
        goal = self.get_goal(tenant_id, goal_id)
        if request.tenant_id != tenant_id:
            raise ValueError("Tenant mismatch")
        protected = {
            "id", "tenant_id", "series_id", "previous_cycle_id", "cycle_number",
            "version", "status", "created_at", "updated_at",
        }
        if protected.intersection(request.changes):
            raise ValueError("Amendment contains protected fields")
        data = goal.model_dump(mode="json")
        data.update(request.changes)
        data["version"] = goal.version + 1
        data["updated_at"] = utc_now().isoformat()
        revised = GoalContract.model_validate(data)
        if revised.review_at <= revised.start_at:
            raise ValueError("review_at must be after start_at")
        amendment = GoalAmendment(
            id=str(uuid.uuid4()),
            goal_id=goal.id,
            from_version=goal.version,
            to_version=revised.version,
            **request.model_dump(),
        )
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO goal_amendments
                   (id, tenant_id, goal_id, effective_at, payload) VALUES (?, ?, ?, ?, ?)""",
                (
                    amendment.id,
                    tenant_id,
                    goal.id,
                    _iso(amendment.effective_at),
                    _json(amendment),
                ),
            )
        self._update_goal(revised)
        return revised, amendment

    def list_goal_amendments(self, tenant_id: str, goal_id: str) -> list[GoalAmendment]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT payload FROM goal_amendments
                   WHERE tenant_id = ? AND goal_id = ? ORDER BY effective_at""",
                (tenant_id, goal_id),
            ).fetchall()
        return [GoalAmendment.model_validate_json(row["payload"]) for row in rows]

    def _update_goal(self, goal: GoalContract) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE goals SET domain = ?, owner_agent = ?, status = ?,
                   version = ?, review_at = ?, payload = ?, updated_at = ?
                   WHERE tenant_id = ? AND id = ?""",
                (
                    goal.domain,
                    goal.owner_agent,
                    goal.status,
                    goal.version,
                    _iso(goal.review_at),
                    _json(goal),
                    _iso(goal.updated_at),
                    goal.tenant_id,
                    goal.id,
                ),
            )
        if cursor.rowcount != 1:
            raise KeyError("Goal not found")

    def renew_goal(
        self,
        tenant_id: str,
        goal_id: str,
        start_at: datetime,
        review_at: datetime,
        changes: dict,
    ) -> GoalContract:
        previous = self.get_goal(tenant_id, goal_id)
        if review_at <= start_at:
            raise ValueError("review_at must be after start_at")
        data = previous.model_dump(mode="json")
        protected = {
            "id", "tenant_id", "series_id", "previous_cycle_id", "cycle_number",
            "version", "status", "created_at", "updated_at", "start_at", "review_at",
        }
        if protected.intersection(changes):
            raise ValueError("Renewal contains protected fields")
        data.update(changes)
        now = utc_now()
        data.update(
            id=str(uuid.uuid4()),
            previous_cycle_id=previous.id,
            cycle_number=previous.cycle_number + 1,
            version=1,
            status=GoalStatus.DRAFT,
            start_at=_iso(start_at),
            review_at=_iso(review_at),
            created_at=_iso(now),
            updated_at=_iso(now),
        )
        renewed = GoalContract.model_validate(data)
        self._insert_goal(renewed)
        return renewed

    def save_tracking_protocol(self, protocol: TrackingProtocol) -> TrackingProtocol:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO tracking_protocols
                   (id, tenant_id, goal_id, goal_version, approved, payload, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    protocol.id,
                    protocol.tenant_id,
                    protocol.goal_id,
                    protocol.goal_version,
                    int(protocol.approved),
                    _json(protocol),
                    _iso(protocol.created_at),
                ),
            )
        return protocol

    def get_tracking_protocol(self, tenant_id: str, goal_id: str) -> TrackingProtocol:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT payload FROM tracking_protocols
                   WHERE tenant_id = ? AND goal_id = ? ORDER BY created_at DESC LIMIT 1""",
                (tenant_id, goal_id),
            ).fetchone()
        if row is None:
            raise KeyError("Tracking protocol not found")
        return TrackingProtocol.model_validate_json(row["payload"])

    def set_tracking_protocol_approval(
        self, tenant_id: str, goal_id: str, approved: bool
    ) -> TrackingProtocol:
        protocol = self.get_tracking_protocol(tenant_id, goal_id)
        protocol.approved = approved
        with self._connect() as connection:
            connection.execute(
                """UPDATE tracking_protocols SET approved = ?, payload = ?
                   WHERE tenant_id = ? AND id = ?""",
                (int(approved), _json(protocol), tenant_id, protocol.id),
            )
        return protocol

    def replace_pending_check_ins(
        self, tenant_id: str, goal_id: str, check_ins: list[ScheduledCheckIn]
    ) -> list[ScheduledCheckIn]:
        with self._connect() as connection:
            connection.execute(
                """DELETE FROM scheduled_check_ins
                   WHERE tenant_id = ? AND goal_id = ? AND status = ?""",
                (tenant_id, goal_id, CheckInStatus.PENDING),
            )
            connection.executemany(
                """INSERT INTO scheduled_check_ins
                   (id, tenant_id, goal_id, protocol_id, due_at, status, payload, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        item.id,
                        item.tenant_id,
                        item.goal_id,
                        item.protocol_id,
                        _iso(item.due_at),
                        item.status,
                        _json(item),
                        _iso(item.created_at),
                    )
                    for item in check_ins
                ],
            )
        return check_ins

    def due_check_ins(
        self, tenant_id: str, as_of: datetime, limit: int = 100
    ) -> list[ScheduledCheckIn]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT payload FROM scheduled_check_ins
                   WHERE tenant_id = ? AND status = ?""",
                (tenant_id, CheckInStatus.PENDING),
            ).fetchall()
        check_ins = [
            ScheduledCheckIn.model_validate_json(row["payload"]) for row in rows
        ]
        return sorted(
            (item for item in check_ins if item.due_at <= as_of),
            key=lambda item: item.due_at,
        )[:limit]

    def list_check_ins(
        self,
        tenant_id: str,
        start_at: datetime,
        end_at: datetime,
        limit: int = 500,
    ) -> list[ScheduledCheckIn]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT payload FROM scheduled_check_ins
                   WHERE tenant_id = ?""",
                (tenant_id,),
            ).fetchall()
        check_ins = [
            ScheduledCheckIn.model_validate_json(row["payload"]) for row in rows
        ]
        return sorted(
            (item for item in check_ins if start_at <= item.due_at <= end_at),
            key=lambda item: item.due_at,
        )[:limit]

    def get_check_in(self, tenant_id: str, check_in_id: str) -> ScheduledCheckIn:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT payload FROM scheduled_check_ins
                   WHERE tenant_id = ? AND id = ?""",
                (tenant_id, check_in_id),
            ).fetchone()
        if row is None:
            raise KeyError("Check-in not found")
        return ScheduledCheckIn.model_validate_json(row["payload"])

    def save_check_in_photo(
        self, photo: CheckInPhoto, image: bytes, extension: str
    ) -> CheckInPhoto:
        database_path = Path(self.path).resolve()
        attachment_root = database_path.parent / f"{database_path.stem}_attachments"
        tenant_directory = attachment_root / photo.storage_key.split("/", 1)[0]
        tenant_directory.mkdir(parents=True, exist_ok=True)
        os.chmod(attachment_root, 0o700)
        os.chmod(tenant_directory, 0o700)
        target = attachment_root / photo.storage_key
        if target.suffix != f".{extension}" or target.parent != tenant_directory:
            raise ValueError("Invalid photo storage key")
        try:
            target.write_bytes(image)
            os.chmod(target, 0o600)
            with self._connect() as connection:
                connection.execute(
                    """INSERT INTO check_in_photos
                       (id, tenant_id, check_in_id, payload, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        photo.id,
                        photo.tenant_id,
                        photo.check_in_id,
                        _json(photo),
                        _iso(photo.created_at),
                    ),
                )
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return photo

    def list_check_in_photos(
        self, tenant_id: str, check_in_id: str
    ) -> list[CheckInPhoto]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT payload FROM check_in_photos
                   WHERE tenant_id = ? AND check_in_id = ? ORDER BY created_at""",
                (tenant_id, check_in_id),
            ).fetchall()
        return [CheckInPhoto.model_validate_json(row["payload"]) for row in rows]

    def get_check_in_photo(
        self, tenant_id: str, check_in_id: str, photo_id: str
    ) -> CheckInPhoto:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT payload FROM check_in_photos
                   WHERE tenant_id = ? AND check_in_id = ? AND id = ?""",
                (tenant_id, check_in_id, photo_id),
            ).fetchone()
        if row is None:
            raise KeyError("Check-in photo not found")
        return CheckInPhoto.model_validate_json(row["payload"])

    def read_check_in_photo(self, photo: CheckInPhoto) -> bytes:
        database_path = Path(self.path).resolve()
        attachment_root = (
            database_path.parent / f"{database_path.stem}_attachments"
        ).resolve()
        target = (attachment_root / photo.storage_key).resolve()
        if not target.is_relative_to(attachment_root):
            raise ValueError("Invalid photo storage key")
        return target.read_bytes()

    def update_check_in_photo_analysis(
        self, photo: CheckInPhoto, analysis: PhotoAnalysis
    ) -> CheckInPhoto:
        photo.analysis = analysis
        photo.analysis_status = PhotoAnalysisStatus.COMPLETED
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE check_in_photos SET payload = ?
                   WHERE tenant_id = ? AND check_in_id = ? AND id = ?""",
                (_json(photo), photo.tenant_id, photo.check_in_id, photo.id),
            )
        if cursor.rowcount != 1:
            raise KeyError("Check-in photo not found")
        return photo

    def update_check_in_status(
        self,
        tenant_id: str,
        check_in_id: str,
        status: CheckInStatus,
        outcome: CheckInOutcome | None = None,
    ) -> ScheduledCheckIn:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT payload FROM scheduled_check_ins
                   WHERE tenant_id = ? AND id = ?""",
                (tenant_id, check_in_id),
            ).fetchone()
            if row is None:
                raise KeyError("Check-in not found")
            item = ScheduledCheckIn.model_validate_json(row["payload"])
            item.status = status
            item.status_updated_at = utc_now()
            item.outcome = outcome if status == CheckInStatus.RESPONDED else None
            item.completed_at = (
                item.status_updated_at if status == CheckInStatus.RESPONDED else None
            )
            connection.execute(
                """UPDATE scheduled_check_ins SET status = ?, payload = ?
                   WHERE tenant_id = ? AND id = ?""",
                (status, _json(item), tenant_id, check_in_id),
            )
        return item

    def create_commitment(self, request: CommitmentCreate) -> Commitment:
        now = utc_now()
        commitment = Commitment(id=str(uuid.uuid4()), **request.model_dump(), created_at=now, updated_at=now)
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO commitments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    commitment.id,
                    commitment.tenant_id,
                    commitment.domain,
                    commitment.title,
                    commitment.minimum_success,
                    _iso(commitment.due_at),
                    commitment.goal_id,
                    commitment.evidence_policy,
                    commitment.reminder_policy,
                    commitment.status,
                    _iso(commitment.created_at),
                    _iso(commitment.updated_at),
                ),
            )
        return commitment

    def update_commitment_status(
        self, tenant_id: str, commitment_id: str, status: CommitmentStatus
    ) -> Commitment:
        updated_at = utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE commitments SET status = ?, updated_at = ?
                   WHERE tenant_id = ? AND id = ?""",
                (status, _iso(updated_at), tenant_id, commitment_id),
            )
            if cursor.rowcount != 1:
                raise KeyError("Commitment not found")
        return self.get_commitment(tenant_id, commitment_id)

    def get_commitment(self, tenant_id: str, commitment_id: str) -> Commitment:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM commitments WHERE tenant_id = ? AND id = ?",
                (tenant_id, commitment_id),
            ).fetchone()
        if row is None:
            raise KeyError("Commitment not found")
        return _commitment(row)

    def list_commitments(self, tenant_id: str) -> list[Commitment]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM commitments WHERE tenant_id = ? ORDER BY created_at DESC",
                (tenant_id,),
            ).fetchall()
        return [_commitment(row) for row in rows]

    def create_event(self, request: ProgressEventCreate) -> ProgressEvent:
        event = ProgressEvent(id=str(uuid.uuid4()), **request.model_dump())
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO progress_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event.id,
                    event.tenant_id,
                    event.domain,
                    event.metric,
                    event.value,
                    event.unit,
                    event.source,
                    event.confidence,
                    _iso(event.occurred_at),
                    event.goal_id,
                    json.dumps(event.metadata),
                ),
            )
        return event

    def upsert_event_by_source_key(
        self, request: ProgressEventCreate, source_key: str
    ) -> tuple[ProgressEvent, str]:
        """Create or update one provider-owned event without duplicating imports."""
        metadata = {**request.metadata, "source_key": source_key}
        request = request.model_copy(update={"metadata": metadata})
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM progress_events
                   WHERE tenant_id = ? AND source = ? AND metric = ?
                     AND json_extract(metadata, '$.source_key') = ?
                   LIMIT 1""",
                (request.tenant_id, request.source, request.metric, source_key),
            ).fetchone()
            if row is None:
                event = ProgressEvent(id=str(uuid.uuid4()), **request.model_dump())
                connection.execute(
                    """INSERT INTO progress_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        event.id,
                        event.tenant_id,
                        event.domain,
                        event.metric,
                        event.value,
                        event.unit,
                        event.source,
                        event.confidence,
                        _iso(event.occurred_at),
                        event.goal_id,
                        json.dumps(event.metadata),
                    ),
                )
                return event, "created"

            current = _event(row)
            if current.model_dump() == ProgressEvent(id=current.id, **request.model_dump()).model_dump():
                return current, "unchanged"
            event = ProgressEvent(id=current.id, **request.model_dump())
            connection.execute(
                """UPDATE progress_events
                   SET domain = ?, value = ?, unit = ?, confidence = ?, occurred_at = ?,
                       goal_id = ?, metadata = ?
                   WHERE id = ?""",
                (
                    event.domain,
                    event.value,
                    event.unit,
                    event.confidence,
                    _iso(event.occurred_at),
                    event.goal_id,
                    json.dumps(event.metadata),
                    event.id,
                ),
            )
        return event, "updated"

    def list_events(self, tenant_id: str) -> list[ProgressEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM progress_events WHERE tenant_id = ? ORDER BY occurred_at DESC",
                (tenant_id,),
            ).fetchall()
        return [_event(row) for row in rows]

    def propose_memory(self, request: MemoryCreate) -> Memory:
        memory = Memory(id=str(uuid.uuid4()), **request.model_dump())
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    memory.id,
                    memory.tenant_id,
                    memory.domain,
                    memory.fact,
                    memory.source,
                    memory.confidence,
                    _iso(memory.expires_at),
                    int(memory.confirmed),
                    _iso(memory.created_at),
                ),
            )
        return memory

    def confirm_memory(self, tenant_id: str, memory_id: str) -> Memory:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE memories SET confirmed = 1 WHERE tenant_id = ? AND id = ?",
                (tenant_id, memory_id),
            )
            if cursor.rowcount != 1:
                raise KeyError("Memory not found")
            row = connection.execute(
                "SELECT * FROM memories WHERE tenant_id = ? AND id = ?",
                (tenant_id, memory_id),
            ).fetchone()
        return _memory(row)

    def confirmed_context(self, tenant_id: str, domain: str) -> list[Memory]:
        now = _iso(utc_now())
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM memories
                   WHERE tenant_id = ? AND confirmed = 1
                     AND domain IN (?, 'global')
                     AND (expires_at IS NULL OR expires_at > ?)
                   ORDER BY created_at DESC""",
                (tenant_id, domain, now),
            ).fetchall()
        return [_memory(row) for row in rows]


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _json(value: object) -> str:
    if hasattr(value, "model_dump"):
        return json.dumps(value.model_dump(mode="json"))
    return json.dumps(value)


def _commitment(row: sqlite3.Row) -> Commitment:
    return Commitment.model_validate(dict(row))


def _event(row: sqlite3.Row) -> ProgressEvent:
    data = dict(row)
    data["metadata"] = json.loads(data["metadata"])
    return ProgressEvent.model_validate(data)


def _memory(row: sqlite3.Row) -> Memory:
    return Memory.model_validate(dict(row))
