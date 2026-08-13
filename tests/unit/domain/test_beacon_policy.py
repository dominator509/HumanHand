"""Unit tests for the beacon policy firewall and bundled policy resources."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from humanhand.domain.beacon_evidence import EvidenceSet, create_evidence
from humanhand.domain.beacon_policy import (
    MANDATORY_BLOCKED_ACTIONS,
    action_category_for_kind,
    load_allowed_actions_from_resource,
    policy_decision_for_category,
    review_proposal,
)
from humanhand.domain.beacon_proposals import BeaconProposal, ProposalKind, create_proposal
from humanhand.domain.beacon_types import (
    BeaconStatus,
    BeaconTriggerType,
    EvidenceTrustTier,
    create_trigger,
)
from humanhand.domain.types import DomainError
from humanhand.infra.beacon.policy_loader import (
    load_allowed_actions,
    load_blocked_actions,
    load_trust_tiers,
)

_ALLOWED = load_allowed_actions()
_BLOCKED = load_blocked_actions()

_RESOURCES_DIR = (
    Path(__file__).resolve().parents[3] / "src" / "humanhand" / "resources" / "policies"
)


def _resource_actions(filename: str) -> frozenset[str]:
    raw = json.loads((_RESOURCES_DIR / filename).read_text(encoding="utf-8"))
    actions = raw["actions"]
    assert isinstance(actions, dict)
    return frozenset(actions)


def _resource_tiers(filename: str) -> dict[str, str]:
    raw = json.loads((_RESOURCES_DIR / filename).read_text(encoding="utf-8"))
    tiers = raw["tiers"]
    assert isinstance(tiers, dict)
    return {name: entry["description"] for name, entry in tiers.items()}


def make_proposal(kind: ProposalKind = ProposalKind.METADATA_FIELD) -> BeaconProposal:
    trigger = create_trigger(
        BeaconTriggerType.SECURITY_ADVISORY,
        "A security advisory affects a bundled parser dependency.",
    )
    evidence = EvidenceSet(
        items=(
            create_evidence(
                trigger_id=trigger.trigger_id,
                tier=EvidenceTrustTier.TIER_4_TECHNICAL_ANALYSIS,
                source_kind="advisory",
                summary="Vendor advisory analysis",
                url="https://example.org/advisory-2026-08",
                snippet_sha256="a" * 64,
            ),
        )
    )
    return create_proposal(
        trigger=trigger,
        kind=kind,
        summary="Proposal summary for policy review.",
        evidence=evidence,
        high_impact=False,
    )


class TestLoadedResources:
    def test_allowed_actions_match_resource_file(self) -> None:
        assert load_allowed_actions() == _resource_actions("beacon-allowed-actions.json")

    def test_blocked_actions_match_resource_file(self) -> None:
        assert load_blocked_actions() == _resource_actions("beacon-blocked-actions.json")

    def test_blocked_actions_include_every_mandatory_action(self) -> None:
        assert MANDATORY_BLOCKED_ACTIONS.issubset(_BLOCKED)
        assert len(_BLOCKED) == len(MANDATORY_BLOCKED_ACTIONS)

    def test_allowed_actions_match_the_kind_categories(self) -> None:
        categories = {action_category_for_kind(kind) for kind in ProposalKind}
        assert categories == _ALLOWED

    def test_trust_tiers_match_resource_file(self) -> None:
        assert load_trust_tiers() == _resource_tiers("trusted-source-tiers.json")

    def test_trust_tiers_cover_all_enum_tiers(self) -> None:
        assert set(load_trust_tiers()) == {tier.value for tier in EvidenceTrustTier}

    def test_loads_are_deterministic(self) -> None:
        assert load_allowed_actions() == load_allowed_actions()
        assert load_blocked_actions() == load_blocked_actions()
        assert load_trust_tiers() == load_trust_tiers()

    @pytest.mark.parametrize(
        "mutation",
        (
            {"schema": "wrong"},
            {"schema_version": 99},
            {"actions": {}},
        ),
    )
    def test_allowed_resource_schema_fails_closed(self, mutation: dict[str, object]) -> None:
        resource = json.loads(
            (_RESOURCES_DIR / "beacon-allowed-actions.json").read_text(encoding="utf-8")
        )
        resource.update(mutation)
        with pytest.raises(DomainError):
            load_allowed_actions_from_resource(resource)

    def test_allowed_resource_requires_curated_provenance(self) -> None:
        resource = json.loads(
            (_RESOURCES_DIR / "beacon-allowed-actions.json").read_text(encoding="utf-8")
        )
        resource["actions"]["metadata_field_addition"]["provenance"] = "external"
        with pytest.raises(DomainError, match="provenance"):
            load_allowed_actions_from_resource(resource)


class TestFirewall:
    @pytest.mark.parametrize("blocked", sorted(_BLOCKED))
    def test_every_blocked_action_is_blocked(self, blocked: str) -> None:
        decision = policy_decision_for_category(
            blocked, allowed_actions=_ALLOWED, blocked_actions=_BLOCKED
        )
        assert decision.decision == "block"
        assert decision.reasons
        assert "blocked by policy" in decision.reasons[0]

    @pytest.mark.parametrize("allowed", sorted(_ALLOWED))
    def test_every_allowed_action_is_allowed(self, allowed: str) -> None:
        decision = policy_decision_for_category(
            allowed, allowed_actions=_ALLOWED, blocked_actions=_BLOCKED
        )
        assert decision.decision == "allow"
        assert "allowed by policy" in decision.reasons[0]

    def test_unknown_category_is_blocked_with_documented_reason(self) -> None:
        decision = policy_decision_for_category(
            "not_a_real_category", allowed_actions=_ALLOWED, blocked_actions=_BLOCKED
        )
        assert decision.decision == "block"
        assert "not in the allowed or blocked" in decision.reasons[0]

    def test_blocked_wins_over_allowed(self) -> None:
        decision = policy_decision_for_category(
            "metadata_field_addition",
            allowed_actions=_ALLOWED,
            blocked_actions=_BLOCKED | {"metadata_field_addition"},
        )
        assert decision.decision == "block"


class TestReviewProposal:
    def test_review_blocks_when_category_is_in_blocked_set(self) -> None:
        reviewed = review_proposal(
            make_proposal(ProposalKind.METADATA_FIELD),
            allowed_actions=_ALLOWED,
            blocked_actions=_BLOCKED | {"metadata_field_addition"},
        )
        assert reviewed.status is BeaconStatus.POLICY_REVIEWED
        assert reviewed.blocked_action is True
        assert reviewed.status.value != BeaconStatus.APPROVED.value
        assert "decision=block" in reviewed.policy_note
        assert "'metadata_field_addition'" in reviewed.policy_note

    def test_review_never_approves_a_blocked_proposal(self) -> None:
        reviewed = review_proposal(
            make_proposal(ProposalKind.METADATA_FIELD),
            allowed_actions=_ALLOWED,
            blocked_actions=_BLOCKED | {"metadata_field_addition"},
        )
        for status in (BeaconStatus.APPROVED, BeaconStatus.RELEASE_APPROVED):
            assert reviewed.status is not status

    @pytest.mark.parametrize("kind", list(ProposalKind))
    def test_allowed_proposals_pass_with_policy_note(self, kind: ProposalKind) -> None:
        reviewed = review_proposal(
            make_proposal(kind),
            allowed_actions=_ALLOWED,
            blocked_actions=_BLOCKED,
        )
        assert reviewed.status is BeaconStatus.POLICY_REVIEWED
        assert reviewed.blocked_action is False
        assert "decision=allow" in reviewed.policy_note
        assert action_category_for_kind(kind) in reviewed.policy_note
        assert reviewed.policy_note.startswith("policy_mode=private_audited")

    def test_unknown_category_is_reviewed_but_never_approved(self) -> None:
        reviewed = review_proposal(
            make_proposal(ProposalKind.METADATA_FIELD),
            allowed_actions=frozenset(),
            blocked_actions=frozenset(),
        )
        assert reviewed.status is BeaconStatus.POLICY_REVIEWED
        assert reviewed.blocked_action is False
        assert reviewed.status.value != BeaconStatus.APPROVED.value
        assert "decision=block" in reviewed.policy_note
        assert "not in the allowed or blocked" in reviewed.policy_note

    def test_review_returns_a_new_proposal_without_mutating_the_input(self) -> None:
        proposal = make_proposal()
        reviewed = review_proposal(proposal, allowed_actions=_ALLOWED, blocked_actions=_BLOCKED)
        assert reviewed is not proposal
        assert proposal.status is BeaconStatus.PROPOSED
        assert proposal.policy_note == ""

    def test_review_is_deterministic(self) -> None:
        first = review_proposal(make_proposal(), allowed_actions=_ALLOWED, blocked_actions=_BLOCKED)
        second = review_proposal(
            make_proposal(), allowed_actions=_ALLOWED, blocked_actions=_BLOCKED
        )
        assert first == second
        assert first.policy_note == second.policy_note

    def test_policy_mode_is_recorded_in_the_note(self) -> None:
        default = review_proposal(
            make_proposal(), allowed_actions=_ALLOWED, blocked_actions=_BLOCKED
        )
        assert "policy_mode=private_audited" in default.policy_note
        custom = review_proposal(
            make_proposal(),
            allowed_actions=_ALLOWED,
            blocked_actions=_BLOCKED,
            policy_mode="strict_local",
        )
        assert "policy_mode=strict_local" in custom.policy_note

    def test_review_re_evaluates_any_incoming_status(self) -> None:
        approved = replace(make_proposal(), status=BeaconStatus.APPROVED)
        reviewed = review_proposal(approved, allowed_actions=_ALLOWED, blocked_actions=_BLOCKED)
        assert reviewed.status is BeaconStatus.POLICY_REVIEWED
