from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timezone
from typing import Any

from life_os.connectors.oura import OuraConnector
from life_os.models import GoalStatus, LifeArea, ProgressEventCreate
from life_os.store import LifeOSStore


def sync_oura_daily(
    store: LifeOSStore,
    connector: OuraConnector,
    tenant_id: str,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    """Import Oura daily metrics without duplicating a prior sync."""
    summaries = connector.daily_summaries(start_date, end_date)
    active_fitness_goals = [
        goal
        for goal in store.list_goals(tenant_id, GoalStatus.ACTIVE)
        if goal.domain == LifeArea.FITNESS
    ]
    goal_id = active_fitness_goals[0].id if active_fitness_goals else None
    existing = {
        (event.metric, str(event.metadata.get("oura_key", "")))
        for event in store.list_events(tenant_id)
        if event.source == "oura_api"
    }
    candidates: list[tuple[str, float, str, str, str, float]] = []

    for document in summaries.get("daily_sleep", []):
        _append_score(candidates, document, "oura_sleep_score", "daily_sleep")
    for document in summaries.get("daily_readiness", []):
        _append_score(candidates, document, "oura_readiness_score", "daily_readiness")
    for document in summaries.get("daily_activity", []):
        _append_score(candidates, document, "oura_activity_score", "daily_activity")
        _append_number(candidates, document, "steps", "oura_steps", "step", "daily_activity")
        _append_number(
            candidates,
            document,
            "active_calories",
            "oura_active_calories",
            "kcal",
            "daily_activity",
        )

    sleep_by_day: dict[str, float] = defaultdict(float)
    for document in summaries.get("sleep", []):
        day = str(document.get("day", ""))
        duration = document.get("total_sleep_duration")
        if day and isinstance(duration, (int, float)):
            sleep_by_day[day] += float(duration) / 3600
    for day, hours in sleep_by_day.items():
        candidates.append(("total_sleep_hours", hours, "hour", day, "sleep", 1))
        if hours >= 7:
            candidates.append(("seven_hour_sleep_days", 1, "day", day, "sleep", 1))

    created = 0
    skipped = 0
    imported_days: set[str] = set()
    for metric, value, unit, day, data_type, confidence in candidates:
        oura_key = f"{data_type}:{day}"
        if (metric, oura_key) in existing:
            skipped += 1
            continue
        occurred_at = datetime.combine(
            date.fromisoformat(day), time(hour=12), tzinfo=timezone.utc
        )
        store.create_event(
            ProgressEventCreate(
                tenant_id=tenant_id,
                domain="fitness",
                metric=metric,
                value=value,
                unit=unit,
                source="oura_api",
                confidence=confidence,
                occurred_at=occurred_at,
                goal_id=goal_id,
                metadata={
                    "provider": "oura",
                    "data_type": data_type,
                    "day": day,
                    "oura_key": oura_key,
                },
            )
        )
        existing.add((metric, oura_key))
        imported_days.add(day)
        created += 1
    return {
        "connected": True,
        "created_events": created,
        "skipped_existing": skipped,
        "imported_days": sorted(imported_days),
    }


def _append_score(
    candidates: list[tuple[str, float, str, str, str, float]],
    document: dict[str, Any],
    metric: str,
    data_type: str,
) -> None:
    _append_number(candidates, document, "score", metric, "score", data_type)


def _append_number(
    candidates: list[tuple[str, float, str, str, str, float]],
    document: dict[str, Any],
    field: str,
    metric: str,
    unit: str,
    data_type: str,
) -> None:
    day = str(document.get("day", ""))
    value = document.get(field)
    if day and isinstance(value, (int, float)):
        candidates.append((metric, float(value), unit, day, data_type, 1))
