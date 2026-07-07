"""Unit tests for the logging module focusing on structured log field contracts.

Redaction behavior is covered by test_redaction.py — these tests focus on
field structure, emission mechanics, and helper functions.
"""

from __future__ import annotations

import json
import re

import pytest

from humanhand.infra.logging import (
    _build_log_record,
    _emit,
    _iso_timestamp_now,
    log_debug,
    log_error,
    log_info,
    log_warning,
    safe_length,
    safe_sha256_prefix,
)

# ---------------------------------------------------------------------------
# _build_log_record — record structure and field contracts
# ---------------------------------------------------------------------------


class TestBuildLogRecord:
    """_build_log_record produces correctly structured records."""

    def test_required_fields_present(self) -> None:
        """Record always contains timestamp, level, event, message."""
        record = _build_log_record("info", "test.event", "Test message")
        assert "timestamp" in record
        assert record["level"] == "info"
        assert record["event"] == "test.event"
        assert record["message"] == "Test message"

    def test_timestamp_iso8601_format(self) -> None:
        """Timestamp field is ISO-8601 UTC (YYYY-MM-DDTHH:MM:SSZ)."""
        record = _build_log_record("info", "test.event", "Test")
        ts = record["timestamp"]
        assert isinstance(ts, str)
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", ts), (
            f"Timestamp '{ts}' does not match ISO-8601 format"
        )

    def test_message_redacted(self) -> None:
        """Message string passes through _redact_string."""
        record = _build_log_record(
            "info",
            "test.event",
            "Using key sk-abcdefghijklmnopqrstuvwxyz12345",
        )
        assert "sk-abcdefghijklmnopqrstuvwxyz12345" not in record["message"]
        assert "<REDACTED_KEY>" in record["message"]

    def test_extra_fields_included(self) -> None:
        """All documented extra fields are passed through."""
        record = _build_log_record(
            "info",
            "test.event",
            "Test",
            extra={
                "elapsed_ms": 150.5,
                "endpoint_host": "api.openai.com",
                "input_length": 1024,
                "output_length": 512,
                "sha256_prefix": "abcdef01",
                "cache_hit": True,
                "attempt": 2,
                "retry_reason": "http_503",
                "model": "gpt-4o-mini",
            },
        )
        assert record["elapsed_ms"] == 150.5
        assert record["endpoint_host"] == "api.openai.com"
        assert record["input_length"] == 1024
        assert record["output_length"] == 512
        assert record["sha256_prefix"] == "abcdef01"
        assert record["cache_hit"] is True
        assert record["attempt"] == 2
        assert record["retry_reason"] == "http_503"
        assert record["model"] == "gpt-4o-mini"

    def test_missing_extra_fields_do_not_appear(self) -> None:
        """When no extras are provided, no extra keys exist in the record."""
        record = _build_log_record("info", "test.event", "Test")
        assert "elapsed_ms" not in record
        assert "endpoint_host" not in record
        assert "input_length" not in record
        assert "output_length" not in record
        assert "sha256_prefix" not in record
        assert "cache_hit" not in record
        assert "attempt" not in record
        assert "retry_reason" not in record
        assert "model" not in record

    def test_none_extra_values_preserved(self) -> None:
        """Explicit None values in extra are included as-is."""
        record = _build_log_record(
            "info",
            "test.event",
            "Test",
            extra={"elapsed_ms": None, "model": None},
        )
        assert record.get("elapsed_ms") is None
        assert record.get("model") is None

    def test_secret_key_in_extra_redacted(self) -> None:
        """Extra with secret-like key name is redacted to <REDACTED_SECRET>."""
        record = _build_log_record(
            "info",
            "test.event",
            "Test",
            extra={"api_key": "sk-abc123"},
        )
        assert record["api_key"] == "<REDACTED_SECRET>"

    def test_never_log_key_in_extra_redacted(self) -> None:
        """Extra with never-log key name is redacted to <REDACTED>."""
        record = _build_log_record(
            "info",
            "test.event",
            "Test",
            extra={"source_text": "secret user writing"},
        )
        assert record["source_text"] == "<REDACTED>"

    def test_primitive_types_in_extra(self) -> None:
        """int, float, bool, str pass through unchanged in extras."""
        record = _build_log_record(
            "info",
            "test.event",
            "Test",
            extra={
                "int_val": 42,
                "float_val": 3.14,
                "bool_val": True,
                "str_val": "safe text",
            },
        )
        assert record["int_val"] == 42
        assert record["float_val"] == 3.14
        assert record["bool_val"] is True
        assert record["str_val"] == "safe text"

    def test_nested_dict_extra_redacted(self) -> None:
        """Nested dicts in extras are recursively redacted."""
        record = _build_log_record(
            "info",
            "test.event",
            "Test",
            extra={
                "metadata": {
                    "model": "gpt-4o",
                    "api_key": "sk-secret",
                }
            },
        )
        assert record["metadata"]["model"] == "gpt-4o"
        assert record["metadata"]["api_key"] == "<REDACTED_SECRET>"

    def test_bytes_in_extra_replaced(self) -> None:
        """Bytes values in extras are replaced with a length descriptor."""
        record = _build_log_record(
            "info",
            "test.event",
            "Test",
            extra={"binary": b"\x00\x01\x02"},
        )
        assert isinstance(record["binary"], str)
        assert "bytes" in record["binary"]

    def test_partial_extra_fields(self) -> None:
        """Only provided extra fields appear; missing ones do not."""
        record = _build_log_record(
            "info",
            "test.event",
            "Test",
            extra={"elapsed_ms": 42.0, "model": "gpt-4o"},
        )
        assert record["elapsed_ms"] == 42.0
        assert record["model"] == "gpt-4o"
        # These should not appear
        assert "endpoint_host" not in record
        assert "input_length" not in record
        assert "output_length" not in record
        assert "sha256_prefix" not in record
        assert "cache_hit" not in record
        assert "attempt" not in record
        assert "retry_reason" not in record


# ---------------------------------------------------------------------------
# _iso_timestamp_now — timestamp format compliance
# ---------------------------------------------------------------------------


class TestIsoTimestamp:
    """_iso_timestamp_now returns valid ISO-8601 timestamps."""

    def test_returns_string(self) -> None:
        ts = _iso_timestamp_now()
        assert isinstance(ts, str)

    def test_iso8601_format(self) -> None:
        ts = _iso_timestamp_now()
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", ts), (
            f"Timestamp '{ts}' is not ISO-8601"
        )

    def test_ends_with_z(self) -> None:
        ts = _iso_timestamp_now()
        assert ts.endswith("Z"), "Timestamp must end with Z for UTC"

    def test_date_components_valid(self) -> None:
        ts = _iso_timestamp_now()
        date_part = ts.split("T")[0]
        parts = date_part.split("-")
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        assert 2024 <= year <= 2030, f"Year {year} out of expected range"
        assert 1 <= month <= 12, f"Month {month} out of range"
        assert 1 <= day <= 31, f"Day {day} out of range"


# ---------------------------------------------------------------------------
# _emit — JSONL emission to stderr
# ---------------------------------------------------------------------------


class TestEmit:
    """_emit writes valid JSONL to stderr."""

    def test_emits_jsonl_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        record = {
            "timestamp": "2025-01-01T00:00:00Z",
            "level": "info",
            "event": "test",
            "message": "test",
        }
        _emit(record)
        captured = capsys.readouterr()
        assert captured.out == "", "Nothing should be written to stdout"
        assert captured.err, "Expected output on stderr"
        parsed = json.loads(captured.err.strip())
        assert parsed == record

    def test_fallback_on_serialization_failure(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Non-serializable values trigger the error fallback record."""

        class NonSerializable:
            pass

        record = {
            "timestamp": "2025-01-01T00:00:00Z",
            "level": "info",
            "event": "test",
            "message": "test",
            "bad_value": NonSerializable(),
        }
        _emit(record)
        captured = capsys.readouterr()
        parsed = json.loads(captured.err.strip())
        assert parsed["level"] == "error"
        assert parsed["event"] == "log.write_failed"
        assert "message" in parsed

    def test_stdout_empty_after_emit(self, capsys: pytest.CaptureFixture[str]) -> None:
        """_emit must not write anything to stdout."""
        record = {
            "timestamp": "2025-01-01T00:00:00Z",
            "level": "debug",
            "event": "test.stdout",
            "message": "stdout check",
        }
        _emit(record)
        captured = capsys.readouterr()
        assert captured.out == ""


# ---------------------------------------------------------------------------
# Log level functions — correct level in emitted records
# ---------------------------------------------------------------------------


class TestLogLevelFunctions:
    """Each log level function produces the correct level field."""

    def test_log_info_produces_info_level(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_info("test.info_event", "info message")
        captured = capsys.readouterr()
        record = json.loads(captured.err.strip())
        assert record["level"] == "info"
        assert record["event"] == "test.info_event"
        assert record["message"] == "info message"

    def test_log_error_produces_error_level(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_error("test.error_event", "error message")
        captured = capsys.readouterr()
        record = json.loads(captured.err.strip())
        assert record["level"] == "error"
        assert record["event"] == "test.error_event"

    def test_log_warning_produces_warning_level(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_warning("test.warning_event", "warning message")
        captured = capsys.readouterr()
        record = json.loads(captured.err.strip())
        assert record["level"] == "warning"
        assert record["event"] == "test.warning_event"

    def test_log_debug_produces_debug_level(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_debug("test.debug_event", "debug message")
        captured = capsys.readouterr()
        record = json.loads(captured.err.strip())
        assert record["level"] == "debug"
        assert record["event"] == "test.debug_event"

    def test_all_functions_include_timestamp(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Every log function includes an ISO-8601 timestamp."""
        log_info("test.ts", "test")
        captured = capsys.readouterr()
        record = json.loads(captured.err.strip())
        assert "timestamp" in record
        assert re.match(r"^\d{4}-\d{2}-\d{2}T", record["timestamp"])

    def test_all_functions_emit_only_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Every log function writes exclusively to stderr."""
        log_info("test.stderr1", "test")
        log_error("test.stderr2", "test")
        log_warning("test.stderr3", "test")
        log_debug("test.stderr4", "test")
        captured = capsys.readouterr()
        assert captured.out == "", "No output should appear on stdout"


# ---------------------------------------------------------------------------
# safe_length / safe_sha256_prefix helpers
# ---------------------------------------------------------------------------


class TestSafeHelpers:
    """safe_length and safe_sha256_prefix work correctly."""

    def test_safe_length_with_text(self) -> None:
        assert safe_length("hello world") == 11

    def test_safe_length_empty_string(self) -> None:
        assert safe_length("") == 0

    def test_safe_length_none(self) -> None:
        assert safe_length(None) is None

    def test_safe_sha256_prefix_length(self) -> None:
        prefix = safe_sha256_prefix("hello world")
        assert len(prefix) == 8

    def test_safe_sha256_prefix_deterministic(self) -> None:
        assert safe_sha256_prefix("hello") == safe_sha256_prefix("hello")

    def test_safe_sha256_prefix_custom_length(self) -> None:
        prefix = safe_sha256_prefix("test", prefix_len=16)
        assert len(prefix) == 16

    def test_safe_sha256_prefix_hex_chars_only(self) -> None:
        prefix = safe_sha256_prefix("hello")
        assert all(c in "0123456789abcdef" for c in prefix)

    def test_safe_sha256_prefix_differs_for_different_inputs(self) -> None:
        assert safe_sha256_prefix("input_a") != safe_sha256_prefix("input_b")
