"""TXT public-document exporter (blueprint section 11.2).

Guarantees: UTF-8, no BOM, LF line endings, no front matter, no comments,
no internal identifiers, no unexplained controls, and exactly one trailing
newline. Claims are intentionally NOT part of the TXT artifact: TXT is
content-only, and claims travel with Markdown, DOCX, and PDF instead.
"""

from __future__ import annotations

from humanhand.domain.export_contract import ExportFormat
from humanhand.domain.public_document import PublicDocument
from humanhand.infra.exporters.base import BaseExporter, ExporterError, _raise_if_empty


class TextExporter(BaseExporter):
    """Render a public document as a byte-clean TXT artifact."""

    format = ExportFormat.TXT

    def export_bytes(self, document: PublicDocument) -> bytes:
        _raise_if_empty(document)
        lines: list[str] = []
        title = document.title or ""
        if title.strip():
            lines.append(title)
        lines.extend(document.sections)
        if not lines:
            raise ExporterError(
                "TXT is content-only: refusing an artifact with no title or sections"
            )
        return ("\n\n".join(lines) + "\n").encode("utf-8")
