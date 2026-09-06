from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from life_os.analytics import build_progress_summary
from life_os.models import (
    AgentId,
    CommitmentCreate,
    CommitmentStatus,
    MemoryCreate,
    ProgressEventCreate,
    ScheduledCheckIn,
)
from life_os.store import LifeOSStore


def test_tenant_isolation(tmp_path: Path) -> None:
    store = LifeOSStore(tmp_path / "test.db")
    created = store.create_commitment(
        CommitmentCreate(
            tenant_id="tenant-a",
            domain="professional",
            title="Draft proposal",
            minimum_success="Reviewable draft",
        )
    )
    assert store.list_commitments("tenant-a")[0].id == created.id
    assert store.list_commitments("tenant-b") == []
    with pytest.raises(KeyError):
        store.update_commitment_status("tenant-b", created.id, CommitmentStatus.DONE)


def test_memory_requires_confirmation(tmp_path: Path) -> None:
    store = LifeOSStore(tmp_path / "test.db")
    proposed = store.propose_memory(
        MemoryCreate(
            tenant_id="tenant-a",
            domain="global",
            fact="Prefers concise reminders",
            source="user_statement",
            confidence=1,
        )
    )
    assert store.confirmed_context("tenant-a", "professional") == []
    store.confirm_memory("tenant-a", proposed.id)
    assert store.confirmed_context("tenant-a", "professional")[0].fact == proposed.fact


def test_analytics_use_confirmed_records(tmp_path: Path) -> None:
    store = LifeOSStore(tmp_path / "test.db")
    commitment = store.create_commitment(
        CommitmentCreate(
            tenant_id="tenant-a",
            domain="fitness",
            title="Complete movement session",
            minimum_success="Twenty minutes",
        )
    )
    store.update_commitment_status("tenant-a", commitment.id, CommitmentStatus.DONE)
    store.create_event(
        ProgressEventCreate(
            tenant_id="tenant-a",
            domain="fitness",
            metric="minutes",
            value=25,
            unit="minute",
            source="user_confirmed",
            confidence=1,
        )
    )
    summary = build_progress_summary(store, "tenant-a")
    assert summary.completion_rate == 1
    assert summary.event_totals["fitness.minutes.minute"] == 25


def test_check_in_ranges_compare_actual_instants_across_timezone_offsets(
    tmp_path: Path,
) -> None:
    store = LifeOSStore(tmp_path / "test.db")
    pacific = timezone(timedelta(hours=-7))
    check_ins = [
        ScheduledCheckIn(
            id="due-now",
            tenant_id="tenant-a",
            goal_id="goal-a",
            protocol_id="protocol-a",
            prompt_id="evening-review",
            agent_id=AgentId.CHIEF_ACCOUNTABILITY_OFFICER,
            prompt="Evening review",
            due_at=datetime(2026, 8, 30, 22, 30, tzinfo=pacific),
        ),
        ScheduledCheckIn(
            id="due-later",
            tenant_id="tenant-a",
            goal_id="goal-a",
            protocol_id="protocol-a",
            prompt_id="late-task",
            agent_id=AgentId.CHIEF_ACCOUNTABILITY_OFFICER,
            prompt="Late task",
            due_at=datetime(2026, 8, 30, 23, 30, tzinfo=pacific),
        ),
    ]
    store.replace_pending_check_ins("tenant-a", "goal-a", check_ins)

    due = store.due_check_ins(
        "tenant-a", datetime(2026, 8, 31, 5, 32, tzinfo=timezone.utc)
    )
    assert [item.id for item in due] == ["due-now"]

    selected_day = store.list_check_ins(
        "tenant-a",
        datetime(2026, 8, 30, 7, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 31, 6, 59, 59, tzinfo=timezone.utc),
    )
    assert [item.id for item in selected_day] == ["due-now", "due-later"]
