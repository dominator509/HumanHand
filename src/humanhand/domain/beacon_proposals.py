"""Research Beacon proposal records, payloads, and the evidence gate (blueprint 13.4).

Proposals start at ``PROPOSED`` status. ``blocked_action`` and ``policy_note``
are set only by policy review, never by the author. Proposal ids are
deterministic: ``"prop-" + sha256(content)[:24]``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from enum import StrEnum

from humanhand.domain.beacon_evidence import (
    BeaconEvidence,
    EvidenceSet,
    evidence_from_payload,
    evidence_to_payload,
    high_impact_sufficient,
)
from humanhand.domain.beacon_types import BeaconStatus, BeaconTrigger
from humanhand.domain.types import DomainError

_PROPOSAL_ID_PREFIX = "prop-"
_PROPOSAL_ID_HEX_LENGTH = 24
_PROPOSAL_SCHEMA_NAME = "beacon-proposal"
PROPOSAL_SCHEMA_VERSION = 1


class ProposalKind(StrEnum):
    """The seven documented proposal kinds."""

    METADATA_FIELD = "metadata_field"
    CONTAINER_MECHANISM = "container_mechanism"
    PROVENANCE_STANDARD = "provenance_standard"
    TELEMETRY_CHANGE = "telemetry_change"
    PARSER_EXPORTER_CHANGE = "parser_exporter_change"
    PRIVACY_TECHNIQUE = "privacy_technique"
    SCANNER_BENCHMARK_CHANGE = "scanner_benchmark_change"


@dataclass(frozen=True)
class BeaconProposal:
    """One research proposal derived from a trigger and its evidence.

    ``blocked_action`` is True only when policy review matched a blocked
    action; it is never set by the author. ``policy_note`` records the
    policy review finding.
    """

    proposal_id: str
    trigger_id: str
    kind: ProposalKind
    summary: str
    high_impact: bool
    evidence: EvidenceSet
    status: BeaconStatus = BeaconStatus.PROPOSED
    blocked_action: bool = False
    policy_note: str = ""


def _proposal_id_for(proposal: BeaconProposal) -> str:
    """Deterministic proposal id: sha256 of the content fields, 24 hex chars."""
    encoded = "\x00".join(
        (
            proposal.trigger_id,
            proposal.kind.value,
            proposal.summary,
            "high_impact" if proposal.high_impact else "not_high_impact",
            *[item.evidence_id for item in proposal.evidence.items],
        )
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()[:_PROPOSAL_ID_HEX_LENGTH]
    return f"{_PROPOSAL_ID_PREFIX}{digest}"


def create_proposal(
    *,
    trigger: BeaconTrigger,
    kind: ProposalKind,
    summary: str,
    evidence: EvidenceSet,
    high_impact: bool,
) -> BeaconProposal:
    """Create a proposal at ``PROPOSED`` status.

    Raises DomainError when evidence is insufficient under the blueprint
    13.2 rule. High-impact proposals require one Tier-1 source or two
    independent Tier-2/3 sources; other proposals require one Tier 1-4 source.
    """
    if high_impact and not high_impact_sufficient(evidence, high_impact=True):
        raise DomainError(
            "High-impact proposal requires one Tier-1 source or two independent Tier-2/3 sources"
        )
    if not high_impact and not high_impact_sufficient(evidence, high_impact=False):
        raise DomainError("Proposal requires at least one Tier 1-4 evidence source")
    if not summary.strip():
        raise DomainError("Proposal summary must not be empty")
    proposal = BeaconProposal(
        proposal_id="",
        trigger_id=trigger.trigger_id,
        kind=kind,
        summary=summary,
        high_impact=high_impact,
        evidence=evidence,
        status=BeaconStatus.PROPOSED,
        blocked_action=False,
        policy_note="",
    )
    return replace(proposal, proposal_id=_proposal_id_for(proposal))


def proposal_to_payload(proposal: BeaconProposal) -> dict[str, object]:
    """Render a proposal as a stable JSON-ready payload."""
    return {
        "schema": _PROPOSAL_SCHEMA_NAME,
        "schema_version": PROPOSAL_SCHEMA_VERSION,
        "proposal_id": proposal.proposal_id,
        "trigger_id": proposal.trigger_id,
        "kind": proposal.kind.value,
        "summary": proposal.summary,
        "high_impact": proposal.high_impact,
        "evidence": {"items": [evidence_to_payload(item) for item in proposal.evidence.items]},
        "status": proposal.status.value,
        "blocked_action": proposal.blocked_action,
        "policy_note": proposal.policy_note,
    }


def _expect_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise DomainError(f"Invalid beacon proposal payload: {key} must be a string")
    return value


def _expect_bool(payload: dict[str, object], key: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise DomainError(f"Invalid beacon proposal payload: {key} must be a boolean")
    return value


def proposal_from_payload(payload: dict[str, object]) -> BeaconProposal:
    """Deserialize and validate a proposal payload (strict, fails closed).

    Rejects payloads whose ``proposal_id`` does not match the deterministic
    id recomputed from the payload content.
    """
    if payload.get("schema") != _PROPOSAL_SCHEMA_NAME:
        raise DomainError("Invalid beacon proposal payload: schema must be 'beacon-proposal'")
    if payload.get("schema_version") != PROPOSAL_SCHEMA_VERSION:
        raise DomainError("Unsupported beacon proposal payload schema version")

    kind_value = _expect_str(payload, "kind")
    status_value = _expect_str(payload, "status")
    try:
        kind = ProposalKind(kind_value)
        status = BeaconStatus(status_value)
    except ValueError as exc:
        raise DomainError("Invalid beacon proposal payload: unknown enum value") from exc

    raw_evidence = payload.get("evidence")
    if not isinstance(raw_evidence, dict):
        raise DomainError("Invalid beacon proposal payload: evidence must be an object")
    raw_items = raw_evidence.get("items")
    if not isinstance(raw_items, list):
        raise DomainError("Invalid beacon proposal payload: evidence.items must be a list")
    items: list[BeaconEvidence] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            raise DomainError("Invalid beacon proposal payload: evidence items must be objects")
        items.append(evidence_from_payload(raw_item))

    proposal = BeaconProposal(
        proposal_id=_expect_str(payload, "proposal_id"),
        trigger_id=_expect_str(payload, "trigger_id"),
        kind=kind,
        summary=_expect_str(payload, "summary"),
        high_impact=_expect_bool(payload, "high_impact"),
        evidence=EvidenceSet(items=tuple(items)),
        status=status,
        blocked_action=_expect_bool(payload, "blocked_action"),
        policy_note=_expect_str(payload, "policy_note"),
    )
    if proposal.proposal_id != _proposal_id_for(proposal):
        raise DomainError("Invalid beacon proposal payload: proposal_id does not match content")
    return proposal
