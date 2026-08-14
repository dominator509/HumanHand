"""Integration tests for independent metadata-free public artifact auditors."""

from __future__ import annotations

import io
import unicodedata
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from humanhand.domain.artifact_findings import (
    ArtifactAuditReport,
    ArtifactAuditStatus,
    ArtifactFindingSeverity,
)
from humanhand.domain.public_document import PublicDocument, build_public_document
from humanhand.infra.auditors import (
    AuditorError,
    DocxAuditor,
    MarkdownAuditor,
    PackageAuditor,
    PdfAuditor,
    TextAuditor,
    UnicodeAuditor,
    audit_artifact,
    auditor_for,
)
from humanhand.infra.auditors.base import AuditCode
from humanhand.infra.exporters import (
    DOCX_EXPORTER,
    MARKDOWN_EXPORTER,
    PDF_EXPORTER,
    TXT_EXPORTER,
)
from tests.integration.support.pdf_builder import (
    build_pdf_with_acroform,
    build_pdf_with_attachment,
    build_pdf_with_javascript,
    build_pdf_with_names_javascript,
)

TITLE = "Synthetic Sample"
SECTIONS = (
    "The quick brown fox jumps over the lazy dog.",
    "A second paragraph describing the content.",
)
CLAIMS = ("Internal validation claim that must remain private.",)
EXTRA_SECTION = "An extra section that is not present in the artifact."


def sample_document(*, claims: tuple[str, ...] = CLAIMS) -> PublicDocument:
    return build_public_document(title=TITLE, sections=SECTIONS, claims=claims)


def error_codes(report: ArtifactAuditReport) -> set[str]:
    return {
        finding.code
        for finding in report.findings
        if finding.severity is ArtifactFindingSeverity.ERROR
    }


def all_codes(report: ArtifactAuditReport) -> set[str]:
    return {finding.code for finding in report.findings}


def replace_zip_part(data: bytes, part_name: str, new_part: bytes) -> bytes:
    buffer = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(data), "r") as source,
        zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as target,
    ):
        for name in source.namelist():
            target.writestr(name, new_part if name == part_name else source.read(name))
    return buffer.getvalue()


def add_zip_part(data: bytes, part_name: str, part_bytes: bytes) -> bytes:
    buffer = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(data), "r") as source,
        zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as target,
    ):
        for name in source.namelist():
            target.writestr(name, source.read(name))
        target.writestr(part_name, part_bytes)
    return buffer.getvalue()


def add_pdf_metadata(data: bytes) -> bytes:
    reader = PdfReader(io.BytesIO(data), strict=True)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.add_metadata({"/Producer": "Injected Test Producer"})
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def write(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


@pytest.mark.importers
class TestTextAuditor:
    def test_clean_exporter_txt_passes(self, tmp_path: Path) -> None:
        artifact = write(tmp_path / "document.txt", TXT_EXPORTER.export_bytes(sample_document()))
        report = TextAuditor().audit_file(artifact, expected=sample_document())
        assert report.status is ArtifactAuditStatus.PASS
        assert report.findings == ()
        assert CLAIMS[0].encode() not in artifact.read_bytes()

    @pytest.mark.parametrize(
        ("name", "mutator", "code"),
        [
            ("bom.txt", lambda data: b"\xef\xbb\xbf" + data, AuditCode.UTF8_BOM),
            (
                "crlf.txt",
                lambda data: data.replace(b"\n", b"\r\n"),
                AuditCode.LINE_ENDINGS_CR,
            ),
            (
                "missing-newline.txt",
                lambda data: data[:-1],
                AuditCode.TRAILING_NEWLINE_MISSING,
            ),
            (
                "extra-newline.txt",
                lambda data: data + b"\n",
                AuditCode.TRAILING_NEWLINE_EXTRA,
            ),
        ],
    )
    def test_byte_contract_tampers_fail(
        self,
        tmp_path: Path,
        name: str,
        mutator: Callable[[bytes], bytes],
        code: str,
    ) -> None:
        data = mutator(TXT_EXPORTER.export_bytes(sample_document()))
        report = TextAuditor().audit_file(write(tmp_path / name, data), expected=sample_document())
        assert report.status is ArtifactAuditStatus.FAIL
        assert code in error_codes(report)

    def test_prohibited_identifier_and_missing_content_fail(self, tmp_path: Path) -> None:
        data = TXT_EXPORTER.export_bytes(sample_document())[:-1] + b" project_id=42\n"
        report = TextAuditor().audit_file(write(tmp_path / "meta.txt", data), expected=sample_document())
        assert AuditCode.METADATA_PROHIBITED in error_codes(report)

        expected = build_public_document(
            title=TITLE,
            sections=(*SECTIONS, EXTRA_SECTION),
            claims=(),
        )
        report = TextAuditor().audit_file(
            write(tmp_path / "missing.txt", TXT_EXPORTER.export_bytes(sample_document())),
            expected=expected,
        )
        assert AuditCode.CONTENT_MISSING in error_codes(report)

    def test_sections_must_remain_ordered(self, tmp_path: Path) -> None:
        reversed_doc = build_public_document(
            title=TITLE,
            sections=(SECTIONS[1], SECTIONS[0]),
            claims=(),
        )
        report = TextAuditor().audit_file(
            write(tmp_path / "order.txt", TXT_EXPORTER.export_bytes(reversed_doc)),
            expected=sample_document(),
        )
        assert AuditCode.CONTENT_MISSING in error_codes(report)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(AuditorError):
            TextAuditor().audit_file(tmp_path / "missing.txt", expected=None)


@pytest.mark.importers
class TestMarkdownAuditor:
    def test_clean_content_only_markdown_passes(self, tmp_path: Path) -> None:
        artifact = write(
            tmp_path / "document.md",
            MARKDOWN_EXPORTER.export_bytes(sample_document()),
        )
        report = MarkdownAuditor().audit_file(artifact, expected=sample_document())
        assert report.status is ArtifactAuditStatus.PASS
        assert b"## Claims" not in artifact.read_bytes()
        assert CLAIMS[0].encode() not in artifact.read_bytes()

    def test_internal_claims_appendix_fails(self, tmp_path: Path) -> None:
        data = MARKDOWN_EXPORTER.export_bytes(sample_document())[:-1]
        data += b"\n\n## Claims\n\n- Private claim\n"
        report = MarkdownAuditor().audit_file(
            write(tmp_path / "claims.md", data),
            expected=sample_document(),
        )
        assert AuditCode.CLAIMS_HEADING in error_codes(report)

    def test_missing_title_and_active_content_fail(self, tmp_path: Path) -> None:
        data = MARKDOWN_EXPORTER.export_bytes(sample_document()).replace(
            b"# Synthetic Sample",
            b"Synthetic Sample",
        )
        report = MarkdownAuditor().audit_file(
            write(tmp_path / "notitle.md", data),
            expected=sample_document(),
        )
        assert AuditCode.HEADING_TITLE in error_codes(report)

        data = MARKDOWN_EXPORTER.export_bytes(sample_document())[:-1]
        data += b"\n<script>alert(1)</script>\n"
        report = MarkdownAuditor().audit_file(
            write(tmp_path / "script.md", data),
            expected=sample_document(),
        )
        assert AuditCode.HTML_ACTIVE_CONTENT in error_codes(report)

        data = MARKDOWN_EXPORTER.export_bytes(sample_document())[:-1]
        data += b"\n[remote](https://example.invalid/resource)\n"
        report = MarkdownAuditor().audit_file(
            write(tmp_path / "remote.md", data),
            expected=sample_document(),
        )
        assert AuditCode.HTML_ACTIVE_CONTENT in error_codes(report)


@pytest.mark.importers
class TestUnicodeAuditor:
    def test_clean_exporter_txt_passes(self, tmp_path: Path) -> None:
        artifact = write(tmp_path / "clean.txt", TXT_EXPORTER.export_bytes(sample_document()))
        assert UnicodeAuditor().audit_file(artifact, expected=None).status is ArtifactAuditStatus.PASS

    def test_control_invalid_utf8_nfd_and_surrogate_findings(self, tmp_path: Path) -> None:
        control = UnicodeAuditor().audit_file(
            write(tmp_path / "control.txt", b"one\x01two\n"),
            expected=None,
        )
        assert AuditCode.UNICODE_CONTROL_CHARS in error_codes(control)

        invalid = UnicodeAuditor().audit_file(
            write(tmp_path / "invalid.txt", b"\xff"),
            expected=None,
        )
        assert AuditCode.UNICODE_INVALID_UTF8 in error_codes(invalid)

        nfd = UnicodeAuditor.scan_unicode_text(unicodedata.normalize("NFD", "café"))
        assert {finding.code for finding in nfd} == {AuditCode.UNICODE_NOT_NFC}

        surrogate = UnicodeAuditor.scan_unicode_text("bad\ud800char")
        assert {finding.code for finding in surrogate} == {AuditCode.UNICODE_SURROGATES}


@pytest.mark.importers
class TestDocxAuditor:
    def test_clean_metadata_free_docx_passes(self, tmp_path: Path) -> None:
        artifact = write(tmp_path / "document.docx", DOCX_EXPORTER.export_bytes(sample_document()))
        report = DocxAuditor().audit_file(artifact, expected=sample_document())
        assert report.status is ArtifactAuditStatus.PASS
        with zipfile.ZipFile(artifact) as archive:
            assert archive.namelist() == [
                "[Content_Types].xml",
                "_rels/.rels",
                "word/document.xml",
            ]

    def test_corrupt_malformed_and_missing_content_fail(self, tmp_path: Path) -> None:
        corrupt = DOCX_EXPORTER.export_bytes(sample_document())[:-22]
        report = DocxAuditor().audit_file(
            write(tmp_path / "bad.docx", corrupt),
            expected=sample_document(),
        )
        assert AuditCode.DOCX_ZIP_INVALID in error_codes(report)

        malformed = replace_zip_part(
            DOCX_EXPORTER.export_bytes(sample_document()),
            "word/document.xml",
            b"<w:document><w:body>",
        )
        report = DocxAuditor().audit_file(
            write(tmp_path / "badxml.docx", malformed),
            expected=sample_document(),
        )
        assert AuditCode.DOCX_DOCUMENT_XML_MALFORMED in error_codes(report)

        expected = build_public_document(
            title=TITLE,
            sections=(*SECTIONS, EXTRA_SECTION),
            claims=(),
        )
        report = DocxAuditor().audit_file(
            write(tmp_path / "missing.docx", DOCX_EXPORTER.export_bytes(sample_document())),
            expected=expected,
        )
        assert AuditCode.CONTENT_MISSING in error_codes(report)

    @pytest.mark.parametrize(
        ("part", "content", "expected_code"),
        [
            ("docProps/core.xml", b"<core><creator>test</creator></core>", AuditCode.DOCX_METADATA_PROHIBITED),
            ("customXml/item1.xml", b"<meta/>", AuditCode.DOCX_METADATA_PROHIBITED),
            ("word/vbaProject.bin", b"VBA", AuditCode.DOCX_MACROS),
            ("custom/hidden.xml", b"<w:rPr><w:vanish/></w:rPr>", AuditCode.DOCX_HIDDEN_CONTENT),
            ("custom/revision.xml", b"<w:ins/>", AuditCode.DOCX_HIDDEN_CONTENT),
        ],
    )
    def test_prohibited_package_parts_or_markers_fail(
        self,
        tmp_path: Path,
        part: str,
        content: bytes,
        expected_code: str,
    ) -> None:
        data = add_zip_part(DOCX_EXPORTER.export_bytes(sample_document()), part, content)
        report = DocxAuditor().audit_file(
            write(tmp_path / "tampered.docx", data),
            expected=sample_document(),
        )
        assert expected_code in error_codes(report)

    def test_external_relationship_and_internal_identifier_fail(self, tmp_path: Path) -> None:
        relationships = (
            b'<Relationships><Relationship Target="https://example.invalid" '
            b'TargetMode="External"/></Relationships>'
        )
        data = add_zip_part(
            DOCX_EXPORTER.export_bytes(sample_document()),
            "word/_rels/document.xml.rels",
            relationships,
        )
        report = DocxAuditor().audit_file(
            write(tmp_path / "external.docx", data),
            expected=sample_document(),
        )
        assert AuditCode.DOCX_EXTERNAL_RELATIONSHIP in error_codes(report)

        data = add_zip_part(
            DOCX_EXPORTER.export_bytes(sample_document()),
            "custom/metadata.xml",
            b"<meta>project_id=42</meta>",
        )
        report = DocxAuditor().audit_file(
            write(tmp_path / "identifier.docx", data),
            expected=sample_document(),
        )
        assert AuditCode.DOCX_METADATA_PROHIBITED in error_codes(report)


@pytest.mark.importers
class TestPdfAuditor:
    def test_clean_metadata_free_pdf_passes(self, tmp_path: Path) -> None:
        artifact = write(tmp_path / "document.pdf", PDF_EXPORTER.export_bytes(sample_document()))
        report = PdfAuditor().audit_file(artifact, expected=sample_document())
        assert report.status is ArtifactAuditStatus.PASS
        reader = PdfReader(artifact, strict=True)
        assert not reader.metadata
        assert reader.xmp_metadata is None
        assert reader.trailer.get("/ID") is None

    def test_non_pdf_and_injected_metadata_fail(self, tmp_path: Path) -> None:
        report = PdfAuditor().audit_file(
            write(tmp_path / "fake.pdf", b"not a pdf"),
            expected=None,
        )
        assert AuditCode.PDF_OPEN_FAILED in error_codes(report)

        data = add_pdf_metadata(PDF_EXPORTER.export_bytes(sample_document()))
        report = PdfAuditor().audit_file(
            write(tmp_path / "metadata.pdf", data),
            expected=sample_document(),
        )
        assert AuditCode.METADATA_PROHIBITED in error_codes(report)

    @pytest.mark.parametrize(
        ("builder", "code"),
        [
            (build_pdf_with_javascript, AuditCode.PDF_JAVASCRIPT),
            (build_pdf_with_names_javascript, AuditCode.PDF_JAVASCRIPT),
            (build_pdf_with_acroform, AuditCode.PDF_ACTIVE_CONTENT),
            (build_pdf_with_attachment, AuditCode.PDF_ACTIVE_CONTENT),
        ],
    )
    def test_active_pdf_content_fails(
        self,
        tmp_path: Path,
        builder: Callable[[list[str]], bytes],
        code: str,
    ) -> None:
        report = PdfAuditor().audit_file(
            write(tmp_path / "active.pdf", builder(["Some page text."])),
            expected=None,
        )
        assert code in error_codes(report)

    def test_missing_expected_title_or_section_fails(self, tmp_path: Path) -> None:
        other_doc = build_public_document(title="Other Title", sections=SECTIONS, claims=())
        report = PdfAuditor().audit_file(
            write(tmp_path / "other.pdf", PDF_EXPORTER.export_bytes(other_doc)),
            expected=sample_document(),
        )
        assert AuditCode.TITLE_MISSING in error_codes(report)

        expected = build_public_document(
            title=TITLE,
            sections=(*SECTIONS, EXTRA_SECTION),
            claims=(),
        )
        report = PdfAuditor().audit_file(
            write(tmp_path / "missing.pdf", PDF_EXPORTER.export_bytes(sample_document())),
            expected=expected,
        )
        assert AuditCode.CONTENT_MISSING in error_codes(report)


@pytest.mark.importers
class TestRegistryAndPackageAuditor:
    def test_auditor_for_selects_by_extension(self) -> None:
        assert isinstance(auditor_for("a.txt"), TextAuditor)
        assert isinstance(auditor_for("a.md"), MarkdownAuditor)
        assert isinstance(auditor_for("a.docx"), DocxAuditor)
        assert isinstance(auditor_for("a.pdf"), PdfAuditor)
        assert isinstance(auditor_for("a.xyz"), PackageAuditor)

    def test_unknown_text_warns_and_binary_fails(self, tmp_path: Path) -> None:
        artifact = write(tmp_path / "doc.xyz", TXT_EXPORTER.export_bytes(sample_document()))
        report = audit_artifact(artifact, expected=sample_document())
        assert report.status is ArtifactAuditStatus.PASS
        assert all_codes(report) == {AuditCode.FORMAT_UNKNOWN}

        report = audit_artifact(write(tmp_path / "binary.xyz", b"\xff"), expected=None)
        assert report.status is ArtifactAuditStatus.FAIL
        assert AuditCode.UNICODE_INVALID_UTF8 in error_codes(report)

    def test_package_combines_unicode_and_unknown_findings(self, tmp_path: Path) -> None:
        report = PackageAuditor().audit_file(
            write(tmp_path / "doc.xyz", b"one\x01two\n"),
            expected=None,
        )
        assert report.status is ArtifactAuditStatus.FAIL
        assert all_codes(report) == {
            AuditCode.UNICODE_CONTROL_CHARS,
            AuditCode.FORMAT_UNKNOWN,
        }
