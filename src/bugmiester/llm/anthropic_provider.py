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
        "give_up": {"type": "boolean"},
        "feedback": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["correct", "partial", "give_up", "feedback", "confidence"],
    "additionalProperties": False,
}

RECOVERY_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "distractors": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["distractors"],
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


def _omit_sampling(model: str) -> bool:
    """Newer Claude models reject non-default temperature / top_p / top_k."""
    name = (model or "").strip().lower().replace("_", "-")
    return (
        "sonnet-5" in name
        or "opus-4-7" in name
        or "opus-4-8" in name
        or "opus-4.7" in name
        or "opus-4.8" in name
    )


def _adaptive_thinking_default(model: str) -> bool:
    """Sonnet 5 / newer Opus think unless the request turns it off."""
    return _omit_sampling(model)


def _temperature_rejected(exc: BaseException) -> bool:
    message = str(exc).lower()
    return "temperature" in message and (
        "deprecated" in message
        or "invalid_request" in message
        or "not accepted" in message
        or "sampling" in message
    )


def _messages_create(client: Any, kwargs: dict[str, Any]) -> Any:
    try:
        return client.messages.create(**kwargs)
    except AnthropicConfigError:
        raise
    except AnthropicRequestError:
        raise
    except Exception as exc:  # noqa: BLE001
        if "temperature" in kwargs and _temperature_rejected(exc):
            retry = {key: value for key, value in kwargs.items() if key != "temperature"}
            try:
                return client.messages.create(**retry)
            except AnthropicConfigError:
                raise
            except AnthropicRequestError:
                raise
            except Exception as retry_exc:  # noqa: BLE001
                raise AnthropicRequestError(
                    f"Anthropic request failed: {retry_exc}"
                ) from retry_exc
        raise


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
    timeout_seconds: float | None = None,
) -> str:
    """
    Force structured JSON via Anthropic tool_use (reliable Messages strategy).

    Falls back to plain text JSON if tool_use is rejected by the API/model.
    """
    client = _build_client(settings)
    if timeout_seconds is not None and hasattr(client, "with_options"):
        client = client.with_options(timeout=float(timeout_seconds))
    model = settings.llm.model
    messages = [{"role": "user", "content": user}]
    tools = [
        {
            "name": tool_name,
            "description": tool_description,
            "input_schema": schema,
        }
    ]
    common: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
        "tools": tools,
        "tool_choice": {"type": "tool", "name": tool_name},
    }
    if not _omit_sampling(model):
        common["temperature"] = temperature
    if _adaptive_thinking_default(model):
        # Adaptive thinking is on by default and shares max_tokens with tool JSON.
        common["thinking"] = {"type": "disabled"}

    try:
        response = _messages_create(client, common)
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

    plaintext: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": (
            f"{system} Reply with a single JSON object only — no markdown fences."
        ),
        "messages": messages,
    }
    if not _omit_sampling(model):
        plaintext["temperature"] = temperature
    if _adaptive_thinking_default(model):
        plaintext["thinking"] = {"type": "disabled"}
    try:
        response = _messages_create(client, plaintext)
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
        max_tokens=4096,
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


def recovery_raw(prompt: str, settings: Settings) -> str:
    """Call Anthropic for recovery distractors (short timeout)."""
    return _messages_json(
        settings,
        system=(
            "You write plausible wrong answers for a Swift bug quiz. "
            "Fill the tool arguments with recovery JSON."
        ),
        user=prompt,
        temperature=float(settings.llm.temperature),
        tool_name="bugmiester_recovery",
        tool_description="Record wrong multiple-choice answers that are not the real bug.",
        schema=RECOVERY_JSON_SCHEMA,
        max_tokens=1024,
        timeout_seconds=float(settings.recovery.timeout_seconds),
    )
