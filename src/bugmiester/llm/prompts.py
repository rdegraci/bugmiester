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
- Honor any seed constraint exactly. Keep the same bug class; change the costume.
- Costume variation (required): invent a fresh surface each time — different type/function names, domain, and API shape. Do not reuse a stock textbook skeleton for this seed (for example the same URLSession+continuation, Counter actor, or Board/@MainActor demo). Prefer an uncommon but realistic setting that still demonstrates the seed.
- Vary control-flow shape when the constraint still holds (different branching, callback style, or call sites) so the snippet does not look like a near-clone of a common sample.
- Stealth (required): the snippet must look like ordinary production {language} if the bug were fixed. Do not telegraph the defect.
- No puzzle tells: no suspicious names (e.g. unsafe, force, bug, broken, wrong), no dead decoy lines, no "look here" structure, no contrived one-liner that exists only to showcase the bug.
- Correctness path (required): the buggy site must look correct under a common / plausible reading of the code (for example "this await is fine if you assume MainActor", "this capture looks intentional", "this unwrap is safe after the earlier check"). The challenge should come from a wrong mental model, not from an obviously broken token.
- Cross-site bug (required): the defect must only become clear when the reader follows how pieces interact across call sites or scopes (A → B → C: e.g. setup, call, and use; or definition and two call sites). Do not put a self-contained one-line giveaway that needs no surrounding context — still honor the seed constraint and stay one screen.
- Red herring (encouraged): include at most ONE nearby lookalike that appears suspicious but is actually correct / safe / intentional in context (for example a force-unwrap after a guaranteed non-nil check, or a correct await). It must not be a second real defect.
- Still exactly ONE real bug. "bug_summary" and "keywords" must describe only that real bug — never the red herring.
- Length: prefer about 30–45 lines of {language}. Aim under 45 lines; never exceed 60 lines.
- No multiple interacting defects (the red herring does not count as a bug).
- The JSON "code" must contain the bug. Do not return the correct snippet.
- "code" must contain no comments (no //, no /* */, no ///). Do not label the bug or the red herring in the source. Put any hint only in "hints".
- "bug_summary" is one short sentence that names the defect. Not a tutorial. Not the fix.
- Short enough to read carefully in under a minute (one screen on a laptop).
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

The snippet may include a red herring: code that looks suspicious but is not the intended bug. Only the expected bug summary below counts as correct.

Swift code:
```
{code}
```

Expected bug summary (the ONE real bug):
{expected_summary}

Player answer:
{player_answer}

Return ONLY valid JSON with these keys:
- "correct": boolean (true only if the player clearly named the intended bug above)
- "partial": boolean (true for incomplete but on-track answers about that same bug; false if correct)
- "give_up": boolean (true if the player is declining to guess — e.g. "I don't know", "no clue", "beats me", "pass" — not a real bug hypothesis)
- "feedback": string (short verdict only, e.g. "Yes." / "Partially correct." / "Not quite." — do not repeat the expected bug summary; use "" when give_up is true)
- "confidence": number from 0.0 to 1.0

If the player only names a red herring / lookalike and misses the expected bug, mark correct=false and partial=false.
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
