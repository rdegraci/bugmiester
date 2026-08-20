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
    The model should invent a correct use of the seed feature, then break it
    once; only the broken snippet is returned.
    """
    avoid = _format_avoid_list(avoid_list)
    return f"""You write short {language} code puzzles for a bug-spotting game.

Scenario seed:
{format_scenario_seed(seed)}

Work in this order. Do not put the correct version in the JSON:
1. Mentally write a short, correct {language} example that uses this seed's language feature (category and setting).
2. Introduce exactly ONE intentional bug of that seed's class (correctness / runtime / compile-logic — not style).
3. Return only the broken snippet.

Rules:
- The bug must fit this seed's category. Do not substitute a generic force-unwrap or missing await unless the category requires it.
- No multiple interacting defects.
- The JSON "code" must contain the bug. Do not return the correct snippet.
- "code" must contain no comments (no //, no /* */, no ///). Do not label the bug in the source. Put any hint only in "hints".
- "bug_summary" is one short sentence that names the defect. Not a tutorial. Not the fix.
- Short enough to read on one screen.
- Do NOT reuse or near-duplicate anything on the avoid-list.
- Do not reuse an avoid-list failure mode (for example a second force-unwrap, a second missing await, or a second empty-array crash).

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
- "give_up": boolean (true if the player is declining to guess — e.g. "I don't know", "no clue", "beats me", "pass" — not a real bug hypothesis)
- "feedback": string (short verdict only, e.g. "Yes." / "Partially correct." / "Not quite." — do not repeat the expected bug summary; use "" when give_up is true)
- "confidence": number from 0.0 to 1.0

If give_up is true, set correct and partial to false.
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

The player already has partial credit. The quiz tests a precise reading of THIS bug, not a different bug class.

Swift code:
```
{code}
```

The ONE real bug is:
{expected_summary}

Player partial answer (you may use this as one wrong choice if it is a different claim; do not copy the real bug):
{player_answer}

Return ONLY valid JSON with this key:
- "distractors": array of exactly {n} strings

Rules:
- Each distractor is an incorrect variant of this same bug: a nearby misreading of this feature or this snippet.
- Use a wrong mechanism, a wrong location, or a true fact that is not the bug (for example initial empty state).
- Do not name a different bug class (retain cycle, integer overflow, missing await) unless that class is the real bug.
- Do not paraphrase the real bug. The same claim in different words is not a distractor.
- One short sentence each.
- No numbering, no labels like "A)" or "wrong".
"""
