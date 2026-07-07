"""E2E tests for CLI error states, messages, and exit codes."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from humanhand.application.services import RewriteQualityError
from humanhand.cli.app import EXIT_CONFIG_ERROR, EXIT_INPUT_ERROR, EXIT_IO_ERROR, app
from humanhand.cli.errors import (
    ERROR_MESSAGES,
    error_for_exception,
    get_error_message,
    message_for_exception,
)
from humanhand.infra.detectors.base import DetectorError, ProviderUnavailableError
from humanhand.infra.files import FileIOError
from humanhand.infra.llm import LlmError

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
        assert "whitespace" in result.stderr.lower() or "empty" in result.stderr.lower()

    def test_missing_file_error_message(self) -> None:
        """Missing file produces 'File not found' error."""
        result = runner.invoke(app, ["verify", "definitely_missing_file.txt"])
        assert result.exit_code != 0
        assert "File not found" in result.stderr

    def test_absolute_missing_file_path_is_sanitized(self, tmp_path: Path) -> None:
        """Absolute missing paths do not leak into user-facing error text."""
        missing_path = tmp_path / "missing_absolute.txt"
        result = runner.invoke(app, ["verify", str(missing_path)])
        assert result.exit_code != 0
        assert result.stderr.rstrip().endswith("error: File not found")
        assert str(missing_path) not in result.stderr

    def test_missing_style_file_error(
        self, source_file: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Rewrite with missing style file produces error."""
        monkeypatch.setenv("HUMANHAND_LLM_BASE_URL", "https://example.com/v1")
        monkeypatch.setenv("HUMANHAND_LLM_MODEL", "example-model")
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

    def test_missing_style_file_error_precedes_llm_config(self, source_file: str) -> None:
        """Rewrite surfaces style path errors before missing LLM config."""
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
        assert result.exit_code == EXIT_IO_ERROR
        assert result.stderr.rstrip().endswith("error: File not found")

    def test_missing_source_file_error(
        self, style_file: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Rewrite with missing source file produces error."""
        monkeypatch.setenv("HUMANHAND_LLM_BASE_URL", "https://example.com/v1")
        monkeypatch.setenv("HUMANHAND_LLM_MODEL", "example-model")
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

    def test_missing_source_file_error_precedes_llm_config(self, style_file: str) -> None:
        """Rewrite surfaces source path errors before missing LLM config."""
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
        assert result.exit_code == EXIT_IO_ERROR
        assert result.stderr.rstrip().endswith("error: File not found")

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

    def test_rewrite_empty_source_caught_by_strict_read(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Rewrite with empty source file is caught before LLM call."""
        monkeypatch.setenv("HUMANHAND_LLM_BASE_URL", "https://example.com/v1")
        monkeypatch.setenv("HUMANHAND_LLM_MODEL", "example-model")
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
        assert "whitespace" in result.stderr.lower() or "empty" in result.stderr.lower()

    def test_rewrite_rejects_output_path_matching_source(
        self, source_file: str, style_file: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Rewrite rejects output paths that match an input file."""
        monkeypatch.setenv("HUMANHAND_LLM_BASE_URL", "https://example.com/v1")
        monkeypatch.setenv("HUMANHAND_LLM_MODEL", "example-model")
        result = runner.invoke(
            app,
            [
                "rewrite",
                "--source",
                source_file,
                "--style",
                style_file,
                "--out",
                source_file,
            ],
        )
        assert result.exit_code == EXIT_IO_ERROR
        assert result.stderr.rstrip().endswith("error: Output path must not match any input path")

    def test_rewrite_output_path_error_precedes_llm_config(
        self, source_file: str, style_file: str
    ) -> None:
        """Rewrite surfaces output/input path overlap before missing LLM config."""
        result = runner.invoke(
            app,
            [
                "rewrite",
                "--source",
                source_file,
                "--style",
                style_file,
                "--out",
                source_file,
            ],
        )
        assert result.exit_code == EXIT_IO_ERROR
        assert result.stderr.rstrip().endswith("error: Output path must not match any input path")

    def test_scrub_rejects_output_path_matching_input(self, output_file: str) -> None:
        """Scrub rejects writing back to the input path."""
        result = runner.invoke(app, ["scrub", output_file, "--out", output_file])
        assert result.exit_code == EXIT_IO_ERROR
        assert result.stderr.rstrip().endswith("error: Output path must not match any input path")

    def test_invalid_utf8_file_error(self, tmp_path: Path) -> None:
        """Invalid UTF-8 file produces a clear error message."""
        bad_file = tmp_path / "bad_utf8.txt"
        bad_file.write_bytes(b"\xff\xfe\x00\x00")
        result = runner.invoke(app, ["scrub", str(bad_file), "--audit"])
        assert result.exit_code != 0
        assert "invalid utf-8" in result.stderr.lower() or "UTF-8" in result.stderr

    def test_directory_not_a_file_error(self, tmp_path: Path) -> None:
        """Directory path passed as file produces a clear error message."""
        result = runner.invoke(app, ["verify", str(tmp_path)])
        assert result.exit_code != 0
        assert "not a regular file" in result.stderr.lower()


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

    def test_json_error_message_is_sanitized_for_absolute_paths(self, tmp_path: Path) -> None:
        """JSON error messages do not include absolute file paths."""
        missing_path = tmp_path / "missing_absolute_json.txt"
        result = runner.invoke(app, ["verify", str(missing_path), "--json"])
        assert result.exit_code != 0
        data = json.loads(result.stdout)
        assert data["message"] == "File not found"
        assert str(missing_path) not in data["message"]

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
        assert result.stderr.rstrip().endswith("error: Unknown detector provider")

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

    def test_config_invalid_max_chars_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid max_chars=0 produces config error."""
        monkeypatch.setenv("HUMANHAND_MAX_CHARS", "0")
        result = runner.invoke(app, ["verify", "dummy_config_zero.txt"])
        assert result.exit_code == EXIT_CONFIG_ERROR
        assert "configuration is invalid" in result.stderr.lower()

    def test_config_invalid_cache_enabled_boolean(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid cache_enabled value produces config error."""
        monkeypatch.setenv("HUMANHAND_CACHE_ENABLED", "not_a_bool")
        result = runner.invoke(app, ["verify", "dummy_config_bool.txt"])
        assert result.exit_code == EXIT_CONFIG_ERROR
        assert "configuration is invalid" in result.stderr.lower()

    def test_rewrite_missing_llm_url(self, tmp_path: Path) -> None:
        """Rewrite fails clearly when no LLM endpoint URL is configured."""
        source = tmp_path / "rewrite_source.txt"
        source.write_text("The Eiffel Tower is 330 meters tall.\n")
        style = tmp_path / "rewrite_style.txt"
        style.write_text("I write in short, direct sentences.\n")
        out = tmp_path / "rewrite_out.txt"

        result = runner.invoke(
            app,
            [
                "rewrite",
                "--source",
                str(source),
                "--style",
                str(style),
                "--out",
                str(out),
            ],
        )

        assert result.exit_code == EXIT_CONFIG_ERROR
        assert result.stderr.rstrip().endswith("error: LLM endpoint URL is not configured")

    def test_rewrite_missing_llm_model(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Rewrite fails clearly when no LLM model is configured."""
        monkeypatch.setenv("HUMANHAND_LLM_BASE_URL", "https://example.com/v1")
        source = tmp_path / "rewrite_source.txt"
        source.write_text("The Eiffel Tower is 330 meters tall.\n")
        style = tmp_path / "rewrite_style.txt"
        style.write_text("I write in short, direct sentences.\n")
        out = tmp_path / "rewrite_out.txt"

        result = runner.invoke(
            app,
            [
                "rewrite",
                "--source",
                str(source),
                "--style",
                str(style),
                "--out",
                str(out),
            ],
        )

        assert result.exit_code == EXIT_CONFIG_ERROR
        assert result.stderr.rstrip().endswith("error: LLM model is not configured")


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


# ── Rewrite size errors ───────────────────────────────────────────


class TestRewriteSizeErrors:
    """Errors when rewrite input exceeds size limits."""

    def test_rewrite_source_too_large(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Source exceeding max_chars produces error."""
        monkeypatch.setenv("HUMANHAND_MAX_CHARS", "1")
        monkeypatch.setenv("HUMANHAND_LLM_BASE_URL", "https://example.com/v1")
        monkeypatch.setenv("HUMANHAND_LLM_MODEL", "example-model")
        source = tmp_path / "src_too_large.txt"
        source.write_text("Source text longer than 1 char")
        style = tmp_path / "style_too_large.txt"
        style.write_text("Short")
        out = tmp_path / "out_too_large.txt"
        result = runner.invoke(
            app,
            [
                "rewrite",
                "--source",
                str(source),
                "--style",
                str(style),
                "--out",
                str(out),
            ],
        )
        assert result.exit_code != 0
        assert "exceeds" in result.stderr.lower()

    def test_rewrite_style_too_large(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Style exceeding max_chars produces error."""
        monkeypatch.setenv("HUMANHAND_MAX_CHARS", "5")
        monkeypatch.setenv("HUMANHAND_LLM_BASE_URL", "https://example.com/v1")
        monkeypatch.setenv("HUMANHAND_LLM_MODEL", "example-model")
        source = tmp_path / "src_short.txt"
        source.write_text("Short")
        style = tmp_path / "style_long.txt"
        style.write_text("Style text that is longer than five characters")
        out = tmp_path / "out_style_too_large.txt"
        result = runner.invoke(
            app,
            [
                "rewrite",
                "--source",
                str(source),
                "--style",
                str(style),
                "--out",
                str(out),
            ],
        )
        assert result.exit_code != 0
        assert "exceeds" in result.stderr.lower()

    def test_rewrite_size_json_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Size limit error in JSON mode produces valid JSON error."""
        monkeypatch.setenv("HUMANHAND_MAX_CHARS", "1")
        monkeypatch.setenv("HUMANHAND_LLM_BASE_URL", "https://example.com/v1")
        monkeypatch.setenv("HUMANHAND_LLM_MODEL", "example-model")
        source = tmp_path / "src_json.txt"
        source.write_text("Too long source text")
        style = tmp_path / "style_json.txt"
        style.write_text("Short")
        out = tmp_path / "out_json.txt"
        result = runner.invoke(
            app,
            [
                "rewrite",
                "--source",
                str(source),
                "--style",
                str(style),
                "--out",
                str(out),
                "--json",
            ],
        )
        assert result.exit_code != 0
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "message" in data
        assert data["exit_code"] == EXIT_INPUT_ERROR


# ── Error mapping direct tests ────────────────────────────────────


class TestErrorMapping:
    """Direct tests of error mapping functions."""

    # ── error_for_exception: FileIOError / FileNotFoundError ──

    def test_error_for_exception_file_not_found(self) -> None:
        """FileNotFoundError maps to file_not_found."""
        exc = FileNotFoundError("File not found: /some/path")
        assert error_for_exception(exc) == "file_not_found"

    def test_error_for_exception_file_io_not_a_file(self) -> None:
        """FileIOError with 'not a regular file' maps to not_a_file."""
        exc = FileIOError("Not a regular file: /some/path")
        assert error_for_exception(exc) == "not_a_file"

    def test_error_for_exception_bom_detected(self) -> None:
        """FileIOError with BOM maps to bom_detected."""
        exc = FileIOError("UTF-8 BOM detected; BOM is not accepted")
        assert error_for_exception(exc) == "bom_detected"

    def test_error_for_exception_invalid_utf8(self) -> None:
        """FileIOError with 'invalid utf-8' maps to invalid_utf8."""
        exc = FileIOError("Invalid UTF-8 in file: /path")
        assert error_for_exception(exc) == "invalid_utf8"

    def test_error_for_exception_cannot_read(self) -> None:
        """FileIOError with 'cannot read file' maps to cannot_read."""
        exc = FileIOError("Cannot read file: /path")
        assert error_for_exception(exc) == "cannot_read"

    def test_error_for_exception_cannot_write(self) -> None:
        """FileIOError with 'cannot write output file' maps to cannot_write."""
        exc = FileIOError("Cannot write output file: /path")
        assert error_for_exception(exc) == "cannot_write"

    def test_error_for_exception_cannot_create_output_dir(self) -> None:
        """FileIOError with 'cannot create output directory' maps to cannot_write."""
        exc = FileIOError("Cannot create output directory: /path")
        assert error_for_exception(exc) == "cannot_write"

    def test_error_for_exception_output_is_input(self) -> None:
        """FileIOError with 'output path must not match' maps to output_is_input."""
        exc = FileIOError("Output path must not match an input path: /path")
        assert error_for_exception(exc) == "output_is_input"

    def test_error_for_exception_whitespace_only(self) -> None:
        """FileIOError with 'whitespace-only' maps to whitespace_only."""
        exc = FileIOError("File is empty or whitespace-only: /path")
        assert error_for_exception(exc) == "whitespace_only"

    # ── error_for_exception: LlmError ──

    def test_error_for_exception_llm_timeout(self) -> None:
        """LlmError with 'timed out' maps to llm_timeout."""
        exc = LlmError("Request timed out after 30s")
        assert error_for_exception(exc) == "llm_timeout"

    def test_error_for_exception_missing_llm_url(self) -> None:
        """Missing configured LLM URL maps to missing_llm_url."""
        exc = LlmError("LLM endpoint URL is not configured")
        assert error_for_exception(exc) == "missing_llm_url"

    def test_error_for_exception_missing_llm_model(self) -> None:
        """Missing configured LLM model maps to missing_llm_model."""
        exc = LlmError("LLM model is not configured")
        assert error_for_exception(exc) == "missing_llm_model"

    def test_error_for_exception_llm_unsafe_endpoint(self) -> None:
        """LlmError with 'http is not allowed' maps to unsafe_endpoint."""
        exc = LlmError("HTTP is not allowed for non-localhost endpoints")
        assert error_for_exception(exc) == "unsafe_endpoint"

    def test_error_for_exception_llm_generic(self) -> None:
        """Generic LlmError maps to llm_error."""
        exc = LlmError("LLM request failed with 503")
        assert error_for_exception(exc) == "llm_error"

    # ── error_for_exception: DetectorError / ProviderUnavailableError ──

    def test_error_for_exception_detector_unavailable(self) -> None:
        """DetectorError maps to detector_unavailable."""
        exc = DetectorError("Detector provider is down")
        assert error_for_exception(exc) == "detector_unavailable"

    def test_error_for_exception_provider_no_key(self) -> None:
        """ProviderUnavailableError with 'api key' maps to provider_no_key."""
        exc = ProviderUnavailableError("API key not configured for provider")
        assert error_for_exception(exc) == "provider_no_key"

    def test_error_for_exception_provider_no_docs(self) -> None:
        """Generic ProviderUnavailableError maps to provider_no_docs."""
        exc = ProviderUnavailableError("Provider not yet available")
        assert error_for_exception(exc) == "provider_no_docs"

    # ── error_for_exception: RewriteQualityError ──

    def test_error_for_exception_fact_drift(self) -> None:
        """RewriteQualityError maps to fact_drift."""
        exc = RewriteQualityError("Fact drift repair failed")
        assert error_for_exception(exc) == "fact_drift"

    # ── error_for_exception: ValueError ──

    def test_error_for_exception_value_error_source_too_large(self) -> None:
        """ValueError with 'source text exceeds' maps to source_too_large."""
        exc = ValueError("Source text exceeds maximum characters (100)")
        assert error_for_exception(exc) == "source_too_large"

    def test_error_for_exception_value_error_style_too_large(self) -> None:
        """ValueError with 'style text exceeds' maps to style_too_large."""
        exc = ValueError("Style text exceeds maximum characters (100)")
        assert error_for_exception(exc) == "style_too_large"

    def test_error_for_exception_value_error_empty_source(self) -> None:
        """ValueError with 'source text must not be empty' maps to empty_source."""
        exc = ValueError("Source text must not be empty")
        assert error_for_exception(exc) == "empty_source"

    def test_error_for_exception_value_error_empty_style(self) -> None:
        """ValueError with 'style text must not be empty' maps to empty_style."""
        exc = ValueError("Style text must not be empty")
        assert error_for_exception(exc) == "empty_style"

    def test_error_for_exception_value_error_unknown_provider(self) -> None:
        """ValueError with 'unknown detector provider' maps to unknown_provider."""
        exc = ValueError("Unknown detector provider: foo")
        assert error_for_exception(exc) == "unknown_provider"

    def test_error_for_exception_value_error_positive_int(self) -> None:
        """ValueError with 'must be a positive' maps to config_invalid."""
        exc = ValueError("HUMANHAND_MAX_CHARS must be a positive integer")
        assert error_for_exception(exc) == "config_invalid"

    def test_error_for_exception_value_error_boolean_like(self) -> None:
        """ValueError with 'boolean-like' maps to config_invalid."""
        exc = ValueError("HUMANHAND_CACHE_ENABLED must be a boolean-like value")
        assert error_for_exception(exc) == "config_invalid"

    def test_error_for_exception_value_error_generic(self) -> None:
        """Unrecognised ValueError maps to missing_argument."""
        exc = ValueError("Some other value error")
        assert error_for_exception(exc) == "missing_argument"

    # ── error_for_exception: KeyError / TypeError ──

    def test_error_for_exception_key_error(self) -> None:
        """KeyError maps to schema_invalid."""
        exc = KeyError("missing_field")
        assert error_for_exception(exc) == "schema_invalid"

    def test_error_for_exception_type_error(self) -> None:
        """TypeError maps to schema_invalid."""
        exc = TypeError("expected str, got int")
        assert error_for_exception(exc) == "schema_invalid"

    # ── error_for_exception: Unknown ──

    def test_error_for_exception_unknown(self) -> None:
        """Unknown exception type maps to internal_error."""
        exc = RuntimeError("Unexpected failure")
        assert error_for_exception(exc) == "internal_error"

    # ── get_error_message ──

    def test_get_error_message_known_key(self) -> None:
        """Known key returns its message."""
        msg = get_error_message("empty_source")
        assert msg == "Source text must not be empty"

    def test_get_error_message_unknown_key_with_fallback(self) -> None:
        """Unknown key with fallback returns the fallback."""
        msg = get_error_message("nonexistent_key", fallback="Custom message")
        assert msg == "Custom message"

    def test_get_error_message_unknown_key_no_fallback(self) -> None:
        """Unknown key without fallback returns the internal error message."""
        msg = get_error_message("nonexistent_key")
        assert msg == ERROR_MESSAGES["internal_error"]

    # ── message_for_exception ──

    def test_message_for_exception_with_fallback(self) -> None:
        """message_for_exception returns the correct user-facing message."""
        exc = FileNotFoundError("File not found: test.txt")
        msg = message_for_exception(exc)
        assert msg == "File not found"
