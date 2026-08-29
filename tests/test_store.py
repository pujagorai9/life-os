from pathlib import Path

import pytest

from life_os.analytics import build_progress_summary
from life_os.models import (
    CommitmentCreate,
    CommitmentStatus,
    MemoryCreate,
    ProgressEventCreate,
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
