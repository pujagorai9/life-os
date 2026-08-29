from life_os.agent_catalog import get_agent, list_agents
from life_os.models import AgentId


def test_all_agents_are_registered() -> None:
    assert {agent.id for agent in list_agents()} == set(AgentId)


def test_private_agents_are_marked() -> None:
    assert get_agent(AgentId.INNER_WELLBEING_GURU).private_by_default is True
    assert get_agent(AgentId.CHIEF_ARCHIVIST).private_by_default is True


def test_external_actions_require_approval() -> None:
    assert get_agent(AgentId.CAREER_COACH).can_propose_external_actions is True
    assert "approval" in get_agent(AgentId.CAREER_COACH).instructions.casefold()
