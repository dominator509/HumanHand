"""Unit tests for Claim V2 extraction and payload round trips."""

from __future__ import annotations

import pytest

from humanhand.domain.canonical_document import (
    CanonicalDocument,
    CoverageSummary,
    ImportInspection,
    build_document,
    make_inspection,
)
from humanhand.domain.claims_v2 import (
    ClaimStatus,
    ClaimV2,
    CoverageStatus,
    Modality,
    build_claims_from_package,
    claims_from_payload,
    claims_to_payload,
)
from humanhand.domain.document_nodes import NodeBuilder, NodeType, SourceLocation
from humanhand.domain.file_identity import derive_identity
from humanhand.domain.import_findings import ImportStatus
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.protected_spans import ProtectedSpan, ProtectedSpanSet, SpanKind
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


class TestBuildClaimsFromPackage:
    def test_number_date_citation_quotation_spans_become_claims(self) -> None:
        # Hand-computed: the protected spans appear in document order as
        # s1 date, s2 number, s3 citation, s4 quotation, so claims are
        # cl1..cl4 in that same order.
        package = _package(
            "On 2024-05-01 we shipped 300 units [1]; "
            'he said "this is a quite long quoted sentence."'
        )
        claims, coverage = build_claims_from_package(package)
        assert coverage is CoverageStatus.UNKNOWN_COVERAGE
        assert [claim.claim_id for claim in claims] == ["cl1", "cl2", "cl3", "cl4"]
        assert [claim.canonical_proposition for claim in claims] == [
            "2024-05-01",
            "300 units",
            "[1]",
            "this is a quite long quoted sentence.",
        ]
        assert [claim.modality for claim in claims] == [
            Modality.ASSERTED,
            Modality.ASSERTED,
            Modality.ASSERTED,
            Modality.REPORTED,
        ]
        assert [claim.negation for claim in claims] == [False, False, False, False]
        assert [claim.source_evidence_refs for claim in claims] == [
            ("s1",),
            ("s2",),
            ("s3",),
            ("s4",),
        ]
        assert all(claim.attribution == "" for claim in claims)
        assert all(claim.confidence is None for claim in claims)
        assert all(claim.allowed_paraphrase_scope == "exact" for claim in claims)
        assert all(claim.status is ClaimStatus.PROPOSED for claim in claims)

    def test_hedged_conditional_and_negation_markers(self) -> None:
        # Hand-computed: spans are passed in order s1..s5, so claim ids
        # follow as cl1..cl5 with the expected modality and negation flags.
        spans = (
            _key_term_span("s1", "it might be true"),
            _key_term_span("s2", "we never ship on time"),
            _key_term_span("s3", "if the price rises, we stop"),
            _key_term_span("s4", "we stop when the price falls"),
            _key_term_span("s5", "we stop unless the price falls"),
        )
        claims, coverage = build_claims_from_package(_handmade_package(spans))
        assert coverage is CoverageStatus.UNKNOWN_COVERAGE
        assert [claim.claim_id for claim in claims] == ["cl1", "cl2", "cl3", "cl4", "cl5"]
        assert [claim.modality for claim in claims] == [
            Modality.HEDGED,
            Modality.ASSERTED,
            Modality.CONDITIONAL,
            Modality.CONDITIONAL,
            Modality.CONDITIONAL,
        ]
        assert [claim.negation for claim in claims] == [False, True, False, False, False]

    def test_zero_spans_return_passed_coverage_status(self) -> None:
        package = _handmade_package(())
        claims, coverage = build_claims_from_package(
            package, coverage_status=CoverageStatus.UNKNOWN_COVERAGE
        )
        assert claims == ()
        assert coverage is CoverageStatus.UNKNOWN_COVERAGE
        # The function never guesses: the caller's explicit value is
        # returned unchanged, so a caller that mislabels an empty package
        # gets exactly the status it asked for (the caller's duty).
        _, known = build_claims_from_package(package, coverage_status=CoverageStatus.KNOWN)
        assert known is CoverageStatus.KNOWN

    def test_coverage_status_known_passed_through(self) -> None:
        package = _package("On 2024-05-01 we shipped 300 units [1].")
        _, coverage = build_claims_from_package(package, coverage_status=CoverageStatus.KNOWN)
        assert coverage is CoverageStatus.KNOWN

    def test_claim_ids_are_deterministic(self) -> None:
        text = "On 2024-05-01 we shipped 300 units [1]."
        first = build_claims_from_package(_package(text))
        second = build_claims_from_package(_package(text))
        assert first == second


def _first_claim_payload(payload: dict[str, object]) -> dict[str, object]:
    raw_claims = payload["claims"]
    assert isinstance(raw_claims, list)
    first = raw_claims[0]
    assert isinstance(first, dict)
    return dict(first)


def _with_first_claim(
    payload: dict[str, object], claim_payload: dict[str, object]
) -> dict[str, object]:
    raw_claims = payload["claims"]
    assert isinstance(raw_claims, list)
    bad_payload: dict[str, object] = dict(payload)
    bad_payload["claims"] = [claim_payload] + raw_claims[1:]
    return bad_payload


class TestClaimsPayload:
    def test_round_trip(self) -> None:
        package = _package(
            "On 2024-05-01 we shipped 300 units [1]; "
            'he said "this is a quite long quoted sentence."'
        )
        claims, coverage = build_claims_from_package(package)
        assert claims_from_payload(claims_to_payload(claims, coverage)) == (claims, coverage)

    def test_round_trip_with_custom_fields(self) -> None:
        claim = ClaimV2(
            claim_id="cl9",
            canonical_proposition="the temperature rose",
            modality=Modality.HEDGED,
            negation=True,
            attribution="",
            source_evidence_refs=("s3", "s7"),
            confidence=0.5,
            status=ClaimStatus.ACCEPTED,
            contradictions=("cl2",),
            allowed_paraphrase_scope="numeric",
        )
        assert claims_from_payload(claims_to_payload((claim,), CoverageStatus.KNOWN)) == (
            (claim,),
            CoverageStatus.KNOWN,
        )

    def test_from_payload_rejects_unknown_modality(self) -> None:
        claims, coverage = build_claims_from_package(_package("In 2024 we shipped 300 units."))
        payload = claims_to_payload(claims, coverage)
        bad_claim = _first_claim_payload(payload)
        bad_claim["modality"] = "bogus"
        with pytest.raises(DomainError, match="modality"):
            claims_from_payload(_with_first_claim(payload, bad_claim))

    def test_from_payload_rejects_unknown_coverage_status(self) -> None:
        claims, coverage = build_claims_from_package(_package("In 2024 we shipped 300 units."))
        bad_payload: dict[str, object] = dict(claims_to_payload(claims, coverage))
        bad_payload["coverage_status"] = "bogus"
        with pytest.raises(DomainError, match="coverage"):
            claims_from_payload(bad_payload)

    def test_from_payload_requires_claims_list(self) -> None:
        claims, coverage = build_claims_from_package(_package("In 2024 we shipped 300 units."))
        bad_payload: dict[str, object] = dict(claims_to_payload(claims, coverage))
        bad_payload.pop("claims")
        with pytest.raises(DomainError, match="claims"):
            claims_from_payload(bad_payload)

    def test_from_payload_rejects_unknown_claim_status(self) -> None:
        claims, coverage = build_claims_from_package(_package("In 2024 we shipped 300 units."))
        payload = claims_to_payload(claims, coverage)
        bad_claim = _first_claim_payload(payload)
        bad_claim["status"] = "bogus"
        with pytest.raises(DomainError, match="status"):
            claims_from_payload(_with_first_claim(payload, bad_claim))

    def test_from_payload_rejects_non_string_evidence_refs(self) -> None:
        claims, coverage = build_claims_from_package(_package("In 2024 we shipped 300 units."))
        payload = claims_to_payload(claims, coverage)
        bad_claim = _first_claim_payload(payload)
        bad_claim["source_evidence_refs"] = [1]
        with pytest.raises(DomainError, match="source_evidence_refs"):
            claims_from_payload(_with_first_claim(payload, bad_claim))

    def test_from_payload_rejects_boolean_confidence(self) -> None:
        claims, coverage = build_claims_from_package(_package("In 2024 we shipped 300 units."))
        payload = claims_to_payload(claims, coverage)
        bad_claim = _first_claim_payload(payload)
        bad_claim["confidence"] = True
        with pytest.raises(DomainError, match="confidence"):
            claims_from_payload(_with_first_claim(payload, bad_claim))
