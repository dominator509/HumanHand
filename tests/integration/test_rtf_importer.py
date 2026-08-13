"""Integration tests for the clean-room RTF importer (EP-013)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from humanhand.domain.canonical_document import CanonicalDocument, CoverageSummary
from humanhand.domain.document_nodes import DocumentNode, NodeType
from humanhand.domain.document_serialization import (
    document_from_json,
    document_to_json,
    finding_from_payload,
)
from humanhand.domain.import_findings import (
    FindingCategory,
    FindingCode,
    FindingSeverity,
    ImportFinding,
    ImportStatus,
)
from humanhand.domain.import_policy import ImportPolicy
from humanhand.infra.importers.rtf_importer import RtfImporter

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "import"

SAMPLE_RTF = (FIXTURES_DIR / "sample.rtf").read_bytes()

# In-file variants: all start with the RTF magic so identity checks agree
# with the declared kind.
EMBEDDED_OBJECT_RTF = b"{\\rtf1\\ansi{\\object{\\objdata 010203}}}"
FIELD_RTF = b'{\\rtf1\\ansi{\\field{\\*\\fldinst HYPERLINK "https://example.com"}}}'
TABLE_RTF = b"{\\rtf1\\ansi\\trowd\\cellx1000 cell text\\cell\\row}"
UTF8_BOM_RTF = b"\xef\xbb\xbf{\\rtf1\\ansi Hello}"
UTF16_LE_BOM_RTF = b"\xff\xfe{\\rtf1\\ansi\\par}"

EMBED_OBJECT_DESCRIPTION = "RTF contains an embedded object"
FIELD_DESCRIPTION = "RTF contains dynamic fields"
TABLE_DESCRIPTION = "RTF table structure is not represented in the canonical AST"

# file_type.py (EP-012 gate, not editable in this plan's seam) resolves RTF
# to an unsupported format, so inspect() fails closed before parsing. The
# adapter's contract is parse_payloads; tests drive that seam and rebuild
# domain objects from the envelope exactly as assemble_inspection does.


def _parse(raw: bytes, policy: ImportPolicy | None = None) -> dict[str, object]:
    return RtfImporter().parse_payloads(raw, policy if policy is not None else ImportPolicy())


def _document(payloads: dict[str, object]) -> CanonicalDocument:
    document_payload = payloads["document"]
    assert document_payload is not None
    return document_from_json(json.dumps(document_payload, ensure_ascii=False))


def _findings(payloads: dict[str, object]) -> list[ImportFinding]:
    raw = payloads["findings"]
    assert isinstance(raw, list)
    return [finding_from_payload(item, "finding") for item in raw if isinstance(item, dict)]


def _coverage(payloads: dict[str, object]) -> CoverageSummary:
    payload = payloads["coverage"]
    assert isinstance(payload, dict)
    supported = payload["supported_structures"]
    unsupported = payload["unsupported_structures"]
    assert isinstance(supported, list)
    assert isinstance(unsupported, list)
    return CoverageSummary(
        adapter=str(payload["adapter"]),
        supported_structures=tuple(str(item) for item in supported),
        unsupported_structures=tuple(str(item) for item in unsupported),
        status=str(payload["status"]),
    )


def _nodes_of(payloads: dict[str, object], node_type: NodeType) -> list[DocumentNode]:
    return [node for node in _document(payloads).nodes if node.node_type is node_type]


@pytest.mark.importers
class TestRtfImporter:
    def test_sample_structure_and_status(self) -> None:
        payloads = _parse(SAMPLE_RTF)
        assert payloads["status"] == ImportStatus.OK
        document = _document(payloads)
        assert document.parser_name == "rtf"
        assert document.parser_version == "1"
        assert document.root.node_type is NodeType.DOCUMENT
        assert _findings(payloads) == []

        paragraphs = _nodes_of(payloads, NodeType.PARAGRAPH)
        assert [paragraph.text for paragraph in paragraphs] == [
            "Hello RTF world.",
            "Second paragraph with café and a é fallback.",
        ]
        assert document.surface_text == (
            "Hello RTF world.\nSecond paragraph with café and a é fallback.\n"
        )
        coverage = _coverage(payloads)
        assert coverage.supported_structures == ("paragraph",)
        assert coverage.unsupported_structures == ()
        assert coverage.status == "complete"

    def test_canonical_json_is_deterministic(self) -> None:
        first = _document(_parse(SAMPLE_RTF))
        second = _document(_parse(SAMPLE_RTF))
        assert document_to_json(first) == document_to_json(second)

    def test_embedded_object_review_required(self) -> None:
        payloads = _parse(EMBEDDED_OBJECT_RTF)
        assert payloads["status"] == ImportStatus.HUMAN_REVIEW_REQUIRED
        object_findings = [
            finding
            for finding in _findings(payloads)
            if finding.code == FindingCode.ACTIVE_CONTENT_EMBED_OBJECT
        ]
        assert len(object_findings) == 1
        assert object_findings[0].severity is FindingSeverity.ERROR
        assert object_findings[0].category is FindingCategory.ACTIVE_CONTENT
        assert object_findings[0].description == EMBED_OBJECT_DESCRIPTION
        assert object_findings[0].evidence == "rtf_object"
        coverage = _coverage(payloads)
        assert "object" in coverage.unsupported_structures
        assert coverage.status == "partial"
        assert _document(payloads).surface_text == ""
        assert _nodes_of(payloads, NodeType.PARAGRAPH) == []

    def test_dynamic_field_warning(self) -> None:
        payloads = _parse(FIELD_RTF)
        assert payloads["status"] == ImportStatus.FINDINGS
        field_findings = [
            finding
            for finding in _findings(payloads)
            if finding.code == FindingCode.UNSUPPORTED_FEATURE and finding.evidence == "rtf_field"
        ]
        assert len(field_findings) == 1
        assert field_findings[0].severity is FindingSeverity.WARNING
        assert field_findings[0].category is FindingCategory.UNSUPPORTED_FEATURE
        assert field_findings[0].description == FIELD_DESCRIPTION
        coverage = _coverage(payloads)
        assert "field" in coverage.unsupported_structures
        assert coverage.status == "partial"
        assert _document(payloads).surface_text == ""

    def test_table_structure_warning(self) -> None:
        payloads = _parse(TABLE_RTF)
        assert payloads["status"] == ImportStatus.FINDINGS
        table_findings = [
            finding
            for finding in _findings(payloads)
            if finding.code == FindingCode.UNSUPPORTED_FEATURE and finding.evidence == "rtf_table"
        ]
        assert len(table_findings) == 1
        assert table_findings[0].severity is FindingSeverity.WARNING
        assert table_findings[0].category is FindingCategory.UNSUPPORTED_FEATURE
        assert table_findings[0].description == TABLE_DESCRIPTION
        coverage = _coverage(payloads)
        assert "table" in coverage.unsupported_structures
        assert coverage.status == "partial"
        # Cell text still flows into paragraphs; \cell and \row become breaks.
        # The space after \cellx1000 is that control word's delimiter, not content.
        assert _document(payloads).surface_text == "cell text\n\n"
        paragraph_texts = [node.text for node in _nodes_of(payloads, NodeType.PARAGRAPH)]
        assert paragraph_texts == ["cell text"]

    def test_garbage_bytes_quarantined(self) -> None:
        # The identity gate is the subject here, so drive inspect() directly:
        # an .rtf name over non-RTF magic fails closed with MAGIC_MISMATCH.
        raw = b"not rtf at all"
        inspection = RtfImporter().inspect(raw, "garbage.rtf", ImportPolicy())
        assert inspection.status is ImportStatus.QUARANTINED
        assert inspection.document is None
        mismatch = [
            finding for finding in inspection.findings if finding.code == FindingCode.MAGIC_MISMATCH
        ]
        assert len(mismatch) == 1
        assert mismatch[0].severity is FindingSeverity.ERROR
        assert mismatch[0].category is FindingCategory.MAGIC_MISMATCH

    def test_size_limit_enforced(self) -> None:
        policy = ImportPolicy(lane="source", max_bytes=10)
        payloads = _parse(SAMPLE_RTF, policy)
        assert payloads["status"] == ImportStatus.FAILED
        assert payloads["document"] is None
        limit_findings = [
            finding for finding in _findings(payloads) if finding.code == FindingCode.LIMIT_BYTES
        ]
        assert len(limit_findings) == 1
        assert limit_findings[0].severity is FindingSeverity.ERROR
        assert limit_findings[0].category is FindingCategory.RESOURCE_LIMIT

    def test_input_bytes_unchanged(self) -> None:
        original = SAMPLE_RTF
        _parse(original)
        assert original == SAMPLE_RTF

    def test_paragraph_spans_align_with_surface_text(self) -> None:
        payloads = _parse(SAMPLE_RTF)
        surface_text = _document(payloads).surface_text
        for node in _nodes_of(payloads, NodeType.PARAGRAPH):
            location = node.source_location
            assert location is not None
            assert 0 <= location.start_offset <= location.end_offset <= len(surface_text)
            assert 1 <= location.line_start <= location.line_end
            assert surface_text[location.start_offset : location.end_offset] == node.text

    def test_utf8_bom_warns_and_is_stripped(self) -> None:
        payloads = _parse(UTF8_BOM_RTF)
        assert payloads["status"] == "findings"
        bom_findings = [
            finding for finding in _findings(payloads) if finding.code == FindingCode.ENCODING_BOM
        ]
        assert len(bom_findings) == 1
        assert bom_findings[0].severity is FindingSeverity.WARNING
        assert bom_findings[0].category is FindingCategory.ENCODING
        unicode_payload = payloads["unicode"]
        assert isinstance(unicode_payload, dict)
        assert unicode_payload["has_bom"] is True
        assert unicode_payload["bom_name"] == "utf-8"
        node_texts = [node.text for node in _document(payloads).nodes if node.text]
        assert node_texts == ["Hello"]

    def test_utf16_bom_rejected(self) -> None:
        payloads = _parse(UTF16_LE_BOM_RTF)
        assert payloads["status"] == ImportStatus.FAILED
        assert payloads["document"] is None
        unsupported = [
            finding
            for finding in _findings(payloads)
            if finding.code == FindingCode.ENCODING_UTF16_UNSUPPORTED
        ]
        assert len(unsupported) == 1
        assert unsupported[0].severity is FindingSeverity.ERROR
