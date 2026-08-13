"""Integration tests for the clean-room PDF importer (EP-013)."""

from __future__ import annotations

import io

import pytest
from pypdf import PdfReader

from humanhand.domain.canonical_document import ImportInspection
from humanhand.domain.document_nodes import NodeType
from humanhand.domain.document_serialization import document_to_json
from humanhand.domain.import_findings import (
    FindingCode,
    FindingSeverity,
    ImportFinding,
    ImportStatus,
)
from humanhand.domain.import_policy import ImportPolicy
from humanhand.infra.importers.pdf_importer import PdfImporter
from humanhand.infra.importers.pdf_inspection import (
    acroform_present,
    annotations_count,
    attachments_count,
    javascript_present,
    page_has_image,
)
from tests.integration.support.pdf_builder import (
    build_image_only_pdf,
    build_pdf,
    build_pdf_with_acroform,
    build_pdf_with_annotation,
    build_pdf_with_attachment,
    build_pdf_with_javascript,
    build_pdf_with_names_javascript,
)

SAMPLE_TEXT_PAGES = ["Hello PDF world.", "Second page line"]


def _inspect(raw: bytes, path: str = "sample.bin") -> ImportInspection:
    # An unknown-extension path is used so the full inspect() pipeline runs:
    # file_type.py (EP-012 baseline, outside this adapter's file scope) still
    # lists PDF under UNSUPPORTED_KINDS, so a ".pdf" path is hard-blocked by
    # the identity precheck with UNSUPPORTED_FORMAT before the adapter runs.
    # With a declared-UNKNOWN identity plus PDF magic there are no identity
    # findings, and parse_payloads executes exactly as it does in the worker.
    return PdfImporter().inspect(raw, path, ImportPolicy())


def _paragraph_texts(inspection: ImportInspection) -> list[str]:
    assert inspection.document is not None
    return [node.text for node in inspection.document.nodes if node.node_type is NodeType.PARAGRAPH]


def _findings_by_code(inspection: ImportInspection, code: str) -> list[ImportFinding]:
    return [finding for finding in inspection.findings if finding.code == code]


@pytest.mark.importers
class TestPdfImporter:
    def test_happy_path_text_pages_and_sections(self) -> None:
        inspection = _inspect(build_pdf(SAMPLE_TEXT_PAGES))
        assert inspection.status is ImportStatus.HUMAN_REVIEW_REQUIRED
        assert inspection.document is not None
        assert inspection.document.parser_name == "pdf"
        assert inspection.document.parser_version == "1"
        sections = [
            node for node in inspection.document.nodes if node.node_type is NodeType.SECTION
        ]
        assert len(sections) == 2
        assert _paragraph_texts(inspection) == SAMPLE_TEXT_PAGES
        assert inspection.document.surface_text == "Hello PDF world.\n\nSecond page line"

    def test_deterministic_replay(self) -> None:
        raw = build_pdf(SAMPLE_TEXT_PAGES)
        first = _inspect(raw)
        second = _inspect(raw)
        assert first.to_json(include_content=True) == second.to_json(include_content=True)
        assert first.document is not None
        assert second.document is not None
        assert document_to_json(first.document) == document_to_json(second.document)

    def test_javascript_openaction_flagged(self) -> None:
        inspection = _inspect(build_pdf_with_javascript(["Hello PDF world."]))
        assert inspection.status is ImportStatus.HUMAN_REVIEW_REQUIRED
        scripts = _findings_by_code(inspection, FindingCode.ACTIVE_CONTENT_SCRIPT)
        assert len(scripts) == 1
        assert scripts[0].severity is FindingSeverity.ERROR
        assert scripts[0].evidence == "pdf_javascript"

    def test_javascript_names_tree_flagged(self) -> None:
        inspection = _inspect(build_pdf_with_names_javascript(["Hello PDF world."]))
        assert inspection.status is ImportStatus.HUMAN_REVIEW_REQUIRED
        scripts = _findings_by_code(inspection, FindingCode.ACTIVE_CONTENT_SCRIPT)
        assert len(scripts) == 1

    def test_acroform_flagged(self) -> None:
        inspection = _inspect(build_pdf_with_acroform(["Hello PDF world."]))
        assert inspection.status is ImportStatus.HUMAN_REVIEW_REQUIRED
        unsupported = [
            finding
            for finding in inspection.findings
            if finding.description == "PDF contains an interactive form"
        ]
        assert len(unsupported) == 1
        assert unsupported[0].severity is FindingSeverity.WARNING
        assert unsupported[0].evidence == "acroform"

    def test_attachment_metadata_and_finding(self) -> None:
        inspection = _inspect(build_pdf_with_attachment(["Hello PDF world."]))
        by_key = {item.key: item for item in inspection.metadata.items}
        attachment = by_key["attachments"]
        assert attachment.kind == "pdf_attachments"
        assert attachment.value == "1"
        unsupported = [
            finding
            for finding in inspection.findings
            if finding.description == "PDF contains 1 embedded attachment(s)"
        ]
        assert len(unsupported) == 1
        assert unsupported[0].severity is FindingSeverity.WARNING
        assert unsupported[0].evidence == "attachments=1"

    def test_annotation_metadata(self) -> None:
        inspection = _inspect(build_pdf_with_annotation(["Hello PDF world."]))
        assert inspection.status is ImportStatus.HUMAN_REVIEW_REQUIRED
        by_key = {item.key: item for item in inspection.metadata.items}
        annotation = by_key["annotations"]
        assert annotation.kind == "pdf_annotations"
        assert annotation.value == "1"

    def test_not_a_pdf_fails_closed_in_parse_payloads(self) -> None:
        payloads = PdfImporter().parse_payloads(b"not a pdf at all", ImportPolicy())
        assert payloads["document"] is None
        findings = payloads["findings"]
        assert isinstance(findings, list)
        descriptions = [item["description"] for item in findings if isinstance(item, dict)]
        assert "Not a valid PDF" in descriptions

    def test_truncated_pdf_fails_closed_via_inspect(self) -> None:
        raw = build_pdf(["Hello PDF world."])
        truncated = raw[: len(raw) // 2]
        assert truncated.startswith(b"%PDF-")
        inspection = _inspect(truncated)
        assert inspection.status is ImportStatus.FAILED
        assert inspection.document is None
        assert any(finding.description == "Not a valid PDF" for finding in inspection.findings)

    def test_size_limit_blocks_document(self) -> None:
        raw = build_pdf(["Hello PDF world."])
        policy = ImportPolicy(max_bytes=len(raw) - 1)
        inspection = PdfImporter().inspect(raw, "sample.bin", policy)
        assert any(finding.code == FindingCode.LIMIT_BYTES for finding in inspection.findings)
        assert inspection.document is None

    def test_image_only_pdf_fails_closed(self) -> None:
        inspection = _inspect(build_image_only_pdf(), path="image.bin")
        assert inspection.document is None
        errors = [
            finding for finding in inspection.findings if finding.severity is FindingSeverity.ERROR
        ]
        assert len(errors) == 1
        assert errors[0].code == FindingCode.UNSUPPORTED_FEATURE
        assert errors[0].evidence == "image_only_pdf"
        warnings = [finding for finding in inspection.findings if finding.evidence == "page=1"]
        assert len(warnings) == 1
        assert warnings[0].severity is FindingSeverity.WARNING

    def test_coverage_declares_honest_limitations(self) -> None:
        inspection = _inspect(build_pdf(SAMPLE_TEXT_PAGES))
        assert inspection.coverage.status == "partial"
        assert set(inspection.coverage.supported_structures) == {
            "section",
            "paragraph",
            "image_placeholder",
        }
        assert "reading_order_verification" in inspection.coverage.unsupported_structures
        assert "ocr_layer_detection" in inspection.coverage.unsupported_structures

    def test_unverified_reading_order_requires_human_review(self) -> None:
        inspection = _inspect(build_pdf(SAMPLE_TEXT_PAGES))
        findings = _findings_by_code(
            inspection,
            FindingCode.STRUCTURE_READING_ORDER_UNVERIFIED,
        )
        assert inspection.status is ImportStatus.HUMAN_REVIEW_REQUIRED
        assert len(findings) == 1
        assert findings[0].severity is FindingSeverity.ERROR
        assert findings[0].evidence == "reading_order_unverified"

    def test_input_bytes_unchanged(self) -> None:
        raw = build_pdf(SAMPLE_TEXT_PAGES)
        snapshot = raw
        _inspect(raw)
        assert raw == snapshot


@pytest.mark.importers
class TestPdfInspectionHelpers:
    def test_javascript_detected_in_openaction(self) -> None:
        reader = PdfReader(io.BytesIO(build_pdf_with_javascript(["x"])))
        assert javascript_present(reader) is True

    def test_javascript_detected_in_names_tree(self) -> None:
        reader = PdfReader(io.BytesIO(build_pdf_with_names_javascript(["x"])))
        assert javascript_present(reader) is True

    def test_acroform_detected(self) -> None:
        reader = PdfReader(io.BytesIO(build_pdf_with_acroform(["x"])))
        assert acroform_present(reader) is True

    def test_attachments_counted(self) -> None:
        reader = PdfReader(io.BytesIO(build_pdf_with_attachment(["x"])))
        assert attachments_count(reader) == 1

    def test_annotations_counted(self) -> None:
        reader = PdfReader(io.BytesIO(build_pdf_with_annotation(["x"])))
        assert annotations_count(reader) == 1

    def test_page_has_image_detects_image_xobject(self) -> None:
        reader = PdfReader(io.BytesIO(build_image_only_pdf()))
        assert page_has_image(reader.pages[0]) is True

    def test_plain_pdf_reports_no_features(self) -> None:
        reader = PdfReader(io.BytesIO(build_pdf(["Hello PDF world."])))
        assert javascript_present(reader) is False
        assert acroform_present(reader) is False
        assert attachments_count(reader) == 0
        assert annotations_count(reader) == 0
        assert page_has_image(reader.pages[0]) is False
