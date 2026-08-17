"""Mock LLM fixtures for local UI/scoring."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from bugmiester.freshness import GeneratedSnippet, HistoryEntry, ScenarioSeed


@dataclass(frozen=True)
class MockSnippet:
    code: str
    bug_summary: str
    bug_category: str
    difficulty: str
    hints: tuple[str, ...] = field(default_factory=tuple)
    keywords: tuple[str, ...] = field(default_factory=tuple)


# Ten distinct one-bug Swift snippets for a full mock round.
MOCK_SNIPPETS: tuple[MockSnippet, ...] = (
    MockSnippet(
        code="""\
func firstName(from dict: [String: String]) -> String {
    return dict["name"]!
}
""",
        bug_summary="Force unwrap of a dictionary value that may be nil",
        bug_category="optionals",
        difficulty="beginner",
        hints=("Look at the ! operator",),
        keywords=("force unwrap", "optional", "nil", "dictionary"),
    ),
    MockSnippet(
        code="""\
func average(_ values: [Int]) -> Int {
    return values.reduce(0, +) / values.count
}
""",
        bug_summary="Division by zero when the array is empty",
        bug_category="collections",
        difficulty="beginner",
        hints=("What if values is empty?",),
        keywords=("division by zero", "empty", "count", "zero"),
    ),
    MockSnippet(
        code="""\
class Counter {
    var value = 0
}

func bump(_ counter: Counter) {
    var copy = counter
    copy.value += 1
}
""",
        bug_summary="Misleading copy of a class reference; intent may assume value semantics",
        bug_category="value vs reference",
        difficulty="intermediate",
        hints=("Counter is a class",),
        keywords=("class", "reference", "copy", "struct"),
    ),
    MockSnippet(
        code="""\
func label(for status: Int) -> String {
    switch status {
    case 0:
        return "ok"
    case 1:
        return "retry"
    }
}
""",
        bug_summary="Switch on Int is not exhaustive; missing default or remaining cases",
        bug_category="control flow",
        difficulty="beginner",
        hints=("Does every Int match a case?",),
        keywords=("exhaustive", "switch", "default", "missing"),
    ),
    MockSnippet(
        code="""\
func loadUser(id: String) async -> String {
    let data = try await fetch(id)
    return String(decoding: data, as: UTF8.self)
}
""",
        bug_summary="async function uses try without throws or try/catch handling",
        bug_category="errors",
        difficulty="intermediate",
        hints=("try appears without throws",),
        keywords=("throws", "try", "error", "async"),
    ),
    MockSnippet(
        code="""\
var items = ["a", "b", "c"]
let last = items[items.count]
print(last)
""",
        bug_summary="Off-by-one index uses count instead of count - 1",
        bug_category="collections",
        difficulty="beginner",
        hints=("Valid indices are 0..<count",),
        keywords=("off-by-one", "index", "count", "out of range", "bounds"),
    ),
    MockSnippet(
        code="""\
func greet(_ name: String?) {
    print("Hello, \\(name)")
}
""",
        bug_summary="Optional String interpolated directly prints Optional(...) or is type-incorrect intent",
        bug_category="optionals",
        difficulty="beginner",
        hints=("name is optional",),
        keywords=("optional", "unwrap", "interpolation", "nil"),
    ),
    MockSnippet(
        code="""\
import Foundation

func save(text: String, to url: URL) {
    try? text.write(to: url, atomically: true, encoding: .utf8)
    print("saved")
}
""",
        bug_summary="Ignoring write failure with try? still prints saved",
        bug_category="errors",
        difficulty="intermediate",
        hints=("try? can yield nil on failure",),
        keywords=("try?", "ignore", "error", "failure", "write"),
    ),
    MockSnippet(
        code="""\
actor Box {
    var value = 0
}

func bump(_ box: Box) async {
    box.value += 1
}
""",
        bug_summary="Actor-isolated property mutated without await crossing isolation",
        bug_category="concurrency",
        difficulty="advanced",
        hints=("Actor isolation",),
        keywords=("actor", "isolation", "await", "concurrency"),
    ),
    MockSnippet(
        code="""\
struct Point {
    var x: Int
    var y: Int
}

let origin = Point(x: 0, y: 0)
origin.x = 1
""",
        bug_summary="Cannot mutate a let struct value; origin.x = 1 is illegal",
        bug_category="value vs reference",
        difficulty="beginner",
        hints=("origin is declared with let",),
        keywords=("let", "mutate", "struct", "immutable", "var"),
    ),
)

# Primary mock output keyed by scenario seed_id (aligned with SEED_POOL).
SEED_SNIPPETS: dict[str, MockSnippet] = {
    "opt-dict-force": MOCK_SNIPPETS[0],
    "col-empty-avg": MOCK_SNIPPETS[1],
    "ref-class-copy": MOCK_SNIPPETS[2],
    "flow-switch-int": MOCK_SNIPPETS[3],
    "err-async-try": MOCK_SNIPPETS[4],
    "col-off-by-one": MOCK_SNIPPETS[5],
    "opt-greet-print": MOCK_SNIPPETS[6],
    "err-try-optional": MOCK_SNIPPETS[7],
    "conc-actor-mut": MOCK_SNIPPETS[8],
    "val-let-struct": MOCK_SNIPPETS[9],
    "opt-array-first": MockSnippet(
        code="""\
func first(_ values: [Int]) -> Int {
    return values[0]
}
""",
        bug_summary="Unconditional [0] crashes on an empty array",
        bug_category="optionals",
        difficulty="beginner",
        hints=("Check isEmpty first",),
        keywords=("empty", "index", "crash", "bounds"),
    ),
    "conc-await-miss": MockSnippet(
        code="""\
func load() async -> String {
    return fetchRemote()
}
func fetchRemote() async -> String { "ok" }
""",
        bug_summary="Missing await when calling an async function",
        bug_category="concurrency",
        difficulty="intermediate",
        hints=("fetchRemote is async",),
        keywords=("await", "async", "missing"),
    ),
}


class MockProvider:
    """Seed-aware canned snippets; no network calls."""

    def __init__(
        self,
        snippets: tuple[MockSnippet, ...] = MOCK_SNIPPETS,
        seed_map: dict[str, MockSnippet] | None = None,
    ) -> None:
        if not snippets:
            raise ValueError("MockProvider requires at least one snippet")
        self._snippets = snippets
        self._seed_map = seed_map if seed_map is not None else dict(SEED_SNIPPETS)
        self._cursor = 0

    def generate_for_seed(
        self,
        seed: ScenarioSeed,
        _avoid: Sequence[HistoryEntry] | None = None,
    ) -> GeneratedSnippet:
        snip = self._seed_map.get(seed.seed_id)
        if snip is None:
            snip = next(
                (s for s in self._snippets if s.bug_category == seed.category),
                self._snippets[self._cursor % len(self._snippets)],
            )
            self._cursor += 1
        return GeneratedSnippet(
            code=snip.code,
            bug_summary=snip.bug_summary,
            bug_category=snip.bug_category,
            difficulty=snip.difficulty,
            hints=snip.hints,
            keywords=snip.keywords,
            seed=seed,
        )

    def next_snippet(self, round_index: int) -> MockSnippet:
        """Legacy index rotation (prefer generate_for_seed)."""
        if round_index < len(self._snippets):
            return self._snippets[round_index]
        snippet = self._snippets[self._cursor % len(self._snippets)]
        self._cursor += 1
        return snippet
