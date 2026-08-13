"""PDF public-document exporter (blueprint section 11.5) built on reportlab.

Renders the title in Helvetica-Bold 16, sections as wrapped paragraphs, and
claim bullets when the document carries claims, then writes a fresh PDF via
``SimpleDocTemplate``.

Honest determinism note: PDF bytes are NOT byte-deterministic across runs —
reportlab embeds creation-time metadata (Info dictionary and document id) —
so the sha256 returned for a PDF export is of THIS run's bytes only. The
content (title, sections, claims) is deterministic; the container metadata
is not.
"""

from __future__ import annotations

import io
from html import escape

# reportlab ships no PEP 561 type stubs; mypy strict treats it as Any.
from reportlab.lib.pagesizes import letter  # type: ignore[import-untyped]
from reportlab.lib.styles import ParagraphStyle  # type: ignore[import-untyped]
from reportlab.lib.units import inch  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    Flowable,
    Paragraph,
    SimpleDocTemplate,
)

from humanhand.domain.export_contract import ExportFormat
from humanhand.domain.public_document import PublicDocument
from humanhand.infra.exporters.base import BaseExporter, _raise_if_empty, document_claims

_TITLE_STYLE = ParagraphStyle(
    "hh-title",
    fontName="Helvetica-Bold",
    fontSize=16,
    leading=20,
    spaceAfter=12,
)
_BODY_STYLE = ParagraphStyle(
    "hh-body",
    fontName="Helvetica",
    fontSize=11,
    leading=15,
    spaceAfter=8,
)
_CLAIMS_STYLE = ParagraphStyle(
    "hh-claims",
    fontName="Helvetica-Bold",
    fontSize=12,
    leading=15,
    spaceAfter=6,
)


class PdfExporter(BaseExporter):
    """Render a public document as a fresh PDF artifact."""

    format = ExportFormat.PDF

    def export_bytes(self, document: PublicDocument) -> bytes:
        _raise_if_empty(document)
        buffer = io.BytesIO()
        title = document.title or ""
        template = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            title=title,
            leftMargin=inch,
            rightMargin=inch,
            topMargin=inch,
            bottomMargin=inch,
        )
        flowables: list[Flowable] = []
        if title.strip():
            flowables.append(Paragraph(escape(title), _TITLE_STYLE))
        for section in document.sections:
            flowables.append(Paragraph(escape(section), _BODY_STYLE))
        claims = document_claims(document)
        if claims:
            flowables.append(Paragraph("Claims", _CLAIMS_STYLE))
            for proposition in claims:
                flowables.append(Paragraph(escape(f"• {proposition}"), _BODY_STYLE))
        template.build(flowables)
        return buffer.getvalue()
