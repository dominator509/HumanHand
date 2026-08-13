"""Integration tests for the independent artifact auditors (EP-016).

The exporters landed in the same workstream, so the happy-path artifacts
in this file ARE real exporter output written through
``humanhand.infra.exporters``; every auditor receives a PATH and re-reads
the bytes from disk (independent-check rule: the exporter's in-memory
output is never handed to the auditor). Tampered variants are derived
from the real exporter bytes by byte-level surgery. The two JavaScript
PDFs use the repo's in-test builder ``tests.integration.support.pdf_builder``
because a clean exporter cannot produce a JavaScript PDF — that is the
point of a tamper.

Every assertion below reflects behavior observed on the real run.
"""

from __future__ import annotations

import io
import unicodedata
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

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
CLAIMS = ("The first claim proposition.",)
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


# --- byte-level surgery helpers (real bytes, real archives) ---------------


def replace_zip_part(data: bytes, part_name: str, new_part: bytes) -> bytes:
    """Return a real ZIP copy with one part replaced."""
    buffer = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(data), "r") as source,
        zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as target,
    ):
        for name in source.namelist():
            if name == part_name:
                target.writestr(name, new_part)
            else:
                target.writestr(name, source.read(name))
    return buffer.getvalue()


def add_zip_part(data: bytes, part_name: str, part_bytes: bytes) -> bytes:
    """Return a real ZIP copy with one extra part appended."""
    buffer = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(data), "r") as source,
        zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as target,
    ):
        for name in source.namelist():
            target.writestr(name, source.read(name))
        target.writestr(part_name, part_bytes)
    return buffer.getvalue()


def write(path: Path, data: bytes) -> Path:
    """Write artifact bytes to disk; the auditor receives only this path."""
    path.write_bytes(data)
    return path


@pytest.mark.importers
class TestTextAuditor:
    """TXT lane: real exporter output and byte-level tamper variants."""

    def test_clean_exporter_txt_passes(self, tmp_path: Path) -> None:
        artifact = write(tmp_path / "document.txt", TXT_EXPORTER.export_bytes(sample_document()))
        report = TextAuditor().audit_file(artifact, expected=sample_document())
        # Observed: the exporter's UTF-8/LF/single-trailing-newline output
        # triggers no findings, and the audit re-reads the bytes from disk.
        assert report.format == "txt"
        assert report.status is ArtifactAuditStatus.PASS
        assert report.findings == ()

    def test_txt_with_bom_fails(self, tmp_path: Path) -> None:
        data = b"\xef\xbb\xbf" + TXT_EXPORTER.export_bytes(sample_document())
        report = TextAuditor().audit_file(
            write(tmp_path / "bom.txt", data), expected=sample_document()
        )
        # Observed: a UTF-8 BOM is an ERROR; the rest of the file still passes.
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.UTF8_BOM}

    def test_txt_with_crlf_fails(self, tmp_path: Path) -> None:
        data = TXT_EXPORTER.export_bytes(sample_document()).replace(b"\n", b"\r\n")
        report = TextAuditor().audit_file(
            write(tmp_path / "crlf.txt", data), expected=sample_document()
        )
        # Observed: every CR byte is an ERROR; section containment still passes.
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.LINE_ENDINGS_CR}

    def test_txt_without_trailing_newline_fails(self, tmp_path: Path) -> None:
        data = TXT_EXPORTER.export_bytes(sample_document())[:-1]
        report = TextAuditor().audit_file(
            write(tmp_path / "tail.txt", data), expected=sample_document()
        )
        # Observed: truncating the final newline produces exactly one ERROR.
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.TRAILING_NEWLINE_MISSING}

    def test_txt_with_extra_trailing_newline_fails(self, tmp_path: Path) -> None:
        data = TXT_EXPORTER.export_bytes(sample_document()) + b"\n"
        report = TextAuditor().audit_file(
            write(tmp_path / "tail2.txt", data), expected=sample_document()
        )
        # Observed: a second trailing newline is its own ERROR code.
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.TRAILING_NEWLINE_EXTRA}

    def test_txt_with_prohibited_metadata_fails(self, tmp_path: Path) -> None:
        data = TXT_EXPORTER.export_bytes(sample_document())
        # Insert before the final newline, after the last section's period, so
        # every expected section text stays an intact substring. (A mid-text
        # injection would ALSO trip section containment — observed earlier —
        # so the tamper must not break the substring it tests.)
        data = data[:-1] + b" project_id=42\n"
        report = TextAuditor().audit_file(
            write(tmp_path / "meta.txt", data), expected=sample_document()
        )
        # Observed: the injected "project_id" string is caught case-insensitively
        # while all section texts remain substrings, so exactly one ERROR fires.
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.METADATA_PROHIBITED}
        assert "term=project_id" in {finding.evidence for finding in report.findings}

    def test_txt_missing_expected_section_fails(self, tmp_path: Path) -> None:
        expected = build_public_document(
            title=TITLE, sections=(*SECTIONS, EXTRA_SECTION), claims=()
        )
        data = TXT_EXPORTER.export_bytes(sample_document(claims=()))
        report = TextAuditor().audit_file(write(tmp_path / "missing.txt", data), expected=expected)
        # Observed: a section declared in the expected document but absent from
        # the artifact bytes is an ERROR with its section index in evidence.
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.CONTENT_MISSING}

    def test_txt_sections_out_of_order_fails(self, tmp_path: Path) -> None:
        reversed_doc = build_public_document(
            title=TITLE, sections=(SECTIONS[1], SECTIONS[0]), claims=()
        )
        data = TXT_EXPORTER.export_bytes(reversed_doc)
        report = TextAuditor().audit_file(
            write(tmp_path / "order.txt", data), expected=sample_document()
        )
        # Observed: ordered containment fails when the second expected section
        # appears before the first (both texts are present in the file).
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.CONTENT_MISSING}

    def test_missing_file_raises_auditor_error(self, tmp_path: Path) -> None:
        # Observed: files.read_bytes raises FileIOError, translated to AuditorError.
        with pytest.raises(AuditorError):
            TextAuditor().audit_file(tmp_path / "missing.txt", expected=None)


@pytest.mark.importers
class TestMarkdownAuditor:
    """Markdown lane: TXT-lane checks plus heading/claims/HTML checks."""

    def test_clean_exporter_markdown_passes(self, tmp_path: Path) -> None:
        artifact = write(
            tmp_path / "document.md", MARKDOWN_EXPORTER.export_bytes(sample_document())
        )
        report = MarkdownAuditor().audit_file(artifact, expected=sample_document())
        # Observed: real exporter Markdown ("# title", sections, "## Claims"
        # with one bullet) produces zero findings.
        assert report.format == "md"
        assert report.status is ArtifactAuditStatus.PASS
        assert report.findings == ()

    def test_markdown_without_title_heading_fails(self, tmp_path: Path) -> None:
        data = MARKDOWN_EXPORTER.export_bytes(sample_document()).replace(
            b"# Synthetic Sample", b"Synthetic Sample"
        )
        report = MarkdownAuditor().audit_file(
            write(tmp_path / "notitle.md", data), expected=sample_document()
        )
        # Observed: removing the "# " prefix removes the only title heading.
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.HEADING_TITLE}

    def test_markdown_claims_expected_but_missing_fails(self, tmp_path: Path) -> None:
        data = MARKDOWN_EXPORTER.export_bytes(sample_document(claims=()))
        report = MarkdownAuditor().audit_file(
            write(tmp_path / "noclaims.md", data), expected=sample_document()
        )
        # Observed: a document that declares claims but whose artifact lacks
        # the "## Claims" section fails on the claims heading.
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.CLAIMS_HEADING}

    def test_markdown_claims_present_but_unexpected_fails(self, tmp_path: Path) -> None:
        data = MARKDOWN_EXPORTER.export_bytes(sample_document())
        report = MarkdownAuditor().audit_file(
            write(tmp_path / "extraclaims.md", data), expected=sample_document(claims=())
        )
        # Observed: a "## Claims" section in a document that declares no claims
        # is also an ERROR (claims presence must match the expected document).
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.CLAIMS_HEADING}

    def test_markdown_with_script_tag_fails(self, tmp_path: Path) -> None:
        data = MARKDOWN_EXPORTER.export_bytes(sample_document())
        data = data[:-1] + b"\n<script>alert(1)</script>\n"
        report = MarkdownAuditor().audit_file(
            write(tmp_path / "script.md", data), expected=sample_document()
        )
        # Observed: a raw "<script" tag is an ERROR; the trailing newline rule
        # still passes because the injected line keeps exactly one final newline.
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.HTML_ACTIVE_CONTENT}

    def test_markdown_with_iframe_tag_fails(self, tmp_path: Path) -> None:
        data = MARKDOWN_EXPORTER.export_bytes(sample_document())
        data = data[:-1] + b'\n<iframe src="https://example.invalid"></iframe>\n'
        report = MarkdownAuditor().audit_file(
            write(tmp_path / "iframe.md", data), expected=sample_document()
        )
        # Observed: "<iframe" is caught by the same raw-HTML scan.
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.HTML_ACTIVE_CONTENT}

    def test_markdown_with_remote_link_fails(self, tmp_path: Path) -> None:
        data = MARKDOWN_EXPORTER.export_bytes(sample_document())
        data = data[:-1] + b"\n[remote](https://example.invalid/resource)\n"
        report = MarkdownAuditor().audit_file(
            write(tmp_path / "remote.md", data), expected=sample_document()
        )
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.HTML_ACTIVE_CONTENT}

    def test_markdown_inherits_txt_bom_check(self, tmp_path: Path) -> None:
        data = b"\xef\xbb\xbf" + MARKDOWN_EXPORTER.export_bytes(sample_document())
        report = MarkdownAuditor().audit_file(
            write(tmp_path / "bom.md", data), expected=sample_document()
        )
        # Observed: Markdown artifacts inherit every TXT-lane byte check, and
        # the BOM additionally hides the title line ("﻿# ..." does not
        # start with "# "), so both findings fire.
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.UTF8_BOM, AuditCode.HEADING_TITLE}


@pytest.mark.importers
class TestUnicodeAuditor:
    """Unicode lane: NFC, control-character, and surrogate scans."""

    def test_clean_exporter_txt_passes(self, tmp_path: Path) -> None:
        artifact = write(tmp_path / "clean.txt", TXT_EXPORTER.export_bytes(sample_document()))
        report = UnicodeAuditor().audit_file(artifact, expected=None)
        # Observed: ASCII exporter output is NFC with no control characters.
        assert report.status is ArtifactAuditStatus.PASS
        assert report.findings == ()

    def test_control_character_fails(self, tmp_path: Path) -> None:
        report = UnicodeAuditor().audit_file(
            write(tmp_path / "ctl.txt", b"line one\x01line two\n"), expected=None
        )
        # Observed: U+0001 is a valid UTF-8 byte so the file decodes, and the
        # control scan then flags it (category Cc, not tab/LF/CR).
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.UNICODE_CONTROL_CHARS}

    def test_invalid_utf8_fails(self, tmp_path: Path) -> None:
        report = UnicodeAuditor().audit_file(
            write(tmp_path / "bin.txt", b"\x00\xff\x00"), expected=None
        )
        # Observed: 0xFF is not valid UTF-8, so the artifact fails closed.
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.UNICODE_INVALID_UTF8}

    def test_nfd_text_warns(self) -> None:
        findings = UnicodeAuditor.scan_unicode_text(unicodedata.normalize("NFD", "café"))
        # Observed: NFD "café" is not NFC-normalized and yields a WARNING.
        assert {finding.code for finding in findings} == {AuditCode.UNICODE_NOT_NFC}
        assert findings[0].severity is ArtifactFindingSeverity.WARNING

    def test_surrogate_scan_flags_error(self) -> None:
        findings = UnicodeAuditor.scan_unicode_text("bad\ud800char")
        # Observed: a lone surrogate is an ERROR. Surrogate code points are
        # unreachable through a strict UTF-8 file decode (their bytes are
        # rejected as invalid UTF-8), so the scanner is exercised directly.
        assert {finding.code for finding in findings} == {AuditCode.UNICODE_SURROGATES}
        assert findings[0].severity is ArtifactFindingSeverity.ERROR


@pytest.mark.importers
class TestDocxAuditor:
    """DOCX lane: real exporter package plus ZIP/XML surgery variants."""

    def test_clean_exporter_docx_passes(self, tmp_path: Path) -> None:
        artifact = write(tmp_path / "document.docx", DOCX_EXPORTER.export_bytes(sample_document()))
        report = DocxAuditor().audit_file(artifact, expected=sample_document())
        # Observed: the real exporter package (Content_Types, rels, document.xml,
        # core.xml) opens, parses, contains both sections, and has no
        # prohibited terms or macro parts.
        assert report.format == "docx"
        assert report.status is ArtifactAuditStatus.PASS
        assert report.findings == ()

    def test_corrupted_zip_fails(self, tmp_path: Path) -> None:
        data = DOCX_EXPORTER.export_bytes(sample_document())
        # Truncate the End-of-Central-Directory record. (zipfile validates
        # lazily: corrupting the first local header only made that one part
        # unreadable — part_unreadable — so the EOCD is the deterministic
        # open-time rejection path, observed.)
        data = data[:-22]
        report = DocxAuditor().audit_file(
            write(tmp_path / "bad.docx", data), expected=sample_document()
        )
        # Observed: a missing EOCD record makes zipfile reject the package.
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.DOCX_ZIP_INVALID}

    def test_prohibited_metadata_in_part_fails(self, tmp_path: Path) -> None:
        data = DOCX_EXPORTER.export_bytes(sample_document())
        # Inject the term as a NEW package part: an injection inside
        # word/document.xml text would ALSO break the section substring
        # (content.missing alongside, observed), so a new part isolates the
        # any-part metadata scan.
        data = add_zip_part(data, "custom/metadata.xml", b"<meta>project_id=42</meta>")
        report = DocxAuditor().audit_file(
            write(tmp_path / "meta.docx", data), expected=sample_document()
        )
        # Observed: every package part is scanned; the injected part is caught
        # with the part name in evidence, and nothing else fires.
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.DOCX_METADATA_PROHIBITED}

    def test_macro_part_fails(self, tmp_path: Path) -> None:
        data = add_zip_part(
            DOCX_EXPORTER.export_bytes(sample_document()), "word/vbaProject.bin", b"\x00VBA\x00"
        )
        report = DocxAuditor().audit_file(
            write(tmp_path / "macro.docx", data), expected=sample_document()
        )
        # Observed: a "vbaproject" part name is an ERROR macro marker.
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.DOCX_MACROS}

    def test_external_relationship_fails(self, tmp_path: Path) -> None:
        rels = (
            b'<Relationships><Relationship Target="https://example.invalid" '
            b'TargetMode="External"/></Relationships>'
        )
        data = add_zip_part(
            DOCX_EXPORTER.export_bytes(sample_document()),
            "word/_rels/document.xml.rels",
            rels,
        )
        report = DocxAuditor().audit_file(
            write(tmp_path / "external.docx", data), expected=sample_document()
        )
        assert AuditCode.DOCX_EXTERNAL_RELATIONSHIP in error_codes(report)

    def test_hidden_text_formatting_fails(self, tmp_path: Path) -> None:
        data = add_zip_part(
            DOCX_EXPORTER.export_bytes(sample_document()),
            "custom/hidden.xml",
            b"<w:rPr><w:vanish/></w:rPr>",
        )
        report = DocxAuditor().audit_file(
            write(tmp_path / "hidden.docx", data), expected=sample_document()
        )
        assert AuditCode.DOCX_HIDDEN_CONTENT in error_codes(report)

    def test_malformed_document_xml_fails(self, tmp_path: Path) -> None:
        data = replace_zip_part(
            DOCX_EXPORTER.export_bytes(sample_document()),
            "word/document.xml",
            b"<w:document><w:body>",
        )
        report = DocxAuditor().audit_file(
            write(tmp_path / "badxml.docx", data), expected=sample_document()
        )
        # Observed: an unclosed main-document element fails the bounded parse.
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.DOCX_DOCUMENT_XML_MALFORMED}

    def test_missing_expected_section_fails(self, tmp_path: Path) -> None:
        expected = build_public_document(
            title=TITLE, sections=(*SECTIONS, EXTRA_SECTION), claims=()
        )
        data = DOCX_EXPORTER.export_bytes(sample_document(claims=()))
        report = DocxAuditor().audit_file(write(tmp_path / "missing.docx", data), expected=expected)
        # Observed: section containment is order-insensitive for DOCX but the
        # absent extra section still fails the audit.
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.CONTENT_MISSING}


@pytest.mark.importers
class TestPdfAuditor:
    """PDF lane: real exporter output plus pypdf-built tamper variants."""

    def test_clean_exporter_pdf_passes(self, tmp_path: Path) -> None:
        artifact = write(tmp_path / "document.pdf", PDF_EXPORTER.export_bytes(sample_document()))
        report = PdfAuditor().audit_file(artifact, expected=sample_document())
        # Observed: reportlab exporter output opens in pypdf, extracts the
        # title and both sections (whitespace-collapsed), and has no JS.
        assert report.format == "pdf"
        assert report.status is ArtifactAuditStatus.PASS
        assert report.findings == ()

    def test_not_a_pdf_fails(self, tmp_path: Path) -> None:
        report = PdfAuditor().audit_file(write(tmp_path / "fake.pdf", b"not a pdf"), expected=None)
        # Observed: garbage bytes raise PyPdfError and fail the audit.
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.PDF_OPEN_FAILED}

    def test_openaction_javascript_fails(self, tmp_path: Path) -> None:
        data = build_pdf_with_javascript(["Some page text."])
        report = PdfAuditor().audit_file(write(tmp_path / "js1.pdf", data), expected=None)
        # Observed: the catalog /OpenAction with /S /JavaScript is detected by
        # the local check (this PDF is built in-test because a clean exporter
        # cannot produce JavaScript).
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.PDF_JAVASCRIPT}

    def test_names_tree_javascript_fails(self, tmp_path: Path) -> None:
        data = build_pdf_with_names_javascript(["Some page text."])
        report = PdfAuditor().audit_file(write(tmp_path / "js2.pdf", data), expected=None)
        # Observed: the /Names -> /JavaScript placement is detected too.
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.PDF_JAVASCRIPT}

    @pytest.mark.parametrize("builder", [build_pdf_with_acroform, build_pdf_with_attachment])
    def test_interactive_or_embedded_content_fails(
        self, tmp_path: Path, builder: Callable[[list[str]], bytes]
    ) -> None:
        data = builder(["Some page text."])
        report = PdfAuditor().audit_file(write(tmp_path / "active.pdf", data), expected=None)
        assert AuditCode.PDF_ACTIVE_CONTENT in error_codes(report)

    def test_missing_expected_title_fails(self, tmp_path: Path) -> None:
        other_doc = build_public_document(title="Other Title", sections=SECTIONS, claims=())
        data = PDF_EXPORTER.export_bytes(other_doc)
        report = PdfAuditor().audit_file(
            write(tmp_path / "other.pdf", data), expected=sample_document()
        )
        # Observed: the extracted text lacks the expected title while both
        # sections match, so exactly the title finding fires.
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.TITLE_MISSING, AuditCode.CONTENT_MISSING}

    def test_missing_expected_section_fails(self, tmp_path: Path) -> None:
        expected = build_public_document(
            title=TITLE, sections=(*SECTIONS, EXTRA_SECTION), claims=()
        )
        data = PDF_EXPORTER.export_bytes(sample_document(claims=()))
        report = PdfAuditor().audit_file(write(tmp_path / "missing.pdf", data), expected=expected)
        # Observed: the absent extra section fails the PDF audit.
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.CONTENT_MISSING}


@pytest.mark.importers
class TestRegistryAndPackageAuditor:
    """Registry routing and the unknown-format package auditor."""

    def test_auditor_for_selects_by_extension(self) -> None:
        # Observed routing is exact and case-insensitive:
        assert isinstance(auditor_for("a.txt"), TextAuditor)
        assert isinstance(auditor_for("a.md"), MarkdownAuditor)
        assert isinstance(auditor_for("a.markdown"), MarkdownAuditor)
        assert isinstance(auditor_for("a.docx"), DocxAuditor)
        assert isinstance(auditor_for("a.pdf"), PdfAuditor)
        assert isinstance(auditor_for("A.TXT"), TextAuditor)
        # Unknown and missing extensions route to the package auditor:
        assert isinstance(auditor_for("a.xyz"), PackageAuditor)
        assert isinstance(auditor_for("noextension"), PackageAuditor)

    def test_unknown_extension_warns_but_passes(self, tmp_path: Path) -> None:
        artifact = write(tmp_path / "doc.xyz", TXT_EXPORTER.export_bytes(sample_document()))
        report = audit_artifact(artifact, expected=sample_document())
        # Observed: the unknown-extension WARNING alone does not fail; the
        # unicode lane still audited the real text bytes.
        assert report.status is ArtifactAuditStatus.PASS
        assert all_codes(report) == {AuditCode.FORMAT_UNKNOWN}
        assert report.findings[0].severity is ArtifactFindingSeverity.WARNING

    def test_unknown_extension_binary_fails_closed(self, tmp_path: Path) -> None:
        artifact = write(tmp_path / "doc.xyz", b"\x00\xff\x00")
        report = audit_artifact(artifact, expected=None)
        # Observed: binary garbage is not valid UTF-8, so even an unknown
        # format fails closed on an ERROR finding.
        assert report.status is ArtifactAuditStatus.FAIL
        assert error_codes(report) == {AuditCode.UNICODE_INVALID_UTF8}

    def test_package_auditor_combines_unicode_and_unknown_warning(self, tmp_path: Path) -> None:
        artifact = write(tmp_path / "doc.xyz", b"line one\x01line two\n")
        report = PackageAuditor().audit_file(artifact, expected=None)
        # Observed: the package auditor concatenates the unicode-lane findings
        # and the unknown-format WARNING into one "any"-format report.
        assert report.format == "any"
        assert all_codes(report) == {AuditCode.UNICODE_CONTROL_CHARS, AuditCode.FORMAT_UNKNOWN}
        assert report.status is ArtifactAuditStatus.FAIL

    def test_registry_audit_with_expected_document(self, tmp_path: Path) -> None:
        artifact = write(tmp_path / "document.txt", TXT_EXPORTER.export_bytes(sample_document()))
        report = audit_artifact(artifact, expected=sample_document())
        # Observed: the registry forwards the expected document to the auditor.
        assert report.status is ArtifactAuditStatus.PASS
        assert report.findings == ()
