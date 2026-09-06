from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient

from life_os.api import create_app
from life_os.connectors.whoop import WHOOP_SCOPES, WhoopConnector
from life_os.store import LifeOSStore
from life_os.whoop_sync import sync_whoop_daily


def test_whoop_authorization_requests_read_only_scopes(tmp_path: Path) -> None:
    connector = WhoopConnector(
        "client-id",
        "client-secret",
        "https://example.com/v1/integrations/whoop/callback",
        tmp_path / "whoop-token.json",
    )

    authorization = connector.begin_authorization()
    query = parse_qs(urlsplit(authorization.url).query)

    assert query["client_id"] == ["client-id"]
    assert query["scope"] == [" ".join(WHOOP_SCOPES)]
    assert query["redirect_uri"] == [
        "https://example.com/v1/integrations/whoop/callback"
    ]
    assert query["state"] == [authorization.state]
    assert len(authorization.state) >= 8


def test_whoop_exchange_validates_state_and_writes_private_token(
    tmp_path: Path,
) -> None:
    token_path = tmp_path / "private" / "whoop-token.json"

    def exchange(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/oauth/oauth2/token"
        return httpx.Response(
            200,
            json={
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_in": 3600,
                "scope": " ".join(WHOOP_SCOPES),
            },
        )

    connector = WhoopConnector(
        "client-id",
        "client-secret",
        "https://example.com/v1/integrations/whoop/callback",
        token_path,
        httpx.Client(transport=httpx.MockTransport(exchange)),
    )
    authorization = connector.begin_authorization()

    status = connector.exchange_code("authorization-code", authorization.state)

    assert status["connected"] is True
    assert status["has_refresh_token"] is True
    assert status["scope"] == sorted(WHOOP_SCOPES)
    stored = json.loads(token_path.read_text())
    assert stored["access_token"] == "access"
    assert token_path.stat().st_mode & 0o777 == 0o600


def test_whoop_exchange_rejects_mismatched_state(tmp_path: Path) -> None:
    connector = WhoopConnector(
        "client-id",
        "client-secret",
        "https://example.com/v1/integrations/whoop/callback",
        tmp_path / "whoop-token.json",
    )
    connector.begin_authorization()

    with pytest.raises(RuntimeError, match="did not match"):
        connector.exchange_code("authorization-code", "wrong-state")


def test_whoop_sync_imports_daily_metrics_idempotently(tmp_path: Path) -> None:
    class FakeConnector:
        def daily_data(self, start_date, end_date):
            assert start_date == date.fromisoformat("2026-09-05")
            assert end_date == date.fromisoformat("2026-09-06")
            return {
                "cycles": [
                    {
                        "id": 42,
                        "start": "2026-09-06T01:00:00-07:00",
                        "score": {"strain": 8.2, "kilojoule": 2092},
                    }
                ],
                "recoveries": [
                    {
                        "cycle_id": 42,
                        "score": {
                            "recovery_score": 78,
                            "hrv_rmssd_milli": 52.4,
                            "resting_heart_rate": 57,
                            "spo2_percentage": 97.2,
                        },
                    }
                ],
                "sleeps": [
                    {
                        "id": "sleep-id",
                        "end": "2026-09-06T07:30:00-07:00",
                        "nap": False,
                        "score": {
                            "stage_summary": {
                                "total_light_sleep_time_milli": 14_400_000,
                                "total_slow_wave_sleep_time_milli": 5_400_000,
                                "total_rem_sleep_time_milli": 5_400_000,
                            },
                            "sleep_performance_percentage": 91,
                            "sleep_efficiency_percentage": 94,
                        },
                    }
                ],
                "workouts": [
                    {
                        "id": "workout-id",
                        "start": "2026-09-06T10:00:00-07:00",
                        "end": "2026-09-06T10:45:00-07:00",
                        "score": {"strain": 9.1},
                    }
                ],
            }

    store = LifeOSStore(tmp_path / "life-os.db")
    start = date.fromisoformat("2026-09-05")
    end = date.fromisoformat("2026-09-06")

    first = sync_whoop_daily(store, FakeConnector(), "me", start, end)
    second = sync_whoop_daily(store, FakeConnector(), "me", start, end)

    assert first["created_events"] == 11
    assert second["created_events"] == 0
    assert second["skipped_existing"] == 11
    events = store.list_events("me")
    assert {event.metric for event in events} == {
        "whoop_day_strain",
        "whoop_calories_burned",
        "whoop_recovery_score",
        "whoop_hrv_rmssd_ms",
        "whoop_resting_heart_rate",
        "whoop_spo2",
        "whoop_sleep_hours",
        "whoop_sleep_performance",
        "whoop_sleep_efficiency",
        "whoop_workout_minutes",
        "whoop_workout_strain",
    }


def test_whoop_status_reports_unconfigured_without_exposing_callback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LIFE_OS_API_TOKEN", "private-cloud-token")
    monkeypatch.delenv("WHOOP_CLIENT_ID", raising=False)
    monkeypatch.delenv("WHOOP_CLIENT_SECRET", raising=False)
    client = TestClient(create_app(tmp_path / "api.db"))

    response = client.get(
        "/v1/integrations/whoop/status",
        headers={"Authorization": "Bearer private-cloud-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "configured": False,
        "connected": False,
        "scope": [],
        "has_refresh_token": False,
    }
    assert client.get("/v1/integrations/whoop/status").status_code == 401
