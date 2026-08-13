"""Deterministic structural digest of a canonical document (EP-015).

The signature is a pure function of the canonical document: node types in
document order, exact heading texts, and the paragraph count. No wall
clock, no randomness, no parser state; equal documents always produce
byte-identical signatures.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass

from humanhand.domain.canonical_document import CanonicalDocument
from humanhand.domain.document_nodes import NodeType

STRUCTURE_SIGNATURE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class StructureSignature:
    """Deterministic structural digest of a canonical document."""

    signature: str  # hex sha256 digest
    section_order: tuple[str, ...]  # heading texts in order (exact)
    node_type_counts: dict[str, int]  # sorted keys
    total_nodes: int


def compute_structure_signature(document: CanonicalDocument) -> StructureSignature:
    """Compute the deterministic structural digest of a canonical document.

    The digest covers, in this order: the schema version, every node type
    value in document order, the exact text of every HEADING node, and the
    total paragraph count. NUL bytes separate the framed parts so the
    encoding cannot be ambiguous. ``section_order`` holds the exact heading
    texts in document order, ``node_type_counts`` maps node type values to
    counts with sorted keys, and ``total_nodes`` is the raw node count.
    """
    digest = hashlib.sha256()
    digest.update(f"structure-signature-v{STRUCTURE_SIGNATURE_SCHEMA_VERSION}".encode())
    digest.update(b"\x00")
    headings: list[str] = []
    counts: Counter[str] = Counter()
    paragraph_count = 0
    for node in document.nodes:
        counts[node.node_type.value] += 1
        digest.update(node.node_type.value.encode("utf-8"))
        digest.update(b"\x00")
        if node.node_type is NodeType.HEADING:
            headings.append(node.text)
            digest.update(node.text.encode("utf-8"))
            digest.update(b"\x00")
        if node.node_type is NodeType.PARAGRAPH:
            paragraph_count += 1
    digest.update(f"paragraphs={paragraph_count}".encode())
    return StructureSignature(
        signature=digest.hexdigest(),
        section_order=tuple(headings),
        node_type_counts=dict(sorted(counts.items())),
        total_nodes=len(document.nodes),
    )


def signatures_equal(a: StructureSignature, b: StructureSignature) -> bool:
    """Return True when two signatures agree on every field.

    The digest alone would suffice (it covers the other three fields), but
    comparing every field is stricter and fails on accidental digest
    collisions instead of silently passing.
    """
    return (
        a.signature == b.signature
        and a.section_order == b.section_order
        and a.node_type_counts == b.node_type_counts
        and a.total_nodes == b.total_nodes
    )
