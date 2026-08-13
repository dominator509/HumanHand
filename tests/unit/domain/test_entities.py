"""Unit tests for deterministic entity extraction."""

from __future__ import annotations

import pytest

from humanhand.domain.canonical_document import (
    CanonicalDocument,
    CoverageSummary,
    ImportInspection,
    build_document,
    make_inspection,
)
from humanhand.domain.document_nodes import NodeBuilder, NodeType, SourceLocation
from humanhand.domain.entities import (
    EntityType,
    build_entities_from_package,
    registry_from_payload,
    registry_to_payload,
)
from humanhand.domain.file_identity import derive_identity
from humanhand.domain.import_findings import ImportStatus
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.protected_spans import ProtectedSpan, ProtectedSpanSet, SpanKind
from humanhand.domain.quotations import Quotation
from humanhand.domain.source_evidence import SourceEvidence
from humanhand.domain.source_package import (
    LANE_SOURCE,
    SOURCE_PACKAGE_SCHEMA_VERSION,
    SourcePackage,
    build_source_package,
)
from humanhand.domain.types import DomainError


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


class TestBuildEntitiesFromPackage:
    def test_extracts_capitalized_phrases_and_person_from_citation(self) -> None:
        # Hand-computed: the quotation span is s1 ("Acme Corporation
        # shipped 300 units") and the author-year citation span is s2
        # ("Smith, 2020"), so entities are e1 "Acme Corporation" (OTHER)
        # and e2 "Smith" (PERSON, from the citation name).
        package = _package('"Acme Corporation shipped 300 units" (Smith, 2020).')
        registry = build_entities_from_package(package)
        assert [entity.entity_id for entity in registry.entities] == ["e1", "e2"]
        acme = registry.by_id("e1")
        smith = registry.by_id("e2")
        assert acme.name == "Acme Corporation"
        assert acme.entity_type is EntityType.OTHER
        assert acme.aliases == ()
        assert acme.evidence_refs == ("s1",)
        assert smith.name == "Smith"
        assert smith.entity_type is EntityType.PERSON
        assert smith.evidence_refs == ("s2",)

    def test_by_name_is_exact_and_case_sensitive(self) -> None:
        package = _package('"Acme Corporation shipped 300 units" (Smith, 2020).')
        registry = build_entities_from_package(package)
        assert registry.by_name("Acme Corporation") == registry.by_id("e1")
        assert registry.by_name("acme corporation") is None
        assert registry.by_name("Smith") == registry.by_id("e2")

    def test_by_id_raises_for_unknown(self) -> None:
        registry = build_entities_from_package(
            _package('"Acme Corporation shipped 300 units" (Smith, 2020).')
        )
        with pytest.raises(KeyError):
            registry.by_id("e99")

    def test_person_typing_when_name_appears_in_author_year_citation(self) -> None:
        # "Smith Corporation" is first seen as an OTHER phrase but the
        # author-year citation names it, so it is typed PERSON on the
        # strength of the citation alone.
        package = _package('"Smith Corporation shipped 300 units" (Smith Corporation, 2020).')
        registry = build_entities_from_package(package)
        smith_corp = registry.by_name("Smith Corporation")
        assert smith_corp is not None
        assert smith_corp.entity_type is EntityType.PERSON

    def test_cap_limits_entities_in_first_seen_order(self) -> None:
        # Hand-computed: candidates arrive as "Acme Corporation", then
        # "Beta Labs" (both from the quotation claim), then "Smith" (the
        # citation name); the cap of 2 keeps only the first two.
        package = _package('"Acme Corporation shipped 300 units to Beta Labs" (Smith, 2020).')
        registry = build_entities_from_package(package, max_entities=2)
        assert [entity.name for entity in registry.entities] == ["Acme Corporation", "Beta Labs"]

    def test_extracts_entities_from_quotation_attribution(self) -> None:
        # The key-term span carries no capitalized phrase, so the only
        # entity source is the quotation's hand-supplied attribution.
        document = _document("a plain fact")
        key_term = _key_term_span("s1", "a plain fact")
        quotation = Quotation(
            text="quoted text",
            source_location=SourceLocation(start_offset=0, end_offset=11),
            attribution="Acme Corporation",
        )
        evidence = SourceEvidence(
            document=document,
            protected_spans=ProtectedSpanSet(spans=(key_term,)),
            quotations=(quotation,),
            citations=(),
        )
        package = SourcePackage(
            schema_version=SOURCE_PACKAGE_SCHEMA_VERSION,
            package_id="src-handmade",
            document=document,
            evidence=evidence,
            findings=(),
            status=ImportStatus.OK,
            revision_policy="review_required",
        )
        registry = build_entities_from_package(package)
        assert [entity.name for entity in registry.entities] == ["Acme Corporation"]
        acme = registry.by_id("e1")
        assert acme.entity_type is EntityType.OTHER
        # No protected span text mentions the name, so there is no
        # evidence reference to invent.
        assert acme.evidence_refs == ()


def _first_entity_payload(payload: dict[str, object]) -> dict[str, object]:
    raw_entities = payload["entities"]
    assert isinstance(raw_entities, list)
    first = raw_entities[0]
    assert isinstance(first, dict)
    return dict(first)


def _with_first_entity(
    payload: dict[str, object], entity_payload: dict[str, object]
) -> dict[str, object]:
    raw_entities = payload["entities"]
    assert isinstance(raw_entities, list)
    bad_payload: dict[str, object] = dict(payload)
    bad_payload["entities"] = [entity_payload] + raw_entities[1:]
    return bad_payload


class TestEntityRegistryPayload:
    def test_round_trip(self) -> None:
        package = _package('"Acme Corporation shipped 300 units" (Smith, 2020).')
        registry = build_entities_from_package(package)
        assert registry_from_payload(registry_to_payload(registry)) == registry

    def test_from_payload_rejects_unknown_entity_type(self) -> None:
        package = _package('"Acme Corporation shipped 300 units" (Smith, 2020).')
        registry = build_entities_from_package(package)
        payload = registry_to_payload(registry)
        bad_entity = _first_entity_payload(payload)
        bad_entity["entity_type"] = "bogus"
        with pytest.raises(DomainError, match="Unknown entity type"):
            registry_from_payload(_with_first_entity(payload, bad_entity))

    def test_from_payload_requires_entities_list(self) -> None:
        package = _package('"Acme Corporation shipped 300 units" (Smith, 2020).')
        registry = build_entities_from_package(package)
        bad_payload: dict[str, object] = dict(registry_to_payload(registry))
        bad_payload.pop("entities")
        with pytest.raises(DomainError, match="entities"):
            registry_from_payload(bad_payload)
