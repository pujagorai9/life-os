from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta

from pywebpush import WebPushException, webpush

from life_os.models import CheckInStatus, ScheduledCheckIn
from life_os.store import LifeOSStore


def notification_key(check_in: ScheduledCheckIn) -> str:
    return f"{check_in.goal_id}:{check_in.prompt_id}"


def _notification_title(check_in: ScheduledCheckIn) -> str:
    if "how much did you pump" in check_in.prompt.lower():
        return "Pumping session"
    routine = re.match(r"^Did you complete '(.+?)'\?", check_in.prompt)
    if routine:
        return routine.group(1)
    return check_in.prompt.split(".", 1)[0][:80]


def notifications_configured() -> bool:
    return bool(
        os.getenv("LIFE_OS_VAPID_PUBLIC_KEY", "").strip()
        and os.getenv("LIFE_OS_VAPID_PRIVATE_KEY", "").strip()
    )


def send_due_notifications(
    store: LifeOSStore, now: datetime
) -> tuple[int, int]:
    if not notifications_configured():
        return 0, 0
    sent = 0
    removed = 0
    private_key = os.environ["LIFE_OS_VAPID_PRIVATE_KEY"].strip()
    subject = os.getenv(
        "LIFE_OS_VAPID_SUBJECT", "mailto:puja.gorai@gmail.com"
    ).strip()
    for subscription in store.list_push_subscriptions():
        selected = set(subscription.notification_keys)
        if not selected:
            continue
        due = store.list_check_ins(
            subscription.tenant_id,
            now - timedelta(minutes=5),
            now + timedelta(seconds=30),
            limit=100,
        )
        for check_in in due:
            if (
                check_in.status is not CheckInStatus.PENDING
                or notification_key(check_in) not in selected
                or store.push_was_delivered(subscription.id, check_in.id)
            ):
                continue
            payload = json.dumps(
                {
                    "title": "Life OS reminder",
                    "body": f"It’s time for {_notification_title(check_in)}.",
                    "url": "/",
                    "tag": f"life-os-{check_in.id}",
                }
            )
            try:
                webpush(
                    subscription_info={
                        "endpoint": subscription.endpoint,
                        "keys": subscription.keys.model_dump(),
                    },
                    data=payload,
                    vapid_private_key=private_key,
                    vapid_claims={"sub": subject},
                    ttl=15 * 60,
                )
            except WebPushException as error:
                status_code = getattr(getattr(error, "response", None), "status_code", None)
                if status_code in {404, 410}:
                    store.delete_push_subscription(
                        subscription.tenant_id, subscription.endpoint
                    )
                    removed += 1
                    break
                continue
            store.mark_push_delivered(subscription.id, check_in.id)
            sent += 1
    return sent, removed
