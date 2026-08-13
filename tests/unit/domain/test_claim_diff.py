"""Unit tests for deterministic claim diffing."""

from __future__ import annotations

from humanhand.domain.claim_diff import claim_diff_to_payload, diff_claims
from humanhand.domain.claims_v2 import ClaimV2, CoverageStatus, Modality


def _claim(claim_id: str, proposition: str, *, negation: bool = False) -> ClaimV2:
    return ClaimV2(
        claim_id=claim_id,
        canonical_proposition=proposition,
        modality=Modality.ASSERTED,
        negation=negation,
        attribution="",
        source_evidence_refs=(),
        confidence=None,
    )


class TestDiffClaims:
    def test_preserved_omitted_added(self) -> None:
        source = (
            _claim("cl1", "the price is 50 dollars"),
            _claim("cl2", "we shipped 300 units"),
        )
        candidate = (
            _claim("c1", "the price is 50 dollars"),
            _claim("c2", "a new claim cites 42"),
        )
        report = diff_claims(source, candidate)
        assert report.preserved == ("cl1",)
        assert report.omitted == ("cl2",)
        assert report.added == ("c2",)
        assert report.contradicted_pairs == ()
        assert report.coverage_status is CoverageStatus.KNOWN

    def test_contradiction_numeric_change(self) -> None:
        source = (_claim("cl1", "the price is $50"),)
        candidate = (_claim("c1", "the price is $60"),)
        report = diff_claims(source, candidate)
        assert report.contradicted_pairs == (("cl1", "c1"),)
        assert report.preserved == ()
        assert report.omitted == ()
        assert report.added == ()

    def test_contradiction_negation_pair(self) -> None:
        source = (_claim("cl1", "the price is not $50.", negation=True),)
        candidate = (_claim("c1", "the price is $50."),)
        report = diff_claims(source, candidate)
        assert report.contradicted_pairs == (("cl1", "c1"),)
        assert report.preserved == ()
        assert report.omitted == ()
        assert report.added == ()

    def test_no_contradiction_for_unrelated_propositions(self) -> None:
        source = (_claim("cl1", "the price is $50"),)
        candidate = (_claim("c1", "we shipped 300 units"),)
        report = diff_claims(source, candidate)
        assert report.contradicted_pairs == ()
        assert report.omitted == ("cl1",)
        assert report.added == ("c1",)

    def test_negation_stripping_is_token_based(self) -> None:
        # Documented limitation: only whole negation-marker tokens are
        # stripped, so "does not work" vs "works" is NOT a contradiction.
        source = (_claim("cl1", "the product does not work"),)
        candidate = (_claim("c1", "the product works"),)
        report = diff_claims(source, candidate)
        assert report.contradicted_pairs == ()
        assert report.omitted == ("cl1",)
        assert report.added == ("c1",)

    def test_empty_source_reports_unknown_coverage(self) -> None:
        candidate = (_claim("c1", "the price is $50"),)
        report = diff_claims((), candidate)
        assert report.coverage_status is CoverageStatus.UNKNOWN_COVERAGE
        assert report.preserved == ()
        assert report.omitted == ()
        assert report.added == ("c1",)

    def test_multiset_matching_consumes_one_candidate_per_source_claim(self) -> None:
        source = (_claim("cl1", "same"), _claim("cl2", "same"))
        candidate = (_claim("c1", "same"),)
        report = diff_claims(source, candidate)
        assert report.preserved == ("cl1",)
        assert report.omitted == ("cl2",)
        assert report.added == ()

    def test_deterministic(self) -> None:
        source = (
            _claim("cl1", "the price is $50"),
            _claim("cl2", "we shipped 300 units"),
        )
        candidate = (
            _claim("c1", "the price is $60"),
            _claim("c2", "the price is 50 dollars"),
        )
        assert diff_claims(source, candidate) == diff_claims(source, candidate)


class TestClaimDiffPayload:
    def test_payload_shape(self) -> None:
        source = (_claim("cl1", "the price is $50"),)
        candidate = (_claim("c1", "the price is $60"),)
        report = diff_claims(source, candidate)
        payload = claim_diff_to_payload(report)
        assert payload == {
            "preserved": [],
            "omitted": [],
            "added": [],
            "contradicted_pairs": [["cl1", "c1"]],
            "coverage_status": "known",
        }

    def test_payload_shape_with_preserved_and_omitted(self) -> None:
        report = diff_claims(
            (_claim("cl1", "x"), _claim("cl2", "y")),
            (_claim("c1", "x"),),
        )
        assert claim_diff_to_payload(report) == {
            "preserved": ["cl1"],
            "omitted": ["cl2"],
            "added": [],
            "contradicted_pairs": [],
            "coverage_status": "known",
        }
