"""E2E tests for JSON-only stdout mode across all CLI commands."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from humanhand.application.services import (
    DiffFactsResult,
    RewriteResult,
    ScrubResult,
    VerifyResult,
)
from humanhand.cli.app import EXIT_CONFIG_ERROR, EXIT_INPUT_ERROR, EXIT_IO_ERROR, app
from humanhand.cli.output import (
    render_diff_facts_result,
    render_health,
    render_rewrite_result,
    render_scrub_result,
    render_verify_result,
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


# ── Health JSON ─────────────────────────────────────────────────


class TestJsonHealth:
    """Health command JSON output structure."""

    def test_health_json_required_keys(self) -> None:
        """Health --json includes all required keys."""
        result = runner.invoke(app, ["health", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert "version" in data
        assert "python_version" in data
        assert "platform" in data
        assert "llm_configured" in data
        assert "detector_provider" in data
        assert "cache_enabled" in data
        assert "cache_dir" in data
        assert "config_valid" in data

    def test_health_json_commands_list(self) -> None:
        """Health --json commands object contains all five subcommands."""
        result = runner.invoke(app, ["health", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        commands = data["commands"]
        for cmd in ("health", "rewrite", "verify", "diff-facts", "scrub"):
            assert cmd in commands
            assert commands[cmd] is True

    def test_health_json_config_error_null_when_valid(self) -> None:
        """Health --json config_error is null when config is valid."""
        result = runner.invoke(app, ["health", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["config_error"] is None

    def test_root_json_flag_health(self) -> None:
        """Root-level --json propagates to the health command."""
        result = runner.invoke(app, ["--json", "health"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"


# ── Verify JSON ─────────────────────────────────────────────────


class TestJsonVerify:
    """Verify command JSON output structure."""

    def test_verify_json_structure(self, output_file: str) -> None:
        """Verify --json includes provider/score/label/cache_hit."""
        result = runner.invoke(app, ["verify", output_file, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert data["provider"] == "local"
        assert "score" in data
        assert "label" in data
        assert "cache_hit" in data

    def test_verify_json_all_keys(self, output_file: str) -> None:
        """Verify --json includes all expected keys."""
        result = runner.invoke(app, ["verify", output_file, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert "provider" in data
        assert "model" in data
        assert "score" in data or data["score"] is None
        assert "label" in data or data["label"] is None
        assert "cache_hit" in data
        assert "duration_ms" in data

    def test_verify_json_cache_hit_is_bool(self, output_file: str) -> None:
        """Verify --json cache_hit is a boolean."""
        result = runner.invoke(app, ["verify", output_file, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data["cache_hit"], bool)

    def test_verify_json_duration_ms_is_number(self, output_file: str) -> None:
        """Verify --json duration_ms is a number."""
        result = runner.invoke(app, ["verify", output_file, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data["duration_ms"], int | float)


# ── Diff-facts JSON ─────────────────────────────────────────────


class TestJsonDiffFacts:
    """Diff-facts command JSON output structure."""

    def test_diff_facts_json_structure(self, source_file: str, output_file: str) -> None:
        """Diff-facts --json includes preservation_score/omissions/additions/contradictions."""
        result = runner.invoke(app, ["diff-facts", source_file, output_file, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert "preservation_score" in data
        assert "total_source_anchors" in data
        assert "total_candidate_anchors" in data
        assert "omissions" in data
        assert "additions" in data
        assert "contradictions" in data
        assert "has_drift" in data
        assert "source_chars" in data
        assert "candidate_chars" in data

    def test_diff_facts_json_has_drift_is_bool(self, source_file: str, output_file: str) -> None:
        """Diff-facts --json has_drift is a boolean."""
        result = runner.invoke(app, ["diff-facts", source_file, output_file, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data["has_drift"], bool)

    def test_diff_facts_json_counts_are_integers(self, source_file: str, output_file: str) -> None:
        """Diff-facts --json counts are integers."""
        result = runner.invoke(app, ["diff-facts", source_file, output_file, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data["omissions"], int)
        assert isinstance(data["additions"], int)
        assert isinstance(data["contradictions"], int)
        assert isinstance(data["total_source_anchors"], int)
        assert isinstance(data["total_candidate_anchors"], int)

    def test_diff_facts_json_preservation_score_is_float(
        self, source_file: str, output_file: str
    ) -> None:
        """Diff-facts --json preservation_score is a float."""
        result = runner.invoke(app, ["diff-facts", source_file, output_file, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data["preservation_score"], float)


# ── Scrub JSON ──────────────────────────────────────────────────


class TestJsonScrub:
    """Scrub command JSON output structure."""

    def test_scrub_audit_json_structure(self, output_file: str) -> None:
        """Scrub --audit --json includes findings/audit_only."""
        result = runner.invoke(app, ["scrub", output_file, "--audit", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert data["audit_only"] is True
        assert "findings_count" in data
        assert "findings" in data
        assert isinstance(data["findings"], list)
        assert "duration_ms" in data

    def test_scrub_json_with_output(self, output_file: str, tmp_path: Path) -> None:
        """Scrub --out --json includes output_path."""
        out_path = tmp_path / "scrubbed.json_test.txt"
        result = runner.invoke(app, ["scrub", output_file, "--out", str(out_path), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert data["output_path"] is not None
        assert "modifications" in data

    def test_scrub_json_findings_list_structure(self, output_file: str) -> None:
        """Scrub --json findings list items have category/location/description."""
        result = runner.invoke(app, ["scrub", output_file, "--audit", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        for finding in data["findings"]:
            assert "category" in finding
            assert "location" in finding
            assert "description" in finding
            assert "removed" in finding


# ── Error JSON ──────────────────────────────────────────────────


class TestJsonError:
    """JSON error output shape and mode behavior."""

    def test_json_error_on_missing_file(self) -> None:
        """JSON error mode produces standard error shape on missing file."""
        result = runner.invoke(app, ["verify", "nonexistent_json_error.txt", "--json"])
        assert result.exit_code != 0
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "message" in data
        assert "exit_code" in data
        assert isinstance(data["exit_code"], int)
        assert data["exit_code"] > 0

    def test_json_rewrite_missing_source_error_shape(
        self, style_file: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Rewrite with missing source in JSON mode produces valid error JSON."""
        monkeypatch.setenv("HUMANHAND_LLM_BASE_URL", "https://example.com/v1")
        monkeypatch.setenv("HUMANHAND_LLM_MODEL", "example-model")
        result = runner.invoke(
            app,
            [
                "rewrite",
                "--source",
                "nonexistent_rewrite_json.txt",
                "--style",
                style_file,
                "--out",
                "out_json_error.txt",
                "--json",
            ],
        )
        assert result.exit_code != 0
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "message" in data
        assert "exit_code" in data

    def test_json_error_exit_code_is_positive_int(self) -> None:
        """JSON error exit_code is a positive integer."""
        result = runner.invoke(app, ["verify", "nonexistent_exit_code.txt", "--json"])
        assert result.exit_code != 0
        data = json.loads(result.stdout)
        assert isinstance(data["exit_code"], int)
        assert data["exit_code"] > 0

    def test_json_error_message_is_string(self) -> None:
        """JSON error message is a non-empty string."""
        result = runner.invoke(app, ["verify", "nonexistent_error_msg.txt", "--json"])
        assert result.exit_code != 0
        data = json.loads(result.stdout)
        assert isinstance(data["message"], str)
        assert len(data["message"]) > 0

    def test_json_error_directory_not_a_file(self, tmp_path: Path) -> None:
        """JSON error for directory path has correct exit code."""
        result = runner.invoke(app, ["verify", str(tmp_path), "--json"])
        assert result.exit_code != 0
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "message" in data
        assert data["exit_code"] == EXIT_IO_ERROR

    def test_json_error_invalid_utf8(self, tmp_path: Path) -> None:
        """JSON error for invalid UTF-8 produces valid error JSON."""
        bad_file = tmp_path / "bad_utf8_json.txt"
        bad_file.write_bytes(b"\xff\xfe\x00\x00")
        result = runner.invoke(app, ["scrub", str(bad_file), "--audit", "--json"])
        assert result.exit_code != 0
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "message" in data
        assert data["exit_code"] > 0

    def test_json_config_invalid_max_chars_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """JSON error for invalid config has correct exit code."""
        monkeypatch.setenv("HUMANHAND_MAX_CHARS", "0")
        result = runner.invoke(app, ["verify", "dummy_cfg_json.txt", "--json"])
        assert result.exit_code != 0
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert "message" in data
        assert data["exit_code"] == EXIT_CONFIG_ERROR

    def test_json_rewrite_source_too_large(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """JSON error for source too large has correct exit code."""
        monkeypatch.setenv("HUMANHAND_MAX_CHARS", "1")
        monkeypatch.setenv("HUMANHAND_LLM_BASE_URL", "https://example.com/v1")
        monkeypatch.setenv("HUMANHAND_LLM_MODEL", "example-model")
        source = tmp_path / "src_json_too_large.txt"
        source.write_text("Longer source text")
        style = tmp_path / "style_json_too_large.txt"
        style.write_text("Short")
        out = tmp_path / "out_json_too_large.txt"
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

    def test_json_rewrite_rejects_print_combination(
        self, source_file: str, style_file: str, tmp_path: Path
    ) -> None:
        """Rewrite rejects --json with --print to preserve JSON-only stdout."""
        out = tmp_path / "out_json_print_conflict.txt"
        result = runner.invoke(
            app,
            [
                "rewrite",
                "--source",
                source_file,
                "--style",
                style_file,
                "--out",
                str(out),
                "--json",
                "--print",
            ],
        )
        assert result.exit_code == EXIT_INPUT_ERROR
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert data["exit_code"] == EXIT_INPUT_ERROR
        assert "--print" in data["message"]
        assert "--json" in data["message"]
        assert not out.exists()

    def test_root_json_rewrite_rejects_print_combination(
        self, source_file: str, style_file: str, tmp_path: Path
    ) -> None:
        """Root-level --json also rejects rewrite --print for JSON-only stdout."""
        out = tmp_path / "out_root_json_print_conflict.txt"
        result = runner.invoke(
            app,
            [
                "--json",
                "rewrite",
                "--source",
                source_file,
                "--style",
                style_file,
                "--out",
                str(out),
                "--print",
            ],
        )
        assert result.exit_code == EXIT_INPUT_ERROR
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert data["exit_code"] == EXIT_INPUT_ERROR
        assert "--print" in data["message"]
        assert "--json" in data["message"]
        assert not out.exists()


# ── JSON output hygiene ─────────────────────────────────────────


class TestJsonHygiene:
    """JSON output correctness and isolation."""

    def test_health_json_stdout_only(self) -> None:
        """Health --json stdout is valid JSON with no stderr leakage."""
        result = runner.invoke(app, ["health", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, dict)
        # Stderr may contain JSONL log lines
        if result.stderr:
            for line in result.stderr.splitlines():
                line = line.strip()
                if line:
                    log_entry = json.loads(line)
                    assert isinstance(log_entry, dict)

    def test_diff_facts_json_stdout_only(self, source_file: str, output_file: str) -> None:
        """Diff-facts --json stdout is valid JSON."""
        result = runner.invoke(app, ["diff-facts", source_file, output_file, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    def test_scrub_json_stdout_valid(self, output_file: str) -> None:
        """Scrub --audit --json stdout is valid JSON."""
        result = runner.invoke(app, ["scrub", output_file, "--audit", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    def test_all_json_responses_have_status_field(self) -> None:
        """Every JSON response includes a status field."""
        result = runner.invoke(app, ["health", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "status" in data

    def test_json_error_also_has_status_field(self) -> None:
        """Error JSON responses include a status field."""
        result = runner.invoke(app, ["verify", "nonexistent_status_test.txt", "--json"])
        assert result.exit_code != 0
        data = json.loads(result.stdout)
        assert data["status"] == "error"


# ── JSON render function direct tests ─────────────────────────────


class TestJsonRenderFunctions:
    """Direct tests of JSON render output functions with synthetic data."""

    def test_render_health_json_default(self, capsys: pytest.CaptureFixture[str]) -> None:
        """render_health with JSON includes all keys."""
        render_health(Config(), json_mode=True, config_valid=True, config_error=None, no_color=True)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "ok"
        assert data["config_valid"] is True
        assert data["config_error"] is None
        assert "commands" in data
        assert "version" in data

    def test_render_health_json_config_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        """render_health JSON includes config_error field."""
        render_health(
            Config(), json_mode=True, config_valid=False, config_error="ValueError", no_color=True
        )
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["config_valid"] is False
        assert data["config_error"] == "ValueError"

    def test_render_verify_json_score_none(self, capsys: pytest.CaptureFixture[str]) -> None:
        """render_verify_result JSON with None score/label."""
        result = VerifyResult(provider="local", model="test", score=None, label=None)
        render_verify_result(result, json_mode=True, no_color=True)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["score"] is None
        assert data["label"] is None
        assert data["provider"] == "local"

    def test_render_verify_json_cache_hit(self, capsys: pytest.CaptureFixture[str]) -> None:
        """render_verify_result JSON with cache_hit."""
        result = VerifyResult(
            provider="local",
            model="test",
            score=0.85,
            label="human",
            cache_hit=True,
            duration_ms=5.0,
        )
        render_verify_result(result, json_mode=True, no_color=True)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["cache_hit"] is True
        assert data["score"] == 0.85

    def test_render_scrub_json_empty_findings(self, capsys: pytest.CaptureFixture[str]) -> None:
        """render_scrub_result JSON with no findings."""
        report = ScrubReport(findings=())
        result = ScrubResult(report=report, audit_only=True, output_path=None)
        render_scrub_result(result, json_mode=True, no_color=True)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["findings_count"] == 0
        assert data["findings"] == []
        assert data["audit_only"] is True

    def test_render_scrub_json_removed_finding(self, capsys: pytest.CaptureFixture[str]) -> None:
        """render_scrub_result JSON includes removed flag."""
        finding = ScrubFinding(
            category="timestamp",
            location="header",
            description="Found timestamp",
            removed=True,
        )
        report = ScrubReport(findings=(finding,), modifications=1)
        result = ScrubResult(report=report, audit_only=False, output_path="/tmp/out.txt")
        render_scrub_result(result, json_mode=True, no_color=True)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["modifications"] == 1
        assert len(data["findings"]) == 1
        assert data["findings"][0]["removed"] is True
        assert data["output_path"] is not None

    def test_render_diff_facts_json_with_counts(self, capsys: pytest.CaptureFixture[str]) -> None:
        """render_diff_facts_result JSON includes count and drift fields."""
        anchor = FactAnchor(text="fact", category="claim", position=0)
        report = FactDiffReport(
            omissions=(anchor,),
            additions=(),
            contradictions=(),
            preservation_score=0.85,
            total_source_anchors=3,
            total_candidate_anchors=2,
        )
        result = DiffFactsResult(
            report=report, source_chars=100, candidate_chars=80, duration_ms=10.0
        )
        render_diff_facts_result(result, json_mode=True, no_color=True)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["preservation_score"] == 0.85
        assert data["omissions"] == 1
        assert data["additions"] == 0
        assert data["contradictions"] == 0
        assert data["has_drift"] is True

    def test_render_rewrite_json_all_keys(self, capsys: pytest.CaptureFixture[str]) -> None:
        """render_rewrite_result JSON includes all expected keys."""
        result = RewriteResult(
            output_path="/tmp/output.txt",
            input_chars=100,
            output_chars=80,
            repair_attempts=2,
            preservation_score=0.95,
            duration_ms=500.0,
        )
        render_rewrite_result(result, json_mode=True, no_color=True)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "ok"
        assert data["output_path"] == "/tmp/output.txt"
        assert data["input_chars"] == 100
        assert data["output_chars"] == 80
        assert data["repair_attempts"] == 2
        assert data["preservation_score"] == 0.95
        assert data["duration_ms"] == 500.0
