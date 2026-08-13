"""Deterministic auditor registry (EP-016).

``auditor_for`` maps a file extension to exactly one auditor class, so
the same path always yields the same audit behavior:

- ``.txt`` -> text auditor,
- ``.md`` / ``.markdown`` -> markdown auditor,
- ``.docx`` -> docx auditor,
- ``.pdf`` -> pdf auditor,
- anything else (or no extension) -> package auditor, which combines
  the unicode audit with a WARNING that the format is unknown. The
  unknown-format WARNING alone passes; any ERROR finding fails.
"""

from __future__ import annotations

from pathlib import Path

from humanhand.domain.artifact_findings import ArtifactAuditReport
from humanhand.domain.public_document import PublicDocument

from .base import BaseAuditor
from .docx_auditor import DocxAuditor
from .markdown_auditor import MarkdownAuditor
from .package_auditor import PackageAuditor
from .pdf_auditor import PdfAuditor
from .text_auditor import TextAuditor

_EXTENSION_ROUTES: tuple[tuple[str, type[BaseAuditor]], ...] = (
    (".txt", TextAuditor),
    (".md", MarkdownAuditor),
    (".markdown", MarkdownAuditor),
    (".docx", DocxAuditor),
    (".pdf", PdfAuditor),
)


def auditor_for(path: str | Path) -> BaseAuditor:
    """Return the deterministic auditor for the file at ``path``."""
    suffix = Path(path).suffix.lower()
    for extension, auditor_type in _EXTENSION_ROUTES:
        if suffix == extension:
            return auditor_type()
    return PackageAuditor()


def audit_artifact(
    path: str | Path, *, expected: PublicDocument | None = None
) -> ArtifactAuditReport:
    """Audit the artifact at ``path`` through its format auditor."""
    return auditor_for(path).audit_file(path, expected=expected)
