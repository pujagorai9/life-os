from datetime import datetime, timezone
from pathlib import Path

from life_os.models import (
    AgentId,
    PushSubscriptionCreate,
    ScheduledCheckIn,
)
from life_os.notifications import notification_key, send_due_notifications
from life_os.store import LifeOSStore


def test_selected_task_notification_is_delivered_only_once(
    tmp_path: Path, monkeypatch
) -> None:
    store = LifeOSStore(tmp_path / "notifications.db")
    due_at = datetime(2030, 1, 1, 9, 30, tzinfo=timezone.utc)
    check_in = ScheduledCheckIn(
        id="check-in-a",
        tenant_id="tenant-a",
        goal_id="goal-a",
        protocol_id="protocol-a",
        prompt_id="prompt-a",
        agent_id=AgentId.OPERATIONS_MANAGER,
        prompt="How much did you pump in ml for the 9:30 AM session?",
        due_at=due_at,
    )
    store.replace_pending_check_ins("tenant-a", "goal-a", [check_in])
    subscription = store.upsert_push_subscription(
        PushSubscriptionCreate(
            tenant_id="tenant-a",
            endpoint="https://push.example/subscription-a",
            keys={"p256dh": "device-public-key", "auth": "device-auth"},
            notification_keys=[notification_key(check_in)],
            timezone="UTC",
        )
    )
    delivered: list[dict] = []
    monkeypatch.setenv("LIFE_OS_VAPID_PUBLIC_KEY", "public-key")
    monkeypatch.setenv("LIFE_OS_VAPID_PRIVATE_KEY", "private-key")
    monkeypatch.setattr(
        "life_os.notifications.webpush",
        lambda **kwargs: delivered.append(kwargs),
    )

    first = send_due_notifications(store, due_at)
    second = send_due_notifications(store, due_at)

    assert first == (1, 0)
    assert second == (0, 0)
    assert len(delivered) == 1
    assert store.push_was_delivered(subscription.id, check_in.id)
