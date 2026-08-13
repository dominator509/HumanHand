"""Unit tests for protected spans."""

from __future__ import annotations

import pytest

from humanhand.domain.document_nodes import SourceLocation
from humanhand.domain.protected_spans import (
    ProtectedSpan,
    SpanKind,
    SpanStatus,
    build_protected_span_set,
)


def _span(
    start: int,
    end: int,
    kind: SpanKind = SpanKind.QUOTATION,
    text: str = "x",
) -> ProtectedSpan:
    return ProtectedSpan(
        span_id="",
        kind=kind,
        source_location=SourceLocation(start, end),
        text=text,
    )


class TestBuildProtectedSpanSet:
    def test_assigns_deterministic_ids_in_order(self) -> None:
        span_set = build_protected_span_set(
            (_span(0, 4, SpanKind.DATE, "2024"), _span(10, 20, SpanKind.QUOTATION, "q"))
        )
        assert [span.span_id for span in span_set.spans] == ["s1", "s2"]
        assert span_set.spans[0].kind is SpanKind.DATE
        assert span_set.spans[0].status is SpanStatus.EXTRACTED

    def test_deduplicates_exact_duplicates(self) -> None:
        span_set = build_protected_span_set((_span(0, 4), _span(0, 4), _span(6, 8)))
        assert [span.span_id for span in span_set.spans] == ["s1", "s2"]

    def test_nested_spans_are_tolerated_deterministically(self) -> None:
        # A citation inside a quotation keeps the outer span only; nested
        # or out-of-order candidates never crash the import.
        span_set = build_protected_span_set(
            (_span(0, 40), _span(10, 20, SpanKind.CITATION), _span(15, 18, SpanKind.NUMBER))
        )
        assert [span.source_location.start_offset for span in span_set.spans] == [0]

    def test_rejects_negative_offsets(self) -> None:
        from humanhand.domain.types import DomainError

        with pytest.raises(DomainError, match="invalid offsets"):
            build_protected_span_set((_span(-1, 4),))

    def test_empty_set(self) -> None:
        span_set = build_protected_span_set(())
        assert span_set.spans == ()
        assert span_set.to_payload() == {"count": 0, "spans": []}


class TestProtectedSpanSetAccess:
    def test_spans_of_kind(self) -> None:
        span_set = build_protected_span_set(
            (_span(0, 4, SpanKind.DATE), _span(6, 8, SpanKind.DATE), _span(10, 20))
        )
        dates = span_set.spans_of_kind(SpanKind.DATE)
        assert len(dates) == 2

    def test_by_id(self) -> None:
        span_set = build_protected_span_set((_span(0, 4), _span(6, 8)))
        assert span_set.by_id("s2").source_location.start_offset == 6
        with pytest.raises(KeyError):
            span_set.by_id("s99")

    def test_payload_round_trip_shape(self) -> None:
        span_set = build_protected_span_set((_span(0, 4, SpanKind.DATE, "2024"),))
        payload = span_set.to_payload()
        assert payload["count"] == 1
        raw_spans = payload["spans"]
        assert isinstance(raw_spans, list)
        item = raw_spans[0]
        assert isinstance(item, dict)
        assert item["span_id"] == "s1"
        assert item["kind"] == "date"
        location = item["source_location"]
        assert isinstance(location, dict)
        assert location["start_offset"] == 0
