from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx

from life_os.connectors.oura import OuraConnector
from life_os.oura_sync import sync_oura_daily
from life_os.store import LifeOSStore


def test_oura_authorization_requests_only_daily_scope(tmp_path: Path) -> None:
    connector = OuraConnector(
        "client-id",
        "client-secret",
        "http://localhost:8765/callback",
        tmp_path / "token.json",
    )

    authorization = connector.begin_authorization()
    query = parse_qs(urlsplit(authorization.url).query)

    assert query["client_id"] == ["client-id"]
    assert query["scope"] == ["daily"]
    assert query["redirect_uri"] == ["http://localhost:8765/callback"]
    assert query["state"] == [authorization.state]


def test_oura_exchange_writes_private_token(tmp_path: Path) -> None:
    token_path = tmp_path / "private" / "oura-token.json"

    def exchange(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/oauth/token"
        return httpx.Response(
            200,
            json={
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_in": 86400,
                "scope": "daily",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(exchange))
    connector = OuraConnector(
        "client-id",
        "client-secret",
        "http://localhost:8765/callback",
        token_path,
        client,
    )

    status = connector.exchange_code("authorization-code")

    assert status == {
        "connected": True,
        "scope": ["daily"],
        "has_refresh_token": True,
        "expires_in": 86400,
    }
    stored = json.loads(token_path.read_text())
    assert stored["access_token"] == "access"
    assert token_path.stat().st_mode & 0o777 == 0o600


def test_oura_sync_imports_daily_metrics_idempotently(tmp_path: Path) -> None:
    class FakeConnector:
        def daily_summaries(self, start_date, end_date):
            assert start_date.isoformat() == "2026-08-29"
            assert end_date.isoformat() == "2026-08-30"
            return {
                "daily_sleep": [{"day": "2026-08-30", "score": 84}],
                "daily_readiness": [{"day": "2026-08-30", "score": 79}],
                "daily_activity": [
                    {
                        "day": "2026-08-30",
                        "score": 81,
                        "steps": 6500,
                        "active_calories": 430,
                    }
                ],
                "sleep": [
                    {"day": "2026-08-30", "total_sleep_duration": 27000}
                ],
            }

    store = LifeOSStore(tmp_path / "life-os.db")
    start = date.fromisoformat("2026-08-29")
    end = date.fromisoformat("2026-08-30")

    first = sync_oura_daily(store, FakeConnector(), "me", start, end)
    second = sync_oura_daily(store, FakeConnector(), "me", start, end)

    assert first["created_events"] == 7
    assert second["created_events"] == 0
    assert second["skipped_existing"] == 7
    events = store.list_events("me")
    assert {event.metric for event in events} == {
        "oura_sleep_score",
        "oura_readiness_score",
        "oura_activity_score",
        "oura_steps",
        "oura_active_calories",
        "total_sleep_hours",
        "seven_hour_sleep_days",
    }
