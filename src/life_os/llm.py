from __future__ import annotations

import json
import os
from typing import Protocol

import httpx

from life_os.models import AgentDefinition, AgentId, AgentOutput


class LLMClient(Protocol):
    def respond(self, agent: AgentDefinition, message: str, context: str) -> AgentOutput: ...


class OpenAIResponsesClient:
    """Minimal Responses API client with structured output and no response storage."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("LIFE_OS_MODEL", "gpt-5.6-luna")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for live agent responses")

    def respond(self, agent: AgentDefinition, message: str, context: str) -> AgentOutput:
        schema = AgentOutput.model_json_schema()
        payload = {
            "model": self.model,
            "store": False,
            "instructions": agent.instructions,
            "input": f"Relevant confirmed context:\n{context or '(none)'}\n\nCEO request:\n{message}",
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "life_os_agent_output",
                    "strict": False,
                    "schema": schema,
                }
            },
        }
        response = httpx.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=90,
        )
        response.raise_for_status()
        data = response.json()
        output_text = data.get("output_text") or self._extract_output_text(data)
        parsed = json.loads(output_text)
        parsed["agent_id"] = agent.id
        return AgentOutput.model_validate(parsed)

    @staticmethod
    def _extract_output_text(data: dict) -> str:
        for item in data.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    return content["text"]
        raise ValueError("Responses API returned no output text")


class OfflineClient:
    """Safe local fallback used for setup and tests; it performs no model call."""

    def respond(self, agent: AgentDefinition, message: str, context: str) -> AgentOutput:
        return AgentOutput(
            agent_id=agent.id,
            summary=(
                f"{agent.name} received the request. Configure OPENAI_API_KEY for a live "
                "response; the public runtime and deterministic services are available offline."
            ),
            questions=["What outcome would count as success?"],
        )


def default_client() -> LLMClient:
    if os.getenv("OPENAI_API_KEY"):
        return OpenAIResponsesClient()
    return OfflineClient()
