"""Configuration loading and validation."""

from __future__ import annotations

import os
from dataclasses import dataclass

TRUE_VALUES = {"1", "true", "yes"}
FALSE_VALUES = {"0", "false", "no"}
KNOWN_DETECTOR_PROVIDERS = {
    "local",
    "gptzero",
    "originality",
    "copyleaks",
    "winston",
    "turnitin",
}


@dataclass(frozen=True)
class Config:
    """Immutable configuration for a Human Hand command invocation."""

    max_chars: int = 200_000
    timeout_seconds: float = 30.0
    cache_dir: str = ".cache/humanhand"
    cache_enabled: bool = True
    detector_provider: str = "local"
    allow_insecure: bool = False
    seed: int | None = None
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None


def _parse_positive_int(raw: str | None, default: int, env_name: str) -> int:
    if raw is None:
        return default
    value = int(raw)
    if value <= 0:
        raise ValueError(f"{env_name} must be a positive integer")
    return value


def _parse_positive_float(raw: str | None, default: float, env_name: str) -> float:
    if raw is None:
        return default
    value = float(raw)
    if value <= 0:
        raise ValueError(f"{env_name} must be a positive number")
    return value


def _parse_bool(raw: str | None, default: bool, env_name: str) -> bool:
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"{env_name} must be a boolean-like value")


def _parse_detector_provider(raw: str | None) -> str:
    if raw is None:
        return "local"
    provider = raw.strip().lower()
    if provider not in KNOWN_DETECTOR_PROVIDERS:
        raise ValueError(f"Unknown detector provider: {raw}")
    return provider


def _parse_optional_string(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    return value if value else None


def load_config() -> Config:
    """Load and validate configuration from environment variables.

    Returns a Config dataclass. Does not log secrets.
    """
    max_chars = _parse_positive_int(
        os.getenv("HUMANHAND_MAX_CHARS"),
        200_000,
        "HUMANHAND_MAX_CHARS",
    )
    timeout_seconds = _parse_positive_float(
        os.getenv("HUMANHAND_TIMEOUT_SECONDS"),
        30.0,
        "HUMANHAND_TIMEOUT_SECONDS",
    )
    cache_enabled = _parse_bool(
        os.getenv("HUMANHAND_CACHE_ENABLED"),
        True,
        "HUMANHAND_CACHE_ENABLED",
    )
    allow_insecure = _parse_bool(
        os.getenv("HUMANHAND_ALLOW_INSECURE"),
        False,
        "HUMANHAND_ALLOW_INSECURE",
    )

    seed_str = os.getenv("HUMANHAND_SEED")
    seed = int(seed_str) if seed_str else None

    return Config(
        max_chars=max_chars,
        timeout_seconds=timeout_seconds,
        cache_dir=os.getenv("HUMANHAND_CACHE_DIR", ".cache/humanhand"),
        cache_enabled=cache_enabled,
        detector_provider=_parse_detector_provider(os.getenv("HUMANHAND_DETECTOR_PROVIDER")),
        allow_insecure=allow_insecure,
        seed=seed,
        llm_base_url=_parse_optional_string(os.getenv("HUMANHAND_LLM_BASE_URL")),
        llm_api_key=_parse_optional_string(os.getenv("HUMANHAND_LLM_API_KEY")),
        llm_model=_parse_optional_string(os.getenv("HUMANHAND_LLM_MODEL")),
    )
