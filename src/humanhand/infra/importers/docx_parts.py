"""Deterministic DOCX package part inventory for the clean-room importer.

Every part read and XML parse goes through the ``container_utils`` bounded
helpers so hostile packages fail closed with findings instead of exhausting
memory. Nothing in this module opens files, touches the network, or
executes content.

Metadata property parts (``docProps/core.xml``, ``docProps/app.xml``,
``docProps/custom.xml``) become ``docx_property`` metadata items; other
parts contribute deterministic presence counts. Document text is extracted
mechanically with stdlib ``re`` only: the content of ``<w:t>`` runs is kept
and runs are joined per paragraph with ``\\n``. No namespace-preserving
trickery is attempted.

Each helper that needs ``word/document.xml`` reads it independently through
the bounded entry reader; results stay deterministic and the per-read
expanded-size limit is enforced on every read.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from html import unescape

from humanhand.domain.document_nodes import SourceLocation
from humanhand.domain.import_findings import (
    FindingCategory,
    FindingCode,
    FindingSeverity,
    ImportFinding,
)
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.metadata_inventory import MetadataItem
from humanhand.infra.importers.container_utils import (
    ET,
    parse_xml_bounded,
    read_zip_entry_bounded,
)

MAIN_DOCUMENT_PART = "word/document.xml"
CORE_PROPERTIES_PART = "docProps/core.xml"
APP_PROPERTIES_PART = "docProps/app.xml"
CUSTOM_PROPERTIES_PART = "docProps/custom.xml"
COMMENTS_PART = "word/comments.xml"
SETTINGS_PART = "word/settings.xml"

# Mechanical text extraction: <w:t> run contents, joined per <w:p> paragraph.
_W_T_RE = re.compile(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", re.DOTALL)
_W_P_RE = re.compile(r"<w:p(?:\s[^>]*)?>.*?</w:p>", re.DOTALL)

# Mechanical presence scans inside part XML text.
_FLD_CHAR_RE = re.compile(r"<w:fldChar\b")
_VANISH_RE = re.compile(r"<w:vanish\b")
_DOC_VAR_RE = re.compile(r"<w:docVar\b")

# Tracked-change markers (insertions and deletions).
_W_INS_DEL_RE = re.compile(r"<w:(ins|del)\b", re.IGNORECASE)

# Mechanical table extraction: <w:tbl> blocks, <w:tr> rows, <w:tc> cells.
_TBL_RE = re.compile(r"<w:tbl(?:\s[^>]*)?>.*?</w:tbl>", re.DOTALL)
_TR_RE = re.compile(r"<w:tr(?:\s[^>]*)?>.*?</w:tr>", re.DOTALL)
_TC_RE = re.compile(r"<w:tc(?:\s[^>]*)?>.*?</w:tc>", re.DOTALL)

_PROPERTY_PARTS: tuple[tuple[str, str], ...] = (
    (CORE_PROPERTIES_PART, "core"),
    (APP_PROPERTIES_PART, "app"),
    (CUSTOM_PROPERTIES_PART, "custom"),
)


@dataclass(frozen=True)
class DocxTableCell:
    """Mechanically extracted table-cell text and its exact surface span."""

    text: str
    source_location: SourceLocation | None


def _local(tag: str) -> str:
    """Return the local part of a possibly namespace-prefixed element tag."""
    return tag.rsplit("}", 1)[-1]


def _property_items(root: ET.Element, prefix: str) -> list[MetadataItem]:
    """Extract core/app property elements as ``docx_property`` items."""
    items: list[MetadataItem] = []
    for element in root:
        value = "".join(element.itertext()).strip()
        if not value:
            continue
        items.append(
            MetadataItem(
                key=f"{prefix}:{_local(element.tag)}",
                kind="docx_property",
                value=value,
            )
        )
    return items


def _custom_property_items(root: ET.Element) -> list[MetadataItem]:
    """Extract custom.xml ``property`` elements (named via their name attribute)."""
    items: list[MetadataItem] = []
    for element in root:
        if _local(element.tag) != "property":
            continue
        name = element.attrib.get("name", "")
        value = "".join(element.itertext()).strip()
        if not name or not value:
            continue
        items.append(
            MetadataItem(
                key=f"custom:{name}",
                kind="docx_property",
                value=value,
            )
        )
    return items


def _extract_runs(xml_fragment: str) -> str:
    """Concatenate and unescape the <w:t> run contents of an XML fragment."""
    return unescape("".join(_W_T_RE.findall(xml_fragment)))


def _read_document_xml(
    archive: zipfile.ZipFile, policy: ImportPolicy
) -> tuple[str, list[ImportFinding]]:
    """Read ``word/document.xml`` for scans, tolerating broken UTF-8.

    Findings (missing part, over-limit, unreadable) are returned instead of
    raised; ``xml_text`` is empty when findings are non-empty.
    """
    data, findings = read_zip_entry_bounded(archive, MAIN_DOCUMENT_PART, policy)
    if findings:
        return "", list(findings)
    return data.decode("utf-8", errors="replace"), []


def inventory_parts(
    archive: zipfile.ZipFile, policy: ImportPolicy
) -> tuple[list[MetadataItem], list[ImportFinding]]:
    """Inventory DOCX parts: properties, presence counts, and their findings.

    Returns ``(items, findings)`` in a fixed deterministic order. Presence
    counts are recorded only when greater than zero; the count is the
    number of parts (or XML occurrences) of that kind.
    """
    items: list[MetadataItem] = []
    findings: list[ImportFinding] = []
    names = archive.namelist()
    name_set = set(names)

    for part, prefix in _PROPERTY_PARTS:
        if part not in name_set:
            continue
        data, read_findings = read_zip_entry_bounded(archive, part, policy)
        findings.extend(read_findings)
        if not data:
            continue
        root, parse_findings = parse_xml_bounded(data, policy, part)
        findings.extend(parse_findings)
        if root is None:
            continue
        if part == CUSTOM_PROPERTIES_PART:
            items.extend(_custom_property_items(root))
        else:
            items.extend(_property_items(root, prefix))

    def _record(kind: str, count: int) -> None:
        if count > 0:
            items.append(MetadataItem(key=kind, kind=kind, value=str(count)))

    comments = sum(1 for name in names if re.fullmatch(r"word/comments\d*\.xml", name) is not None)
    headers_footers = sum(
        1 for name in names if re.fullmatch(r"word/(header|footer)\d*\.xml", name) is not None
    )
    footnotes_endnotes = sum(
        1 for name in names if name in {"word/footnotes.xml", "word/endnotes.xml"}
    )
    styles = 1 if "word/styles.xml" in name_set else 0
    numbering = 1 if "word/numbering.xml" in name_set else 0
    custom_xml = sum(
        1 for name in names if re.fullmatch(r"word/customXml/item\d+\.xml", name) is not None
    )
    embedded_objects = sum(1 for name in names if name.startswith("word/embeddings/"))

    document_xml, document_findings = _read_document_xml(archive, policy)
    findings.extend(document_findings)
    fields = len(_FLD_CHAR_RE.findall(document_xml))
    hidden_text = len(_VANISH_RE.findall(document_xml))

    settings_xml = ""
    if SETTINGS_PART in name_set:
        data, part_findings = read_zip_entry_bounded(archive, SETTINGS_PART, policy)
        findings.extend(part_findings)
        settings_xml = data.decode("utf-8", errors="replace")
    document_variables = len(_DOC_VAR_RE.findall(settings_xml))

    _record("docx_comments", comments)
    _record("docx_headers_footers", headers_footers)
    _record("docx_footnotes_endnotes", footnotes_endnotes)
    _record("docx_fields", fields)
    _record("docx_document_variables", document_variables)
    _record("docx_styles", styles)
    _record("docx_numbering", numbering)
    _record("docx_custom_xml", custom_xml)
    _record("docx_hidden_text", hidden_text)
    _record("docx_embedded_objects", embedded_objects)

    return items, findings


def _is_macro_part(name: str) -> bool:
    lowered = name.lower()
    return "vbaproject" in lowered or "macro" in lowered


def macro_part_name(archive: zipfile.ZipFile) -> str | None:
    """Return the first part path containing ``vbaProject`` or ``macro``."""
    for name in archive.namelist():
        if _is_macro_part(name):
            return name
    return None


def has_macros(archive: zipfile.ZipFile) -> bool:
    """True when the package contains a VBA macro part."""
    return macro_part_name(archive) is not None


def embedded_object_names(names: list[str]) -> tuple[str, ...]:
    """Return archive entry names of embedded OLE object parts."""
    return tuple(name for name in names if name.startswith("word/embeddings/"))


def has_tracked_changes(
    archive: zipfile.ZipFile, policy: ImportPolicy
) -> tuple[bool, list[ImportFinding]]:
    """True when the document part contains ``<w:ins>`` or ``<w:del>`` elements."""
    xml_text, findings = _read_document_xml(archive, policy)
    if findings:
        return False, list(findings)
    return _W_INS_DEL_RE.search(xml_text) is not None, []


def external_relationships(
    archive: zipfile.ZipFile, policy: ImportPolicy
) -> tuple[tuple[str, ...], list[ImportFinding]]:
    """Return external relationship URLs plus bounded read/parse findings.

    Every ``*.rels`` part is parsed; each ``Relationship`` element with
    ``TargetMode="External"`` contributes its ``Target`` URL. Parts that
    fail to read or parse contribute findings so callers fail closed rather
    than silently treating an uninspected relationship part as safe.
    """
    urls: set[str] = set()
    findings: list[ImportFinding] = []
    for name in archive.namelist():
        if not name.endswith(".rels"):
            continue
        data, read_findings = read_zip_entry_bounded(archive, name, policy)
        findings.extend(read_findings)
        if not data:
            continue
        root, parse_findings = parse_xml_bounded(data, policy, name)
        findings.extend(parse_findings)
        if root is None:
            continue
        for element in root.iter():
            if _local(element.tag) != "Relationship":
                continue
            if element.attrib.get("TargetMode") == "External":
                target = element.attrib.get("Target")
                if target:
                    urls.add(target)
    return tuple(sorted(urls)), findings


def document_body_text(
    archive: zipfile.ZipFile, policy: ImportPolicy
) -> tuple[str, list[ImportFinding]]:
    """Extract paragraph text from ``word/document.xml`` mechanically.

    Returns ``(text, findings)`` where ``text`` joins each paragraph's
    ``<w:t>`` run contents with ``\\n``. On a missing, unreadable, or
    over-limit part, or invalid UTF-8, ``text`` is empty and the findings
    explain why.
    """
    data, findings = read_zip_entry_bounded(archive, MAIN_DOCUMENT_PART, policy)
    if findings:
        return "", list(findings)
    try:
        xml_text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        finding = ImportFinding(
            code=FindingCode.ENCODING_INVALID_UTF8,
            severity=FindingSeverity.ERROR,
            category=FindingCategory.ENCODING,
            description="DOCX document part is not valid utf-8",
            evidence=f"decode_error={exc.reason}",
        )
        return "", [finding]
    paragraphs = [_extract_runs(part) for part in _W_P_RE.findall(xml_text)]
    return "\n".join(paragraphs), []


def document_tables(
    archive: zipfile.ZipFile, policy: ImportPolicy
) -> tuple[list[list[list[DocxTableCell]]], list[ImportFinding]]:
    """Extract table cell texts from ``word/document.xml`` mechanically.

    Returns ``(tables, findings)`` where each table is a list of rows and
    each row contains cell text plus its exact span in ``document_body_text``.
    Extraction is regex-based and flat: nested tables are not reconstructed.
    """
    xml_text, findings = _read_document_xml(archive, policy)
    if findings:
        return [], list(findings)
    paragraph_spans: list[tuple[int, int, str, SourceLocation]] = []
    surface_cursor = 0
    for paragraph in _W_P_RE.finditer(xml_text):
        text = _extract_runs(paragraph.group())
        paragraph_spans.append(
            (
                paragraph.start(),
                paragraph.end(),
                text,
                SourceLocation(surface_cursor, surface_cursor + len(text)),
            )
        )
        surface_cursor += len(text) + 1

    tables: list[list[list[DocxTableCell]]] = []
    for tbl_match in _TBL_RE.finditer(xml_text):
        rows: list[list[DocxTableCell]] = []
        for tr_match in _TR_RE.finditer(tbl_match.group()):
            row: list[DocxTableCell] = []
            row_xml_start = tbl_match.start() + tr_match.start()
            for tc_match in _TC_RE.finditer(tr_match.group()):
                cell_xml_start = row_xml_start + tc_match.start()
                cell_xml_end = row_xml_start + tc_match.end()
                cell_paragraphs = [
                    item
                    for item in paragraph_spans
                    if item[0] >= cell_xml_start and item[1] <= cell_xml_end
                ]
                if cell_paragraphs:
                    cell_text = "\n".join(item[2] for item in cell_paragraphs)
                    location = SourceLocation(
                        cell_paragraphs[0][3].start_offset,
                        cell_paragraphs[-1][3].end_offset,
                    )
                else:
                    cell_text = _extract_runs(tc_match.group())
                    location = None
                row.append(DocxTableCell(cell_text, location))
            rows.append(row)
        tables.append(rows)
    return tables, []
