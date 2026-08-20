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
    "err-empty-catch": MockSnippet(
        code="""\
func load(_ url: URL) -> Data {
    do {
        return try Data(contentsOf: url)
    } catch {
    }
    return Data()
}
""",
        bug_summary="Empty catch hides the read failure and returns empty Data",
        bug_category="errors",
        difficulty="beginner",
        hints=("Log or throw from catch",),
        keywords=("catch", "empty", "swallow", "Data"),
    ),
    "err-try-bang": MockSnippet(
        code="""\
func decode(_ data: Data) -> Any {
    return try! JSONSerialization.jsonObject(with: data)
}
""",
        bug_summary="try! crashes if the JSON is invalid",
        bug_category="errors",
        difficulty="beginner",
        hints=("Use try without the bang",),
        keywords=("try!", "JSON", "crash", "force"),
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
    "opt-iflet-outer": MockSnippet(
        code="""\
func join(_ a: String?, _ b: String) -> String {
    if let a {
        return a + b
    }
    return a + b
}
""",
        bug_summary="The else branch uses a as String? after if let already ended",
        bug_category="optionals",
        difficulty="beginner",
        hints=("Unwrap in both branches, or return a default",),
        keywords=("if let", "else", "optional", "String"),
    ),
    "opt-chain-skip": MockSnippet(
        code="""\
final class Session {
    func logout() { print("bye") }
}
func leave(_ session: Session?) {
    session?.logout()
    print("left")
}
""",
        bug_summary="session?.logout() is skipped when session is nil, but leave still prints left",
        bug_category="optionals",
        difficulty="beginner",
        hints=("Chaining does not mean the call ran",),
        keywords=("optional chaining", "?.", "logout", "nil"),
    ),
    "opt-iuo-outlet": MockSnippet(
        code="""\
import UIKit
final class Screen: UIViewController {
    var banner: UIImageView!
    func show() {
        banner.isHidden = false
    }
}
""",
        bug_summary="banner is an implicitly unwrapped UIImageView that is never assigned; show() crashes",
        bug_category="optionals",
        difficulty="beginner",
        hints=("IUO is still optional underneath",),
        keywords=("IUO", "UIImageView", "!", "crash"),
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
    "conc-nontask-async": MockSnippet(
        code="""\
import UIKit
final class Screen: UIViewController {
    func appear() {
        title = await fetch()
    }
    func fetch() async -> String { "ok" }
}
""",
        bug_summary="appear() is a sync method, so await fetch() is illegal; start a Task instead",
        bug_category="concurrency",
        difficulty="intermediate",
        hints=("Task { title = await fetch() }",),
        keywords=("Task", "async", "await", "sync"),
    ),
    "conc-task-orphan": MockSnippet(
        code="""\
import Foundation
final class Board {
    func start() {
        Task.detached {
            while true {
                try? await Task.sleep(nanoseconds: 500_000_000)
                print("still running")
            }
        }
    }
}
""",
        bug_summary="Task.detached is discarded, so the loop never cancels when Board is released",
        bug_category="concurrency",
        difficulty="intermediate",
        hints=("Store the Task and cancel it",),
        keywords=("Task.detached", "cancel", "orphan", "loop"),
    ),
    "conc-continuation-stuck": MockSnippet(
        code="""\
import Foundation
func fetch(_ url: URL) async -> Data {
    await withCheckedContinuation { cont in
        URLSession.shared.dataTask(with: url) { data, _, _ in
            if let data {
                cont.resume(returning: data)
            }
        }.resume()
    }
}
""",
        bug_summary="If data is nil the continuation never resumes, so the async caller hangs",
        bug_category="concurrency",
        difficulty="advanced",
        hints=("Resume on the failure path too",),
        keywords=("continuation", "resume", "nil", "hang"),
    ),
    "conc-continuation-double": MockSnippet(
        code="""\
func bridge(_ work: (@escaping (Result<Int, Error>) -> Void) -> Void) async throws -> Int {
    try await withCheckedThrowingContinuation { cont in
        work { result in
            switch result {
            case .success(let value):
                cont.resume(returning: value)
                cont.resume(returning: value)
            case .failure(let error):
                cont.resume(throwing: error)
            }
        }
    }
}
""",
        bug_summary="The success path calls resume(returning:) twice on the same continuation",
        bug_category="concurrency",
        difficulty="advanced",
        hints=("Resume exactly once",),
        keywords=("continuation", "resume", "twice", "success"),
    ),
    "conc-task-loop": MockSnippet(
        code="""\
func warmup(_ ids: [Int]) async {
    for id in ids {
        Task.detached {
            await spin(id)
        }
    }
}
func spin(_ id: Int) async {}
""",
        bug_summary="Task.detached in a loop is unstructured; warmup ends while spin still runs",
        bug_category="concurrency",
        difficulty="intermediate",
        hints=("withTaskGroup so the parent waits",),
        keywords=("Task.detached", "loop", "TaskGroup", "unstructured"),
    ),
    "conc-taskgroup-early": MockSnippet(
        code="""\
func firstWins(_ ids: [Int]) async -> Int {
    await withTaskGroup(of: Int.self) { group in
        for id in ids {
            group.addTask { id * id }
        }
        return await group.next() ?? 0
    }
}
""",
        bug_summary="Returning the first group.next() cancels every other child before it finishes",
        bug_category="concurrency",
        difficulty="advanced",
        hints=("Collect all results, then return",),
        keywords=("TaskGroup", "next", "cancel", "first"),
    ),
    "conc-async-let": MockSnippet(
        code="""\
func total() async -> Int {
    async let x = left()
    async let y = right()
    return x + y
}
func left() async -> Int { 1 }
func right() async -> Int { 2 }
""",
        bug_summary="x and y are async let bindings; adding them needs await",
        bug_category="concurrency",
        difficulty="intermediate",
        hints=("await x + await y",),
        keywords=("async let", "await", "missing", "Int"),
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
    "ui-stateobject-passed": MockSnippet(
        code="""\
import SwiftUI
final class Model: ObservableObject { @Published var n = 0 }
struct Pane: View {
    @StateObject var model: Model
    init(model: Model) {
        _model = StateObject(wrappedValue: model)
    }
    var body: some View { Text("\\(model.n)") }
}
""",
        bug_summary="StateObject(wrappedValue:) still claims ownership of a Model created elsewhere",
        bug_category="SwiftUI state",
        difficulty="intermediate",
        hints=("Use ObservedObject(wrappedValue:)",),
        keywords=("StateObject", "wrappedValue", "ownership", "ObservedObject"),
    ),
    "ui-foreach-index": MockSnippet(
        code="""\
import SwiftUI
struct Roster: View {
    var items: [String]
    var body: some View {
        ForEach(Array(items.enumerated()), id: \\.offset) { _, item in
            Text(item)
        }
    }
}
""",
        bug_summary="ForEach ids rows by enumerated offset, so later inserts reuse the wrong identity",
        bug_category="SwiftUI state",
        difficulty="intermediate",
        hints=("Use a stable item id, not offset",),
        keywords=("ForEach", "offset", "enumerated", "identity"),
    ),
    "ui-onappear-task": MockSnippet(
        code="""\
import SwiftUI
struct Clock: View {
    @State private var stamp = ""
    var body: some View {
        Text(stamp)
            .onAppear {
                Task {
                    while true {
                        try? await Task.sleep(nanoseconds: 2_000_000_000)
                        stamp = "tick"
                    }
                }
            }
    }
}
""",
        bug_summary="onAppear starts an unbounded loop that is not cancelled on disappear",
        bug_category="SwiftUI state",
        difficulty="intermediate",
        hints=("Use .task so SwiftUI cancels the loop",),
        keywords=("onAppear", "Task", "loop", "cancel"),
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
    "cap-session-vc": MockSnippet(
        code="""\
import UIKit
final class Screen: UIViewController {
    var task: URLSessionDataTask?
    func load(_ url: URL) {
        task = URLSession.shared.dataTask(with: url) { _, _, _ in
            self.view.setNeedsLayout()
        }
        task?.resume()
    }
}
""",
        bug_summary="The VC stores the data task whose completion captures self, forming a retain cycle",
        bug_category="captures",
        difficulty="intermediate",
        hints=("Capture [weak self]",),
        keywords=("dataTask", "retain cycle", "self", "UIViewController"),
    ),
    "cap-notify-observer": MockSnippet(
        code="""\
import Foundation
final class Watch {
    init() {
        NotificationCenter.default.addObserver(
            forName: Notification.Name("tick"),
            object: nil,
            queue: .main
        ) { _ in
            print(self)
        }
    }
}
""",
        bug_summary="Block observer captures self strongly and the token is never stored or removed",
        bug_category="captures",
        difficulty="intermediate",
        hints=("Store the observer token and remove it",),
        keywords=("addObserver", "token", "self", "NotificationCenter"),
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
    "send-actor-task-race": MockSnippet(
        code="""\
final class Bag {
    var items: [String] = []
}
actor Shelf {
    let bag = Bag()
    func stock(_ item: String) {
        Task { self.bag.items.append(item) }
        bag.items.append(item)
    }
}
""",
        bug_summary="Shelf and the Task it starts both append to the same non-Sendable Bag",
        bug_category="sendable",
        difficulty="advanced",
        hints=("Keep Bag mutations on one isolation domain",),
        keywords=("Sendable", "actor", "Task", "Bag"),
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
    "proto-static-dispatch": MockSnippet(
        code="""\
protocol Label {
    var text: String { get }
}
extension Label {
    func tag() -> String { text }
}
struct User: Label {
    var text: String
    func tag() -> String { "user:" + text }
}
func show(_ item: Label) -> String {
    item.tag()
}
""",
        bug_summary="tag() lives only in the extension, so show(User) returns text, not user:text",
        bug_category="protocol witnesses",
        difficulty="advanced",
        hints=("Add tag() to the protocol",),
        keywords=("extension", "protocol", "dispatch", "tag"),
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
    "cast-any-force": MockSnippet(
        code="""\
func asString(_ value: Any) -> String {
    return value as! String
}
""",
        bug_summary="Forced as! String crashes when value is another type",
        bug_category="type casting",
        difficulty="beginner",
        hints=("as? String",),
        keywords=("as!", "String", "Any", "cast"),
    ),
    "cast-array-wrong": MockSnippet(
        code="""\
func ns(_ values: [Any]) -> [NSNumber] {
    return values as! [NSNumber]
}
""",
        bug_summary="Forced [NSNumber] cast fails if the array is not all NSNumber",
        bug_category="type casting",
        difficulty="beginner",
        hints=("compactMap",),
        keywords=("as!", "NSNumber", "array", "cast"),
    ),
    "init-url-force": MockSnippet(
        code="""\
func file(_ path: String) -> URL {
    return URL(string: "file://" + path)!
}
""",
        bug_summary="Building a file URL with URL(string:)! still crashes if the string is invalid",
        bug_category="failable init",
        difficulty="beginner",
        hints=("URL(fileURLWithPath:)",),
        keywords=("URL", "string", "failable", "file"),
    ),
    "init-int-force": MockSnippet(
        code="""\
func score(from raw: String) -> Double {
    return Double(raw)!
}
""",
        bug_summary="Double(String) is failable; force unwrap crashes on junk text",
        bug_category="failable init",
        difficulty="beginner",
        hints=("Double(raw) is Optional",),
        keywords=("Double", "String", "failable", "unwrap"),
    ),
    "inout-local-copy": MockSnippet(
        code="""\
func clear(_ items: [String]) {
    var items = items
    items.removeAll()
}
""",
        bug_summary="removeAll mutates a local copy of the array, not the caller's value",
        bug_category="inout / COW",
        difficulty="beginner",
        hints=("inout [String]",),
        keywords=("inout", "copy", "removeAll", "array"),
    ),
    "cow-iterate-mutate": MockSnippet(
        code="""\
func dropOdds(_ items: inout [Int]) {
    for (i, n) in items.enumerated() {
        if n % 2 == 1 {
            items.remove(at: i)
        }
    }
}
""",
        bug_summary="remove(at:) while enumerated() walks items shifts indices and can trap",
        bug_category="inout / COW",
        difficulty="intermediate",
        hints=("Filter into a new array",),
        keywords=("remove", "enumerated", "mutate", "indices"),
    ),
    "enum-if-case-wrong": MockSnippet(
        code="""\
enum Slot { case ready(Int), idle }
func value(_ slot: Slot) -> Int {
    guard case .ready = slot else { return 0 }
    return 1
}
""",
        bug_summary="guard case .ready does not unwrap the Int payload so the function returns 1 not the value",
        bug_category="enums",
        difficulty="beginner",
        hints=("case .ready(let n)",),
        keywords=("enum", "guard case", "payload", "Int"),
    ),
    "enum-switch-assoc": MockSnippet(
        code="""\
enum Event { case ping(String), pong }
func name(_ event: Event) -> String {
    switch event {
    case .ping:
        return "ping"
    case .pong:
        return "pong"
    }
}
""",
        bug_summary="case .ping drops the associated String and always returns the label ping",
        bug_category="enums",
        difficulty="beginner",
        hints=("case .ping(let s)",),
        keywords=("enum", "switch", "associated", "String"),
    ),
    "defer-after-return": MockSnippet(
        code="""\
final class Latch {
    var held = false
    func lock() { held = true }
    func unlock() { held = false }
}
func unlock(_ latch: Latch, _ n: Int) -> Int {
    latch.lock()
    return n
    latch.unlock()
}
""",
        bug_summary="unlock() after return never runs so the latch stays held",
        bug_category="defer",
        difficulty="beginner",
        hints=("defer { latch.unlock() }",),
        keywords=("return", "unlock", "latch", "defer"),
    ),
    "defer-stale-copy": MockSnippet(
        code="""\
func next(_ n: Int) -> Int {
    var n = n
    defer { print("leaving", n) }
    return n + 1
}
""",
        bug_summary="defer prints n after the return is computed; it still shows the old n because n + 1 was not stored",
        bug_category="defer",
        difficulty="intermediate",
        hints=("Assign n += 1 before return",),
        keywords=("defer", "print", "return", "n"),
    ),
    "defer-file-handle": MockSnippet(
        code="""\
import Foundation
func save(_ url: URL, _ data: Data) throws {
    let handle = try FileHandle(forWritingTo: url)
    handle.write(data)
}
""",
        bug_summary="The write handle is never closed, so the file descriptor leaks",
        bug_category="defer",
        difficulty="beginner",
        hints=("defer { try? handle.close() }",),
        keywords=("FileHandle", "write", "close", "leak"),
    ),
    "unowned-self-gone": MockSnippet(
        code="""\
class Client {
    var onOK: (() -> Void)?
    func arm() {
        onOK = { [unowned self] in print(self) }
    }
}
""",
        bug_summary="unowned self in onOK crashes if the callback fires after Client is freed",
        bug_category="unowned",
        difficulty="intermediate",
        hints=("[weak self]",),
        keywords=("unowned", "callback", "crash", "self"),
    ),
    "unowned-not-weak": MockSnippet(
        code="""\
class Child {
    unowned var owner: Parent
    init(owner: Parent) { self.owner = owner }
}
class Parent {
    var child: Child?
}
""",
        bug_summary="unowned owner crashes if Parent can outlive or nil-out the relationship unsafely; Child requires a living Parent",
        bug_category="unowned",
        difficulty="intermediate",
        hints=("weak var owner",),
        keywords=("unowned", "owner", "Parent", "weak"),
    ),
    "some-any-assoc": MockSnippet(
        code="""\
protocol Box { associatedtype Value }
func dump(_ box: Box) {
    print(box)
}
""",
        bug_summary="Box has associatedtype Value so it cannot be a parameter type without any or generics",
        bug_category="some vs any",
        difficulty="intermediate",
        hints=("any Box",),
        keywords=("associatedtype", "any", "protocol", "Box"),
    ),
    "some-return-mismatch": MockSnippet(
        code="""\
protocol Pet {}
struct Cat: Pet {}
struct Dog: Pet {}
func pet(flag: Bool) -> some Pet {
    flag ? Cat() : Dog()
}
""",
        bug_summary="Ternary of Cat and Dog is not one concrete type for some Pet",
        bug_category="some vs any",
        difficulty="intermediate",
        hints=("any Pet",),
        keywords=("some", "ternary", "Pet", "opaque"),
    ),
    "auto-store-nonescaping": MockSnippet(
        code="""\
final class Holder {
    var block: () -> String = { "" }
    func take(_ text: @autoclosure () -> String) {
        block = text
    }
}
""",
        bug_summary="take cannot assign a non-escaping autoclosure to the stored block property",
        bug_category="autoclosure",
        difficulty="intermediate",
        hints=("@escaping @autoclosure",),
        keywords=("autoclosure", "stored", "escaping", "block"),
    ),
    "auto-eval-twice": MockSnippet(
        code="""\
func assertOK(_ test: @autoclosure () -> Bool) {
    if !test() { print("fail", test()) }
}
""",
        bug_summary="On failure, test() runs a second time so the autoclosure side effects repeat",
        bug_category="autoclosure",
        difficulty="beginner",
        hints=("Store test() in a let",),
        keywords=("autoclosure", "twice", "assert", "side effect"),
    ),
    "default-instance-member": MockSnippet(
        code="""\
class Maker {
    var base = 10
    func add(n: Int = base) -> Int { n + base }
}
""",
        bug_summary="Default n: Int = base uses instance member base, which is not allowed",
        bug_category="default arguments",
        difficulty="intermediate",
        hints=("Use a static default or pass base",),
        keywords=("default", "instance", "base", "argument"),
    ),
    "default-proto-extension": MockSnippet(
        code="""\
protocol Reset {
    func reset(to value: Int)
}
extension Reset {
    func reset(to value: Int = 0) { }
}
struct Counter: Reset {
    func reset(to value: Int) {}
}
func zero(_ c: Counter) { c.reset() }
""",
        bug_summary="Counter.reset() has no default; the extension's default is not the protocol witness default",
        bug_category="default arguments",
        difficulty="advanced",
        hints=("Add a default on the protocol requirement",),
        keywords=("protocol", "extension", "default", "reset"),
    ),
    "main-task-ui": MockSnippet(
        code="""\
import UIKit
func paint(_ view: UIView) {
    Task.detached {
        view.backgroundColor = .red
    }
}
""",
        bug_summary="UIView is mutated from Task.detached, which is not the main actor",
        bug_category="MainActor",
        difficulty="intermediate",
        hints=("MainActor.run",),
        keywords=("MainActor", "UIView", "detached", "UI"),
    ),
    "main-callback-label": MockSnippet(
        code="""\
import UIKit
func ping(_ field: UITextField, url: URL) {
    URLSession.shared.dataTask(with: url) { data, _, _ in
        field.text = data.flatMap { String(data: $0, encoding: .utf8) }
    }.resume()
}
""",
        bug_summary="UITextField.text is set on the session callback queue, not the main actor",
        bug_category="MainActor",
        difficulty="intermediate",
        hints=("Hop to main before touching field",),
        keywords=("MainActor", "UITextField", "URLSession", "callback"),
    ),
    "main-task-published": MockSnippet(
        code="""\
import Combine
final class Roster: ObservableObject {
    @Published var count = 0
    func bump() {
        DispatchQueue.global().async {
            self.count += 1
        }
    }
}
""",
        bug_summary="@Published count is incremented on a background queue, not the main actor",
        bug_category="MainActor",
        difficulty="intermediate",
        hints=("Publish on the main queue",),
        keywords=("MainActor", "@Published", "background", "DispatchQueue"),
    ),
    "main-gcd-async": MockSnippet(
        code="""\
import UIKit
func round(_ view: UIView) {
    DispatchQueue.global().async {
        view.layer.cornerRadius = 8
    }
}
""",
        bug_summary="UIView.layer is mutated on a background DispatchQueue",
        bug_category="MainActor",
        difficulty="intermediate",
        hints=("Hop to the main queue before touching layer",),
        keywords=("DispatchQueue", "global", "layer", "UIView"),
    ),
    "main-await-hop": MockSnippet(
        code="""\
@MainActor
final class Meter {
    var total = 0
    nonisolated func ingest(_ n: Int) async {
        let remote = await Self.pull()
        total = remote + n
    }
    static nonisolated func pull() async -> Int { 1 }
}
""",
        bug_summary="nonisolated ingest writes MainActor-isolated total after await without an actor hop",
        bug_category="MainActor",
        difficulty="advanced",
        hints=("Keep ingest on the main actor",),
        keywords=("MainActor", "nonisolated", "await", "total"),
    ),
    "cancel-ignore-flag": MockSnippet(
        code="""\
func drain(_ n: Int) async {
    var i = 0
    while i < n {
        i += 1
        await Task.yield()
    }
}
""",
        bug_summary="while loop never reads Task.isCancelled",
        bug_category="Task cancellation",
        difficulty="intermediate",
        hints=("Break when Task.isCancelled",),
        keywords=("isCancelled", "while", "Task", "cancellation"),
    ),
    "cancel-no-check": MockSnippet(
        code="""\
func pump(_ n: Int) async {
    for _ in 0..<n {
        try? await Task.sleep(for: .milliseconds(1))
    }
}
""",
        bug_summary="try? swallows CancellationError so the loop does not stop when the task is cancelled",
        bug_category="Task cancellation",
        difficulty="intermediate",
        hints=("Don't swallow cancellation with try?",),
        keywords=("try?", "CancellationError", "sleep", "loop"),
    ),
    "actor-await-stale": MockSnippet(
        code="""\
actor Flag {
    var on = false
    func toggle() async {
        let was = on
        await Task.yield()
        on = !was
    }
}
""",
        bug_summary="toggle awaits then writes !was, racing another toggle and losing updates",
        bug_category="actor reentrancy",
        difficulty="advanced",
        hints=("Toggle on after await without the snapshot",),
        keywords=("actor", "reentrancy", "toggle", "await"),
    ),
    "actor-await-balance": MockSnippet(
        code="""\
actor Tank {
    var ml = 100
    func pour(_ x: Int) async {
        await Task.yield()
        ml -= x
    }
}
""",
        bug_summary="pour does not check remaining ml after await so concurrent pours can drive ml negative",
        bug_category="actor reentrancy",
        difficulty="advanced",
        hints=("Guard ml after await",),
        keywords=("actor", "reentrancy", "pour", "await"),
    ),
    "ui-env-missing": MockSnippet(
        code="""\
import SwiftUI
class Hub: ObservableObject { var title = "" }
struct Pane: View {
    @EnvironmentObject var hub: Hub
    var body: some View { Text(hub.title) }
}
""",
        bug_summary="@EnvironmentObject Hub is never injected by a parent view",
        bug_category="SwiftUI environment",
        difficulty="intermediate",
        hints=("environmentObject(Hub())",),
        keywords=("EnvironmentObject", "Hub", "inject", "SwiftUI"),
    ),
    "ui-observable-state": MockSnippet(
        code="""\
import SwiftUI
@Observable
final class Hub { var title = "" }
struct Pane: View {
    @State private var hub = Hub()
    var body: some View { Text(hub.title) }
}
""",
        bug_summary="@State creates a private Hub; siblings cannot share it through the environment",
        bug_category="SwiftUI environment",
        difficulty="intermediate",
        hints=("@Environment(Hub.self)",),
        keywords=("@State", "@Observable", "Hub", "share"),
    ),
    "ui-env-wrong-sibling": MockSnippet(
        code="""\
import SwiftUI
final class Hub: ObservableObject { @Published var title = "" }
struct Root: View {
    @StateObject var hub = Hub()
    var body: some View {
        TabView {
            NavPane().environmentObject(hub)
            BodyPane()
        }
    }
}
struct NavPane: View { var body: some View { Text("nav") } }
struct BodyPane: View {
    @EnvironmentObject var hub: Hub
    var body: some View { Text(hub.title) }
}
""",
        bug_summary="environmentObject is on NavPane only, so BodyPane in the other tab has no Hub",
        bug_category="SwiftUI environment",
        difficulty="intermediate",
        hints=("Attach environmentObject to TabView",),
        keywords=("environmentObject", "TabView", "sibling", "Hub"),
    ),
    "slice-index-zero": MockSnippet(
        code="""\
func last(_ slice: ArraySlice<String>) -> String {
    return slice[slice.count - 1]
}
""",
        bug_summary="slice[count - 1] assumes indices start at 0; slices often start later and trap",
        bug_category="Sequence slices",
        difficulty="beginner",
        hints=("slice.last or endIndex",),
        keywords=("ArraySlice", "count", "indices", "trap"),
    ),
    "slice-drop-first": MockSnippet(
        code="""\
func tail(_ items: [String]) -> String {
    let t = items.suffix(from: 1)
    return t[1]
}
""",
        bug_summary="suffix(from: 1) keeps original indices so t[1] is the second original element only if that index exists; it is easy to mix up with 0-based access",
        bug_category="Sequence slices",
        difficulty="beginner",
        hints=("t.startIndex",),
        keywords=("suffix", "slice", "indices", "1"),
    ),
    "comb-sink-dropped": MockSnippet(
        code="""\
import Combine
import Foundation

final class Clock {
    func start() {
        Timer.publish(every: 1, on: .main, in: .common)
            .autoconnect()
            .sink { date in
                print(date)
            }
    }
}
""",
        bug_summary="Timer.publish sink is not stored, so the subscription ends as soon as start() returns",
        bug_category="Combine",
        difficulty="intermediate",
        hints=("Keep the cancellable on Clock",),
        keywords=("Timer.publish", "sink", "AnyCancellable", "store"),
    ),
    "comb-receive-main": MockSnippet(
        code="""\
import Combine

final class Roster: ObservableObject {
    @Published var heading = ""

    func load(_ url: URL) {
        URLSession.shared.dataTaskPublisher(for: url)
            .map { String(data: $0.data, encoding: .utf8) ?? "" }
            .replaceError(with: "")
            .assign(to: &$heading)
    }
}
""",
        bug_summary="@Published heading is assigned from dataTaskPublisher without hopping to the main queue",
        bug_category="Combine",
        difficulty="intermediate",
        hints=("receive(on: DispatchQueue.main) before assign",),
        keywords=("receive(on:)", "@Published", "dataTaskPublisher", "main"),
    ),
    "comb-bag-local": MockSnippet(
        code="""\
import Combine
import UIKit

final class Screen: UIViewController {
    func viewDidLoadBind() {
        var bag = Set<AnyCancellable>()
        NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)
            .sink { _ in print("active") }
            .store(in: &bag)
    }
}
""",
        bug_summary="viewDidLoadBind stores cancellables in a local Set that is released when the method returns",
        bug_category="Combine",
        difficulty="intermediate",
        hints=("Keep the Set as a property on Screen",),
        keywords=("AnyCancellable", "viewDidLoad", "local", "Set"),
    ),
    "comb-never-cancel": MockSnippet(
        code="""\
import Combine

final class AppBag {
    static let shared = AppBag()
    var bag = Set<AnyCancellable>()
}

final class Roster: ObservableObject {
    func bind() {
        Just(1)
            .delay(for: .seconds(60), scheduler: RunLoop.main)
            .sink { _ in print("late") }
            .store(in: &AppBag.shared.bag)
    }
}
""",
        bug_summary="The delayed sink is stored on a process-wide bag, so it outlives Roster",
        bug_category="Combine",
        difficulty="intermediate",
        hints=("Keep the cancellable on Roster",),
        keywords=("AnyCancellable", "shared", "delay", "lifetime"),
    ),
    "excl-inout-same": MockSnippet(
        code="""\
func swap(_ a: inout Int, _ b: inout Int) {
    let t = a
    a = b
    b = t
}
func flip(_ n: inout Int) {
    swap(&n, &n)
}
""",
        bug_summary="swap(&n, &n) gives two overlapping inout accesses to the same Int",
        bug_category="exclusivity",
        difficulty="intermediate",
        hints=("The two & arguments must be distinct memory",),
        keywords=("inout", "swap", "overlap", "exclusivity"),
    ),
    "excl-self-inout": MockSnippet(
        code="""\
struct Box {
    var n = 0
    mutating func merge(_ other: inout Box) {
        n += other.n
    }
}
func clash() {
    var box = Box()
    box.merge(&box)
}
""",
        bug_summary="merge takes inout Box that is the same instance as self",
        bug_category="exclusivity",
        difficulty="intermediate",
        hints=("Use a second Box",),
        keywords=("inout", "self", "merge", "exclusivity"),
    ),
    "excl-prop-inout": MockSnippet(
        code="""\
struct Stats {
    var hits = 0
    var total = 0
    mutating func copyHits(_ dest: inout Int) {
        dest = hits
        hits = 0
    }
}
func clash() {
    var stats = Stats()
    stats.copyHits(&stats.hits)
}
""",
        bug_summary="copyHits writes hits while dest is an inout alias of hits",
        bug_category="exclusivity",
        difficulty="intermediate",
        hints=("Pass a different Int, not &stats.hits",),
        keywords=("inout", "property", "hits", "exclusivity"),
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
