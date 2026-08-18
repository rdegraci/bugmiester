"""OpenAI provider. Stub — Slice 11."""

from __future__ import annotations

from bugmiester.config import Settings


def generate_raw(prompt: str, settings: Settings) -> str:
    raise NotImplementedError(
        "OpenAI generate_raw is not implemented yet (Slice 11). "
        "Set llm.provider to mock for local play."
    )


def judge_raw(prompt: str, settings: Settings) -> str:
    raise NotImplementedError(
        "OpenAI judge_raw is not implemented yet (Slice 11). "
        "Set llm.provider to mock for local play."
    )
