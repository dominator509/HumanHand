"""Markdown public-document exporter (blueprint section 11.3).

Follows the TXT byte rules (UTF-8, no BOM, LF, exactly one trailing
newline) and emits only approved constructs: an ``# <title>`` heading,
section paragraphs, and an optional ``## Claims`` list that appears ONLY
when the document carries claims. No private front matter, Obsidian block
ids, HTML comments, or Dataview fields are ever emitted.
"""

from __future__ import annotations

from humanhand.domain.export_contract import ExportFormat
from humanhand.domain.public_document import PublicDocument
from humanhand.infra.exporters.base import BaseExporter, _raise_if_empty, document_claims


class MarkdownExporter(BaseExporter):
    """Render a public document as a byte-clean Markdown artifact."""

    format = ExportFormat.MARKDOWN

    def export_bytes(self, document: PublicDocument) -> bytes:
        _raise_if_empty(document)
        parts: list[str] = []
        title = document.title or ""
        if title.strip():
            parts.append(f"# {title}")
        parts.extend(document.sections)
        claims = document_claims(document)
        if claims:
            parts.append("## Claims")
            parts.extend(f"- {proposition}" for proposition in claims)
        return ("\n\n".join(parts) + "\n").encode("utf-8")
