"""E2E tests for human-readable CLI UX behavior."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from humanhand.application.services import (
    DiffFactsResult,
    RewriteResult,
    ScrubResult,
    VerifyResult,
)
from humanhand.cli.app import app
from humanhand.cli.output import (
    _color,
    _color_enabled,
    bold,
    dim,
    green,
    red,
    render_diff_facts_result,
    render_health,
    render_rewrite_result,
    render_scrub_result,
    render_verify_result,
    status,
    yellow,
)
from humanhand.domain.types import (
    FactAnchor,
    FactDiffReport,
    ScrubFinding,
    ScrubReport,
)
from humanhand.infra.config import Config

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
    """Create a temporary output file with enough text for heuristic analysis."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(
            "The Eiffel Tower is 330 meters tall and was completed in 1889. "
            "It receives approximately 7 million visitors annually. "
            "The tower is one of the most recognizable landmarks in the world.\n"
        )
    return f.name


# ── Info commands ────────────────────────────────────────────────


class TestInfoCommands:
    """Health, help, and version text output."""

    def test_health_text_contains_ok(self) -> None:
        """Health text output contains 'health: ok'."""
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        assert "health: ok" in result.stdout

    def test_help_lists_all_commands(self) -> None:
        """Help text lists all commands: rewrite, verify, diff-facts, scrub, health."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for cmd in ("rewrite", "verify", "diff-facts", "scrub", "health"):
            assert cmd in result.stdout.lower()

    def test_health_help_lists_options(self) -> None:
        """Health --help lists --json and --no-color options."""
        result = runner.invoke(app, ["health", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.stdout
        assert "--no-color" in result.stdout

    def test_version_outputs_version_string(self) -> None:
        """Version flag outputs version string."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "humanhand" in result.stdout
        assert re.search(r"\d+\.\d+\.\d+", result.stdout)

    def test_repo_cli_script_uses_repo_local_cache(self, tmp_path: Path) -> None:
        """scripts/cli.sh keeps uv cache/temp paths inside the repo-defined cache root."""
        cache_root = tmp_path / "repo-cache"
        env = os.environ.copy()
        env.pop("UV_CACHE_DIR", None)
        env.pop("TMPDIR", None)
        env.pop("TMP", None)
        env.pop("TEMP", None)
        env["CACHE_ROOT"] = str(cache_root)

        result = subprocess.run(
            ["sh", "scripts/cli.sh", "--version"],
            capture_output=True,
            cwd=Path.cwd(),
            encoding="utf-8",
            env=env,
            check=False,
        )

        assert result.returncode == 0
        assert "humanhand" in result.stdout.lower()
        assert (cache_root / "uv").is_dir()
        assert (cache_root / "tmp").is_dir()

    def test_dependency_audit_script_uses_repo_local_cache(self, tmp_path: Path) -> None:
        """scripts/dependency-audit.sh exports a repo-local pip-audit cache path."""
        cache_root = tmp_path / "audit-cache-root"
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        fake_uv = fake_bin / "uv"
        fake_uv.write_text(
            "#!/usr/bin/env sh\n"
            "set -eu\n"
            "printf 'cache=%s\\n' \"${PIP_AUDIT_CACHE_DIR:-}\"\n"
            "printf 'args=%s\\n' \"$*\"\n",
            encoding="utf-8",
            newline="\n",
        )
        fake_uv.chmod(fake_uv.stat().st_mode | 0o111)

        env = os.environ.copy()
        env["CACHE_ROOT"] = str(cache_root)
        env["PATH"] = f"{fake_bin}{os.pathsep}{env.get('PATH', '')}"

        result = subprocess.run(
            ["sh", "scripts/dependency-audit.sh"],
            capture_output=True,
            cwd=Path.cwd(),
            encoding="utf-8",
            env=env,
            check=False,
        )

        assert result.returncode == 0
        expected_cache = str(cache_root / "pip-audit").replace("\\", "/")
        assert f"cache={expected_cache}" in result.stdout.replace("\\", "/")
        assert "args=run pip-audit" in result.stdout
        assert "dependency audit: ok" in result.stdout
        assert (cache_root / "pip-audit").is_dir()

    def test_rewrite_help_lists_all_options(self) -> None:
        """Rewrite --help lists --source, --style, --out, --print, --json, --no-color."""
        result = runner.invoke(app, ["rewrite", "--help"])
        assert result.exit_code == 0
        for opt in ("--source", "--style", "--out", "--print", "--json", "--no-color"):
            assert opt in result.stdout

    def test_verify_help_lists_options(self) -> None:
        """Verify --help lists --provider, --json, --no-color."""
        result = runner.invoke(app, ["verify", "--help"])
        assert result.exit_code == 0
        for opt in ("--provider", "--json", "--no-color"):
            assert opt in result.stdout

    def test_scrub_help_lists_options(self) -> None:
        """Scrub --help lists --out, --audit, --json, --no-color."""
        result = runner.invoke(app, ["scrub", "--help"])
        assert result.exit_code == 0
        for opt in ("--out", "--audit", "--json", "--no-color"):
            assert opt in result.stdout

    def test_diff_facts_help_lists_options(self) -> None:
        """Diff-facts --help lists --json, --no-color."""
        result = runner.invoke(app, ["diff-facts", "--help"])
        assert result.exit_code == 0
        for opt in ("--json", "--no-color"):
            assert opt in result.stdout


# ── No-color flag ────────────────────────────────────────────────


class TestNoColorFlag:
    """--no-color flag is accepted by all commands."""

    def test_health_no_color(self) -> None:
        """Health accepts --no-color."""
        result = runner.invoke(app, ["health", "--no-color"])
        assert result.exit_code == 0
        assert "health: ok" in result.stdout

    def test_verify_no_color(self, output_file: str) -> None:
        """Verify accepts --no-color."""
        result = runner.invoke(app, ["verify", output_file, "--no-color"])
        assert result.exit_code == 0
        assert "Verify" in result.stdout

    def test_diff_facts_no_color(self, source_file: str, output_file: str) -> None:
        """Diff-facts accepts --no-color."""
        result = runner.invoke(app, ["diff-facts", source_file, output_file, "--no-color"])
        assert result.exit_code == 0
        assert "preservation" in result.stdout.lower()

    def test_scrub_audit_no_color(self, output_file: str) -> None:
        """Scrub --audit accepts --no-color."""
        result = runner.invoke(app, ["scrub", output_file, "--audit", "--no-color"])
        assert result.exit_code == 0
        assert "Audit" in result.stdout

    def test_scrub_write_no_color(self, output_file: str, tmp_path: Path) -> None:
        """Scrub --out accepts --no-color."""
        out_path = tmp_path / "scrubbed_no_color.txt"
        result = runner.invoke(app, ["scrub", output_file, "--out", str(out_path), "--no-color"])
        assert result.exit_code == 0

    def test_no_color_output_has_no_ansi_codes(self, output_file: str) -> None:
        """Output with --no-color has no ANSI escape sequences."""
        result = runner.invoke(app, ["verify", output_file, "--no-color"])
        assert result.exit_code == 0
        assert "\033[" not in result.stdout
        assert "\033[" not in result.stderr

    def test_health_no_color_output_has_no_ansi_codes(self) -> None:
        """Health output with --no-color has no ANSI escape sequences."""
        result = runner.invoke(app, ["health", "--no-color"])
        assert result.exit_code == 0
        assert "\033[" not in result.stdout

    def test_diff_facts_no_color_output_has_no_ansi_codes(
        self, source_file: str, output_file: str
    ) -> None:
        """Diff-facts output with --no-color has no ANSI escape sequences."""
        result = runner.invoke(app, ["diff-facts", source_file, output_file, "--no-color"])
        assert result.exit_code == 0
        assert "\033[" not in result.stdout

    def test_root_no_color_flag_propagates(
        self, output_file: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Root-level --no-color propagates into colorized subcommand output."""
        seen_flags: list[bool] = []

        def fake_color_enabled(no_color_flag: bool = False) -> bool:
            seen_flags.append(no_color_flag)
            return not no_color_flag

        monkeypatch.setattr("humanhand.cli.output._color_enabled", fake_color_enabled)
        result = runner.invoke(app, ["--no-color", "verify", output_file])
        assert result.exit_code == 0
        assert seen_flags
        assert all(seen_flags)
        assert "\033[" not in result.stdout


# ── NO_COLOR env var ─────────────────────────────────────────────


class TestNoColorEnvVar:
    """NO_COLOR environment variable is honored."""

    def test_health_no_color_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Health with NO_COLOR=1 emits no ANSI codes."""
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        assert "health: ok" in result.stdout
        assert "\033[" not in result.stdout

    def test_verify_no_color_env(self, output_file: str, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify with NO_COLOR=1 works without ANSI codes."""
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["verify", output_file])
        assert result.exit_code == 0
        assert "\033[" not in result.stdout

    def test_diff_facts_no_color_env(
        self, source_file: str, output_file: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Diff-facts with NO_COLOR=1 works without ANSI codes."""
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["diff-facts", source_file, output_file])
        assert result.exit_code == 0
        assert "\033[" not in result.stdout

    def test_scrub_no_color_env(self, output_file: str, monkeypatch: pytest.MonkeyPatch) -> None:
        """Scrub with NO_COLOR=1 works without ANSI codes."""
        monkeypatch.setenv("NO_COLOR", "1")
        result = runner.invoke(app, ["scrub", output_file, "--audit"])
        assert result.exit_code == 0
        assert "\033[" not in result.stdout

    def test_no_color_env_var_case_insensitivity(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """NO_COLOR=0 still suppresses color (any non-empty value)."""
        monkeypatch.setenv("NO_COLOR", "0")
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        assert "health: ok" in result.stdout

    def test_no_color_env_empty_string_allows_color(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """NO_COLOR set to empty string does not suppress color."""
        monkeypatch.setenv("NO_COLOR", "")
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        assert "health: ok" in result.stdout

    def test_verify_json_and_no_color(self, output_file: str) -> None:
        """Verify with both --json and --no-color works."""
        result = runner.invoke(app, ["verify", output_file, "--json", "--no-color"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"

    def test_health_json_and_no_color(self) -> None:
        """Health with both --json and --no-color works."""
        result = runner.invoke(app, ["health", "--json", "--no-color"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"

    def test_diff_facts_json_and_no_color(self, source_file: str, output_file: str) -> None:
        """Diff-facts with both --json and --no-color works."""
        result = runner.invoke(
            app, ["diff-facts", source_file, output_file, "--json", "--no-color"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"

    def test_scrub_json_and_no_color(self, output_file: str) -> None:
        """Scrub --audit with both --json and --no-color works."""
        result = runner.invoke(app, ["scrub", output_file, "--audit", "--json", "--no-color"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"


# ── stdout/stderr separation ─────────────────────────────────────


class TestStdoutStderrSeparation:
    """Status messages, logs, and errors are correctly routed."""

    def test_health_status_goes_to_stdout(self) -> None:
        """Health status text is on stdout, not stderr."""
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        assert "health: ok" in result.stdout
        # stderr may have logs, but not the status line
        assert "health: ok" not in result.stderr

    def test_verify_status_goes_to_stdout(self, output_file: str) -> None:
        """Verify status text is on stdout, not stderr."""
        result = runner.invoke(app, ["verify", output_file])
        assert result.exit_code == 0
        assert "Verify" in result.stdout
        assert "Verify" not in result.stderr

    def test_logs_go_to_stderr(self) -> None:
        """Health JSONL log entries appear on stderr."""
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        assert "health.start" in result.stderr
        assert "health.end" in result.stderr


# ── Text output content ──────────────────────────────────────────


class TestTextOutput:
    """Human-readable text output in specific commands."""

    def test_verify_text_has_score_and_label(self, output_file: str) -> None:
        """Verify text output includes score and label."""
        result = runner.invoke(app, ["verify", output_file])
        assert result.exit_code == 0
        assert "score" in result.stdout.lower()
        assert "label" in result.stdout.lower()

    def test_verify_text_has_provider(self, output_file: str) -> None:
        """Verify text output includes provider name."""
        result = runner.invoke(app, ["verify", output_file])
        assert result.exit_code == 0
        assert "local" in result.stdout.lower()

    def test_diff_facts_text_has_preservation_percentage(
        self, source_file: str, output_file: str
    ) -> None:
        """Diff-facts text output includes preservation percentage."""
        result = runner.invoke(app, ["diff-facts", source_file, output_file])
        assert result.exit_code == 0
        assert "%" in result.stdout
        assert "preservation" in result.stdout.lower()

    def test_diff_facts_text_lists_counts(self, source_file: str, output_file: str) -> None:
        """Diff-facts text output lists omissions, additions, contradictions."""
        result = runner.invoke(app, ["diff-facts", source_file, output_file])
        assert result.exit_code == 0
        assert "Omissions" in result.stdout or "omissions" in result.stdout
        assert "Additions" in result.stdout or "additions" in result.stdout
        assert "Contradictions" in result.stdout or "contradictions" in result.stdout

    def test_scrub_audit_text_has_audit_label(self, output_file: str) -> None:
        """Scrub --audit text output includes 'Audit' label."""
        result = runner.invoke(app, ["scrub", output_file, "--audit"])
        assert result.exit_code == 0
        assert "Audit" in result.stdout

    def test_scrub_audit_text_shows_findings_count(self, output_file: str) -> None:
        """Scrub --audit text output shows number of findings."""
        result = runner.invoke(app, ["scrub", output_file, "--audit"])
        assert result.exit_code == 0
        assert "finding" in result.stdout.lower()

    def test_scrub_write_text_has_output_path(self, output_file: str, tmp_path: Path) -> None:
        """Scrub --out text output includes output path."""
        out_path = tmp_path / "scrubbed_text_test.txt"
        result = runner.invoke(app, ["scrub", output_file, "--out", str(out_path)])
        assert result.exit_code == 0
        assert "Output" in result.stdout

    def test_rewrite_help_has_print_option(self) -> None:
        """Rewrite --help marks --print as text-mode-only output."""
        result = runner.invoke(app, ["rewrite", "--help"])
        assert result.exit_code == 0
        assert "--print" in result.stdout
        normalized = " ".join(result.stdout.lower().split())
        sanitized = normalized.replace("│", " ")
        assert "text mode only" in " ".join(sanitized.split())


# ── No prose without --print ─────────────────────────────────────


class TestNoProseWithoutPrint:
    """Generated prose is hidden without --print flag."""

    def test_rewrite_help_mentions_no_prose_default(self) -> None:
        """Rewrite help describes --print as the way to show prose."""
        result = runner.invoke(app, ["rewrite", "--help"])
        assert result.exit_code == 0
        assert "--print" in result.stdout

    def test_rewrite_print_stdout_is_prose_only(
        self,
        source_file: str,
        style_file: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Rewrite --print keeps stdout limited to the generated prose."""
        expected_output = "A calmer, more human rewrite.\n"
        out_path = tmp_path / "rewrite_print_only.txt"

        monkeypatch.setattr(
            "humanhand.cli.app.load_config",
            lambda: Config(
                llm_base_url="https://example.com/v1",
                llm_model="test-model",
            ),
        )
        monkeypatch.setattr("humanhand.cli.app.OpenAiLlmClient", lambda config: object())

        def fake_rewrite(
            *,
            source_text: str,
            style_text: str,
            output_path: str,
            llm_client: object,
            file_writer: Any,
            logger: object,
            max_chars: int = 200_000,
            max_repair_attempts: int = 3,
            seed: int | None = None,
        ) -> RewriteResult:
            del llm_client, logger, max_chars, max_repair_attempts, seed
            written_path = file_writer.write(output_path, expected_output, input_paths=[])
            return RewriteResult(
                output_path=str(written_path),
                input_chars=len(source_text) + len(style_text),
                output_chars=len(expected_output),
                preservation_score=0.99,
            )

        monkeypatch.setattr("humanhand.cli.app.rewrite", fake_rewrite)

        result = runner.invoke(
            app,
            [
                "rewrite",
                "--source",
                source_file,
                "--style",
                style_file,
                "--out",
                str(out_path),
                "--print",
            ],
        )

        assert result.exit_code == 0
        assert result.stdout == expected_output
        assert "Rewrite complete" not in result.stdout
        assert expected_output not in result.stderr


# ── Exact output format ──────────────────────────────────────────


class TestExactOutputFormat:
    """Specific output formatting checks."""

    def test_version_output_format(self) -> None:
        """Version output follows 'humanhand X.Y.Z' format."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        match = re.match(r"humanhand\s+(\d+\.\d+\.\d+)", result.stdout.strip())
        assert match is not None

    def test_health_no_trailing_spaces_on_stdout(self) -> None:
        """Health stdout line is cleanly formatted."""
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        line = result.stdout.strip()
        assert line == "health: ok"


# ── Color helper direct tests ─────────────────────────────────────


class TestColorHelpers:
    """Direct tests of color helper functions."""

    def test_bold_with_no_color(self) -> None:
        """bold() with no_color=True returns plain text."""
        assert bold("hello", no_color=True) == "hello"

    def test_red_with_no_color(self) -> None:
        """red() with no_color=True returns plain text."""
        assert red("error", no_color=True) == "error"

    def test_green_with_no_color(self) -> None:
        """green() with no_color=True returns plain text."""
        assert green("ok", no_color=True) == "ok"

    def test_yellow_with_no_color(self) -> None:
        """yellow() with no_color=True returns plain text."""
        assert yellow("warn", no_color=True) == "warn"

    def test_dim_with_no_color(self) -> None:
        """dim() with no_color=True returns plain text."""
        assert dim("subtle", no_color=True) == "subtle"

    def test_color_with_no_color(self) -> None:
        """_color() with no_color_flag=True returns plain text."""
        assert _color(31, "text", no_color=True) == "text"


class TestColorEnabled:
    """Direct tests of _color_enabled() helper."""

    def test_no_color_flag_disables_color(self) -> None:
        """_color_enabled(no_color_flag=True) returns False."""
        assert _color_enabled(no_color_flag=True) is False

    def test_no_color_env_disables_color(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_color_enabled with NO_COLOR set returns False."""
        monkeypatch.setenv("NO_COLOR", "1")
        assert _color_enabled() is False

    def test_no_color_env_empty_allows_color(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_color_enabled with NO_COLOR empty and tty returns True."""
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.setattr("humanhand.cli.output.sys.stdout.isatty", lambda: True)
        monkeypatch.setattr("humanhand.cli.output.sys.platform", "linux")
        assert _color_enabled() is True

    def test_disabled_on_pipe(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_color_enabled returns False when stdout is not a tty."""
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.setattr("humanhand.cli.output.sys.stdout.isatty", lambda: False)
        monkeypatch.setattr("humanhand.cli.output.sys.platform", "linux")
        assert _color_enabled() is False

    def test_windows_term_uppercase_xterm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Windows ANSI TERM detection accepts uppercase xterm values."""
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.setenv("TERM", "XTERM-256COLOR")
        monkeypatch.setattr("humanhand.cli.output.sys.stdout.isatty", lambda: True)
        monkeypatch.setattr("humanhand.cli.output.sys.platform", "win32")
        assert _color_enabled() is True


class TestStatus:
    """Direct tests of status() helper."""

    def test_status_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """status() prints to stderr."""
        status("test message")
        captured = capsys.readouterr()
        assert "test message" in captured.err
        assert captured.out == ""


# ── Text render function direct tests ─────────────────────────────


class TestTextRenderFunctions:
    """Direct tests of text-mode render functions with synthetic data."""

    def test_render_verify_score_high(self, capsys: pytest.CaptureFixture[str]) -> None:
        """render_verify_result with high score shows score value."""
        result = VerifyResult(provider="local", model="test", score=0.96, label="human")
        render_verify_result(result, json_mode=False, no_color=True)
        captured = capsys.readouterr()
        assert "0.9600" in captured.out
        assert "human" in captured.out

    def test_render_verify_score_low(self, capsys: pytest.CaptureFixture[str]) -> None:
        """render_verify_result with low score renders label."""
        result = VerifyResult(provider="local", model="test", score=0.12, label="human")
        render_verify_result(result, json_mode=False, no_color=True)
        captured = capsys.readouterr()
        assert "0.1200" in captured.out

    def test_render_verify_score_none(self, capsys: pytest.CaptureFixture[str]) -> None:
        """render_verify_result with None score shows N/A."""
        result = VerifyResult(provider="local", model="test", score=None, label=None)
        render_verify_result(result, json_mode=False, no_color=True)
        captured = capsys.readouterr()
        assert "N/A" in captured.out

    def test_render_verify_label_ai(self, capsys: pytest.CaptureFixture[str]) -> None:
        """render_verify_result with 'ai' label renders correctly."""
        result = VerifyResult(provider="local", model="test", score=0.85, label="ai")
        render_verify_result(result, json_mode=False, no_color=True)
        captured = capsys.readouterr()
        assert "0.8500" in captured.out
        assert "ai" in captured.out

    def test_render_verify_label_uncertain(self, capsys: pytest.CaptureFixture[str]) -> None:
        """render_verify_result with 'uncertain' label renders correctly."""
        result = VerifyResult(provider="local", model="test", score=0.50, label="uncertain")
        render_verify_result(result, json_mode=False, no_color=True)
        captured = capsys.readouterr()
        assert "uncertain" in captured.out

    def test_render_verify_cache_hit(self, capsys: pytest.CaptureFixture[str]) -> None:
        """render_verify_result with cache_hit shows cached indicator."""
        result = VerifyResult(
            provider="local",
            model="test",
            score=0.75,
            label="ai",
            cache_hit=True,
        )
        render_verify_result(result, json_mode=False, no_color=True)
        captured = capsys.readouterr()
        assert "cached" in captured.out

    def test_render_diff_facts_with_drift(self, capsys: pytest.CaptureFixture[str]) -> None:
        """render_diff_facts_result shows drift warning when has_drift is True."""
        anchor = FactAnchor(text="test", category="claim", position=0)
        report = FactDiffReport(
            omissions=(anchor,),
            additions=(),
            contradictions=(),
            preservation_score=0.75,
            total_source_anchors=5,
            total_candidate_anchors=3,
        )
        result = DiffFactsResult(report=report, source_chars=100, candidate_chars=80)
        render_diff_facts_result(result, json_mode=False, no_color=True)
        captured = capsys.readouterr()
        assert "drift" in captured.out.lower()

    def test_render_diff_facts_no_drift(self, capsys: pytest.CaptureFixture[str]) -> None:
        """render_diff_facts_result without drift has no warning."""
        report = FactDiffReport(
            omissions=(),
            additions=(),
            contradictions=(),
            preservation_score=0.98,
            total_source_anchors=5,
            total_candidate_anchors=5,
        )
        result = DiffFactsResult(report=report, source_chars=100, candidate_chars=100)
        render_diff_facts_result(result, json_mode=False, no_color=True)
        captured = capsys.readouterr()
        assert "drift" not in captured.out.lower()

    def test_render_scrub_audit_no_findings(self, capsys: pytest.CaptureFixture[str]) -> None:
        """render_scrub_result with no findings shows summary."""
        report = ScrubReport(findings=())
        result = ScrubResult(report=report, audit_only=True)
        render_scrub_result(result, json_mode=False, no_color=True)
        captured = capsys.readouterr()
        assert "0 finding" in captured.out.lower()

    def test_render_scrub_with_findings(self, capsys: pytest.CaptureFixture[str]) -> None:
        """render_scrub_result lists findings correctly."""
        finding = ScrubFinding(
            category="timestamp",
            location="header",
            description="Found timestamp",
            removed=True,
        )
        report = ScrubReport(findings=(finding,), modifications=1)
        result = ScrubResult(report=report, audit_only=False, output_path="/tmp/output.txt")
        render_scrub_result(result, json_mode=False, no_color=True)
        captured = capsys.readouterr()
        assert "timestamp" in captured.out
        assert "finding" in captured.out.lower()
        assert "/tmp/output.txt" in captured.out

    def test_render_health_text_mode(self, capsys: pytest.CaptureFixture[str]) -> None:
        """render_health in text mode prints ok."""
        render_health(
            Config(), json_mode=False, config_valid=True, config_error=None, no_color=True
        )
        captured = capsys.readouterr()
        assert "health: ok" in captured.out

    def test_render_rewrite_text_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """render_rewrite_result in text mode prints summary."""
        result = RewriteResult(
            output_path="/tmp/output.txt",
            input_chars=100,
            output_chars=80,
            repair_attempts=1,
            preservation_score=0.92,
            duration_ms=500.0,
        )
        render_rewrite_result(result, json_mode=False, no_color=True)
        captured = capsys.readouterr()
        assert "output.txt" in captured.out
        assert "100" in captured.out
        assert "80" in captured.out
        assert "repair" in captured.out.lower()
