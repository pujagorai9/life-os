from __future__ import annotations

from collections import Counter, defaultdict

from life_os.models import CommitmentStatus, ProgressSummary
from life_os.store import LifeOSStore


def build_progress_summary(store: LifeOSStore, tenant_id: str) -> ProgressSummary:
    commitments = store.list_commitments(tenant_id)
    status_counts = Counter(str(item.status) for item in commitments)
    done = status_counts[CommitmentStatus.DONE]
    total = len(commitments)

    event_totals: dict[str, float] = defaultdict(float)
    for event in store.list_events(tenant_id):
        event_totals[f"{event.domain}.{event.metric}.{event.unit}"] += event.value

    return ProgressSummary(
        tenant_id=tenant_id,
        commitments_total=total,
        commitments_done=done,
        completion_rate=(done / total if total else 0.0),
        by_status=dict(status_counts),
        event_totals=dict(event_totals),
    )
