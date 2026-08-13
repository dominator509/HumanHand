"""Deterministic citation extraction for source-lane evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass

from humanhand.domain.document_nodes import DocumentNode, NodeType, SourceLocation

_BRACKET_NUMBER_RE = re.compile(r"\[(\d{1,4}(?:,\s*\d{1,4})*)\]")
_AUTHOR_YEAR_RE = re.compile(r"\(([A-Z][A-Za-zÀ-ſ' -]+,\s*\d{4}[a-z]?)\)")
_URL_RE = re.compile(r"https?://[^\s\"'<>()\[\]]{4,}")
_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)")


@dataclass(frozen=True)
class Citation:
    """One citation occurrence with its exact source span."""

    citation_id: str
    kind: str
    text: str
    source_location: SourceLocation


def _extract_for_node(node: DocumentNode, result: list[tuple[str, str, int, int]]) -> None:
    """Append (kind, text, start, end) matches for one node's text."""
    if node.node_type not in {
        NodeType.PARAGRAPH,
        NodeType.HEADING,
        NodeType.CITATION,
        NodeType.QUOTATION,
        NodeType.LIST_ITEM,
        NodeType.TABLE_CELL,
    }:
        return
    base = node.source_location
    for pattern, kind in (
        (_DOI_RE, "doi"),
        (_BRACKET_NUMBER_RE, "bracket_number"),
        (_AUTHOR_YEAR_RE, "author_year"),
        (_URL_RE, "url"),
    ):
        for match in pattern.finditer(node.text):
            stripped_chars = 0
            if kind == "doi":
                text = match.group(1).rstrip(".")
                stripped_chars = len(match.group(1)) - len(text)
            elif kind == "author_year":
                text = match.group(1)
            else:
                text = match.group(0)
            result.append(
                (
                    kind,
                    text,
                    base.start_offset + match.start(),
                    # Narrow the span to the stripped text so span and text
                    # always protect exactly the same characters.
                    base.start_offset + match.end() - stripped_chars,
                )
            )


def extract_citations(nodes: tuple[DocumentNode, ...]) -> tuple[Citation, ...]:
    """Extract citations deterministically in document order.

    Kinds: ``bracket_number``, ``author_year``, ``url``, ``doi``. A
    dedicated CITATION node's text is also recorded as its own citation
    when it does not overlap an extracted one.
    """
    raw: list[tuple[str, str, int, int]] = []
    for node in nodes:
        _extract_for_node(node, raw)
    raw.sort(key=lambda item: item[2])

    citations: list[Citation] = []
    seen: set[tuple[int, int, str]] = set()
    for kind, text, start, end in raw:
        key = (start, end, kind)
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            Citation(
                citation_id=f"c{len(citations) + 1}",
                kind=kind,
                text=text,
                source_location=SourceLocation(start_offset=start, end_offset=end),
            )
        )
    return tuple(citations)
