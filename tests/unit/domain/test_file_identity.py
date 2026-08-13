"""Unit tests for deterministic file identity and magic detection."""

from __future__ import annotations

import pytest

from humanhand.domain.file_identity import (
    FileKind,
    derive_identity,
    detect_magic,
    extension_of,
    identity_findings,
)
from humanhand.domain.import_findings import FindingCategory, FindingCode, FindingSeverity


class TestExtensionOf:
    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("sample.txt", "txt"),
            ("docs/SAMPLE.TXT", "txt"),
            ("note.md", "md"),
            ("archive.tar.gz", "gz"),
            ("no-extension", ""),
            ("hidden.", ""),
        ],
    )
    def test_extension_extraction(self, path: str, expected: str) -> None:
        assert extension_of(path) == expected


class TestDetectMagic:
    @pytest.mark.parametrize(
        ("raw", "kind"),
        [
            (b"plain text", FileKind.TXT),
            (b"\xef\xbb\xbfbom text", FileKind.TXT),
            (b"%PDF-1.7\n....", FileKind.PDF),
            (b"PK\x03\x04\x14\x00....", FileKind.UNKNOWN),
            (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1....", FileKind.LEGACY_DOC),
            (b"{\\rtf1\\ansi ....", FileKind.RTF),
            (b"<!DOCTYPE html><html>", FileKind.HTML),
            (b"<html><body>x</body></html>", FileKind.HTML),
            (b"\x1f\x8b\x08\x00....", FileKind.UNKNOWN),
            (b"\x00\x01\x02\x03", FileKind.UNKNOWN),
            (b"text\x00with nul", FileKind.UNKNOWN),
        ],
    )
    def test_magic_kind(self, raw: bytes, kind: FileKind) -> None:
        signature = detect_magic(raw)
        assert signature.kind is kind

    def test_container_flags(self) -> None:
        assert detect_magic(b"PK\x03\x04abc").is_container is True
        assert detect_magic(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1abc").is_container is True
        assert detect_magic(b"plain text").is_container is False
        assert detect_magic(b"PK\x03\x04abc").matched is False


class TestDeriveIdentity:
    def test_txt_identity(self) -> None:
        identity = derive_identity("sample.txt", b"hello world")
        assert identity.extension == "txt"
        assert identity.size_bytes == 11
        assert identity.declared_kind is FileKind.TXT
        assert identity.magic_kind is FileKind.TXT
        assert identity.has_clear_mismatch() is False

    def test_markdown_identity(self) -> None:
        identity = derive_identity("notes.md", b"# Title")
        assert identity.declared_kind is FileKind.MARKDOWN
        assert identity.has_clear_mismatch() is False

    def test_unknown_extension(self) -> None:
        identity = derive_identity("data.xyz", b"plain text")
        assert identity.declared_kind is FileKind.UNKNOWN
        assert identity.is_declared_supported() is False
        assert identity.has_clear_mismatch() is False

    def test_mismatch_txt_named_docx(self) -> None:
        identity = derive_identity("fake.docx", b"this is really plain text")
        assert identity.declared_kind is FileKind.DOCX
        assert identity.magic_kind is FileKind.TXT
        assert identity.has_clear_mismatch() is True

    def test_zip_container_does_not_mismatch_docx(self) -> None:
        identity = derive_identity("real.docx", b"PK\x03\x04........")
        assert identity.declared_kind is FileKind.DOCX
        assert identity.magic_kind is FileKind.UNKNOWN
        assert identity.has_clear_mismatch() is False
        assert identity.magic.is_container is True


class TestRichFormatRouting:
    """EP-013 regression: rich-format magics must route to their own kinds."""

    @pytest.mark.parametrize(
        ("path", "raw", "expected"),
        [
            ("doc.pdf", b"%PDF-1.7\n....", FileKind.PDF),
            ("page.html", b"<!DOCTYPE html><html></html>", FileKind.HTML),
            ("doc.rtf", b"{\\rtf1\\ansi sample}", FileKind.RTF),
            ("doc.docx", b"PK\x03\x04........", FileKind.DOCX),
            ("doc.odt", b"PK\x03\x04........", FileKind.ODT),
            ("notes.txt", b"plain text", FileKind.TXT),
            ("notes.md", b"# Heading", FileKind.MARKDOWN),
        ],
    )
    def test_resolve_kind_routes_by_declared_kind(
        self, path: str, raw: bytes, expected: FileKind
    ) -> None:
        from humanhand.infra.importers.file_type import resolve_kind

        identity = derive_identity(path, raw)
        assert resolve_kind(identity) is expected


class TestIdentityFindings:
    def test_no_findings_for_clean_identity(self) -> None:
        assert identity_findings(derive_identity("sample.txt", b"hello")) == ()

    def test_mismatch_finding(self) -> None:
        findings = identity_findings(derive_identity("fake.docx", b"plain text"))
        assert [finding.code for finding in findings] == [FindingCode.MAGIC_MISMATCH]
        assert findings[0].severity is FindingSeverity.ERROR
        assert findings[0].category is FindingCategory.MAGIC_MISMATCH
        assert "docx" in findings[0].evidence

    def test_binary_finding(self) -> None:
        findings = identity_findings(derive_identity("blob.dat", b"\x00\x01\x02\x03"))
        assert [finding.code for finding in findings] == [FindingCode.ENCODING_BINARY]
        assert findings[0].severity is FindingSeverity.ERROR

    def test_binary_content_with_declared_kind_reports_binary(self) -> None:
        # Magic is UNKNOWN for binary data, so no clear two-way mismatch is
        # possible; the binary-encoding finding still fails the import closed.
        findings = identity_findings(derive_identity("blob.pdf", b"\x00\x01\x02\x03"))
        assert [finding.code for finding in findings] == [FindingCode.ENCODING_BINARY]

    def test_container_signature_is_not_binary(self) -> None:
        # A recognized container signature (ZIP) is not binary data; the
        # format adapter validates the container parts itself.
        findings = identity_findings(derive_identity("doc.docx", b"PK\x03\x04........"))
        assert findings == ()
        assert derive_identity("doc.docx", b"PK\x03\x04........").magic.is_container is True
