"""Foundation unit tests."""

import pytest

import humanhand
from humanhand.infra.config import Config, load_config


class TestPackage:
    def test_version_is_string(self) -> None:
        assert isinstance(humanhand.__version__, str)
        assert len(humanhand.__version__) > 0

    def test_version_parseable(self) -> None:
        parts = humanhand.__version__.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)


class TestConfig:
    def test_defaults(self) -> None:
        config = Config()
        assert config.max_chars == 200_000
        assert config.timeout_seconds == 30.0
        assert config.detector_provider == "local"
        assert config.cache_enabled is True
        assert config.allow_insecure is False

    def test_config_is_dataclass(self) -> None:
        config = Config(max_chars=1000)
        assert config.max_chars == 1000
        assert config.timeout_seconds == 30.0


class TestLoadConfig:
    def test_load_config_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """load_config returns defaults with no env vars set."""
        for var in [
            "HUMANHAND_MAX_CHARS",
            "HUMANHAND_TIMEOUT_SECONDS",
            "HUMANHAND_CACHE_DIR",
            "HUMANHAND_CACHE_ENABLED",
            "HUMANHAND_DETECTOR_PROVIDER",
            "HUMANHAND_ALLOW_INSECURE",
            "HUMANHAND_SEED",
            "HUMANHAND_LLM_BASE_URL",
            "HUMANHAND_LLM_API_KEY",
            "HUMANHAND_LLM_MODEL",
        ]:
            monkeypatch.delenv(var, raising=False)

        config = load_config()
        assert config.max_chars == 200_000
        assert config.timeout_seconds == 30.0
        assert config.detector_provider == "local"

    def test_load_config_max_chars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_MAX_CHARS", "5000")
        config = load_config()
        assert config.max_chars == 5000

    def test_load_config_allow_insecure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_ALLOW_INSECURE", "1")
        config = load_config()
        assert config.allow_insecure is True

    def test_load_config_seed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_SEED", "42")
        config = load_config()
        assert config.seed == 42
