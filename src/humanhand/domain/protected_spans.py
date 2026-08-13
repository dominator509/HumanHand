"""Protected spans — deterministically extracted fact-bearing text regions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from humanhand.domain.document_nodes import SourceLocation
from humanhand.domain.types import DomainError


class SpanKind(StrEnum):
    """Kinds of source text that later stages must not rewrite silently."""

    QUOTATION = "quotation"
    CITATION = "citation"
    NUMBER = "number"
    UNIT = "unit"
    DATE = "date"
    ENTITY = "entity"
    KEY_TERM = "key_term"


class SpanStatus(StrEnum):
    """Review state of one protected span."""

    EXTRACTED = "extracted"
    APPROVED = "approved"
    EXCLUDED = "excluded"


@dataclass(frozen=True)
class ProtectedSpan:
    """One protected text region with its exact span and stable id."""

    span_id: str
    kind: SpanKind
    source_location: SourceLocation
    text: str
    label: str = ""
    status: SpanStatus = SpanStatus.EXTRACTED


@dataclass(frozen=True)
class ProtectedSpanSet:
    """Immutable, deterministic set of protected spans for one source package.

    Spans are kept in document order; ids are assigned by
    :func:`build_protected_span_set` and are stable for equal inputs.
    """

    spans: tuple[ProtectedSpan, ...]

    def spans_of_kind(self, kind: SpanKind) -> tuple[ProtectedSpan, ...]:
        return tuple(span for span in self.spans if span.kind is kind)

    def by_id(self, span_id: str) -> ProtectedSpan:
        for span in self.spans:
            if span.span_id == span_id:
                return span
        raise KeyError(span_id)

    def to_payload(self) -> dict[str, object]:
        return {
            "count": len(self.spans),
            "spans": [
                {
                    "span_id": span.span_id,
                    "kind": span.kind.value,
                    "status": span.status.value,
                    "label": span.label,
                    "text": span.text,
                    "source_location": {
                        "start_offset": span.source_location.start_offset,
                        "end_offset": span.source_location.end_offset,
                        "line_start": span.source_location.line_start,
                        "line_end": span.source_location.line_end,
                    },
                }
                for span in self.spans
            ],
        }


def build_protected_span_set(spans: tuple[ProtectedSpan, ...]) -> ProtectedSpanSet:
    """Assign deterministic ``s{n}`` ids in document order.

    Tolerance rules (deterministic, first-occurrence wins):
    - exact duplicates are dropped;
    - a span that starts inside the previously kept span is dropped
      (nested spans such as a citation inside a quotation keep only the
      outermost region; out-of-order inputs are therefore safe too).

    Raises DomainError only for structurally invalid (negative or
    reversed) offsets, which extraction can never produce.
    """
    seen: set[tuple[SpanKind, int, int]] = set()
    ordered: list[ProtectedSpan] = []
    previous_end = -1
    for index, span in enumerate(spans):
        location = span.source_location
        if location.start_offset < 0 or location.end_offset < location.start_offset:
            raise DomainError(f"Span {index} has invalid offsets")
        key = (span.kind, location.start_offset, location.end_offset)
        if key in seen:
            continue
        if location.start_offset < previous_end:
            continue
        seen.add(key)
        ordered.append(
            ProtectedSpan(
                span_id=f"s{len(ordered) + 1}",
                kind=span.kind,
                source_location=location,
                text=span.text,
                label=span.label,
                status=span.status,
            )
        )
        previous_end = location.end_offset
    return ProtectedSpanSet(spans=tuple(ordered))
