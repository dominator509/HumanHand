"""Synthetic ODT builders for importer integration tests (stdlib only).

Every builder emits a real, parseable OpenDocument Text package in memory:
the standard ``mimetype`` first entry (stored, per the ODF packaging rule),
a minimal ``content.xml`` with the correct namespaces, an optional
``meta.xml``, and an optional embedded macro library entry. Only the
Python standard library is used; no external libraries are required.
"""

from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape

_OFFICE_NS = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
_TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
_TABLE_NS = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
_DRAW_NS = "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
_XLINK_NS = "http://www.w3.org/1999/xlink"
_META_NS = "urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
_DC_NS = "http://purl.org/dc/elements/1.1/"

_MIMETYPE = "application/vnd.oasis.opendocument.text"

_CONTENT_TEMPLATE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    "<office:document-content "
    f'xmlns:office="{_OFFICE_NS}" xmlns:text="{_TEXT_NS}" '
    f'xmlns:table="{_TABLE_NS}" xmlns:draw="{_DRAW_NS}" '
    f'xmlns:xlink="{_XLINK_NS}" xmlns:meta="{_META_NS}" xmlns:dc="{_DC_NS}" '
    'office:version="1.2">'
    "<office:body><office:text>{body}</office:text></office:body>"
    "</office:document-content>"
)

_META_TEMPLATE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    "<office:document-meta "
    f'xmlns:office="{_OFFICE_NS}" xmlns:meta="{_META_NS}" xmlns:dc="{_DC_NS}" '
    'office:version="1.2">'
    "<office:meta>{fields}</office:meta>"
    "</office:document-meta>"
)


def _escape_attr(value: str) -> str:
    """Escape text for use inside a double-quoted XML attribute."""
    return escape(value, {'"': "&quot;"})


def _inline_xml(link_pairs: list[tuple[str, str]]) -> str:
    """Render link pairs as inline elements: empty labels become images."""
    rendered: list[str] = []
    for href, label in link_pairs:
        if label:
            rendered.append(f'<text:a xlink:href="{_escape_attr(href)}">{escape(label)}</text:a>')
        else:
            rendered.append(
                f'<draw:frame><draw:image xlink:href="{_escape_attr(href)}"/></draw:frame>'
            )
    return "".join(rendered)


def _body_xml(
    *,
    paragraphs: list[str],
    heading: str | None,
    links: list[tuple[str, str]] | None,
) -> str:
    """Render the office:text body: heading first, then paragraphs.

    Link pairs are inlined into the first paragraph: a non-empty label
    renders as a hyperlink, an empty label as an inline image.
    """
    parts: list[str] = []
    if heading is not None:
        parts.append(f'<text:h text:outline-level="1">{escape(heading)}</text:h>')
    link_pairs = list(links or [])
    text_paragraphs = list(paragraphs)
    if not text_paragraphs and link_pairs:
        text_paragraphs = [""]
    for index, text in enumerate(text_paragraphs):
        inline = _inline_xml(link_pairs) if index == 0 else ""
        if inline:
            parts.append(f"<text:p>{escape(text)} {inline}</text:p>")
        else:
            parts.append(f"<text:p>{escape(text)}</text:p>")
    return "".join(parts)


def _meta_xml(title: str | None) -> str:
    """Render meta.xml with the requested fields (empty when none)."""
    if title is None:
        return ""
    return _META_TEMPLATE.format(fields=f"<dc:title>{escape(title)}</dc:title>")


def _write_odt(content_xml: bytes, *, meta_xml: bytes, macros: bool) -> bytes:
    """Write a real ODT package in memory and return its bytes."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            zipfile.ZipInfo("mimetype"),
            _MIMETYPE,
            compress_type=zipfile.ZIP_STORED,
        )
        archive.writestr("content.xml", content_xml)
        if meta_xml:
            archive.writestr("meta.xml", meta_xml)
        if macros:
            archive.writestr(
                "Basic/Standard/Module1.xml",
                '<script:module xmlns:script="urn:oasis:names:tc:opendocument:xmlns:script:1.0" '
                'script:name="Module1">Sub Main\nEnd Sub</script:module>',
            )
    return buffer.getvalue()


def build_odt(
    *,
    paragraphs: list[str],
    heading: str | None = None,
    links: list[tuple[str, str]] | None = None,
    macros: bool = False,
    title: str | None = None,
) -> bytes:
    """Build a minimal valid ODT package with the requested structure."""
    body = _body_xml(paragraphs=paragraphs, heading=heading, links=links)
    content = _CONTENT_TEMPLATE.format(body=body).encode("utf-8")
    meta = _meta_xml(title).encode("utf-8") if title is not None else b""
    return _write_odt(content, meta_xml=meta, macros=macros)


def build_odt_with_content(
    content: bytes, *, title: str | None = None, macros: bool = False
) -> bytes:
    """Build an ODT package with a caller-supplied content.xml part."""
    meta = _meta_xml(title).encode("utf-8") if title is not None else b""
    return _write_odt(content, meta_xml=meta, macros=macros)
