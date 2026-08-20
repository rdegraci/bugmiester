"""Application Support paths, copy examples, load env/yaml."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml
from dotenv import dotenv_values, load_dotenv

from bugmiester.mix import DEFAULT_MIX, normalize_mix

PLACEHOLDER_KEY = "replace-me"

PROVIDER_ENV_KEYS: dict[str, str | None] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "xai": "XAI_API_KEY",
    "mock": None,
}

DEFAULT_REPORTS_DIR = "reports"
DEFAULT_LOGS_DIR = "logs"


def default_app_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "Bugmiester"


def default_examples_dir() -> Path:
    """Repo root (editable install / source checkout)."""
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class LlmSettings:
    provider: str = "openai"
    base_url: str | None = None
    model: str = "gpt-4o-mini"
    temperature: float = 0.4
    judge_temperature: float = 0.0
    timeout_seconds: int = 60


@dataclass(frozen=True)
class GameSettings:
    bugs_per_round: int = 10
    language: str = "swift"
    mix: str = "senior_mix"


@dataclass(frozen=True)
class ScoringSettings:
    mode: str = "hybrid"
    points_per_bug: int = 10
    partial_credit: bool = True
    generosity: str = "prefer_partial_on_low_confidence"


@dataclass(frozen=True)
class FreshnessSettings:
    avoid_list_max: int = 20
    similarity_reject_threshold: float = 0.72
    max_generate_attempts: int = 2
    max_category_repeats_per_round: int = 1
    shuffle_seeds: bool = True
    recent_seed_rounds: int = 3


@dataclass(frozen=True)
class ResilienceSettings:
    max_judge_calls_per_submit: int = 1
    use_canned_fallback_on_generate_exhaustion: bool = True
    prefetch_next_bug: bool = True


@dataclass(frozen=True)
class RecoverySettings:
    enabled: bool = True
    choice_count: int = 4
    timeout_seconds: int = 4
    max_llm_calls: int = 1
    use_seed_bank_fallback: bool = True


@dataclass(frozen=True)
class MetricsSettings:
    log_per_bug: bool = True
    log_dir_name: str = DEFAULT_LOGS_DIR


@dataclass(frozen=True)
class ReportsSettings:
    enabled: bool = True
    dir_name: str = DEFAULT_REPORTS_DIR


@dataclass(frozen=True)
class FeedbackSettings:
    analyze_on_ops_load: bool = True


@dataclass(frozen=True)
class ServerSettings:
    host: str = "127.0.0.1"
    port: int = 8765


@dataclass
class Settings:
    """Loaded Bugmiester settings plus Application Support paths."""

    app_dir: Path
    env_path: Path
    config_path: Path
    llm: LlmSettings = field(default_factory=LlmSettings)
    game: GameSettings = field(default_factory=GameSettings)
    scoring: ScoringSettings = field(default_factory=ScoringSettings)
    freshness: FreshnessSettings = field(default_factory=FreshnessSettings)
    resilience: ResilienceSettings = field(default_factory=ResilienceSettings)
    recovery: RecoverySettings = field(default_factory=RecoverySettings)
    metrics: MetricsSettings = field(default_factory=MetricsSettings)
    reports: ReportsSettings = field(default_factory=ReportsSettings)
    feedback: FeedbackSettings = field(default_factory=FeedbackSettings)
    server: ServerSettings = field(default_factory=ServerSettings)
    api_key: str | None = None
    missing_key: str | None = None
    config_ready: bool = False

    @property
    def reports_dir(self) -> Path:
        return self.app_dir / self.reports.dir_name

    @property
    def logs_dir(self) -> Path:
        return self.app_dir / self.metrics.log_dir_name


def _clamp_int(value: Any, *, lo: int, hi: int, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(lo, min(hi, parsed))


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _section(data: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    raw = data.get(name) or {}
    if not isinstance(raw, Mapping):
        raise ValueError(f"config.yaml section '{name}' must be a mapping")
    return raw


def _parse_yaml_config(raw: Mapping[str, Any]) -> dict[str, Any]:
    llm_raw = _section(raw, "llm")
    game_raw = _section(raw, "game")
    scoring_raw = _section(raw, "scoring")
    freshness_raw = _section(raw, "freshness")
    resilience_raw = _section(raw, "resilience")
    recovery_raw = _section(raw, "recovery")
    metrics_raw = _section(raw, "metrics")
    reports_raw = _section(raw, "reports")
    feedback_raw = _section(raw, "feedback")
    server_raw = _section(raw, "server")

    base_url = llm_raw.get("base_url", None)
    if base_url is not None:
        base_url = _as_optional_str(base_url)

    return {
        "llm": LlmSettings(
            provider=str(llm_raw.get("provider", "openai")).strip().lower(),
            base_url=base_url,
            model=str(llm_raw.get("model", "gpt-4o-mini")),
            temperature=float(llm_raw.get("temperature", 0.4)),
            judge_temperature=float(llm_raw.get("judge_temperature", 0.0)),
            timeout_seconds=int(llm_raw.get("timeout_seconds", 60)),
        ),
        "game": GameSettings(
            bugs_per_round=int(game_raw.get("bugs_per_round", 10)),
            language=str(game_raw.get("language", "swift")),
            mix=normalize_mix(game_raw.get("mix", DEFAULT_MIX)),
        ),
        "scoring": ScoringSettings(
            mode=str(scoring_raw.get("mode", "hybrid")),
            points_per_bug=int(scoring_raw.get("points_per_bug", 10)),
            partial_credit=bool(scoring_raw.get("partial_credit", True)),
            generosity=str(
                scoring_raw.get("generosity", "prefer_partial_on_low_confidence")
            ),
        ),
        "freshness": FreshnessSettings(
            avoid_list_max=int(freshness_raw.get("avoid_list_max", 20)),
            similarity_reject_threshold=float(
                freshness_raw.get("similarity_reject_threshold", 0.72)
            ),
            max_generate_attempts=int(freshness_raw.get("max_generate_attempts", 2)),
            max_category_repeats_per_round=_clamp_int(
                freshness_raw.get("max_category_repeats_per_round", 1),
                lo=1,
                hi=5,
                default=1,
            ),
            shuffle_seeds=bool(freshness_raw.get("shuffle_seeds", True)),
            recent_seed_rounds=_clamp_int(
                freshness_raw.get("recent_seed_rounds", 3),
                lo=0,
                hi=10,
                default=3,
            ),
        ),
        "resilience": ResilienceSettings(
            max_judge_calls_per_submit=int(
                resilience_raw.get("max_judge_calls_per_submit", 1)
            ),
            use_canned_fallback_on_generate_exhaustion=bool(
                resilience_raw.get("use_canned_fallback_on_generate_exhaustion", True)
            ),
            prefetch_next_bug=bool(resilience_raw.get("prefetch_next_bug", True)),
        ),
        "recovery": RecoverySettings(
            enabled=bool(recovery_raw.get("enabled", True)),
            choice_count=_clamp_int(
                recovery_raw.get("choice_count", 4), lo=3, hi=5, default=4
            ),
            timeout_seconds=_clamp_int(
                recovery_raw.get("timeout_seconds", 4), lo=1, hi=15, default=4
            ),
            max_llm_calls=_clamp_int(
                recovery_raw.get("max_llm_calls", 1), lo=0, hi=1, default=1
            ),
            use_seed_bank_fallback=bool(
                recovery_raw.get("use_seed_bank_fallback", True)
            ),
        ),
        "metrics": MetricsSettings(
            log_per_bug=bool(metrics_raw.get("log_per_bug", True)),
            log_dir_name=str(metrics_raw.get("log_dir_name", DEFAULT_LOGS_DIR)),
        ),
        "reports": ReportsSettings(
            enabled=bool(reports_raw.get("enabled", True)),
            dir_name=str(reports_raw.get("dir_name", DEFAULT_REPORTS_DIR)),
        ),
        "feedback": FeedbackSettings(
            analyze_on_ops_load=bool(feedback_raw.get("analyze_on_ops_load", True)),
        ),
        "server": ServerSettings(
            host=str(server_raw.get("host", "127.0.0.1")),
            port=int(server_raw.get("port", 8765)),
        ),
    }


def _is_usable_key(value: str | None) -> bool:
    if value is None:
        return False
    stripped = value.strip()
    if not stripped:
        return False
    if stripped.lower() == PLACEHOLDER_KEY:
        return False
    return True


def resolve_provider_key(
    provider: str,
    env_values: Mapping[str, str | None] | None = None,
) -> tuple[str | None, str | None, bool]:
    """
    Return (api_key, missing_key_name, config_ready).

    mock is always ready. Other providers need a non-placeholder env value.
    """
    name = provider.strip().lower()
    if name not in PROVIDER_ENV_KEYS:
        raise ValueError(
            f"Unknown llm.provider '{provider}'. "
            f"Expected one of: {', '.join(sorted(PROVIDER_ENV_KEYS))}"
        )

    env_key = PROVIDER_ENV_KEYS[name]
    if env_key is None:
        return None, None, True

    values = env_values if env_values is not None else os.environ
    raw = values.get(env_key)
    if isinstance(raw, str):
        key = raw
    elif raw is None:
        key = None
    else:
        key = str(raw)

    if _is_usable_key(key):
        return key.strip(), None, True
    return None, env_key, False


def ensure_app_dir(
    app_dir: Path | None = None,
    examples_dir: Path | None = None,
    *,
    reports_dir_name: str = DEFAULT_REPORTS_DIR,
    logs_dir_name: str = DEFAULT_LOGS_DIR,
) -> Path:
    """
    Create Application Support app dir, reports/, logs/, and example copies if missing.
    """
    root = Path(app_dir) if app_dir is not None else default_app_dir()
    examples = Path(examples_dir) if examples_dir is not None else default_examples_dir()

    root.mkdir(parents=True, exist_ok=True)
    (root / reports_dir_name).mkdir(parents=True, exist_ok=True)
    (root / logs_dir_name).mkdir(parents=True, exist_ok=True)

    env_path = root / ".env"
    config_path = root / "config.yaml"
    example_env = examples / ".env.example"
    example_config = examples / "config.yaml.example"

    if not env_path.exists():
        if not example_env.is_file():
            raise FileNotFoundError(f"Missing example env file: {example_env}")
        shutil.copyfile(example_env, env_path)

    if not config_path.exists():
        if not example_config.is_file():
            raise FileNotFoundError(f"Missing example config file: {example_config}")
        shutil.copyfile(example_config, config_path)

    return root


def load_settings(
    app_dir: Path | None = None,
    examples_dir: Path | None = None,
    *,
    load_env_into_process: bool = True,
) -> Settings:
    """
    Ensure Application Support files exist, then load .env + config.yaml.
    """
    root = ensure_app_dir(app_dir=app_dir, examples_dir=examples_dir)
    env_path = root / ".env"
    config_path = root / "config.yaml"

    if load_env_into_process:
        load_dotenv(env_path, override=False)

    file_env = dotenv_values(env_path)
    # Prefer values from the app .env file; fall back to process env.
    merged: dict[str, str | None] = dict(os.environ)
    for key, value in file_env.items():
        if value is not None:
            merged[key] = value

    with config_path.open(encoding="utf-8") as handle:
        raw_yaml = yaml.safe_load(handle) or {}
    if not isinstance(raw_yaml, Mapping):
        raise ValueError(f"config.yaml must be a mapping: {config_path}")

    parsed = _parse_yaml_config(raw_yaml)
    llm: LlmSettings = parsed["llm"]
    metrics: MetricsSettings = parsed["metrics"]
    reports: ReportsSettings = parsed["reports"]

    # Reconcile configured subdir names (create if yaml uses non-defaults).
    (root / reports.dir_name).mkdir(parents=True, exist_ok=True)
    (root / metrics.log_dir_name).mkdir(parents=True, exist_ok=True)

    api_key, missing_key, config_ready = resolve_provider_key(llm.provider, merged)

    return Settings(
        app_dir=root,
        env_path=env_path,
        config_path=config_path,
        llm=llm,
        game=parsed["game"],
        scoring=parsed["scoring"],
        freshness=parsed["freshness"],
        resilience=parsed["resilience"],
        recovery=parsed["recovery"],
        metrics=metrics,
        reports=reports,
        feedback=parsed["feedback"],
        server=parsed["server"],
        api_key=api_key,
        missing_key=missing_key,
        config_ready=config_ready,
    )
