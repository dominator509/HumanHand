"""Metadata-free public PDF exporter (EP-019).

The first pass renders approved visible content with ReportLab in invariant
mode. The second pass copies only pages into a fresh pypdf writer, removes the
regular metadata dictionary, omits XMP/root metadata, and leaves the trailer
identifier unset. Internal claim records are never rendered into the public
artifact.
"""

from __future__ import annotations

import io
from html import escape
from typing import Any

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject
from reportlab.lib.pagesizes import letter  # type: ignore[import-untyped]
from reportlab.lib.styles import ParagraphStyle  # type: ignore[import-untyped]
from reportlab.lib.units import inch  # type: ignore[import-untyped]
from reportlab.pdfgen.canvas import Canvas  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    Flowable,
    Paragraph,
    SimpleDocTemplate,
)

from humanhand.domain.export_contract import ExportFormat
from humanhand.domain.public_document import PublicDocument
from humanhand.infra.exporters.base import BaseExporter, _raise_if_empty

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


def _invariant_canvas(*args: Any, **kwargs: Any) -> Canvas:
    """Build a ReportLab canvas with deterministic timestamp/ID inputs."""
    kwargs["invariant"] = 1
    return Canvas(*args, **kwargs)


def _sanitize_pdf(rendered: bytes) -> bytes:
    """Copy visible pages into a fresh metadata-free PDF object tree."""
    reader = PdfReader(io.BytesIO(rendered), strict=True)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.metadata = None
    writer.root_object.pop(NameObject("/Metadata"), None)
    # A new writer starts without an identifier. Set it explicitly to make
    # the no-/ID contract clear and fail independent audit if pypdf changes.
    writer._ID = None  # noqa: SLF001 - deliberate PDF trailer contract
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


class PdfExporter(BaseExporter):
    """Render approved content as a fresh, independently auditable PDF."""

    format = ExportFormat.PDF

    def export_bytes(self, document: PublicDocument) -> bytes:
        _raise_if_empty(document)
        buffer = io.BytesIO()
        title = document.title or ""
        template = SimpleDocTemplate(
            buffer,
            pagesize=letter,
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
        template.build(flowables, canvasmaker=_invariant_canvas)
        return _sanitize_pdf(buffer.getvalue())
