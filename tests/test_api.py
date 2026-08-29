from pathlib import Path

from fastapi.testclient import TestClient

from life_os.api import create_app


def test_health_and_agent_catalog(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))
    assert client.get("/health").json() == {"status": "ok"}
    agents = client.get("/v1/agents").json()
    assert len(agents) == 11
    assert {agent["name"] for agent in agents} >= {"Chief of Staff", "Chief Archivist"}


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
