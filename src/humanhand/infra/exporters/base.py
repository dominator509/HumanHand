"""Base exporter contract, atomic byte writes, and the format registry.

Public artifacts are written as RAW bytes with no scrub pass: the exporters
in this package own their byte streams end to end (UTF-8 no BOM, LF, exactly
one trailing newline for TXT/Markdown; minimal OOXML and reportlab PDF
packages), so ``humanhand.infra.files.write_clean_text`` and its scrub step
are intentionally NOT used here. Blueprint section 11 requires post-write
byte equality with approved content.

The write is atomic (temp file + ``os.replace`` in the same directory) and
fail closed: any output path that resolves inside a ``.humanhand`` directory
is refused because that tree holds private project state.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from humanhand.domain.export_contract import (
    ExportFormat,
    ExportRequest,
    ExportResult,
    validate_export_request,
)
from humanhand.domain.public_document import PublicDocument


class ExporterError(Exception):
    """Raised when an export cannot be produced or written."""


def _claim_proposition(claim: object) -> str:
    """Return the public proposition text of a claim entry.

    Claim entries may be plain strings or proposition-bearing entries: the
    repository's :class:`humanhand.domain.claims_v2.ClaimV2` carries the
    proposition in ``canonical_proposition``, and a plain ``proposition``
    attribute is accepted as well. Anything else fails closed.
    """
    if isinstance(claim, str):
        return claim
    for attribute in ("canonical_proposition", "proposition"):
        value = getattr(claim, attribute, None)
        if isinstance(value, str):
            return value
    raise ExporterError(f"Unsupported claim entry: {type(claim).__name__}")


def document_claims(document: PublicDocument) -> list[str]:
    """Return the public proposition texts of a document's claims."""
    return [_claim_proposition(claim) for claim in document.claims]


def _raise_if_empty(document: PublicDocument) -> None:
    """Refuse to emit an artifact from an empty public document."""
    title = document.title or ""
    has_title = bool(title.strip())
    has_sections = any(section.strip() for section in document.sections)
    if not has_title and not has_sections and not document_claims(document):
        raise ExporterError("Refusing to export an empty public document")


def _reject_humanhand_output(path: Path) -> None:
    """Fail closed when the output resolves inside any ``.humanhand`` tree."""
    if any(part == ".humanhand" for part in path.parent.parts):
        raise ExporterError(f"Output path must not resolve into a .humanhand directory: {path}")


def _atomic_write(path: Path, data: bytes) -> None:
    """Atomically write raw artifact bytes via temp file + ``os.replace``."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
        )
    except OSError as exc:
        raise ExporterError(f"Cannot prepare output file: {path}") from exc
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        os.replace(temp_name, path)
    except OSError as exc:
        with contextlib.suppress(OSError):
            os.unlink(temp_name)
        raise ExporterError(f"Cannot write output file: {path}") from exc


class BaseExporter(ABC):
    """One clean-room exporter for one public artifact format."""

    format: ExportFormat

    @abstractmethod
    def export_bytes(self, document: PublicDocument) -> bytes:
        """Render the document into this format's raw artifact bytes."""

    def export(self, request: ExportRequest) -> ExportResult:
        """Validate, render, and atomically write the artifact.

        Returns an :class:`ExportResult` carrying the output path, format,
        sha256, and byte count of the bytes written to
        ``request.output_path``. Any violation code from
        :func:`validate_export_request` fails the export closed.
        """
        violations = validate_export_request(request)
        if violations:
            raise ExporterError(f"Refusing export request: {', '.join(violations)}")
        if request.format is not self.format:
            raise ExporterError(
                f"Exporter {self.format} cannot handle request format {request.format}"
            )
        data = self.export_bytes(request.document)
        output = Path(request.output_path).resolve()
        _reject_humanhand_output(output)
        _atomic_write(output, data)
        return ExportResult(
            output_path=str(output),
            format=self.format,
            sha256=hashlib.sha256(data).hexdigest(),
            byte_count=len(data),
        )


def get_exporter(fmt: ExportFormat) -> BaseExporter:
    """Resolve the exporter registered for ``fmt``.

    Concrete exporters are imported lazily so this module stays free of
    import cycles with the per-format modules.
    """
    from humanhand.infra.exporters.docx_exporter import DocxExporter
    from humanhand.infra.exporters.markdown_exporter import MarkdownExporter
    from humanhand.infra.exporters.pdf_exporter import PdfExporter
    from humanhand.infra.exporters.text_exporter import TextExporter

    registry: dict[ExportFormat, BaseExporter] = {
        ExportFormat.TXT: TextExporter(),
        ExportFormat.MARKDOWN: MarkdownExporter(),
        ExportFormat.DOCX: DocxExporter(),
        ExportFormat.PDF: PdfExporter(),
    }
    try:
        return registry[fmt]
    except KeyError as exc:
        raise ExporterError(f"Unsupported export format: {fmt}") from exc
