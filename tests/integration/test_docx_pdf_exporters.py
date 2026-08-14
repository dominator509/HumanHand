"""Integration tests for metadata-free DOCX and PDF public exporters."""

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
    def test_package_contains_only_approved_content_parts(self, tmp_path: Path) -> None:
        document = build_public_document(
            title="Quarterly <Summary> & Notes",
            sections=("Revenue grew 10% & costs fell.",),
            claims=("Internal validation claim.",),
        )
        output = tmp_path / "report.docx"
        DocxExporter().export(_request(document, output, ExportFormat.DOCX))

        with zipfile.ZipFile(output) as archive:
            assert archive.namelist() == [
                "[Content_Types].xml",
                "_rels/.rels",
                "word/document.xml",
            ]
            document_xml = archive.read("word/document.xml").decode("utf-8")
            assert "Quarterly &lt;Summary&gt; &amp; Notes" in document_xml
            assert "Revenue grew 10% &amp; costs fell." in document_xml
            assert "Internal validation claim" not in document_xml
            assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())

    def test_content_only_output_is_byte_deterministic(self) -> None:
        document = build_public_document(
            title="Memo",
            sections=("One.",),
            claims=("First internal claim.", "Second internal claim."),
        )
        first = DocxExporter().export_bytes(document)
        second = DocxExporter().export_bytes(document)
        assert first == second
        with zipfile.ZipFile(io.BytesIO(first)) as archive:
            package = b"\n".join(archive.read(name) for name in archive.namelist())
        assert b"Claims:" not in package
        assert b"First internal claim" not in package
        assert b"docProps" not in package

    def test_refuses_humanhand_output_path(self, tmp_path: Path) -> None:
        document = build_public_document(title="Memo", sections=("One.",), claims=())
        output = tmp_path / ".humanhand" / "memo.docx"
        with pytest.raises(ExporterError):
            DocxExporter().export(_request(document, output, ExportFormat.DOCX))
        assert not output.exists()


@pytest.mark.importers
class TestPdfExporter:
    def test_pdf_is_content_only_and_metadata_free(self, tmp_path: Path) -> None:
        document = build_public_document(
            title="Annual Review",
            sections=("Findings are summarized here.",),
            claims=("Internal claim one.",),
        )
        output = tmp_path / "review.pdf"
        PdfExporter().export(_request(document, output, ExportFormat.PDF))

        raw = output.read_bytes()
        assert raw.startswith(b"%PDF")
        reader = PdfReader(io.BytesIO(raw), strict=True)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        assert "Annual Review" in text
        assert "Findings are summarized here." in text
        assert "Internal claim one" not in text
        assert not reader.metadata
        assert reader.xmp_metadata is None
        assert reader.trailer.get("/ID") is None
        assert "/Metadata" not in reader.root_object

    def test_pdf_bytes_are_deterministic_for_equal_content(self) -> None:
        document = build_public_document(
            title="Review",
            sections=("One.", "Two."),
            claims=("Internal claim.",),
        )
        assert PdfExporter().export_bytes(document) == PdfExporter().export_bytes(document)

    def test_refuses_humanhand_output_path(self, tmp_path: Path) -> None:
        document = build_public_document(title="Review", sections=("One.",), claims=())
        output = tmp_path / ".humanhand" / "review.pdf"
        with pytest.raises(ExporterError):
            PdfExporter().export(_request(document, output, ExportFormat.PDF))
        assert not output.exists()
