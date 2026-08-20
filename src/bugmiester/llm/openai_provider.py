"""OpenAI chat completions provider (generate + judge)."""

from __future__ import annotations

from typing import Any

from bugmiester.config import Settings

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


class OpenAIConfigError(RuntimeError):
    """Missing / unusable OpenAI API key."""


class OpenAIRequestError(RuntimeError):
    """OpenAI API call failed."""


def _require_api_key(settings: Settings) -> str:
    key = (settings.api_key or "").strip()
    if not key or not settings.config_ready:
        raise OpenAIConfigError(
            "OPENAI_API_KEY is missing or still a placeholder. "
            f"Set it in {settings.env_path}"
        )
    return key


def _build_client(settings: Settings):
    from openai import OpenAI

    api_key = _require_api_key(settings)
    kwargs: dict[str, Any] = {
        "api_key": api_key,
        "timeout": float(settings.llm.timeout_seconds),
    }
    if settings.llm.base_url:
        kwargs["base_url"] = settings.llm.base_url
    return OpenAI(**kwargs)


def _response_format(name: str, schema: dict[str, Any], *, use_schema: bool) -> dict[str, Any]:
    if use_schema:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": name,
                "strict": True,
                "schema": schema,
            },
        }
    return {"type": "json_object"}


def _omit_temperature(model: str) -> bool:
    """GPT-5 / reasoning models only accept the default temperature."""
    name = (model or "").strip().lower().replace("_", "-")
    return (
        name.startswith("gpt-5")
        or name.startswith("o1")
        or name.startswith("o3")
        or name.startswith("o4")
    )


def _temperature_rejected(exc: BaseException) -> bool:
    message = str(exc).lower()
    return "temperature" in message and (
        "unsupported" in message
        or "does not support" in message
        or "only the default" in message
        or "invalid_request" in message
        or "unsupported_value" in message
    )


def _completions_create(client: Any, kwargs: dict[str, Any]) -> Any:
    try:
        return client.chat.completions.create(**kwargs)
    except OpenAIConfigError:
        raise
    except OpenAIRequestError:
        raise
    except Exception as exc:  # noqa: BLE001
        if "temperature" in kwargs and _temperature_rejected(exc):
            retry = {key: value for key, value in kwargs.items() if key != "temperature"}
            try:
                return client.chat.completions.create(**retry)
            except OpenAIConfigError:
                raise
            except OpenAIRequestError:
                raise
            except Exception as retry_exc:  # noqa: BLE001
                raise OpenAIRequestError(
                    f"OpenAI request failed: {retry_exc}"
                ) from retry_exc
        raise


def _chat_json(
    settings: Settings,
    *,
    system: str,
    user: str,
    temperature: float,
    schema_name: str,
    schema: dict[str, Any],
    timeout_seconds: float | None = None,
) -> str:
    client = _build_client(settings)
    if timeout_seconds is not None and hasattr(client, "with_options"):
        client = client.with_options(timeout=float(timeout_seconds))
    model = settings.llm.model
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    # Prefer structured json_schema; fall back to json_object if the model rejects it.
    last_error: Exception | None = None
    for use_schema in (True, False):
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "response_format": _response_format(
                    schema_name, schema, use_schema=use_schema
                ),
                "messages": messages,
            }
            if not _omit_temperature(model):
                kwargs["temperature"] = temperature
            response = _completions_create(client, kwargs)
            choice = response.choices[0]
            content = choice.message.content
            if not content or not str(content).strip():
                raise OpenAIRequestError("OpenAI returned empty content")
            return str(content)
        except OpenAIConfigError:
            raise
        except OpenAIRequestError:
            raise
        except Exception as exc:  # noqa: BLE001 — map SDK / HTTP errors
            last_error = exc
            message = str(exc).lower()
            # Retry without schema only when schema appears unsupported.
            if use_schema and (
                "response_format" in message
                or "json_schema" in message
                or "invalid_json_schema" in message
            ):
                continue
            raise OpenAIRequestError(f"OpenAI request failed: {exc}") from exc

    raise OpenAIRequestError(f"OpenAI request failed: {last_error}")


def generate_raw(prompt: str, settings: Settings) -> str:
    """Call OpenAI for generation JSON (uses config model/temperature/timeout)."""
    return _chat_json(
        settings,
        system=(
            "You are Bugmiester's Swift puzzle generator. "
            "Reply with JSON only that matches the requested contract."
        ),
        user=prompt,
        temperature=float(settings.llm.temperature),
        schema_name="bugmiester_generation",
        schema=GENERATION_JSON_SCHEMA,
    )


def judge_raw(prompt: str, settings: Settings) -> str:
    """Call OpenAI for judge JSON (uses judge_temperature)."""
    return _chat_json(
        settings,
        system=(
            "You are Bugmiester's answer judge. "
            "Be careful and slightly generous. Reply with JSON only."
        ),
        user=prompt,
        temperature=float(settings.llm.judge_temperature),
        schema_name="bugmiester_judge",
        schema=JUDGE_JSON_SCHEMA,
    )


def recovery_raw(prompt: str, settings: Settings) -> str:
    """Call OpenAI for recovery distractors (short timeout)."""
    return _chat_json(
        settings,
        system=(
            "You write plausible wrong answers for a Swift bug quiz. "
            "Reply with JSON only."
        ),
        user=prompt,
        temperature=float(settings.llm.temperature),
        schema_name="bugmiester_recovery",
        schema=RECOVERY_JSON_SCHEMA,
        timeout_seconds=float(settings.recovery.timeout_seconds),
    )
