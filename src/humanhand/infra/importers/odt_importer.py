"""Clean-room ODT importer producing canonical document structures (EP-013).

Parses OpenDocument Text (ODT) packages with stdlib ``zipfile`` and the
defused ``ElementTree`` exposed by ``container_utils`` (the repository's
single XML choke point). Every
archive access and XML parse goes through the ``container_utils`` bounded
helpers, so hostile packages fail closed with findings instead of exhausting
memory. The importer never opens files, never touches the network, and
never executes content: macro libraries are detected structurally and
reported as active-content evidence, and remote ``xlink:href`` targets are
reported with scheme-and-host evidence only.

Representation model
--------------------
The canonical tree mirrors the ODT block model:
- ``text:h`` -> HEADING with ``level`` from ``text:outline-level`` ("1" when absent)
- ``text:p`` -> PARAGRAPH (paragraphs inside list items and table cells are
  consumed into the item/cell text instead)
- ``text:list`` -> LIST; ``text:list-item`` -> LIST_ITEM whose text is the
  item's own paragraph text (nested lists attach to their containing item)
- ``table:table`` / ``table:table-row`` / ``table:table-cell`` -> TABLE /
  TABLE_ROW / TABLE_CELL; a cell's text is its concatenated descendant text
- ``text:a`` -> HYPERLINK (only when not inside a paragraph or heading,
  where inline links attach to the containing block instead)
- ``draw:image`` (or ``draw:frame`` carrying an ``xlink:href`` itself and no
  child image) -> IMAGE_PLACEHOLDER with attribute ``url``

``surface_text`` joins every block text (headings, body paragraphs, list
items, table cells) with ``\\n``. Each block line is placed where its block
opens, which is document order for typical bodies. A block whose text is
collected from paragraphs inside a list item or table cell is a single
line, so text nested between such paragraphs cannot be re-split back into
visual order — the line order is deterministic, not a fidelity guarantee.
Node spans index the surface text exactly.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field

from humanhand.domain.active_content import scheme_host_only
from humanhand.domain.canonical_document import CoverageSummary
from humanhand.domain.document_nodes import NodeBuilder, NodeType, SourceLocation
from humanhand.domain.file_identity import FileKind
from humanhand.domain.import_findings import (
    FindingCategory,
    FindingCode,
    FindingSeverity,
    ImportFinding,
)
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.metadata_inventory import MetadataInventory, MetadataItem
from humanhand.infra.importers.base import ContainerImporter, assemble_rich_payloads
from humanhand.infra.importers.container_utils import (
    ET,
    evidence_name,
    open_zip_bounded,
    parse_xml_bounded,
    read_zip_entry_bounded,
)

_OFFICE_NS = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
_TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
_TABLE_NS = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
_DRAW_NS = "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
_XLINK_NS = "http://www.w3.org/1999/xlink"
_META_NS = "urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
_DC_NS = "http://purl.org/dc/elements/1.1/"

CONTENT_PART = "content.xml"
META_PART = "meta.xml"

_TAG_TEXT_H = f"{{{_TEXT_NS}}}h"
_TAG_TEXT_P = f"{{{_TEXT_NS}}}p"
_TAG_TEXT_LIST = f"{{{_TEXT_NS}}}list"
_TAG_TEXT_LIST_ITEM = f"{{{_TEXT_NS}}}list-item"
_TAG_TEXT_A = f"{{{_TEXT_NS}}}a"
_TAG_TABLE = f"{{{_TABLE_NS}}}table"
_TAG_TABLE_ROW = f"{{{_TABLE_NS}}}table-row"
_TAG_TABLE_CELL = f"{{{_TABLE_NS}}}table-cell"
_TAG_DRAW_IMAGE = f"{{{_DRAW_NS}}}image"
_TAG_DRAW_FRAME = f"{{{_DRAW_NS}}}frame"
_TAG_DC_TITLE = f"{{{_DC_NS}}}title"
_TAG_DC_CREATOR = f"{{{_DC_NS}}}creator"
_TAG_META_CREATION_DATE = f"{{{_META_NS}}}creation-date"
_TAG_META_USER_DEFINED = f"{{{_META_NS}}}user-defined"

_ATTR_XLINK_HREF = f"{{{_XLINK_NS}}}href"
_ATTR_TEXT_OUTLINE_LEVEL = f"{{{_TEXT_NS}}}outline-level"
_ATTR_META_NAME = f"{{{_META_NS}}}name"

# Structures this adapter can represent, in a stable order.
_SUPPORTED_STRUCTURES = (
    "heading",
    "paragraph",
    "list",
    "list_item",
    "table",
    "table_row",
    "table_cell",
    "hyperlink",
    "image_placeholder",
)

# Mirrors domain/active_content.py: evidence carries scheme and host only.
_SCHEME_HOST_RE = re.compile(r"[a-z][a-z0-9+.-]*://[^/\s\"'<>()?#]{0,64}", re.IGNORECASE)

_BLOCK_TAGS = frozenset({_TAG_TEXT_P, _TAG_TEXT_H})
_ACTIVE_CATEGORIES = frozenset(
    {
        FindingCategory.ACTIVE_CONTENT,
        FindingCategory.EXTERNAL_RELATIONSHIP,
        FindingCategory.UNSUPPORTED_FEATURE,
    }
)


@dataclass(frozen=True)
class _LinkHit:
    """One inline link with its exact span inside a block's text."""

    text: str
    start: int
    end: int
    href: str


@dataclass
class _Unit:
    """One surface-text line owned by a block (paragraph, heading, item, cell)."""

    builder: NodeBuilder
    element: ET.Element
    parts: list[str] = field(default_factory=list)
    hits: list[_LinkHit] = field(default_factory=list)
    length: int = 0

    @property
    def text(self) -> str:
        return "".join(self.parts)

    def append_text(self, text: str, hits: list[_LinkHit]) -> None:
        """Append paragraph text, rebasing its link hits into unit offsets."""
        for hit in hits:
            self.hits.append(
                _LinkHit(
                    text=hit.text,
                    start=self.length + hit.start,
                    end=self.length + hit.end,
                    href=hit.href,
                )
            )
        self.parts.append(text)
        self.length += len(text)


def _is_remote_href(href: str) -> bool:
    """True when an ``xlink:href`` targets a remote resource."""
    return href.startswith(("http://", "https://", "//"))


def _collect_text(elem: ET.Element) -> tuple[str, list[_LinkHit]]:
    """Concatenate an element's text in document order, recording links.

    The returned offsets index the returned text exactly, so block texts
    can be joined into surface text and every inline link gets a valid
    span inside it.
    """
    chunks: list[str] = []
    hits: list[_LinkHit] = []
    offset = 0

    def append(text: str | None) -> None:
        nonlocal offset
        if text:
            chunks.append(text)
            offset += len(text)

    append(elem.text)
    for child in elem:
        if not isinstance(child.tag, str):
            append(child.tail)
            continue
        if child.tag == _TAG_TEXT_A:
            text = "".join(child.itertext())
            hits.append(
                _LinkHit(
                    text=text,
                    start=offset,
                    end=offset + len(text),
                    href=str(child.get(_ATTR_XLINK_HREF) or ""),
                )
            )
            append(text)
        else:
            inner_text, inner_hits = _collect_text(child)
            for hit in inner_hits:
                hits.append(_LinkHit(hit.text, offset + hit.start, offset + hit.end, hit.href))
            append(inner_text)
        append(child.tail)
    return "".join(chunks), hits


def _macro_findings(archive: zipfile.ZipFile) -> tuple[ImportFinding, ...]:
    """Flag every archive entry that carries an ODT macro library."""
    findings: list[ImportFinding] = []
    for info in archive.infolist():
        lowered = info.filename.lower()
        if "basic/" in lowered or "scripts/" in lowered:
            findings.append(
                ImportFinding(
                    code=FindingCode.ACTIVE_CONTENT_MACRO,
                    severity=FindingSeverity.ERROR,
                    category=FindingCategory.ACTIVE_CONTENT,
                    description="ODT contains an embedded macro library",
                    evidence=evidence_name(info.filename),
                )
            )
    return tuple(findings)


def _meta_items(archive: zipfile.ZipFile, policy: ImportPolicy) -> tuple[MetadataItem, ...]:
    """Extract ``odt_meta`` items from the optional ``meta.xml`` part.

    ``meta.xml`` is an optional part: absent, unreadable, or malformed
    meta.xml yields no items and no findings.
    """
    try:
        archive.getinfo(META_PART)
    except KeyError:
        return ()
    data, _ = read_zip_entry_bounded(archive, META_PART, policy)
    root, _ = parse_xml_bounded(data, policy, META_PART)
    if root is None:
        return ()
    items: list[MetadataItem] = []
    user_defined_count = 0
    for elem in root.iter():
        value = "".join(elem.itertext())
        if elem.tag == _TAG_DC_TITLE:
            items.append(MetadataItem(key="dc:title", kind="odt_meta", value=value))
        elif elem.tag == _TAG_DC_CREATOR:
            items.append(MetadataItem(key="dc:creator", kind="odt_meta", value=value))
        elif elem.tag == _TAG_META_CREATION_DATE:
            items.append(MetadataItem(key="meta:creation-date", kind="odt_meta", value=value))
        elif elem.tag == _TAG_META_USER_DEFINED and user_defined_count < 5:
            user_defined_count += 1
            items.append(
                MetadataItem(
                    key=str(elem.get(_ATTR_META_NAME) or ""),
                    kind="odt_meta",
                    value=value,
                )
            )
    return tuple(items)


def _attach_placeholder(
    document: NodeBuilder,
    stack: list[ET.Element],
    open_builders: dict[ET.Element, NodeBuilder],
    href: str,
) -> None:
    """Attach an IMAGE_PLACEHOLDER to the innermost open container."""
    builder = NodeBuilder(node_type=NodeType.IMAGE_PLACEHOLDER, attributes={"url": href})
    _parent_of(stack, open_builders, document).add_child(builder)


def _parent_of(
    stack: list[ET.Element],
    open_builders: dict[ET.Element, NodeBuilder],
    document: NodeBuilder,
) -> NodeBuilder:
    """Return the innermost open container builder for the current element."""
    for elem in reversed(stack):
        builder = open_builders.get(elem)
        if builder is not None:
            return builder
    return document


def _nearest_unit(stack: list[ET.Element], open_units: dict[ET.Element, _Unit]) -> _Unit | None:
    """Return the innermost open list item or table cell, if any."""
    for elem in reversed(stack):
        unit = open_units.get(elem)
        if unit is not None:
            return unit
    return None


def _inside_block(stack: list[ET.Element]) -> bool:
    """True when the current element is inside a paragraph or heading."""
    return any(elem.tag in _BLOCK_TAGS for elem in stack)


def _parse_content(root: ET.Element) -> tuple[NodeBuilder, str, tuple[ImportFinding, ...]]:
    """Build the canonical tree, surface text, and findings from content.xml.

    Blocks are routed in document order; every list item and table cell
    opens a unit line at its own position, so nested blocks keep document
    order. Unit lines are emitted where their block opens (not where it
    closes), which is document order for typical bodies.
    """
    document = NodeBuilder(node_type=NodeType.DOCUMENT, source_location=SourceLocation(0, 0))
    stack: list[ET.Element] = []
    open_builders: dict[ET.Element, NodeBuilder] = {}
    open_units: dict[ET.Element, _Unit] = {}
    current_block: _Unit | None = None
    units: list[_Unit] = []
    findings: list[ImportFinding] = []

    for elem in root.iter():
        while stack and not any(child is elem for child in stack[-1]):
            closed = stack.pop()
            open_units.pop(closed, None)
            open_builders.pop(closed, None)
            if current_block is not None and current_block.element is closed:
                current_block = None
        stack.append(elem)

        href = elem.get(_ATTR_XLINK_HREF)
        if href is not None and _is_remote_href(href):
            findings.append(
                ImportFinding(
                    code=FindingCode.EXTERNAL_REMOTE_RESOURCE,
                    severity=FindingSeverity.ERROR,
                    category=FindingCategory.EXTERNAL_RELATIONSHIP,
                    description="ODT document references a remote resource",
                    evidence=scheme_host_only(href),
                )
            )

        tag = elem.tag
        if tag == _TAG_TEXT_H:
            level = elem.get(_ATTR_TEXT_OUTLINE_LEVEL) or "1"
            text, hits = _collect_text(elem)
            unit = _Unit(
                builder=NodeBuilder(node_type=NodeType.HEADING, attributes={"level": level}),
                element=elem,
                parts=[text],
                hits=hits,
                length=len(text),
            )
            _parent_of(stack, open_builders, document).add_child(unit.builder)
            _close_block(open_builders, current_block)
            current_block = unit
            open_builders[elem] = unit.builder
            units.append(unit)
        elif tag == _TAG_TEXT_P:
            text, hits = _collect_text(elem)
            container = _nearest_unit(stack, open_units)
            if container is not None:
                container.append_text(text, hits)
            else:
                unit = _Unit(
                    builder=NodeBuilder(node_type=NodeType.PARAGRAPH),
                    element=elem,
                    parts=[text],
                    hits=hits,
                    length=len(text),
                )
                document.add_child(unit.builder)
                _close_block(open_builders, current_block)
                current_block = unit
                open_builders[elem] = unit.builder
                units.append(unit)
        elif tag in {_TAG_TEXT_LIST, _TAG_TABLE, _TAG_TABLE_ROW}:
            node_type = {
                _TAG_TEXT_LIST: NodeType.LIST,
                _TAG_TABLE: NodeType.TABLE,
                _TAG_TABLE_ROW: NodeType.TABLE_ROW,
            }[tag]
            builder = NodeBuilder(node_type=node_type)
            _parent_of(stack, open_builders, document).add_child(builder)
            open_builders[elem] = builder
        elif tag in {_TAG_TEXT_LIST_ITEM, _TAG_TABLE_CELL}:
            node_type = {
                _TAG_TEXT_LIST_ITEM: NodeType.LIST_ITEM,
                _TAG_TABLE_CELL: NodeType.TABLE_CELL,
            }[tag]
            builder = NodeBuilder(node_type=node_type)
            _parent_of(stack, open_builders, document).add_child(builder)
            unit = _Unit(builder=builder, element=elem)
            open_builders[elem] = builder
            open_units[elem] = unit
            units.append(unit)
        elif tag == _TAG_DRAW_IMAGE:
            if href is not None:
                _attach_placeholder(document, stack, open_builders, href)
        elif tag == _TAG_DRAW_FRAME:
            if href is not None and elem.find(f".//{_TAG_DRAW_IMAGE}") is None:
                _attach_placeholder(document, stack, open_builders, href)
        elif tag == _TAG_TEXT_A and not _inside_block(stack):
            if href is not None:
                text = "".join(elem.itertext())
                builder = NodeBuilder(
                    node_type=NodeType.HYPERLINK, text=text, attributes={"url": href}
                )
                _parent_of(stack, open_builders, document).add_child(builder)

    # Finalize: give every unit line its exact span inside the surface text.
    line_number = 1
    offset = 0
    unit_spans: dict[int, SourceLocation] = {}
    for unit in units:
        text = unit.text
        unit.builder.text = text
        span = SourceLocation(
            offset,
            offset + len(text),
            line_number,
            line_number + text.count("\n"),
        )
        unit_spans[id(unit.builder)] = span
        unit.builder.source_location = span
        offset += len(text) + 1
        line_number += text.count("\n") + 1
    surface_text = "\n".join(unit.text for unit in units)
    document.source_location = SourceLocation(0, len(surface_text), 1, surface_text.count("\n") + 1)

    # Attach inline hyperlinks to their containing block with exact spans.
    for unit in units:
        span = unit_spans[id(unit.builder)]
        text = unit.text
        for hit in unit.hits:
            start_line = span.line_start + text[: hit.start].count("\n")
            end_line = span.line_start + text[: max(hit.end - 1, 0)].count("\n")
            unit.builder.add_child(
                NodeBuilder(
                    node_type=NodeType.HYPERLINK,
                    text=hit.text,
                    attributes={"url": hit.href},
                    source_location=SourceLocation(
                        span.start_offset + hit.start,
                        span.start_offset + hit.end,
                        start_line,
                        end_line,
                    ),
                )
            )

    _assign_container_spans(document, unit_spans)
    document_span = document.source_location
    if document_span is not None:
        _assign_image_spans(document, document_span)
    return document, surface_text, tuple(findings)


def _close_block(
    open_builders: dict[ET.Element, NodeBuilder],
    current_block: _Unit | None,
) -> None:
    """Drop a still-open block when a new block replaces it."""
    if current_block is not None:
        open_builders.pop(current_block.element, None)


def _assign_container_spans(
    node: NodeBuilder,
    unit_spans: dict[int, SourceLocation],
) -> tuple[int, int]:
    """Fill container spans as the union of descendant unit spans.

    Returns the (start, end) coverage of the node's subtree so parents can
    union their own. Nodes without any unit in their subtree keep (0, 0).
    """
    starts: list[int] = []
    ends: list[int] = []
    own = unit_spans.get(id(node))
    if own is not None:
        starts.append(own.start_offset)
        ends.append(own.end_offset)
    for child in node.children:
        child_start, child_end = _assign_container_spans(child, unit_spans)
        starts.append(child_start)
        ends.append(child_end)
    if node.source_location is None:
        node.source_location = (
            SourceLocation(min(starts), max(ends)) if starts else SourceLocation(0, 0)
        )
    location = node.source_location
    return location.start_offset, location.end_offset


def _assign_image_spans(node: NodeBuilder, parent_span: SourceLocation) -> None:
    """Give image placeholders the span of their containing block."""
    for child in node.children:
        span = child.source_location if child.source_location is not None else parent_span
        if child.node_type is NodeType.IMAGE_PLACEHOLDER:
            child.source_location = span
        _assign_image_spans(child, span)


class OdtImporter(ContainerImporter):
    """Deterministic clean-room parser for OpenDocument Text containers."""

    parser_name = "odt"
    parser_version = "1"
    supported_kinds = frozenset({FileKind.ODT})

    def parse_payloads(self, raw: bytes, policy: ImportPolicy) -> dict[str, object]:
        """Parse ODT bytes into the shared payload envelope.

        The archive is opened with the bounded helpers, so invalid or
        over-limit containers fail closed with findings and no document.
        """
        findings: list[ImportFinding] = []
        archive, open_findings = open_zip_bounded(raw, policy)
        if archive is None:
            findings.extend(open_findings)
            return self._payloads(
                policy=policy,
                raw=raw,
                surface_text="",
                root=None,
                findings=findings,
                metadata=MetadataInventory(),
                status="partial",
            )
        try:
            findings.extend(_macro_findings(archive))
            content_data, read_findings = read_zip_entry_bounded(archive, CONTENT_PART, policy)
            findings.extend(read_findings)
            content_root: ET.Element | None = None
            if not read_findings:
                content_root, xml_findings = parse_xml_bounded(content_data, policy, CONTENT_PART)
                findings.extend(xml_findings)
            if content_root is None:
                return self._payloads(
                    policy=policy,
                    raw=raw,
                    surface_text="",
                    root=None,
                    findings=findings,
                    metadata=MetadataInventory(),
                    status="partial",
                )
            root, surface_text, tree_findings = _parse_content(content_root)
            findings.extend(tree_findings)
            metadata = MetadataInventory(items=_meta_items(archive, policy))
            has_active_or_unsupported = any(
                finding.severity is FindingSeverity.ERROR and finding.category in _ACTIVE_CATEGORIES
                for finding in findings
            )
            status = "partial" if has_active_or_unsupported else "complete"
            return self._payloads(
                policy=policy,
                raw=raw,
                surface_text=surface_text,
                root=root,
                findings=findings,
                metadata=metadata,
                status=status,
            )
        finally:
            archive.close()

    def _payloads(
        self,
        *,
        policy: ImportPolicy,
        raw: bytes,
        surface_text: str,
        root: NodeBuilder | None,
        findings: list[ImportFinding],
        metadata: MetadataInventory,
        status: str,
    ) -> dict[str, object]:
        """Assemble the shared payload envelope with ODT coverage."""
        coverage = CoverageSummary(
            adapter=self.parser_name,
            supported_structures=_SUPPORTED_STRUCTURES,
            unsupported_structures=(),
            status=status,
        )
        return assemble_rich_payloads(
            raw=raw,
            policy=policy,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            surface_text=surface_text,
            root=root,
            findings=findings,
            coverage=coverage,
            metadata=metadata,
            active=(),
        )
