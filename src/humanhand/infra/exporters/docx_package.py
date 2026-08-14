"""Minimal metadata-free deterministic OOXML DOCX package builder.

The package contains only the content-types declaration, root office-document
relationship, and ``word/document.xml``. It deliberately omits ``docProps``,
custom XML, comments, revisions, macros, external relationships, headers,
footers, thumbnails, and embedded objects. Equal paragraph inputs produce
byte-identical ZIP bytes with fixed member order and timestamps.
"""

from __future__ import annotations

import io
import zipfile
from html import escape

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def _content_types_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Types xmlns="{_CT_NS}">'
        '<Default Extension="rels" ContentType="'
        'application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="'
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )


def _root_rels_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_PK_REL_NS}">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        'officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )


def _document_xml(paragraphs: list[str]) -> str:
    body_parts = [
        f'<w:p><w:r><w:t xml:space="preserve">{escape(paragraph)}</w:t></w:r></w:p>'
        for paragraph in paragraphs
    ]
    body_parts.append("<w:sectPr/>")
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{_W_NS}"><w:body>' + "".join(body_parts) + "</w:body></w:document>"
    )


def _write_member(archive: zipfile.ZipFile, name: str, text: str) -> None:
    info = zipfile.ZipInfo(filename=name, date_time=_FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    archive.writestr(info, text.encode("utf-8"))


def build_docx_package(paragraphs: list[str]) -> bytes:
    """Build a fresh deterministic DOCX package from approved paragraphs."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        _write_member(archive, "[Content_Types].xml", _content_types_xml())
        _write_member(archive, "_rels/.rels", _root_rels_xml())
        _write_member(archive, "word/document.xml", _document_xml(paragraphs))
    return buffer.getvalue()
