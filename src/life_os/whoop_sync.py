from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timezone
from typing import Any

from life_os.connectors.whoop import WhoopConnector
from life_os.models import GoalStatus, LifeArea, ProgressEventCreate
from life_os.store import LifeOSStore


Candidate = tuple[str, float, str, str, str, str]


def sync_whoop_daily(
    store: LifeOSStore,
    connector: WhoopConnector,
    tenant_id: str,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    """Import WHOOP recovery, sleep, cycle, and workout metrics idempotently."""
    documents = connector.daily_data(start_date, end_date)
    active_fitness_goals = [
        goal
        for goal in store.list_goals(tenant_id, GoalStatus.ACTIVE)
        if goal.domain == LifeArea.FITNESS
    ]
    goal_id = active_fitness_goals[0].id if active_fitness_goals else None
    existing = {
        (event.metric, str(event.metadata.get("whoop_key", "")))
        for event in store.list_events(tenant_id)
        if event.source == "whoop_api"
    }
    candidates: list[Candidate] = []

    cycle_days: dict[int, str] = {}
    for cycle in documents.get("cycles", []):
        day = _record_day(cycle, "start")
        cycle_id = cycle.get("id")
        if not day or not isinstance(cycle_id, int):
            continue
        cycle_days[cycle_id] = day
        score = cycle.get("score") or {}
        _append_number(
            candidates,
            score,
            "strain",
            "whoop_day_strain",
            "strain",
            day,
            f"cycle:{cycle_id}",
        )
        kilojoule = score.get("kilojoule")
        if isinstance(kilojoule, (int, float)):
            candidates.append(
                (
                    "whoop_calories_burned",
                    float(kilojoule) / 4.184,
                    "kcal",
                    day,
                    "cycle",
                    f"cycle:{cycle_id}",
                )
            )

    for recovery in documents.get("recoveries", []):
        cycle_id = recovery.get("cycle_id")
        day = cycle_days.get(cycle_id) if isinstance(cycle_id, int) else None
        if not day:
            continue
        key = f"recovery:{cycle_id}"
        score = recovery.get("score") or {}
        for field, metric, unit in (
            ("recovery_score", "whoop_recovery_score", "score"),
            ("hrv_rmssd_milli", "whoop_hrv_rmssd_ms", "ms"),
            ("resting_heart_rate", "whoop_resting_heart_rate", "bpm"),
            ("spo2_percentage", "whoop_spo2", "percent"),
        ):
            _append_number(candidates, score, field, metric, unit, day, key)

    for sleep in documents.get("sleeps", []):
        if sleep.get("nap") is True:
            continue
        day = _record_day(sleep, "end") or _record_day(sleep, "start")
        sleep_id = str(sleep.get("id", ""))
        if not day or not sleep_id:
            continue
        key = f"sleep:{sleep_id}"
        score = sleep.get("score") or {}
        stage = score.get("stage_summary") or {}
        asleep_milli = sum(
            float(stage.get(field, 0) or 0)
            for field in (
                "total_light_sleep_time_milli",
                "total_slow_wave_sleep_time_milli",
                "total_rem_sleep_time_milli",
            )
        )
        if asleep_milli > 0:
            candidates.append(
                (
                    "whoop_sleep_hours",
                    asleep_milli / 3_600_000,
                    "hour",
                    day,
                    "sleep",
                    key,
                )
            )
        for field, metric in (
            ("sleep_performance_percentage", "whoop_sleep_performance"),
            ("sleep_efficiency_percentage", "whoop_sleep_efficiency"),
        ):
            _append_number(candidates, score, field, metric, "percent", day, key)

    workout_minutes: dict[str, float] = defaultdict(float)
    workout_strain: dict[str, float] = defaultdict(float)
    for workout in documents.get("workouts", []):
        day = _record_day(workout, "start")
        if not day:
            continue
        start = _parse_instant(workout.get("start"))
        end = _parse_instant(workout.get("end"))
        if start and end and end > start:
            workout_minutes[day] += (end - start).total_seconds() / 60
        strain = (workout.get("score") or {}).get("strain")
        if isinstance(strain, (int, float)):
            workout_strain[day] = max(workout_strain[day], float(strain))
    for day, minutes in workout_minutes.items():
        candidates.append(
            (
                "whoop_workout_minutes",
                minutes,
                "minute",
                day,
                "workout",
                f"workout:{day}",
            )
        )
    for day, strain in workout_strain.items():
        candidates.append(
            ("whoop_workout_strain", strain, "strain", day, "workout", f"workout:{day}")
        )

    created = 0
    skipped = 0
    imported_days: set[str] = set()
    for metric, value, unit, day, data_type, whoop_key in candidates:
        if (metric, whoop_key) in existing:
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
                source="whoop_api",
                confidence=1,
                occurred_at=occurred_at,
                goal_id=goal_id,
                metadata={
                    "provider": "whoop",
                    "data_type": data_type,
                    "day": day,
                    "whoop_key": whoop_key,
                },
            )
        )
        existing.add((metric, whoop_key))
        imported_days.add(day)
        created += 1
    return {
        "connected": True,
        "created_events": created,
        "skipped_existing": skipped,
        "imported_days": sorted(imported_days),
    }


def _record_day(record: dict[str, Any], field: str) -> str:
    value = record.get(field)
    return str(value)[:10] if isinstance(value, str) and len(value) >= 10 else ""


def _parse_instant(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _append_number(
    candidates: list[Candidate],
    document: dict[str, Any],
    field: str,
    metric: str,
    unit: str,
    day: str,
    key: str,
) -> None:
    value = document.get(field)
    if isinstance(value, (int, float)):
        candidates.append(
            (metric, float(value), unit, day, key.split(":", 1)[0], key)
        )
