from __future__ import annotations

from life_os.agent_catalog import get_agent
from life_os.config import load_profile
from life_os.llm import LLMClient, default_client
from life_os.models import AgentId, AgentOutput, ChatRequest, GoalStatus, LifeArea, Profile
from life_os.store import LifeOSStore


ROUTING_KEYWORDS: dict[AgentId, tuple[str, ...]] = {
    AgentId.CAREER_COACH: (
        "career", "job", "interview", "work", "promotion", "stakeholder", "network", "blog",
    ),
    AgentId.KNOWLEDGE_GURU: ("learn", "study", "book", "course", "practice", "understand", "skill"),
    AgentId.BRIEFING_INTERN: ("news", "brief", "article", "newsletter", "update", "headline"),
    AgentId.NUTRITION_COACH: ("meal", "food", "eat", "calorie", "protein", "grocery", "nutrition"),
    AgentId.FITNESS_COACH: ("workout", "exercise", "walk", "run", "sleep", "recovery", "fitness"),
    AgentId.INNER_WELLBEING_GURU: (
        "reflect", "journal", "gratitude", "meditate", "affirmation", "emotion", "mindset",
    ),
    AgentId.OPERATIONS_MANAGER: (
        "family", "house", "appointment", "travel", "trip", "buy", "pet", "schedule",
    ),
    AgentId.CHIEF_ACCOUNTABILITY_OFFICER: (
        "accountable", "commitment", "remind", "blocked", "reschedule", "didn't do",
    ),
    AgentId.HEAD_OF_PERFORMANCE_ANALYTICS: (
        "progress", "chart", "trend", "report", "analytics", "monthly", "weekly review",
    ),
    AgentId.CHIEF_ARCHIVIST: ("remember", "memory", "forget", "preference", "context"),
}

AGENT_AREAS: dict[AgentId, LifeArea] = {
    AgentId.CAREER_COACH: LifeArea.PROFESSIONAL,
    AgentId.KNOWLEDGE_GURU: LifeArea.LEARNING,
    AgentId.BRIEFING_INTERN: LifeArea.BRIEFING,
    AgentId.NUTRITION_COACH: LifeArea.NUTRITION,
    AgentId.FITNESS_COACH: LifeArea.FITNESS,
    AgentId.INNER_WELLBEING_GURU: LifeArea.WELLBEING,
    AgentId.OPERATIONS_MANAGER: LifeArea.OPERATIONS,
}


class LifeOS:
    def __init__(
        self,
        store: LifeOSStore,
        client: LLMClient | None = None,
        profile: Profile | None = None,
    ) -> None:
        self.store = store
        self.client = client or default_client()
        self.profile = profile or load_profile()

    def route(self, message: str) -> AgentId:
        normalized = message.casefold()
        scores = {
            agent_id: sum(keyword in normalized for keyword in keywords)
            for agent_id, keywords in ROUTING_KEYWORDS.items()
        }
        winner = max(scores, key=scores.get)
        return winner if scores[winner] else AgentId.CHIEF_OF_STAFF

    def chat(self, request: ChatRequest) -> AgentOutput:
        agent_id = request.agent_id or self.route(request.message)
        if agent_id not in self.profile.enabled_agents:
            agent_id = AgentId.CHIEF_OF_STAFF
        selection = self.store.get_onboarding_selection(request.tenant_id)
        if (
            selection
            and agent_id in AGENT_AREAS
            and AGENT_AREAS[agent_id] not in selection.selected_areas
        ):
            agent_id = AgentId.CHIEF_OF_STAFF
        agent = get_agent(agent_id)
        memories = self.store.confirmed_context(request.tenant_id, agent.domain)
        stored_goals = self.store.list_goals(request.tenant_id, GoalStatus.ACTIVE)
        context_lines = [
            (
                f"Approved Goal Contract [{goal.domain}] cycle {goal.cycle_number}: "
                f"{goal.title}; success={goal.success_definition}; review_at={goal.review_at}; "
                f"metrics={goal.metrics}"
            )
            for goal in stored_goals
            if agent_id == AgentId.CHIEF_OF_STAFF or goal.owner_agent == agent_id
        ]
        if not stored_goals:
            active_goals = [goal for goal in self.profile.goals if goal.status == "active"]
            context_lines.extend(f"Legacy profile goal [{goal.domain}]: {goal.title}" for goal in active_goals)
        if agent_id == AgentId.BRIEFING_INTERN:
            context_lines.extend(
                f"Approved source [{source.kind}]: {source.id} via {source.access}"
                for source in self.profile.sources
                if source.enabled
            )
        context_lines.extend(f"Confirmed memory: {memory.fact}" for memory in memories)
        if agent_id == AgentId.CHIEF_ARCHIVIST:
            records = self.store.search_knowledge_records(
                request.tenant_id, query=request.message, limit=8
            )
            context_lines.extend(
                (
                    f"Confirmed knowledge record [{record.source_title} / {record.topic}]: "
                    f"summary={record.user_summary}; interview_recall={record.interview_recall}; "
                    f"gaps={record.gaps}"
                )
                for record in records
            )
        return self.client.respond(agent, request.message, "\n".join(context_lines))
