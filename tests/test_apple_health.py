from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from life_os.api import create_app


def test_apple_health_import_is_authenticated_and_idempotent(
    tmp_path: Path, monkeypatch
) -> None:
    token = tmp_path / "health-token.txt"
    token.write_text("test-health-token\n")
    monkeypatch.setenv("LIFE_OS_HEALTH_INGEST_TOKEN_PATH", str(token))
    client = TestClient(create_app(tmp_path / "api.db"))
    payload = {
        "tenant_id": "tenant-a",
        "day": "2030-01-02T22:30:00-08:00",
        "timezone": "America/Los_Angeles",
        "active_energy_kcal": 480,
        "move_goal_kcal": 450,
        "exercise_minutes": "32 min",
        "stand_minutes": "84 min",
        "stand_hours": 12,
        "cardio_minutes": 10,
        "strength_minutes": 20,
    }

    assert client.post(
        "/v1/integrations/apple-health/import", json=payload
    ).status_code == 401
    response = client.post(
        "/v1/integrations/apple-health/import",
        json=payload,
        headers={"authorization": "Bearer test-health-token"},
    )
    assert response.status_code == 200
    assert response.json()["created_events"] == 14

    unchanged = client.post(
        "/v1/integrations/apple-health/import",
        json=payload,
        headers={"authorization": "Bearer test-health-token"},
    ).json()
    assert unchanged["created_events"] == 0
    assert unchanged["unchanged_events"] == 14

    payload["exercise_minutes"] = 40
    updated = client.post(
        "/v1/integrations/apple-health/import",
        json=payload,
        headers={"authorization": "Bearer test-health-token"},
    ).json()
    assert updated["updated_events"] == 1

    events = client.get("/v1/events", params={"tenant_id": "tenant-a"}).json()
    assert len(events) == 14
    exercise = next(event for event in events if event["metric"] == "apple_exercise_minutes")
    assert exercise["value"] == 40


def test_compact_shortcut_endpoint_accepts_health_measurements(
    tmp_path: Path, monkeypatch
) -> None:
    token = tmp_path / "health-token.txt"
    token.write_text("test-health-token\n")
    monkeypatch.setenv("LIFE_OS_HEALTH_INGEST_TOKEN_PATH", str(token))
    client = TestClient(create_app(tmp_path / "api.db"))
    response = client.post(
        "/v1/integrations/apple-health/shortcut",
        params={
            "tenant_id": "tenant-a",
            "day": "2030-01-02T22:30:00-08:00",
            "timezone": "America/Los_Angeles",
            "exercise_minutes": "32 min",
            "stand_minutes": "84 min",
            "active_energy_kcal": "480 kcal",
        },
        headers={"authorization": "Bearer test-health-token"},
    )
    assert response.status_code == 200
    assert response.json()["created_events"] == 5
