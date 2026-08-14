"""Deterministically apply reviewed lexical changes to a canonical document.

The transform is intentionally narrow: accepted lexical changes may touch only
exactly represented editable text nodes. Headings, quotations, citations,
code, and ambiguous/overlapping spans fail closed. Empty structural parent
nodes may overlap a change and receive shifted offsets, but never synthesize
text. Node ids and macro structure remain unchanged.
"""

from __future__ import annotations

import unicodedata
from dataclasses import replace

from humanhand.domain.canonical_document import CanonicalDocument
from humanhand.domain.document_nodes import DocumentNode, NodeType, SourceLocation
from humanhand.domain.lexical_normalizer import LexicalChange, LexicalProposal, apply_changes
from humanhand.domain.types import DomainError

_EDITABLE_NODE_TYPES = frozenset(
    {
        NodeType.PARAGRAPH,
        NodeType.SENTENCE,
        NodeType.TEXT_RUN,
        NodeType.LIST_ITEM,
        NodeType.TABLE_CELL,
    }
)
_PROTECTED_TEXT_NODE_TYPES = frozenset(
    {
        NodeType.HEADING,
        NodeType.QUOTATION,
        NodeType.CITATION,
        NodeType.FOOTNOTE,
        NodeType.ENDNOTE,
        NodeType.CODE_BLOCK,
        NodeType.HYPERLINK,
    }
)


def _ordered_changes(proposal: LexicalProposal) -> tuple[LexicalChange, ...]:
    changes = tuple(sorted(proposal.changes, key=lambda item: (item.offset, item.length)))
    previous_end = -1
    for change in changes:
        if "\n" in change.source_surface or "\r" in change.source_surface:
            raise DomainError(f"Change {change.change_id} crosses a line boundary")
        if "\n" in change.target or "\r" in change.target:
            raise DomainError(f"Change {change.change_id} introduces a line boundary")
        if change.offset < previous_end:
            raise DomainError("Lexical proposal contains overlapping changes")
        previous_end = change.offset + change.length
    return changes


def _shifted_offset(offset: int, changes: tuple[LexicalChange, ...]) -> int:
    """Translate one original offset after all changes ending at/before it."""
    shift = 0
    for change in changes:
        if change.offset + change.length <= offset:
            shift += len(change.target) - change.length
    return offset + shift


def _changes_inside(
    start: int, end: int, changes: tuple[LexicalChange, ...]
) -> tuple[LexicalChange, ...]:
    inside: list[LexicalChange] = []
    for change in changes:
        change_end = change.offset + change.length
        overlaps = change.offset < end and start < change_end
        if not overlaps:
            continue
        if change.offset < start or change_end > end:
            raise DomainError(f"Change {change.change_id} crosses a canonical node boundary")
        inside.append(change)
    return tuple(inside)


def _apply_node_changes(
    node: DocumentNode,
    document: CanonicalDocument,
    changes: tuple[LexicalChange, ...],
) -> tuple[DocumentNode, tuple[str, ...]]:
    location = node.source_location
    start = location.start_offset
    end = location.end_offset
    node_changes = _changes_inside(start, end, changes)

    if node_changes and node.text and node.node_type in _PROTECTED_TEXT_NODE_TYPES:
        raise DomainError(
            f"Lexical change touches protected canonical node "
            f"{node.node_id}:{node.node_type.value}"
        )
    if node_changes and node.text and node.node_type not in _EDITABLE_NODE_TYPES:
        raise DomainError(
            f"Lexical change touches unsupported canonical node "
            f"{node.node_id}:{node.node_type.value}"
        )

    new_text = node.text
    covered: tuple[str, ...] = ()
    if node_changes and node.text:
        if start < 0 or end > len(document.surface_text) or end < start:
            raise DomainError(f"Canonical node {node.node_id} has invalid source offsets")
        if document.surface_text[start:end] != node.text:
            raise DomainError(
                f"Canonical node {node.node_id} is not an exact surface span and cannot be edited"
            )
        working = node.text
        for change in sorted(node_changes, key=lambda item: item.offset, reverse=True):
            local_offset = change.offset - start
            if working[local_offset : local_offset + change.length] != change.source_surface:
                raise DomainError(f"Change {change.change_id} does not match canonical node text")
            working = (
                working[:local_offset]
                + change.target
                + working[local_offset + change.length :]
            )
        new_text = working
        covered = tuple(change.change_id for change in node_changes)

    # _shifted_offset(end) already includes every delta for changes contained
    # in this node, so no second node-local delta is applied here.
    new_start = _shifted_offset(start, changes)
    new_end = _shifted_offset(end, changes)
    return (
        replace(
            node,
            text=new_text,
            source_location=SourceLocation(
                start_offset=new_start,
                end_offset=new_end,
                line_start=location.line_start,
                line_end=location.line_end,
            ),
        ),
        covered,
    )


def apply_reviewed_proposal(
    document: CanonicalDocument, proposal: LexicalProposal
) -> CanonicalDocument:
    """Return a new canonical document with every reviewed change applied.

    ``proposal`` must contain only explicitly accepted changes (normally the
    result of :func:`humanhand.domain.lexical_review.apply_review`). The
    proposal hash is verified by :func:`apply_changes`; every change must map
    to at least one exactly represented editable text node. Structure and node
    ids remain stable while source offsets and affected node texts are updated.
    """
    changes = _ordered_changes(proposal)
    new_surface = apply_changes(document.surface_text, proposal)
    covered_change_ids: set[str] = set()
    new_nodes: list[DocumentNode] = []
    for node in document.nodes:
        transformed, covered = _apply_node_changes(node, document, changes)
        covered_change_ids.update(covered)
        new_nodes.append(transformed)
    expected_ids = {change.change_id for change in changes}
    if covered_change_ids != expected_ids:
        missing = sorted(expected_ids - covered_change_ids)
        raise DomainError(
            "Lexical changes are not covered by exact editable nodes: " + ",".join(missing)
        )
    transformed = replace(
        document,
        surface_text=new_surface,
        canonical_text=unicodedata.normalize("NFC", new_surface),
        nodes=tuple(new_nodes),
    )
    for node in transformed.nodes:
        location = node.source_location
        if (
            node.node_type in _EDITABLE_NODE_TYPES
            and node.text
            and transformed.surface_text[location.start_offset : location.end_offset] != node.text
        ):
            raise DomainError(
                f"Transformed canonical node {node.node_id} failed surface-span validation"
            )
    return transformed
