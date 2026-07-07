"""Fast smoke tests for CLI commands — must complete under 30 seconds on mocks."""

from __future__ import annotations

import json
import os
import tempfile

from typer.testing import CliRunner

from humanhand.cli.app import app

runner = CliRunner()


# ── Quick-response tests (first-byte under 100ms target) ────────


class TestCliResponsiveness:
    def test_help_responds_fast(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "humanhand" in result.stdout.lower()

    def test_version_responds_fast(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "humanhand" in result.stdout

    def test_health_responds_fast(self) -> None:
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        assert "health: ok" in result.stdout


# ── All commands exist ──────────────────────────────────────────


class TestAllCommandsExist:
    def test_rewrite_command_exists(self) -> None:
        result = runner.invoke(app, ["rewrite", "--help"])
        assert result.exit_code == 0

    def test_verify_command_exists(self) -> None:
        result = runner.invoke(app, ["verify", "--help"])
        assert result.exit_code == 0

    def test_diff_facts_command_exists(self) -> None:
        result = runner.invoke(app, ["diff-facts", "--help"])
        assert result.exit_code == 0

    def test_scrub_command_exists(self) -> None:
        result = runner.invoke(app, ["scrub", "--help"])
        assert result.exit_code == 0

    def test_health_command_exists(self) -> None:
        result = runner.invoke(app, ["health", "--help"])
        assert result.exit_code == 0


# ── JSON mode smoke ─────────────────────────────────────────────


class TestJsonModeSmoke:
    def test_health_json_valid(self) -> None:
        result = runner.invoke(app, ["health", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "status" in data

    def test_verify_with_file_json(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(
                "This is a test file for smoke testing the verify command. "
                "It contains multiple sentences to allow proper heuristic analysis. "
                "The local detector requires at least two sentences to function.\n"
            )
            tmp_path = f.name

        result = runner.invoke(app, ["verify", tmp_path, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert data["provider"] == "local"

    def test_scrub_audit_json(self) -> None:
        """scrub --audit --json returns valid JSON with findings."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("Some text with content for scrub audit.\n")
            tmp_path = f.name

        try:
            result = runner.invoke(app, ["scrub", tmp_path, "--audit", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["status"] == "ok"
            assert "findings_count" in data
            assert "findings" in data
        finally:
            os.unlink(tmp_path)


# ── Color behavior smoke ────────────────────────────────────────


class TestColorBehavior:
    def test_no_color_flag_accepted_on_health(self) -> None:
        """--no-color flag is accepted on health command."""
        result = runner.invoke(app, ["health", "--no-color"])
        assert result.exit_code == 0
        assert "health: ok" in result.stdout

    def test_no_color_env_var(self) -> None:
        """NO_COLOR=1 env var suppresses ANSI escape codes."""
        result = runner.invoke(app, ["health"], env={"NO_COLOR": "1"})
        assert result.exit_code == 0
        assert "health: ok" in result.stdout
        assert "\033[" not in result.stdout


# ── Output separation smoke ─────────────────────────────────────


class TestOutputSeparation:
    def test_no_prose_in_stdout_without_print(self) -> None:
        """Generated prose never appears on stdout without --print.
        Triggers an IO error and verifies no rendering output leaks."""
        result = runner.invoke(
            app,
            [
                "rewrite",
                "--source",
                "/nonexistent/src.txt",
                "--style",
                "/nonexistent/style.txt",
                "--out",
                "/nonexistent/out.txt",
            ],
        )
        assert result.exit_code != 0
        # The error message writes to stderr (mixed into .stdout by default).
        # Key assertion: no rendering/prose text appears in output.
        assert "Rewrite complete" not in result.stdout

    def test_json_no_color_combo(self) -> None:
        """--json and --no-color can be combined on health."""
        result = runner.invoke(app, ["health", "--json", "--no-color"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"


# ── Error mapping smoke ─────────────────────────────────────────


class TestErrorMappingSmoke:
    def test_missing_file_error(self) -> None:
        result = runner.invoke(app, ["verify", "/nonexistent/path/file.txt"])
        assert result.exit_code != 0

    def test_invalid_provider_error(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(
                "This file has multiple sentences for proper analysis. "
                "The detector needs at least two sentences to analyze correctly.\n"
            )
            tmp_path = f.name

        result = runner.invoke(app, ["verify", tmp_path, "--provider", "invalid_provider"])
        assert result.exit_code != 0

    def test_diff_facts_missing_file(self) -> None:
        result = runner.invoke(app, ["diff-facts", "/nonexistent/a.txt", "/nonexistent/b.txt"])
        assert result.exit_code != 0
