"""Integration tests for the clean-room Markdown importer (EP-012)."""

from __future__ import annotations

from pathlib import Path

import pytest

from humanhand.domain.canonical_document import ImportInspection
from humanhand.domain.document_nodes import DocumentNode, NodeType
from humanhand.domain.document_serialization import document_to_json
from humanhand.domain.import_findings import (
    FindingCategory,
    FindingCode,
    FindingSeverity,
    ImportStatus,
)
from humanhand.domain.import_policy import ImportPolicy
from humanhand.infra.importers.markdown_importer import MarkdownImporter

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "import"
FIXTURE_NAMES = (
    "sample.md",
    "front-matter.md",
    "comments.md",
    "remote-resource.md",
    "script.md",
    "block-ids.md",
    "raw-html.md",
)


def _fixture_path(name: str) -> Path:
    return FIXTURES_DIR / name


def _fixture_text(name: str) -> str:
    return _fixture_path(name).read_bytes().decode("utf-8-sig")


def _inspect(name: str) -> ImportInspection:
    path = _fixture_path(name)
    return MarkdownImporter().inspect(path.read_bytes(), str(path), ImportPolicy())


def _nodes_of(inspection: ImportInspection, node_type: NodeType) -> list[DocumentNode]:
    assert inspection.document is not None
    return [node for node in inspection.document.nodes if node.node_type is node_type]


@pytest.mark.importers
class TestMarkdownImporter:
    def test_sample_structure_and_status(self) -> None:
        inspection = _inspect("sample.md")
        assert inspection.status is ImportStatus.OK
        assert inspection.document is not None
        assert inspection.document.parser_name == "markdown"
        assert inspection.document.parser_version == "1"
        assert inspection.document.root.node_type is NodeType.DOCUMENT

        headings = _nodes_of(inspection, NodeType.HEADING)
        assert len(headings) == 2
        assert sorted(heading.attributes["level"] for heading in headings) == ["1", "2"]

        links = _nodes_of(inspection, NodeType.HYPERLINK)
        assert len(links) == 1
        assert links[0].text == "readme"
        assert links[0].attributes == {"url": "docs/readme.md"}

        assert len(_nodes_of(inspection, NodeType.LIST)) == 1
        assert len(_nodes_of(inspection, NodeType.LIST_ITEM)) == 3

        quotations = _nodes_of(inspection, NodeType.QUOTATION)
        assert len(quotations) == 1

        code_blocks = _nodes_of(inspection, NodeType.CODE_BLOCK)
        assert len(code_blocks) == 1
        assert code_blocks[0].text == 'print("hello")'
        assert code_blocks[0].attributes == {"language": "python"}

        assert len(_nodes_of(inspection, NodeType.TABLE)) == 1
        assert len(_nodes_of(inspection, NodeType.TABLE_ROW)) == 3
        cells = [node.text for node in _nodes_of(inspection, NodeType.TABLE_CELL)]
        assert cells == ["Name", "Value", "alpha", "1", "beta", "2"]

    def test_canonical_json_is_deterministic(self) -> None:
        first = _inspect("sample.md")
        second = _inspect("sample.md")
        assert first.document is not None
        assert second.document is not None
        assert document_to_json(first.document) == document_to_json(second.document)

    def test_front_matter_metadata(self) -> None:
        inspection = _inspect("front-matter.md")
        assert inspection.status is ImportStatus.OK
        by_key = {item.key: item for item in inspection.metadata.items}
        title = by_key["title"]
        assert title.kind == "front_matter"
        assert title.value == "Test Document"
        assert by_key["author"].value == "Synthetic Author"
        assert inspection.document is not None
        node_texts = [node.text for node in inspection.document.nodes if node.text]
        assert "Test Document" not in node_texts

    def test_html_comment_metadata(self) -> None:
        inspection = _inspect("comments.md")
        assert inspection.status is ImportStatus.OK
        comments = [item for item in inspection.metadata.items if item.kind == "html_comment"]
        assert len(comments) == 1
        assert comments[0].key == "html_comment_1"
        assert comments[0].value == " this is a note "

    def test_remote_resource_image_flagged(self) -> None:
        inspection = _inspect("remote-resource.md")
        assert inspection.status is ImportStatus.HUMAN_REVIEW_REQUIRED
        resource_findings = [
            finding
            for finding in inspection.findings
            if finding.code == FindingCode.EXTERNAL_REMOTE_RESOURCE
        ]
        assert len(resource_findings) == 1
        assert resource_findings[0].evidence == "https://example.com"
        images = _nodes_of(inspection, NodeType.IMAGE_PLACEHOLDER)
        assert len(images) == 1
        assert images[0].attributes == {"url": "https://example.com/pixel.png"}

    def test_active_content_script_flagged(self) -> None:
        inspection = _inspect("script.md")
        assert inspection.status is ImportStatus.HUMAN_REVIEW_REQUIRED
        script_findings = [
            finding
            for finding in inspection.findings
            if finding.code == FindingCode.ACTIVE_CONTENT_SCRIPT
        ]
        assert len(script_findings) == 1

    def test_block_ids_metadata(self) -> None:
        inspection = _inspect("block-ids.md")
        assert inspection.status is ImportStatus.OK
        by_key = {item.key: item for item in inspection.metadata.items}
        alpha = by_key["alpha1"]
        assert alpha.kind == "block_id"
        assert alpha.value == "alpha1"
        assert by_key["beta-2"].value == "beta-2"
        paragraph_texts = [node.text for node in _nodes_of(inspection, NodeType.PARAGRAPH)]
        assert "First block ^alpha1\nSecond block ^beta-2" in paragraph_texts

    def test_raw_html_unsupported_feature(self) -> None:
        inspection = _inspect("raw-html.md")
        assert inspection.status is ImportStatus.FINDINGS
        unsupported = [
            finding
            for finding in inspection.findings
            if finding.code == FindingCode.UNSUPPORTED_FEATURE
        ]
        assert len(unsupported) == 1
        assert unsupported[0].severity is FindingSeverity.WARNING
        assert unsupported[0].category is FindingCategory.UNSUPPORTED_FEATURE
        assert (
            unsupported[0].description
            == "Raw HTML block is not part of the supported Markdown subset"
        )
        assert unsupported[0].evidence == "line=3"
        assert inspection.coverage.status == "partial"
        assert "raw_html" in inspection.coverage.unsupported_structures
        paragraph_texts = [node.text for node in _nodes_of(inspection, NodeType.PARAGRAPH)]
        assert '<div class="x">text</div>' in paragraph_texts

    def test_paragraph_whitespace_preserved(self) -> None:
        inspection = _inspect("sample.md")
        paragraph_texts = [node.text for node in _nodes_of(inspection, NodeType.PARAGRAPH)]
        assert "line one\n  indented second line" in paragraph_texts

    def test_all_source_offsets_within_text(self) -> None:
        for name in FIXTURE_NAMES:
            inspection = _inspect(name)
            assert inspection.document is not None
            text_length = len(_fixture_text(name))
            for node in inspection.document.nodes:
                location = node.source_location
                assert location is not None
                assert 0 <= location.start_offset <= location.end_offset <= text_length
                assert 1 <= location.line_start <= location.line_end

    def test_degenerate_table_rows_are_not_dropped(self) -> None:
        # Regression: rows without a hyphen in every cell are data rows,
        # never silently consumed as delimiter structure.
        text = "| a | b |\n|---|---|\n| : | |\n| - | x |\n"
        inspection = MarkdownImporter().inspect(
            text.encode("utf-8"), "degenerate.md", ImportPolicy()
        )
        assert inspection.document is not None
        assert inspection.status is ImportStatus.OK
        rows = _nodes_of(inspection, NodeType.TABLE_ROW)
        assert len(rows) == 3  # header + two data rows
        cell_texts = [cell.text for row in rows for cell in _children(row, inspection)]
        assert ":" in cell_texts
        assert "-" in cell_texts


def _children(node: DocumentNode, inspection: ImportInspection) -> list[DocumentNode]:
    document = inspection.document
    assert document is not None
    return [candidate for candidate in document.nodes if candidate.parent_id == node.node_id]
