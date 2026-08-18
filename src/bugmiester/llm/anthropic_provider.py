"""Anthropic provider. Stub — Slice 12."""

from __future__ import annotations

from bugmiester.config import Settings


def generate_raw(prompt: str, settings: Settings) -> str:
    raise NotImplementedError(
        "Anthropic generate_raw is not implemented yet (Slice 12). "
        "Set llm.provider to mock for local play."
    )


def judge_raw(prompt: str, settings: Settings) -> str:
    raise NotImplementedError(
        "Anthropic judge_raw is not implemented yet (Slice 12). "
        "Set llm.provider to mock for local play."
    )
