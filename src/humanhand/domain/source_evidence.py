"""Source-lane evidence: protected spans, quotations, and citations.

This module never runs for style-lane imports; source facts must not enter
the style lane (ADR-002).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from humanhand.domain.canonical_document import CanonicalDocument
from humanhand.domain.citations import Citation, extract_citations
from humanhand.domain.document_nodes import DocumentNode, NodeType, SourceLocation
from humanhand.domain.protected_spans import (
    ProtectedSpan,
    ProtectedSpanSet,
    SpanKind,
    build_protected_span_set,
)
from humanhand.domain.quotations import Quotation, extract_quotations

_NUMBER_UNIT_RE = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*([A-Za-zÀ-ſµΩ°%]{1,12})\b")
_DATE_RE = re.compile(
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|"
    r"\d{1,2}\s+(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+\d{4})\b"
)

_MEASURE_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "is",
        "are",
        "was",
        "were",
        "be",
        "by",
        "for",
        "with",
        "as",
        "at",
        "not",
        "no",
        "it",
        "we",
        "they",
        "he",
        "she",
        "if",
        "so",
        "but",
        "do",
        "does",
        "did",
    }
)


@dataclass(frozen=True)
class SourceEvidence:
    """Deterministic source-lane evidence extracted from a canonical document."""

    document: CanonicalDocument
    protected_spans: ProtectedSpanSet
    quotations: tuple[Quotation, ...]
    citations: tuple[Citation, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "protected_spans": self.protected_spans.to_payload(),
            "quotations": [
                {
                    "text": quotation.text,
                    "attribution": quotation.attribution,
                    "citation_ref": quotation.citation_ref,
                    "source_location": {
                        "start_offset": quotation.source_location.start_offset,
                        "end_offset": quotation.source_location.end_offset,
                        "line_start": quotation.source_location.line_start,
                        "line_end": quotation.source_location.line_end,
                    },
                }
                for quotation in self.quotations
            ],
            "citations": [
                {
                    "citation_id": citation.citation_id,
                    "kind": citation.kind,
                    "text": citation.text,
                    "source_location": {
                        "start_offset": citation.source_location.start_offset,
                        "end_offset": citation.source_location.end_offset,
                        "line_start": citation.source_location.line_start,
                        "line_end": citation.source_location.line_end,
                    },
                }
                for citation in self.citations
            ],
        }


def _number_unit_spans(node: DocumentNode, result: list[ProtectedSpan]) -> None:
    location = node.source_location
    for match in _NUMBER_UNIT_RE.finditer(node.text):
        unit_text = match.group(2)
        if unit_text.lower() in _MEASURE_STOPWORDS:
            continue
        start = location.start_offset + match.start()
        end = location.start_offset + match.end()
        result.append(
            ProtectedSpan(
                span_id="",
                kind=SpanKind.NUMBER,
                source_location=SourceLocation(start, end, location.line_start, location.line_end),
                text=match.group(0),
                label=unit_text,
            )
        )


def _date_spans(node: DocumentNode, result: list[ProtectedSpan]) -> None:
    location = node.source_location
    for match in _DATE_RE.finditer(node.text):
        start = location.start_offset + match.start()
        end = location.start_offset + match.end()
        result.append(
            ProtectedSpan(
                span_id="",
                kind=SpanKind.DATE,
                source_location=SourceLocation(start, end, location.line_start, location.line_end),
                text=match.group(0),
            )
        )


def _span_from_quotation(quotation: Quotation) -> ProtectedSpan:
    return ProtectedSpan(
        span_id="",
        kind=SpanKind.QUOTATION,
        source_location=quotation.source_location,
        text=quotation.text,
    )


def _span_from_citation(citation: Citation) -> ProtectedSpan:
    return ProtectedSpan(
        span_id="",
        kind=SpanKind.CITATION,
        source_location=citation.source_location,
        text=citation.text,
        label=citation.kind,
    )


def build_source_evidence(document: CanonicalDocument) -> SourceEvidence:
    """Extract evidence deterministically from a source-lane document.

    Protected spans start as quotations, citations, number+unit pairs, and
    dates, in document order; overlapping spans are deduplicated by
    :func:`build_protected_span_set` (first occurrence wins).
    """
    quotations = extract_quotations(document.nodes)
    citations = extract_citations(document.nodes)
    span_candidates: list[ProtectedSpan] = []
    span_candidates.extend(_span_from_quotation(quotation) for quotation in quotations)
    span_candidates.extend(_span_from_citation(citation) for citation in citations)
    text_nodes = [
        node
        for node in document.nodes
        if node.node_type
        in {NodeType.PARAGRAPH, NodeType.HEADING, NodeType.LIST_ITEM, NodeType.TABLE_CELL}
    ]
    for node in text_nodes:
        _number_unit_spans(node, span_candidates)
        _date_spans(node, span_candidates)
    span_candidates.sort(
        key=lambda span: (
            span.source_location.start_offset,
            span.source_location.end_offset,
            span.kind.value,
        )
    )
    return SourceEvidence(
        document=document,
        protected_spans=build_protected_span_set(tuple(span_candidates)),
        quotations=quotations,
        citations=citations,
    )
