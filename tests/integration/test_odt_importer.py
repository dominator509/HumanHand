"""Integration tests for the clean-room ODT importer (EP-013)."""

from __future__ import annotations

import pytest

from humanhand.domain.canonical_document import ImportInspection
from humanhand.domain.document_nodes import DocumentNode, NodeType
from humanhand.domain.document_serialization import document_to_json
from humanhand.domain.import_findings import (
    FindingCategory,
    FindingCode,
    FindingSeverity,
    ImportFinding,
    ImportStatus,
)
from humanhand.domain.import_policy import ImportPolicy
from humanhand.infra.importers.odt_importer import OdtImporter
from tests.integration.support.odt_builder import build_odt, build_odt_with_content

# A non-ODT extension keeps the full inspect() pipeline runnable: file_type.py
# (EP-012 baseline, outside this adapter's file scope) still lists ODT under
# UNSUPPORTED_KINDS, so a ".odt" path would be hard-blocked by the identity
# precheck with UNSUPPORTED_FORMAT before the adapter runs. With a
# declared-UNKNOWN identity plus ZIP magic there are no identity findings,
# and parse_payloads executes exactly as it does in the worker.
_INSPECT_PATH = "sample.bin"


def _inspect(raw: bytes) -> ImportInspection:
    return OdtImporter().inspect(raw, _INSPECT_PATH, ImportPolicy())


def _nodes_of(inspection: ImportInspection, node_type: NodeType) -> list[DocumentNode]:
    assert inspection.document is not None
    return [node for node in inspection.document.nodes if node.node_type is node_type]


def _findings_by_code(inspection: ImportInspection, code: str) -> list[ImportFinding]:
    return [finding for finding in inspection.findings if finding.code == code]


def _content_with(body_fragment: str) -> bytes:
    """Wrap a body fragment in a full content.xml part for a real ODT."""
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<office:document-content "
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
        'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" office:version="1.2">'
        "<office:body><office:text>"
        f"{body_fragment}"
        "</office:text></office:body></office:document-content>"
    ).encode()
    return build_odt_with_content(content)


@pytest.mark.importers
class TestOdtImporter:
    def test_happy_path_heading_and_paragraphs(self) -> None:
        inspection = _inspect(
            build_odt(paragraphs=["First paragraph", "Second one"], heading="Section One")
        )
        assert inspection.status is ImportStatus.OK
        assert inspection.document is not None
        assert inspection.document.parser_name == "odt"
        assert inspection.document.parser_version == "1"
        headings = _nodes_of(inspection, NodeType.HEADING)
        assert len(headings) == 1
        assert headings[0].attributes == {"level": "1"}
        assert headings[0].text == "Section One"
        assert [node.text for node in _nodes_of(inspection, NodeType.PARAGRAPH)] == [
            "First paragraph",
            "Second one",
        ]
        assert inspection.document.surface_text == ("Section One\nFirst paragraph\nSecond one")
        assert inspection.coverage.status == "complete"

    def test_deterministic_replay(self) -> None:
        raw = build_odt(paragraphs=["First paragraph", "Second one"], heading="Section One")
        first = _inspect(raw)
        second = _inspect(raw)
        assert first.to_json(include_content=True) == second.to_json(include_content=True)
        assert first.document is not None
        assert second.document is not None
        assert document_to_json(first.document) == document_to_json(second.document)

    def test_local_image_and_remote_link(self) -> None:
        inspection = _inspect(
            build_odt(
                paragraphs=["First paragraph"],
                links=[("assets/x.png", ""), ("https://example.com/docs", "docs")],
            )
        )
        assert inspection.status is ImportStatus.HUMAN_REVIEW_REQUIRED
        images = _nodes_of(inspection, NodeType.IMAGE_PLACEHOLDER)
        assert len(images) == 1
        assert images[0].attributes == {"url": "assets/x.png"}
        hyperlinks = _nodes_of(inspection, NodeType.HYPERLINK)
        assert len(hyperlinks) == 1
        assert hyperlinks[0].text == "docs"
        assert hyperlinks[0].attributes == {"url": "https://example.com/docs"}
        remote = _findings_by_code(inspection, FindingCode.EXTERNAL_REMOTE_RESOURCE)
        assert len(remote) == 1
        assert remote[0].severity is FindingSeverity.ERROR
        assert remote[0].category is FindingCategory.EXTERNAL_RELATIONSHIP
        assert remote[0].evidence == "https://example.com"
        assert inspection.coverage.status == "partial"

    def test_embedded_macros_flagged(self) -> None:
        inspection = _inspect(build_odt(paragraphs=["Hello"], macros=True))
        assert inspection.status is ImportStatus.HUMAN_REVIEW_REQUIRED
        macro_findings = _findings_by_code(inspection, FindingCode.ACTIVE_CONTENT_MACRO)
        assert len(macro_findings) == 1
        assert macro_findings[0].severity is FindingSeverity.ERROR
        assert macro_findings[0].category is FindingCategory.ACTIVE_CONTENT
        assert macro_findings[0].description == "ODT contains an embedded macro library"
        assert macro_findings[0].evidence == "Basic/Standard/Module1.xml"
        assert inspection.coverage.status == "partial"

    def test_meta_title_metadata(self) -> None:
        inspection = _inspect(build_odt(paragraphs=["Hello"], title="My Title"))
        assert inspection.status is ImportStatus.OK
        by_key = {item.key: item for item in inspection.metadata.items}
        title = by_key["dc:title"]
        assert title.kind == "odt_meta"
        assert title.value == "My Title"

    def test_not_a_zip_fails_closed_in_parse_payloads(self) -> None:
        payloads = OdtImporter().parse_payloads(b"garbage", ImportPolicy())
        assert payloads["document"] is None
        findings = payloads["findings"]
        assert isinstance(findings, list)
        zip_findings = [
            item
            for item in findings
            if isinstance(item, dict) and item.get("description") == "Not a valid ZIP container"
        ]
        assert len(zip_findings) == 1
        assert zip_findings[0]["evidence"] == "bad_zip"

    def test_malformed_content_xml_fails_closed(self) -> None:
        payloads = OdtImporter().parse_payloads(build_odt_with_content(b"<not-xml"), ImportPolicy())
        assert payloads["document"] is None
        findings = payloads["findings"]
        assert isinstance(findings, list)
        unsupported = [
            item
            for item in findings
            if isinstance(item, dict) and item.get("code") == FindingCode.UNSUPPORTED_FEATURE
        ]
        assert len(unsupported) == 1
        assert unsupported[0]["severity"] == "error"
        assert unsupported[0]["category"] == "structure"
        assert unsupported[0]["evidence"] == "malformed=content.xml"

    def test_expanded_size_limit_blocks_document(self) -> None:
        raw = build_odt(paragraphs=["Hello"])
        policy = ImportPolicy(max_expanded_bytes=16)
        inspection = OdtImporter().inspect(raw, _INSPECT_PATH, policy)
        assert inspection.status is ImportStatus.FAILED
        assert inspection.document is None
        assert any(
            finding.code == FindingCode.LIMIT_EXPANDED_BYTES for finding in inspection.findings
        )

    def test_input_bytes_unchanged(self) -> None:
        raw = build_odt(paragraphs=["First paragraph"], heading="Section One")
        snapshot = raw
        _inspect(raw)
        assert raw == snapshot

    def test_list_and_table_structures(self) -> None:
        inspection = _inspect(
            _content_with(
                "<text:list>"
                "<text:list-item><text:p>Alpha</text:p></text:list-item>"
                "<text:list-item><text:p>Beta</text:p></text:list-item>"
                "</text:list>"
                "<table:table><table:table-row>"
                "<table:table-cell><text:p>One</text:p></table:table-cell>"
                "<table:table-cell><text:p>Two</text:p></table:table-cell>"
                "</table:table-row></table:table>"
            )
        )
        assert inspection.status is ImportStatus.OK
        assert len(_nodes_of(inspection, NodeType.LIST)) == 1
        assert len(_nodes_of(inspection, NodeType.TABLE)) == 1
        assert len(_nodes_of(inspection, NodeType.TABLE_ROW)) == 1
        assert [node.text for node in _nodes_of(inspection, NodeType.LIST_ITEM)] == [
            "Alpha",
            "Beta",
        ]
        assert [node.text for node in _nodes_of(inspection, NodeType.TABLE_CELL)] == [
            "One",
            "Two",
        ]
        assert inspection.document is not None
        assert inspection.document.surface_text == "Alpha\nBeta\nOne\nTwo"

    def test_list_item_link_span_and_remote_evidence(self) -> None:
        inspection = _inspect(
            _content_with(
                "<text:list>"
                "<text:list-item><text:p>Item with "
                '<text:a xlink:href="https://example.org/path?q=1">link</text:a>'
                "</text:p></text:list-item>"
                "</text:list>"
            )
        )
        assert inspection.status is ImportStatus.HUMAN_REVIEW_REQUIRED
        items = _nodes_of(inspection, NodeType.LIST_ITEM)
        assert len(items) == 1
        assert items[0].text == "Item with link"
        links = _nodes_of(inspection, NodeType.HYPERLINK)
        assert len(links) == 1
        assert links[0].text == "link"
        assert links[0].attributes == {"url": "https://example.org/path?q=1"}
        assert items[0].source_location.start_offset <= links[0].source_location.start_offset
        assert links[0].source_location.end_offset <= items[0].source_location.end_offset
        remote = _findings_by_code(inspection, FindingCode.EXTERNAL_REMOTE_RESOURCE)
        assert len(remote) == 1
        assert remote[0].evidence == "https://example.org"

    def test_heading_level_defaults_to_one(self) -> None:
        inspection = _inspect(_content_with("<text:h>No level</text:h>"))
        headings = _nodes_of(inspection, NodeType.HEADING)
        assert len(headings) == 1
        assert headings[0].attributes == {"level": "1"}

    def test_all_source_offsets_within_text(self) -> None:
        samples = [
            build_odt(paragraphs=["First paragraph", "Second one"], heading="Section One"),
            build_odt(
                paragraphs=["First paragraph"],
                links=[("assets/x.png", ""), ("https://example.com/docs", "docs")],
            ),
            _content_with(
                "<text:list>"
                "<text:list-item><text:p>Item with "
                '<text:a xlink:href="https://example.org">link</text:a>'
                "</text:p></text:list-item>"
                "</text:list>"
                "<table:table><table:table-row>"
                "<table:table-cell><text:p>Cell</text:p></table:table-cell>"
                "</table:table-row></table:table>"
            ),
        ]
        for raw in samples:
            inspection = _inspect(raw)
            assert inspection.document is not None
            text_length = len(inspection.document.surface_text)
            for node in inspection.document.nodes:
                location = node.source_location
                assert 0 <= location.start_offset <= location.end_offset <= text_length
                assert 1 <= location.line_start <= location.line_end
