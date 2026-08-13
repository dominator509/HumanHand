"""Deterministic adapter resolution for imported files."""

from __future__ import annotations

from humanhand.domain.file_identity import FileIdentity, FileKind
from humanhand.domain.import_findings import (
    FindingCategory,
    FindingCode,
    FindingSeverity,
    ImportFinding,
)

# Kinds this program's adapters can parse (EP-012 + EP-013).
SUPPORTED_KINDS = frozenset(
    {
        FileKind.TXT,
        FileKind.MARKDOWN,
        FileKind.DOCX,
        FileKind.PDF,
        FileKind.HTML,
        FileKind.RTF,
        FileKind.ODT,
    }
)

# Kinds handled by a dedicated port rather than a direct adapter.
UNSUPPORTED_KINDS = frozenset(
    {
        FileKind.LEGACY_DOC,
    }
)


def resolve_kind(identity: FileIdentity) -> FileKind:
    """Resolve the adapter kind for a file identity.

    Markdown and TXT are text-compatible, so a Markdown declaration with a
    text magic resolves to Markdown; an unknown declaration with a text
    magic resolves to TXT. A declared supported kind (DOCX/PDF/HTML/RTF/ODT)
    resolves to itself so its adapter can validate the container. Anything
    else resolves to the declared kind or UNKNOWN.
    """
    if identity.magic_kind in {FileKind.TXT, FileKind.MARKDOWN}:
        if identity.declared_kind is FileKind.MARKDOWN:
            return FileKind.MARKDOWN
        return FileKind.TXT
    if identity.declared_kind in SUPPORTED_KINDS:
        return identity.declared_kind
    if identity.declared_kind in UNSUPPORTED_KINDS:
        return identity.declared_kind
    return FileKind.UNKNOWN


def unsupported_format_finding(identity: FileIdentity) -> ImportFinding | None:
    """Return a fail-closed finding for unsupported formats, or None."""
    kind = resolve_kind(identity)
    if kind in SUPPORTED_KINDS or kind is FileKind.UNKNOWN:
        return None
    return ImportFinding(
        code=FindingCode.UNSUPPORTED_FORMAT,
        severity=FindingSeverity.ERROR,
        category=FindingCategory.UNSUPPORTED_FEATURE,
        description=(
            f"Format '{kind.value}' is not supported by EP-012 importers (TXT and Markdown only)"
        ),
        evidence=f"kind={kind.value}",
    )
