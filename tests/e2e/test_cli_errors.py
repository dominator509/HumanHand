"""E2E tests for CLI error states, messages, and exit codes."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from humanhand.cli.app import EXIT_CONFIG_ERROR, EXIT_IO_ERROR, app

runner = CliRunner()


# ── Fixtures ────────────────────────────────────────────────────


@pytest.fixture
def source_file() -> str:
    """Create a temporary source text file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(
            "The Eiffel Tower is 330 meters tall. "
            "It was completed in 1889 and receives 7 million visitors annually.\n"
        )
    return f.name


@pytest.fixture
def style_file() -> str:
    """Create a temporary style sample file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(
            "I went to the store yesterday. The prices were quite reasonable. "
            "I bought some bread and cheese for dinner.\n"
        )
    return f.name


@pytest.fixture
def output_file() -> str:
    """Create a temporary output file with text for verification."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(
            "The Eiffel Tower is 330 meters tall and was completed in 1889. "
            "It receives approximately 7 million visitors annually. "
            "The tower is one of the most recognizable landmarks in the world.\n"
        )
    return f.name


# ── File errors ─────────────────────────────────────────────────


class TestFileErrors:
    """Errors related to file content and availability."""

    def test_empty_source_file_error(self, tmp_path: Path) -> None:
        """Empty source file produces a clear error message."""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")
        result = runner.invoke(app, ["scrub", str(empty_file), "--audit"])
        assert result.exit_code != 0
        assert "empty" in result.stderr.lower()

    def test_missing_file_error_message(self) -> None:
        """Missing file produces 'File not found' error."""
        result = runner.invoke(app, ["verify", "definitely_missing_file.txt"])
        assert result.exit_code != 0
        assert "File not found" in result.stderr

    def test_missing_style_file_error(self, source_file: str) -> None:
        """Rewrite with missing style file produces error."""
        result = runner.invoke(
            app,
            [
                "rewrite",
                "--source",
                source_file,
                "--style",
                "nonexistent_style_file.txt",
                "--out",
                "out_style_error.txt",
            ],
        )
        assert result.exit_code != 0
        assert "File not found" in result.stderr

    def test_missing_source_file_error(self, style_file: str) -> None:
        """Rewrite with missing source file produces error."""
        result = runner.invoke(
            app,
            [
                "rewrite",
                "--source",
                "nonexistent_source_file.txt",
                "--style",
                style_file,
                "--out",
                "out_source_error.txt",
            ],
        )
        assert result.exit_code != 0
        assert "File not found" in result.stderr

    def test_bom_file_rejected_with_clear_message(self, tmp_path: Path) -> None:
        """BOM file is rejected with clear error message."""
        bom_file = tmp_path / "bom.txt"
        bom_file.write_bytes(b"\xef\xbb\xbfHello world.\n")
        result = runner.invoke(app, ["scrub", str(bom_file), "--audit"])
        assert result.exit_code != 0
        assert "BOM" in result.stderr

    def test_whitespace_only_file_error(self, tmp_path: Path) -> None:
        """Whitespace-only file produces a clear error message."""
        ws_file = tmp_path / "whitespace_only.txt"
        ws_file.write_text("   \n\t\n  \n")
        result = runner.invoke(app, ["scrub", str(ws_file), "--audit"])
        assert result.exit_code != 0
        assert "empty" in result.stderr.lower() or "whitespace" in result.stderr.lower()

    def test_rewrite_empty_source_caught_by_strict_read(self, tmp_path: Path) -> None:
        """Rewrite with empty source file is caught before LLM call."""
        empty_file = tmp_path / "empty_rewrite_source.txt"
        empty_file.write_text("")
        result = runner.invoke(
            app,
            [
                "rewrite",
                "--source",
                str(empty_file),
                "--style",
                str(empty_file),
                "--out",
                "out_empty_rewrite.txt",
            ],
        )
        assert result.exit_code != 0
        assert "empty" in result.stderr.lower()


# ── Provider errors ──────────────────────────────────────────────


class TestProviderErrors:
    """Errors related to detector/LLM providers."""

    def test_unknown_provider_error_message(self, output_file: str) -> None:
        """Unknown provider produces an error message."""
        result = runner.invoke(app, ["verify", output_file, "--provider", "nonexistent_provider"])
        assert result.exit_code != 0
        assert "provider" in result.stderr.lower() or "Provider" in result.stderr

    def test_unknown_provider_exit_code(self, output_file: str) -> None:
        """Unknown provider exits with config error code."""
        result = runner.invoke(app, ["verify", output_file, "--provider", "bogus_provider"])
        assert result.exit_code == EXIT_CONFIG_ERROR

    def test_stub_provider_unavailable_has_message(self, output_file: str) -> None:
        """Stub provider without API key produces error message."""
        result = runner.invoke(app, ["verify", output_file, "--provider", "gptzero"])
        assert result.exit_code != 0
        assert len(result.stderr) > 0


# ── Error format hygiene ─────────────────────────────────────────


class TestErrorFormat:
    """Error output format: no stack traces, no system paths, correct streams."""

    def test_error_exit_codes_are_nonzero(self) -> None:
        """Error states produce nonzero exit codes."""
        result = runner.invoke(app, ["verify", "nonexistent_exit_check.txt"])
        assert result.exit_code != 0

    def test_missing_file_exit_code(self) -> None:
        """Missing file exits with I/O error code."""
        result = runner.invoke(app, ["verify", "nonexistent_io_error.txt"])
        assert result.exit_code == EXIT_IO_ERROR

    def test_missing_argument_exit_code(self) -> None:
        """Missing required argument produces nonzero exit code."""
        result = runner.invoke(app, ["verify"])
        assert result.exit_code != 0

    def test_error_messages_no_stack_traces(self) -> None:
        """Error messages do not contain stack traces."""
        result = runner.invoke(app, ["verify", "nonexistent_no_traceback.txt"])
        assert result.exit_code != 0
        assert "Traceback" not in result.stderr
        assert "Traceback" not in result.stdout

    def test_error_messages_no_stack_traces_bom(self, tmp_path: Path) -> None:
        """BOM file error messages do not contain stack traces."""
        bom_file = tmp_path / "bom_no_traceback.txt"
        bom_file.write_bytes(b"\xef\xbb\xbfTest data.\n")
        result = runner.invoke(app, ["scrub", str(bom_file), "--audit"])
        assert result.exit_code != 0
        assert "Traceback" not in result.stderr
        assert "Traceback" not in result.stdout

    def test_error_messages_no_system_paths_in_stderr(self) -> None:
        """Error messages on stderr do not contain raw system paths."""
        result = runner.invoke(app, ["verify", "missing_no_path.txt"])
        assert result.exit_code != 0
        assert "C:\\" not in result.stderr
        assert "/home/" not in result.stderr
        assert "/Users/" not in result.stderr

    def test_error_messages_no_system_paths_in_stdout(self) -> None:
        """Error messages on stdout do not contain raw system paths."""
        result = runner.invoke(app, ["verify", "missing_no_path_json.txt", "--json"])
        assert result.exit_code != 0
        assert "C:\\" not in result.stdout
        assert "/home/" not in result.stdout
        assert "/Users/" not in result.stdout

    def test_error_messages_no_system_paths_bom(self, tmp_path: Path) -> None:
        """BOM file error messages do not contain raw system paths."""
        bom_file = tmp_path / "bom_no_path.txt"
        bom_file.write_bytes(b"\xef\xbb\xbfData.\n")
        result = runner.invoke(app, ["scrub", str(bom_file), "--audit"])
        assert result.exit_code != 0
        assert "C:\\" not in result.stderr
        assert "/home/" not in result.stderr

    def test_json_error_mode_produces_valid_json(self) -> None:
        """JSON error mode produces valid JSON with message."""
        result = runner.invoke(app, ["verify", "nonexistent_json_error.txt", "--json"])
        assert result.exit_code != 0
        data = json.loads(result.stdout)
        assert "status" in data
        assert "message" in data
        assert "exit_code" in data

    def test_json_error_message_has_no_traceback(self) -> None:
        """JSON error message does not contain stack trace."""
        result = runner.invoke(app, ["verify", "nonexistent_json_tb.txt", "--json"])
        assert result.exit_code != 0
        data = json.loads(result.stdout)
        assert "Traceback" not in data["message"]

    def test_json_error_exit_code_matches_cli_code(self) -> None:
        """JSON error exit_code matches CLI return code for missing file."""
        result = runner.invoke(app, ["verify", "nonexistent_exit_match.txt", "--json"])
        assert result.exit_code != 0
        data = json.loads(result.stdout)
        assert data["exit_code"] == result.exit_code

    def test_text_error_mode_goes_to_stderr(self) -> None:
        """Text mode error messages go to stderr, not stdout."""
        result = runner.invoke(app, ["verify", "nonexistent_stderr_test.txt"])
        assert result.exit_code != 0
        assert "error:" in result.stderr
        # stdout should not contain the error message
        assert "File not found" not in result.stdout
        assert "error:" not in result.stdout

    def test_text_error_contains_error_prefix(self) -> None:
        """Text mode error messages contain 'error:' on stderr."""
        result = runner.invoke(app, ["verify", "nonexistent_prefix_test.txt"])
        assert result.exit_code != 0
        assert "error:" in result.stderr


# ── Config errors ────────────────────────────────────────────────


class TestConfigErrors:
    """Errors related to configuration."""

    def test_config_error_invalid_detector_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid detector provider in env var produces config error."""
        monkeypatch.setenv("HUMANHAND_DETECTOR_PROVIDER", "invalid_provider_name")
        result = runner.invoke(app, ["verify", "dummy_path_for_config_test.txt"])
        assert result.exit_code != 0
        assert "Unknown" in result.stderr or "provider" in result.stderr.lower()

    def test_config_error_exit_code(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid config exits with config error code."""
        monkeypatch.setenv("HUMANHAND_DETECTOR_PROVIDER", "bogus_provider_name")
        result = runner.invoke(app, ["verify", "dummy_path_exit_code.txt"])
        assert result.exit_code == EXIT_CONFIG_ERROR

    def test_config_error_json_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid config in JSON mode produces valid JSON error."""
        monkeypatch.setenv("HUMANHAND_DETECTOR_PROVIDER", "not_a_real_provider")
        result = runner.invoke(app, ["verify", "dummy_json_config.txt", "--json"])
        assert result.exit_code != 0
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "message" in data
        assert data["exit_code"] == EXIT_CONFIG_ERROR

    def test_health_handles_invalid_config_gracefully(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Health command handles invalid config gracefully (no crash)."""
        monkeypatch.setenv("HUMANHAND_DETECTOR_PROVIDER", "invalid_for_health_test")
        result = runner.invoke(app, ["health", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["config_valid"] is False
        assert data["config_error"] is not None


# ── Argument errors ──────────────────────────────────────────────


class TestArgumentErrors:
    """Errors from missing or invalid arguments."""

    def test_missing_verify_argument(self) -> None:
        """Missing verify argument produces error."""
        result = runner.invoke(app, ["verify"])
        assert result.exit_code != 0

    def test_missing_diff_facts_arguments(self) -> None:
        """Missing diff-facts arguments produces error."""
        result = runner.invoke(app, ["diff-facts"])
        assert result.exit_code != 0

    def test_missing_diff_facts_second_argument(self, source_file: str) -> None:
        """Missing second diff-facts argument produces error."""
        result = runner.invoke(app, ["diff-facts", source_file])
        assert result.exit_code != 0

    def test_missing_scrub_argument(self) -> None:
        """Missing scrub argument produces error."""
        result = runner.invoke(app, ["scrub"])
        assert result.exit_code != 0

    def test_missing_rewrite_options(self) -> None:
        """Missing rewrite options produces error."""
        result = runner.invoke(app, ["rewrite"])
        assert result.exit_code != 0

    def test_unknown_command(self) -> None:
        """Unknown command produces nonzero exit code."""
        result = runner.invoke(app, ["nonexistent_command"])
        assert result.exit_code != 0
