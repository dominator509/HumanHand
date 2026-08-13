"""Unit tests for deterministic relationship extraction."""

from __future__ import annotations

from humanhand.domain.canonical_document import (
    CanonicalDocument,
    CoverageSummary,
    ImportInspection,
    build_document,
    make_inspection,
)
from humanhand.domain.document_nodes import NodeBuilder, NodeType, SourceLocation
from humanhand.domain.entities import Entity, EntityRegistry, build_entities_from_package
from humanhand.domain.file_identity import derive_identity
from humanhand.domain.import_findings import ImportStatus
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.protected_spans import ProtectedSpan, ProtectedSpanSet, SpanKind
from humanhand.domain.relationships import build_relationships, relationships_to_payload
from humanhand.domain.source_evidence import SourceEvidence
from humanhand.domain.source_package import (
    LANE_SOURCE,
    SOURCE_PACKAGE_SCHEMA_VERSION,
    SourcePackage,
    build_source_package,
)


def _document(text: str) -> CanonicalDocument:
    root = NodeBuilder(node_type=NodeType.DOCUMENT)
    root.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text=text))
    return build_document(
        root=root,
        lane=LANE_SOURCE,
        parser_name="text",
        parser_version="1",
        policy=ImportPolicy(lane=LANE_SOURCE),
        surface_text=text,
    )


def _inspection(text: str) -> ImportInspection:
    raw = text.encode("utf-8")
    return make_inspection(
        raw=raw,
        identity=derive_identity("sample.txt", raw),
        lane=LANE_SOURCE,
        parser_name="text",
        parser_version="1",
        policy=ImportPolicy(lane=LANE_SOURCE),
        findings=(),
        coverage=CoverageSummary(
            adapter="text",
            supported_structures=("paragraph",),
            unsupported_structures=(),
            status="complete",
        ),
        document=_document(text),
    )


def _package(text: str) -> SourcePackage:
    return build_source_package(_inspection(text))


def _handmade_package(
    spans: tuple[ProtectedSpan, ...], *, text: str = "fact text"
) -> SourcePackage:
    document = _document(text)
    evidence = SourceEvidence(
        document=document,
        protected_spans=ProtectedSpanSet(spans=spans),
        quotations=(),
        citations=(),
    )
    return SourcePackage(
        schema_version=SOURCE_PACKAGE_SCHEMA_VERSION,
        package_id="src-handmade",
        document=document,
        evidence=evidence,
        findings=(),
        status=ImportStatus.OK,
        revision_policy="review_required",
    )


def _key_term_span(span_id: str, text: str) -> ProtectedSpan:
    return ProtectedSpan(
        span_id=span_id,
        kind=SpanKind.KEY_TERM,
        source_location=SourceLocation(start_offset=0, end_offset=len(text)),
        text=text,
    )


def _registry(*names: str) -> EntityRegistry:
    entities = tuple(
        Entity(entity_id=f"e{index}", name=name) for index, name in enumerate(names, start=1)
    )
    return EntityRegistry(entities=entities)


class TestBuildRelationships:
    def test_predicate_between_two_entities(self) -> None:
        # Hand-computed: the quotation span is s1, so claim cl1 carries
        # evidence refs ("s1",); "Acme Corporation" starts at 0 and "Beta
        # Labs" at 26, so the predicate is the exact words between them.
        package = _package('"Acme Corporation acquired Beta Labs" (Smith, 2020).')
        registry = build_entities_from_package(package)
        relationships = build_relationships(package, registry)
        assert len(relationships.relationships) == 1
        relationship = relationships.relationships[0]
        assert relationship.relationship_id == "r1"
        assert relationship.subject_id == "e1"
        assert relationship.predicate == "acquired"
        assert relationship.object_id == "e2"
        assert relationship.evidence_refs == ("s1",)

    def test_adjacent_entities_produce_no_relationship(self) -> None:
        # "Acme Corporation" and "Beta Labs" are adjacent, so the predicate
        # between them is empty and no relationship is created.
        package = _handmade_package((_key_term_span("s1", "Acme Corporation Beta Labs compete"),))
        registry = _registry("Acme Corporation", "Beta Labs")
        relationships = build_relationships(package, registry)
        assert relationships.relationships == ()
        assert relationships_to_payload(relationships) == {"relationships": []}

    def test_multiple_relationships(self) -> None:
        # Hand-computed: claim cl1 gives r1 (e1 acquired e2) and claim cl2
        # gives r2 (e2 sold e3).
        package = _package(
            '"Acme Corporation acquired Beta Labs" and "Beta Labs sold Gamma Works" (Smith, 2020).'
        )
        registry = build_entities_from_package(package)
        relationships = build_relationships(package, registry)
        assert [r.relationship_id for r in relationships.relationships] == ["r1", "r2"]
        assert relationships.relationships[0].predicate == "acquired"
        assert relationships.relationships[1].predicate == "sold"
        assert relationships.relationships[1].subject_id == "e2"
        assert relationships.relationships[1].object_id == "e3"

    def test_cap_limits_relationships_in_first_seen_order(self) -> None:
        package = _package(
            '"Acme Corporation acquired Beta Labs" and "Beta Labs sold Gamma Works" (Smith, 2020).'
        )
        registry = build_entities_from_package(package)
        relationships = build_relationships(package, registry, max_relationships=1)
        assert [r.relationship_id for r in relationships.relationships] == ["r1"]
        assert relationships.relationships[0].predicate == "acquired"

    def test_deterministic(self) -> None:
        package = _package('"Acme Corporation acquired Beta Labs" (Smith, 2020).')
        registry = build_entities_from_package(package)
        first = build_relationships(package, registry)
        second = build_relationships(package, registry)
        assert first == second


class TestRelationshipsPayload:
    def test_payload_shape(self) -> None:
        package = _package('"Acme Corporation acquired Beta Labs" (Smith, 2020).')
        registry = build_entities_from_package(package)
        relationships = build_relationships(package, registry)
        assert relationships_to_payload(relationships) == {
            "relationships": [
                {
                    "relationship_id": "r1",
                    "subject_id": "e1",
                    "predicate": "acquired",
                    "object_id": "e2",
                    "evidence_refs": ["s1"],
                }
            ]
        }
