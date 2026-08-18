"""Generation + judge prompts (shared across providers)."""

from __future__ import annotations

from collections.abc import Sequence

from bugmiester.freshness import HistoryEntry, ScenarioSeed


def _format_avoid_list(avoid_list: Sequence[HistoryEntry], *, limit: int = 20) -> str:
    if not avoid_list:
        return "(none yet)"
    lines: list[str] = []
    for entry in list(avoid_list)[-limit:]:
        lines.append(
            f"- [{entry.bug_category}] {entry.bug_summary} (theme: {entry.theme})"
        )
    return "\n".join(lines)


def format_scenario_seed(seed: ScenarioSeed) -> str:
    parts = [
        f"category: {seed.category}",
        f"setting: {seed.setting}",
    ]
    if seed.constraint:
        parts.append(f"constraint: {seed.constraint}")
    parts.append(f"seed_id: {seed.seed_id}")
    return "; ".join(parts)


def build_generation_prompt(
    seed: ScenarioSeed,
    avoid_list: Sequence[HistoryEntry],
    *,
    language: str = "swift",
) -> str:
    """
    Prompt for one-bug Swift snippet JSON.

    Contract keys: code, bug_summary, bug_category, difficulty, hints.
    """
    avoid = _format_avoid_list(avoid_list)
    return f"""You write short {language} code puzzles for a bug-spotting game.

Task: Write a NEW {language} snippet for this scenario seed:
{format_scenario_seed(seed)}

Rules:
- Exactly ONE intentional bug (correctness / runtime / compile-logic — not style).
- No multiple interacting defects.
- Short enough to read on one screen.
- Do NOT reuse or near-duplicate anything on the avoid-list.

Avoid-list (do not reuse):
{avoid}

Return ONLY valid JSON with these keys:
- "code": string ({language} source with the bug)
- "bug_summary": string (canonical explanation of the one bug)
- "bug_category": string (short tag, e.g. optionals)
- "difficulty": "beginner" | "intermediate" | "advanced"
- "hints": array of strings (short hints; server-only until after submit)
Optional: "keywords": array of strings useful for scoring.
"""


def build_judge_prompt(
    *,
    code: str,
    expected_summary: str,
    player_answer: str,
) -> str:
    """Prompt for low-temperature answer judging JSON."""
    return f"""You judge whether a player correctly identified the bug in a Swift snippet.

Use a careful, generous rubric: prefer partial credit over a harsh wrong when unsure.

Swift code:
```
{code}
```

Expected bug summary:
{expected_summary}

Player answer:
{player_answer}

Return ONLY valid JSON with these keys:
- "correct": boolean (true only if the player clearly named the intended bug)
- "partial": boolean (true for incomplete but on-track answers; false if correct)
- "feedback": string (short feedback for the player)
- "confidence": number from 0.0 to 1.0
"""


def build_recovery_prompt(
    *,
    code: str,
    expected_summary: str,
    player_answer: str,
    distractor_count: int,
) -> str:
    """Prompt for wrong multiple-choice answers (not the real bug)."""
    n = max(1, distractor_count)
    return f"""You write wrong multiple-choice answers for a Swift bug-spotting game.

Swift code:
```
{code}
```

The ONE real bug is:
{expected_summary}

Player partial answer (do not reuse this as a choice):
{player_answer}

Return ONLY valid JSON with this key:
- "distractors": array of exactly {n} strings

Rules:
- Each distractor names a DIFFERENT defect a reader might believe is in this code.
- Do not paraphrase the real bug.
- One short sentence each.
- No numbering, no labels like "A)" or "wrong".
"""
