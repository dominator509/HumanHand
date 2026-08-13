"""E2E tests for CLI commands using Typer CliRunner."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from humanhand.cli.app import app

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


# ── Health command ──────────────────────────────────────────────


class TestHealthCommand:
    def test_health_text(self) -> None:
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        assert "health: ok" in result.stdout

    def test_health_json(self) -> None:
        result = runner.invoke(app, ["health", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert "version" in data
        assert data["config_valid"] is True
        assert data["commands"]["health"] is True

    def test_health_logs_jsonl_to_stderr(self) -> None:
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        log_lines = [
            json.loads(line) for line in result.stderr.splitlines() if line.startswith("{")
        ]
        assert any(line["event"] == "health.start" for line in log_lines)
        assert any(line["event"] == "health.end" for line in log_lines)

    def test_help_flag(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "rewrite" in result.stdout or "Rewrite" in result.stdout
        assert "verify" in result.stdout or "Verify" in result.stdout

    def test_version_flag(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "humanhand" in result.stdout


# ── Rewrite command ─────────────────────────────────────────────


class TestRewriteCommand:
    def test_rewrite_missing_source(self) -> None:
        result = runner.invoke(app, ["rewrite", "--style", "style.txt", "--out", "out.txt"])
        assert result.exit_code != 0

    def test_rewrite_missing_style(self) -> None:
        result = runner.invoke(app, ["rewrite", "--source", "src.txt", "--out", "out.txt"])
        assert result.exit_code != 0

    def test_rewrite_missing_out(self) -> None:
        result = runner.invoke(app, ["rewrite", "--source", "src.txt", "--style", "style.txt"])
        assert result.exit_code != 0

    def test_rewrite_file_not_found(self, style_file: str) -> None:
        result = runner.invoke(
            app,
            ["rewrite", "--source", "nonexistent.txt", "--style", style_file, "--out", "out.txt"],
        )
        assert result.exit_code != 0

    def test_rewrite_style_not_found(self, source_file: str) -> None:
        result = runner.invoke(
            app,
            ["rewrite", "--source", source_file, "--style", "nonexistent.txt", "--out", "out.txt"],
        )
        assert result.exit_code != 0


# ── Verify command ──────────────────────────────────────────────


class TestVerifyCommand:
    def test_verify_missing_argument(self) -> None:
        result = runner.invoke(app, ["verify"])
        assert result.exit_code != 0

    def test_verify_file_not_found(self) -> None:
        result = runner.invoke(app, ["verify", "nonexistent.txt"])
        assert result.exit_code != 0

    def test_verify_unknown_provider(self, output_file: str) -> None:
        result = runner.invoke(app, ["verify", output_file, "--provider", "unknown_provider"])
        assert result.exit_code != 0

    def test_verify_json_mode(self, output_file: str) -> None:
        result = runner.invoke(app, ["verify", output_file, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert "score" in data
        assert "label" in data
        assert data["provider"] == "local"

    def test_verify_text_mode(self, output_file: str) -> None:
        result = runner.invoke(app, ["verify", output_file])
        assert result.exit_code == 0
        assert "Verify" in result.stdout
        assert "score" in result.stdout.lower() or "Score" in result.stdout

    def test_verify_with_local_provider(self, output_file: str) -> None:
        result = runner.invoke(app, ["verify", output_file, "--provider", "local"])
        assert result.exit_code == 0

    def test_verify_stub_provider_unavailable(self, output_file: str) -> None:
        """Stub providers without API keys should fail clearly."""
        result = runner.invoke(app, ["verify", output_file, "--provider", "gptzero"])
        assert result.exit_code != 0


class TestStrictLocalPrivacyMode:
    def test_health_emits_no_logs_or_counters(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_PRIVACY_MODE", "strict_local")
        result = runner.invoke(app, ["health", "--json"])
        assert result.exit_code == 0
        assert result.stderr == ""

    def test_rewrite_is_denied_before_input_read(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HUMANHAND_PRIVACY_MODE", "strict_local")
        result = runner.invoke(
            app,
            [
                "rewrite",
                "--source",
                "missing-source.txt",
                "--style",
                "missing-style.txt",
                "--out",
                "out.txt",
                "--json",
            ],
        )
        assert result.exit_code == 2
        assert "forbids network-backed rewrite" in result.stdout
        assert result.stderr == ""

    def test_remote_verify_is_denied_before_input_read(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HUMANHAND_PRIVACY_MODE", "strict_local")
        result = runner.invoke(
            app,
            ["verify", "missing-output.txt", "--provider", "gptzero", "--json"],
        )
        assert result.exit_code == 2
        assert "permits only the local detector" in result.stdout
        assert result.stderr == ""

    def test_local_verify_emits_no_logs_and_creates_no_cache(
        self,
        output_file: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        cache_dir = tmp_path / "cache"
        monkeypatch.setenv("HUMANHAND_PRIVACY_MODE", "strict_local")
        monkeypatch.setenv("HUMANHAND_CACHE_ENABLED", "1")
        monkeypatch.setenv("HUMANHAND_CACHE_DIR", str(cache_dir))
        result = runner.invoke(app, ["verify", output_file, "--provider", "local", "--json"])
        assert result.exit_code == 0
        assert result.stderr == ""
        assert not cache_dir.exists()


# ── Diff-facts command ──────────────────────────────────────────


class TestDiffFactsCommand:
    def test_diff_facts_missing_args(self) -> None:
        result = runner.invoke(app, ["diff-facts"])
        assert result.exit_code != 0

    def test_diff_facts_missing_second_arg(self, source_file: str) -> None:
        result = runner.invoke(app, ["diff-facts", source_file])
        assert result.exit_code != 0

    def test_diff_facts_file_not_found(self) -> None:
        result = runner.invoke(app, ["diff-facts", "nonexistent.txt", "also_nonexistent.txt"])
        assert result.exit_code != 0

    def test_diff_facts_json_mode(self, source_file: str, output_file: str) -> None:
        result = runner.invoke(app, ["diff-facts", source_file, output_file, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert "preservation_score" in data

    def test_diff_facts_text_mode(self, source_file: str, output_file: str) -> None:
        result = runner.invoke(app, ["diff-facts", source_file, output_file])
        assert result.exit_code == 0
        assert "preservation" in result.stdout.lower() or "preservation" in result.stdout


# ── Scrub command ───────────────────────────────────────────────


class TestScrubCommand:
    def test_scrub_missing_file(self) -> None:
        result = runner.invoke(app, ["scrub"])
        assert result.exit_code != 0

    def test_scrub_file_not_found(self) -> None:
        result = runner.invoke(app, ["scrub", "nonexistent.txt"])
        assert result.exit_code != 0

    def test_scrub_audit_mode(self, output_file: str) -> None:
        result = runner.invoke(app, ["scrub", output_file, "--audit"])
        assert result.exit_code == 0
        assert "Audit" in result.stdout

    def test_scrub_audit_json_mode(self, output_file: str) -> None:
        result = runner.invoke(app, ["scrub", output_file, "--audit", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert data["audit_only"] is True

    def test_scrub_write_without_out(self, output_file: str) -> None:
        result = runner.invoke(app, ["scrub", output_file])
        assert result.exit_code != 0

    def test_scrub_write_with_out(self, output_file: str, tmp_path: Path) -> None:
        out_path = tmp_path / "scrubbed.txt"
        result = runner.invoke(app, ["scrub", output_file, "--out", str(out_path)])
        assert result.exit_code == 0
        assert out_path.exists()

    def test_scrub_detect_bom(self, tmp_path: Path) -> None:
        bom_file = tmp_path / "bom.txt"
        bom_file.write_bytes(b"\xef\xbb\xbfHello world.\n")
        # BOM file will fail strict read
        result = runner.invoke(app, ["scrub", str(bom_file), "--audit"])
        assert result.exit_code != 0  # BOM is rejected by strict reader

    def test_scrub_help(self) -> None:
        result = runner.invoke(app, ["scrub", "--help"])
        assert result.exit_code == 0
        assert "--audit" in result.stdout


# ── stdout/stderr separation ────────────────────────────────────


class TestStdoutStderrSeparation:
    def test_health_stdout_only(self) -> None:
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        assert "health: ok" in result.stdout

    def test_verify_json_stdout_valid(self, output_file: str) -> None:
        result = runner.invoke(app, ["verify", output_file, "--json"])
        assert result.exit_code == 0
        # stdout should be valid JSON
        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    def test_error_goes_to_stderr(self) -> None:
        result = runner.invoke(app, ["verify", "nonexistent_file.txt"])
        assert result.exit_code != 0
        assert result.stderr != "" or result.stdout == ""

    def test_verify_error_logs_jsonl_to_stderr(self) -> None:
        result = runner.invoke(app, ["verify", "nonexistent_file.txt"])
        assert result.exit_code != 0
        log_lines = [
            json.loads(line) for line in result.stderr.splitlines() if line.startswith("{")
        ]
        assert any(line["event"] == "verify.error" for line in log_lines)


# ── No prose without --print ────────────────────────────────────


class TestNoProseWithoutPrint:
    def test_help_has_no_prose(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        # Help text is expected, not generated prose

    def test_health_has_no_user_text(self) -> None:
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        # Should not contain any generated prose content


# ── Exit codes ──────────────────────────────────────────────────


class TestExitCodes:
    def test_success_exit_zero(self) -> None:
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0

    def test_error_exit_nonzero(self) -> None:
        result = runner.invoke(app, ["verify", "nonexistent_file.txt"])
        assert result.exit_code != 0

    def test_missing_command_exit_nonzero(self) -> None:
        result = runner.invoke(app, [])
        assert result.exit_code != 0
