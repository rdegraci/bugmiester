"""Canned per-seed fallbacks when generate attempts are exhausted."""

from __future__ import annotations

from bugmiester.freshness import GeneratedSnippet, ScenarioSeed
from bugmiester.llm.mock_provider import MockSnippet


# Distinct from primary mock bank so degraded path still teaches a clear bug.
_FALLBACK_BANK: dict[str, MockSnippet] = {
    "opt-dict-force": MockSnippet(
        code="""\
func title(from json: [String: Any]) -> String {
    return json["title"] as! String
}
""",
        bug_summary="Forced cast (as!) of a missing JSON value can crash",
        bug_category="optionals",
        difficulty="beginner",
        hints=("as! is a force cast",),
        keywords=("force cast", "as!", "crash", "json"),
    ),
    "col-empty-avg": MockSnippet(
        code="""\
func max(of values: [Int]) -> Int {
    return values.max()!
}
""",
        bug_summary="Force unwrap of max() on an empty array",
        bug_category="collections",
        difficulty="beginner",
        hints=("max() returns optional",),
        keywords=("force unwrap", "empty", "max", "nil"),
    ),
    "ref-class-copy": MockSnippet(
        code="""\
final class Bag {
    var items: [String] = []
}
func clear(_ bag: Bag) {
    var local = bag
    local = Bag()
}
""",
        bug_summary="Rebinding a local reference does not replace the caller's class instance",
        bug_category="value vs reference",
        difficulty="intermediate",
        hints=("local = Bag() only changes the local name",),
        keywords=("class", "reference", "rebind", "caller"),
    ),
    "flow-switch-int": MockSnippet(
        code="""\
func mood(code: Int) -> String {
    switch code {
    case 1: return "happy"
    case 2: return "sad"
    }
}
""",
        bug_summary="Non-exhaustive switch over Int without default",
        bug_category="control flow",
        difficulty="beginner",
        hints=("Need default",),
        keywords=("exhaustive", "switch", "default"),
    ),
    "err-async-try": MockSnippet(
        code="""\
func bytes(from url: URL) async -> Data {
    try await URLSession.shared.data(from: url).0
}
""",
        bug_summary="Uses try in a non-throwing async function",
        bug_category="errors",
        difficulty="intermediate",
        hints=("Function signature needs throws",),
        keywords=("throws", "try", "async", "error"),
    ),
    "col-off-by-one": MockSnippet(
        code="""\
let letters = ["x", "y", "z"]
print(letters[letters.endIndex])
""",
        bug_summary="Using endIndex as a subscript is out of bounds",
        bug_category="collections",
        difficulty="beginner",
        hints=("endIndex is past the last element",),
        keywords=("endIndex", "bounds", "index", "out of range"),
    ),
    "opt-greet-print": MockSnippet(
        code="""\
func show(_ value: Int?) {
    print(value! + 1)
}
""",
        bug_summary="Force unwrap of optional Int before arithmetic",
        bug_category="optionals",
        difficulty="beginner",
        hints=("value can be nil",),
        keywords=("force unwrap", "optional", "nil"),
    ),
    "err-try-optional": MockSnippet(
        code="""\
func readText(url: URL) -> String {
    return (try? String(contentsOf: url))!
}
""",
        bug_summary="Force unwrap of try? result ignores read failures then crashes",
        bug_category="errors",
        difficulty="intermediate",
        hints=("try? yields nil on failure",),
        keywords=("try?", "force unwrap", "nil", "error"),
    ),
    "conc-actor-mut": MockSnippet(
        code="""\
actor Counter {
    var n = 0
}
func inc(_ c: Counter) {
    Task { c.n += 1 }
}
""",
        bug_summary="Actor state mutated from a Task without await on the actor",
        bug_category="concurrency",
        difficulty="advanced",
        hints=("Need await c isolation",),
        keywords=("actor", "await", "isolation", "task"),
    ),
    "val-let-struct": MockSnippet(
        code="""\
struct Size { var w: Int; var h: Int }
let box = Size(w: 1, h: 2)
box.w += 1
""",
        bug_summary="Mutating a property of a let struct value is illegal",
        bug_category="value vs reference",
        difficulty="beginner",
        hints=("box is let",),
        keywords=("let", "mutate", "struct", "var"),
    ),
    "opt-array-first": MockSnippet(
        code="""\
func head(_ items: [String]) -> String {
    return items.first!
}
""",
        bug_summary="Force unwrap of first on a possibly empty array",
        bug_category="optionals",
        difficulty="beginner",
        hints=("first is optional",),
        keywords=("force unwrap", "first", "empty", "nil"),
    ),
    "conc-await-miss": MockSnippet(
        code="""\
func main() async {
    let value = load()
    print(value)
}
func load() async -> Int { 1 }
""",
        bug_summary="Async call used without await",
        bug_category="concurrency",
        difficulty="intermediate",
        hints=("load is async",),
        keywords=("await", "async", "missing"),
    ),
}

_DEFAULT_FALLBACK = MockSnippet(
    code="""\
func head(_ items: [String]) -> String {
    return items.first!
}
""",
    bug_summary="Force unwrap of first on a possibly empty array",
    bug_category="optionals",
    difficulty="beginner",
    hints=("first is optional",),
    keywords=("force unwrap", "first", "empty", "nil"),
)


def fallback_for_seed(seed: ScenarioSeed) -> GeneratedSnippet:
    snip = _FALLBACK_BANK.get(seed.seed_id)
    if snip is None:
        for candidate in _FALLBACK_BANK.values():
            if candidate.bug_category == seed.category:
                snip = candidate
                break
    if snip is None:
        snip = _DEFAULT_FALLBACK
    return GeneratedSnippet(
        code=snip.code,
        bug_summary=snip.bug_summary,
        bug_category=snip.bug_category,
        difficulty=snip.difficulty,
        hints=snip.hints,
        keywords=snip.keywords,
        seed=seed,
    )
