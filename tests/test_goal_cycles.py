from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from life_os.api import create_app


def goal_payload() -> dict:
    return {
        "tenant_id": "tenant-a",
        "domain": "nutrition",
        "owner_agent": "nutrition_coach",
        "title": "Follow an agreed nutrition plan",
        "motivation": "Support steady energy",
        "success_definition": "Stay within the approved calorie range most days",
        "start_at": "2030-01-01T08:00:00Z",
        "review_at": "2030-01-29T08:00:00Z",
        "metrics": [
            {
                "key": "daily_calories",
                "label": "Daily calories",
                "unit": "kcal",
                "target_type": "range",
                "minimum_value": 1800,
                "maximum_value": 2200,
                "cadence": "daily",
            }
        ],
        "milestones": [
            {
                "title": "Understand the first assigned topic",
                "success_criteria": "Summarize the source and answer a probe",
                "due_at": "2030-01-01T20:00:00Z",
            }
        ],
        "routines": [
            {
                "title": "Complete food log",
                "cadence": "daily",
                "target_count": 1,
                "unit": "log",
                "minimum_success": "All meals are recorded",
                "preferred_time": "20:30",
            },
            {
                "title": "Complete weekly outreach",
                "cadence": "weekly",
                "target_count": 3,
                "unit": "message",
                "minimum_success": "Three messages are sent",
                "preferred_time": "18:00",
            }
        ],
    }


def test_onboarding_makes_briefing_explicit(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))
    options = client.get("/v1/onboarding/options").json()
    briefing = next(option for option in options if option["id"] == "briefing")
    assert briefing["title"] == "News & Industry Briefings"
    assert briefing["agent_id"] == "briefing_intern"

    response = client.put(
        "/v1/onboarding/selection",
        json={"tenant_id": "tenant-a", "selected_areas": ["nutrition", "briefing"]},
    )
    assert response.status_code == 200
    saved = client.get(
        "/v1/onboarding/selection", params={"tenant_id": "tenant-a"}
    ).json()
    assert saved["selected_areas"] == ["nutrition", "briefing"]


def test_specialist_planning_session_preserves_discussion_and_finalizes_draft(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))
    client.put(
        "/v1/onboarding/selection",
        json={"tenant_id": "tenant-a", "selected_areas": ["nutrition"]},
    )
    session = client.post(
        "/v1/planning-sessions",
        json={"tenant_id": "tenant-a", "area": "nutrition"},
    ).json()
    assert session["agent_id"] == "nutrition_coach"
    assert "exact nutrition outcome" in session["messages"][0]["content"]

    turn = client.post(
        f"/v1/planning-sessions/{session['id']}/messages",
        json={"tenant_id": "tenant-a", "message": "I want a four-week plan."},
    )
    assert turn.status_code == 200
    assert len(turn.json()["session"]["messages"]) == 3

    finalized = client.post(
        f"/v1/planning-sessions/{session['id']}/finalize",
        json={"tenant_id": "tenant-a", "goal": goal_payload()},
    )
    assert finalized.status_code == 200
    completion = finalized.json()
    assert completion["goal"]["status"] == "draft"
    assert completion["onboarding_complete"] is True
    assert completion["next_session"] is None
    assert completion["chief_of_staff_message"].startswith("Chief of Staff:")
    saved_session = client.get(
        f"/v1/planning-sessions/{session['id']}",
        params={"tenant_id": "tenant-a"},
    ).json()
    assert saved_session["status"] == "finalized"
    assert saved_session["goal_id"] == completion["goal"]["id"]


def test_finalizing_one_area_returns_to_chief_of_staff_and_opens_next(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))
    client.put(
        "/v1/onboarding/selection",
        json={
            "tenant_id": "tenant-a",
            "selected_areas": ["nutrition", "briefing", "fitness"],
        },
    )
    nutrition = client.post(
        "/v1/planning-sessions",
        json={"tenant_id": "tenant-a", "area": "nutrition"},
    ).json()

    completion = client.post(
        f"/v1/planning-sessions/{nutrition['id']}/finalize",
        json={"tenant_id": "tenant-a", "goal": goal_payload()},
    ).json()

    assert completion["onboarding_complete"] is False
    assert completion["remaining_areas"] == ["briefing", "fitness"]
    assert completion["chief_of_staff_message"].startswith("Chief of Staff:")
    assert "News & Industry Briefings" in completion["chief_of_staff_message"]
    assert completion["next_session"]["area"] == "briefing"
    assert completion["next_session"]["agent_id"] == "briefing_intern"
    messages = completion["next_session"]["messages"]
    assert messages[0]["content"] == completion["chief_of_staff_message"]
    assert "topics, sources" in messages[1]["content"]


def test_professional_onboarding_prompt_is_generic(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))
    session = client.post(
        "/v1/planning-sessions",
        json={"tenant_id": "new-user", "area": "professional"},
    ).json()
    opening = session["messages"][0]["content"].casefold()
    assert "searching for a job" in opening
    assert "next promotion" in opening
    assert "personal project" in opening
    assert "professional brand" in opening


def test_goal_approval_creates_editable_tracking_protocol(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))
    client.put(
        "/v1/onboarding/selection",
        json={"tenant_id": "tenant-a", "selected_areas": ["nutrition"]},
    )
    draft = client.post("/v1/goals", json=goal_payload()).json()
    assert draft["status"] == "draft"

    activation = client.post(
        f"/v1/goals/{draft['id']}/approve", params={"tenant_id": "tenant-a"}
    )
    assert activation.status_code == 200
    result = activation.json()
    assert result["goal"]["status"] == "active"
    prompts = result["proposed_tracking_protocol"]["prompts"]
    assert {prompt["cadence"] for prompt in prompts} >= {"daily", "end_of_cycle"}
    assert result["proposed_tracking_protocol"]["approved"] is False

    approval = client.post(
        f"/v1/goals/{draft['id']}/tracking-protocol/approval",
        json={"tenant_id": "tenant-a", "approved": True},
    )
    assert approval.json()["approved"] is True
    due = client.get(
        "/v1/check-ins/due",
        params={"tenant_id": "tenant-a", "as_of": "2030-01-01T21:00:00Z"},
    ).json()
    assert due[0]["agent_id"] == "nutrition_coach"
    assert any("Complete food log" in item["prompt"] for item in due)
    assert not any(item["agent_id"] == "chief_archivist" for item in due)
    assert any(
        item["agent_id"] == "nutrition_coach"
        and "Today you committed to" in item["prompt"]
        for item in due
    )
    delivered = client.patch(
        f"/v1/check-ins/{due[0]['id']}",
        json={"tenant_id": "tenant-a", "status": "delivered"},
    )
    assert delivered.json()["status"] == "delivered"
    remaining = client.get(
        "/v1/check-ins/due",
        params={"tenant_id": "tenant-a", "as_of": "2030-01-01T21:00:00Z"},
    ).json()
    assert due[0]["id"] not in {item["id"] for item in remaining}
    assert not any("weekly outreach" in item["prompt"] for item in due)
    week_end = client.get(
        "/v1/check-ins/due",
        params={"tenant_id": "tenant-a", "as_of": "2030-01-07T19:00:00Z"},
    ).json()
    assert any("weekly outreach" in item["prompt"] for item in week_end)


def test_learning_milestones_route_to_archivist(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))
    payload = goal_payload()
    payload.update(
        domain="learning",
        owner_agent="knowledge_guru",
        title="Understand an assigned book",
    )
    draft = client.post("/v1/goals", json=payload).json()
    activation = client.post(
        f"/v1/goals/{draft['id']}/approve", params={"tenant_id": "tenant-a"}
    ).json()
    milestone_prompt = next(
        prompt
        for prompt in activation["proposed_tracking_protocol"]["prompts"]
        if prompt["cadence"] == "once"
    )
    assert milestone_prompt["agent_id"] == "chief_archivist"
    assert "each assigned source separately" in milestone_prompt["prompt"]


def test_non_learning_milestone_can_offer_archivist_handoff(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))
    payload = goal_payload()
    payload["domain"] = "professional"
    payload["owner_agent"] = "career_coach"
    payload["milestones"][0]["capture_knowledge"] = True
    draft = client.post("/v1/goals", json=payload).json()
    activation = client.post(
        f"/v1/goals/{draft['id']}/approve", params={"tenant_id": "tenant-a"}
    ).json()
    milestone_prompt = next(
        prompt
        for prompt in activation["proposed_tracking_protocol"]["prompts"]
        if prompt["cadence"] == "once"
    )
    assert milestone_prompt["agent_id"] == "career_coach"
    assert "offer a Chief Archivist handoff" in milestone_prompt["prompt"]
    assert "save it only after the user confirms" in milestone_prompt["prompt"]


def test_agent_delivery_milestone_prompts_the_owning_agent(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))
    payload = goal_payload()
    payload["domain"] = "briefing"
    payload["owner_agent"] = "briefing_intern"
    payload["milestones"][0]["kind"] = "agent_delivery"
    draft = client.post("/v1/goals", json=payload).json()
    activation = client.post(
        f"/v1/goals/{draft['id']}/approve", params={"tenant_id": "tenant-a"}
    ).json()
    milestone_prompt = next(
        prompt
        for prompt in activation["proposed_tracking_protocol"]["prompts"]
        if prompt["cadence"] == "once"
    )
    assert milestone_prompt["agent_id"] == "briefing_intern"
    assert milestone_prompt["prompt"].startswith("Prepare and deliver")
    assert "Do not ask the user to report" in milestone_prompt["prompt"]


def test_goal_amendments_are_versioned(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))
    draft = client.post("/v1/goals", json=goal_payload()).json()
    revised = client.post(
        f"/v1/goals/{draft['id']}/amendments",
        json={
            "tenant_id": "tenant-a",
            "reason": "The first review window was too short",
            "changes": {"review_at": "2030-02-05T08:00:00Z"},
        },
    )
    assert revised.status_code == 200
    assert revised.json()["version"] == 2
    history = client.get(
        f"/v1/goals/{draft['id']}/amendments", params={"tenant_id": "tenant-a"}
    ).json()
    assert history[0]["from_version"] == 1
    assert history[0]["to_version"] == 2
    protocol = client.get(
        f"/v1/goals/{draft['id']}/tracking-protocol",
        params={"tenant_id": "tenant-a"},
    ).json()
    assert protocol["goal_version"] == 2
    assert protocol["approved"] is False


def test_due_review_uses_goal_statistics_and_renews_cycle(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))
    draft = client.post("/v1/goals", json=goal_payload()).json()
    client.post(f"/v1/goals/{draft['id']}/approve", params={"tenant_id": "tenant-a"})
    commitment = client.post(
        "/v1/commitments",
        json={
            "tenant_id": "tenant-a",
            "domain": "nutrition",
            "goal_id": draft["id"],
            "title": "Complete food log",
            "minimum_success": "All meals recorded",
        },
    ).json()
    client.patch(
        f"/v1/commitments/{commitment['id']}",
        params={"tenant_id": "tenant-a", "status": "done"},
    )
    client.post(
        "/v1/events",
        json={
            "tenant_id": "tenant-a",
            "domain": "nutrition",
            "goal_id": draft["id"],
            "metric": "daily_calories",
            "value": 2000,
            "unit": "kcal",
            "source": "user_confirmed",
            "confidence": 1,
        },
    )

    due = client.get(
        "/v1/reviews/due",
        params={"tenant_id": "tenant-a", "as_of": "2030-01-30T08:00:00Z"},
    ).json()
    assert [goal["id"] for goal in due] == [draft["id"]]

    review = client.post(
        f"/v1/goals/{draft['id']}/review", params={"tenant_id": "tenant-a"}
    ).json()
    assert review["specialist_agent"] == "nutrition_coach"
    assert review["statistics"]["completion_rate"] == 1
    assert review["statistics"]["metric_totals"]["daily_calories.kcal"] == 2000
    assert review["goal"]["status"] == "awaiting_review"

    renewed = client.post(
        f"/v1/goals/{draft['id']}/renew",
        json={
            "tenant_id": "tenant-a",
            "start_at": "2030-02-01T08:00:00Z",
            "review_at": "2030-03-01T08:00:00Z",
        },
    )
    assert renewed.status_code == 200
    next_cycle = renewed.json()
    assert next_cycle["cycle_number"] == 2
    assert next_cycle["previous_cycle_id"] == draft["id"]
    assert next_cycle["status"] == "draft"


def test_archivist_knowledge_records_require_confirmation_and_are_searchable(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))
    proposed = client.post(
        "/v1/knowledge-records",
        json={
            "tenant_id": "tenant-a",
            "source_title": "AI Engineering",
            "topic": "Retrieval-augmented generation",
            "expected_scope": "Retrieval, grounding, and freshness",
            "user_summary": "RAG retrieves relevant context before generation.",
            "probe_questions": ["When is retrieval preferable to fine-tuning?"],
            "probe_answers": ["When knowledge changes or citations matter."],
            "interview_recall": "Use RAG for fresh, attributable private knowledge.",
            "strengths": ["Explained freshness"],
            "gaps": ["Needs stronger retrieval evaluation examples"],
            "tags": ["rag", "grounding", "interview-prep"],
        },
    ).json()
    hidden = client.get(
        "/v1/knowledge-records",
        params={"tenant_id": "tenant-a", "query": "RAG"},
    ).json()
    assert hidden == []

    confirmed = client.post(
        f"/v1/knowledge-records/{proposed['id']}/confirm",
        params={"tenant_id": "tenant-a"},
    ).json()
    assert confirmed["confirmed"] is True
    found = client.get(
        "/v1/knowledge-records",
        params={"tenant_id": "tenant-a", "query": "grounding"},
    ).json()
    assert [record["id"] for record in found] == [proposed["id"]]
    isolated = client.get(
        "/v1/knowledge-records",
        params={"tenant_id": "tenant-b", "query": "grounding"},
    ).json()
    assert isolated == []
