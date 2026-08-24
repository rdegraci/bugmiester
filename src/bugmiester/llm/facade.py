"""LLM facade implementation: generate_bug(), judge_answer()."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from bugmiester.config import Settings
from bugmiester.fallback_snippets import fallback_for_seed
from bugmiester.freshness import (
    SEED_POOL,
    GeneratedSnippet,
    HistoryEntry,
    ScenarioSeed,
    generate_with_freshness,
)
from bugmiester.llm.base import JudgeResult, SnippetWithKey
from bugmiester.llm.mock_provider import MockProvider
from bugmiester.llm.parse import ParseError, parse_generation_payload, parse_judge_payload, parse_recovery_payload
from bugmiester.llm.prompts import build_generation_prompt, build_judge_prompt, build_recovery_prompt

__all__ = [
    "GenerateBugResult",
    "JudgeResult",
    "ParseError",
    "RecoveryLlmError",
    "SnippetWithKey",
    "generate_bug",
    "generate_recovery_distractors",
    "judge_answer",
]


@dataclass(frozen=True)
class GenerateBugResult:
    """Outcome of generate_bug including attempt / reject accounting."""

    snippet: SnippetWithKey
    seed: ScenarioSeed
    degraded: bool
    attempts: int
    freshness_rejects: int
    parse_failures: int = 0

    def as_generated_snippet(self) -> GeneratedSnippet:
        return GeneratedSnippet(
            code=self.snippet.code,
            bug_summary=self.snippet.bug_summary,
            bug_category=self.snippet.bug_category,
            difficulty=self.snippet.difficulty,
            hints=self.snippet.hints,
            keywords=self.snippet.keywords,
            seed=self.seed,
        )


_MOCK = MockProvider()


class ProviderNotImplementedError(NotImplementedError):
    """Raised when a live provider adapter is not wired yet."""


def _provider_name(settings: Settings) -> str:
    return (settings.llm.provider or "").strip().lower()


def _snippet_to_generated(snippet: SnippetWithKey, seed: ScenarioSeed) -> GeneratedSnippet:
    return GeneratedSnippet(
        code=snippet.code,
        bug_summary=snippet.bug_summary,
        bug_category=snippet.bug_category,
        difficulty=snippet.difficulty,
        hints=snippet.hints,
        keywords=snippet.keywords,
        seed=seed,
    )


def _mock_generate_raw(
    seed: ScenarioSeed,
    avoid: Sequence[HistoryEntry],
    settings: Settings,
) -> str:
    prompt = build_generation_prompt(
        seed,
        avoid,
        language=settings.game.language,
    )
    return _MOCK.generate_raw(prompt, settings, seed=seed)


def _live_generate_raw(provider: str, prompt: str, settings: Settings) -> str:
    # Real adapters land in later slices; keep a clear failure mode now.
    if provider == "openai":
        from bugmiester.llm import openai_provider

        return openai_provider.generate_raw(prompt, settings)
    if provider == "anthropic":
        from bugmiester.llm import anthropic_provider

        return anthropic_provider.generate_raw(prompt, settings)
    if provider == "xai":
        from bugmiester.llm import xai_provider

        return xai_provider.generate_raw(prompt, settings)
    raise ProviderNotImplementedError(
        f"Unknown llm.provider '{provider}'. Expected openai|anthropic|xai|mock."
    )


def generate_bug(
    settings: Settings,
    *,
    used_seed_ids: set[str],
    history: Sequence[HistoryEntry],
    seed_pool: Sequence[ScenarioSeed] = SEED_POOL,
    mix: str | None = None,
    bugs_per_round: int | None = None,
    adaptation_cluster_misses: int = 0,
    adaptation_miss_threshold: int | None = None,
    cross_round_first_common_bias: bool = False,
) -> GenerateBugResult:
    """
    Generate one validated snippet.

    Freshness picks the seed; JSON parse failures and similarity rejects share
    ``freshness.max_generate_attempts``. Mock is live; other providers stubbed.
    """
    provider = _provider_name(settings)
    max_attempts = settings.freshness.max_generate_attempts

    # Capture seed chosen inside generate_with_freshness via parse_raw closure —
    # we re-bind parse_raw per attempt by wrapping generate_raw_fn.
    chosen_seed: dict[str, ScenarioSeed] = {}

    def generate_raw_fn(seed: ScenarioSeed, avoid: Sequence[HistoryEntry]) -> str:
        chosen_seed["seed"] = seed
        if provider == "mock":
            return _mock_generate_raw(seed, avoid, settings)
        prompt = build_generation_prompt(
            seed, avoid, language=settings.game.language
        )
        return _live_generate_raw(provider, prompt, settings)

    def parse_raw(raw: str) -> GeneratedSnippet:
        seed = chosen_seed["seed"]
        return _snippet_to_generated(parse_generation_payload(raw), seed)

    generated, degraded, attempts, rejects, parse_failures = generate_with_freshness(
        used_seed_ids=used_seed_ids,
        history=history,
        seed_pool=seed_pool,
        max_attempts=max_attempts,
        similarity_threshold=settings.freshness.similarity_reject_threshold,
        avoid_list_max=settings.freshness.avoid_list_max,
        use_fallback=settings.resilience.use_canned_fallback_on_generate_exhaustion,
        max_category_repeats=settings.freshness.max_category_repeats_per_round,
        mix=mix if mix is not None else settings.game.mix,
        bugs_per_round=(
            bugs_per_round
            if bugs_per_round is not None
            else settings.game.bugs_per_round
        ),
        adaptation_enabled=settings.adaptation.enabled,
        cluster_misses=adaptation_cluster_misses if settings.adaptation.enabled else 0,
        miss_threshold=(
            adaptation_miss_threshold
            if adaptation_miss_threshold is not None
            else settings.adaptation.miss_threshold
        ),
        max_delayed_gnarly=settings.adaptation.max_delayed_gnarly,
        adaptation_cluster=settings.adaptation.cluster,
        cross_round_first_common_bias=cross_round_first_common_bias,
        generate_raw_fn=generate_raw_fn,
        parse_raw=parse_raw,
        fallback_fn=fallback_for_seed,
    )

    snippet = SnippetWithKey(
        code=generated.code,
        bug_summary=generated.bug_summary,
        bug_category=generated.bug_category,
        difficulty=generated.difficulty,
        hints=generated.hints,
        keywords=generated.keywords,
    )
    return GenerateBugResult(
        snippet=snippet,
        seed=generated.seed,
        degraded=degraded,
        attempts=attempts,
        freshness_rejects=rejects,
        parse_failures=parse_failures,
    )


def judge_answer(
    code: str,
    expected_summary: str,
    player_answer: str,
    settings: Settings,
) -> JudgeResult:
    """Judge a player answer via the configured provider (mock implemented)."""
    provider = _provider_name(settings)
    prompt = build_judge_prompt(
        code=code,
        expected_summary=expected_summary,
        player_answer=player_answer,
    )
    if provider == "mock":
        raw = _MOCK.judge_raw(prompt, settings)
        return parse_judge_payload(raw)

    if provider == "openai":
        from bugmiester.llm import openai_provider

        raw = openai_provider.judge_raw(prompt, settings)
        return parse_judge_payload(raw)
    if provider == "anthropic":
        from bugmiester.llm import anthropic_provider

        raw = anthropic_provider.judge_raw(prompt, settings)
        return parse_judge_payload(raw)
    if provider == "xai":
        from bugmiester.llm import xai_provider

        raw = xai_provider.judge_raw(prompt, settings)
        return parse_judge_payload(raw)

    raise ProviderNotImplementedError(
        f"Unknown llm.provider '{provider}'. Expected openai|anthropic|xai|mock."
    )


class RecoveryLlmError(RuntimeError):
    """Distractor generation failed or timed out."""


def _call_with_timeout(fn, timeout_seconds: int):
    import concurrent.futures

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(fn)
        return future.result(timeout=float(timeout_seconds))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def generate_recovery_distractors(
    *,
    code: str,
    expected_summary: str,
    player_answer: str,
    settings: Settings,
) -> list[str]:
    """
    One capped LLM call for wrong quiz answers.

    Raises RecoveryLlmError on skip, timeout, parse failure, or provider error.
    """
    needed = max(1, settings.recovery.choice_count - 1)
    if settings.recovery.max_llm_calls <= 0:
        raise RecoveryLlmError("recovery.max_llm_calls is 0")

    provider = _provider_name(settings)
    prompt = build_recovery_prompt(
        code=code,
        expected_summary=expected_summary,
        player_answer=player_answer,
        distractor_count=needed,
    )

    def _invoke() -> str:
        if provider == "mock":
            return _MOCK.recovery_raw(prompt, settings)
        if provider == "openai":
            from bugmiester.llm import openai_provider

            return openai_provider.recovery_raw(prompt, settings)
        if provider == "anthropic":
            from bugmiester.llm import anthropic_provider

            return anthropic_provider.recovery_raw(prompt, settings)
        if provider == "xai":
            from bugmiester.llm import xai_provider

            return xai_provider.recovery_raw(prompt, settings)
        raise ProviderNotImplementedError(
            f"Unknown llm.provider '{provider}'. Expected openai|anthropic|xai|mock."
        )

    try:
        raw = _call_with_timeout(_invoke, settings.recovery.timeout_seconds)
        return parse_recovery_payload(raw, needed=needed)
    except ProviderNotImplementedError:
        raise
    except Exception as exc:  # noqa: BLE001 — timeout, parse, provider
        raise RecoveryLlmError(str(exc) or "recovery distractors failed") from exc
