"""Canonical document node model — typed structural nodes and exact source spans."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class NodeType(StrEnum):
    """Deterministic structural node kinds for canonical documents."""

    DOCUMENT = "document"
    SECTION = "section"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    SENTENCE = "sentence"
    TEXT_RUN = "text_run"
    LIST = "list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    TABLE_ROW = "table_row"
    TABLE_CELL = "table_cell"
    QUOTATION = "quotation"
    CITATION = "citation"
    FOOTNOTE = "footnote"
    ENDNOTE = "endnote"
    CODE_BLOCK = "code_block"
    HYPERLINK = "hyperlink"
    PAGE_BREAK = "page_break"
    SECTION_BREAK = "section_break"
    IMAGE_PLACEHOLDER = "image_placeholder"


@dataclass(frozen=True)
class SourceLocation:
    """Exact span of a node inside the source surface text.

    Offsets are character offsets into the decoded surface text.
    Line numbers are 1-based.
    """

    start_offset: int
    end_offset: int
    line_start: int = 1
    line_end: int = 1


@dataclass(frozen=True)
class DocumentNode:
    """One immutable node in a canonical document tree.

    Nodes carry no public export IDs by default; ``node_id`` values are
    deterministic document-local identifiers assigned by
    :func:`humanhand.domain.canonical_document.build_document`.
    """

    node_id: str
    parent_id: str | None
    node_type: NodeType
    position: int
    source_location: SourceLocation
    text: str = ""
    attributes: dict[str, str] = field(default_factory=dict)
    authorship_class: str | None = None
    protected_span_refs: tuple[str, ...] = ()
    finding_codes: tuple[str, ...] = ()


@dataclass
class NodeBuilder:
    """Mutable assembly tree used before deterministic id assignment.

    Parsers build a ``NodeBuilder`` tree and pass the root to
    ``build_document``, which assigns stable ids and positions and returns an
    immutable :class:`CanonicalDocument`.
    """

    node_type: NodeType
    text: str = ""
    attributes: dict[str, str] | None = None
    source_location: SourceLocation | None = None
    authorship_class: str | None = None
    protected_span_refs: tuple[str, ...] = ()
    finding_codes: tuple[str, ...] = ()
    children: list[NodeBuilder] = field(default_factory=list)

    def add_child(self, child: NodeBuilder) -> NodeBuilder:
        """Append a child builder and return it for chaining."""
        self.children.append(child)
        return child
