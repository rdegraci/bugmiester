"""LLM facade: generate_bug(), judge_answer().

Heavy imports live in ``facade.py`` so ``llm.parse`` can load without cycles
(``freshness`` → ``parse`` must not pull in the full facade).
"""

from __future__ import annotations

from typing import Any

from bugmiester.llm.base import JudgeResult, SnippetWithKey
from bugmiester.llm.parse import ParseError

__all__ = [
    "GenerateBugResult",
    "JudgeResult",
    "ParseError",
    "SnippetWithKey",
    "generate_bug",
    "judge_answer",
]


def __getattr__(name: str) -> Any:
    if name in {"generate_bug", "judge_answer", "GenerateBugResult"}:
        from bugmiester.llm import facade

        return getattr(facade, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
