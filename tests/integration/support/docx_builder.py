"""Deterministic in-memory DOCX builder for the docx importer tests.

Builds a minimal but valid OPC package (a ZIP of XML parts) matching the
structure the docx adapter inspects. Nothing here touches the filesystem.
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
_DCTERMS_NS = "http://purl.org/dc/terms/"
_XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def _xml_paragraph(text: str, *, tracked_change: bool = False) -> str:
    escaped = escape(text)
    if tracked_change:
        return f'<w:p><w:ins w:id="1"><w:r><w:t>{escaped}</w:t></w:r></w:ins></w:p>'
    return f"<w:p><w:r><w:t>{escaped}</w:t></w:r></w:p>"


def _document_xml(
    paragraphs: list[str],
    *,
    tracked_changes: bool = False,
    table: bool = False,
) -> str:
    body_parts = [_xml_paragraph(p, tracked_change=tracked_changes) for p in paragraphs]
    if table:
        body_parts.append(
            "<w:tbl>"
            "<w:tr><w:tc><w:p><w:r><w:t>alpha</w:t></w:r></w:p></w:tc>"
            "<w:tc><w:p><w:r><w:t>beta</w:t></w:r></w:p></w:tc></w:tr>"
            "<w:tr><w:tc><w:p><w:r><w:t>gamma</w:t></w:r></w:p></w:tc>"
            "<w:tc><w:p><w:r><w:t>delta</w:t></w:r></w:p></w:tc></w:tr>"
            "</w:tbl>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{_W_NS}"><w:body>' + "".join(body_parts) + "</w:body></w:document>"
    )


def _content_types(*, comments: bool, properties: bool) -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<Types xmlns="{_CT_NS}">',
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Override PartName="/word/document.xml" ContentType="'
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>',
    ]
    if comments:
        parts.append(
            '<Override PartName="/word/comments.xml" ContentType="'
            'application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"/>'
        )
    if properties:
        parts.append(
            '<Override PartName="/docProps/core.xml" ContentType="'
            'application/vnd.openxmlformats-package.core-properties+xml"/>'
        )
    parts.append("</Types>")
    return "".join(parts)


def _root_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_PKG_REL_NS}">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        'officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )


def _external_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_PKG_REL_NS}">'
        '<Relationship Id="rIdE1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        'hyperlink" Target="https://example.com/page" TargetMode="External"/>'
        "</Relationships>"
    )


def _comments_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:comments xmlns:w="{_W_NS}">'
        '<w:comment w:id="0" w:author="Reviewer">'
        "<w:p><w:r><w:t>Note about paragraph one</w:t></w:r></w:p>"
        "</w:comment>"
        "</w:comments>"
    )


def _core_properties_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<cp:coreProperties xmlns:cp="{_CORE_NS}" xmlns:dc="{_DC_NS}" '
        f'xmlns:dcterms="{_DCTERMS_NS}" xmlns:xsi="{_XSI_NS}">'
        "<dc:title>Synthetic Document</dc:title>"
        "<dc:creator>Synthetic Author</dc:creator>"
        "<cp:lastModifiedBy>Synthetic Editor</cp:lastModifiedBy>"
        '<dcterms:created xsi:type="dcterms:W3CDTF">2026-01-01T00:00:00Z</dcterms:created>'
        "</cp:coreProperties>"
    )


def build_docx(
    paragraphs: list[str],
    *,
    comments: bool = False,
    tracked_changes: bool = False,
    macros: bool = False,
    external_link: bool = False,
    properties: bool = False,
    table: bool = False,
) -> bytes:
    """Build a synthetic .docx package and return it as bytes.

    ``paragraphs`` become ``<w:p>`` paragraphs in the document body.
    Optional extras (comments, tracked changes, macros, external links,
    core properties, a fixed 2x2 table) are included on request so tests
    exercise each adapter path deterministically.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml", _content_types(comments=comments, properties=properties)
        )
        archive.writestr("_rels/.rels", _root_rels())
        archive.writestr(
            "word/document.xml",
            _document_xml(paragraphs, tracked_changes=tracked_changes, table=table),
        )
        if comments:
            archive.writestr("word/comments.xml", _comments_xml())
        if external_link:
            archive.writestr("word/_rels/document.xml.rels", _external_rels())
        if macros:
            archive.writestr("word/vbaProject.bin", b"\x00VBA\x00\x01\x02")
        if properties:
            archive.writestr("docProps/core.xml", _core_properties_xml())
    return buffer.getvalue()
