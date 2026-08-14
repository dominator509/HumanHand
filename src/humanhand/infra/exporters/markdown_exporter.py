"""Content-only Markdown public-document exporter.

Emits only approved visible title and section content. Internal claims,
project identifiers, front matter, Obsidian block ids, HTML comments, and
Dataview fields are never rendered into the public artifact.
"""

from __future__ import annotations

from humanhand.domain.export_contract import ExportFormat
from humanhand.domain.public_document import PublicDocument
from humanhand.infra.exporters.base import BaseExporter, _raise_if_empty


class MarkdownExporter(BaseExporter):
    """Render a public document as byte-clean Markdown."""

    format = ExportFormat.MARKDOWN

    def export_bytes(self, document: PublicDocument) -> bytes:
        _raise_if_empty(document)
        parts: list[str] = []
        title = document.title or ""
        if title.strip():
            parts.append(f"# {title}")
        parts.extend(document.sections)
        return ("\n\n".join(parts) + "\n").encode("utf-8")
