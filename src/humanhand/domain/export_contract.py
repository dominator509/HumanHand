"""Export contract — approved content and explicit formats only (SPEC-013, blueprint 11).

Exporters accept exactly an :class:`ExportRequest` (format, public
document, output path) and return an :class:`ExportResult` (output path,
format, sha256 of the exported bytes, byte count). The request carries no
internal workflow data, so an exporter can never see project ids, model
fields, prompts, or receipts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from humanhand.domain.public_document import PublicDocument


class ExportFormat(StrEnum):
    """Supported public export formats."""

    TXT = "txt"
    MARKDOWN = "md"
    DOCX = "docx"
    PDF = "pdf"


@dataclass(frozen=True)
class ExportRequest:
    """One export of one approved public document."""

    format: ExportFormat
    document: PublicDocument
    output_path: str


@dataclass(frozen=True)
class ExportResult:
    """Result of one completed export."""

    output_path: str
    format: ExportFormat
    sha256: str  # of the exported file bytes
    byte_count: int


_FORMAT_SUFFIXES: dict[ExportFormat, tuple[str, ...]] = {
    ExportFormat.TXT: (".txt",),
    ExportFormat.MARKDOWN: (".md", ".markdown"),
    ExportFormat.DOCX: (".docx",),
    ExportFormat.PDF: (".pdf",),
}


def _document_is_empty(document: PublicDocument) -> bool:
    return not document.title and not document.sections and not document.claims


def validate_export_request(request: ExportRequest) -> tuple[str, ...]:
    """Return violation codes for an export request; empty tuple means valid.

    Codes:
    - ``empty_document``: the document has no title, sections, or claims.
    - ``unsafe_output_path``: the output path ends with ``.humanhand``
      (case-insensitive) or equals one of the documented internal paths.
    """
    violations: list[str] = []
    if _document_is_empty(request.document):
        violations.append("empty_document")
    output_path = request.output_path
    normalized = output_path.replace("\\", "/").lower().strip("/")
    parts = tuple(part for part in normalized.split("/") if part)
    contains_private_path = ".humanhand" in parts or any(
        parts[index : index + 2] == (".cache", "humanhand")
        for index in range(max(0, len(parts) - 1))
    )
    if normalized.endswith(".humanhand") or contains_private_path:
        violations.append("unsafe_output_path")
    lowered = output_path.lower()
    if not any(lowered.endswith(suffix) for suffix in _FORMAT_SUFFIXES[request.format]):
        violations.append("format_extension_mismatch")
    return tuple(violations)
