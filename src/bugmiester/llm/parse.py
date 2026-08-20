"""Validate / parse LLM JSON for generation and judging."""

from __future__ import annotations

import json
import re
from typing import Any

from bugmiester.llm.base import DIFFICULTIES, JudgeResult, SnippetWithKey

REQUIRED_GENERATION_KEYS = (
    "code",
    "bug_summary",
    "bug_category",
    "difficulty",
    "hints",
)

# Soft target in the generate prompt is ~30–45 lines; hard reject above this.
MAX_CODE_LINES = 60
MAX_CODE_CHARS = 8192


class ParseError(ValueError):
    """Raised when model output is not usable generation/judge JSON."""


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    fence = re.match(
        r"^```(?:json)?\s*([\s\S]*?)\s*```$",
        stripped,
        flags=re.IGNORECASE,
    )
    if fence:
        return fence.group(1).strip()
    return stripped


def loads_json_object(raw: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    text = _strip_code_fences(str(raw))
    if not text:
        raise ParseError("Empty model output")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ParseError(f"Invalid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ParseError("JSON root must be an object")
    return data


def _as_nonempty_str(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ParseError(f"'{field}' must be a string")
    text = value.strip()
    if not text:
        raise ParseError(f"'{field}' must be non-empty")
    return text


def _as_hints(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ParseError("'hints' must be an array of strings")
    hints: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ParseError("'hints' entries must be strings")
        cleaned = item.strip()
        if cleaned:
            hints.append(cleaned)
    return tuple(hints)


def _as_keywords(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ParseError("'keywords' must be an array of strings when present")
    words: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ParseError("'keywords' entries must be strings")
        cleaned = item.strip()
        if cleaned:
            words.append(cleaned)
    return tuple(words)


def strip_source_comments(code: str) -> str:
    """Remove // and /* */ comments from Swift-like source for the player board.

    Leaves ``//`` inside double-quoted strings (e.g. https:// URLs).
    """
    text = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    kept: list[str] = []
    for line in text.splitlines():
        cleaned = _strip_line_comment(line).rstrip()
        if not cleaned.strip():
            if kept and kept[-1] != "":
                kept.append("")
            continue
        kept.append(cleaned)
    while kept and kept[-1] == "":
        kept.pop()
    while kept and kept[0] == "":
        kept.pop(0)
    return "\n".join(kept)


def _strip_line_comment(line: str) -> str:
    in_string = False
    escape = False
    i = 0
    while i < len(line):
        ch = line[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            i += 1
            continue
        if ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
            return line[:i]
        i += 1
    return line


def _code_line_count(code: str) -> int:
    """Physical lines, ignoring a single trailing empty line from a final newline."""
    lines = code.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    return len(lines)


def _one_bug_smell(code: str, summary: str) -> None:
    """Reject obvious multi-bug / oversized payloads (light MVP checks)."""
    if len(code) > MAX_CODE_CHARS:
        raise ParseError("code is too large for MVP")
    lines = _code_line_count(code)
    if lines > MAX_CODE_LINES:
        raise ParseError(
            f"code has {lines} lines; maximum is {MAX_CODE_LINES}"
        )
    upper = code.upper()
    if "BUG 1" in upper and "BUG 2" in upper:
        raise ParseError("code appears to contain multiple labeled bugs")
    if summary.lower().count(" and ") >= 3 and "bug" in summary.lower():
        # Soft smell only when very chatty; keep permissive.
        pass


def parse_generation_payload(raw: str | dict[str, Any]) -> SnippetWithKey:
    """Validate required generation keys and return SnippetWithKey."""
    data = loads_json_object(raw)
    missing = [key for key in REQUIRED_GENERATION_KEYS if key not in data]
    if missing:
        raise ParseError(f"Missing required keys: {', '.join(missing)}")

    code = strip_source_comments(_as_nonempty_str(data["code"], "code"))
    if not code.strip():
        raise ParseError("'code' must be non-empty")
    bug_summary = _as_nonempty_str(data["bug_summary"], "bug_summary")
    bug_category = _as_nonempty_str(data["bug_category"], "bug_category")
    difficulty = _as_nonempty_str(data["difficulty"], "difficulty").lower()
    if difficulty not in DIFFICULTIES:
        raise ParseError(
            f"difficulty must be one of: {', '.join(sorted(DIFFICULTIES))}"
        )
    hints = _as_hints(data["hints"])
    keywords = _as_keywords(data.get("keywords"))
    _one_bug_smell(code, bug_summary)

    return SnippetWithKey(
        code=code,
        bug_summary=bug_summary,
        bug_category=bug_category,
        difficulty=difficulty,
        hints=hints,
        keywords=keywords,
    )


def parse_judge_payload(raw: str | dict[str, Any]) -> JudgeResult:
    """Validate judge JSON → JudgeResult."""
    data = loads_json_object(raw)
    for key in ("correct", "partial", "feedback"):
        if key not in data:
            raise ParseError(f"Missing required judge key: {key}")

    correct = data["correct"]
    partial = data["partial"]
    if not isinstance(correct, bool):
        raise ParseError("'correct' must be a boolean")
    if not isinstance(partial, bool):
        raise ParseError("'partial' must be a boolean")

    give_up_raw = data.get("give_up", False)
    if not isinstance(give_up_raw, bool):
        raise ParseError("'give_up' must be a boolean")
    give_up = bool(give_up_raw)

    if give_up:
        feedback = str(data.get("feedback") or "").strip()
        correct = False
        partial = False
    else:
        feedback = _as_nonempty_str(data["feedback"], "feedback")

    confidence_raw = data.get("confidence", 1.0)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError) as exc:
        raise ParseError("'confidence' must be a number") from exc
    confidence = max(0.0, min(1.0, confidence))

    if correct and partial:
        partial = False

    return JudgeResult(
        correct=correct,
        partial=partial,
        feedback=feedback,
        confidence=confidence,
        give_up=give_up,
    )


def parse_recovery_payload(raw: str | dict[str, Any], *, needed: int) -> list[str]:
    """Validate recovery JSON → list of distractor strings."""
    data = loads_json_object(raw)
    if "distractors" not in data:
        raise ParseError("Missing required recovery key: distractors")
    items = data["distractors"]
    if not isinstance(items, list):
        raise ParseError("'distractors' must be an array of strings")
    distractors: list[str] = []
    for item in items:
        if not isinstance(item, str):
            raise ParseError("'distractors' entries must be strings")
        cleaned = item.strip()
        if cleaned:
            distractors.append(cleaned)
    if len(distractors) < needed:
        raise ParseError(
            f"Need at least {needed} distractors, got {len(distractors)}"
        )
    return distractors[: max(needed, len(distractors))]

