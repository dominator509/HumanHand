"""Integration tests for the clean-room DOCX importer adapter.

The adapter never opens files, never touches the network, and never
executes content; all fixtures are built in memory by
``tests.integration.support.docx_builder``.
"""

from __future__ import annotations

import io
import zipfile

import pytest

from humanhand.domain.canonical_document import ImportInspection
from humanhand.domain.document_nodes import NodeType
from humanhand.domain.import_findings import (
    FindingCode,
    FindingSeverity,
    ImportStatus,
)
from humanhand.domain.import_policy import ImportPolicy
from humanhand.infra.importers.docx_importer import DocxImporter
from tests.integration.support.docx_builder import build_docx


@pytest.mark.importers
class TestDocxImporter:
    """Focused clean-room DOCX import pipeline tests."""

    def _inspect(self, raw: bytes, path: str = "sample.docx") -> ImportInspection:
        return DocxImporter().inspect(raw, path, ImportPolicy())

    def _findings_by_code(self, inspection: ImportInspection) -> dict[str, list[str]]:
        by_code: dict[str, list[str]] = {}
        for finding in inspection.findings:
            by_code.setdefault(finding.code, []).append(finding.evidence)
        return by_code

    def test_docx_parses_ok(self) -> None:
        raw = build_docx(["First paragraph", "Second paragraph"])
        inspection = self._inspect(raw)

        assert inspection.status is ImportStatus.OK
        assert inspection.document is not None
        assert "First paragraph" in inspection.document.canonical_text
        assert "Second paragraph" in inspection.document.canonical_text
        assert inspection.coverage.status == "complete"
        assert "paragraph" in inspection.coverage.supported_structures
        assert inspection.coverage.unsupported_structures == ()

    def test_docx_payload_is_deterministic(self) -> None:
        raw = build_docx(["Deterministic line one", "Deterministic line two"])
        first = self._inspect(raw).to_json(include_content=True)
        second = self._inspect(raw).to_json(include_content=True)

        assert first == second

    def test_docx_comments_are_findings(self) -> None:
        raw = build_docx(["First paragraph"], comments=True)
        inspection = self._inspect(raw)

        assert inspection.status is ImportStatus.FINDINGS
        by_code = self._findings_by_code(inspection)
        assert FindingCode.REVISION_COMMENTS in by_code
        comments_finding = next(
            f for f in inspection.findings if f.code == FindingCode.REVISION_COMMENTS
        )
        assert comments_finding.severity is FindingSeverity.WARNING
        assert comments_finding.evidence == "comments"
        # Warnings never block document construction.
        assert inspection.document is not None

    def test_docx_tracked_changes_require_review(self) -> None:
        raw = build_docx(["First paragraph"], tracked_changes=True)
        inspection = self._inspect(raw)

        assert inspection.status is ImportStatus.HUMAN_REVIEW_REQUIRED
        by_code = self._findings_by_code(inspection)
        assert FindingCode.REVISION_TRACKED_CHANGES in by_code
        tracked_finding = next(
            f for f in inspection.findings if f.code == FindingCode.REVISION_TRACKED_CHANGES
        )
        assert tracked_finding.severity is FindingSeverity.ERROR
        assert tracked_finding.evidence == "tracked_changes"
        assert inspection.document is not None

    def test_docx_macros_require_review(self) -> None:
        raw = build_docx(["First paragraph"], macros=True)
        inspection = self._inspect(raw)

        assert inspection.status is ImportStatus.HUMAN_REVIEW_REQUIRED
        by_code = self._findings_by_code(inspection)
        assert FindingCode.ACTIVE_CONTENT_MACRO in by_code
        macro_finding = next(
            f for f in inspection.findings if f.code == FindingCode.ACTIVE_CONTENT_MACRO
        )
        assert macro_finding.severity is FindingSeverity.ERROR
        assert macro_finding.evidence == "part=word/vbaProject.bin"

    def test_docx_external_link_evidence_is_scheme_host(self) -> None:
        raw = build_docx(["First paragraph"], external_link=True)
        inspection = self._inspect(raw)

        assert inspection.status is ImportStatus.HUMAN_REVIEW_REQUIRED
        by_code = self._findings_by_code(inspection)
        assert FindingCode.EXTERNAL_REMOTE_RESOURCE in by_code
        assert by_code[FindingCode.EXTERNAL_REMOTE_RESOURCE] == ["https://example.com"]

    def test_malformed_relationship_part_fails_closed(self) -> None:
        source = io.BytesIO(build_docx(["First paragraph"], external_link=True))
        output = io.BytesIO()
        with zipfile.ZipFile(source) as original, zipfile.ZipFile(output, "w") as rebuilt:
            for info in original.infolist():
                payload = original.read(info)
                if info.filename == "word/_rels/document.xml.rels":
                    payload = b"<Relationships><broken>"
                rebuilt.writestr(info, payload)

        inspection = self._inspect(output.getvalue())

        assert inspection.status is ImportStatus.FAILED
        assert any(
            finding.evidence == "malformed=word/_rels/document.xml.rels"
            for finding in inspection.findings
        )

    def test_duplicate_container_entry_fails_closed(self) -> None:
        buffer = io.BytesIO(build_docx(["First paragraph"]))
        with (
            pytest.warns(UserWarning, match="Duplicate name"),
            zipfile.ZipFile(buffer, "a") as archive,
        ):
            archive.writestr("word/document.xml", b"duplicate")

        inspection = self._inspect(buffer.getvalue())

        assert inspection.status is ImportStatus.FAILED
        assert inspection.document is None
        duplicate_findings = [
            finding
            for finding in inspection.findings
            if finding.code == FindingCode.CONTAINER_DUPLICATE_ENTRY
        ]
        assert len(duplicate_findings) == 1
        assert duplicate_findings[0].evidence == "duplicates=1"

    def test_docx_core_properties_are_metadata(self) -> None:
        raw = build_docx(["First paragraph"], properties=True)
        inspection = self._inspect(raw)

        assert inspection.status is ImportStatus.OK
        items = inspection.metadata.items
        assert ("core:title", "docx_property", "Synthetic Document") in {
            (item.key, item.kind, item.value) for item in items
        }
        assert ("core:creator", "docx_property", "Synthetic Author") in {
            (item.key, item.kind, item.value) for item in items
        }

    def test_docx_expanded_limit_blocks_document(self) -> None:
        raw = build_docx(["First paragraph"])
        policy = ImportPolicy(max_expanded_bytes=100)
        inspection = DocxImporter().inspect(raw, "sample.docx", policy)

        assert inspection.status is ImportStatus.FAILED
        by_code = self._findings_by_code(inspection)
        assert FindingCode.LIMIT_EXPANDED_BYTES in by_code
        assert inspection.document is None
        assert inspection.coverage.unsupported_structures == ("container",)

    def test_docx_not_a_zip_fails_closed(self) -> None:
        raw = b"not a zip at all"
        payloads = DocxImporter().parse_payloads(raw, ImportPolicy())

        assert payloads["status"] == ImportStatus.FAILED.value
        findings_payload = payloads["findings"]
        assert isinstance(findings_payload, list)
        finding_codes = {item["code"] for item in findings_payload if isinstance(item, dict)}
        assert FindingCode.UNSUPPORTED_FEATURE in finding_codes
        assert any(
            item["description"] == "Not a valid ZIP container"
            for item in findings_payload
            if isinstance(item, dict)
        )
        assert payloads["document"] is None

    def test_docx_text_extension_mismatch_quarantines(self) -> None:
        # Plain text named .docx is a magic mismatch, never a parse attempt.
        inspection = self._inspect(b"this is not a zip", "sample.docx")

        assert inspection.status is ImportStatus.QUARANTINED
        by_code = self._findings_by_code(inspection)
        assert FindingCode.MAGIC_MISMATCH in by_code
        assert inspection.document is None

    def test_docx_table_structure(self) -> None:
        raw = build_docx(["First paragraph"], table=True)
        inspection = self._inspect(raw)

        assert inspection.status is ImportStatus.OK
        assert inspection.document is not None
        assert "table" in inspection.coverage.supported_structures
        nodes = inspection.document.nodes
        table_nodes = [node for node in nodes if node.node_type is NodeType.TABLE]
        row_nodes = [node for node in nodes if node.node_type is NodeType.TABLE_ROW]
        cell_nodes = [node for node in nodes if node.node_type is NodeType.TABLE_CELL]
        assert len(table_nodes) == 1
        assert len(row_nodes) == 2
        assert len(cell_nodes) == 4
        assert {cell.text for cell in cell_nodes} == {"alpha", "beta", "gamma", "delta"}
        surface_text = inspection.document.surface_text
        for cell in cell_nodes:
            assert cell.source_location is not None
            assert (
                surface_text[cell.source_location.start_offset : cell.source_location.end_offset]
                == cell.text
            )

    def test_docx_raw_bytes_never_modified(self) -> None:
        raw = build_docx(["First paragraph"], comments=True)
        snapshot = bytes(raw)
        self._inspect(raw)

        assert raw == snapshot
