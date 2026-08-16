"""Integrated deterministic pre-SLM workflow services (EP-019).

This application layer joins the already-built clean-room import, Style
Fidelity Vault, Project Brain, context, lexical review, revision, and public
artifact contracts. It performs no network access and no direct CLI rendering.
The future SLM must enter after this workflow, not bypass it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace

from humanhand.domain.canonical_document import CanonicalDocument
from humanhand.domain.citations import Citation, extract_citations
from humanhand.domain.claims_v2 import (
    ClaimStatus,
    ClaimV2,
    CoverageStatus,
    Modality,
    build_claims_from_package,
)
from humanhand.domain.context_capsule import ContextCapsule, build_context_capsule
from humanhand.domain.context_policy import ContextPolicy
from humanhand.domain.document_nodes import SourceLocation
from humanhand.domain.document_serialization import document_to_json
from humanhand.domain.entities import Entity, EntityType, build_entities_from_package
from humanhand.domain.lexical_context import build_contexts
from humanhand.domain.lexical_normalizer import LexicalProposal, propose_changes
from humanhand.domain.lexical_review import (
    LexicalReviewJournal,
    apply_review,
    revalidate_facts_and_citations,
    revalidate_structure,
)
from humanhand.domain.lexical_types import RulesetVersion
from humanhand.domain.project import ProjectState
from humanhand.domain.protected_spans import (
    ProtectedSpan,
    ProtectedSpanSet,
    SpanKind,
    SpanStatus,
)
from humanhand.domain.relationships import build_relationships
from humanhand.domain.revision_transform import apply_reviewed_proposal
from humanhand.domain.revisions import (
    DocumentRevision,
    accept_revision,
    create_initial_revision,
    propose_next_revision,
)
from humanhand.domain.source_package import SourcePackage
from humanhand.domain.structure_signature import compute_structure_signature
from humanhand.domain.style_compare import StyleComparisonReport, compare_profile
from humanhand.domain.style_profiles import StyleEvidenceProfile
from humanhand.domain.types import DomainError
from humanhand.infra.stores.integrated_project_store import (
    IntegratedProjectStore,
    StoredRevisionContent,
)
from humanhand.infra.stores.project_store import ProjectStoreError


@dataclass(frozen=True)
class IngestResult:
    """Result of persisting one clean-room source package."""

    project_id: str
    document_id: str
    revision_id: str
    claim_count: int
    entity_count: int
    protected_span_count: int
    relationship_count: int


@dataclass(frozen=True)
class LoadedDocumentState:
    """All deterministic records needed for context/finalization/export."""

    project: ProjectState
    revision: DocumentRevision
    content: StoredRevisionContent
    document: CanonicalDocument
    claims: tuple[ClaimV2, ...]
    protected_spans: tuple[ProtectedSpan, ...]
    citations: tuple[Citation, ...]
    entities: tuple[Entity, ...]


@dataclass(frozen=True)
class FinalizationResult:
    """One accepted revision created from a reviewed lexical proposal."""

    document_id: str
    revision_id: str
    accepted_change_count: int
    accepted_text_sha256: str
    style_report: StyleComparisonReport | None


def _ensure_project(store: IntegratedProjectStore, project: ProjectState) -> None:
    try:
        store.load_project(project.project_id)
    except ProjectStoreError:
        store.create_project(project)


def ingest_source_package(
    *,
    package: SourcePackage,
    project: ProjectState,
    store: IntegratedProjectStore,
    style_profile_id: str = "",
) -> IngestResult:
    """Persist a clean source package as the initial accepted revision."""
    if package.document.lane != "source":
        raise DomainError("Integrated ingest requires a source-lane package")
    if store.current_revision(package.package_id) is not None:
        raise DomainError(f"Document already ingested: {package.package_id}")

    claims, _ = build_claims_from_package(package)
    entities = build_entities_from_package(package)
    relationships = build_relationships(package, entities)
    spans = package.evidence.protected_spans.spans
    signature = compute_structure_signature(package.document)
    accepted_text = package.document.surface_text
    accepted_sha = hashlib.sha256(accepted_text.encode("utf-8")).hexdigest()
    revision = create_initial_revision(
        document_id=package.package_id,
        structure_signature=signature,
        accepted_text_sha256=accepted_sha,
    )
    canonical_json = document_to_json(package.document)

    with store.atomic():
        _ensure_project(store, project)
        store.add_document(package.package_id, project.project_id, purpose="")
        store.save_claims(package.package_id, claims)
        store.save_entities(package.package_id, entities.entities)
        store.save_protected_spans(package.package_id, spans)
        store.save_relationships(package.package_id, relationships.relationships)
        store.save_revision(revision)
        store.save_revision_content(
            revision=revision,
            accepted_text=accepted_text,
            canonical_document_json=canonical_json,
            style_profile_id=style_profile_id,
        )
        if style_profile_id:
            store.bind_style_profile(project.project_id, style_profile_id)
        store.record_approval(
            target_kind="ingest",
            target_id=f"{package.package_id}:{revision.revision_id}",
            decision="accepted",
            decided_by="human",
        )

    return IngestResult(
        project_id=project.project_id,
        document_id=package.package_id,
        revision_id=revision.revision_id,
        claim_count=len(claims),
        entity_count=len(entities.entities),
        protected_span_count=len(spans),
        relationship_count=len(relationships.relationships),
    )


def _required_int(row: dict[str, object], key: str) -> int:
    value = row.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProjectStoreError(f"Stored row field {key!r} must be an integer")
    return value


def _optional_float(row: dict[str, object], key: str) -> float | None:
    value = row.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProjectStoreError(f"Stored row field {key!r} must be numeric or null")
    return float(value)


def _required_boolish(row: dict[str, object], key: str) -> bool:
    value = row.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    raise ProjectStoreError(f"Stored row field {key!r} must be boolean or 0/1")


def _claim_from_row(row: dict[str, object]) -> ClaimV2:
    try:
        return ClaimV2(
            claim_id=str(row["claim_id"]),
            canonical_proposition=str(row["proposition"]),
            modality=Modality(str(row["modality"])),
            negation=_required_boolish(row, "negation"),
            attribution=str(row.get("attribution") or ""),
            source_evidence_refs=(),
            confidence=_optional_float(row, "confidence"),
            status=ClaimStatus(str(row["status"])),
            contradictions=(),
            allowed_paraphrase_scope=str(row["paraphrase_scope"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ProjectStoreError("Stored claim row is corrupt") from exc


def _protected_span_from_row(row: dict[str, object]) -> ProtectedSpan:
    try:
        return ProtectedSpan(
            span_id=str(row["span_id"]),
            kind=SpanKind(str(row["kind"])),
            source_location=SourceLocation(
                start_offset=_required_int(row, "start_offset"),
                end_offset=_required_int(row, "end_offset"),
            ),
            text=str(row["text"]),
            status=SpanStatus.APPROVED,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ProjectStoreError("Stored protected-span row is corrupt") from exc


def _entity_from_row(row: dict[str, object]) -> Entity:
    try:
        return Entity(
            entity_id=str(row["entity_id"]),
            name=str(row["name"]),
            entity_type=EntityType(str(row["entity_type"])),
            aliases=(),
            evidence_refs=(),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ProjectStoreError("Stored entity row is corrupt") from exc


def load_document_state(
    *,
    project_id: str,
    document_id: str,
    store: IntegratedProjectStore,
) -> LoadedDocumentState:
    """Load the latest accepted revision and all context records."""
    project = store.load_project(project_id)
    if document_id not in project.document_ids:
        raise DomainError(f"Document is not part of project: {document_id}")
    revision = store.latest_accepted_revision(document_id)
    if revision is None:
        raise DomainError(f"Document has no accepted revision: {document_id}")
    content = store.load_revision_content(document_id, revision.revision_id)
    if content is None:
        raise DomainError(
            f"Accepted revision has no persisted content: {document_id}:{revision.revision_id}"
        )
    document = content.canonical_document
    claims = tuple(_claim_from_row(row) for row in store.load_claims(document_id))
    spans = tuple(_protected_span_from_row(row) for row in store.load_protected_spans(document_id))
    entities = tuple(_entity_from_row(row) for row in store.load_entities(document_id))
    citations = extract_citations(document.nodes)
    return LoadedDocumentState(
        project=project,
        revision=revision,
        content=content,
        document=document,
        claims=claims,
        protected_spans=spans,
        citations=citations,
        entities=entities,
    )


def build_integrated_context(
    *,
    state: LoadedDocumentState,
    block_id: str,
    profile: StyleEvidenceProfile | None,
    policy: ContextPolicy | None = None,
) -> ContextCapsule:
    """Build a context capsule from the accepted revision and style profile."""
    return build_context_capsule(
        document=state.document,
        revision=state.revision,
        block_id=block_id,
        project_state=state.project,
        claims=state.claims,
        protected_spans=state.protected_spans,
        citations=state.citations,
        entities=state.entities,
        profile=profile,
        policy=policy or ContextPolicy(),
    )


def propose_integrated_lexical_changes(
    *,
    state: LoadedDocumentState,
    ruleset: RulesetVersion,
    user_preferences: dict[str, str] | None = None,
    safe_threshold: float = 0.90,
) -> LexicalProposal:
    """Build a deterministic lexical proposal over the accepted revision."""
    spans = ProtectedSpanSet(spans=state.protected_spans)
    contexts = build_contexts(state.content.accepted_text, spans)
    return propose_changes(
        state.content.accepted_text,
        ruleset,
        contexts,
        user_preferences=user_preferences or {},
        project_glossary=(),
        register_rules=(),
        domain_glossary=(),
        safe_threshold=safe_threshold,
        protected_spans=spans,
    )


def _rebase_protected_spans(
    *,
    spans: tuple[ProtectedSpan, ...],
    proposal: LexicalProposal,
    accepted_change_ids: frozenset[str],
    transformed_text: str,
) -> tuple[ProtectedSpan, ...]:
    """Shift stored source offsets across accepted non-overlapping edits."""
    accepted = tuple(
        change for change in proposal.changes if change.change_id in accepted_change_ids
    )
    rebased: list[ProtectedSpan] = []
    for span in spans:
        location = span.source_location
        shift = 0
        for change in accepted:
            change_end = change.offset + change.length
            if change_end <= location.start_offset:
                shift += len(change.target) - change.length
            elif change.offset < location.end_offset:
                raise DomainError(
                    f"Accepted lexical change overlaps protected span: {span.span_id}"
                )
        rebased_location = replace(
            location,
            start_offset=location.start_offset + shift,
            end_offset=location.end_offset + shift,
        )
        rebased_range = slice(rebased_location.start_offset, rebased_location.end_offset)
        rebased_text = transformed_text[rebased_range]
        if rebased_text != span.text:
            raise DomainError(f"Protected span rebase failed: {span.span_id}")
        rebased.append(replace(span, source_location=rebased_location))
    return tuple(rebased)


def finalize_reviewed_revision(
    *,
    state: LoadedDocumentState,
    proposal: LexicalProposal,
    journal: LexicalReviewJournal,
    store: IntegratedProjectStore,
    profile: StyleEvidenceProfile | None,
) -> FinalizationResult:
    """Apply reviewed changes, revalidate, and commit a new accepted revision."""
    reviewed = apply_review(proposal, journal)
    transformed = apply_reviewed_proposal(state.document, reviewed)
    rebased_spans = _rebase_protected_spans(
        spans=state.protected_spans,
        proposal=proposal,
        accepted_change_ids=frozenset(change.change_id for change in reviewed.changes),
        transformed_text=transformed.surface_text,
    )

    facts_ok, fact_findings = revalidate_facts_and_citations(
        state.content.accepted_text, transformed.surface_text
    )
    if not facts_ok:
        raise DomainError(
            "Finalization fact/citation validation failed: " + ";".join(fact_findings)
        )

    transformed_signature = compute_structure_signature(transformed)
    structure_ok, structure_findings = revalidate_structure(
        transformed_signature, state.revision.structure_signature
    )
    if not structure_ok:
        raise DomainError(
            "Finalization structure validation failed: " + ";".join(structure_findings)
        )

    style_report: StyleComparisonReport | None = None
    if profile is not None:
        if profile.status != "complete":
            raise DomainError("Bound style profile is not complete")
        style_report = compare_profile(profile, transformed)
        if style_report.hard_invariant_violations:
            raise DomainError(
                "Finalization violates bound style invariants: "
                f"count={len(style_report.hard_invariant_violations)}"
            )

    accepted_text = transformed.surface_text
    accepted_sha = hashlib.sha256(accepted_text.encode("utf-8")).hexdigest()
    proposed_revision = propose_next_revision(
        current=state.revision,
        structure_signature=transformed_signature,
        accepted_text_sha256=accepted_sha,
        note=f"lexical finalization {proposal.run_id}",
    )
    accepted_revision = accept_revision(
        proposed=proposed_revision,
        expected_current=state.revision,
    )

    with store.atomic():
        current = store.latest_accepted_revision(state.revision.document_id)
        if current is None or current.revision_id != state.revision.revision_id:
            raise DomainError("Accepted revision changed while finalization was pending")
        store.save_revision(accepted_revision)
        store.save_revision_content(
            revision=accepted_revision,
            accepted_text=accepted_text,
            canonical_document_json=document_to_json(transformed),
            style_profile_id=profile.profile_id if profile else "",
            finalization_run_id=proposal.run_id,
        )
        store.save_protected_spans(state.revision.document_id, rebased_spans)
        store.record_approval(
            target_kind="revision",
            target_id=f"{state.revision.document_id}:{accepted_revision.revision_id}",
            decision="accepted",
            decided_by="human",
        )

    return FinalizationResult(
        document_id=state.revision.document_id,
        revision_id=accepted_revision.revision_id,
        accepted_change_count=len(reviewed.changes),
        accepted_text_sha256=accepted_sha,
        style_report=style_report,
    )


def coverage_status_for_state(state: LoadedDocumentState) -> CoverageStatus:
    """Return known coverage only when at least one stored claim exists."""
    return CoverageStatus.KNOWN if state.claims else CoverageStatus.UNKNOWN_COVERAGE
