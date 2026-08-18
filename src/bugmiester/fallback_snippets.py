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
    "acc-mutating-let": MockSnippet(
        code="""\
extension Int {
    mutating func bump() { self += 1 }
}
let n = 3
n.bump()
""",
        bug_summary="mutating bump() is called on a let Int",
        bug_category="access control",
        difficulty="beginner",
        hints=("n is let",),
        keywords=("mutating", "let", "Int", "method"),
    ),
    "acc-private-field": MockSnippet(
        code="""\
enum Keys {
    private static let secret = "x"
}
print(Keys.secret)
""",
        bug_summary="private static member is read from outside the enum",
        bug_category="access control",
        difficulty="beginner",
        hints=("private on Keys",),
        keywords=("private", "static", "enum", "access"),
    ),
    "ui-state-let": MockSnippet(
        code="""\
import SwiftUI
struct TapView: View {
    var taps = 0
    var body: some View {
        Button("Tap") { taps += 1 }
    }
}
""",
        bug_summary="View body mutates stored taps; it needs @State, not a plain var",
        bug_category="SwiftUI state",
        difficulty="beginner",
        hints=("Views are structs",),
        keywords=("@State", "var", "View", "mutate"),
    ),
    "ui-binding-dollar": MockSnippet(
        code="""\
import SwiftUI
struct SwitchRow: View {
    @State private var enabled = false
    var body: some View {
        Toggle("On", isOn: enabled)
    }
}
""",
        bug_summary="Toggle needs a Binding; missing $ on enabled",
        bug_category="SwiftUI state",
        difficulty="beginner",
        hints=("Use $enabled",),
        keywords=("Binding", "$", "Toggle", "@State"),
    ),
    "cap-stored-self": MockSnippet(
        code="""\
final class Hook {
    var handler: (() -> Void)?
    func attach() {
        handler = { self.fire() }
    }
    func fire() {}
}
""",
        bug_summary="Stored handler closure captures self strongly",
        bug_category="captures",
        difficulty="intermediate",
        hints=("[weak self]",),
        keywords=("retain cycle", "self", "closure", "weak"),
    ),
    "cap-timer-cycle": MockSnippet(
        code="""\
final class Pump {
    var again: (() -> Void)?
    func arm() {
        again = { self.arm() }
    }
}
""",
        bug_summary="again stores a closure that calls arm() and captures self",
        bug_category="captures",
        difficulty="intermediate",
        hints=("self.arm inside again",),
        keywords=("retain cycle", "self", "closure", "stored"),
    ),
    "eq-identity-id": MockSnippet(
        code="""\
class Row: Equatable {
    let key: String
    init(_ key: String) { self.key = key }
    static func == (lhs: Row, rhs: Row) -> Bool { lhs.key == rhs.key }
}
func has(_ rows: [Row], _ row: Row) -> Bool {
    rows.contains { $0 === row }
}
""",
        bug_summary="contains uses === while Row equality is by key",
        bug_category="equality",
        difficulty="intermediate",
        hints=("=== vs ==",),
        keywords=("===", "==", "identity", "Equatable"),
    ),
    "eq-missing-protocol": MockSnippet(
        code="""\
class Item {
    var sku = ""
}
func unique(_ items: [Item]) -> Set<Item> {
    Set(items)
}
""",
        bug_summary="Set<Item> requires Hashable; Item does not conform",
        bug_category="equality",
        difficulty="beginner",
        hints=("Hashable",),
        keywords=("Hashable", "Set", "conform", "class"),
    ),
    "send-task-mutate": MockSnippet(
        code="""\
final class Flag {
    var on = false
}
func arm(_ flag: Flag) {
    Task.detached { flag.on = true }
}
""",
        bug_summary="Non-Sendable Flag is written from Task.detached",
        bug_category="sendable",
        difficulty="intermediate",
        hints=("Flag is not Sendable",),
        keywords=("Sendable", "Task", "detached", "class"),
    ),
    "send-actor-escape": MockSnippet(
        code="""\
class Token {
    var n = 0
}
actor Gate {
    func admit(_ token: Token) {}
}
func enter() async {
    await Gate().admit(Token())
}
""",
        bug_summary="Task-free async function still sends a non-Sendable Token into an actor",
        bug_category="sendable",
        difficulty="intermediate",
        hints=("Token is not Sendable",),
        keywords=("Sendable", "actor", "Token", "isolation"),
    ),
    "cod-key-mismatch": MockSnippet(
        code="""\
struct Team: Codable {
    var name: String
}
func loadTeams(_ data: Data) throws -> Team {
    try JSONDecoder().decode(Team.self, from: data)
}
""",
        bug_summary="Decodes a JSON array of teams as a single Team object",
        bug_category="codable",
        difficulty="beginner",
        hints=("decode [Team].self",),
        keywords=("Codable", "array", "JSON", "decode"),
    ),
    "cod-date-strategy": MockSnippet(
        code="""\
struct Visit: Codable {
    var arrived: Date
}
func visit(_ data: Data) throws -> Visit {
    let decoder = JSONDecoder()
    decoder.dateDecodingStrategy = .secondsSince1970
    return try decoder.decode(Visit.self, from: data)
}
""",
        bug_summary="Date strategy is seconds since 1970 but the JSON is milliseconds or ISO-8601",
        bug_category="codable",
        difficulty="intermediate",
        hints=("dateDecodingStrategy does not match payload",),
        keywords=("Date", "secondsSince1970", "JSONDecoder", "Codable"),
    ),
    "str-int-subscript": MockSnippet(
        code="""\
func second(_ text: String) -> Character {
    return text[text.startIndex + 1]
}
""",
        bug_summary="String.Index cannot be advanced with + 1; use index(_:offsetBy:)",
        bug_category="string indexes",
        difficulty="beginner",
        hints=("index(_:offsetBy:)",),
        keywords=("String", "Index", "offsetBy", "startIndex"),
    ),
    "str-offset-end": MockSnippet(
        code="""\
func afterEnd(_ text: String) -> String.Index {
    text.index(after: text.endIndex)
}
""",
        bug_summary="index(after:) on endIndex is past the string's valid range",
        bug_category="string indexes",
        difficulty="beginner",
        hints=("endIndex is already past the last character",),
        keywords=("endIndex", "index(after:)", "String", "bounds"),
    ),
    "lazy-let-struct": MockSnippet(
        code="""\
struct Cache {
    lazy var n = 0
}
func show() {
    let cache = Cache()
    print(cache.n)
}
""",
        bug_summary="lazy var n mutates Cache but cache is declared with let",
        bug_category="lazy",
        difficulty="intermediate",
        hints=("cache must be var",),
        keywords=("lazy", "let", "struct", "var"),
    ),
    "lazy-stale-total": MockSnippet(
        code="""\
struct Box {
    var label = "a"
    lazy var stamp = label.uppercased()
}
func retag(_ box: inout Box) -> String {
    _ = box.stamp
    box.label = "b"
    return box.stamp
}
""",
        bug_summary="lazy stamp keeps the first label and ignores later changes",
        bug_category="lazy",
        difficulty="intermediate",
        hints=("lazy is cached",),
        keywords=("lazy", "stale", "cached", "label"),
    ),
    "proto-wrong-name": MockSnippet(
        code="""\
protocol Named {
    var name: String { get }
}
struct Person: Named {
    var title: String
}
""",
        bug_summary="Person claims Named but provides title instead of name",
        bug_category="protocol witnesses",
        difficulty="beginner",
        hints=("Need var name",),
        keywords=("protocol", "witness", "name", "property"),
    ),
    "proto-mutating-req": MockSnippet(
        code="""\
protocol Tick {
    mutating func tick()
}
struct Clock: Tick {
    var n = 0
    func tick() { n += 1 }
}
""",
        bug_summary="Clock.tick is not mutating so it cannot satisfy Tick.tick",
        bug_category="protocol witnesses",
        difficulty="intermediate",
        hints=("mutating func tick",),
        keywords=("mutating", "protocol", "tick", "struct"),
    ),
    "res-optional-result": MockSnippet(
        code="""\
func value(_ result: Result<Int, Error>) -> Int {
    switch result {
    case .success(let n):
        return n
    }
}
""",
        bug_summary="Switch on Result is not exhaustive; failure is unhandled",
        bug_category="result",
        difficulty="beginner",
        hints=("Handle .failure",),
        keywords=("Result", "switch", "failure", "exhaustive"),
    ),
    "res-try-get": MockSnippet(
        code="""\
func value(_ result: Result<Int, Error>) -> Int {
    result.get()
}
""",
        bug_summary="Result.get() throws but the call site has no try",
        bug_category="result",
        difficulty="beginner",
        hints=("Need try",),
        keywords=("Result", "get", "try", "throws"),
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
