from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from life_os.models import (
    Commitment,
    CommitmentCreate,
    CommitmentStatus,
    CheckInStatus,
    GoalAmendment,
    GoalAmendmentCreate,
    GoalContract,
    GoalContractCreate,
    GoalPlanningSession,
    GoalStatus,
    Memory,
    MemoryCreate,
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
                """
            )

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
                   WHERE tenant_id = ? AND status = ? AND due_at <= ?
                   ORDER BY due_at LIMIT ?""",
                (tenant_id, CheckInStatus.PENDING, _iso(as_of), limit),
            ).fetchall()
        return [ScheduledCheckIn.model_validate_json(row["payload"]) for row in rows]

    def update_check_in_status(
        self, tenant_id: str, check_in_id: str, status: CheckInStatus
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
