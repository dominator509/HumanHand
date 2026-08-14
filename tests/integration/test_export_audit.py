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


def sample_document(*, claims: tuple[str, ...] = CLAIMS) -> PublicDocument:
    return build_public_document(title=TITLE, sections=SECTIONS, claims=claims)


def error_codes(report: ArtifactAuditReport) -> set[str]:
    return {
        finding.code
        for finding in report.findings
        if finding.severity is ArtifactFindingSeverity.ERROR
    }


def write(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def add_zip_part(data: bytes, name: str, content: bytes) -> bytes:
    output = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(data)) as source,
        zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target,
    ):
        for existing in source.namelist():
            target.writestr(existing, source.read(existing))
        target.writestr(name, content)
    return output.getvalue()


def replace_zip_part(data: bytes, name: str, content: bytes) -> bytes:
    output = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(data)) as source,
        zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target,
    ):
        for existing in source.namelist():
            target.writestr(existing, content if existing == name else source.read(existing))
    return output.getvalue()


def add_pdf_metadata(data: bytes) -> bytes:
    reader = PdfReader(io.BytesIO(data), strict=True)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.add_metadata({"/Producer": "Injected Test Producer"})
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.mark.importers
class TestTextAndMarkdownAuditors:
    def test_clean_content_only_exports_pass(self, tmp_path: Path) -> None:
        txt = write(tmp_path / "document.txt", TXT_EXPORTER.export_bytes(sample_document()))
        md = write(
            tmp_path / "document.md",
            MARKDOWN_EXPORTER.export_bytes(sample_document()),
        )
        assert TextAuditor().audit_file(txt, expected=sample_document()).status is (
            ArtifactAuditStatus.PASS
        )
        assert MarkdownAuditor().audit_file(md, expected=sample_document()).status is (
            ArtifactAuditStatus.PASS
        )
        assert CLAIMS[0].encode() not in txt.read_bytes()
        assert CLAIMS[0].encode() not in md.read_bytes()
        assert b"## Claims" not in md.read_bytes()

    @pytest.mark.parametrize(
        ("mutator", "code"),
        [
            (lambda data: b"\xef\xbb\xbf" + data, AuditCode.UTF8_BOM),
            (lambda data: data.replace(b"\n", b"\r\n"), AuditCode.LINE_ENDINGS_CR),
            (lambda data: data[:-1], AuditCode.TRAILING_NEWLINE_MISSING),
            (lambda data: data + b"\n", AuditCode.TRAILING_NEWLINE_EXTRA),
        ],
    )
    def test_txt_byte_contract_tampers_fail(
        self,
        tmp_path: Path,
        mutator: Callable[[bytes], bytes],
        code: str,
    ) -> None:
        artifact = write(
            tmp_path / "tampered.txt",
            mutator(TXT_EXPORTER.export_bytes(sample_document())),
        )
        report = TextAuditor().audit_file(artifact, expected=sample_document())
        assert report.status is ArtifactAuditStatus.FAIL
        assert code in error_codes(report)

    def test_missing_ordered_content_and_identifier_fail(self, tmp_path: Path) -> None:
        data = TXT_EXPORTER.export_bytes(sample_document())[:-1]
        artifact = write(tmp_path / "identifier.txt", data + b" project_id=42\n")
        assert AuditCode.METADATA_PROHIBITED in error_codes(
            TextAuditor().audit_file(artifact, expected=sample_document())
        )

        reversed_doc = build_public_document(
            title=TITLE,
            sections=tuple(reversed(SECTIONS)),
            claims=(),
        )
        artifact = write(tmp_path / "order.txt", TXT_EXPORTER.export_bytes(reversed_doc))
        assert AuditCode.CONTENT_MISSING in error_codes(
            TextAuditor().audit_file(artifact, expected=sample_document())
        )

    def test_markdown_claims_and_active_content_fail(self, tmp_path: Path) -> None:
        base = MARKDOWN_EXPORTER.export_bytes(sample_document())[:-1]
        claims = write(tmp_path / "claims.md", base + b"\n\n## Claims\n\n- Private\n")
        assert AuditCode.CLAIMS_HEADING in error_codes(
            MarkdownAuditor().audit_file(claims, expected=sample_document())
        )

        script = write(tmp_path / "script.md", base + b"\n<script>alert(1)</script>\n")
        assert AuditCode.HTML_ACTIVE_CONTENT in error_codes(
            MarkdownAuditor().audit_file(script, expected=sample_document())
        )

        remote = write(
            tmp_path / "remote.md",
            base + b"\n[remote](https://example.invalid/resource)\n",
        )
        assert AuditCode.HTML_ACTIVE_CONTENT in error_codes(
            MarkdownAuditor().audit_file(remote, expected=sample_document())
        )

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(AuditorError):
            TextAuditor().audit_file(tmp_path / "missing.txt", expected=None)


@pytest.mark.importers
class TestUnicodeAuditor:
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
        artifact = write(
            tmp_path / "document.docx",
            DOCX_EXPORTER.export_bytes(sample_document()),
        )
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
            write(tmp_path / "corrupt.docx", corrupt),
            expected=sample_document(),
        )
        assert AuditCode.DOCX_ZIP_INVALID in error_codes(report)

        malformed = replace_zip_part(
            DOCX_EXPORTER.export_bytes(sample_document()),
            "word/document.xml",
            b"<w:document><w:body>",
        )
        report = DocxAuditor().audit_file(
            write(tmp_path / "malformed.docx", malformed),
            expected=sample_document(),
        )
        assert AuditCode.DOCX_DOCUMENT_XML_MALFORMED in error_codes(report)

        expected = build_public_document(
            title=TITLE,
            sections=(*SECTIONS, "Missing section."),
            claims=(),
        )
        report = DocxAuditor().audit_file(
            write(
                tmp_path / "missing.docx",
                DOCX_EXPORTER.export_bytes(sample_document()),
            ),
            expected=expected,
        )
        assert AuditCode.CONTENT_MISSING in error_codes(report)

    @pytest.mark.parametrize(
        ("part", "content", "code"),
        [
            (
                "docProps/core.xml",
                b"<core><creator>test</creator></core>",
                AuditCode.DOCX_METADATA_PROHIBITED,
            ),
            (
                "customXml/item1.xml",
                b"<meta/>",
                AuditCode.DOCX_METADATA_PROHIBITED,
            ),
            ("word/vbaProject.bin", b"VBA", AuditCode.DOCX_MACROS),
            (
                "custom/hidden.xml",
                b"<w:rPr><w:vanish/></w:rPr>",
                AuditCode.DOCX_HIDDEN_CONTENT,
            ),
            (
                "custom/revision.xml",
                b"<w:ins/>",
                AuditCode.DOCX_HIDDEN_CONTENT,
            ),
        ],
    )
    def test_prohibited_parts_and_markers_fail(
        self,
        tmp_path: Path,
        part: str,
        content: bytes,
        code: str,
    ) -> None:
        data = add_zip_part(DOCX_EXPORTER.export_bytes(sample_document()), part, content)
        report = DocxAuditor().audit_file(
            write(tmp_path / "tampered.docx", data),
            expected=sample_document(),
        )
        assert code in error_codes(report)

    def test_external_relationship_and_identifier_fail(self, tmp_path: Path) -> None:
        relationship = (
            b'<Relationships><Relationship Target="https://example.invalid" '
            b'TargetMode="External"/></Relationships>'
        )
        data = add_zip_part(
            DOCX_EXPORTER.export_bytes(sample_document()),
            "word/_rels/document.xml.rels",
            relationship,
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
        artifact = write(
            tmp_path / "document.pdf",
            PDF_EXPORTER.export_bytes(sample_document()),
        )
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
        artifact = write(tmp_path / "active.pdf", builder(["Some page text."]))
        report = PdfAuditor().audit_file(artifact, expected=None)
        assert code in error_codes(report)

    def test_missing_expected_title_or_section_fails(self, tmp_path: Path) -> None:
        other = build_public_document(title="Other Title", sections=SECTIONS, claims=())
        report = PdfAuditor().audit_file(
            write(tmp_path / "other.pdf", PDF_EXPORTER.export_bytes(other)),
            expected=sample_document(),
        )
        assert AuditCode.TITLE_MISSING in error_codes(report)

        expected = build_public_document(
            title=TITLE,
            sections=(*SECTIONS, "Missing section."),
            claims=(),
        )
        report = PdfAuditor().audit_file(
            write(
                tmp_path / "missing.pdf",
                PDF_EXPORTER.export_bytes(sample_document()),
            ),
            expected=expected,
        )
        assert AuditCode.CONTENT_MISSING in error_codes(report)


@pytest.mark.importers
class TestRegistryAndPackageAuditor:
    def test_registry_selects_expected_auditors(self) -> None:
        assert isinstance(auditor_for("a.txt"), TextAuditor)
        assert isinstance(auditor_for("a.md"), MarkdownAuditor)
        assert isinstance(auditor_for("a.docx"), DocxAuditor)
        assert isinstance(auditor_for("a.pdf"), PdfAuditor)
        assert isinstance(auditor_for("a.xyz"), PackageAuditor)

    def test_unknown_text_warns_and_unknown_binary_fails(self, tmp_path: Path) -> None:
        artifact = write(
            tmp_path / "document.xyz",
            TXT_EXPORTER.export_bytes(sample_document()),
        )
        report = audit_artifact(artifact, expected=sample_document())
        assert report.status is ArtifactAuditStatus.PASS
        assert {finding.code for finding in report.findings} == {AuditCode.FORMAT_UNKNOWN}

        report = audit_artifact(
            write(tmp_path / "binary.xyz", b"\xff"),
            expected=None,
        )
        assert report.status is ArtifactAuditStatus.FAIL
        assert AuditCode.UNICODE_INVALID_UTF8 in error_codes(report)
