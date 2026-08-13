"""Lane-separated import packages: source packages and style sample packages.

ADR-002: source and style imports use separate types. ``SourcePackage``
carries fact-bearing evidence; ``StyleSamplePackage`` carries none — the
type system itself prevents source facts from crossing into the style lane.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from humanhand.domain.canonical_document import CanonicalDocument, ImportInspection
from humanhand.domain.document_serialization import (
    document_from_json,
    document_to_json,
    document_to_payload,
    finding_from_payload,
    finding_to_payload,
)
from humanhand.domain.import_findings import ImportFinding, ImportStatus
from humanhand.domain.metadata_inventory import MetadataInventory
from humanhand.domain.source_evidence import SourceEvidence, build_source_evidence
from humanhand.domain.types import DomainError

SOURCE_PACKAGE_SCHEMA_VERSION = 1
STYLE_SAMPLE_PACKAGE_SCHEMA_VERSION = 1

LANE_SOURCE = "source"
LANE_STYLE = "style"


_LANE_PREFIX: dict[str, str] = {LANE_SOURCE: "src", LANE_STYLE: "sty"}


def _package_digest(lane: str, canonical_json: str) -> str:
    digest = hashlib.sha256()
    digest.update(lane.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(canonical_json.encode("utf-8"))
    return f"{_LANE_PREFIX[lane]}-{digest.hexdigest()[:24]}"


@dataclass(frozen=True)
class SourcePackage:
    """Source-lane import package: canonical document plus fact evidence.

    Only source-lane documents may produce a SourcePackage; quotations,
    citations, and protected spans never appear in the style lane.
    """

    schema_version: int
    package_id: str
    document: CanonicalDocument
    evidence: SourceEvidence
    findings: tuple[ImportFinding, ...]
    status: ImportStatus
    revision_policy: str

    def to_json(self) -> str:
        from humanhand.domain.document_serialization import dumps_stable

        return dumps_stable(self.to_payload())

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "source-package",
            "schema_version": self.schema_version,
            "package_id": self.package_id,
            "lane": LANE_SOURCE,
            "status": self.status.value,
            "revision_policy": self.revision_policy,
            "findings": [finding_to_payload(finding) for finding in self.findings],
            "document": document_to_payload(self.document),
            "evidence": self.evidence.to_payload(),
        }


@dataclass(frozen=True)
class StyleSamplePackage:
    """Style-lane import package: canonical document only, no fact evidence.

    Quotations, citations, and protected spans are deliberately absent from
    this type; style samples never contribute to the project fact graph.
    """

    schema_version: int
    package_id: str
    document: CanonicalDocument
    findings: tuple[ImportFinding, ...]
    status: ImportStatus
    authorship_status: str
    metadata: MetadataInventory

    def to_json(self) -> str:
        from humanhand.domain.document_serialization import dumps_stable

        return dumps_stable(self.to_payload())

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "style-sample-package",
            "schema_version": self.schema_version,
            "package_id": self.package_id,
            "lane": LANE_STYLE,
            "status": self.status.value,
            "authorship_status": self.authorship_status,
            "findings": [finding_to_payload(finding) for finding in self.findings],
            "document": document_to_payload(self.document),
            "metadata": self.metadata.to_payload(),
        }


def _require_document(inspection: ImportInspection) -> CanonicalDocument:
    if inspection.document is None:
        raise DomainError("Cannot build an import package without a canonical document")
    return inspection.document


def build_source_package(inspection: ImportInspection) -> SourcePackage:
    """Build a source package from a source-lane inspection (fails closed)."""
    if inspection.lane != LANE_SOURCE:
        raise DomainError(
            f"Source packages require the {LANE_SOURCE!r} lane, got {inspection.lane!r}"
        )
    document = _require_document(inspection)
    if document.lane != LANE_SOURCE:
        raise DomainError("Source package document is not a source-lane document")
    canonical_json = document_to_json(document)
    return SourcePackage(
        schema_version=SOURCE_PACKAGE_SCHEMA_VERSION,
        package_id=_package_digest(LANE_SOURCE, canonical_json),
        document=document,
        evidence=build_source_evidence(document),
        findings=inspection.findings,
        status=inspection.status,
        revision_policy=document.revision_policy,
    )


def build_style_sample_package(inspection: ImportInspection) -> StyleSamplePackage:
    """Build a style sample package from a style-lane inspection (fails closed)."""
    if inspection.lane != LANE_STYLE:
        raise DomainError(
            f"Style packages require the {LANE_STYLE!r} lane, got {inspection.lane!r}"
        )
    document = _require_document(inspection)
    if document.lane != LANE_STYLE:
        raise DomainError("Style package document is not a style-lane document")
    canonical_json = document_to_json(document)
    return StyleSamplePackage(
        schema_version=STYLE_SAMPLE_PACKAGE_SCHEMA_VERSION,
        package_id=_package_digest(LANE_STYLE, canonical_json),
        document=document,
        findings=inspection.findings,
        status=inspection.status,
        authorship_status="unreviewed",
        metadata=inspection.metadata,
    )


def source_package_from_json(text: str) -> SourcePackage:
    """Deserialize and validate a source package JSON string."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DomainError("Invalid source package JSON: not valid JSON") from exc
    if not isinstance(payload, dict):
        raise DomainError("Invalid source package JSON: top level must be an object")
    if payload.get("schema") != "source-package":
        raise DomainError("Invalid source package JSON: schema must be 'source-package'")
    if payload.get("schema_version") != SOURCE_PACKAGE_SCHEMA_VERSION:
        raise DomainError("Unsupported source package schema version")
    if payload.get("lane") != LANE_SOURCE:
        raise DomainError("Invalid source package JSON: lane must be 'source'")
    document = document_from_json(json.dumps(payload["document"], ensure_ascii=False))
    raw_findings = payload.get("findings") or []
    if not isinstance(raw_findings, list):
        raise DomainError("Invalid source package JSON: findings must be a list")
    findings = tuple(
        finding_from_payload(item, "source package finding")
        for item in raw_findings
        if isinstance(item, dict)
    )
    try:
        status = ImportStatus(str(payload.get("status", "failed")))
    except ValueError as exc:
        raise DomainError("Invalid source package JSON: unknown status value") from exc
    if document.lane != LANE_SOURCE:
        raise DomainError("Invalid source package JSON: embedded document is not source-lane")
    evidence_payload = payload.get("evidence")
    if not isinstance(evidence_payload, dict):
        raise DomainError("Invalid source package JSON: evidence must be an object")
    # Evidence and the package id are re-derived deterministically from the
    # document instead of trusting the payload; round-trips cannot drift.
    evidence = build_source_evidence(document)
    canonical_json = document_to_json(document)
    return SourcePackage(
        schema_version=SOURCE_PACKAGE_SCHEMA_VERSION,
        package_id=_package_digest(LANE_SOURCE, canonical_json),
        document=document,
        evidence=evidence,
        findings=findings,
        status=status,
        revision_policy=document.revision_policy,
    )


def style_sample_package_from_json(text: str) -> StyleSamplePackage:
    """Deserialize and validate a style sample package JSON string."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DomainError("Invalid style sample package JSON: not valid JSON") from exc
    if not isinstance(payload, dict):
        raise DomainError("Invalid style sample package JSON: top level must be an object")
    if payload.get("schema") != "style-sample-package":
        raise DomainError(
            "Invalid style sample package JSON: schema must be 'style-sample-package'"
        )
    if payload.get("schema_version") != STYLE_SAMPLE_PACKAGE_SCHEMA_VERSION:
        raise DomainError("Unsupported style sample package schema version")
    if payload.get("lane") != LANE_STYLE:
        raise DomainError("Invalid style sample package JSON: lane must be 'style'")
    document = document_from_json(json.dumps(payload["document"], ensure_ascii=False))
    raw_findings = payload.get("findings") or []
    if not isinstance(raw_findings, list):
        raise DomainError("Invalid style sample package JSON: findings must be a list")
    findings = tuple(
        finding_from_payload(item, "style sample package finding")
        for item in raw_findings
        if isinstance(item, dict)
    )
    try:
        status = ImportStatus(str(payload.get("status", "failed")))
    except ValueError as exc:
        raise DomainError("Invalid style sample package JSON: unknown status value") from exc
    if document.lane != LANE_STYLE:
        raise DomainError("Invalid style sample package JSON: embedded document is not style-lane")
    canonical_json = document_to_json(document)
    return StyleSamplePackage(
        schema_version=STYLE_SAMPLE_PACKAGE_SCHEMA_VERSION,
        package_id=_package_digest(LANE_STYLE, canonical_json),
        document=document,
        findings=findings,
        status=status,
        authorship_status=str(payload.get("authorship_status", "unreviewed")),
        metadata=inspection_metadata_from_json_payload(payload.get("metadata")),
    )


def inspection_metadata_from_json_payload(payload: object) -> MetadataInventory:
    """Parse a metadata payload, tolerating content-gated null values."""
    from humanhand.domain.metadata_inventory import MetadataItem

    if not isinstance(payload, dict):
        return MetadataInventory()
    items = payload.get("items") or []
    if not isinstance(items, list):
        return MetadataInventory()
    parsed = []
    for item in items:
        if not isinstance(item, dict):
            continue
        value = item.get("value")
        parsed.append(
            MetadataItem(
                key=str(item.get("key", "")),
                kind=str(item.get("kind", "")),
                value=str(value) if value is not None else "",
            )
        )
    return MetadataInventory(items=tuple(parsed))
