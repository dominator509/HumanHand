"""Minimal but REAL OOXML DOCX package builder (deterministic).

Mirrors the structural pattern of ``tests/integration/support/docx_builder.py``:
a ZIP of ``[Content_Types].xml``, ``_rels/.rels``, ``word/document.xml`` with
``w:p/w:r/w:t`` runs (text XML-escaped), and ``docProps/core.xml`` carrying
only ``dc:title``. A fresh package means no comments, tracked changes, macros,
embeddings, external relationships, headers/footers, or author/revision
metadata (blueprint section 11.4 audit list). Byte-deterministic: fixed member
order, fixed compression, and zipfile's fixed default member timestamps.
"""

from __future__ import annotations

import io
import zipfile
from html import escape

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_CORE_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
_DC_NS = "http://purl.org/dc/elements/1.1/"


def _content_types_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Types xmlns="{_CT_NS}">'
        '<Default Extension="rels" ContentType="'
        'application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="'
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="'
        'application/vnd.openxmlformats-package.core-properties+xml"/>'
        "</Types>"
    )


def _root_rels_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_PKG_REL_NS}">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        'officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )


def _document_xml(paragraphs: list[str]) -> str:
    body_parts = [f"<w:p><w:r><w:t>{escape(p)}</w:t></w:r></w:p>" for p in paragraphs]
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{_W_NS}"><w:body>' + "".join(body_parts) + "</w:body></w:document>"
    )


def _core_properties_xml(title: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<cp:coreProperties xmlns:cp="{_CORE_NS}" xmlns:dc="{_DC_NS}">'
        f"<dc:title>{escape(title)}</dc:title>"
        "</cp:coreProperties>"
    )


def build_docx_package(title: str, paragraphs: list[str]) -> bytes:
    """Build a minimal valid DOCX package in memory and return its bytes.

    ``title`` becomes ``dc:title`` in ``docProps/core.xml``; ``paragraphs``
    become ``<w:p><w:r><w:t>`` runs in the document body with text escaped.
    The package is deterministic for identical inputs.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml())
        archive.writestr("_rels/.rels", _root_rels_xml())
        archive.writestr("word/document.xml", _document_xml(paragraphs))
        archive.writestr("docProps/core.xml", _core_properties_xml(title))
    return buffer.getvalue()
