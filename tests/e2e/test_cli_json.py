"""E2E tests for JSON-only stdout mode across all CLI commands."""

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

    def test_json_rewrite_missing_source_error_shape(self, style_file: str) -> None:
        """Rewrite with missing source in JSON mode produces valid error JSON."""
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
