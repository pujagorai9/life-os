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
    Memory,
    MemoryCreate,
    ProgressEvent,
    ProgressEventCreate,
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
                """
            )

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


def _commitment(row: sqlite3.Row) -> Commitment:
    return Commitment.model_validate(dict(row))


def _event(row: sqlite3.Row) -> ProgressEvent:
    data = dict(row)
    data["metadata"] = json.loads(data["metadata"])
    return ProgressEvent.model_validate(data)


def _memory(row: sqlite3.Row) -> Memory:
    return Memory.model_validate(dict(row))
