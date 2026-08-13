"""Clean-room import adapters and their deterministic registry."""

from humanhand.domain.file_identity import FileIdentity, FileKind
from humanhand.infra.importers.base import (
    BaseImporter,
    ContainerImporter,
    DecodeResult,
    ParserAdapter,
    assemble_inspection,
    assemble_rich_payloads,
    decode_text,
    fail_closed_inspection,
    identity_precheck,
)
from humanhand.infra.importers.docx_importer import DocxImporter
from humanhand.infra.importers.file_type import (
    SUPPORTED_KINDS,
    UNSUPPORTED_KINDS,
    resolve_kind,
    unsupported_format_finding,
)
from humanhand.infra.importers.html_importer import HtmlImporter
from humanhand.infra.importers.legacy_doc_importer import (
    LegacyDocConverter,
    get_legacy_doc_converter,
    inspect_legacy_doc,
    set_legacy_doc_converter,
)
from humanhand.infra.importers.markdown_importer import MarkdownImporter
from humanhand.infra.importers.odt_importer import OdtImporter
from humanhand.infra.importers.pdf_importer import PdfImporter
from humanhand.infra.importers.rtf_importer import RtfImporter
from humanhand.infra.importers.text_importer import TextImporter

TEXT_IMPORTER = TextImporter()
MARKDOWN_IMPORTER = MarkdownImporter()
DOCX_IMPORTER = DocxImporter()
PDF_IMPORTER = PdfImporter()
HTML_IMPORTER = HtmlImporter()
RTF_IMPORTER = RtfImporter()
ODT_IMPORTER = OdtImporter()

_IMPORTER_BY_KIND: dict[FileKind, ParserAdapter] = {
    FileKind.TXT: TEXT_IMPORTER,
    FileKind.MARKDOWN: MARKDOWN_IMPORTER,
    FileKind.DOCX: DOCX_IMPORTER,
    FileKind.PDF: PDF_IMPORTER,
    FileKind.HTML: HTML_IMPORTER,
    FileKind.RTF: RTF_IMPORTER,
    FileKind.ODT: ODT_IMPORTER,
}

_IMPORTER_BY_NAME: dict[str, ParserAdapter] = {
    TEXT_IMPORTER.parser_name: TEXT_IMPORTER,
    MARKDOWN_IMPORTER.parser_name: MARKDOWN_IMPORTER,
    DOCX_IMPORTER.parser_name: DOCX_IMPORTER,
    PDF_IMPORTER.parser_name: PDF_IMPORTER,
    HTML_IMPORTER.parser_name: HTML_IMPORTER,
    RTF_IMPORTER.parser_name: RTF_IMPORTER,
    ODT_IMPORTER.parser_name: ODT_IMPORTER,
}


def get_importer_for(identity: FileIdentity) -> ParserAdapter | None:
    """Resolve the adapter for a file identity, or None when unsupported."""
    return _IMPORTER_BY_KIND.get(resolve_kind(identity))


def get_importer_by_name(name: str) -> ParserAdapter:
    """Resolve a registered adapter by parser name.

    Raises ValueError for unknown names so parser workers fail closed.
    """
    try:
        return _IMPORTER_BY_NAME[name]
    except KeyError as exc:
        raise ValueError(f"Unknown importer: {name}") from exc


__all__ = [
    "DOCX_IMPORTER",
    "HTML_IMPORTER",
    "MARKDOWN_IMPORTER",
    "ODT_IMPORTER",
    "PDF_IMPORTER",
    "RTF_IMPORTER",
    "SUPPORTED_KINDS",
    "TEXT_IMPORTER",
    "UNSUPPORTED_KINDS",
    "BaseImporter",
    "ContainerImporter",
    "DecodeResult",
    "LegacyDocConverter",
    "ParserAdapter",
    "assemble_inspection",
    "assemble_rich_payloads",
    "decode_text",
    "fail_closed_inspection",
    "get_importer_by_name",
    "get_importer_for",
    "get_legacy_doc_converter",
    "identity_precheck",
    "inspect_legacy_doc",
    "resolve_kind",
    "set_legacy_doc_converter",
    "unsupported_format_finding",
]
