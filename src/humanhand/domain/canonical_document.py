"""Canonical document, import inspection, and deterministic construction."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from humanhand.domain.active_content import ActiveContentFinding
from humanhand.domain.document_nodes import DocumentNode, NodeBuilder, NodeType, SourceLocation
from humanhand.domain.file_identity import FileIdentity
from humanhand.domain.import_findings import ImportFinding, ImportStatus, classify_status
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.metadata_inventory import MetadataInventory
from humanhand.domain.types import DomainError
from humanhand.domain.unicode_policy import UnicodeInventory, canonical_text_view

CANONICAL_DOCUMENT_SCHEMA_VERSION = 1
IMPORT_INSPECTION_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CoverageSummary:
    """Which structures an adapter recognized and which it did not."""

    adapter: str
    supported_structures: tuple[str, ...]
    unsupported_structures: tuple[str, ...]
    status: str  # "complete" | "partial" | "unsupported_format"


@dataclass(frozen=True)
class ResourceMeasurements:
    """Measured resource usage for one import (metadata channel)."""

    size_bytes: int
    expanded_bytes: int
    node_count: int
    tree_depth: int
    duration_ms: int | None = None
    peak_memory_bytes: int | None = None

    def to_payload(self) -> dict[str, object]:
        """Render the measurements as a plain JSON-ready mapping."""
        return {
            "duration_ms": self.duration_ms,
            "expanded_bytes": self.expanded_bytes,
            "node_count": self.node_count,
            "peak_memory_bytes": self.peak_memory_bytes,
            "size_bytes": self.size_bytes,
            "tree_depth": self.tree_depth,
        }


@dataclass(frozen=True)
class CanonicalDocument:
    """Deterministic canonical evidence for one imported document.

    Equal input bytes, parser name/version, policy version, lane, and
    revision policy produce a byte-identical canonical JSON rendering
    (see ``document_serialization``). Note: ``derive_import_id`` hashes
    raw bytes, lane, parser name/version, and the policy version only; the
    revision policy is carried in the document body, not the digest.
    """

    schema_version: int
    lane: str
    parser_name: str
    parser_version: str
    policy_version: str
    revision_policy: str
    surface_text: str
    canonical_text: str
    nodes: tuple[DocumentNode, ...]
    findings: tuple[ImportFinding, ...]

    @property
    def root(self) -> DocumentNode:
        if not self.nodes or self.nodes[0].node_type is not NodeType.DOCUMENT:
            raise DomainError("Canonical document has no DOCUMENT root node")
        return self.nodes[0]

    def node_by_id(self, node_id: str) -> DocumentNode:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        raise KeyError(node_id)

    def to_payload(self) -> dict[str, object]:
        # Imported here to avoid a circular import at module load time.
        from humanhand.domain.document_serialization import document_to_payload

        return document_to_payload(self)


def _node_span(builder: NodeBuilder) -> SourceLocation:
    if builder.source_location is not None:
        return builder.source_location
    return SourceLocation(start_offset=0, end_offset=0)


def _wrap_nodes(
    builder: NodeBuilder,
    parent_id: str | None,
    position: int,
    id_counter: list[int],
    *,
    depth: int,
) -> tuple[DocumentNode, ...]:
    """Depth-first, pre-order wrap of a builder tree into frozen nodes."""
    id_counter[0] += 1
    node_id = f"n{id_counter[0]}"
    wrapped = DocumentNode(
        node_id=node_id,
        parent_id=parent_id,
        node_type=builder.node_type,
        position=position,
        source_location=_node_span(builder),
        text=builder.text,
        attributes=dict(builder.attributes or {}),
        authorship_class=builder.authorship_class,
        protected_span_refs=builder.protected_span_refs,
        finding_codes=builder.finding_codes,
    )
    nodes = [wrapped]
    child_depth = depth + 1
    for index, child in enumerate(builder.children, start=1):
        nodes.extend(
            _wrap_nodes(
                child,
                parent_id=node_id,
                position=index,
                id_counter=id_counter,
                depth=child_depth,
            )
        )
    return tuple(nodes)


def build_document(
    *,
    root: NodeBuilder,
    lane: str,
    parser_name: str,
    parser_version: str,
    policy: ImportPolicy,
    surface_text: str,
    findings: tuple[ImportFinding, ...] = (),
) -> CanonicalDocument:
    """Assign deterministic ids/positions and build a CanonicalDocument.

    Raises DomainError when the tree has no DOCUMENT root or exceeds the
    policy node limit.
    """
    if root.node_type is not NodeType.DOCUMENT:
        raise DomainError("Root builder must have node_type DOCUMENT")
    id_counter = [0]
    nodes = _wrap_nodes(root, parent_id=None, position=1, id_counter=id_counter, depth=0)
    if len(nodes) > policy.max_nodes:
        raise DomainError(
            f"Document has {len(nodes)} nodes, exceeding policy limit {policy.max_nodes}"
        )
    return CanonicalDocument(
        schema_version=CANONICAL_DOCUMENT_SCHEMA_VERSION,
        lane=lane,
        parser_name=parser_name,
        parser_version=parser_version,
        policy_version=policy.version,
        revision_policy=policy.revision_policy,
        surface_text=surface_text,
        canonical_text=canonical_text_view(surface_text),
        nodes=nodes,
        findings=findings,
    )


def measure_document(document: CanonicalDocument | None, size_bytes: int) -> ResourceMeasurements:
    """Measure a built document's resources deterministically."""
    if document is None or not document.nodes:
        return ResourceMeasurements(
            size_bytes=size_bytes,
            expanded_bytes=size_bytes,
            node_count=0,
            tree_depth=0,
        )
    parent_by_id: dict[str, str | None] = {node.node_id: node.parent_id for node in document.nodes}
    depth = 0
    for node in document.nodes:
        chain = 1
        parent_id = node.parent_id
        while parent_id is not None:
            chain += 1
            parent_id = parent_by_id.get(parent_id)
        depth = max(depth, chain)
    return ResourceMeasurements(
        size_bytes=size_bytes,
        expanded_bytes=len(document.surface_text.encode("utf-8")),
        node_count=len(document.nodes),
        tree_depth=depth,
    )


@dataclass(frozen=True)
class ImportInspection:
    """Result of a clean-room import inspection (metadata channel).

    ``document`` carries canonical content and is optional so callers can
    keep content out of results unless explicitly requested.
    """

    schema_version: int
    import_id: str
    lane: str
    status: ImportStatus
    file_identity: FileIdentity
    findings: tuple[ImportFinding, ...]
    coverage: CoverageSummary
    metadata: MetadataInventory = field(default_factory=MetadataInventory)
    unicode: UnicodeInventory | None = None
    active_content: tuple[ActiveContentFinding, ...] = ()
    measurements: ResourceMeasurements | None = None
    document: CanonicalDocument | None = None

    def to_payload(self, *, include_content: bool = False) -> dict[str, object]:
        # Imported here to avoid a circular import at module load time.
        from humanhand.domain.document_serialization import inspection_to_payload

        return inspection_to_payload(self, include_content=include_content)

    def to_json(self, *, include_content: bool = False) -> str:
        from humanhand.domain.document_serialization import inspection_to_json

        return inspection_to_json(self, include_content=include_content)


def derive_import_id(
    *,
    raw: bytes,
    lane: str,
    parser_name: str,
    parser_version: str,
    policy: ImportPolicy,
) -> str:
    """Derive a stable import id from content bytes and versions.

    Only a digest is produced; raw bytes are never retained by this function.
    """
    digest = hashlib.sha256()
    digest.update(raw)
    digest.update(b"\x00")
    digest.update(lane.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(parser_name.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(parser_version.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(policy.version.encode("utf-8"))
    return f"import-{digest.hexdigest()[:32]}"


def make_inspection(
    *,
    raw: bytes,
    identity: FileIdentity,
    lane: str,
    parser_name: str,
    parser_version: str,
    policy: ImportPolicy,
    findings: tuple[ImportFinding, ...],
    coverage: CoverageSummary,
    metadata: MetadataInventory | None = None,
    unicode_inventory: UnicodeInventory | None = None,
    active_content: tuple[ActiveContentFinding, ...] = (),
    measurements: ResourceMeasurements | None = None,
    document: CanonicalDocument | None = None,
    status_override: ImportStatus | None = None,
) -> ImportInspection:
    """Assemble an ImportInspection with status derived from findings."""
    status = status_override if status_override is not None else classify_status(findings)
    return ImportInspection(
        schema_version=IMPORT_INSPECTION_SCHEMA_VERSION,
        import_id=derive_import_id(
            raw=raw,
            lane=lane,
            parser_name=parser_name,
            parser_version=parser_version,
            policy=policy,
        ),
        lane=lane,
        status=status,
        file_identity=identity,
        findings=findings,
        coverage=coverage,
        metadata=metadata if metadata is not None else MetadataInventory(),
        unicode=unicode_inventory,
        active_content=active_content,
        measurements=measurements,
        document=document,
    )
