"""Deterministic quotation extraction for source-lane evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass

from humanhand.domain.document_nodes import DocumentNode, NodeType, SourceLocation

_QUOTED_RUN_RE = re.compile(r'"([^"\n]{20,})"')
_MIN_INLINE_QUOTE_CHARS = 20

_SMART_QUOTED_RUN_RE = re.compile(r"“([^”\n]{20,})”")


@dataclass(frozen=True)
class Quotation:
    """One quoted region extracted from source evidence.

    ``attribution`` records surrounding attribution text when present; it
    never asserts authorship.
    """

    text: str
    source_location: SourceLocation
    attribution: str = ""
    citation_ref: str | None = None


def _add(
    result: list[Quotation],
    text: str,
    location: SourceLocation,
) -> None:
    if any(quote.source_location == location for quote in result):
        return
    result.append(Quotation(text=text, source_location=location))


def extract_quotations(nodes: tuple[DocumentNode, ...]) -> tuple[Quotation, ...]:
    """Extract quotations deterministically from canonical nodes.

    Rules:
    - Every QUOTATION node's text is a quotation (exact span).
    - Straight- or curly-quoted runs of at least 20 characters inside
      paragraph/heading text are quotations (span covers the quoted run
      including quote marks when computable).
    """
    result: list[Quotation] = []
    for node in nodes:
        if node.node_type is NodeType.QUOTATION:
            if node.text.strip():
                _add(result, node.text, node.source_location)
            continue
        if node.node_type not in {NodeType.PARAGRAPH, NodeType.HEADING}:
            continue
        location = node.source_location
        for pattern in (_QUOTED_RUN_RE, _SMART_QUOTED_RUN_RE):
            for match in pattern.finditer(node.text):
                inner = match.group(1).strip()
                if len(inner) < _MIN_INLINE_QUOTE_CHARS:
                    continue
                span = SourceLocation(
                    start_offset=location.start_offset + match.start(),
                    end_offset=location.start_offset + match.end(),
                    line_start=location.line_start,
                    line_end=location.line_end,
                )
                _add(result, inner, span)
    return tuple(result)
