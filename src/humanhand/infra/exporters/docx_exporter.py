"""DOCX public-document exporter (blueprint section 11.4).

Builds a fresh OOXML package from title + sections, plus a final ``Claims:``
paragraph block with one bullet paragraph per claim when the document
carries claims. The package is byte-deterministic for identical documents.
"""

from __future__ import annotations

from humanhand.domain.export_contract import ExportFormat
from humanhand.domain.public_document import PublicDocument
from humanhand.infra.exporters.base import BaseExporter, _raise_if_empty, document_claims
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
        claims = document_claims(document)
        if claims:
            paragraphs.append("Claims:")
            paragraphs.extend(f"• {proposition}" for proposition in claims)
        return build_docx_package(title, paragraphs)
