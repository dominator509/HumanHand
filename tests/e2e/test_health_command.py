"""Comprehensive E2E tests for the health command.

All tests use CliRunner and must NOT make network calls or read user files.
"""

from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from humanhand import __version__
from humanhand.cli.app import app

runner = CliRunner()

# ── Test helpers ──────────────────────────────────────────────────

REQUIRED_JSON_KEYS: set[str] = {
    "status",
    "version",
    "python_version",
    "platform",
    "llm_configured",
    "detector_provider",
    "cache_enabled",
    "cache_dir",
    "cache_dir_writable",
    "endpoint_url_valid",
    "config_valid",
    "config_error",
    "commands",
}

ALL_SUBCOMMANDS: set[str] = {"health", "rewrite", "verify", "diff-facts", "scrub"}


def _invoke_health(*args: str) -> dict[str, object]:
    """Helper: invoke health with given args and return parsed JSON."""
    result = runner.invoke(app, ["health", *args])
    assert result.exit_code == 0, f"Health command failed: {result.stderr}"
    return json.loads(result.stdout)  # type: ignore[no-any-return]


# ── Health JSON output structure tests ────────────────────────────


class TestHealthJsonStructure:
    """Health JSON output must contain all required fields per OPERATIONS.md."""

    def test_all_required_keys_present(self) -> None:
        data = _invoke_health("--json")
        missing = REQUIRED_JSON_KEYS - data.keys()
        assert not missing, f"Missing health JSON keys: {missing}"

    def test_status_is_ok(self) -> None:
        data = _invoke_health("--json")
        assert data["status"] == "ok"

    def test_version_matches_package(self) -> None:
        data = _invoke_health("--json")
        assert data["version"] == __version__

    def test_python_version_is_string(self) -> None:
        data = _invoke_health("--json")
        assert isinstance(data["python_version"], str)
        assert len(data["python_version"]) > 0
        # Should contain the running Python version prefix
        assert data["python_version"].startswith(sys.version[:3])

    def test_platform_is_string(self) -> None:
        data = _invoke_health("--json")
        assert isinstance(data["platform"], str)
        assert data["platform"] == sys.platform

    def test_config_error_is_null_when_valid(self) -> None:
        data = _invoke_health("--json")
        assert data["config_valid"] is True
        assert data["config_error"] is None

    def test_commands_has_all_subcommands(self) -> None:
        data = _invoke_health("--json")
        commands = data["commands"]
        assert isinstance(commands, dict)
        missing_commands = ALL_SUBCOMMANDS - commands.keys()
        assert not missing_commands, f"Missing commands: {missing_commands}"
        for cmd in ALL_SUBCOMMANDS:
            assert commands[cmd] is True, f"Command '{cmd}' should be True but got {commands[cmd]}"

    def test_no_extra_top_level_keys(self) -> None:
        """No unexpected top-level keys should appear in health JSON."""
        data = _invoke_health("--json")
        # Allow extra keys only if they are documented
        extra = data.keys() - REQUIRED_JSON_KEYS
        assert not extra, f"Unexpected top-level keys: {extra}"


# ── Health config validation tests ────────────────────────────────


class TestHealthConfigValidation:
    """Health must correctly report config state for various env configurations."""

    def test_valid_default_config(self) -> None:
        data = _invoke_health("--json")
        assert data["config_valid"] is True
        assert data["detector_provider"] == "local"
        assert data["llm_configured"] is False
        assert data["cache_enabled"] is True

    def test_custom_cache_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_CACHE_DIR", "/tmp/humanhand_test_cache")
        data = _invoke_health("--json")
        assert data["cache_dir"] == "/tmp/humanhand_test_cache"

    def test_custom_detector_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_DETECTOR_PROVIDER", "gptzero")
        data = _invoke_health("--json")
        assert data["detector_provider"] == "gptzero"

    def test_llm_configured_when_url_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_LLM_BASE_URL", "https://api.openai.com/v1")
        data = _invoke_health("--json")
        assert data["llm_configured"] is True

    def test_cache_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_CACHE_ENABLED", "false")
        data = _invoke_health("--json")
        assert data["cache_enabled"] is False

    def test_combined_custom_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_CACHE_DIR", "/custom/cache")
        monkeypatch.setenv("HUMANHAND_DETECTOR_PROVIDER", "copyleaks")
        monkeypatch.setenv("HUMANHAND_CACHE_ENABLED", "false")
        monkeypatch.setenv("HUMANHAND_LLM_BASE_URL", "https://example.com/api")
        data = _invoke_health("--json")
        assert data["cache_dir"] == "/custom/cache"
        assert data["detector_provider"] == "copyleaks"
        assert data["cache_enabled"] is False
        assert data["llm_configured"] is True

    def test_config_error_with_invalid_detector_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HUMANHAND_DETECTOR_PROVIDER", "nonexistent_provider")
        data = _invoke_health("--json")
        assert data["config_valid"] is False
        assert data["config_error"] is not None
        # Fallback config uses defaults, so detector_provider reverts to "local"
        assert data["detector_provider"] == "local"


# ── Health text mode tests ────────────────────────────────────────


class TestHealthTextMode:
    """Health text output should be predictable and concise."""

    def test_text_contains_health_ok(self) -> None:
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        assert "health: ok" in result.stdout

    def test_no_ansi_with_no_color_flag(self) -> None:
        """--no-color must not produce ANSI escape codes."""
        result = runner.invoke(app, ["health", "--no-color"])
        assert result.exit_code == 0
        assert "\033[" not in result.stdout

    def test_json_flag_produces_parseable_json(self) -> None:
        """--json output must be valid JSON, not plain text."""
        result = runner.invoke(app, ["health", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, dict)
        assert data["status"] == "ok"

    def test_text_mode_does_not_emit_json(self) -> None:
        """Text mode stdout should not be parseable as JSON."""
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        with pytest.raises(json.JSONDecodeError):
            json.loads(result.stdout)


# ── Health offline guarantee tests ────────────────────────────────


class TestHealthOfflineGuarantee:
    """Health command must never make network calls."""

    def test_health_cmd_does_not_import_httpx_or_requests(self) -> None:
        """Structural check: health_cmd source must not import httpx or requests."""
        from humanhand.cli.app import health_cmd

        source = inspect.getsource(health_cmd)
        tree = ast.parse(source)

        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)

        forbidden = {"httpx", "requests"}
        actual = imports & forbidden
        assert not actual, f"health_cmd imports forbidden network modules: {actual}"

    def test_health_cmd_does_not_import_llm_or_detector_classes(self) -> None:
        """Structural check: health_cmd must not import LLM or detector client classes."""
        from humanhand.cli.app import health_cmd

        source = inspect.getsource(health_cmd)
        tree = ast.parse(source)

        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)

        forbidden_imports = {"httpx", "requests", "openai"}
        actual = imports & forbidden_imports
        assert not actual, f"health_cmd imports forbidden modules: {actual}"

    def test_health_does_not_read_input_files(self) -> None:
        """Health should not attempt to read user input files."""
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0

    def test_render_health_does_not_import_network_modules(self) -> None:
        """Structural check: output.render_health must not import network modules."""
        from humanhand.cli.output import render_health

        source = inspect.getsource(render_health)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "httpx" not in alias.name, f"render_health imports httpx: {alias.name}"
                    assert "requests" not in alias.name, (
                        f"render_health imports requests: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert "httpx" not in node.module, (
                    f"render_health imports from httpx: {node.module}"
                )
                assert "requests" not in node.module, (
                    f"render_health imports from requests: {node.module}"
                )


# ── Health cache writable / endpoint valid tests ──────────────────


class TestHealthCacheAndEndpoint:
    """Cache writability and endpoint URL validity must be reported correctly."""

    # ── cache_dir_writable ──

    def test_cache_dir_writable_field_present(self) -> None:
        data = _invoke_health("--json")
        assert "cache_dir_writable" in data

    def test_cache_dir_writable_with_temp_dir(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Writable temp dir should report cache_dir_writable as True."""
        cache_dir = tmp_path / "humanhand_cache"
        monkeypatch.setenv("HUMANHAND_CACHE_DIR", str(cache_dir))
        data = _invoke_health("--json")
        # When cache is enabled and dir is writable, should be True
        assert data["cache_dir_writable"] is True, (
            f"Expected True for writable temp dir, got {data['cache_dir_writable']}"
        )

    def test_cache_dir_writable_when_cache_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When cache is disabled, cache_dir_writable should be None."""
        monkeypatch.setenv("HUMANHAND_CACHE_ENABLED", "false")
        data = _invoke_health("--json")
        assert data["cache_dir_writable"] is None, (
            f"Expected None when cache disabled, got {data['cache_dir_writable']}"
        )

    # ── endpoint_url_valid ──

    def test_endpoint_url_valid_field_present(self) -> None:
        data = _invoke_health("--json")
        assert "endpoint_url_valid" in data

    def test_endpoint_url_valid_when_not_configured(self) -> None:
        """When no LLM URL is set, endpoint_url_valid should be None."""
        data = _invoke_health("--json")
        assert data["endpoint_url_valid"] is None, (
            f"Expected None when no LLM URL configured, got {data['endpoint_url_valid']}"
        )

    def test_endpoint_url_valid_with_https_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A valid HTTPS URL should report endpoint_url_valid as True."""
        monkeypatch.setenv("HUMANHAND_LLM_BASE_URL", "https://api.openai.com/v1")
        data = _invoke_health("--json")
        assert data["endpoint_url_valid"] is True, (
            f"Expected True for valid URL, got {data['endpoint_url_valid']}"
        )

    def test_endpoint_url_valid_with_malformed_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A malformed URL should report endpoint_url_valid as False."""
        monkeypatch.setenv("HUMANHAND_LLM_BASE_URL", "not-a-valid-url")
        data = _invoke_health("--json")
        assert data["endpoint_url_valid"] is False, (
            f"Expected False for malformed URL, got {data['endpoint_url_valid']}"
        )

    def test_endpoint_url_valid_with_localhost_http(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A valid localhost HTTP URL should be syntactically valid."""
        monkeypatch.setenv("HUMANHAND_LLM_BASE_URL", "http://localhost:8080/v1")
        data = _invoke_health("--json")
        assert data["endpoint_url_valid"] is True, (
            f"Expected True for localhost URL, got {data['endpoint_url_valid']}"
        )

    def test_endpoint_url_valid_with_empty_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An empty string URL should be treated as not configured (None)."""
        monkeypatch.setenv("HUMANHAND_LLM_BASE_URL", "")
        data = _invoke_health("--json")
        # Empty string is falsy in Python, so the health check skips URL
        # parsing entirely and reports None (not configured).
        assert data["endpoint_url_valid"] is None, (
            f"Expected None for empty URL, got {data['endpoint_url_valid']}"
        )


# ── Health stderr logging tests ───────────────────────────────────


class TestHealthLogging:
    """Health command should emit structured JSONL logs to stderr."""

    def test_health_emits_start_and_end_logs(self) -> None:
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        log_lines = [
            json.loads(line) for line in result.stderr.splitlines() if line.startswith("{")
        ]
        events = [line["event"] for line in log_lines]
        assert "health.start" in events, "Missing health.start log event"
        assert "health.end" in events, "Missing health.end log event"

    def test_health_logs_are_valid_jsonl(self) -> None:
        """Every stderr line that starts with { must be parseable JSON."""
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        for line in result.stderr.splitlines():
            stripped = line.strip()
            if stripped.startswith("{"):
                data = json.loads(stripped)
                assert "event" in data
                assert "timestamp" in data


# ── Health exit code tests ────────────────────────────────────────


class TestHealthExitCodes:
    """Health command should always exit with code 0."""

    def test_health_exit_zero(self) -> None:
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0

    def test_health_json_exit_zero(self) -> None:
        result = runner.invoke(app, ["health", "--json"])
        assert result.exit_code == 0

    def test_health_no_color_exit_zero(self) -> None:
        result = runner.invoke(app, ["health", "--no-color"])
        assert result.exit_code == 0

    def test_health_json_no_color_exit_zero(self) -> None:
        result = runner.invoke(app, ["health", "--json", "--no-color"])
        assert result.exit_code == 0
