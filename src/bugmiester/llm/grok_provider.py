"""Grok (xAI) provider; OpenAI-compatible HTTP. Stub — Slice 13."""

from __future__ import annotations

from bugmiester.config import Settings


def generate_raw(prompt: str, settings: Settings) -> str:
    raise NotImplementedError(
        "Grok generate_raw is not implemented yet (Slice 13). "
        "Set llm.provider to mock for local play."
    )


def judge_raw(prompt: str, settings: Settings) -> str:
    raise NotImplementedError(
        "Grok judge_raw is not implemented yet (Slice 13). "
        "Set llm.provider to mock for local play."
    )
