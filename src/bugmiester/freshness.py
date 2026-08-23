"""Scenario seeds, avoid-list, normalize + similarity reject."""

from __future__ import annotations

import difflib
import random
import re
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from bugmiester.llm.parse import ParseError
from bugmiester.mix import (
    adaptive_phase,
    is_gnarly_seed,
    normalize_mix,
    preferred_categories,
)


@dataclass(frozen=True)
class ScenarioSeed:
    seed_id: str
    category: str
    setting: str
    constraint: str | None = None

    @property
    def theme(self) -> str:
        base = f"{self.category}: {self.setting}"
        if self.constraint:
            return f"{base} ({self.constraint})"
        return base


# Curated pool — 32 categories so a 10-bug round can skip class repeats
# and later rounds still have unused classes.
SEED_POOL: tuple[ScenarioSeed, ...] = (
    ScenarioSeed("opt-dict-force", "optionals", "dictionary lookup"),
    ScenarioSeed("col-empty-avg", "collections", "empty array average"),
    ScenarioSeed("ref-class-copy", "value vs reference", "class mistaken for value type"),
    ScenarioSeed("flow-switch-int", "control flow", "non-exhaustive switch"),
    ScenarioSeed("err-async-try", "errors", "async networking decode"),
    ScenarioSeed("col-off-by-one", "collections", "table selection index"),
    ScenarioSeed("opt-greet-print", "optionals", "login form greeting"),
    ScenarioSeed("err-try-optional", "errors", "file URL write"),
    ScenarioSeed(
        "err-empty-catch",
        "errors",
        "empty catch swallows the error",
        "must have catch with an empty body; not try?; not Result.get",
    ),
    ScenarioSeed(
        "err-try-bang",
        "errors",
        "try! on a throwing call",
        "must use try!; not try?; not a failable init !",
    ),
    ScenarioSeed("conc-actor-mut", "concurrency", "timer callback bump", "must involve actor"),
    ScenarioSeed("val-let-struct", "value vs reference", "immutable point"),
    ScenarioSeed("opt-array-first", "optionals", "first element access"),
    ScenarioSeed(
        "opt-iflet-outer",
        "optionals",
        "if let then uses the outer optional",
        "must bind with if let or guard let then still use the wrapped optional; no force unwrap",
    ),
    ScenarioSeed(
        "opt-chain-skip",
        "optionals",
        "optional chaining skips a side effect",
        "must use ?. so a mutating or saving call is skipped when nil; no force unwrap; not if let outer",
    ),
    ScenarioSeed(
        "opt-iuo-outlet",
        "optionals",
        "implicitly unwrapped IBOutlet",
        "must use an IUO outlet or UILabel!; not a dictionary !; not as!",
    ),
    ScenarioSeed("conc-await-miss", "concurrency", "missing await on async call"),
    ScenarioSeed(
        "conc-nontask-async",
        "concurrency",
        "async work from viewDidLoad without Task",
        "must call async from a sync UIKit entry; not a missing await inside an async function",
    ),
    ScenarioSeed(
        "conc-task-orphan",
        "concurrency",
        "unstructured Task never cancelled",
        "must start Task that outlives the owner; not missing await; not MainActor; not a retain-cycle-only puzzle",
    ),
    ScenarioSeed(
        "conc-continuation-stuck",
        "concurrency",
        "checked continuation never resumed",
        "must call withCheckedContinuation and skip resume on a path; not missing await",
    ),
    ScenarioSeed(
        "conc-continuation-double",
        "concurrency",
        "checked continuation resumed twice",
        "must resume the same continuation on two paths (e.g. missing return after resume); not a never-resume hang; not missing await",
    ),
    ScenarioSeed(
        "conc-task-loop",
        "concurrency",
        "unstructured Task inside a for-loop",
        "must spawn Task in a loop instead of withTaskGroup; not a single orphaned Task; not missing await on one call",
    ),
    ScenarioSeed(
        "conc-taskgroup-early",
        "concurrency",
        "TaskGroup returns after the first child and cancels the rest",
        "must use withTaskGroup and return after group.next() (or equivalent) so remaining children are cancelled; not unstructured Task in a loop; not missing await on one call",
    ),
    ScenarioSeed(
        "conc-async-let",
        "concurrency",
        "async let results used without await",
        "must use async let and skip await; not a plain missing await; not TaskGroup",
    ),
    ScenarioSeed("acc-mutating-let", "access control", "mutating method on a let value"),
    ScenarioSeed("acc-private-field", "access control", "private property from a free function"),
    ScenarioSeed("ui-state-let", "SwiftUI state", "counter button stored as let"),
    ScenarioSeed("ui-binding-dollar", "SwiftUI state", "TextField missing binding prefix"),
    ScenarioSeed(
        "ui-stateobject-passed",
        "SwiftUI state",
        "StateObject owns an object the parent passed in",
        "must involve @StateObject on a passed-in object; not $ Binding; not let count",
    ),
    ScenarioSeed(
        "ui-foreach-index",
        "SwiftUI state",
        "ForEach over 0..<count",
        "must be ForEach identity; not $ Binding; not @State let",
    ),
    ScenarioSeed(
        "ui-onappear-task",
        "SwiftUI state",
        "onAppear starts a Task that is not cancelled",
        "must use onAppear plus Task; not .task; not $ Binding; not ForEach",
    ),
    ScenarioSeed("cap-stored-self", "captures", "escaping closure stored on self"),
    ScenarioSeed("cap-timer-cycle", "captures", "repeating timer owned by self"),
    ScenarioSeed(
        "cap-session-vc",
        "captures",
        "URLSession completion on a view controller",
        "must capture self in a URLSession completion stored on the VC; not a Timer; not missing await; not MainActor",
    ),
    ScenarioSeed(
        "cap-notify-observer",
        "captures",
        "NotificationCenter observer never removed",
        "must add a NotificationCenter observer and never remove it; not a Timer; not URLSession",
    ),
    ScenarioSeed("eq-identity-id", "equality", "identity used instead of id equality"),
    ScenarioSeed("eq-missing-protocol", "equality", "class compared with == but not Equatable"),
    ScenarioSeed(
        "send-task-mutate",
        "sendable",
        "class mutated from Task",
        "must involve Sendable or isolation; no force unwrap",
    ),
    ScenarioSeed(
        "send-actor-escape",
        "sendable",
        "non-Sendable class passed into actor",
        "must be a compile-logic isolation error",
    ),
    ScenarioSeed(
        "send-actor-task-race",
        "sendable",
        "actor and Task both mutate the same non-Sendable class",
        "must mutate one non-Sendable instance from an actor method and from a Task it starts; not only passing the class into an actor; not Task-only mutation without an actor",
    ),
    ScenarioSeed(
        "cod-key-mismatch",
        "codable",
        "JSON key does not match property",
        "must involve Codable keys; no force unwrap",
    ),
    ScenarioSeed(
        "cod-date-strategy",
        "codable",
        "ISO-8601 date decoded with the default strategy",
        "must fail at Date decode; no force unwrap",
    ),
    ScenarioSeed(
        "str-int-subscript",
        "string indexes",
        "String subscripted with Int",
        "must be a String.Index bug",
    ),
    ScenarioSeed(
        "str-offset-end",
        "string indexes",
        "index offset past endIndex",
        "must involve String.Index; no Int subscript",
    ),
    ScenarioSeed(
        "lazy-let-struct",
        "lazy",
        "lazy var on a let struct",
        "must involve lazy",
    ),
    ScenarioSeed(
        "lazy-stale-total",
        "lazy",
        "lazy sum not recomputed after mutation",
        "must involve lazy; not a retain cycle",
    ),
    ScenarioSeed(
        "proto-wrong-name",
        "protocol witnesses",
        "type claims protocol but method name is wrong",
        "must be a protocol witness mismatch",
    ),
    ScenarioSeed(
        "proto-mutating-req",
        "protocol witnesses",
        "non-mutating witness for mutating requirement",
        "must involve a protocol mutating requirement",
    ),
    ScenarioSeed(
        "proto-static-dispatch",
        "protocol witnesses",
        "extension method shadows the type's method on an existential",
        "must call a method that is not a protocol requirement through the protocol type; not a wrong witness name; not some/any",
    ),
    ScenarioSeed(
        "res-optional-result",
        "result",
        "Result treated as Optional",
        "must involve Result; no try? on throws",
    ),
    ScenarioSeed(
        "res-try-get",
        "result",
        "try used on Result.get without throws",
        "must call Result.get",
    ),
    ScenarioSeed(
        "cast-any-force",
        "type casting",
        "Any downcast with as!",
        "must involve as!; not a dictionary force unwrap",
    ),
    ScenarioSeed(
        "cast-array-wrong",
        "type casting",
        "array forced to the wrong element type",
        "must be a wrong as! on a collection",
    ),
    ScenarioSeed(
        "init-url-force",
        "failable init",
        "URL(string:) force unwrapped",
        "must involve a failable init, not a dictionary lookup",
    ),
    ScenarioSeed(
        "init-int-force",
        "failable init",
        "Int(String) force unwrapped",
        "must use a failable numeric init",
    ),
    ScenarioSeed(
        "inout-local-copy",
        "inout / COW",
        "mutates a local copy instead of inout",
        "must involve inout or a missed mutation",
    ),
    ScenarioSeed(
        "cow-iterate-mutate",
        "inout / COW",
        "array mutated while iterating",
        "must mutate a collection during for-in",
    ),
    ScenarioSeed(
        "enum-if-case-wrong",
        "enums",
        "if case binds the wrong associated value",
        "must involve enum associated values; no Result.get",
    ),
    ScenarioSeed(
        "enum-switch-assoc",
        "enums",
        "switch ignores associated payload",
        "must switch on an enum with associated values",
    ),
    ScenarioSeed(
        "defer-after-return",
        "defer",
        "cleanup placed after return",
        "must involve defer or unreachable cleanup",
    ),
    ScenarioSeed(
        "defer-stale-copy",
        "defer",
        "defer captures a value copied too early",
        "must involve defer reading a stale copy",
    ),
    ScenarioSeed(
        "defer-file-handle",
        "defer",
        "FileHandle never closed",
        "must open FileHandle and skip close; not cleanup after return; not a stale defer copy",
    ),
    ScenarioSeed(
        "unowned-self-gone",
        "unowned",
        "unowned self used after the owner is released",
        "must use unowned; not a retain cycle",
    ),
    ScenarioSeed(
        "unowned-not-weak",
        "unowned",
        "unowned where the reference can be nil",
        "must be unowned vs weak; no Timer retain cycle",
    ),
    ScenarioSeed(
        "some-any-assoc",
        "some vs any",
        "protocol with associatedtype used as a type",
        "must involve some/any or Self requirements",
    ),
    ScenarioSeed(
        "some-return-mismatch",
        "some vs any",
        "opaque return hides two different concrete types",
        "must involve some; not SwiftUI Binding",
    ),
    ScenarioSeed(
        "auto-store-nonescaping",
        "autoclosure",
        "non-escaping autoclosure stored for later",
        "must involve @autoclosure",
    ),
    ScenarioSeed(
        "auto-eval-twice",
        "autoclosure",
        "autoclosure side effect runs more than once",
        "must evaluate an autoclosure twice",
    ),
    ScenarioSeed(
        "default-instance-member",
        "default arguments",
        "instance property used as a default argument",
        "must be a default argument using self or an instance member",
    ),
    ScenarioSeed(
        "default-proto-extension",
        "default arguments",
        "protocol extension default is a different function",
        "must involve a protocol requirement vs extension default",
    ),
    ScenarioSeed(
        "main-task-ui",
        "MainActor",
        "UI updated from an unstructured Task",
        "must involve MainActor or UI off the main actor; not missing await",
    ),
    ScenarioSeed(
        "main-callback-label",
        "MainActor",
        "URLSession callback writes a UILabel",
        "must hop to the main actor; not Sendable",
    ),
    ScenarioSeed(
        "main-task-published",
        "MainActor",
        "ViewModel publishes from an unstructured Task",
        "must update @Published off the main actor from Task; not URLSession dataTask; not missing await; not Combine",
    ),
    ScenarioSeed(
        "main-gcd-async",
        "MainActor",
        "UIKit updated from a global DispatchQueue",
        "must use DispatchQueue.global to touch UI; not Task; not URLSession dataTask; not @Published",
    ),
    ScenarioSeed(
        "main-await-hop",
        "MainActor",
        "MainActor state written after await from a nonisolated method",
        "must be a nonisolated async method on a MainActor type that assigns isolated state after await; not unstructured Task UI; not URLSession callback; not DispatchQueue.global",
    ),
    ScenarioSeed(
        "cancel-ignore-flag",
        "Task cancellation",
        "loop ignores Task.isCancelled",
        "must involve Task cancellation; not missing await",
    ),
    ScenarioSeed(
        "cancel-no-check",
        "Task cancellation",
        "throwing loop skips checkCancellation",
        "must call or omit Task.checkCancellation",
    ),
    ScenarioSeed(
        "actor-await-stale",
        "actor reentrancy",
        "actor state used after await is stale",
        "must await inside an actor then use prior state",
    ),
    ScenarioSeed(
        "actor-await-balance",
        "actor reentrancy",
        "withdraw awaits then deducts a stale balance",
        "must be actor reentrancy; not a missing await",
    ),
    ScenarioSeed(
        "ui-env-missing",
        "SwiftUI environment",
        "EnvironmentObject used without injection",
        "must involve environmentObject; not $ Binding",
    ),
    ScenarioSeed(
        "ui-observable-state",
        "SwiftUI environment",
        "shared model stored as @State instead of environment",
        "must involve @Observable or environment; not TextField $",
    ),
    ScenarioSeed(
        "ui-env-wrong-sibling",
        "SwiftUI environment",
        "environmentObject attached to the wrong sibling",
        "must inject on a sibling, not the ancestor of the consumer; not $ Binding",
    ),
    ScenarioSeed(
        "slice-index-zero",
        "Sequence slices",
        "ArraySlice indexed from 0",
        "must index a slice; not String.Index",
    ),
    ScenarioSeed(
        "slice-drop-first",
        "Sequence slices",
        "dropFirst slice then uses [0]",
        "must use a slice after dropFirst or suffix",
    ),
    ScenarioSeed(
        "comb-sink-dropped",
        "Combine",
        "sink result not stored",
        "must drop AnyCancellable; not a retain cycle; not missing await",
    ),
    ScenarioSeed(
        "comb-receive-main",
        "Combine",
        "publisher updates UI off the main queue",
        "must involve Combine receive(on:) or a publisher thread hop; not URLSession dataTask; not missing await",
    ),
    ScenarioSeed(
        "comb-bag-local",
        "Combine",
        "cancellables stored in a local Set",
        "must store AnyCancellable in a function-local Set; not a retain cycle; not missing await; not receive(on:)",
    ),
    ScenarioSeed(
        "comb-never-cancel",
        "Combine",
        "subscription stored on a longer-lived bag",
        "must keep a publisher subscribed after the screen is gone; not a local Set; not a dropped sink; not receive(on:)",
    ),
    ScenarioSeed(
        "excl-inout-same",
        "exclusivity",
        "two inout arguments alias the same memory",
        "must overlap inout accesses; not a missed inout; not mutating a let",
    ),
    ScenarioSeed(
        "excl-self-inout",
        "exclusivity",
        "mutating method takes inout self",
        "must pass &self into a mutating method; not a retain cycle; not mutating a let",
    ),
    ScenarioSeed(
        "excl-prop-inout",
        "exclusivity",
        "inout to a property that the method also accesses",
        "must pass &property into a mutating method that also reads or writes that stored property",
    ),
)


@dataclass(frozen=True)
class HistoryEntry:
    bug_summary: str
    bug_category: str
    theme: str
    code: str
    normalized_code: str


def history_entry(
    *,
    bug_summary: str,
    bug_category: str,
    theme: str,
    code: str,
) -> HistoryEntry:
    return HistoryEntry(
        bug_summary=bug_summary,
        bug_category=bug_category,
        theme=theme,
        code=code,
        normalized_code=normalize_code(code),
    )


@dataclass(frozen=True)
class GeneratedSnippet:
    code: str
    bug_summary: str
    bug_category: str
    difficulty: str
    hints: tuple[str, ...]
    keywords: tuple[str, ...]
    seed: ScenarioSeed


def normalize_code(code: str) -> str:
    """Strip comments and excess whitespace for similarity checks."""
    text = code.replace("\r\n", "\n")
    # Remove // line comments and /* */ blocks (simple).
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    lines: list[str] = []
    for line in text.split("\n"):
        if "//" in line:
            line = line[: line.index("//")]
        lines.append(line)
    text = "\n".join(lines)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9_]+", text.lower()) if len(t) > 1}


def token_jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def difflib_ratio(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def similarity_score(code_a: str, summary_a: str, code_b: str, summary_b: str) -> float:
    """Combined similarity in [0, 1] over normalized code and summaries."""
    na, nb = normalize_code(code_a), normalize_code(code_b)
    code_sim = max(difflib_ratio(na, nb), token_jaccard(na, nb))
    sum_sim = max(
        difflib_ratio(summary_a.lower(), summary_b.lower()),
        token_jaccard(summary_a, summary_b),
    )
    return max(code_sim, sum_sim)


def is_too_similar(
    code: str,
    bug_summary: str,
    history: Sequence[HistoryEntry],
    threshold: float,
) -> bool:
    for entry in history:
        score = similarity_score(code, bug_summary, entry.code, entry.bug_summary)
        if score >= threshold:
            return True
    return False


def build_avoid_list(
    history: Sequence[HistoryEntry],
    *,
    max_items: int,
) -> list[HistoryEntry]:
    if max_items <= 0:
        return []
    return list(history[-max_items:])


def order_seed_pool(
    pool: Sequence[ScenarioSeed],
    *,
    shuffle: bool,
    recent_seed_ids: Sequence[str] = (),
) -> tuple[ScenarioSeed, ...]:
    """
    Copy of the seed pool for this round.

    Seeds not seen in ``recent_seed_ids`` come first. Recently used seeds follow,
    oldest first, so a new round prefers unused settings. ``shuffle`` reorders
    the unused group only.
    """
    recency: dict[str, int] = {}
    for index, seed_id in enumerate(recent_seed_ids):
        recency[seed_id] = index
    unused = [seed for seed in pool if seed.seed_id not in recency]
    used = [seed for seed in pool if seed.seed_id in recency]
    used.sort(key=lambda seed: recency[seed.seed_id])
    if shuffle:
        random.shuffle(unused)
    return tuple(unused + used)


def pick_seed(
    pool: Sequence[ScenarioSeed],
    used_seed_ids: set[str],
    *,
    max_category_repeats: int = 1,
    mix: str = "intermediate_mix",
    bugs_per_round: int = 10,
    adaptation_enabled: bool = False,
) -> ScenarioSeed:
    """
    Next unused seed, preferring categories still under the per-round cap.

    After every category has been used ``max_category_repeats`` times, unused
    seeds in already-seen categories are allowed so a 10-bug round can finish.

    ``mix`` weights which classes come first. Default here is unweighted so unit
    tests stay stable; live rounds pass ``game.mix`` (default ``senior_mix``).

    Within a preferred band (Simple / Common / Gnarly), the next seed is
    chosen at random among matches so the round stays varied even when pool
    order is sticky.
    """
    if not pool:
        raise ValueError("SEED_POOL is empty")
    cap = max(1, max_category_repeats)
    used_seeds = [seed for seed in pool if seed.seed_id in used_seed_ids]
    category_counts = Counter(seed.category for seed in used_seeds)
    unused = [seed for seed in pool if seed.seed_id not in used_seed_ids]
    under_cap = [
        seed for seed in unused if category_counts[seed.category] < cap
    ]
    prefer = preferred_categories(
        mix,
        used_seeds,
        bugs_per_round=bugs_per_round,
        adaptation_enabled=adaptation_enabled,
    )
    gnarly_only = (
        normalize_mix(mix) == "senior_mix"
        and adaptive_phase(
            len(used_seeds),
            bugs_per_round,
            mix=mix,
            adaptation_enabled=adaptation_enabled,
        ) == "gnarly"
    )

    def _preferred(candidates: list[ScenarioSeed]) -> list[ScenarioSeed]:
        if gnarly_only:
            # Include allowlisted concurrency costumes (e.g. stuck continuation)
            # whose category is not in GNARLY_CATEGORIES.
            return [seed for seed in candidates if is_gnarly_seed(seed)]
        matched = [seed for seed in candidates if seed.category in prefer]
        # Reserve reentrancy / exclusivity / allowlisted ids for the end.
        if normalize_mix(mix) == "senior_mix":
            matched = [seed for seed in matched if not is_gnarly_seed(seed)]
        return matched

    def _take(matched: list[ScenarioSeed]) -> ScenarioSeed:
        if len(matched) == 1:
            return matched[0]
        return random.choice(matched)

    if prefer:
        prefer_under = _preferred(under_cap)
        if prefer_under:
            return _take(prefer_under)
        prefer_unused = _preferred(unused)
        if prefer_unused:
            return _take(prefer_unused)
    if under_cap:
        return under_cap[0]
    if unused:
        return unused[0]
    return pool[len(used_seed_ids) % len(pool)]


GenerateFn = Callable[[ScenarioSeed, Sequence[HistoryEntry]], GeneratedSnippet]
RawGenerateFn = Callable[[ScenarioSeed, Sequence[HistoryEntry]], str]
FallbackFn = Callable[[ScenarioSeed], GeneratedSnippet]


def generate_with_freshness(
    *,
    used_seed_ids: set[str],
    history: Sequence[HistoryEntry],
    seed_pool: Sequence[ScenarioSeed] = SEED_POOL,
    max_attempts: int = 2,
    similarity_threshold: float = 0.72,
    avoid_list_max: int = 20,
    use_fallback: bool = True,
    max_category_repeats: int = 1,
    mix: str = "intermediate_mix",
    bugs_per_round: int = 10,
    adaptation_enabled: bool = False,
    generate_fn: GenerateFn | None = None,
    generate_raw_fn: RawGenerateFn | None = None,
    fallback_fn: FallbackFn,
    parse_raw: Callable[[str], GeneratedSnippet] | None = None,
) -> tuple[GeneratedSnippet, bool, int, int, int]:
    """
    Pick a seed, generate with retries on parse failure / near-duplicates, else fallback.

    JSON parse failures and freshness rejects **share** ``max_attempts``.

    Returns
    -------
    (snippet, degraded, attempts_used, freshness_rejects, parse_failures)
    """
    if generate_fn is None and generate_raw_fn is None:
        raise ValueError("Provide generate_fn or generate_raw_fn")
    if generate_raw_fn is not None and parse_raw is None:
        raise ValueError("parse_raw is required when using generate_raw_fn")

    seed = pick_seed(
        seed_pool,
        used_seed_ids,
        max_category_repeats=max_category_repeats,
        mix=mix,
        bugs_per_round=bugs_per_round,
        adaptation_enabled=adaptation_enabled,
    )
    used_seed_ids.add(seed.seed_id)
    avoid = build_avoid_list(history, max_items=avoid_list_max)

    attempts = 0
    rejects = 0
    parse_failures = 0
    last: GeneratedSnippet | None = None

    while attempts < max_attempts:
        attempts += 1
        candidate: GeneratedSnippet | None = None
        if generate_raw_fn is not None:
            assert parse_raw is not None
            raw = generate_raw_fn(seed, avoid)
            try:
                candidate = parse_raw(raw)
            except ParseError:
                parse_failures += 1
                continue
        else:
            assert generate_fn is not None
            candidate = generate_fn(seed, avoid)

        last = candidate
        if not is_too_similar(
            candidate.code,
            candidate.bug_summary,
            avoid,
            similarity_threshold,
        ):
            return candidate, False, attempts, rejects, parse_failures
        rejects += 1
        # Stricter avoid-list for next attempt: include rejected summary as synthetic entry.
        avoid = list(avoid) + [
            history_entry(
                bug_summary=candidate.bug_summary,
                bug_category=candidate.bug_category,
                theme=seed.theme,
                code=candidate.code,
            )
        ]

    if use_fallback:
        fallback = fallback_fn(seed)
        return fallback, True, attempts, rejects, parse_failures

    if last is not None:
        # Last resort without fallback flag: return last attempt undegraded.
        return last, False, attempts, rejects, parse_failures
    raise RuntimeError("generate_with_freshness produced no candidate")
