"""Shared LLM types and provider protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from bugmiester.config import Settings

DIFFICULTIES = frozenset({"beginner", "intermediate", "advanced"})


@dataclass(frozen=True)
class SnippetWithKey:
    """Parsed generation JSON (answer key stays server-side)."""

    code: str
    bug_summary: str
    bug_category: str
    difficulty: str
    hints: tuple[str, ...]
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class JudgeResult:
    """Parsed judge JSON."""

    correct: bool
    partial: bool
    feedback: str
    confidence: float = 1.0


class LlmProvider(Protocol):
    """Provider adapters return raw model text (JSON) for shared parse."""

    def generate_raw(self, prompt: str, settings: Settings) -> str:
        """Return generation JSON text for the given prompt."""

    def judge_raw(self, prompt: str, settings: Settings) -> str:
        """Return judge JSON text for the given prompt."""
