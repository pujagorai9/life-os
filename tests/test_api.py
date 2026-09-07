import base64
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from life_os.api import create_app
from life_os.models import AgentId, PhotoAnalysis, ScheduledCheckIn
from life_os.store import LifeOSStore


def test_health_and_agent_catalog(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))
    assert client.get("/health").json() == {"status": "ok"}
    agents = client.get("/v1/agents").json()
    assert len(agents) == 12
    assert {agent["name"] for agent in agents} >= {
        "Chief of Staff",
        "Chief Archivist",
        "Briefing Officer",
        "Accountability Manager",
        "Progress Tracker",
        "Chief Finance Officer",
    }


def test_private_api_token_protects_cloud_routes(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("LIFE_OS_API_TOKEN", "private-cloud-token")
    client = TestClient(create_app(tmp_path / "api.db"))

    assert client.get("/health").status_code == 200
    assert client.get("/v1/agents").status_code == 401
    assert (
        client.get(
            "/v1/agents",
            headers={"Authorization": "Bearer private-cloud-token"},
        ).status_code
        == 200
    )


def test_pumping_events_replace_the_same_scheduled_slot(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))
    event = {
        "tenant_id": "tenant-a",
        "domain": "operations_manager",
        "metric": "pumping_ml",
        "value": 130,
        "unit": "ml",
        "source": "mobile_user_confirmation",
        "confidence": 1,
        "occurred_at": "2030-01-01T09:30:00-08:00",
        "metadata": {"scheduled_time": "9:30 AM"},
    }

    first = client.post("/v1/events", json=event)
    replacement = client.post("/v1/events", json={**event, "value": 145})
    next_slot = client.post(
        "/v1/events",
        json={**event, "value": 120, "occurred_at": "2030-01-01T12:30:00-08:00"},
    )

    assert first.status_code == replacement.status_code == next_slot.status_code == 200
    events = client.get(
        "/v1/events", params={"tenant_id": "tenant-a", "metric": "pumping_ml"}
    ).json()
    assert [(item["occurred_at"], item["value"]) for item in events] == [
        ("2030-01-01T12:30:00-08:00", 120),
        ("2030-01-01T09:30:00-08:00", 145),
    ]


def test_finance_email_results_build_a_private_daily_report(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("LIFE_OS_TIMEZONE", "America/Los_Angeles")
    client = TestClient(create_app(tmp_path / "api.db"))
    purchase = {
        "tenant_id": "me",
        "source_message_id": "purchase-1",
        "message_at": "2026-08-31T19:10:00-07:00",
        "outcome": "purchase",
        "merchant": "Neighborhood Market",
        "category": "groceries",
        "amount": 42.5,
        "currency": "usd",
        "transaction_at": "2026-08-31T18:45:00-07:00",
        "confidence": 0.98,
    }
    assert client.post("/v1/finance/email-results", json=purchase).status_code == 200
    assert (
        client.post(
            "/v1/finance/email-results",
            json={
                "tenant_id": "me",
                "source_message_id": "promotion-1",
                "message_at": "2026-08-31T20:00:00-07:00",
                "outcome": "not_purchase",
                "summary": "Promotional message; no confirmed transaction.",
            },
        ).status_code
        == 200
    )

    report = client.get(
        "/v1/finance/daily/2026-08-31", params={"tenant_id": "me"}
    ).json()
    assert report["processed_email_count"] == 2
    assert report["purchase_count"] == 1
    assert report["summaries"][0]["currency"] == "USD"
    assert report["summaries"][0]["net_spent"] == 42.5
    assert report["summaries"][0]["categories"] == [
        {"category": "groceries", "amount": 42.5}
    ]


def test_finance_accounts_returns_only_redacted_connection_metadata(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "gmail-accounts.json"
    registry.write_text(
        """{
          "accounts": [{
            "account_id": "suraj",
            "email": "suraj@example.com",
            "member_name": "Suraj",
            "token_file": "suraj-token.json",
            "connected_at": "2026-08-31T12:00:00+00:00",
            "scopes": ["https://www.googleapis.com/auth/gmail.readonly"]
          }]
        }"""
    )
    client = TestClient(
        create_app(tmp_path / "api.db", gmail_accounts_path=registry)
    )

    response = client.get("/v1/finance/accounts", params={"tenant_id": "me"})
    assert response.status_code == 200
    account = response.json()[0]
    assert account["member_name"] == "Suraj"
    assert account["email"] == "suraj@example.com"
    assert "token_file" not in account


def test_private_briefing_is_available_by_day(tmp_path: Path) -> None:
    briefings = tmp_path / "briefings"
    briefings.mkdir()
    (briefings / "2026-08-30-kickoff.md").write_text(
        "# Life OS Briefing — August 30, 2026\n\n## One important update\n\nWhy it matters."
    )
    client = TestClient(create_app(tmp_path / "api.db", briefings_dir=briefings))

    response = client.get("/v1/briefings/2026-08-30", params={"tenant_id": "me"})
    assert response.status_code == 200
    assert response.json()["title"] == "Life OS Briefing — August 30, 2026"
    assert "One important update" in response.json()["markdown"]
    assert response.json()["source_file"] == "2026-08-30-kickoff.md"

    missing = client.get("/v1/briefings/2026-08-31", params={"tenant_id": "me"})
    assert missing.status_code == 404


def test_cloud_briefing_is_saved_by_tenant_and_day(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))
    payload = {
        "tenant_id": "me",
        "day": "2026-09-07",
        "title": "Daily Briefing — September 7, 2026",
        "markdown": "# Daily Briefing — September 7, 2026\n\n## One update\n\nWhy it matters.",
        "source_file": "daily-automation",
    }

    saved = client.post("/v1/briefings", json=payload)
    assert saved.status_code == 200
    assert saved.json()["title"] == payload["title"]

    response = client.get("/v1/briefings/2026-09-07", params={"tenant_id": "me"})
    assert response.status_code == 200
    assert response.json()["markdown"] == payload["markdown"]

    missing_tenant = client.get(
        "/v1/briefings/2026-09-07", params={"tenant_id": "another-user"}
    )
    assert missing_tenant.status_code == 404


def test_private_appointment_sync_is_available_by_local_day(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("LIFE_OS_TIMEZONE", "America/Los_Angeles")
    ledger = tmp_path / "appointment-ledger.json"
    ledger.write_text(
        """{
          "current_cutoff_inclusive": "2026-08-31T05:32:26.771Z",
          "processed_at": "2026-08-31T05:40:00Z",
          "entries": [{
            "gmail_message_id": "message-1",
            "event_fingerprint": "yoga-session-2026-09-25-1900",
            "action": "matched_existing_event_and_attempted_attendee_add",
            "outcome": "exception_attendee_not_added_because_user_is_not_event_organizer",
            "processed_at": "2026-08-31T05:40:00Z"
          }],
          "exceptions": [{
            "gmail_message_id": "message-1",
            "summary": "The event already existed, but the attendee could not be added safely."
          }]
        }"""
    )
    client = TestClient(
        create_app(tmp_path / "api.db", appointment_ledger_path=ledger)
    )

    response = client.get(
        "/v1/appointment-syncs/2026-08-30", params={"tenant_id": "me"}
    )
    assert response.status_code == 200
    document = response.json()
    assert document["emails_processed"] == 1
    assert document["existing_events_matched"] == 1
    assert document["events_created"] == 0
    assert document["items"][0]["exception"] is True
    assert document["items"][0]["event_date"] == "2026-09-25"
    assert document["items"][0]["event_time"] == "7:00 PM"
    assert "attendee could not be added" in document["items"][0]["summary"]

    missing = client.get(
        "/v1/appointment-syncs/2026-08-29", params={"tenant_id": "me"}
    )
    assert missing.status_code == 404


def test_commitment_and_progress_flow(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))
    commitment = client.post(
        "/v1/commitments",
        json={
            "tenant_id": "tenant-a",
            "domain": "professional",
            "title": "Prepare proposal",
            "minimum_success": "A reviewable draft",
        },
    ).json()
    response = client.patch(
        f"/v1/commitments/{commitment['id']}",
        params={"tenant_id": "tenant-a", "status": "done"},
    )
    assert response.status_code == 200
    summary = client.get("/v1/progress", params={"tenant_id": "tenant-a"}).json()
    assert summary["completion_rate"] == 1


def test_nutrition_photo_is_stored_against_check_in(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "api.db"
    store = LifeOSStore(database)
    check_in = ScheduledCheckIn(
        id="nutrition-check-in",
        tenant_id="tenant-a",
        goal_id="nutrition-goal",
        protocol_id="nutrition-protocol",
        prompt_id="meal-photo",
        agent_id=AgentId.NUTRITION_COACH,
        prompt="Did you complete 'Eat breakfast'? Minimum success: Follow the plan",
        due_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )
    store.replace_pending_check_ins("tenant-a", "nutrition-goal", [check_in])
    client = TestClient(create_app(database))

    image = b"\x89PNG\r\n\x1a\n" + b"private-image-data"
    response = client.post(
        "/v1/check-ins/nutrition-check-in/photos",
        params={"tenant_id": "tenant-a"},
        content=image,
        headers={"content-type": "image/png"},
    )
    assert response.status_code == 200
    photo = response.json()
    assert photo["agent_id"] == "nutrition_coach"
    assert photo["analysis_status"] == "not_requested"
    assert photo["size_bytes"] == len(image)
    assert (tmp_path / "api_attachments" / photo["storage_key"]).read_bytes() == image

    listed = client.get(
        "/v1/check-ins/nutrition-check-in/photos",
        params={"tenant_id": "tenant-a"},
    ).json()
    assert [item["id"] for item in listed] == [photo["id"]]
    assert client.get(
        "/v1/check-ins/nutrition-check-in/photos",
        params={"tenant_id": "tenant-b"},
    ).status_code == 404

    monkeypatch.setattr(
        "life_os.api.analyze_check_in_photo",
        lambda **_: PhotoAnalysis(
            summary="A photographed meal",
            estimated_calories=500,
            estimated_protein_g=25,
            estimated_carbohydrates_g=60,
            estimated_fat_g=18,
            estimated_fiber_g=9,
            estimated_calcium_mg=220,
            confidence=0.6,
        ),
    )
    analyzed = client.post(
        f"/v1/check-ins/nutrition-check-in/photos/{photo['id']}/analyze",
        params={"tenant_id": "tenant-a"},
    )
    assert analyzed.status_code == 200
    assert analyzed.json()["analysis"]["estimated_fiber_g"] == 9
    assert analyzed.json()["analysis"]["estimated_calcium_mg"] == 220


def test_photo_rejects_unsupported_check_in(tmp_path: Path) -> None:
    database = tmp_path / "api.db"
    store = LifeOSStore(database)
    check_in = ScheduledCheckIn(
        id="operations-check-in",
        tenant_id="tenant-a",
        goal_id="career-goal",
        protocol_id="career-protocol",
        prompt_id="career-task",
        agent_id=AgentId.OPERATIONS_MANAGER,
        prompt="Did you complete 'Review the household list'?",
        due_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )
    store.replace_pending_check_ins("tenant-a", "career-goal", [check_in])
    client = TestClient(create_app(database))
    response = client.post(
        "/v1/check-ins/operations-check-in/photos",
        params={"tenant_id": "tenant-a"},
        content=b"\x89PNG\r\n\x1a\nnot-a-real-photo",
        headers={"content-type": "image/png"},
    )
    assert response.status_code == 422


def test_nutrition_description_returns_structured_estimate(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "api.db"
    store = LifeOSStore(database)
    check_in = ScheduledCheckIn(
        id="meal-check-in",
        tenant_id="tenant-a",
        goal_id="nutrition-goal",
        protocol_id="nutrition-protocol",
        prompt_id="lunch",
        agent_id=AgentId.NUTRITION_COACH,
        prompt="Did you complete 'Eat lunch'? Minimum success: Follow the plan",
        due_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )
    store.replace_pending_check_ins("tenant-a", "nutrition-goal", [check_in])
    monkeypatch.setattr(
        "life_os.api.analyze_nutrition_description",
        lambda **_: PhotoAnalysis(
            summary="A dal and rice meal",
            estimated_calories=540,
            estimated_protein_g=22,
            estimated_carbohydrates_g=78,
            estimated_fat_g=14,
            estimated_fiber_g=11,
            estimated_calcium_mg=180,
            confidence=0.7,
        ),
    )
    client = TestClient(create_app(database))
    response = client.post(
        "/v1/check-ins/meal-check-in/nutrition-analysis",
        json={
            "tenant_id": "tenant-a",
            "description": "One cup dal, rice, and half a cup of dahi",
        },
    )
    assert response.status_code == 200
    estimate = response.json()
    assert estimate["estimated_calories"] == 540
    assert estimate["estimated_protein_g"] == 22
    assert estimate["estimated_fiber_g"] == 11
    assert estimate["estimated_calcium_mg"] == 180


def test_nutrition_conversation_analyzes_text_and_multiple_images_together(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "api.db"
    store = LifeOSStore(database)
    check_in = ScheduledCheckIn(
        id="meal-conversation",
        tenant_id="tenant-a",
        goal_id="nutrition-goal",
        protocol_id="nutrition-protocol",
        prompt_id="lunch",
        agent_id=AgentId.NUTRITION_COACH,
        prompt="Did you complete 'Eat lunch'? Minimum success: Follow the plan",
        due_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )
    store.replace_pending_check_ins("tenant-a", "nutrition-goal", [check_in])
    captured: dict = {}

    def analyze(**kwargs) -> PhotoAnalysis:
        captured.update(kwargs)
        return PhotoAnalysis(
            summary="Two views of one lunch",
            estimated_calories=610,
            estimated_protein_g=28,
            estimated_carbohydrates_g=82,
            estimated_fat_g=19,
            estimated_calcium_mg=240,
            confidence=0.75,
        )

    monkeypatch.setattr("life_os.api.analyze_nutrition_input", analyze)
    image_one = b"\x89PNG\r\n\x1a\nfirst-view"
    image_two = b"\x89PNG\r\n\x1a\nsecond-view"
    client = TestClient(create_app(database))
    response = client.post(
        "/v1/check-ins/meal-conversation/nutrition-conversation",
        json={
            "tenant_id": "tenant-a",
            "description": "Dal, rice, and dahi shown from two angles",
            "images": [
                {
                    "media_type": "image/png",
                    "data": base64.b64encode(image_one).decode(),
                },
                {
                    "media_type": "image/png",
                    "data": base64.b64encode(image_two).decode(),
                },
            ],
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["analysis"]["estimated_calories"] == 610
    assert len(result["photos"]) == 2
    assert len(captured["images"]) == 2
    assert captured["description"] == "Dal, rice, and dahi shown from two angles"
    assert len(store.list_check_in_photos("tenant-a", "meal-conversation")) == 2
