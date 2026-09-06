from __future__ import annotations

import base64
import json
import os

import httpx

from life_os.models import AgentId, PhotoAnalysis


def analyze_check_in_photo(
    *, agent_id: AgentId, prompt: str, media_type: str, image: bytes
) -> PhotoAnalysis | None:
    """Analyze an explicitly approved image without retaining it at the model provider."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or media_type not in {"image/jpeg", "image/png", "image/webp"}:
        return None

    purpose = (
        "Identify visible food and approximate portions. Estimate total calories, protein, "
        "carbohydrates, fat, fiber, and calcium. Use a single best estimate for each numeric field, "
        "explain important assumptions, and do not claim exact nutrition from an image."
        if agent_id == AgentId.NUTRITION_COACH
        else "Describe visible workout, recovery, equipment, or activity-tracker evidence. "
        "Do not diagnose health conditions or infer completion beyond what is visible."
    )
    encoded = base64.b64encode(image).decode("ascii")
    content = [
        {"type": "input_text", "text": f"Check-in context: {prompt}"},
        {
            "type": "input_image",
            "image_url": f"data:{media_type};base64,{encoded}",
            "detail": "low",
        },
    ]
    return _request_analysis(content, purpose)


def analyze_nutrition_description(
    *, prompt: str, description: str
) -> PhotoAnalysis | None:
    """Estimate nutrition from a user-provided meal description."""
    if not os.getenv("OPENAI_API_KEY"):
        return None
    purpose = (
        "Estimate total calories, protein, carbohydrates, fat, fiber, and calcium from the user's "
        "meal description. Use a single best estimate for each numeric field, state portion "
        "assumptions, and do not present estimates as exact measurements."
    )
    content = [
        {
            "type": "input_text",
            "text": f"Check-in context: {prompt}\nWhat the user ate: {description}",
        }
    ]
    return _request_analysis(content, purpose)


def analyze_nutrition_input(
    *, prompt: str, description: str, images: list[tuple[str, bytes]]
) -> PhotoAnalysis | None:
    """Estimate one meal from a combined text and multi-image message."""
    if not os.getenv("OPENAI_API_KEY"):
        return None
    purpose = (
        "Treat every attached image and the user's text as evidence about one meal. "
        "Use different angles to avoid double-counting the same food. Estimate total "
        "calories, protein, carbohydrates, fat, fiber, and calcium for the meal as a whole. "
        "Use a single best estimate for each numeric field, state portion assumptions, "
        "and do not present estimates as exact measurements."
    )
    content: list[dict] = [
        {
            "type": "input_text",
            "text": (
                f"Check-in context: {prompt}\n"
                f"User message: {description.strip() or 'Meal shown in the attached images.'}"
            ),
        }
    ]
    for media_type, image in images:
        encoded = base64.b64encode(image).decode("ascii")
        content.append(
            {
                "type": "input_image",
                "image_url": f"data:{media_type};base64,{encoded}",
                "detail": "low",
            }
        )
    return _request_analysis(content, purpose)


def _request_analysis(content: list[dict], purpose: str) -> PhotoAnalysis:
    api_key = os.environ["OPENAI_API_KEY"]
    schema = PhotoAnalysis.model_json_schema()
    payload = {
        "model": os.getenv("LIFE_OS_MODEL", "gpt-5.6-luna"),
        "store": False,
        "instructions": (
            "You analyze user-approved evidence for a private personal tracker. "
            "Be concise, distinguish observation from estimate, and state uncertainty. "
            f"{purpose}"
        ),
        "input": [{"role": "user", "content": content}],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "life_os_nutrition_analysis",
                "strict": False,
                "schema": schema,
            }
        },
    }
    response = httpx.post(
        "https://api.openai.com/v1/responses",
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=90,
    )
    response.raise_for_status()
    data = response.json()
    output_text = data.get("output_text") or _extract_output_text(data)
    return PhotoAnalysis.model_validate(json.loads(output_text))


def _extract_output_text(data: dict) -> str:
    for item in data.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return content["text"]
    raise ValueError("Responses API returned no photo analysis")
