"""Synthetic PDF builders for importer integration tests (pypdf only).

Every builder emits a real, parseable PDF whose text pypdf extracts back
deterministically. No external libraries (e.g. reportlab) are used: pages
carry a minimal content stream in the standard Helvetica font, and
features (JavaScript, AcroForm, embedded files, annotations, image
XObjects) are written with pypdf's own generic objects.
"""

from __future__ import annotations

import io

from pypdf import PdfWriter
from pypdf.annotations import Text
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

_FONT_RESOURCES = DictionaryObject(
    {
        NameObject("/Font"): DictionaryObject(
            {
                NameObject("/F1"): DictionaryObject(
                    {
                        NameObject("/Type"): NameObject("/Font"),
                        NameObject("/Subtype"): NameObject("/Type1"),
                        NameObject("/BaseFont"): NameObject("/Helvetica"),
                    }
                )
            }
        )
    }
)


def _content_stream(text: str) -> DecodedStreamObject:
    """Build a real page content stream drawing one line of Helvetica text."""
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii"))
    return stream


def _add_text_page(writer: PdfWriter, text: str) -> None:
    page = writer.add_blank_page(width=612, height=792)
    page[NameObject("/Contents")] = _content_stream(text)
    page[NameObject("/Resources")] = _FONT_RESOURCES


def _write(writer: PdfWriter) -> bytes:
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def build_pdf(text_pages: list[str]) -> bytes:
    """Build a PDF with one native-text page per entry."""
    writer = PdfWriter()
    for text in text_pages:
        _add_text_page(writer, text)
    return _write(writer)


def build_pdf_with_javascript(text_pages: list[str]) -> bytes:
    """Build a text PDF whose catalog /OpenAction is a JavaScript action."""
    writer = PdfWriter()
    for text in text_pages:
        _add_text_page(writer, text)
    writer._root_object[NameObject("/OpenAction")] = DictionaryObject(
        {
            NameObject("/S"): NameObject("/JavaScript"),
            NameObject("/JS"): TextStringObject("app.alert('from synthetic pdf');"),
        }
    )
    return _write(writer)


def build_pdf_with_names_javascript(text_pages: list[str]) -> bytes:
    """Build a text PDF with JavaScript under the catalog /Names name tree."""
    writer = PdfWriter()
    for text in text_pages:
        _add_text_page(writer, text)
    writer.add_js("app.alert('from synthetic pdf');")
    return _write(writer)


def build_pdf_with_acroform(text_pages: list[str]) -> bytes:
    """Build a text PDF whose catalog declares an interactive form."""
    writer = PdfWriter()
    for text in text_pages:
        _add_text_page(writer, text)
    writer._root_object[NameObject("/AcroForm")] = DictionaryObject(
        {NameObject("/Fields"): ArrayObject()}
    )
    return _write(writer)


def build_pdf_with_attachment(text_pages: list[str]) -> bytes:
    """Build a text PDF with one embedded file declared under /Names."""
    writer = PdfWriter()
    for text in text_pages:
        _add_text_page(writer, text)
    writer.add_attachment("note.txt", b"attachment payload")
    return _write(writer)


def build_pdf_with_annotation(text_pages: list[str]) -> bytes:
    """Build a text PDF with one real Text annotation on the first page."""
    writer = PdfWriter()
    for text in text_pages:
        _add_text_page(writer, text)
    writer.add_annotation(0, Text(text="a note", rect=(50, 50, 200, 200)))
    return _write(writer)


def build_image_only_pdf() -> bytes:
    """Build a one-page PDF holding a real 1x1 RGB image XObject and no text.

    The XObject is a genuine image stream (Type/Subtype/Width/Height/
    ColorSpace/BitsPerComponent plus pixel data), so ``page_has_image``
    detects it and ``extract_text`` returns an empty string.
    """
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    image = DecodedStreamObject()
    image.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(1),
            NameObject("/Height"): NumberObject(1),
            NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
            NameObject("/BitsPerComponent"): NumberObject(8),
        }
    )
    image.set_data(b"\x00\x00\x00")
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/XObject"): DictionaryObject({NameObject("/Im0"): image})}
    )
    return _write(writer)
