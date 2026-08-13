"""Unit tests for config loading and validation."""

from dataclasses import FrozenInstanceError

import pytest

from humanhand.infra.config import Config, load_config


class TestConfigDefaults:
    def test_cache_fields(self) -> None:
        config = Config()
        assert config.cache_dir == ".cache/humanhand"
        assert config.cache_enabled is True

    def test_file_io_fields(self) -> None:
        config = Config()
        assert config.max_chars == 200_000
        assert config.timeout_seconds == 30.0

    def test_detector_provider_default(self) -> None:
        config = Config()
        assert config.detector_provider == "local"

    def test_config_is_immutable_dataclass(self) -> None:
        config = Config(max_chars=1000)
        assert config.max_chars == 1000
        assert config.cache_enabled is True

        with pytest.raises(FrozenInstanceError):
            config.max_chars = 2000  # type: ignore[misc]


class TestLoadConfigCache:
    def test_cache_dir_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_CACHE_DIR", "/tmp/test-cache")
        config = load_config()
        assert config.cache_dir == "/tmp/test-cache"

    def test_cache_enabled_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_CACHE_ENABLED", "0")
        config = load_config()
        assert config.cache_enabled is False

    def test_cache_enabled_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_CACHE_ENABLED", "1")
        config = load_config()
        assert config.cache_enabled is True

    def test_cache_enabled_invalid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_CACHE_ENABLED", "maybe")
        with pytest.raises(ValueError, match="HUMANHAND_CACHE_ENABLED"):
            load_config()


class TestLoadConfigMaxChars:
    def test_max_chars_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_MAX_CHARS", "50000")
        config = load_config()
        assert config.max_chars == 50000
        assert isinstance(config.max_chars, int)

    def test_max_chars_invalid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_MAX_CHARS", "not-a-number")
        with pytest.raises(ValueError):
            load_config()

    def test_max_chars_must_be_positive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_MAX_CHARS", "0")
        with pytest.raises(ValueError, match="positive integer"):
            load_config()


class TestLoadConfigTimeout:
    def test_timeout_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_TIMEOUT_SECONDS", "60")
        config = load_config()
        assert config.timeout_seconds == 60.0

    def test_timeout_invalid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_TIMEOUT_SECONDS", "not-float")
        with pytest.raises(ValueError):
            load_config()

    def test_timeout_must_be_positive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_TIMEOUT_SECONDS", "-1")
        with pytest.raises(ValueError, match="positive number"):
            load_config()


class TestLoadConfigDetectorProvider:
    def test_known_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_DETECTOR_PROVIDER", "winston")
        config = load_config()
        assert config.detector_provider == "winston"

    def test_unknown_provider_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_DETECTOR_PROVIDER", "mystery-ai")
        with pytest.raises(ValueError, match="Unknown detector provider"):
            load_config()


class TestLoadConfigOptionalStrings:
    def test_empty_llm_values_become_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_LLM_BASE_URL", "")
        monkeypatch.setenv("HUMANHAND_LLM_API_KEY", "   ")
        monkeypatch.setenv("HUMANHAND_LLM_MODEL", "\t")
        config = load_config()
        assert config.llm_base_url is None
        assert config.llm_api_key is None
        assert config.llm_model is None


class TestLoadConfigImportLimits:
    def test_import_defaults(self) -> None:
        config = Config()
        assert config.import_max_bytes == 4_000_000
        assert config.import_max_expanded_bytes == 16_000_000
        assert config.import_max_nodes == 50_000
        assert config.import_timeout_seconds == 30.0

    def test_import_env_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_IMPORT_MAX_BYTES", "1000")
        monkeypatch.setenv("HUMANHAND_IMPORT_MAX_EXPANDED_BYTES", "4000")
        monkeypatch.setenv("HUMANHAND_IMPORT_MAX_NODES", "500")
        monkeypatch.setenv("HUMANHAND_IMPORT_TIMEOUT_SECONDS", "5")
        config = load_config()
        assert config.import_max_bytes == 1000
        assert config.import_max_expanded_bytes == 4000
        assert config.import_max_nodes == 500
        assert config.import_timeout_seconds == 5.0

    def test_import_max_bytes_must_be_positive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_IMPORT_MAX_BYTES", "0")
        with pytest.raises(ValueError, match="HUMANHAND_IMPORT_MAX_BYTES"):
            load_config()

    def test_import_expanded_must_cover_max_bytes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_IMPORT_MAX_BYTES", "10000")
        monkeypatch.setenv("HUMANHAND_IMPORT_MAX_EXPANDED_BYTES", "9999")
        with pytest.raises(ValueError, match="EXPANDED"):
            load_config()

    def test_import_nodes_must_be_positive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_IMPORT_MAX_NODES", "-3")
        with pytest.raises(ValueError, match="HUMANHAND_IMPORT_MAX_NODES"):
            load_config()

    def test_import_timeout_must_be_positive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_IMPORT_TIMEOUT_SECONDS", "0")
        with pytest.raises(ValueError, match="HUMANHAND_IMPORT_TIMEOUT_SECONDS"):
            load_config()

    def test_project_dir_default_and_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert Config().project_dir is None
        monkeypatch.setenv("HUMANHAND_PROJECT_DIR", "C:/work/my-project")
        assert load_config().project_dir == "C:/work/my-project"
        monkeypatch.setenv("HUMANHAND_PROJECT_DIR", "  ")
        assert load_config().project_dir is None
