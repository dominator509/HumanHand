"""Integration tests for the clean-room HTML importer (EP-013)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from humanhand.domain.canonical_document import CanonicalDocument
from humanhand.domain.document_nodes import DocumentNode, NodeType
from humanhand.domain.document_serialization import document_from_json, document_to_json
from humanhand.domain.import_findings import FindingCode, ImportStatus
from humanhand.domain.import_policy import ImportPolicy
from humanhand.infra.importers.html_importer import HtmlImporter

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "import"

SAFE_HTML = (FIXTURES_DIR / "safe.html").read_bytes()
REMOTE_RESOURCE_HTML = (FIXTURES_DIR / "remote-resource.html").read_bytes()
SCRIPT_HTML = (FIXTURES_DIR / "script.html").read_bytes()

SAFE_SURFACE_TEXT = (
    "Report\n"
    "First paragraph with a local link.\n"
    "Item one\n"
    "Item two\n"
    "A quoted observation.\n"
    'print("code")'
)

EXPECTED_SUPPORTED_STRUCTURES = (
    "heading",
    "paragraph",
    "list",
    "list_item",
    "quotation",
    "code_block",
    "table",
    "hyperlink",
    "image_placeholder",
    "html_meta",
    "html_comment",
)

STYLE_HTML = (
    b"<html><head><style>p { color: red; }</style></head><body><p>styled</p></body></html>\n"
)


@pytest.mark.importers
class TestHtmlImporter:
    """Deterministic HTML parsing into canonical structures (EP-013)."""

    @staticmethod
    def _payloads(raw: bytes, policy: ImportPolicy | None = None) -> dict[str, object]:
        return HtmlImporter().parse_payloads(raw, policy or ImportPolicy())

    @staticmethod
    def _document_or_none(payloads: dict[str, object]) -> CanonicalDocument | None:
        document_payload = payloads["document"]
        if document_payload is None:
            return None
        return document_from_json(json.dumps(document_payload, ensure_ascii=False))

    @staticmethod
    def _status(payloads: dict[str, object]) -> str:
        return str(payloads["status"])

    @staticmethod
    def _finding_codes(payloads: dict[str, object]) -> list[str]:
        raw_findings = payloads["findings"]
        if not isinstance(raw_findings, list):
            return []
        return [str(item["code"]) for item in raw_findings if isinstance(item, dict)]

    @staticmethod
    def _findings_by_code(payloads: dict[str, object], code: str) -> list[dict[str, object]]:
        raw_findings = payloads["findings"]
        if not isinstance(raw_findings, list):
            return []
        return [
            item
            for item in raw_findings
            if isinstance(item, dict) and str(item.get("code")) == code
        ]

    @staticmethod
    def _nodes_of(document: CanonicalDocument, node_type: NodeType) -> list[DocumentNode]:
        return [node for node in document.nodes if node.node_type is node_type]

    @staticmethod
    def _metadata_by_key(
        payloads: dict[str, object], kind: str, key: str
    ) -> list[dict[str, object]]:
        metadata_payload = payloads["metadata"]
        if not isinstance(metadata_payload, dict):
            return []
        raw_items = metadata_payload.get("items")
        if not isinstance(raw_items, list):
            return []
        return [
            item
            for item in raw_items
            if isinstance(item, dict)
            and str(item.get("kind")) == kind
            and str(item.get("key")) == key
        ]

    def test_safe_html_structures_and_metadata(self) -> None:
        payloads = self._payloads(SAFE_HTML)
        document = self._document_or_none(payloads)
        assert document is not None
        assert self._status(payloads) == ImportStatus.OK.value
        assert document.surface_text == SAFE_SURFACE_TEXT

        headings = self._nodes_of(document, NodeType.HEADING)
        assert len(headings) == 1
        assert headings[0].text == "Report"
        assert headings[0].attributes == {"level": "1"}
        assert self._nodes_of(document, NodeType.PARAGRAPH)
        assert self._nodes_of(document, NodeType.LIST)
        list_items = self._nodes_of(document, NodeType.LIST_ITEM)
        assert [item.text for item in list_items] == ["Item one", "Item two"]
        quotations = self._nodes_of(document, NodeType.QUOTATION)
        assert [item.text for item in quotations] == ["A quoted observation."]
        code_blocks = self._nodes_of(document, NodeType.CODE_BLOCK)
        assert [item.text for item in code_blocks] == ['print("code")']

        hyperlinks = self._nodes_of(document, NodeType.HYPERLINK)
        assert len(hyperlinks) == 1
        assert hyperlinks[0].attributes == {"url": "docs/local.html"}
        assert hyperlinks[0].text == "link"

        author = self._metadata_by_key(payloads, "html_meta", "author")
        assert len(author) == 1
        assert str(author[0]["value"]) == "Synthetic Author"
        title = self._metadata_by_key(payloads, "html_title", "title")
        assert len(title) == 1
        assert str(title[0]["value"]) == "Safe Report"
        comment = self._metadata_by_key(payloads, "html_comment", "html_comment_1")
        assert len(comment) == 1
        assert str(comment[0]["value"]) == " generated by a synthetic tool "

    def test_safe_html_deterministic_replay(self) -> None:
        first = self._payloads(SAFE_HTML)
        second = self._payloads(SAFE_HTML)
        assert first == second
        first_document = self._document_or_none(first)
        second_document = self._document_or_none(second)
        assert first_document is not None
        assert second_document is not None
        assert document_to_json(first_document) == document_to_json(second_document)

    def test_remote_resources_fail_closed(self) -> None:
        payloads = self._payloads(REMOTE_RESOURCE_HTML)
        document = self._document_or_none(payloads)
        assert document is not None
        assert self._status(payloads) == ImportStatus.HUMAN_REVIEW_REQUIRED.value

        remote = self._findings_by_code(payloads, FindingCode.EXTERNAL_REMOTE_RESOURCE)
        assert len(remote) == 2
        assert {str(item["evidence"]) for item in remote} == {
            "https://cdn.example.com",
            "https://example.com",
        }

        images = self._nodes_of(document, NodeType.IMAGE_PLACEHOLDER)
        assert len(images) == 1
        assert images[0].attributes == {"url": "https://cdn.example.com/logo.png"}
        hyperlinks = self._nodes_of(document, NodeType.HYPERLINK)
        assert len(hyperlinks) == 1
        assert hyperlinks[0].attributes == {"url": "https://example.com/page"}
        assert hyperlinks[0].text == "the CDN"

    def test_script_content_rejected_and_excluded(self) -> None:
        payloads = self._payloads(SCRIPT_HTML)
        document = self._document_or_none(payloads)
        assert document is not None
        assert self._status(payloads) == ImportStatus.HUMAN_REVIEW_REQUIRED.value

        codes = set(self._finding_codes(payloads))
        assert FindingCode.ACTIVE_CONTENT_SCRIPT in codes
        assert FindingCode.ACTIVE_CONTENT_IFRAME in codes
        assert FindingCode.ACTIVE_CONTENT_EVENT_HANDLER in codes
        assert FindingCode.ACTIVE_CONTENT_JAVASCRIPT_LINK in codes

        assert "alert(1)" not in document.surface_text
        assert document.surface_text == "click"

    def test_magic_mismatch_quarantined_via_inspect(self) -> None:
        inspection = HtmlImporter().inspect(
            b"plain text, not html\n", "not-html.html", ImportPolicy()
        )
        assert inspection.status is ImportStatus.QUARANTINED
        assert inspection.document is None
        assert FindingCode.MAGIC_MISMATCH in [f.code for f in inspection.findings]

    def test_invalid_utf8_fails_closed(self) -> None:
        payloads = self._payloads(b"\xef\xbb\xbf\xff\xfe bad")
        assert self._status(payloads) == ImportStatus.FAILED.value
        assert FindingCode.ENCODING_INVALID_UTF8 in self._finding_codes(payloads)
        assert self._document_or_none(payloads) is None

    def test_size_limit_fails_closed(self) -> None:
        payloads = self._payloads(SAFE_HTML, ImportPolicy(max_bytes=64))
        assert self._status(payloads) == ImportStatus.FAILED.value
        assert FindingCode.LIMIT_BYTES in self._finding_codes(payloads)
        assert self._document_or_none(payloads) is None

    def test_input_bytes_unchanged(self) -> None:
        raw = SAFE_HTML
        self._payloads(raw)
        assert raw == SAFE_HTML
        assert bytes(raw) == SAFE_HTML

    def test_style_element_is_warning_not_content(self) -> None:
        payloads = self._payloads(STYLE_HTML)
        document = self._document_or_none(payloads)
        assert document is not None
        assert self._status(payloads) == ImportStatus.FINDINGS.value
        style = self._findings_by_code(payloads, FindingCode.UNSUPPORTED_FEATURE)
        assert len(style) == 1
        assert str(style[0]["evidence"]) == "style_element"

        coverage = payloads["coverage"]
        assert isinstance(coverage, dict)
        assert str(coverage["status"]) == "partial"
        assert list(coverage["unsupported_structures"]) == ["style_element"]
        assert list(coverage["supported_structures"]) == list(EXPECTED_SUPPORTED_STRUCTURES)

        paragraphs = self._nodes_of(document, NodeType.PARAGRAPH)
        assert [item.text for item in paragraphs] == ["styled"]
        assert document.surface_text == "styled"

    def test_bom_is_encoding_warning_and_content_is_parsed(self) -> None:
        payloads = self._payloads(b"\xef\xbb\xbf" + SAFE_HTML)
        document = self._document_or_none(payloads)
        assert document is not None
        assert FindingCode.ENCODING_BOM in self._finding_codes(payloads)
        assert document.surface_text == SAFE_SURFACE_TEXT

    @pytest.mark.parametrize(
        "name,raw",
        [
            ("safe", SAFE_HTML),
            ("remote-resource", REMOTE_RESOURCE_HTML),
            ("script", SCRIPT_HTML),
        ],
        ids=["safe", "remote-resource", "script"],
    )
    def test_spans_index_decoded_text_within_bounds(self, name: str, raw: bytes) -> None:
        del name
        decoded = raw.decode("utf-8")
        payloads = self._payloads(raw)
        document = self._document_or_none(payloads)
        assert document is not None
        assert document.nodes
        for node in document.nodes:
            location = node.source_location
            assert 0 <= location.start_offset <= location.end_offset <= len(decoded)
            assert 1 <= location.line_start <= location.line_end
