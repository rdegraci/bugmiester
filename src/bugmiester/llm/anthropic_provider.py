"""Anthropic Messages API provider (generate + judge)."""

from __future__ import annotations

import json
from typing import Any

from bugmiester.config import Settings

# Same contracts as the OpenAI path / shared parse layer.
GENERATION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "code": {"type": "string"},
        "bug_summary": {"type": "string"},
        "bug_category": {"type": "string"},
        "difficulty": {
            "type": "string",
            "enum": ["beginner", "intermediate", "advanced"],
        },
        "hints": {"type": "array", "items": {"type": "string"}},
        "keywords": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "code",
        "bug_summary",
        "bug_category",
        "difficulty",
        "hints",
        "keywords",
    ],
    "additionalProperties": False,
}

JUDGE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "correct": {"type": "boolean"},
        "partial": {"type": "boolean"},
        "feedback": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["correct", "partial", "feedback", "confidence"],
    "additionalProperties": False,
}


class AnthropicConfigError(RuntimeError):
    """Missing / unusable Anthropic API key."""


class AnthropicRequestError(RuntimeError):
    """Anthropic API call failed."""


def _require_api_key(settings: Settings) -> str:
    key = (settings.api_key or "").strip()
    if not key or not settings.config_ready:
        raise AnthropicConfigError(
            "ANTHROPIC_API_KEY is missing or still a placeholder. "
            f"Set it in {settings.env_path}"
        )
    return key


def _build_client(settings: Settings):
    from anthropic import Anthropic

    api_key = _require_api_key(settings)
    kwargs: dict[str, Any] = {
        "api_key": api_key,
        "timeout": float(settings.llm.timeout_seconds),
    }
    if settings.llm.base_url:
        kwargs["base_url"] = settings.llm.base_url
    return Anthropic(**kwargs)


def _text_from_content(blocks: Any) -> str:
    parts: list[str] = []
    for block in blocks or []:
        btype = getattr(block, "type", None)
        if btype == "text":
            text = getattr(block, "text", "") or ""
            if text:
                parts.append(str(text))
        elif isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text") or ""
            if text:
                parts.append(str(text))
    return "\n".join(parts).strip()


def _tool_input_json(blocks: Any, tool_name: str) -> str | None:
    for block in blocks or []:
        btype = getattr(block, "type", None)
        name = getattr(block, "name", None)
        tool_input = getattr(block, "input", None)
        if isinstance(block, dict):
            btype = block.get("type", btype)
            name = block.get("name", name)
            tool_input = block.get("input", tool_input)
        if btype == "tool_use" and name == tool_name and tool_input is not None:
            if isinstance(tool_input, str):
                return tool_input
            return json.dumps(tool_input, ensure_ascii=False)
    return None


def _messages_json(
    settings: Settings,
    *,
    system: str,
    user: str,
    temperature: float,
    tool_name: str,
    tool_description: str,
    schema: dict[str, Any],
    max_tokens: int = 2048,
) -> str:
    """
    Force structured JSON via Anthropic tool_use (reliable Messages strategy).

    Falls back to plain text JSON if tool_use is rejected by the API/model.
    """
    client = _build_client(settings)
    model = settings.llm.model
    messages = [{"role": "user", "content": user}]
    tools = [
        {
            "name": tool_name,
            "description": tool_description,
            "input_schema": schema,
        }
    ]

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=messages,
            tools=tools,
            tool_choice={"type": "tool", "name": tool_name},
        )
        raw = _tool_input_json(response.content, tool_name)
        if raw and raw.strip():
            return raw
        # Unexpected shape — try text content before failing.
        text = _text_from_content(response.content)
        if text:
            return text
        raise AnthropicRequestError("Anthropic returned no tool_use JSON")
    except AnthropicConfigError:
        raise
    except AnthropicRequestError:
        raise
    except Exception as exc:  # noqa: BLE001
        message = str(exc).lower()
        # Some models / accounts may reject tool_choice; retry prompt-only JSON.
        if "tool" not in message and "tool_choice" not in message:
            raise AnthropicRequestError(f"Anthropic request failed: {exc}") from exc

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=(
                f"{system} Reply with a single JSON object only — no markdown fences."
            ),
            messages=messages,
        )
        text = _text_from_content(response.content)
        if not text:
            raise AnthropicRequestError("Anthropic returned empty content")
        return text
    except AnthropicConfigError:
        raise
    except AnthropicRequestError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AnthropicRequestError(f"Anthropic request failed: {exc}") from exc


def generate_raw(prompt: str, settings: Settings) -> str:
    """Call Anthropic for generation JSON (model/temperature/timeout from config)."""
    return _messages_json(
        settings,
        system=(
            "You are Bugmiester's Swift puzzle generator. "
            "Fill the tool arguments with the generation JSON contract."
        ),
        user=prompt,
        temperature=float(settings.llm.temperature),
        tool_name="bugmiester_generation",
        tool_description=(
            "Record one Swift snippet with exactly one intentional bug and its answer key."
        ),
        schema=GENERATION_JSON_SCHEMA,
    )


def judge_raw(prompt: str, settings: Settings) -> str:
    """Call Anthropic for judge JSON (uses judge_temperature)."""
    return _messages_json(
        settings,
        system=(
            "You are Bugmiester's answer judge. "
            "Be careful and slightly generous. Fill the tool arguments with judge JSON."
        ),
        user=prompt,
        temperature=float(settings.llm.judge_temperature),
        tool_name="bugmiester_judge",
        tool_description="Score whether the player identified the intended bug.",
        schema=JUDGE_JSON_SCHEMA,
        max_tokens=1024,
    )
