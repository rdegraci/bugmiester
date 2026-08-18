"""Mock LLM fixtures for local UI/scoring."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from bugmiester.config import Settings
from bugmiester.freshness import GeneratedSnippet, HistoryEntry, ScenarioSeed
from bugmiester.llm.base import JudgeResult
from bugmiester.scoring import keyword_match_tier


@dataclass(frozen=True)
class MockSnippet:
    code: str
    bug_summary: str
    bug_category: str
    difficulty: str
    hints: tuple[str, ...] = field(default_factory=tuple)
    keywords: tuple[str, ...] = field(default_factory=tuple)

    def to_generation_json(self) -> str:
        return json.dumps(
            {
                "code": self.code,
                "bug_summary": self.bug_summary,
                "bug_category": self.bug_category,
                "difficulty": self.difficulty,
                "hints": list(self.hints),
                "keywords": list(self.keywords),
            },
            ensure_ascii=False,
        )



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
    "acc-mutating-let": MockSnippet(
        code="""\
struct Counter {
    var n = 0
    mutating func bump() { n += 1 }
}
let counter = Counter()
counter.bump()
""",
        bug_summary="Calling a mutating method on a let struct value is illegal",
        bug_category="access control",
        difficulty="beginner",
        hints=("counter is let",),
        keywords=("mutating", "let", "struct", "method"),
    ),
    "acc-private-field": MockSnippet(
        code="""\
struct Box {
    private var n = 0
}
func reveal(_ box: Box) -> Int {
    return box.n
}
""",
        bug_summary="private stored property is read from a free function outside the type",
        bug_category="access control",
        difficulty="beginner",
        hints=("private is scoped to Box",),
        keywords=("private", "access", "property", "outside"),
    ),
    "ui-state-let": MockSnippet(
        code="""\
import SwiftUI
struct CounterView: View {
    let count = 0
    var body: some View {
        Button("Add") { count += 1 }
    }
}
""",
        bug_summary="View mutates a let; the counter should be @State",
        bug_category="SwiftUI state",
        difficulty="beginner",
        hints=("@State vs let",),
        keywords=("@State", "let", "mutate", "View"),
    ),
    "ui-binding-dollar": MockSnippet(
        code="""\
import SwiftUI
struct NameForm: View {
    @State private var name = ""
    var body: some View {
        TextField("Name", text: name)
    }
}
""",
        bug_summary="TextField needs a Binding; missing $ on name",
        bug_category="SwiftUI state",
        difficulty="beginner",
        hints=("Use $name",),
        keywords=("Binding", "$", "TextField", "@State"),
    ),
    "cap-stored-self": MockSnippet(
        code="""\
class Speaker {
    var say: (() -> Void)?
    func setup() {
        say = { self.announce() }
    }
    func announce() { print("hi") }
}
""",
        bug_summary="Escaping closure stored on self captures self strongly and forms a retain cycle",
        bug_category="captures",
        difficulty="intermediate",
        hints=("[weak self]",),
        keywords=("retain cycle", "self", "closure", "weak"),
    ),
    "cap-timer-cycle": MockSnippet(
        code="""\
class Ticker {
    var timer: Timer?
    var n = 0
    func start() {
        timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { _ in
            self.n += 1
        }
    }
}
""",
        bug_summary="Stored repeating Timer retains a closure that strongly captures self",
        bug_category="captures",
        difficulty="intermediate",
        hints=("Timer plus self",),
        keywords=("Timer", "retain cycle", "self", "closure"),
    ),
    "eq-identity-id": MockSnippet(
        code="""\
class User: Equatable {
    let id: Int
    init(id: Int) { self.id = id }
    static func == (lhs: User, rhs: User) -> Bool { lhs.id == rhs.id }
}
func inList(_ users: [User], _ target: User) -> Bool {
    users.contains { $0 === target }
}
""",
        bug_summary="Uses === identity while User equality is defined by id",
        bug_category="equality",
        difficulty="intermediate",
        hints=("=== vs ==",),
        keywords=("===", "==", "identity", "Equatable"),
    ),
    "eq-missing-protocol": MockSnippet(
        code="""\
class Person {
    var name: String
    init(_ name: String) { self.name = name }
}
func sameName(_ a: Person, _ b: Person) -> Bool {
    a == b
}
""",
        bug_summary="== is used on a class that does not conform to Equatable",
        bug_category="equality",
        difficulty="beginner",
        hints=("Person is not Equatable",),
        keywords=("Equatable", "==", "class", "conform"),
    ),
}


class MockProvider:
    """Seed-aware canned snippets; no network calls."""

    def __init__(
        self,
        snippets: tuple[MockSnippet, ...] = MOCK_SNIPPETS,
        seed_map: dict[str, MockSnippet] | None = None,
        *,
        invalid_raw_queue: Sequence[str] | None = None,
    ) -> None:
        if not snippets:
            raise ValueError("MockProvider requires at least one snippet")
        self._snippets = snippets
        self._seed_map = seed_map if seed_map is not None else dict(SEED_SNIPPETS)
        self._cursor = 0
        # Optional queue of raw strings returned before normal fixtures (tests).
        self._invalid_raw_queue = list(invalid_raw_queue or [])

    def _resolve_snippet(self, seed: ScenarioSeed) -> MockSnippet:
        snip = self._seed_map.get(seed.seed_id)
        if snip is None:
            snip = next(
                (s for s in self._snippets if s.bug_category == seed.category),
                self._snippets[self._cursor % len(self._snippets)],
            )
            self._cursor += 1
        return snip

    def generate_for_seed(
        self,
        seed: ScenarioSeed,
        _avoid: Sequence[HistoryEntry] | None = None,
    ) -> GeneratedSnippet:
        snip = self._resolve_snippet(seed)
        return GeneratedSnippet(
            code=snip.code,
            bug_summary=snip.bug_summary,
            bug_category=snip.bug_category,
            difficulty=snip.difficulty,
            hints=snip.hints,
            keywords=snip.keywords,
            seed=seed,
        )

    def generate_raw(
        self,
        prompt: str,
        settings: Settings | None = None,
        *,
        seed: ScenarioSeed | None = None,
    ) -> str:
        """Return generation JSON text (optionally drained from a test fault queue)."""
        del settings  # mock ignores model/temperature
        if self._invalid_raw_queue:
            return self._invalid_raw_queue.pop(0)
        if seed is None:
            seed = self._seed_from_prompt(prompt)
        return self._resolve_snippet(seed).to_generation_json()

    def _seed_from_prompt(self, prompt: str) -> ScenarioSeed:
        match = re.search(r"seed_id:\s*([a-z0-9\-]+)", prompt)
        if match:
            seed_id = match.group(1)
            for sid, snip in self._seed_map.items():
                if sid == seed_id:
                    return ScenarioSeed(sid, snip.bug_category, sid)
            return ScenarioSeed(seed_id, "optionals", seed_id)
        return ScenarioSeed("opt-dict-force", "optionals", "dictionary lookup")

    def next_snippet(self, round_index: int) -> MockSnippet:
        """Legacy index rotation (prefer generate_for_seed)."""
        if round_index < len(self._snippets):
            return self._snippets[round_index]
        snippet = self._snippets[self._cursor % len(self._snippets)]
        self._cursor += 1
        return snippet

    def judge_raw(self, prompt: str, settings: Settings | None = None) -> str:
        """Return judge JSON text for facade parse."""
        del settings
        # Pull fields back out of the shared judge prompt shape.
        code = ""
        expected = ""
        answer = ""
        code_match = re.search(
            r"Swift code:\n```\n([\s\S]*?)\n```", prompt
        )
        if code_match:
            code = code_match.group(1)
        expected_match = re.search(
            r"Expected bug summary:\n([\s\S]*?)\n\nPlayer answer:", prompt
        )
        if expected_match:
            expected = expected_match.group(1).strip()
        answer_match = re.search(
            r"Player answer:\n([\s\S]*?)\n\nReturn ONLY valid JSON", prompt
        )
        if answer_match:
            answer = answer_match.group(1).strip()
        judged = self.judge_answer(code, expected, answer)
        return json.dumps(
            {
                "correct": judged.correct,
                "partial": judged.partial,
                "feedback": judged.feedback,
                "confidence": judged.confidence,
            }
        )

    def judge_answer(
        self,
        code: str,
        expected_summary: str,
        player_answer: str,
    ) -> JudgeResult:
        """
        Deterministic mock judge (no network).

        Uses the same keyword tiering as the scorer so hybrid/llm_judge modes
        stay exercisable without a live provider.
        """
        del code  # available for future richer fixtures
        keywords: tuple[str, ...] = ()
        for snip in self._snippets:
            if snip.bug_summary == expected_summary:
                keywords = snip.keywords
                break
        else:
            for snip in self._seed_map.values():
                if snip.bug_summary == expected_summary:
                    keywords = snip.keywords
                    break

        tier = keyword_match_tier(
            expected_summary, player_answer, keywords or None
        )
        if tier == "strong":
            return JudgeResult(
                correct=True,
                partial=False,
                feedback=f"Yes — {expected_summary}.",
                confidence=0.95,
            )
        if tier == "weak":
            return JudgeResult(
                correct=False,
                partial=True,
                feedback=f"Partially correct. Expected: {expected_summary}.",
                confidence=0.55,
            )
        stripped = player_answer.strip()
        if len(stripped) < 8:
            return JudgeResult(
                correct=False,
                partial=False,
                feedback="Too vague to judge confidently.",
                confidence=0.25,
            )
        return JudgeResult(
            correct=False,
            partial=False,
            feedback=f"Not quite. Expected: {expected_summary}.",
            confidence=0.9,
        )

    def recovery_raw(self, prompt: str, settings: Settings | None = None) -> str:
        """Wrong-answer summaries from other canned snippets (no network)."""
        del settings
        needed = 3
        count_match = re.search(r"exactly (\d+) strings", prompt, flags=re.I)
        if count_match:
            needed = max(1, int(count_match.group(1)))
        expected = ""
        expected_match = re.search(
            r"The ONE real bug is:\n([\s\S]*?)\n\nPlayer partial answer",
            prompt,
        )
        if expected_match:
            expected = expected_match.group(1).strip()
        distractors: list[str] = []
        seen = {expected.strip().lower()}
        bank = list(self._snippets) + list(self._seed_map.values())
        for snip in bank:
            summary = snip.bug_summary.strip()
            key = summary.lower()
            if key in seen:
                continue
            seen.add(key)
            distractors.append(summary)
            if len(distractors) >= needed:
                break
        return json.dumps({"distractors": distractors})


