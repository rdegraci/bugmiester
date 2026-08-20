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
    "opt-iflet-outer": MockSnippet(
        code="""\
func display(_ name: String?) -> String {
    if let name {
        print("bound")
    }
    return name
}
""",
        bug_summary="if let binds name only inside the block; the return still uses the outer String?",
        bug_category="optionals",
        difficulty="beginner",
        hints=("The unwrap does not last past the if",),
        keywords=("if let", "optional", "outer", "unwrap"),
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
    "conc-nontask-async": MockSnippet(
        code="""\
import UIKit
final class Screen: UIViewController {
    override func viewDidLoad() {
        super.viewDidLoad()
        title = await load()
    }
    func load() async -> String { "ok" }
}
""",
        bug_summary="viewDidLoad is not async, so it cannot await load(); wrap the call in Task",
        bug_category="concurrency",
        difficulty="intermediate",
        hints=("Start a Task in viewDidLoad",),
        keywords=("viewDidLoad", "Task", "async", "await"),
    ),
    "conc-task-orphan": MockSnippet(
        code="""\
import UIKit
final class Screen: UIViewController {
    override func viewDidLoad() {
        super.viewDidLoad()
        Task {
            while true {
                try? await Task.sleep(nanoseconds: 1_000_000_000)
                self.title = "tick"
            }
        }
    }
}
""",
        bug_summary="Unstructured Task is never stored or cancelled, so it keeps running and retains Screen after pop",
        bug_category="concurrency",
        difficulty="intermediate",
        hints=("Hold the Task and cancel in deinit",),
        keywords=("Task", "cancel", "orphan", "viewDidLoad"),
    ),
    "conc-continuation-stuck": MockSnippet(
        code="""\
func wait() async {
    await withCheckedContinuation { (_: CheckedContinuation<Void, Never>) in
    }
}
""",
        bug_summary="withCheckedContinuation never calls resume, so the task hangs and the continuation leaks",
        bug_category="concurrency",
        difficulty="advanced",
        hints=("Resume the continuation on every path",),
        keywords=("continuation", "resume", "hang", "leak"),
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
    "ui-stateobject-passed": MockSnippet(
        code="""\
import SwiftUI
final class Model: ObservableObject { @Published var n = 0 }
struct Pane: View {
    @StateObject var model: Model
    var body: some View { Text("\\(model.n)") }
}
struct Root: View {
    @StateObject var model = Model()
    var body: some View { Pane(model: model) }
}
""",
        bug_summary="@StateObject on Pane takes a Model the parent already owns; Pane should use @ObservedObject",
        bug_category="SwiftUI state",
        difficulty="intermediate",
        hints=("@ObservedObject for a passed-in object",),
        keywords=("@StateObject", "@ObservedObject", "passed", "owned"),
    ),
    "ui-foreach-index": MockSnippet(
        code="""\
import SwiftUI
struct Roster: View {
    var names: [String]
    var body: some View {
        ForEach(0..<names.count) { i in
            Text(names[i])
        }
    }
}
""",
        bug_summary="ForEach(0..<count) identifies rows by index, so inserts and deletes reuse the wrong views",
        bug_category="SwiftUI state",
        difficulty="intermediate",
        hints=("Identify rows by a stable id",),
        keywords=("ForEach", "index", "identity", "count"),
    ),
    "ui-onappear-task": MockSnippet(
        code="""\
import SwiftUI
struct Ticker: View {
    @State private var n = 0
    var body: some View {
        Text("\\(n)")
            .onAppear {
                Task {
                    while true {
                        try? await Task.sleep(nanoseconds: 1_000_000_000)
                        n += 1
                    }
                }
            }
    }
}
""",
        bug_summary="onAppear starts a Task that is not cancelled when the view disappears; use .task instead",
        bug_category="SwiftUI state",
        difficulty="intermediate",
        hints=(".task cancels on disappear",),
        keywords=("onAppear", "Task", "cancel", ".task"),
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
    "cap-session-vc": MockSnippet(
        code="""\
import UIKit
final class Screen: UIViewController {
    var task: URLSessionDataTask?
    var payload: Data?
    func load(_ url: URL) {
        task = URLSession.shared.dataTask(with: url) { data, _, _ in
            self.payload = data
        }
        task?.resume()
    }
}
""",
        bug_summary="Stored URLSession task retains a completion that strongly captures self",
        bug_category="captures",
        difficulty="intermediate",
        hints=("[weak self] in the completion",),
        keywords=("URLSession", "retain cycle", "self", "completion"),
    ),
    "cap-notify-observer": MockSnippet(
        code="""\
import UIKit
final class Screen: UIViewController {
    override func viewDidLoad() {
        super.viewDidLoad()
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(ping),
            name: UIApplication.didBecomeActiveNotification,
            object: nil
        )
    }
    @objc func ping() {}
}
""",
        bug_summary="NotificationCenter keeps a strong observer on Screen because the observer is never removed",
        bug_category="captures",
        difficulty="intermediate",
        hints=("removeObserver in deinit",),
        keywords=("NotificationCenter", "observer", "remove", "leak"),
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
    "send-task-mutate": MockSnippet(
        code="""\
class Counter {
    var n = 0
}
func bump(_ counter: Counter) {
    Task { counter.n += 1 }
}
""",
        bug_summary="Non-Sendable class is mutated from a concurrent Task",
        bug_category="sendable",
        difficulty="intermediate",
        hints=("Counter is not Sendable",),
        keywords=("Sendable", "Task", "isolation", "class"),
    ),
    "send-actor-escape": MockSnippet(
        code="""\
class Bag {
    var items: [String] = []
}
actor Shelf {
    func store(_ bag: Bag) {}
}
func park(_ shelf: Shelf, _ bag: Bag) async {
    await shelf.store(bag)
}
""",
        bug_summary="Non-Sendable class is passed into an actor method",
        bug_category="sendable",
        difficulty="intermediate",
        hints=("Bag crosses isolation",),
        keywords=("Sendable", "actor", "isolation", "class"),
    ),
    "cod-key-mismatch": MockSnippet(
        code="""\
struct User: Codable {
    var fullName: String
}
func load(_ data: Data) throws -> User {
    try JSONDecoder().decode(User.self, from: data)
}
""",
        bug_summary="fullName expects a JSON key fullName; snake_case full_name will not decode",
        bug_category="codable",
        difficulty="beginner",
        hints=("CodingKeys or convertFromSnakeCase",),
        keywords=("Codable", "CodingKeys", "JSON", "key"),
    ),
    "cod-date-strategy": MockSnippet(
        code="""\
struct Event: Codable {
    var when: Date
}
func read(_ data: Data) throws -> Event {
    try JSONDecoder().decode(Event.self, from: data)
}
""",
        bug_summary="JSONDecoder default Date strategy will not decode an ISO-8601 string",
        bug_category="codable",
        difficulty="intermediate",
        hints=("dateDecodingStrategy",),
        keywords=("Date", "JSONDecoder", "ISO-8601", "Codable"),
    ),
    "str-int-subscript": MockSnippet(
        code="""\
func firstChar(_ text: String) -> Character {
    return text[0]
}
""",
        bug_summary="String cannot be subscripted with Int; it needs a String.Index",
        bug_category="string indexes",
        difficulty="beginner",
        hints=("String.Index not Int",),
        keywords=("String", "Index", "subscript", "Int"),
    ),
    "str-offset-end": MockSnippet(
        code="""\
func third(_ text: String) -> Character {
    let i = text.index(text.startIndex, offsetBy: 2)
    return text[i]
}
""",
        bug_summary="index(_:offsetBy: 2) traps when the string is shorter than 3 characters",
        bug_category="string indexes",
        difficulty="beginner",
        hints=("Use limitedBy",),
        keywords=("offsetBy", "endIndex", "String", "Index"),
    ),
    "lazy-let-struct": MockSnippet(
        code="""\
struct Loader {
    lazy var data = expensive()
}
func read(_ loader: Loader) -> Int {
    return loader.data
}
func expensive() -> Int { 1 }
""",
        bug_summary="Accessing lazy var mutates the struct, but loader is a let parameter",
        bug_category="lazy",
        difficulty="intermediate",
        hints=("lazy var needs var",),
        keywords=("lazy", "let", "struct", "mutate"),
    ),
    "lazy-stale-total": MockSnippet(
        code="""\
struct Stats {
    var items: [Int]
    lazy var total = items.reduce(0, +)
}
func bump(_ stats: inout Stats) -> Int {
    _ = stats.total
    stats.items = [9]
    return stats.total
}
""",
        bug_summary="lazy total is computed once and stays stale after items changes",
        bug_category="lazy",
        difficulty="intermediate",
        hints=("lazy does not recompute",),
        keywords=("lazy", "stale", "recompute", "total"),
    ),
    "proto-wrong-name": MockSnippet(
        code="""\
protocol Drawable {
    func draw()
}
struct Dot: Drawable {
    func render() {}
}
""",
        bug_summary="Dot claims Drawable but implements render instead of draw",
        bug_category="protocol witnesses",
        difficulty="beginner",
        hints=("Witness name must match",),
        keywords=("protocol", "witness", "draw", "conform"),
    ),
    "proto-mutating-req": MockSnippet(
        code="""\
protocol Resettable {
    mutating func reset()
}
struct Knob: Resettable {
    var n = 1
    func reset() { n = 0 }
}
""",
        bug_summary="Non-mutating reset cannot witness a mutating protocol requirement",
        bug_category="protocol witnesses",
        difficulty="intermediate",
        hints=("Need mutating func reset",),
        keywords=("mutating", "protocol", "witness", "struct"),
    ),
    "proto-static-dispatch": MockSnippet(
        code="""\
protocol Worker {}
extension Worker {
    func start() { print("default") }
}
struct Job: Worker {
    func start() { print("job") }
}
func run(_ worker: Worker) {
    worker.start()
}
""",
        bug_summary="start() is not a protocol requirement, so run calls the extension and never Job.start",
        bug_category="protocol witnesses",
        difficulty="advanced",
        hints=("Declare start() on Worker",),
        keywords=("extension", "existential", "static", "requirement"),
    ),
    "res-optional-result": MockSnippet(
        code="""\
func label(_ result: Result<String, Error>) -> String {
    if let text = result {
        return text
    }
    return ""
}
""",
        bug_summary="Result is not Optional; if-let will not unwrap success",
        bug_category="result",
        difficulty="beginner",
        hints=("Switch on Result",),
        keywords=("Result", "Optional", "if let", "success"),
    ),
    "res-try-get": MockSnippet(
        code="""\
func name(from result: Result<String, Error>) -> String {
    try result.get()
}
""",
        bug_summary="Result.get() throws but name(from:) is not marked throws",
        bug_category="result",
        difficulty="beginner",
        hints=("Add throws or handle the error",),
        keywords=("Result", "get", "throws", "try"),
    ),
    "cast-any-force": MockSnippet(
        code="""\
func asInt(_ value: Any) -> Int {
    return value as! Int
}
""",
        bug_summary="as! traps if value is not actually an Int",
        bug_category="type casting",
        difficulty="beginner",
        hints=("Use as?",),
        keywords=("as!", "Any", "cast", "Int"),
    ),
    "cast-array-wrong": MockSnippet(
        code="""\
func labels(_ values: [Any]) -> [String] {
    return values as! [String]
}
""",
        bug_summary="as! [String] traps when the array holds mixed Any values",
        bug_category="type casting",
        difficulty="beginner",
        hints=("compactMap as? String",),
        keywords=("as!", "array", "String", "cast"),
    ),
    "init-url-force": MockSnippet(
        code="""\
func page(_ raw: String) -> URL {
    return URL(string: raw)!
}
""",
        bug_summary="URL(string:) is failable; force unwrap crashes on a bad string",
        bug_category="failable init",
        difficulty="beginner",
        hints=("URL(string:) returns URL?",),
        keywords=("URL", "init?", "failable", "force unwrap"),
    ),
    "init-int-force": MockSnippet(
        code="""\
func count(from text: String) -> Int {
    return Int(text)!
}
""",
        bug_summary="Int(String) is failable; force unwrap crashes on non-digits",
        bug_category="failable init",
        difficulty="beginner",
        hints=("Int(text) is Int?",),
        keywords=("Int", "String", "failable", "init?"),
    ),
    "inout-local-copy": MockSnippet(
        code="""\
func bump(_ n: Int) {
    var local = n
    local += 1
}
""",
        bug_summary="Mutates a local copy; the caller's Int is unchanged because there is no inout",
        bug_category="inout / COW",
        difficulty="beginner",
        hints=("Need inout",),
        keywords=("inout", "copy", "mutate", "local"),
    ),
    "cow-iterate-mutate": MockSnippet(
        code="""\
func grow(_ items: inout [Int]) {
    for x in items {
        items.append(x)
    }
}
""",
        bug_summary="Appending to items while iterating it is undefined / traps",
        bug_category="inout / COW",
        difficulty="intermediate",
        hints=("Don't mutate during for-in",),
        keywords=("iterate", "append", "mutate", "array"),
    ),
    "enum-if-case-wrong": MockSnippet(
        code="""\
enum Box { case full(String), empty }
func text(_ box: Box) -> String {
    if case .full = box {
        return "n/a"
    }
    return ""
}
""",
        bug_summary="if case .full does not bind the associated String, so the payload is discarded",
        bug_category="enums",
        difficulty="beginner",
        hints=("if case .full(let s)",),
        keywords=("enum", "if case", "associated", "payload"),
    ),
    "enum-switch-assoc": MockSnippet(
        code="""\
enum Status { case ok(Int), fail }
func code(_ status: Status) -> Int {
    switch status {
    case .ok:
        return 0
    case .fail:
        return -1
    }
}
""",
        bug_summary="switch on .ok ignores the associated Int and always returns 0",
        bug_category="enums",
        difficulty="beginner",
        hints=("case .ok(let n)",),
        keywords=("enum", "switch", "associated", "Int"),
    ),
    "defer-after-return": MockSnippet(
        code="""\
func read(_ n: Int) -> Int {
    return n
    defer { print("done") }
}
""",
        bug_summary="defer after return is unreachable so the cleanup never runs",
        bug_category="defer",
        difficulty="beginner",
        hints=("defer before return",),
        keywords=("defer", "return", "unreachable", "cleanup"),
    ),
    "defer-stale-copy": MockSnippet(
        code="""\
func bump(_ n: Int) -> Int {
    var n = n
    defer { n += 1 }
    return n
}
""",
        bug_summary="defer runs after the return value is copied, so n += 1 never affects the caller",
        bug_category="defer",
        difficulty="intermediate",
        hints=("Mutate before return",),
        keywords=("defer", "return", "copied", "mutate"),
    ),
    "defer-file-handle": MockSnippet(
        code="""\
import Foundation
func slurp(_ url: URL) throws -> Data {
    let handle = try FileHandle(forReadingFrom: url)
    return handle.readDataToEndOfFile()
}
""",
        bug_summary="FileHandle is never closed after the read, so the descriptor leaks",
        bug_category="defer",
        difficulty="beginner",
        hints=("defer { try? handle.close() }",),
        keywords=("FileHandle", "close", "defer", "leak"),
    ),
    "unowned-self-gone": MockSnippet(
        code="""\
class Loader {
    var done: (() -> Void)?
    func start() {
        done = { [unowned self] in self.finish() }
    }
    func finish() {}
}
""",
        bug_summary="unowned self crashes if done runs after Loader is released",
        bug_category="unowned",
        difficulty="intermediate",
        hints=("Use weak self",),
        keywords=("unowned", "self", "crash", "released"),
    ),
    "unowned-not-weak": MockSnippet(
        code="""\
class Node {
    unowned var parent: Node
    init(parent: Node) { self.parent = parent }
}
""",
        bug_summary="unowned parent crashes if the parent can be nil; a root has no parent",
        bug_category="unowned",
        difficulty="intermediate",
        hints=("weak var parent: Node?",),
        keywords=("unowned", "parent", "nil", "weak"),
    ),
    "some-any-assoc": MockSnippet(
        code="""\
protocol Item { associatedtype ID }
func first(_ items: [Item]) -> Item {
    return items[0]
}
""",
        bug_summary="Item has an associated type so it cannot be used as [Item] or a return type",
        bug_category="some vs any",
        difficulty="intermediate",
        hints=("any Item or a generic",),
        keywords=("associatedtype", "any", "protocol", "Item"),
    ),
    "some-return-mismatch": MockSnippet(
        code="""\
protocol Shape {}
struct Dot: Shape {}
struct Box: Shape {}
func make(flag: Bool) -> some Shape {
    if flag { return Dot() }
    return Box()
}
""",
        bug_summary="some Shape must be one concrete type; Dot and Box cannot both be returned",
        bug_category="some vs any",
        difficulty="intermediate",
        hints=("any Shape",),
        keywords=("some", "opaque", "return", "Shape"),
    ),
    "auto-store-nonescaping": MockSnippet(
        code="""\
var later: (() -> Int)?
func once(_ work: @autoclosure () -> Int) {
    later = work
}
""",
        bug_summary="Non-escaping autoclosure cannot be stored in later for later execution",
        bug_category="autoclosure",
        difficulty="intermediate",
        hints=("@autoclosure @escaping",),
        keywords=("autoclosure", "escaping", "stored", "closure"),
    ),
    "auto-eval-twice": MockSnippet(
        code="""\
func both(_ work: @autoclosure () -> Int) -> Int {
    return work() + work()
}
""",
        bug_summary="Autoclosure work() is evaluated twice so side effects run twice",
        bug_category="autoclosure",
        difficulty="beginner",
        hints=("Call work once",),
        keywords=("autoclosure", "twice", "side effect", "evaluate"),
    ),
    "default-instance-member": MockSnippet(
        code="""\
struct Tag {
    var prefix = "id-"
    func make(id: String = prefix) -> String {
        return prefix + id
    }
}
""",
        bug_summary="Default arguments cannot use instance members like prefix",
        bug_category="default arguments",
        difficulty="intermediate",
        hints=("Pass prefix at the call or compute inside",),
        keywords=("default", "instance", "prefix", "argument"),
    ),
    "default-proto-extension": MockSnippet(
        code="""\
protocol Named {
    func label(suffix: String)
}
extension Named {
    func label(suffix: String = "") {}
}
struct User: Named {
    func label(suffix: String) {}
}
func run(_ user: User) {
    user.label()
}
""",
        bug_summary="The extension default does not add a default to Named.label; User.label() still needs suffix",
        bug_category="default arguments",
        difficulty="advanced",
        hints=("Default on the requirement, not only the extension",),
        keywords=("default", "protocol", "extension", "requirement"),
    ),
    "main-task-ui": MockSnippet(
        code="""\
import UIKit
func load(_ label: UILabel) {
    Task {
        let text = "ok"
        label.text = text
    }
}
""",
        bug_summary="UILabel is updated from an unstructured Task off the main actor",
        bug_category="MainActor",
        difficulty="intermediate",
        hints=("@MainActor or MainActor.run",),
        keywords=("MainActor", "UILabel", "Task", "UI"),
    ),
    "main-callback-label": MockSnippet(
        code="""\
import UIKit
func fetch(_ label: UILabel, url: URL) {
    URLSession.shared.dataTask(with: url) { _, _, _ in
        label.text = "done"
    }.resume()
}
""",
        bug_summary="URLSession callback is not on the main actor but writes UILabel.text",
        bug_category="MainActor",
        difficulty="intermediate",
        hints=("Dispatch to main",),
        keywords=("MainActor", "URLSession", "UILabel", "callback"),
    ),
    "main-task-published": MockSnippet(
        code="""\
import Combine
final class Board: ObservableObject {
    @Published var heading = ""
    func refresh() {
        Task {
            heading = "ok"
        }
    }
}
""",
        bug_summary="@Published heading is written from an unstructured Task that is not on the main actor",
        bug_category="MainActor",
        difficulty="intermediate",
        hints=("Hop to the main actor before publishing",),
        keywords=("MainActor", "@Published", "Task", "ObservableObject"),
    ),
    "cancel-ignore-flag": MockSnippet(
        code="""\
func chew(_ n: Int) async {
    for i in 0..<n {
        await Task.yield()
        print(i)
    }
}
""",
        bug_summary="Loop never checks Task.isCancelled so cancellation is ignored",
        bug_category="Task cancellation",
        difficulty="intermediate",
        hints=("Task.isCancelled",),
        keywords=("cancellation", "isCancelled", "Task", "loop"),
    ),
    "cancel-no-check": MockSnippet(
        code="""\
func chew(_ n: Int) async throws {
    for _ in 0..<n {
        try await Task.sleep(nanoseconds: 1)
    }
}
""",
        bug_summary="Throwing loop never calls Task.checkCancellation()",
        bug_category="Task cancellation",
        difficulty="intermediate",
        hints=("try Task.checkCancellation()",),
        keywords=("checkCancellation", "Task", "throws", "loop"),
    ),
    "actor-await-stale": MockSnippet(
        code="""\
actor Counter {
    var n = 0
    func bump() async {
        let start = n
        await Task.yield()
        n = start + 1
    }
}
""",
        bug_summary="After await, n may have changed; writing start + 1 loses concurrent bumps",
        bug_category="actor reentrancy",
        difficulty="advanced",
        hints=("Re-read n after await",),
        keywords=("actor", "reentrancy", "await", "stale"),
    ),
    "actor-await-balance": MockSnippet(
        code="""\
actor Wallet {
    var cash = 10
    func spend(_ k: Int) async -> Bool {
        if cash < k { return false }
        await Task.yield()
        cash -= k
        return true
    }
}
""",
        bug_summary="Balance is checked, then await lets another spend run; cash -= k can go negative",
        bug_category="actor reentrancy",
        difficulty="advanced",
        hints=("Check cash again after await",),
        keywords=("actor", "reentrancy", "balance", "await"),
    ),
    "ui-env-missing": MockSnippet(
        code="""\
import SwiftUI
class Store: ObservableObject {}
struct Screen: View {
    @EnvironmentObject var store: Store
    var body: some View { Text("hi") }
}
struct Root: View {
    var body: some View { Screen() }
}
""",
        bug_summary="Screen needs an EnvironmentObject but Root never calls environmentObject(Store())",
        bug_category="SwiftUI environment",
        difficulty="intermediate",
        hints=(".environmentObject",),
        keywords=("EnvironmentObject", "injection", "SwiftUI", "Store"),
    ),
    "ui-observable-state": MockSnippet(
        code="""\
import SwiftUI
@Observable
final class Store { var n = 0 }
struct Root: View {
    @State var store = Store()
    var body: some View { Child(store: store) }
}
struct Child: View {
    var store: Store
    var body: some View { Text("\\(store.n)") }
}
""",
        bug_summary="@State owns a new Store per Root identity; Child should get a shared environment model",
        bug_category="SwiftUI environment",
        difficulty="intermediate",
        hints=("@Environment or @Bindable",),
        keywords=("@Observable", "@State", "environment", "Store"),
    ),
    "ui-env-wrong-sibling": MockSnippet(
        code="""\
import SwiftUI
final class Store: ObservableObject { @Published var title = "Hi" }
struct Root: View {
    @StateObject var store = Store()
    var body: some View {
        HStack {
            Sidebar().environmentObject(store)
            Detail()
        }
    }
}
struct Sidebar: View { var body: some View { Text("nav") } }
struct Detail: View {
    @EnvironmentObject var store: Store
    var body: some View { Text(store.title) }
}
""",
        bug_summary="environmentObject is attached to Sidebar, so sibling Detail never receives Store",
        bug_category="SwiftUI environment",
        difficulty="intermediate",
        hints=("Inject on the common ancestor",),
        keywords=("environmentObject", "sibling", "HStack", "EnvironmentObject"),
    ),
    "slice-index-zero": MockSnippet(
        code="""\
func first(_ items: ArraySlice<Int>) -> Int {
    return items[0]
}
""",
        bug_summary="ArraySlice indices are not zero-based; items[0] traps if startIndex is not 0",
        bug_category="Sequence slices",
        difficulty="beginner",
        hints=("items[items.startIndex]",),
        keywords=("ArraySlice", "indices", "startIndex", "0"),
    ),
    "slice-drop-first": MockSnippet(
        code="""\
func second(_ items: [Int]) -> Int {
    let rest = items.dropFirst()
    return rest[0]
}
""",
        bug_summary="dropFirst() yields a slice whose startIndex is 1, so rest[0] traps",
        bug_category="Sequence slices",
        difficulty="beginner",
        hints=("rest.first or startIndex",),
        keywords=("dropFirst", "slice", "startIndex", "0"),
    ),
    "comb-sink-dropped": MockSnippet(
        code="""\
import Combine

final class Pulse {
    let ticks = PassthroughSubject<Int, Never>()

    func listen() {
        ticks.sink { value in
            print(value)
        }
    }
}
""",
        bug_summary="sink returns AnyCancellable that is discarded, so the subscription cancels immediately",
        bug_category="Combine",
        difficulty="intermediate",
        hints=("Store the AnyCancellable",),
        keywords=("AnyCancellable", "sink", "discarded", "subscription"),
    ),
    "comb-receive-main": MockSnippet(
        code="""\
import Combine
import UIKit

final class Caption {
    var bag = Set<AnyCancellable>()

    func fill(_ label: UILabel, url: URL) {
        URLSession.shared.dataTaskPublisher(for: url)
            .map { String(data: $0.data, encoding: .utf8) ?? "" }
            .replaceError(with: "")
            .sink { text in
                label.text = text
            }
            .store(in: &bag)
    }
}
""",
        bug_summary="dataTaskPublisher delivers on a background queue; UILabel.text is set without receive(on: main)",
        bug_category="Combine",
        difficulty="intermediate",
        hints=("receive(on: DispatchQueue.main)",),
        keywords=("receive(on:)", "main", "dataTaskPublisher", "UILabel"),
    ),
    "comb-bag-local": MockSnippet(
        code="""\
import Combine

final class Board: ObservableObject {
    @Published var label = ""
    func bind() {
        var bag = Set<AnyCancellable>()
        Just("ok")
            .sink { [weak self] text in
                self?.label = text
            }
            .store(in: &bag)
    }
}
""",
        bug_summary="bag is local to bind(), so the Set dies when the function returns and the subscription cancels",
        bug_category="Combine",
        difficulty="intermediate",
        hints=("Store the Set on Board",),
        keywords=("AnyCancellable", "local", "Set", "store"),
    ),
    "comb-never-cancel": MockSnippet(
        code="""\
import Combine
import UIKit

enum Hub {
    static var bag = Set<AnyCancellable>()
}

final class Screen: UIViewController {
    func listen() {
        Timer.publish(every: 1, on: .main, in: .common)
            .autoconnect()
            .sink { _ in print("tick") }
            .store(in: &Hub.bag)
    }
}
""",
        bug_summary="The timer subscription is stored on a static bag, so it keeps firing after Screen is gone",
        bug_category="Combine",
        difficulty="intermediate",
        hints=("Store cancellables on Screen and cancel on deinit",),
        keywords=("AnyCancellable", "static", "Timer", "cancel"),
    ),
    "excl-inout-same": MockSnippet(
        code="""\
func add(_ a: inout Int, _ b: inout Int) {
    a += b
}
func bump(_ n: inout Int) {
    add(&n, &n)
}
""",
        bug_summary="add is called with &n twice, so the two inout parameters overlap",
        bug_category="exclusivity",
        difficulty="intermediate",
        hints=("Use a copy for the second argument",),
        keywords=("inout", "overlap", "exclusivity", "alias"),
    ),
    "excl-self-inout": MockSnippet(
        code="""\
struct Player {
    var score = 0
    mutating func absorb(_ other: inout Player) {
        score += other.score
    }
}
func clash() {
    var p = Player()
    p.absorb(&p)
}
""",
        bug_summary="absorb mutates p while also taking &p, which is overlapping access to self",
        bug_category="exclusivity",
        difficulty="intermediate",
        hints=("Pass a different Player, not &p",),
        keywords=("inout", "self", "exclusivity", "mutating"),
    ),
    "excl-prop-inout": MockSnippet(
        code="""\
struct Pair {
    var first = 0
    var second = 0
    mutating func reset(_ value: inout Int) {
        value = first
        first = second
    }
}
func clash() {
    var p = Pair()
    p.reset(&p.first)
}
""",
        bug_summary="reset takes &p.first while the method also reads and writes first",
        bug_category="exclusivity",
        difficulty="intermediate",
        hints=("Do not pass a stored property the method also uses",),
        keywords=("inout", "property", "exclusivity", "first"),
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
                feedback="Yes.",
                confidence=0.95,
            )
        if tier == "weak":
            return JudgeResult(
                correct=False,
                partial=True,
                feedback="Partially correct.",
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
            feedback="Not quite.",
            confidence=0.9,
        )

    def recovery_raw(self, prompt: str, settings: Settings | None = None) -> str:
        """Near-miss wrong answers; prefers the player's partial, then other snippets."""
        del settings
        from bugmiester.recovery import too_close_to_expected

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
        player = ""
        player_match = re.search(
            r"Player partial answer[^\n]*:\n([\s\S]*?)\n\nReturn ONLY",
            prompt,
        )
        if player_match:
            player = player_match.group(1).strip()
        distractors: list[str] = []
        seen = {expected.strip().lower()}
        if player and not too_close_to_expected(player, expected):
            distractors.append(player)
            seen.add(player.strip().lower())
        expected_category = ""
        for snip in self._seed_map.values():
            if snip.bug_summary.strip() == expected:
                expected_category = snip.bug_category
                break
        bank = list(self._snippets) + list(self._seed_map.values())
        if expected_category:
            bank = sorted(
                bank,
                key=lambda snip: 0 if snip.bug_category == expected_category else 1,
            )
        for snip in bank:
            summary = snip.bug_summary.strip()
            key = summary.lower()
            if key in seen or too_close_to_expected(summary, expected):
                continue
            seen.add(key)
            distractors.append(summary)
            if len(distractors) >= needed:
                break
        return json.dumps({"distractors": distractors})


