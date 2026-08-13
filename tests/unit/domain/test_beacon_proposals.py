"""Unit tests for beacon proposals, evidence sufficiency, and trigger workflow."""

from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from humanhand.domain.beacon_evidence import (
    BeaconEvidence,
    EvidenceSet,
    create_evidence,
    high_impact_sufficient,
    tier_for_source_kind,
)
from humanhand.domain.beacon_proposals import (
    BeaconProposal,
    ProposalKind,
    create_proposal,
    proposal_from_payload,
    proposal_to_payload,
)
from humanhand.domain.beacon_types import (
    BeaconStatus,
    BeaconTrigger,
    BeaconTriggerType,
    EvidenceTrustTier,
    create_trigger,
    trigger_flow_next,
)
from humanhand.domain.types import DomainError

T1 = EvidenceTrustTier.TIER_1_OFFICIAL_SPEC
T2 = EvidenceTrustTier.TIER_2_PEER_REVIEWED
T3 = EvidenceTrustTier.TIER_3_PREPRINT_OR_RELEASE_NOTES
T4 = EvidenceTrustTier.TIER_4_TECHNICAL_ANALYSIS
T5 = EvidenceTrustTier.TIER_5_COMMUNITY_LEAD

_SOURCE_KIND_BY_TIER = {
    T1: "official_spec",
    T2: "paper",
    T3: "release_notes",
    T4: "advisory",
    T5: "community",
}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_trigger() -> BeaconTrigger:
    return create_trigger(
        BeaconTriggerType.SECURITY_ADVISORY,
        "A security advisory affects a bundled parser dependency.",
        observed_at_note="advisory-2026-08",
    )


def make_evidence(
    tier: EvidenceTrustTier, url: str, summary: str = "Evidence summary"
) -> BeaconEvidence:
    return create_evidence(
        trigger_id=make_trigger().trigger_id,
        tier=tier,
        source_kind=_SOURCE_KIND_BY_TIER[tier],
        summary=summary,
        url=url,
        snippet_sha256=_sha(url),
    )


def make_proposal(
    *,
    kind: ProposalKind = ProposalKind.METADATA_FIELD,
    high_impact: bool = False,
    evidence: EvidenceSet | None = None,
    summary: str = "Add a documented metadata field.",
) -> BeaconProposal:
    if evidence is None:
        evidence = EvidenceSet(items=(make_evidence(T4, "https://example.org/analysis"),))
    return create_proposal(
        trigger=make_trigger(),
        kind=kind,
        summary=summary,
        evidence=evidence,
        high_impact=high_impact,
    )


class TestEvidenceSufficiency:
    def test_high_impact_one_tier1_is_sufficient(self) -> None:
        evidence = EvidenceSet(items=(make_evidence(T1, "https://example.org/spec"),))
        assert high_impact_sufficient(evidence, high_impact=True) is True

    def test_high_impact_two_independent_tier2_is_sufficient(self) -> None:
        evidence = EvidenceSet(
            items=(
                make_evidence(T2, "https://example.org/paper-a"),
                make_evidence(T2, "https://example.org/paper-b"),
            )
        )
        assert high_impact_sufficient(evidence, high_impact=True) is True

    def test_high_impact_two_independent_tier3_is_sufficient(self) -> None:
        evidence = EvidenceSet(
            items=(
                make_evidence(T3, "https://example.org/notes-a"),
                make_evidence(T3, "https://example.org/notes-b"),
            )
        )
        assert high_impact_sufficient(evidence, high_impact=True) is True

    def test_high_impact_two_tier2_same_url_is_insufficient(self) -> None:
        # Same URL, different captured snippets: distinct records (different
        # evidence ids) that are NOT independent sources.
        evidence = EvidenceSet(
            items=(
                make_evidence(T2, "https://example.org/same-paper", summary="Snippet one"),
                make_evidence(T2, "https://example.org/same-paper", summary="Snippet two"),
            )
        )
        assert high_impact_sufficient(evidence, high_impact=True) is False

    def test_high_impact_single_tier2_is_insufficient(self) -> None:
        evidence = EvidenceSet(items=(make_evidence(T2, "https://example.org/paper"),))
        assert high_impact_sufficient(evidence, high_impact=True) is False

    def test_high_impact_tier4_only_is_insufficient(self) -> None:
        evidence = EvidenceSet(items=(make_evidence(T4, "https://example.org/analysis"),))
        assert high_impact_sufficient(evidence, high_impact=True) is False

    def test_high_impact_mixed_tier23_and_tier5_is_insufficient(self) -> None:
        evidence = EvidenceSet(
            items=(
                make_evidence(T2, "https://example.org/paper"),
                make_evidence(T5, "https://example.org/community"),
            )
        )
        assert high_impact_sufficient(evidence, high_impact=True) is False

    def test_high_impact_tier1_plus_community_lead_is_sufficient(self) -> None:
        evidence = EvidenceSet(
            items=(
                make_evidence(T1, "https://example.org/spec"),
                make_evidence(T5, "https://example.org/community"),
            )
        )
        assert high_impact_sufficient(evidence, high_impact=True) is True

    def test_high_impact_empty_is_insufficient(self) -> None:
        assert high_impact_sufficient(EvidenceSet(items=()), high_impact=True) is False

    def test_non_high_impact_tier4_is_sufficient(self) -> None:
        evidence = EvidenceSet(items=(make_evidence(T4, "https://example.org/analysis"),))
        assert high_impact_sufficient(evidence, high_impact=False) is True

    def test_non_high_impact_tier5_only_is_insufficient(self) -> None:
        evidence = EvidenceSet(items=(make_evidence(T5, "https://example.org/lead"),))
        assert high_impact_sufficient(evidence, high_impact=False) is False

    def test_non_high_impact_empty_is_insufficient(self) -> None:
        assert high_impact_sufficient(EvidenceSet(items=()), high_impact=False) is False


class TestEvidenceCreation:
    def test_evidence_id_is_deterministic(self) -> None:
        first = make_evidence(T2, "https://example.org/paper")
        second = make_evidence(T2, "https://example.org/paper")
        assert first.evidence_id == second.evidence_id
        assert first.evidence_id.startswith("ev-")

    def test_evidence_id_changes_with_content(self) -> None:
        assert (
            make_evidence(T2, "https://example.org/a").evidence_id
            != make_evidence(T2, "https://example.org/b").evidence_id
        )

    def test_evidence_rejects_private_url(self) -> None:
        with pytest.raises(DomainError, match="public https"):
            create_evidence(
                trigger_id=make_trigger().trigger_id,
                tier=T4,
                source_kind="advisory",
                summary="Private analysis",
                url="http://internal.example.org/analysis",
                snippet_sha256=_sha("x"),
            )

    def test_evidence_rejects_bad_snippet_sha(self) -> None:
        with pytest.raises(DomainError, match="snippet_sha256"):
            create_evidence(
                trigger_id=make_trigger().trigger_id,
                tier=T4,
                source_kind="advisory",
                summary="Analysis",
                url="https://example.org/analysis",
                snippet_sha256="not-a-sha",
            )

    def test_evidence_rejects_unknown_source_kind(self) -> None:
        with pytest.raises(DomainError, match="source kind"):
            create_evidence(
                trigger_id=make_trigger().trigger_id,
                tier=T2,
                source_kind="bogus",
                summary="Analysis",
                url="https://example.org/paper",
                snippet_sha256=_sha("x"),
            )

    def test_tier_for_source_kind_documented_mapping(self) -> None:
        assert tier_for_source_kind("official_spec") is T1
        assert tier_for_source_kind("paper") is T2
        assert tier_for_source_kind("release_notes") is T3
        assert tier_for_source_kind("advisory") is T4
        assert tier_for_source_kind("community") is T5

    def test_evidence_set_rejects_duplicate_ids(self) -> None:
        evidence = make_evidence(T2, "https://example.org/paper")
        with pytest.raises(DomainError, match="duplicate"):
            EvidenceSet(items=(evidence, evidence))


class TestCreateProposal:
    def test_high_impact_with_insufficient_evidence_raises(self) -> None:
        evidence = EvidenceSet(items=(make_evidence(T5, "https://example.org/lead"),))
        with pytest.raises(DomainError, match="High-impact proposal"):
            create_proposal(
                trigger=make_trigger(),
                kind=ProposalKind.METADATA_FIELD,
                summary="A high-impact change.",
                evidence=evidence,
                high_impact=True,
            )

    def test_high_impact_with_one_tier1_passes(self) -> None:
        evidence = EvidenceSet(items=(make_evidence(T1, "https://example.org/spec"),))
        proposal = create_proposal(
            trigger=make_trigger(),
            kind=ProposalKind.PROVENANCE_STANDARD,
            summary="Adopt the standard.",
            evidence=evidence,
            high_impact=True,
        )
        assert proposal.status is BeaconStatus.PROPOSED

    def test_high_impact_with_two_independent_tier2_passes(self) -> None:
        evidence = EvidenceSet(
            items=(
                make_evidence(T2, "https://example.org/paper-a"),
                make_evidence(T2, "https://example.org/paper-b"),
            )
        )
        proposal = create_proposal(
            trigger=make_trigger(),
            kind=ProposalKind.PROVENANCE_STANDARD,
            summary="Adopt the standard.",
            evidence=evidence,
            high_impact=True,
        )
        assert proposal.status is BeaconStatus.PROPOSED

    def test_high_impact_with_two_independent_tier3_passes(self) -> None:
        evidence = EvidenceSet(
            items=(
                make_evidence(T3, "https://example.org/notes-a"),
                make_evidence(T3, "https://example.org/notes-b"),
            )
        )
        create_proposal(
            trigger=make_trigger(),
            kind=ProposalKind.PROVENANCE_STANDARD,
            summary="Adopt the standard.",
            evidence=evidence,
            high_impact=True,
        )

    def test_high_impact_with_same_url_twice_raises(self) -> None:
        evidence = EvidenceSet(
            items=(
                make_evidence(T2, "https://example.org/paper", summary="Snippet one"),
                make_evidence(T2, "https://example.org/paper", summary="Snippet two"),
            )
        )
        with pytest.raises(DomainError, match="High-impact proposal"):
            create_proposal(
                trigger=make_trigger(),
                kind=ProposalKind.PROVENANCE_STANDARD,
                summary="Adopt the standard.",
                evidence=evidence,
                high_impact=True,
            )

    def test_non_high_impact_with_tier4_passes(self) -> None:
        proposal = make_proposal(high_impact=False)
        assert proposal.status is BeaconStatus.PROPOSED
        assert proposal.blocked_action is False
        assert proposal.policy_note == ""

    def test_non_high_impact_with_tier5_only_raises(self) -> None:
        evidence = EvidenceSet(items=(make_evidence(T5, "https://example.org/lead"),))
        with pytest.raises(DomainError, match="Tier 1-4"):
            make_proposal(high_impact=False, evidence=evidence)

    def test_empty_summary_raises(self) -> None:
        evidence = EvidenceSet(items=(make_evidence(T4, "https://example.org/analysis"),))
        with pytest.raises(DomainError, match="summary"):
            create_proposal(
                trigger=make_trigger(),
                kind=ProposalKind.METADATA_FIELD,
                summary="   ",
                evidence=evidence,
                high_impact=False,
            )

    def test_proposal_id_is_deterministic(self) -> None:
        first = make_proposal()
        second = make_proposal()
        assert first.proposal_id == second.proposal_id
        assert first.proposal_id.startswith("prop-")
        assert first == second

    def test_proposal_id_changes_with_content(self) -> None:
        assert (
            make_proposal(summary="Change A.").proposal_id
            != make_proposal(summary="Change B.").proposal_id
        )


class TestTriggerFlow:
    def test_full_happy_path(self) -> None:
        expected = (
            BeaconStatus.TRIAGED,
            BeaconStatus.RESEARCHED,
            BeaconStatus.VERIFIED,
            BeaconStatus.PROPOSED,
            BeaconStatus.POLICY_REVIEWED,
            BeaconStatus.APPROVED,
            BeaconStatus.QUARANTINED,
            BeaconStatus.VALIDATED,
            BeaconStatus.RELEASE_APPROVED,
        )
        status = BeaconStatus.OBSERVED
        for next_status in expected:
            status = trigger_flow_next(status)
            assert status is next_status
        assert status is BeaconStatus.RELEASE_APPROVED

    def test_policy_reviewed_advances_to_approved(self) -> None:
        assert trigger_flow_next(BeaconStatus.POLICY_REVIEWED) is BeaconStatus.APPROVED

    def test_deny_path_is_terminal(self) -> None:
        # The deny path sets DENIED by explicit human decision; the linear
        # flow must refuse to advance a denied proposal.
        with pytest.raises(DomainError, match="no next state"):
            trigger_flow_next(BeaconStatus.DENIED)

    def test_release_approved_is_terminal(self) -> None:
        with pytest.raises(DomainError, match="no next state"):
            trigger_flow_next(BeaconStatus.RELEASE_APPROVED)


class TestPayloadRoundTrip:
    def test_plain_proposal_round_trip(self) -> None:
        proposal = make_proposal()
        assert proposal_from_payload(proposal_to_payload(proposal)) == proposal

    def test_policy_reviewed_blocked_proposal_round_trip(self) -> None:
        reviewed = replace(
            make_proposal(),
            status=BeaconStatus.POLICY_REVIEWED,
            blocked_action=True,
            policy_note="policy_mode=private_audited; decision=block; action_category='x'",
        )
        assert proposal_from_payload(proposal_to_payload(reviewed)) == reviewed

    def test_policy_note_is_preserved_in_round_trip(self) -> None:
        reviewed = replace(make_proposal(), policy_note="documented finding")
        restored = proposal_from_payload(proposal_to_payload(reviewed))
        assert restored.policy_note == "documented finding"

    def test_multi_evidence_round_trip(self) -> None:
        evidence = EvidenceSet(
            items=(
                make_evidence(T1, "https://example.org/spec"),
                make_evidence(T2, "https://example.org/paper"),
            )
        )
        proposal = make_proposal(high_impact=True, evidence=evidence)
        assert proposal_from_payload(proposal_to_payload(proposal)) == proposal

    def test_from_payload_rejects_wrong_schema(self) -> None:
        payload = proposal_to_payload(make_proposal())
        payload["schema"] = "wrong-schema"
        with pytest.raises(DomainError, match="schema"):
            proposal_from_payload(payload)

    def test_from_payload_rejects_wrong_schema_version(self) -> None:
        payload = proposal_to_payload(make_proposal())
        payload["schema_version"] = 99
        with pytest.raises(DomainError, match="schema version"):
            proposal_from_payload(payload)

    def test_from_payload_rejects_unknown_kind(self) -> None:
        payload = proposal_to_payload(make_proposal())
        payload["kind"] = "not_a_kind"
        with pytest.raises(DomainError, match="enum"):
            proposal_from_payload(payload)

    def test_from_payload_rejects_unknown_status(self) -> None:
        payload = proposal_to_payload(make_proposal())
        payload["status"] = "not_a_status"
        with pytest.raises(DomainError, match="enum"):
            proposal_from_payload(payload)

    def test_from_payload_rejects_non_bool_high_impact(self) -> None:
        payload = proposal_to_payload(make_proposal())
        payload["high_impact"] = "yes"
        with pytest.raises(DomainError, match="high_impact"):
            proposal_from_payload(payload)

    def test_from_payload_rejects_mismatched_proposal_id(self) -> None:
        payload = proposal_to_payload(make_proposal())
        payload["proposal_id"] = "prop-" + "0" * 24
        with pytest.raises(DomainError, match="proposal_id does not match"):
            proposal_from_payload(payload)

    def test_from_payload_rejects_mismatched_evidence_id(self) -> None:
        payload = proposal_to_payload(make_proposal())
        evidence_payload = payload["evidence"]
        assert isinstance(evidence_payload, dict)
        items = evidence_payload["items"]
        assert isinstance(items, list)
        first = items[0]
        assert isinstance(first, dict)
        first["evidence_id"] = "ev-" + "0" * 24
        with pytest.raises(DomainError, match="evidence_id does not match"):
            proposal_from_payload(payload)

    def test_from_payload_rejects_missing_evidence(self) -> None:
        payload = proposal_to_payload(make_proposal())
        del payload["evidence"]
        with pytest.raises(DomainError, match="evidence"):
            proposal_from_payload(payload)

    def test_from_payload_rejects_evidence_not_a_list(self) -> None:
        payload = proposal_to_payload(make_proposal())
        evidence_payload = payload["evidence"]
        assert isinstance(evidence_payload, dict)
        evidence_payload["items"] = "not-a-list"
        with pytest.raises(DomainError, match="items"):
            proposal_from_payload(payload)

    def test_from_payload_rejects_invalid_evidence_snippet_sha(self) -> None:
        payload = proposal_to_payload(make_proposal())
        evidence_payload = payload["evidence"]
        assert isinstance(evidence_payload, dict)
        items = evidence_payload["items"]
        assert isinstance(items, list)
        first = items[0]
        assert isinstance(first, dict)
        first["snippet_sha256"] = "not-a-sha"
        with pytest.raises(DomainError, match="snippet_sha256"):
            proposal_from_payload(payload)
