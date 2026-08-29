from pathlib import Path

from life_os.llm import OfflineClient
from life_os.models import AgentId, ChatRequest, Profile
from life_os.orchestrator import LifeOS
from life_os.store import LifeOSStore


def runtime(tmp_path: Path) -> LifeOS:
    return LifeOS(LifeOSStore(tmp_path / "test.db"), OfflineClient(), Profile())


def test_routes_professional_work(tmp_path: Path) -> None:
    assert runtime(tmp_path).route("Help prepare for a work promotion") == AgentId.CAREER_COACH


def test_routes_learning(tmp_path: Path) -> None:
    assert runtime(tmp_path).route("I want to study a new book") == AgentId.KNOWLEDGE_GURU


def test_routes_briefing(tmp_path: Path) -> None:
    assert runtime(tmp_path).route("Summarize today's news") == AgentId.BRIEFING_INTERN


def test_falls_back_to_chief_of_staff(tmp_path: Path) -> None:
    assert runtime(tmp_path).route("Help me plan tomorrow") == AgentId.CHIEF_OF_STAFF


def test_chat_uses_selected_agent(tmp_path: Path) -> None:
    result = runtime(tmp_path).chat(
        ChatRequest(tenant_id="tenant-a", message="hello", agent_id=AgentId.FITNESS_COACH)
    )
    assert result.agent_id == AgentId.FITNESS_COACH
