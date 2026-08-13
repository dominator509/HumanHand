"""Unit tests for the NullLogger (strict-local logging)."""

from __future__ import annotations

import pytest

from humanhand.infra.privacy.null_logger import NullLogger


class TestNullLogger:
    def test_events_are_discarded(self, capsys: pytest.CaptureFixture[str]) -> None:
        logger = NullLogger()
        logger.log("rewrite.start", level="info", source_length=42)
        logger.log("rewrite.done", level="debug", provider="local", text="secret user text")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_event_count_increments(self) -> None:
        logger = NullLogger()
        assert logger.event_count == 0
        logger.log("a.start")
        logger.log("b.start", level="warning", attempts=3)
        logger.log("c.start", note="any fields are accepted")
        assert logger.event_count == 3

    def test_callable_with_arbitrary_fields(self) -> None:
        logger = NullLogger()
        logger.log("event.one", level="error", key="value", num=7, flag=True)
        logger.log("event.two")
        assert logger.event_count == 2

    def test_accepts_events_without_fields(self) -> None:
        logger = NullLogger()
        logger.log(event="rewrite.start")
        logger.log(event="rewrite.done", level="info", provider="local")
        assert logger.event_count == 2
