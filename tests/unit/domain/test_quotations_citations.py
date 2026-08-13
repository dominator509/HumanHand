"""Unit tests for quotation and citation extraction."""

from __future__ import annotations

from humanhand.domain.citations import Citation, extract_citations
from humanhand.domain.document_nodes import DocumentNode, NodeType, SourceLocation
from humanhand.domain.quotations import Quotation, extract_quotations


def _node(
    node_type: NodeType,
    text: str,
    start: int = 0,
    end: int | None = None,
) -> DocumentNode:
    return DocumentNode(
        node_id="n",
        parent_id=None,
        node_type=node_type,
        position=1,
        source_location=SourceLocation(start, end if end is not None else len(text)),
        text=text,
    )


class TestExtractQuotations:
    def test_quotation_node_becomes_quotation(self) -> None:
        quotations = extract_quotations(
            (_node(NodeType.QUOTATION, "The quick brown fox jumps over the lazy dog."),)
        )
        assert len(quotations) == 1
        assert quotations[0].text.startswith("The quick brown fox")
        assert quotations[0].source_location.start_offset == 0

    def test_inline_straight_quotes_extracted(self) -> None:
        text = 'He said "this is a reasonably long quoted sentence" and left.'
        quotations = extract_quotations((_node(NodeType.PARAGRAPH, text),))
        assert len(quotations) == 1
        assert quotations[0].text == "this is a reasonably long quoted sentence"

    def test_inline_curly_quotes_extracted(self) -> None:
        text = "She wrote “this is a reasonably long quoted sentence” today."
        quotations = extract_quotations((_node(NodeType.PARAGRAPH, text),))
        assert len(quotations) == 1
        assert quotations[0].text == "this is a reasonably long quoted sentence"

    def test_short_quotes_ignored(self) -> None:
        text = 'He said "hi" and left.'
        assert extract_quotations((_node(NodeType.PARAGRAPH, text),)) == ()

    def test_offsets_are_absolute(self) -> None:
        text = 'He said "this is a reasonably long quoted sentence" and left.'
        node = _node(NodeType.PARAGRAPH, text, start=100)
        quotations = extract_quotations((node,))
        assert quotations[0].source_location.start_offset == 100 + text.index('"')

    def test_empty_quotation_node_skipped(self) -> None:
        assert extract_quotations((_node(NodeType.QUOTATION, "   "),)) == ()


class TestExtractCitations:
    def test_bracket_number(self) -> None:
        citations = extract_citations((_node(NodeType.PARAGRAPH, "See the results [12, 15]."),))
        kinds = [citation.kind for citation in citations]
        assert "bracket_number" in kinds

    def test_author_year(self) -> None:
        citations = extract_citations(
            (_node(NodeType.PARAGRAPH, "As shown by (Smith, 2020) elsewhere."),)
        )
        author_year = [c for c in citations if c.kind == "author_year"]
        assert len(author_year) == 1
        assert author_year[0].text == "Smith, 2020"

    def test_url(self) -> None:
        citations = extract_citations(
            (_node(NodeType.PARAGRAPH, "See https://example.com/docs/page for more."),)
        )
        urls = [c for c in citations if c.kind == "url"]
        assert len(urls) == 1
        assert urls[0].text == "https://example.com/docs/page"

    def test_doi(self) -> None:
        citations = extract_citations(
            (_node(NodeType.PARAGRAPH, "Published under 10.1000/abc.123-x."),)
        )
        dois = [c for c in citations if c.kind == "doi"]
        assert len(dois) == 1
        assert dois[0].text == "10.1000/abc.123-x"

    def test_deterministic_ids_and_order(self) -> None:
        text = "First [1], then (Smith, 2020), then https://example.com/x."
        citations = extract_citations((_node(NodeType.PARAGRAPH, text),))
        assert [c.citation_id for c in citations] == [
            f"c{index}" for index in range(1, len(citations) + 1)
        ]
        offsets = [c.source_location.start_offset for c in citations]
        assert offsets == sorted(offsets)

    def test_ignores_non_text_nodes(self) -> None:
        assert extract_citations((_node(NodeType.CODE_BLOCK, "x [1] y"),)) == ()

    def test_quotation_payload_shape(self) -> None:
        quotation = Quotation(
            text="quoted text",
            source_location=SourceLocation(4, 15, 1, 1),
        )
        assert quotation.text == "quoted text"

    def test_citation_payload_shape(self) -> None:
        citation = Citation(
            citation_id="c1",
            kind="url",
            text="https://example.com",
            source_location=SourceLocation(0, 19),
        )
        assert citation.citation_id == "c1"
