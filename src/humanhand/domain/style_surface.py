"""Exact surface representation for style evidence.

The surface view preserves exact code points, structure statistics, and a
link back to the immutable original artifact — it is never normalized or
scrubbed (ADR-003).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from humanhand.domain.canonical_document import CanonicalDocument
from humanhand.domain.document_nodes import NodeType


@dataclass(frozen=True)
class SurfaceStatistics:
    """Deterministic structural statistics of the surface view."""

    code_points: int
    bytes_utf8: int
    lines: int
    paragraphs: int
    headings: int
    list_items: int
    table_cells: int
    quotations: int
    code_blocks: int
    hyperlinks: int


@dataclass(frozen=True)
class CanonicalSurfaceDocument:
    """Exact surface of a style sample, tied to its immutable original."""

    artifact_id: str
    surface_text: str
    sha256: str
    statistics: SurfaceStatistics
    node_count: int

    @property
    def code_point_count(self) -> int:
        return self.statistics.code_points


def surface_statistics(document: CanonicalDocument) -> SurfaceStatistics:
    """Count structural nodes deterministically."""
    counts: dict[NodeType, int] = dict.fromkeys(NodeType, 0)
    for node in document.nodes:
        counts[node.node_type] += 1
    return SurfaceStatistics(
        code_points=len(document.surface_text),
        bytes_utf8=len(document.surface_text.encode("utf-8")),
        lines=document.surface_text.count("\n") + 1,
        paragraphs=counts[NodeType.PARAGRAPH],
        headings=counts[NodeType.HEADING],
        list_items=counts[NodeType.LIST_ITEM],
        table_cells=counts[NodeType.TABLE_CELL],
        quotations=counts[NodeType.QUOTATION],
        code_blocks=counts[NodeType.CODE_BLOCK],
        hyperlinks=counts[NodeType.HYPERLINK],
    )


def build_surface_document(
    *, artifact_id: str, document: CanonicalDocument
) -> CanonicalSurfaceDocument:
    """Build the exact surface for a style document."""
    digest = hashlib.sha256(document.surface_text.encode("utf-8")).hexdigest()
    return CanonicalSurfaceDocument(
        artifact_id=artifact_id,
        surface_text=document.surface_text,
        sha256=digest,
        statistics=surface_statistics(document),
        node_count=len(document.nodes),
    )
