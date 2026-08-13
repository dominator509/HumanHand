"""Clean-room public-document exporters and their deterministic registry."""

from humanhand.infra.exporters.base import BaseExporter, ExporterError, get_exporter
from humanhand.infra.exporters.docx_exporter import DocxExporter
from humanhand.infra.exporters.docx_package import build_docx_package
from humanhand.infra.exporters.markdown_exporter import MarkdownExporter
from humanhand.infra.exporters.pdf_exporter import PdfExporter
from humanhand.infra.exporters.text_exporter import TextExporter

TXT_EXPORTER = TextExporter()
MARKDOWN_EXPORTER = MarkdownExporter()
DOCX_EXPORTER = DocxExporter()
PDF_EXPORTER = PdfExporter()

__all__ = [
    "DOCX_EXPORTER",
    "MARKDOWN_EXPORTER",
    "PDF_EXPORTER",
    "TXT_EXPORTER",
    "BaseExporter",
    "DocxExporter",
    "ExporterError",
    "MarkdownExporter",
    "PdfExporter",
    "TextExporter",
    "build_docx_package",
    "get_exporter",
]
