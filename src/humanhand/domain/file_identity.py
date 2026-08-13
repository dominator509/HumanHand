"""Deterministic file identity — extension, magic bytes, and kind detection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from humanhand.domain.import_findings import (
    FindingCategory,
    FindingCode,
    FindingSeverity,
    ImportFinding,
)

_EXTENSION_RE = re.compile(r"\.([A-Za-z0-9]+)$")


class FileKind(StrEnum):
    """Detected or declared document container kind."""

    TXT = "txt"
    MARKDOWN = "markdown"
    DOCX = "docx"
    PDF = "pdf"
    HTML = "html"
    RTF = "rtf"
    ODT = "odt"
    LEGACY_DOC = "legacy_doc"
    UNKNOWN = "unknown"


_EXTENSION_TO_KIND: dict[str, FileKind] = {
    "txt": FileKind.TXT,
    "text": FileKind.TXT,
    "md": FileKind.MARKDOWN,
    "markdown": FileKind.MARKDOWN,
    "docx": FileKind.DOCX,
    "pdf": FileKind.PDF,
    "html": FileKind.HTML,
    "htm": FileKind.HTML,
    "rtf": FileKind.RTF,
    "odt": FileKind.ODT,
    "doc": FileKind.LEGACY_DOC,
}


@dataclass(frozen=True)
class MagicSignature:
    """Result of deterministic magic-byte inspection."""

    kind: FileKind
    matched: bool
    description: str
    is_container: bool = False


def _magic_kind(raw: bytes) -> tuple[FileKind | None, str, bool]:
    if (
        raw.startswith(b"\xef\xbb\xbf")
        or raw.startswith(b"\xff\xfe")
        or raw.startswith(b"\xfe\xff")
    ):
        return FileKind.TXT, "unicode BOM", False
    if raw.startswith(b"%PDF-"):
        return FileKind.PDF, "PDF header", False
    if raw.startswith(b"PK\x03\x04"):
        return None, "zip container", True
    if raw.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return FileKind.LEGACY_DOC, "OLE2 compound file", True
    if raw.startswith(b"\x1f\x8b"):
        return None, "gzip container", True
    if raw.startswith(b"{\\rtf"):
        return FileKind.RTF, "RTF header", False
    head = raw[:256].lstrip().lower()
    if head.startswith((b"<!doctype html", b"<html", b"<head", b"<body")):
        return FileKind.HTML, "HTML-like header", False
    # Anything that decodes as strict UTF-8 without embedded NULs is plain text.
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return FileKind.UNKNOWN, "binary data (not UTF-8)", False
    if "\x00" in text:
        return FileKind.UNKNOWN, "binary data (embedded NUL)", False
    return FileKind.TXT, "plain UTF-8 text", False


def detect_magic(raw: bytes) -> MagicSignature:
    """Inspect leading bytes deterministically and return a magic signature."""
    kind, description, is_container = _magic_kind(raw)
    if kind is None:
        return MagicSignature(
            kind=FileKind.UNKNOWN, matched=False, description=description, is_container=is_container
        )
    return MagicSignature(
        kind=kind, matched=True, description=description, is_container=is_container
    )


def extension_of(path: str) -> str:
    """Return the lowercased file extension without the dot, or ''."""
    match = _EXTENSION_RE.search(path)
    return match.group(1).lower() if match else ""


@dataclass(frozen=True)
class FileIdentity:
    """Deterministic identity of an imported file."""

    given_path: str
    extension: str
    size_bytes: int
    declared_kind: FileKind
    magic: MagicSignature

    @property
    def magic_kind(self) -> FileKind:
        return self.magic.kind

    def is_declared_supported(self) -> bool:
        return self.declared_kind is not FileKind.UNKNOWN

    def has_clear_mismatch(self) -> bool:
        """True when extension and magic both identify kinds and disagree.

        Plain UTF-8 text is a compatible representation of both TXT and
        Markdown, so a text-magic file with a TXT/Markdown extension is not
        treated as a mismatch.
        """
        if self.declared_kind is FileKind.UNKNOWN or self.magic_kind is FileKind.UNKNOWN:
            return False
        if self.declared_kind is self.magic_kind:
            return False
        text_compatible = {FileKind.TXT, FileKind.MARKDOWN}
        return not (self.declared_kind in text_compatible and self.magic_kind in text_compatible)


def derive_identity(path: str, raw: bytes, *, size_bytes: int | None = None) -> FileIdentity:
    """Build a FileIdentity from a path string and raw bytes.

    ``size_bytes`` overrides the byte length when ``raw`` is only a leading
    sample of a larger file (e.g., an over-limit file's head bytes).
    """
    extension = extension_of(path)
    return FileIdentity(
        given_path=path,
        extension=extension,
        size_bytes=size_bytes if size_bytes is not None else len(raw),
        declared_kind=_EXTENSION_TO_KIND.get(extension, FileKind.UNKNOWN),
        magic=detect_magic(raw),
    )


def identity_findings(identity: FileIdentity) -> tuple[ImportFinding, ...]:
    """Return findings for a file identity, failing closed on mismatches."""
    findings: list[ImportFinding] = []
    if identity.has_clear_mismatch():
        findings.append(
            ImportFinding(
                code=FindingCode.MAGIC_MISMATCH,
                severity=FindingSeverity.ERROR,
                category=FindingCategory.MAGIC_MISMATCH,
                description=(
                    f"Extension '{identity.extension}' disagrees with detected content "
                    f"'{identity.magic_kind.value}'"
                ),
                evidence=f"extension={identity.extension} magic={identity.magic.description}",
            )
        )
    elif identity.magic_kind is FileKind.UNKNOWN and not identity.magic.is_container:
        # Recognized container signatures (ZIP/OLE2/gzip) are not binary
        # data; the format adapter validates the container parts itself.
        findings.append(
            ImportFinding(
                code=FindingCode.ENCODING_BINARY,
                severity=FindingSeverity.ERROR,
                category=FindingCategory.ENCODING,
                description="Content is not recognizable text or a supported container",
                evidence=f"magic={identity.magic.description}",
            )
        )
    return tuple(findings)
