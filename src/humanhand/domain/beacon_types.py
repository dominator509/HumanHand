"""Research Beacon trigger types, evidence tiers, and workflow states (blueprint 13.1-13.4).

Defines the shared enums, the ``BeaconTrigger`` record, and the deterministic
trigger workflow state machine. No wall-clock time is ever used:
``observed_at_note`` is a source note string (for example an advisory id or
release date), never a timestamp.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum

from humanhand.domain.types import DomainError

_TRIGGER_ID_PREFIX = "trig-"
_TRIGGER_ID_HEX_LENGTH = 24


class BeaconTriggerType(StrEnum):
    """The ten documented Beacon trigger types (blueprint 13.1)."""

    ARTIFACT_METADATA_REGRESSION = "artifact_metadata_regression"
    PARSER_EXPORTER_DEPENDENCY_UPDATE = "parser_exporter_dependency_update"
    TOKENIZER_RULE_PACK_CHANGE = "tokenizer_rule_pack_change"
    NEW_STANDARDS_RELEASE = "new_standards_release"
    RUNTIME_TELEMETRY_CHANGE = "runtime_telemetry_change"
    NEW_PROVENANCE_MECHANISM = "new_provenance_mechanism"
    REPEATED_SYNTHETIC_SCANNER_DRIFT = "repeated_synthetic_scanner_drift"
    STYLE_PROFILE_REGRESSION = "style_profile_regression"
    TRAINING_MEMORIZATION_RESEARCH_UPDATE = "training_memorization_research_update"
    SECURITY_ADVISORY = "security_advisory"


class EvidenceTrustTier(StrEnum):
    """The five evidence trust tiers (blueprint 13.2)."""

    TIER_1_OFFICIAL_SPEC = "tier1_official_spec"
    TIER_2_PEER_REVIEWED = "tier2_peer_reviewed"
    TIER_3_PREPRINT_OR_RELEASE_NOTES = "tier3_preprint_or_release_notes"
    TIER_4_TECHNICAL_ANALYSIS = "tier4_technical_analysis"
    TIER_5_COMMUNITY_LEAD = "tier5_community_lead"


class BeaconStatus(StrEnum):
    """Workflow statuses of one Beacon trigger/proposal (blueprint 13.4)."""

    OBSERVED = "observed"
    TRIAGED = "triaged"
    RESEARCHED = "researched"
    VERIFIED = "verified"
    PROPOSED = "proposed"
    POLICY_REVIEWED = "policy_reviewed"
    APPROVED = "approved"
    DENIED = "denied"
    QUARANTINED = "quarantined"
    VALIDATED = "validated"
    RELEASE_APPROVED = "release_approved"


@dataclass(frozen=True)
class BeaconTrigger:
    """One deterministic research trigger.

    ``trigger_id`` is ``"trig-" + sha256(type, summary, observed_at_note)[:24]``.
    ``observed_at_note`` is a source note, never a wall-clock timestamp.
    """

    trigger_id: str
    trigger_type: BeaconTriggerType
    summary: str
    observed_at_note: str = ""


def create_trigger(
    trigger_type: BeaconTriggerType, summary: str, observed_at_note: str = ""
) -> BeaconTrigger:
    """Create a trigger with a deterministic id derived from its content."""
    if not summary.strip():
        raise DomainError("Beacon trigger summary must not be empty")
    encoded = "\x00".join((trigger_type.value, summary, observed_at_note)).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()[:_TRIGGER_ID_HEX_LENGTH]
    return BeaconTrigger(
        trigger_id=f"{_TRIGGER_ID_PREFIX}{digest}",
        trigger_type=trigger_type,
        summary=summary,
        observed_at_note=observed_at_note,
    )


#: Deterministic approve-path state machine (blueprint 13.4). The deny path is
#: an explicit human decision that sets ``DENIED`` directly; ``DENIED`` and
#: ``RELEASE_APPROVED`` are terminal states.
_TRIGGER_FLOW: dict[BeaconStatus, BeaconStatus] = {
    BeaconStatus.OBSERVED: BeaconStatus.TRIAGED,
    BeaconStatus.TRIAGED: BeaconStatus.RESEARCHED,
    BeaconStatus.RESEARCHED: BeaconStatus.VERIFIED,
    BeaconStatus.VERIFIED: BeaconStatus.PROPOSED,
    BeaconStatus.PROPOSED: BeaconStatus.POLICY_REVIEWED,
    BeaconStatus.POLICY_REVIEWED: BeaconStatus.APPROVED,
    BeaconStatus.APPROVED: BeaconStatus.QUARANTINED,
    BeaconStatus.QUARANTINED: BeaconStatus.VALIDATED,
    BeaconStatus.VALIDATED: BeaconStatus.RELEASE_APPROVED,
}


def trigger_flow_next(status: BeaconStatus) -> BeaconStatus:
    """Return the next workflow state (blueprint 13.4 approve path).

    The linear flow is: observed -> triaged -> researched -> verified ->
    proposed -> policy_reviewed -> approved -> quarantined -> validated ->
    release_approved. The deny path (``DENIED``) is set by an explicit human
    decision and never advanced here. Raises DomainError for the terminal
    states (``DENIED``, ``RELEASE_APPROVED``) and for any unknown value.
    """
    if status not in _TRIGGER_FLOW:
        raise DomainError(
            f"Trigger workflow has no next state from {status.value!r} (terminal or unknown state)"
        )
    return _TRIGGER_FLOW[status]
