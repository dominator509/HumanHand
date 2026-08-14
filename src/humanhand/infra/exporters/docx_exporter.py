"""Content-only DOCX public-document exporter.

Builds a fresh minimal OOXML package from the approved visible title and
sections. Internal claim records are never rendered into the public artifact.
"""

from __future__ import annotations

from humanhand.domain.export_contract import ExportFormat
from humanhand.domain.public_document import PublicDocument
from humanhand.infra.exporters.base import BaseExporter, _raise_if_empty
from humanhand.infra.exporters.docx_package import build_docx_package


class DocxExporter(BaseExporter):
    """Render a public document as a fresh minimal DOCX package."""

    format = ExportFormat.DOCX

    def export_bytes(self, document: PublicDocument) -> bytes:
        _raise_if_empty(document)
        paragraphs: list[str] = []
        title = document.title or ""
        if title.strip():
            paragraphs.append(title)
        paragraphs.extend(document.sections)
        return build_docx_package(paragraphs)
