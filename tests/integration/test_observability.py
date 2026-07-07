"""Integration-level observability tests.

Tests focus on stdout/stderr separation, JSONL log event contracts,
redaction guarantees, and timing values across CLI commands.

Uses CliRunner from typer.testing with synthetic data. No live network.
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from humanhand.cli.app import app
from humanhand.infra.files import read_text_strict

runner = CliRunner()

# Sentinel strings that must never appear in log output
SENTINEL_USER_TEXT = "SENTINEL_USER_TEXT_1234567890_OBSERVABILITY"
SENTINEL_API_KEY = "sk-sentinel-api-key-1234567890abcdefghijklmnop"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def source_file() -> str:
    """Create a temporary source text file for diff-facts tests."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(
            "The Eiffel Tower is 330 meters tall. "
            "It was completed in 1889 and receives 7 million visitors annually.\n"
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


@pytest.fixture
def sentinel_file() -> str:
    """Create a file containing sentinel user text for redaction tests."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(f"{SENTINEL_USER_TEXT}\n")
    return f.name


@pytest.fixture
def api_key_file() -> str:
    """Create a file containing a fake API key for secret redaction tests."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(f"This file has an api key: {SENTINEL_API_KEY}\n")
    return f.name


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_jsonl_lines(text: str) -> list[dict[str, Any]]:
    """Parse JSONL lines from stderr text (lines starting with '{')."""
    return [json.loads(line) for line in text.splitlines() if line.strip().startswith("{")]


# ---------------------------------------------------------------------------
# stdout / stderr separation
# ---------------------------------------------------------------------------


class TestStdoutStderrSeparation:
    """Logs go to stderr, results to stdout."""

    def test_health_text_separation(self) -> None:
        """Health text mode: result on stdout, JSONL logs on stderr."""
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        assert "health: ok" in result.stdout
        log_lines = parse_jsonl_lines(result.stderr)
        assert len(log_lines) >= 2

    def test_health_json_separation(self) -> None:
        """Health JSON mode: JSON result on stdout, JSONL logs on stderr."""
        result = runner.invoke(app, ["health", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        log_lines = parse_jsonl_lines(result.stderr)
        assert len(log_lines) >= 2
        assert any(line["event"] == "health.start" for line in log_lines)

    def test_verify_json_separation(self, output_file: str) -> None:
        """Verify JSON mode: result on stdout, logs on stderr."""
        result = runner.invoke(app, ["verify", output_file, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        log_lines = parse_jsonl_lines(result.stderr)
        assert len(log_lines) >= 2

    def test_diff_facts_separation(self, source_file: str, output_file: str) -> None:
        """Diff-facts mode: result on stdout, logs on stderr."""
        result = runner.invoke(app, ["diff-facts", source_file, output_file])
        assert result.exit_code == 0
        assert "preservation" in result.stdout.lower()
        log_lines = parse_jsonl_lines(result.stderr)
        assert len(log_lines) >= 2

    def test_scrub_separation(self, output_file: str) -> None:
        """Scrub audit mode: results on stdout, logs on stderr."""
        result = runner.invoke(app, ["scrub", output_file, "--audit"])
        assert result.exit_code == 0
        assert "Audit" in result.stdout
        log_lines = parse_jsonl_lines(result.stderr)
        assert len(log_lines) >= 2

    def test_error_on_stderr(self) -> None:
        """Error paths output JSONL error events to stderr."""
        result = runner.invoke(app, ["verify", "nonexistent_separation_test.txt"])
        assert result.exit_code != 0
        log_lines = parse_jsonl_lines(result.stderr)
        assert any(line.get("event") == "verify.error" for line in log_lines)

    def test_stdout_has_no_stderr_contamination(self, output_file: str) -> None:
        """stdout result JSON should not contain log-field keys."""
        result = runner.invoke(app, ["verify", output_file, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        # Stdout JSON should have command-specific keys, not log-internal ones
        assert "timestamp" not in data
        assert "level" not in data
        assert "event" not in data


# ---------------------------------------------------------------------------
# Required log events per command
# ---------------------------------------------------------------------------


class TestRequiredLogEvents:
    """CLI commands produce the expected log event names."""

    def test_health_has_start_and_end_events(self) -> None:
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        log_lines = parse_jsonl_lines(result.stderr)
        events = [line["event"] for line in log_lines]
        assert "health.start" in events, "Missing health.start event"
        assert "health.end" in events, "Missing health.end event"

    def test_verify_has_start_and_end_events(self, output_file: str) -> None:
        result = runner.invoke(app, ["verify", output_file])
        assert result.exit_code == 0
        log_lines = parse_jsonl_lines(result.stderr)
        events = [line["event"] for line in log_lines]
        assert "verify.start" in events, "Missing verify.start event"
        assert "verify.end" in events, "Missing verify.end event"

    def test_diff_facts_has_start_and_end_events(self, source_file: str, output_file: str) -> None:
        result = runner.invoke(app, ["diff-facts", source_file, output_file])
        assert result.exit_code == 0
        log_lines = parse_jsonl_lines(result.stderr)
        events = [line["event"] for line in log_lines]
        assert "diff_facts.start" in events, "Missing diff_facts.start event"
        assert "diff_facts.end" in events, "Missing diff_facts.end event"

    def test_scrub_audit_has_start_and_end_events(self, output_file: str) -> None:
        result = runner.invoke(app, ["scrub", output_file, "--audit"])
        assert result.exit_code == 0
        log_lines = parse_jsonl_lines(result.stderr)
        events = [line["event"] for line in log_lines]
        assert "scrub.start" in events, "Missing scrub.start event"
        assert "scrub.end" in events, "Missing scrub.end event"

    def test_verify_error_has_error_event(self) -> None:
        result = runner.invoke(app, ["verify", "nonexistent_req_log.txt"])
        assert result.exit_code != 0
        log_lines = parse_jsonl_lines(result.stderr)
        events = [line["event"] for line in log_lines]
        assert "verify.error" in events, "Missing verify.error event"

    def test_scrub_error_has_error_event(self) -> None:
        result = runner.invoke(app, ["scrub", "nonexistent_scrub_log.txt", "--audit"])
        assert result.exit_code != 0
        log_lines = parse_jsonl_lines(result.stderr)
        events = [line["event"] for line in log_lines]
        assert "scrub.error" in events, "Missing scrub.error event"

    def test_diff_facts_error_has_error_event(self) -> None:
        result = runner.invoke(
            app,
            [
                "diff-facts",
                "nonexistent_a_log.txt",
                "nonexistent_b_log.txt",
            ],
        )
        assert result.exit_code != 0
        log_lines = parse_jsonl_lines(result.stderr)
        events = [line["event"] for line in log_lines]
        assert "diff_facts.error" in events, "Missing diff_facts.error event"


# ---------------------------------------------------------------------------
# Log event levels
# ---------------------------------------------------------------------------


class TestLogEventLevels:
    """Log events have the correct severity levels."""

    def test_start_and_end_events_are_info(self, output_file: str, source_file: str) -> None:
        """Success path .start and .end events should be level 'info'."""
        for cmd_args in [
            ["health"],
            ["verify", output_file],
            ["diff-facts", source_file, output_file],
            ["scrub", output_file, "--audit"],
        ]:
            result = runner.invoke(app, cmd_args)
            assert result.exit_code == 0
            log_lines = parse_jsonl_lines(result.stderr)
            for line in log_lines:
                event = line["event"]
                if event.endswith(".start") or event.endswith(".end"):
                    assert line["level"] == "info", (
                        f"Event '{event}' has level '{line['level']}', expected 'info'"
                    )

    def test_error_events_are_error_level(self) -> None:
        result = runner.invoke(app, ["verify", "nonexistent_level_test.txt"])
        assert result.exit_code != 0
        log_lines = parse_jsonl_lines(result.stderr)
        for line in log_lines:
            if "error" in line["event"]:
                assert line["level"] == "error", (
                    f"Event '{line['event']}' has level '{line['level']}', expected 'error'"
                )

    def test_known_levels_only(self, output_file: str) -> None:
        """All log levels are in the allowed set (debug, info, warning, error)."""
        allowed = {"debug", "info", "warning", "error"}
        result = runner.invoke(app, ["verify", output_file])
        assert result.exit_code == 0
        log_lines = parse_jsonl_lines(result.stderr)
        for line in log_lines:
            assert line["level"] in allowed, (
                f"Unexpected level '{line['level']}' in event '{line['event']}'"
            )


# ---------------------------------------------------------------------------
# No user text in log output
# ---------------------------------------------------------------------------


class TestNoUserTextInLogs:
    """No user text appears in any log output."""

    def test_verify_no_sentinel_in_stderr(self, sentinel_file: str) -> None:
        """Verify command stderr must not contain sentinel user text."""
        result = runner.invoke(app, ["verify", sentinel_file])
        assert result.exit_code == 0
        assert SENTINEL_USER_TEXT not in result.stderr, "Sentinel user text found in verify stderr"

    def test_scrub_audit_no_sentinel_in_stderr(self, sentinel_file: str) -> None:
        """Scrub command stderr must not contain sentinel user text."""
        result = runner.invoke(app, ["scrub", sentinel_file, "--audit"])
        assert result.exit_code == 0
        assert SENTINEL_USER_TEXT not in result.stderr, "Sentinel user text found in scrub stderr"

    def test_diff_facts_no_sentinel_in_stderr(self, source_file: str, sentinel_file: str) -> None:
        """Diff-facts command stderr must not contain sentinel user text."""
        result = runner.invoke(app, ["diff-facts", source_file, sentinel_file])
        assert result.exit_code == 0
        assert SENTINEL_USER_TEXT not in result.stderr, (
            "Sentinel user text found in diff-facts stderr"
        )

    def test_error_path_no_sentinel_in_stderr(self) -> None:
        """Error log paths also must not contain user text."""
        result = runner.invoke(app, ["verify", "nonexistent_sentinel_test.txt"])
        assert result.exit_code != 0
        assert SENTINEL_USER_TEXT not in result.stderr, "Sentinel user text found in error stderr"


# ---------------------------------------------------------------------------
# No secrets in log output
# ---------------------------------------------------------------------------


class TestNoSecretsInLogs:
    """No secrets appear in any log output."""

    def test_verify_no_api_key_in_stderr(self, api_key_file: str) -> None:
        """Verify stderr must not contain API key strings from file content."""
        result = runner.invoke(app, ["verify", api_key_file])
        assert result.exit_code == 0
        assert SENTINEL_API_KEY not in result.stderr, "Sentinel API key found in verify stderr"

    def test_scrub_audit_no_api_key_in_stderr(self, api_key_file: str) -> None:
        """Scrub stderr must not contain API key strings."""
        result = runner.invoke(app, ["scrub", api_key_file, "--audit"])
        assert result.exit_code == 0
        assert SENTINEL_API_KEY not in result.stderr, "Sentinel API key found in scrub stderr"

    def test_diff_facts_no_api_key_in_stderr(self, source_file: str, api_key_file: str) -> None:
        """Diff-facts stderr must not contain API key strings."""
        result = runner.invoke(app, ["diff-facts", source_file, api_key_file])
        assert result.exit_code == 0
        assert SENTINEL_API_KEY not in result.stderr, "Sentinel API key found in diff-facts stderr"


# ---------------------------------------------------------------------------
# Valid JSONL output
# ---------------------------------------------------------------------------


class TestValidJsonl:
    """All log output is valid JSONL with required fields."""

    def test_every_stderr_line_parses_as_json(self, output_file: str) -> None:
        """Every non-empty stderr line is valid JSON."""
        result = runner.invoke(app, ["verify", output_file])
        assert result.exit_code == 0
        for line in result.stderr.splitlines():
            line = line.strip()
            if line:
                parsed = json.loads(line)
                assert isinstance(parsed, dict)

    def test_health_stderr_is_valid_jsonl(self) -> None:
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        for line in result.stderr.splitlines():
            line = line.strip()
            if line:
                parsed = json.loads(line)
                assert isinstance(parsed, dict)

    def test_required_fields_in_every_log_line(self, output_file: str) -> None:
        """Every log line has all four required fields of correct types."""
        result = runner.invoke(app, ["verify", output_file])
        assert result.exit_code == 0
        log_lines = parse_jsonl_lines(result.stderr)
        for line in log_lines:
            assert isinstance(line["timestamp"], str), "timestamp must be string"
            assert len(line["timestamp"]) > 0, "timestamp must not be empty"
            assert isinstance(line["level"], str), "level must be string"
            assert isinstance(line["event"], str), "event must be string"
            assert isinstance(line["message"], str), "message must be string"

    def test_level_is_known_value(self, output_file: str) -> None:
        """Level field must be one of the four allowed levels."""
        allowed = {"debug", "info", "warning", "error"}
        result = runner.invoke(app, ["verify", output_file])
        assert result.exit_code == 0
        log_lines = parse_jsonl_lines(result.stderr)
        for line in log_lines:
            assert line["level"] in allowed, f"Unknown level: {line['level']}"

    def test_timestamp_iso8601_across_commands(self, source_file: str, output_file: str) -> None:
        """Timestamp in every log line is ISO-8601 compatible."""
        for cmd_args in [
            ["health"],
            ["verify", output_file],
            ["diff-facts", source_file, output_file],
            ["scrub", output_file, "--audit"],
        ]:
            result = runner.invoke(app, cmd_args)
            assert result.exit_code == 0
            for line in result.stderr.splitlines():
                line = line.strip()
                if not line:
                    continue
                parsed = json.loads(line)
                ts = parsed["timestamp"]
                assert re.match(r"^\d{4}-\d{2}-\d{2}T", ts), f"Timestamp '{ts}' is not ISO-8601"

    def test_message_field_is_string(self, output_file: str) -> None:
        """Message field is always a string type."""
        result = runner.invoke(app, ["verify", output_file])
        assert result.exit_code == 0
        log_lines = parse_jsonl_lines(result.stderr)
        for line in log_lines:
            assert isinstance(line["message"], str)


# ---------------------------------------------------------------------------
# Timing values
# ---------------------------------------------------------------------------


class TestTimingValues:
    """Timing values in log output are numeric and positive."""

    def test_verify_has_elapsed_ms(self, output_file: str) -> None:
        """Verify .end event should have elapsed_ms (may be 0.0 for fast ops)."""
        result = runner.invoke(app, ["verify", output_file])
        assert result.exit_code == 0
        log_lines = parse_jsonl_lines(result.stderr)
        end_events = [ev for ev in log_lines if ev["event"] == "verify.end"]
        assert len(end_events) >= 1
        for event in end_events:
            assert "elapsed_ms" in event
            assert isinstance(event["elapsed_ms"], int | float)
            assert event["elapsed_ms"] >= 0

    def test_diff_facts_has_elapsed_ms(self, source_file: str, output_file: str) -> None:
        """Diff-facts .end event should have elapsed_ms."""
        result = runner.invoke(app, ["diff-facts", source_file, output_file])
        assert result.exit_code == 0
        log_lines = parse_jsonl_lines(result.stderr)
        end_events = [ev for ev in log_lines if ev["event"] == "diff_facts.end"]
        assert len(end_events) >= 1
        for event in end_events:
            assert "elapsed_ms" in event
            assert isinstance(event["elapsed_ms"], int | float)

    def test_scrub_has_elapsed_ms(self, output_file: str) -> None:
        """Scrub .end event should have elapsed_ms."""
        result = runner.invoke(app, ["scrub", output_file, "--audit"])
        assert result.exit_code == 0
        log_lines = parse_jsonl_lines(result.stderr)
        end_events = [ev for ev in log_lines if ev["event"] == "scrub.end"]
        assert len(end_events) >= 1
        for event in end_events:
            assert "elapsed_ms" in event
            assert isinstance(event["elapsed_ms"], int | float)

    def test_verify_end_elapsed_ms_positive(self, output_file: str) -> None:
        """Verify elapsed_ms is a positive number."""
        result = runner.invoke(app, ["verify", output_file])
        assert result.exit_code == 0
        log_lines = parse_jsonl_lines(result.stderr)
        for line in log_lines:
            if "elapsed_ms" in line:
                val = line["elapsed_ms"]
                if val is not None:
                    assert isinstance(val, int | float)
                    assert val >= 0


# ---------------------------------------------------------------------------
# Event-specific extra fields
# ---------------------------------------------------------------------------


class TestEventSpecificFields:
    """Log events contain appropriate extra fields."""

    def test_verify_start_has_provider_and_model(self, output_file: str) -> None:
        """Verify start event includes provider and model fields."""
        result = runner.invoke(app, ["verify", output_file])
        assert result.exit_code == 0
        log_lines = parse_jsonl_lines(result.stderr)
        start_events = [ev for ev in log_lines if ev["event"] == "verify.start"]
        assert len(start_events) >= 1
        event = start_events[0]
        assert "provider" in event
        assert "model" in event

    def test_verify_end_has_cache_hit(self, output_file: str) -> None:
        """Verify end event includes cache_hit field."""
        result = runner.invoke(app, ["verify", output_file])
        assert result.exit_code == 0
        log_lines = parse_jsonl_lines(result.stderr)
        end_events = [ev for ev in log_lines if ev["event"] == "verify.end"]
        assert len(end_events) >= 1
        event = end_events[0]
        assert "cache_hit" in event
        assert isinstance(event["cache_hit"], bool)

    def test_scrub_start_has_audit_only(self, output_file: str) -> None:
        """Scrub start event includes audit_only field."""
        result = runner.invoke(app, ["scrub", output_file, "--audit"])
        assert result.exit_code == 0
        log_lines = parse_jsonl_lines(result.stderr)
        start_events = [ev for ev in log_lines if ev["event"] == "scrub.start"]
        assert len(start_events) >= 1
        event = start_events[0]
        assert "audit_only" in event
        assert event["audit_only"] is True

    def test_scrub_end_has_findings_count(self, output_file: str) -> None:
        """Scrub end event includes findings count."""
        result = runner.invoke(app, ["scrub", output_file, "--audit"])
        assert result.exit_code == 0
        log_lines = parse_jsonl_lines(result.stderr)
        end_events = [ev for ev in log_lines if ev["event"] == "scrub.end"]
        assert len(end_events) >= 1
        event = end_events[0]
        assert "findings" in event
        assert isinstance(event["findings"], int)

    def test_health_end_has_config_valid(self) -> None:
        """Health end event includes config_valid field."""
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        log_lines = parse_jsonl_lines(result.stderr)
        end_events = [ev for ev in log_lines if ev["event"] == "health.end"]
        assert len(end_events) >= 1
        event = end_events[0]
        assert "config_valid" in event
        assert isinstance(event["config_valid"], bool)


# ---------------------------------------------------------------------------
# Command-end counters
# ---------------------------------------------------------------------------


class TestCommandCounters:
    """Command-scoped counter events are emitted to stderr."""

    def test_health_emits_command_counters(self) -> None:
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        log_lines = parse_jsonl_lines(result.stderr)
        counter_events = [ev for ev in log_lines if ev["event"] == "command.counters"]
        assert len(counter_events) == 1
        assert isinstance(counter_events[0]["duration_ms"], int | float)

    def test_scrub_emits_command_counters(self, output_file: str) -> None:
        result = runner.invoke(app, ["scrub", output_file, "--audit"])
        assert result.exit_code == 0
        log_lines = parse_jsonl_lines(result.stderr)
        counter_events = [ev for ev in log_lines if ev["event"] == "command.counters"]
        assert len(counter_events) == 1
        assert isinstance(counter_events[0]["duration_ms"], int | float)

    def test_verify_cache_miss_emits_counter_values(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        cache_dir = tmp_path / "cache"
        output_path = tmp_path / "verify.txt"
        text = (
            "The Eiffel Tower is 330 meters tall and was completed in 1889. "
            "It receives approximately 7 million visitors annually.\n"
        )
        output_path.write_text(text, encoding="utf-8")
        monkeypatch.setenv("HUMANHAND_CACHE_DIR", str(cache_dir))

        result = runner.invoke(app, ["verify", str(output_path)])
        assert result.exit_code == 0
        log_lines = parse_jsonl_lines(result.stderr)
        counter_events = [ev for ev in log_lines if ev["event"] == "command.counters"]
        assert len(counter_events) == 1
        event = counter_events[0]
        assert event["detector_calls"] == 1
        assert event["cache_misses"] == 1
        assert event["input_chars"] == len(read_text_strict(str(output_path)))
        assert isinstance(event["duration_ms"], int | float)

    def test_verify_cache_hit_emits_counter_values(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        cache_dir = tmp_path / "cache"
        output_path = tmp_path / "verify.txt"
        output_path.write_text(
            "This text is long enough for a stable local heuristic classification.\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("HUMANHAND_CACHE_DIR", str(cache_dir))

        first = runner.invoke(app, ["verify", str(output_path)])
        assert first.exit_code == 0

        second = runner.invoke(app, ["verify", str(output_path)])
        assert second.exit_code == 0
        log_lines = parse_jsonl_lines(second.stderr)
        counter_events = [ev for ev in log_lines if ev["event"] == "command.counters"]
        assert len(counter_events) == 1
        event = counter_events[0]
        assert event["cache_hits"] == 1
        assert "detector_calls" not in event
        assert isinstance(event["duration_ms"], int | float)
