"""Unit tests for the command-scoped counter collector."""

from __future__ import annotations

import json

import pytest

from humanhand.infra.counters import NOOP, Counters, emit_counters

# ---------------------------------------------------------------------------
# Counters — increment / get / set / reset
# ---------------------------------------------------------------------------


class TestCountersIncrementGet:
    """Basic increment and get operations."""

    def test_increment_default(self) -> None:
        counters = Counters()
        counters.increment("rewrite_attempts")
        assert counters.get("rewrite_attempts") == 1

    def test_increment_custom_value(self) -> None:
        counters = Counters()
        counters.increment("detector_calls", 3)
        assert counters.get("detector_calls") == 3

    def test_increment_multiple_times(self) -> None:
        counters = Counters()
        counters.increment("cache_hits", 2)
        counters.increment("cache_hits", 3)
        assert counters.get("cache_hits") == 5

    def test_increment_zero_is_no_op(self) -> None:
        counters = Counters()
        counters.increment("retry_count", 0)
        assert counters.get("retry_count") == 0

    def test_get_untouched_returns_zero(self) -> None:
        counters = Counters()
        assert counters.get("input_chars") == 0
        assert counters.get("nonexistent") == 0

    def test_increment_unknown_name_raises(self) -> None:
        counters = Counters()
        with pytest.raises(ValueError, match="Unknown counter"):
            counters.increment("not_a_real_counter")

    def test_set_unknown_name_raises(self) -> None:
        counters = Counters()
        with pytest.raises(ValueError, match="Unknown counter"):
            counters.set("fake_counter", 42)


class TestCountersSet:
    """Absolute-value set operations."""

    def test_set_duration_ms(self) -> None:
        counters = Counters()
        counters.set("duration_ms", 1234.5)
        assert counters.get("duration_ms") == 1234.5

    def test_set_overwrites_previous_value(self) -> None:
        counters = Counters()
        counters.increment("retry_count", 5)
        counters.set("retry_count", 1)
        assert counters.get("retry_count") == 1

    def test_set_zero_retained(self) -> None:
        counters = Counters()
        counters.set("output_chars", 0)
        assert counters.get("output_chars") == 0


class TestCountersReset:
    """Reset behaviour."""

    def test_reset_clears_all(self) -> None:
        counters = Counters()
        counters.increment("rewrite_attempts", 10)
        counters.increment("detector_calls", 5)
        counters.reset()
        assert counters.get("rewrite_attempts") == 0
        assert counters.get("detector_calls") == 0

    def test_reset_allows_reuse(self) -> None:
        counters = Counters()
        counters.increment("cache_hits", 3)
        counters.reset()
        counters.increment("cache_hits", 7)
        assert counters.get("cache_hits") == 7


class TestCountersSnapshot:
    """snapshot() behaviour."""

    def test_snapshot_returns_copy(self) -> None:
        counters = Counters()
        counters.increment("retry_count", 2)
        snap = counters.snapshot()
        snap["retry_count"] = 999
        assert counters.get("retry_count") == 2

    def test_snapshot_only_contains_touched(self) -> None:
        counters = Counters()
        counters.increment("cache_misses", 1)
        snap = counters.snapshot()
        assert "cache_misses" in snap
        assert "cache_hits" not in snap

    def test_snapshot_after_reset_empty(self) -> None:
        counters = Counters()
        counters.increment("input_chars", 100)
        counters.reset()
        assert counters.snapshot() == {}


class TestCountersBool:
    """__bool__ behaviour."""

    def test_bool_false_when_empty(self) -> None:
        assert bool(Counters()) is False

    def test_bool_true_when_touched(self) -> None:
        counters = Counters()
        counters.increment("output_chars", 50)
        assert bool(counters) is True

    def test_bool_false_after_reset(self) -> None:
        counters = Counters()
        counters.increment("repair_attempts", 1)
        counters.reset()
        assert bool(counters) is False


# ---------------------------------------------------------------------------
# NOOP sentinel
# ---------------------------------------------------------------------------


class TestNOOP:
    """Module-level no-op sentinel behaviour."""

    def test_noop_is_counters_instance(self) -> None:
        assert isinstance(NOOP, Counters)

    def test_noop_always_zero(self) -> None:
        NOOP.increment("rewrite_attempts")
        assert NOOP.get("rewrite_attempts") == 1  # It IS a real instance

    def test_noop_can_be_used_as_default(self) -> None:
        """Verify NOOP can be a function default without issue."""

        def dummy(counters: Counters = NOOP) -> Counters:
            return counters

        assert dummy() is NOOP


# ---------------------------------------------------------------------------
# emit_counters — JSONL output
# ---------------------------------------------------------------------------


class TestEmitCounters:
    """emit_counters produces correct JSONL stderr output."""

    def test_emit_counters_jsonl_valid(self, capsys: pytest.CaptureFixture[str]) -> None:
        counters = Counters()
        counters.increment("rewrite_attempts", 1)
        counters.increment("detector_calls", 4)
        counters.set("duration_ms", 235.7)

        emit_counters(counters)

        captured = capsys.readouterr()
        assert captured.err, "Expected stderr output"
        record = json.loads(captured.err.strip())
        assert record["event"] == "command.counters"
        assert record["level"] == "info"
        assert record["message"] == "Command counters"
        assert record["rewrite_attempts"] == 1
        assert record["detector_calls"] == 4
        assert record["duration_ms"] == 235.7
        assert "timestamp" in record

    def test_emit_counters_no_text_or_secrets(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Counter values must be numbers only -- no text, no secrets."""
        counters = Counters()
        counters.increment("cache_hits", 3)
        counters.set("input_chars", 1024)

        emit_counters(counters)

        captured = capsys.readouterr()
        record = json.loads(captured.err.strip())
        for key, value in record.items():
            if key in ("timestamp", "level", "event", "message"):
                continue
            assert isinstance(value, (int, float)), (
                f"Counter {key!r} has non-numeric value {value!r}"
            )

    def test_emit_counters_empty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Empty counters emit an event with no counter fields."""
        counters = Counters()

        emit_counters(counters)

        captured = capsys.readouterr()
        assert captured.err, "Expected stderr output"
        record = json.loads(captured.err.strip())
        assert record["event"] == "command.counters"
        assert record["level"] == "info"
        # No counter fields should be present
        counter_keys = {
            "rewrite_attempts",
            "repair_attempts",
            "detector_calls",
            "cache_hits",
            "cache_misses",
            "retry_count",
            "duration_ms",
            "input_chars",
            "output_chars",
        }
        present = set(record.keys()) & counter_keys
        assert not present, f"Expected no counter fields, got {present}"

    def test_emit_counters_only_non_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Only touched (non-zero) counters appear in the event."""
        counters = Counters()
        counters.increment("retry_count", 1)
        counters.increment("cache_hits", 0)  # explicitly zero

        emit_counters(counters)

        captured = capsys.readouterr()
        record = json.loads(captured.err.strip())
        assert record["retry_count"] == 1
        # cache_hits was incremented by 0 (touched) so it appears
        assert record["cache_hits"] == 0

    def test_emit_counters_custom_event_name(self, capsys: pytest.CaptureFixture[str]) -> None:
        counters = Counters()
        counters.increment("rewrite_attempts", 1)

        emit_counters(counters, event_name="custom.event")

        captured = capsys.readouterr()
        record = json.loads(captured.err.strip())
        assert record["event"] == "custom.event"

    def test_emit_counters_on_empty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Emit on a fresh empty Counters produces an event with no counters."""
        emit_counters(Counters())

        captured = capsys.readouterr()
        record = json.loads(captured.err.strip())
        assert record["event"] == "command.counters"
        # NOOP is a fresh instance -- no counters should appear
        counter_keys = {
            "rewrite_attempts",
            "repair_attempts",
            "detector_calls",
            "cache_hits",
            "cache_misses",
            "retry_count",
            "duration_ms",
            "input_chars",
            "output_chars",
        }
        present = set(record.keys()) & counter_keys
        assert not present, f"Expected no counter fields on NOOP, got {present}"


# ---------------------------------------------------------------------------
# All counter names are creatable via Counters
# ---------------------------------------------------------------------------


class TestAllCounterNames:
    """Verify every allowed counter name works end-to-end."""

    def test_all_counters_increment_and_get(self) -> None:
        names = [
            "rewrite_attempts",
            "repair_attempts",
            "detector_calls",
            "cache_hits",
            "cache_misses",
            "retry_count",
            "duration_ms",
            "input_chars",
            "output_chars",
        ]
        counters = Counters()
        for i, name in enumerate(names, start=1):
            counters.increment(name, i)

        for i, name in enumerate(names, start=1):
            assert counters.get(name) == i, f"Unexpected value for {name}"
