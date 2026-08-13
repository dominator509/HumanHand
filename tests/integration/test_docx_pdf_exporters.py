"""Integration tests for the DOCX and PDF public-document exporters (EP-016)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from pypdf import PdfReader

from humanhand.domain.export_contract import ExportFormat, ExportRequest
from humanhand.domain.public_document import PublicDocument, build_public_document
from humanhand.infra.exporters.base import ExporterError
from humanhand.infra.exporters.docx_exporter import DocxExporter
from humanhand.infra.exporters.pdf_exporter import PdfExporter


def _request(document: PublicDocument, output: Path, fmt: ExportFormat) -> ExportRequest:
    return ExportRequest(format=fmt, output_path=str(output), document=document)


@pytest.mark.importers
class TestDocxExporter:
    def test_package_contains_escaped_text(self, tmp_path: Path) -> None:
        document = build_public_document(
            title="Quarterly <Summary> & Notes",
            sections=("Revenue grew 10% & costs fell.",),
            claims=(),
        )
        output = tmp_path / "report.docx"
        DocxExporter().export(_request(document, output, ExportFormat.DOCX))

        with zipfile.ZipFile(output) as archive:
            names = set(archive.namelist())
            # Minimal OOXML package: content types, root rels, document, core props.
            assert "[Content_Types].xml" in names
            assert "_rels/.rels" in names
            assert "word/document.xml" in names
            assert "docProps/core.xml" in names
            document_xml = archive.read("word/document.xml").decode("utf-8")
            # XML-escaped text: "<" and "&" become entities inside w:t runs.
            assert "Quarterly &lt;Summary&gt; &amp; Notes" in document_xml
            assert "Revenue grew 10% &amp; costs fell." in document_xml
            core = archive.read("docProps/core.xml").decode("utf-8")
            assert "<dc:title>Quarterly &lt;Summary&gt; &amp; Notes</dc:title>" in core
            # Fresh package: no author or revision metadata.
            assert "Creator" not in core

    def test_claims_block_and_determinism(self, tmp_path: Path) -> None:
        document = build_public_document(
            title="Memo", sections=("One.",), claims=("First claim.", "Second claim.")
        )
        first = DocxExporter().export_bytes(document)
        second = DocxExporter().export_bytes(document)
        # Byte-deterministic for identical documents.
        assert first == second
        with zipfile.ZipFile(io.BytesIO(first)) as archive:
            document_xml = archive.read("word/document.xml").decode("utf-8")
        assert "Claims:" in document_xml
        assert "• First claim." in document_xml
        assert "• Second claim." in document_xml

    def test_refuses_humanhand_output_path(self, tmp_path: Path) -> None:
        document = build_public_document(title="Memo", sections=("One.",), claims=())
        output = tmp_path / ".humanhand" / "memo.docx"
        with pytest.raises(ExporterError):
            DocxExporter().export(_request(document, output, ExportFormat.DOCX))
        assert not output.exists()


@pytest.mark.importers
class TestPdfExporter:
    def test_pdf_readable_and_contains_title(self, tmp_path: Path) -> None:
        document = build_public_document(
            title="Annual Review",
            sections=("Findings are summarized here.",),
            claims=("Claim one.",),
        )
        output = tmp_path / "review.pdf"
        PdfExporter().export(_request(document, output, ExportFormat.PDF))

        raw = output.read_bytes()
        assert raw.startswith(b"%PDF")  # real PDF magic bytes
        reader = PdfReader(io.BytesIO(raw))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        assert "Annual Review" in text
        assert "Claims" in text

    def test_refuses_humanhand_output_path(self, tmp_path: Path) -> None:
        document = build_public_document(title="Review", sections=("One.",), claims=())
        output = tmp_path / ".humanhand" / "review.pdf"
        with pytest.raises(ExporterError):
            PdfExporter().export(_request(document, output, ExportFormat.PDF))
        assert not output.exists()
