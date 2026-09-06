from __future__ import annotations

import hashlib
from datetime import datetime, time, timezone

from life_os.models import (
    AppleHealthDailyImport,
    AppleHealthImportResult,
    GoalStatus,
    LifeArea,
    ProgressEventCreate,
)
from life_os.store import LifeOSStore


def import_apple_health_daily(
    store: LifeOSStore, payload: AppleHealthDailyImport
) -> AppleHealthImportResult:
    active_goals = [
        goal
        for goal in store.list_goals(payload.tenant_id, GoalStatus.ACTIVE)
        if goal.domain == LifeArea.FITNESS
    ]
    goal_id = active_goals[0].id if active_goals else None
    occurred_at = datetime.combine(payload.day, time(hour=23, minute=59), timezone.utc)
    metadata = {
        "provider": "apple_health",
        "day": payload.day.isoformat(),
        "reported_timezone": payload.timezone,
    }
    metrics: list[tuple[str, float, str]] = []

    _append(metrics, "apple_active_energy_kcal", payload.active_energy_kcal, "kcal")
    _append(metrics, "apple_move_goal_kcal", payload.move_goal_kcal, "kcal")
    _append(metrics, "apple_exercise_minutes", payload.exercise_minutes, "minute")
    _append(
        metrics,
        "apple_exercise_goal_minutes",
        payload.exercise_goal_minutes if payload.exercise_minutes is not None else None,
        "minute",
    )
    _append(metrics, "apple_stand_hours", payload.stand_hours, "hour")
    _append(
        metrics,
        "apple_stand_goal_hours",
        payload.stand_goal_hours if payload.stand_hours is not None else None,
        "hour",
    )
    _append(metrics, "apple_stand_minutes", payload.stand_minutes, "minute")
    _append(metrics, "cardio_minutes", payload.cardio_minutes, "minute")
    _append(metrics, "strength_minutes", payload.strength_minutes, "minute")

    if payload.active_energy_kcal is not None and payload.move_goal_kcal is not None:
        metrics.append(
            (
                "apple_move_ring_closed",
                float(payload.active_energy_kcal >= payload.move_goal_kcal),
                "completion",
            )
        )
    if payload.exercise_minutes is not None:
        metrics.append(
            (
                "apple_exercise_ring_closed",
                float(payload.exercise_minutes >= payload.exercise_goal_minutes),
                "completion",
            )
        )
    if payload.stand_hours is not None:
        stand_closed = payload.stand_hours >= payload.stand_goal_hours
        metrics.extend(
            [
                ("apple_stand_ring_closed", float(stand_closed), "completion"),
                ("twelve_stand_hour_days", float(stand_closed), "day"),
            ]
        )
    if (
        payload.active_energy_kcal is not None
        and payload.move_goal_kcal is not None
        and payload.exercise_minutes is not None
        and payload.stand_hours is not None
    ):
        all_closed = (
            payload.active_energy_kcal >= payload.move_goal_kcal
            and payload.exercise_minutes >= payload.exercise_goal_minutes
            and payload.stand_hours >= payload.stand_goal_hours
        )
        metrics.append(("apple_all_rings_closed", float(all_closed), "completion"))

    counts = {"created": 0, "updated": 0, "unchanged": 0}
    imported: list[str] = []
    for metric, value, unit in metrics:
        _, status = store.upsert_event_by_source_key(
            ProgressEventCreate(
                tenant_id=payload.tenant_id,
                domain="fitness",
                metric=metric,
                value=value,
                unit=unit,
                source="apple_health_shortcut",
                confidence=1,
                occurred_at=occurred_at,
                goal_id=goal_id,
                metadata=metadata,
            ),
            f"daily:{payload.day.isoformat()}:{metric}",
        )
        counts[status] += 1
        imported.append(metric)

    for workout in payload.workouts:
        workout_key = workout.workout_id or hashlib.sha256(
            f"{workout.activity_type}|{workout.started_at.isoformat()}".encode()
        ).hexdigest()[:24]
        for metric, value, unit in (
            ("apple_workout_minutes", workout.duration_minutes, "minute"),
            ("structured_workouts", 1.0, "workout"),
        ):
            _, status = store.upsert_event_by_source_key(
                ProgressEventCreate(
                    tenant_id=payload.tenant_id,
                    domain="fitness",
                    metric=metric,
                    value=value,
                    unit=unit,
                    source="apple_health_shortcut",
                    confidence=1,
                    occurred_at=workout.started_at,
                    goal_id=goal_id,
                    metadata={
                        **metadata,
                        "activity_type": workout.activity_type,
                        "active_energy_kcal": workout.active_energy_kcal,
                    },
                ),
                f"workout:{workout_key}:{metric}",
            )
            counts[status] += 1
            imported.append(metric)

    return AppleHealthImportResult(
        created_events=counts["created"],
        updated_events=counts["updated"],
        unchanged_events=counts["unchanged"],
        imported_metrics=sorted(set(imported)),
    )


def _append(
    metrics: list[tuple[str, float, str]], metric: str, value: float | None, unit: str
) -> None:
    if value is not None:
        metrics.append((metric, value, unit))
