"""Deterministic canonical JSON serialization for documents and inspections."""

from __future__ import annotations

import json
from typing import Any

from humanhand.domain.active_content import ActiveContentFinding
from humanhand.domain.canonical_document import (
    CANONICAL_DOCUMENT_SCHEMA_VERSION,
    IMPORT_INSPECTION_SCHEMA_VERSION,
    CanonicalDocument,
    CoverageSummary,
    ImportInspection,
    ResourceMeasurements,
)
from humanhand.domain.document_nodes import DocumentNode, NodeType, SourceLocation
from humanhand.domain.file_identity import FileIdentity
from humanhand.domain.import_findings import (
    FindingCategory,
    FindingSeverity,
    ImportFinding,
    ImportStatus,
)
from humanhand.domain.metadata_inventory import MetadataInventory
from humanhand.domain.types import DomainError
from humanhand.domain.unicode_policy import canonical_text_view

# Stable key order is guaranteed by sort_keys=True in every rendering path.
_JSON_KWARGS: dict[str, Any] = {
    "ensure_ascii": False,
    "separators": (",", ":"),
    "sort_keys": True,
}


def dumps_stable(payload: dict[str, object]) -> str:
    """Render a payload as deterministic UTF-8 JSON with one trailing newline."""
    return json.dumps(payload, **_JSON_KWARGS) + "\n"


def _location_payload(location: SourceLocation) -> dict[str, int]:
    return {
        "end_offset": location.end_offset,
        "line_end": location.line_end,
        "line_start": location.line_start,
        "start_offset": location.start_offset,
    }


def _node_payload(node: DocumentNode) -> dict[str, object]:
    return {
        "attributes": dict(node.attributes),
        "authorship_class": node.authorship_class,
        "finding_codes": list(node.finding_codes),
        "id": node.node_id,
        "parent_id": node.parent_id,
        "position": node.position,
        "protected_span_refs": list(node.protected_span_refs),
        "source_location": _location_payload(node.source_location),
        "text": node.text,
        "text_canonical": canonical_text_view(node.text),
        "type": node.node_type.value,
    }


def finding_to_payload(finding: ImportFinding) -> dict[str, object]:
    """Render one finding as a stable JSON-ready mapping."""
    location = _location_payload(finding.location) if finding.location is not None else None
    return {
        "category": finding.category.value,
        "code": finding.code,
        "description": finding.description,
        "evidence": finding.evidence,
        "location": location,
        "severity": finding.severity.value,
    }


def document_to_payload(document: CanonicalDocument) -> dict[str, object]:
    """Render a canonical document as its stable JSON payload."""
    return {
        "canonical_text": document.canonical_text,
        "findings": [finding_to_payload(finding) for finding in document.findings],
        "lane": document.lane,
        "nodes": [_node_payload(node) for node in document.nodes],
        "parser": {
            "name": document.parser_name,
            "version": document.parser_version,
        },
        "policy_version": document.policy_version,
        "revision_policy": document.revision_policy,
        "schema": "canonical-document",
        "schema_version": document.schema_version,
        "surface_text": document.surface_text,
    }


def document_to_json(document: CanonicalDocument) -> str:
    """Serialize a canonical document deterministically.

    Equal inputs (bytes, parser, policy, lane, revision policy) always
    produce byte-identical output, including key order.
    """
    return dumps_stable(document_to_payload(document))


def _expect_mapping(payload: dict[str, object], key: str, what: str) -> dict[str, object]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise DomainError(f"Invalid canonical document JSON: {what} must be an object")
    return value


def _expect_string(payload: dict[str, object], key: str, what: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise DomainError(f"Invalid canonical document JSON: {what} must be a string")
    return value


def _expect_int(payload: dict[str, object], key: str, what: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise DomainError(f"Invalid canonical document JSON: {what} must be an integer")
    return value


def _coverage_string_list(payload: dict[str, object], key: str) -> tuple[str, ...]:
    raw_structures = payload.get(key) or []
    if not isinstance(raw_structures, list):
        raise DomainError(f"Invalid import inspection JSON: coverage.{key} must be a list")
    return tuple(str(item) for item in raw_structures)


def _location_from_payload(payload: dict[str, object], what: str) -> SourceLocation:
    return SourceLocation(
        start_offset=_expect_int(payload, "start_offset", f"{what}.start_offset"),
        end_offset=_expect_int(payload, "end_offset", f"{what}.end_offset"),
        line_start=_expect_int(payload, "line_start", f"{what}.line_start"),
        line_end=_expect_int(payload, "line_end", f"{what}.line_end"),
    )


def _node_from_payload(payload: dict[str, object], what: str) -> DocumentNode:
    node_type_value = _expect_string(payload, "type", f"{what}.type")
    try:
        node_type = NodeType(node_type_value)
    except ValueError as exc:
        raise DomainError(
            f"Invalid canonical document JSON: unknown node type {node_type_value!r}"
        ) from exc
    parent_id_value = payload.get("parent_id")
    if parent_id_value is not None and not isinstance(parent_id_value, str):
        raise DomainError(
            f"Invalid canonical document JSON: {what}.parent_id must be a string or null"
        )
    location_payload = _expect_mapping(payload, "source_location", f"{what}.source_location")
    attributes_payload = _expect_mapping(payload, "attributes", f"{what}.attributes")
    attributes = {str(key): str(value) for key, value in attributes_payload.items()}
    protected_refs = payload.get("protected_span_refs") or []
    if not isinstance(protected_refs, list):
        raise DomainError(
            f"Invalid canonical document JSON: {what}.protected_span_refs must be a list"
        )
    finding_codes = payload.get("finding_codes") or []
    if not isinstance(finding_codes, list):
        raise DomainError(f"Invalid canonical document JSON: {what}.finding_codes must be a list")
    authorship = payload.get("authorship_class")
    if authorship is not None and not isinstance(authorship, str):
        raise DomainError(
            f"Invalid canonical document JSON: {what}.authorship_class must be a string or null"
        )
    return DocumentNode(
        node_id=_expect_string(payload, "id", f"{what}.id"),
        parent_id=parent_id_value,
        node_type=node_type,
        position=_expect_int(payload, "position", f"{what}.position"),
        source_location=_location_from_payload(location_payload, what),
        text=_expect_string(payload, "text", f"{what}.text"),
        attributes=attributes,
        authorship_class=authorship,
        protected_span_refs=tuple(str(ref) for ref in protected_refs),
        finding_codes=tuple(str(code) for code in finding_codes),
    )


def finding_from_payload(payload: dict[str, object], what: str = "finding") -> ImportFinding:
    """Deserialize and validate one finding payload (public wrapper)."""
    return _finding_from_payload(payload, what)


def _finding_from_payload(payload: dict[str, object], what: str) -> ImportFinding:
    try:
        severity = FindingSeverity(_expect_string(payload, "severity", f"{what}.severity"))
        category = FindingCategory(_expect_string(payload, "category", f"{what}.category"))
    except ValueError as exc:
        raise DomainError(
            f"Invalid canonical document JSON: {what} has unknown enum value"
        ) from exc
    location_payload = payload.get("location")
    location = None
    if location_payload is not None:
        if not isinstance(location_payload, dict):
            raise DomainError(
                f"Invalid canonical document JSON: {what}.location must be an object or null"
            )
        location = _location_from_payload(location_payload, what)
    return ImportFinding(
        code=_expect_string(payload, "code", f"{what}.code"),
        severity=severity,
        category=category,
        description=_expect_string(payload, "description", f"{what}.description"),
        location=location,
        evidence=_expect_string(payload, "evidence", f"{what}.evidence"),
    )


def document_from_json(text: str) -> CanonicalDocument:
    """Deserialize and validate a canonical document JSON string."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DomainError("Invalid canonical document JSON: not valid JSON") from exc
    if not isinstance(payload, dict):
        raise DomainError("Invalid canonical document JSON: top level must be an object")
    if payload.get("schema") != "canonical-document":
        raise DomainError("Invalid canonical document JSON: schema must be 'canonical-document'")
    schema_version = _expect_int(payload, "schema_version", "schema_version")
    if schema_version != CANONICAL_DOCUMENT_SCHEMA_VERSION:
        raise DomainError(f"Unsupported canonical document schema version: {schema_version}")
    parser_payload = _expect_mapping(payload, "parser", "parser")
    raw_nodes = payload.get("nodes")
    if not isinstance(raw_nodes, list):
        raise DomainError("Invalid canonical document JSON: nodes must be a list")
    nodes = tuple(
        _node_from_payload(item, f"nodes[{index}]")
        for index, item in enumerate(raw_nodes)
        if isinstance(item, dict)
    )
    if len(nodes) != len(raw_nodes):
        raise DomainError("Invalid canonical document JSON: nodes must contain only objects")
    raw_findings = payload.get("findings") or []
    if not isinstance(raw_findings, list):
        raise DomainError("Invalid canonical document JSON: findings must be a list")
    findings = tuple(
        _finding_from_payload(item, f"findings[{index}]")
        for index, item in enumerate(raw_findings)
        if isinstance(item, dict)
    )
    if len(findings) != len(raw_findings):
        raise DomainError("Invalid canonical document JSON: findings must contain only objects")
    document = CanonicalDocument(
        schema_version=schema_version,
        lane=_expect_string(payload, "lane", "lane"),
        parser_name=_expect_string(parser_payload, "name", "parser.name"),
        parser_version=_expect_string(parser_payload, "version", "parser.version"),
        policy_version=_expect_string(payload, "policy_version", "policy_version"),
        revision_policy=_expect_string(payload, "revision_policy", "revision_policy"),
        surface_text=_expect_string(payload, "surface_text", "surface_text"),
        canonical_text=_expect_string(payload, "canonical_text", "canonical_text"),
        nodes=nodes,
        findings=findings,
    )
    # Structural validation: single DOCUMENT root and valid parent references.
    root = document.root
    ids = {node.node_id for node in nodes}
    if len(ids) != len(nodes):
        raise DomainError("Invalid canonical document JSON: duplicate node ids")
    if root.parent_id is not None:
        raise DomainError("Invalid canonical document JSON: root node must have null parent_id")
    for node in nodes[1:]:
        if node.parent_id is None or node.parent_id not in ids:
            raise DomainError(
                f"Invalid canonical document JSON: node {node.node_id} has invalid parent_id"
            )
    return document


def _identity_payload(identity: FileIdentity) -> dict[str, object]:
    return {
        "declared_kind": identity.declared_kind.value,
        "extension": identity.extension,
        "given_path": identity.given_path,
        "magic": {
            "description": identity.magic.description,
            "is_container": identity.magic.is_container,
            "kind": identity.magic.kind.value,
            "matched": identity.magic.matched,
        },
        "size_bytes": identity.size_bytes,
    }


def _metadata_payload(metadata: MetadataInventory, *, include_content: bool) -> dict[str, object]:
    return {
        "count": len(metadata.items),
        "items": [
            {
                "key": item.key,
                "kind": item.kind,
                "value": item.value if include_content else None,
            }
            for item in metadata.items
        ],
    }


def _coverage_payload(coverage: CoverageSummary) -> dict[str, object]:
    return {
        "adapter": coverage.adapter,
        "status": coverage.status,
        "supported_structures": list(coverage.supported_structures),
        "unsupported_structures": list(coverage.unsupported_structures),
    }


def _active_content_payload(item: ActiveContentFinding) -> dict[str, object]:
    return {
        "description": item.description,
        "evidence": item.evidence,
        "kind": item.kind.value,
        "offset": item.offset,
    }


def _measurements_payload(measurements: ResourceMeasurements | None) -> dict[str, object] | None:
    if measurements is None:
        return None
    return {
        "duration_ms": measurements.duration_ms,
        "expanded_bytes": measurements.expanded_bytes,
        "node_count": measurements.node_count,
        "peak_memory_bytes": measurements.peak_memory_bytes,
        "size_bytes": measurements.size_bytes,
        "tree_depth": measurements.tree_depth,
    }


def inspection_to_payload(
    inspection: ImportInspection, *, include_content: bool = False
) -> dict[str, object]:
    """Render an import inspection as its stable JSON payload.

    ``include_content`` controls whether the canonical document body is
    embedded. Content is opt-in and off by default.
    """
    payload: dict[str, object] = {
        "active_content": [_active_content_payload(item) for item in inspection.active_content],
        "coverage": _coverage_payload(inspection.coverage),
        "file_identity": _identity_payload(inspection.file_identity),
        "findings": [finding_to_payload(finding) for finding in inspection.findings],
        "import_id": inspection.import_id,
        "lane": inspection.lane,
        "measurements": _measurements_payload(inspection.measurements),
        # Metadata values can be arbitrary document text, so values follow
        # the same content opt-in as the canonical document body.
        "metadata": _metadata_payload(inspection.metadata, include_content=include_content),
        "schema": "import-inspection",
        "schema_version": inspection.schema_version,
        "status": inspection.status.value,
        "unicode": inspection.unicode.to_payload() if inspection.unicode is not None else None,
    }
    if include_content and inspection.document is not None:
        payload["document"] = document_to_payload(inspection.document)
    else:
        payload["document"] = None
    return payload


def inspection_to_json(inspection: ImportInspection, *, include_content: bool = False) -> str:
    """Serialize an import inspection deterministically."""
    return dumps_stable(inspection_to_payload(inspection, include_content=include_content))


def inspection_from_json(text: str) -> ImportInspection:
    """Deserialize and validate an import inspection JSON string."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DomainError("Invalid import inspection JSON: not valid JSON") from exc
    if not isinstance(payload, dict):
        raise DomainError("Invalid import inspection JSON: top level must be an object")
    if payload.get("schema") != "import-inspection":
        raise DomainError("Invalid import inspection JSON: schema must be 'import-inspection'")
    schema_version = _expect_int(payload, "schema_version", "schema_version")
    if schema_version != IMPORT_INSPECTION_SCHEMA_VERSION:
        raise DomainError(f"Unsupported import inspection schema version: {schema_version}")
    identity_payload = _expect_mapping(payload, "file_identity", "file_identity")
    magic_payload = _expect_mapping(identity_payload, "magic", "file_identity.magic")
    from humanhand.domain.file_identity import FileKind, MagicSignature

    try:
        declared_kind = FileKind(
            _expect_string(identity_payload, "declared_kind", "file_identity.declared_kind")
        )
        magic_kind = FileKind(_expect_string(magic_payload, "kind", "file_identity.magic.kind"))
        status = ImportStatus(_expect_string(payload, "status", "status"))
    except ValueError as exc:
        raise DomainError("Invalid import inspection JSON: unknown enum value") from exc
    raw_findings = payload.get("findings") or []
    if not isinstance(raw_findings, list):
        raise DomainError("Invalid import inspection JSON: findings must be a list")
    findings = tuple(
        _finding_from_payload(item, f"findings[{index}]")
        for index, item in enumerate(raw_findings)
        if isinstance(item, dict)
    )
    if len(findings) != len(raw_findings):
        raise DomainError("Invalid import inspection JSON: findings must contain only objects")
    coverage_payload = _expect_mapping(payload, "coverage", "coverage")
    document_payload = payload.get("document")
    document = None
    if document_payload is not None:
        if not isinstance(document_payload, dict):
            raise DomainError("Invalid import inspection JSON: document must be an object or null")
        document = document_from_json(json.dumps(document_payload, **_JSON_KWARGS))
    identity = FileIdentity(
        given_path=_expect_string(identity_payload, "given_path", "file_identity.given_path"),
        extension=_expect_string(identity_payload, "extension", "file_identity.extension"),
        size_bytes=_expect_int(identity_payload, "size_bytes", "file_identity.size_bytes"),
        declared_kind=declared_kind,
        magic=MagicSignature(
            kind=magic_kind,
            matched=bool(magic_payload.get("matched", False)),
            description=_expect_string(
                magic_payload, "description", "file_identity.magic.description"
            ),
            is_container=bool(magic_payload.get("is_container", False)),
        ),
    )
    metadata_payload = _expect_mapping(payload, "metadata", "metadata")
    from humanhand.domain.metadata_inventory import MetadataItem

    raw_items = metadata_payload.get("items") or []
    if not isinstance(raw_items, list):
        raise DomainError("Invalid import inspection JSON: metadata.items must be a list")

    def _metadata_item_value(item: dict[str, object]) -> str:
        value = item.get("value")
        # Gated payloads render metadata values as null; accept them.
        return _expect_string(item, "value", "metadata.items.value") if value is not None else ""

    metadata_items = tuple(
        MetadataItem(
            key=_expect_string(item, "key", "metadata.items.key"),
            kind=_expect_string(item, "kind", "metadata.items.kind"),
            value=_metadata_item_value(item),
        )
        for index, item in enumerate(raw_items)
        if isinstance(item, dict)
    )
    if len(metadata_items) != len(raw_items):
        raise DomainError(
            "Invalid import inspection JSON: metadata.items must contain only objects"
        )
    metadata = MetadataInventory(items=metadata_items)
    raw_active = payload.get("active_content") or []
    if not isinstance(raw_active, list):
        raise DomainError("Invalid import inspection JSON: active_content must be a list")
    from humanhand.domain.active_content import ActiveContentKind

    active_content = tuple(
        ActiveContentFinding(
            kind=ActiveContentKind(_expect_string(item, "kind", "active_content.kind")),
            offset=_expect_int(item, "offset", "active_content.offset"),
            description=_expect_string(item, "description", "active_content.description"),
            evidence=_expect_string(item, "evidence", "active_content.evidence"),
        )
        for index, item in enumerate(raw_active)
        if isinstance(item, dict)
    )
    if len(active_content) != len(raw_active):
        raise DomainError(
            "Invalid import inspection JSON: active_content must contain only objects"
        )
    raw_unicode = payload.get("unicode")
    unicode_inventory = None
    if raw_unicode is not None:
        if not isinstance(raw_unicode, dict):
            raise DomainError("Invalid import inspection JSON: unicode must be an object or null")
        from humanhand.domain.unicode_policy import NormalizationForm, UnicodeInventory

        def _offset_list(key: str) -> tuple[int, ...]:
            raw_offsets = raw_unicode.get(key) or []
            if not isinstance(raw_offsets, list):
                raise DomainError(f"Invalid import inspection JSON: unicode.{key} must be a list")
            return tuple(int(item) for item in raw_offsets)

        unicode_inventory = UnicodeInventory(
            has_bom=bool(raw_unicode.get("has_bom", False)),
            bom_name=_expect_string(raw_unicode, "bom_name", "unicode.bom_name"),
            normalization_form=NormalizationForm(
                _expect_string(raw_unicode, "normalization_form", "unicode.normalization_form")
            ),
            control_char_offsets=_offset_list("control_char_offsets"),
            surrogate_offsets=_offset_list("surrogate_offsets"),
            non_nfc_offsets=_offset_list("non_nfc_offsets"),
            line_ending=_expect_string(raw_unicode, "line_ending", "unicode.line_ending"),
            codepoint_count=_expect_int(raw_unicode, "codepoint_count", "unicode.codepoint_count"),
        )
    measurements_payload = payload.get("measurements")
    measurements = None
    if measurements_payload is not None:
        if not isinstance(measurements_payload, dict):
            raise DomainError(
                "Invalid import inspection JSON: measurements must be an object or null"
            )
        duration = measurements_payload.get("duration_ms")
        peak = measurements_payload.get("peak_memory_bytes")
        measurements = ResourceMeasurements(
            size_bytes=_expect_int(measurements_payload, "size_bytes", "measurements.size_bytes"),
            expanded_bytes=_expect_int(
                measurements_payload, "expanded_bytes", "measurements.expanded_bytes"
            ),
            node_count=_expect_int(measurements_payload, "node_count", "measurements.node_count"),
            tree_depth=_expect_int(measurements_payload, "tree_depth", "measurements.tree_depth"),
            duration_ms=duration if isinstance(duration, int) else None,
            peak_memory_bytes=peak if isinstance(peak, int) else None,
        )
    return ImportInspection(
        schema_version=schema_version,
        import_id=_expect_string(payload, "import_id", "import_id"),
        lane=_expect_string(payload, "lane", "lane"),
        status=status,
        file_identity=identity,
        findings=findings,
        coverage=CoverageSummary(
            adapter=_expect_string(coverage_payload, "adapter", "coverage.adapter"),
            supported_structures=_coverage_string_list(coverage_payload, "supported_structures"),
            unsupported_structures=_coverage_string_list(
                coverage_payload, "unsupported_structures"
            ),
            status=_expect_string(coverage_payload, "status", "coverage.status"),
        ),
        metadata=metadata,
        unicode=unicode_inventory,
        active_content=active_content,
        measurements=measurements,
        document=document,
    )
