"""Style Fidelity Vault use cases — orchestration over injected ports.

No file or network I/O here; the vault port supplies persistence and the
domain layer supplies all analysis. Review decisions are explicit,
recorded, and replayed deterministically (latest decision wins).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from humanhand.application.style_ports import StyleVaultPort
from humanhand.domain.canonical_document import CanonicalDocument, ImportInspection
from humanhand.domain.document_nodes import DocumentNode, NodeType, SourceLocation
from humanhand.domain.document_serialization import document_to_json
from humanhand.domain.style_artifacts import (
    STYLE_EVIDENCE_PACKAGE_SCHEMA_VERSION,
    STYLE_RULESET_VERSION,
    OriginalStyleArtifact,
    StyleEvidencePackage,
)
from humanhand.domain.style_authorship import (
    AuthorshipClass,
    AuthorshipMap,
    AuthorshipSpan,
    ExcludedSpan,
)
from humanhand.domain.style_authorship import (
    approved_voice_text as _domain_approved_voice_text,
)
from humanhand.domain.style_serialization import package_from_json, package_to_json
from humanhand.domain.style_surface import build_surface_document
from humanhand.domain.types import DomainError

_TEXT_NODE_TYPES = frozenset(
    {
        NodeType.PARAGRAPH,
        NodeType.HEADING,
        NodeType.LIST_ITEM,
        NodeType.TABLE_CELL,
        NodeType.QUOTATION,
    }
)


def derive_authorship_spans(document: CanonicalDocument) -> AuthorshipMap:
    """Derive initial review spans from a style document's nodes.

    The only deterministic pre-classification is structural: spans over
    QUOTATION nodes map to ``QUOTATION`` (resolved by construction).
    Every other span starts UNKNOWN and requires an explicit recorded
    review decision — no authorship inference (blueprint 8.3, SPEC-011).
    """
    selected_nodes: list[DocumentNode] = []
    exact_span_indexes: dict[tuple[int, int], int] = {}
    for node in document.nodes:
        if node.node_type not in _TEXT_NODE_TYPES:
            continue
        if not node.text.strip():
            continue
        location = node.source_location
        exact_key = (location.start_offset, location.end_offset)
        has_exact_surface_span = (
            location.end_offset > location.start_offset
            and 0 <= location.start_offset <= location.end_offset <= len(document.surface_text)
            and document.surface_text[location.start_offset : location.end_offset] == node.text
        )
        if has_exact_surface_span and exact_key in exact_span_indexes:
            existing_index = exact_span_indexes[exact_key]
            existing = selected_nodes[existing_index]
            if (
                node.node_type is NodeType.QUOTATION
                and existing.node_type is not NodeType.QUOTATION
            ):
                selected_nodes[existing_index] = node
            continue
        if has_exact_surface_span:
            exact_span_indexes[exact_key] = len(selected_nodes)
        selected_nodes.append(node)

    spans: list[AuthorshipSpan] = []
    for span_number, node in enumerate(selected_nodes, start=1):
        location = node.source_location
        if node.node_type is NodeType.QUOTATION:
            spans.append(
                AuthorshipSpan(
                    span_id=f"a{span_number}",
                    source_location=location,
                    text=node.text,
                    authorship_class=AuthorshipClass.QUOTATION,
                    review_status="resolved",
                    decided_by="structural",
                )
            )
        else:
            spans.append(
                AuthorshipSpan(
                    span_id=f"a{span_number}",
                    source_location=location,
                    text=node.text,
                )
            )
    return AuthorshipMap(spans=tuple(spans), excluded=())


def build_style_evidence_package(
    *,
    inspection: ImportInspection,
    raw: bytes,
    vault: StyleVaultPort,
    profile_label: str,
    parser_version: str,
    package_id: str | None = None,
) -> StyleEvidencePackage:
    """Build and persist a style evidence package for a style-lane import.

    The original bytes and the package JSON are each stored exactly once;
    persisting is what makes a style import reviewable via
    ``style review <package-id>``. ``package_id`` overrides the import id
    so the vault handle matches the id users see in import JSON output.
    """
    if inspection.document is None:
        raise DomainError("Style import produced no canonical document")
    if inspection.lane != "style":
        raise DomainError("Style evidence packages require the style lane")
    document = inspection.document
    artifact_id = vault.store_original(raw)
    surface = build_surface_document(artifact_id=artifact_id, document=document)
    if package_id is None:
        import hashlib

        canonical_json = document_to_json(document).encode("utf-8")
        package_id = f"sty-{hashlib.sha256(canonical_json).hexdigest()[:24]}"
    blocking_features: list[str] = list(inspection.coverage.unsupported_structures)
    for finding in inspection.findings:
        if finding.severity.value == "error" and finding.code not in blocking_features:
            blocking_features.append(finding.code)
    package = StyleEvidencePackage(
        schema_version=STYLE_EVIDENCE_PACKAGE_SCHEMA_VERSION,
        package_id=package_id,
        profile_label=profile_label,
        original_artifact=OriginalStyleArtifact(
            artifact_id=artifact_id,
            sha256=artifact_id,
            size_bytes=len(raw),
            stored=True,
        ),
        exact_surface=surface,
        authorship=derive_authorship_spans(document),
        approved_exemplars=(),
        unsupported_features=tuple(blocking_features),
        parser_version=parser_version,
        ruleset_version=STYLE_RULESET_VERSION,
    )
    vault.store_package(package.package_id, package_to_json(package).encode("utf-8"))
    return package


def replay_decisions(
    package: StyleEvidencePackage, decisions: tuple[dict[str, object], ...]
) -> StyleEvidencePackage:
    """Apply the decision log deterministically (latest decision wins).

    Only decisions targeting this package apply; invalid records fail
    closed with DomainError rather than being silently ignored.
    """
    effective: dict[str, AuthorshipSpan] = {span.span_id: span for span in package.authorship.spans}
    excluded: dict[str, ExcludedSpan] = {span.span_id: span for span in package.authorship.excluded}
    # Exact text and spans always come from the immutable package; decisions
    # only ever change classification state.
    text_by_span: dict[str, str] = {span.span_id: span.text for span in package.authorship.spans}
    location_by_span: dict[str, SourceLocation] = {
        span.span_id: span.source_location for span in package.authorship.spans
    }
    for decision in decisions:
        if decision.get("package_id") != package.package_id:
            continue
        span_id = decision.get("span_id")
        if not isinstance(span_id, str):
            raise DomainError("Invalid style decision: span_id must be a string")
        raw_class = decision.get("authorship_class")
        if not isinstance(raw_class, str):
            raise DomainError("Invalid style decision: authorship_class must be a string")
        try:
            authorship_class = AuthorshipClass(raw_class)
        except ValueError as exc:
            raise DomainError("Invalid style decision: unknown authorship class") from exc
        if authorship_class is AuthorshipClass.UNKNOWN:
            raise DomainError("Invalid style decision: unknown authorship cannot be resolved")
        if span_id not in text_by_span:
            raise DomainError(f"Invalid style decision: unknown span id {span_id!r}")
        source_location = location_by_span[span_id]
        span_text = text_by_span[span_id]
        if authorship_class is AuthorshipClass.EXCLUDE:
            excluded[span_id] = ExcludedSpan(
                span_id=span_id,
                source_location=source_location,
                reason=str(decision.get("reason", "excluded by review")),
            )
            effective.pop(span_id, None)
            continue
        excluded.pop(span_id, None)  # a later decision restores an exclusion
        effective[span_id] = AuthorshipSpan(
            span_id=span_id,
            source_location=source_location,
            text=span_text,
            authorship_class=authorship_class,
            review_status="resolved",
            decided_by=str(decision.get("decided_by", "cli")),
        )
    ordered_spans = tuple(
        effective[span.span_id] for span in package.authorship.spans if span.span_id in effective
    )
    return replace(
        package,
        authorship=AuthorshipMap(
            spans=ordered_spans,
            excluded=tuple(excluded.values()),
        ),
    )


@dataclass(frozen=True)
class ReviewResult:
    """Result of a review operation."""

    package: StyleEvidencePackage
    decisions_applied: int


def record_review_decision(
    *,
    package: StyleEvidencePackage,
    span_id: str,
    authorship_class: AuthorshipClass,
    vault: StyleVaultPort,
    decided_by: str = "cli",
    reason: str | None = None,
) -> ReviewResult:
    """Record one explicit review decision and return the effective package."""
    package.authorship.by_id(span_id)  # raises KeyError for unknown spans
    if authorship_class is AuthorshipClass.UNKNOWN:
        raise DomainError("Unknown authorship cannot be recorded as a resolved decision")
    decision: dict[str, object] = {
        "package_id": package.package_id,
        "span_id": span_id,
        "authorship_class": authorship_class.value,
        "decided_by": decided_by,
    }
    if reason is not None:
        decision["reason"] = reason
    vault.append_decision(decision)
    effective = replay_decisions(package, vault.read_decisions())
    return ReviewResult(package=effective, decisions_applied=1)


def verify_package_integrity(package: StyleEvidencePackage, vault: StyleVaultPort) -> None:
    """Verify a loaded package against its immutable original and surface.

    Raises DomainError when the original is missing or its sha256 does not
    match the artifact id, or when the surface text no longer hashes to
    the recorded surface sha256. This makes every CLI read integrity
    checked, not just the vault's own original reads.
    """
    import hashlib

    artifact_id = package.original_artifact.artifact_id
    original = vault.load_original(artifact_id)
    original_sha = hashlib.sha256(original).hexdigest()
    if original_sha != artifact_id or original_sha != package.original_artifact.sha256:
        raise DomainError("Style package integrity check failed: original mismatch")
    if len(original) != package.original_artifact.size_bytes:
        raise DomainError("Style package integrity check failed: original size mismatch")
    if package.exact_surface.artifact_id != artifact_id:
        raise DomainError("Style package integrity check failed: artifact linkage mismatch")
    surface_sha = hashlib.sha256(package.exact_surface.surface_text.encode("utf-8")).hexdigest()
    if surface_sha != package.exact_surface.sha256:
        raise DomainError("Style package integrity check failed: surface mismatch")
    statistics = package.exact_surface.statistics
    if (
        statistics.code_points != len(package.exact_surface.surface_text)
        or statistics.bytes_utf8 != len(package.exact_surface.surface_text.encode("utf-8"))
        or statistics.lines != package.exact_surface.surface_text.count("\n") + 1
    ):
        raise DomainError("Style package integrity check failed: surface statistics mismatch")
    span_ids = [span.span_id for span in package.authorship.spans]
    if len(span_ids) != len(set(span_ids)):
        raise DomainError("Style package integrity check failed: duplicate authorship span id")
    for span in package.authorship.spans:
        if span.text not in package.exact_surface.surface_text:
            raise DomainError("Style package integrity check failed: authorship text mismatch")


def load_effective_package(*, package_id: str, vault: StyleVaultPort) -> StyleEvidencePackage:
    """Load a stored package, verify its integrity, replay the decision log."""
    package = package_from_json(vault.load_package(package_id).decode("utf-8"))
    if package.package_id != package_id:
        raise DomainError("Style package integrity check failed: package id mismatch")
    verify_package_integrity(package, vault)
    return replay_decisions(package, vault.read_decisions())


def approved_voice_text(package: StyleEvidencePackage) -> str:
    """Concatenated text of approved voice-profile spans, in document order.

    Delegates to the single domain-side voice filter.
    """
    return _domain_approved_voice_text(package.authorship)


def packages_for_label(
    package_ids: tuple[str, ...], vault: StyleVaultPort, label: str
) -> tuple[StyleEvidencePackage, ...]:
    """Load all stored packages matching a profile label."""
    result: list[StyleEvidencePackage] = []
    for package_id in package_ids:
        package = load_effective_package(package_id=package_id, vault=vault)
        if package.profile_label == label:
            result.append(package)
    return tuple(result)
