"""Research Beacon policy firewall (ADR-006, SPEC-015).

The firewall checks a proposal's action category, derived from its kind via
the documented pure kind -> action-category map (no text mining), against
the bundled blocked and allowed action sets. The blocked set wins first;
then the allowed set; anything else is an unknown category that cannot be
approved. Review never approves on its own: it always leaves the proposal at
``POLICY_REVIEWED`` and the human approval gate stays in control.

Resource loading belongs to the infra layer; this module only validates
already-loaded resource mappings and applies the pure policy decision.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from humanhand.domain.beacon_proposals import BeaconProposal, ProposalKind
from humanhand.domain.beacon_types import BeaconStatus
from humanhand.domain.types import DomainError

#: ADR-006 invariants: these action categories can never be allowed.
MANDATORY_BLOCKED_ACTIONS = frozenset(
    {
        "upload_private_document",
        "detector_optimization",
        "provenance_destruction",
        "auto_merge",
        "auto_publish",
        "auto_deploy",
        "watermark_key_recovery",
        "code_change_without_review",
    }
)

#: Documented pure kind -> action category map (no text mining). The seven
#: categories are exactly the bundled allowed-action set.
_KIND_TO_CATEGORY: dict[ProposalKind, str] = {
    ProposalKind.METADATA_FIELD: "metadata_field_addition",
    ProposalKind.CONTAINER_MECHANISM: "container_mechanism_research",
    ProposalKind.PROVENANCE_STANDARD: "provenance_standard_research",
    ProposalKind.TELEMETRY_CHANGE: "telemetry_documentation",
    ProposalKind.PARSER_EXPORTER_CHANGE: "dependency_update_proposal",
    ProposalKind.PRIVACY_TECHNIQUE: "privacy_technique_research",
    ProposalKind.SCANNER_BENCHMARK_CHANGE: "scanner_benchmark",
}


def action_category_for_kind(kind: ProposalKind) -> str:
    """Return the documented action category for a proposal kind."""
    if kind not in _KIND_TO_CATEGORY:
        raise DomainError(f"No documented action category for proposal kind {kind.value!r}")
    return _KIND_TO_CATEGORY[kind]


@dataclass(frozen=True)
class BeaconPolicyDecision:
    """Structured firewall result for one action category."""

    decision: str  # "allow" | "block"
    reasons: tuple[str, ...]


def policy_decision_for_category(
    category: str,
    *,
    allowed_actions: frozenset[str],
    blocked_actions: frozenset[str],
) -> BeaconPolicyDecision:
    """Pure firewall: blocked set wins, then allowed, else unknown (block).

    An unknown category can never be approved: the decision is ``"block"``
    with a documented reason. The proposal-level ``blocked_action`` flag
    stays False for unknown categories because the category matched no
    blocked action.
    """
    if category in blocked_actions:
        return BeaconPolicyDecision(
            "block", (f"action category {category!r} is blocked by policy",)
        )
    if category in allowed_actions:
        return BeaconPolicyDecision(
            "allow", (f"action category {category!r} is allowed by policy",)
        )
    return BeaconPolicyDecision(
        "block",
        (f"action category {category!r} is not in the allowed or blocked action sets",),
    )


def review_proposal(
    proposal: BeaconProposal,
    *,
    allowed_actions: frozenset[str],
    blocked_actions: frozenset[str],
    policy_mode: str = "private_audited",
) -> BeaconProposal:
    """Run the policy firewall on a proposal (ADR-006).

    Returns a new proposal at ``POLICY_REVIEWED`` status. Proposals whose
    action category is in the blocked set get ``blocked_action=True`` and
    review never sets ``APPROVED``; allowed and unknown categories keep
    ``blocked_action=False``. The finding (decision, action category,
    reasons, and the policy mode used) is recorded in ``policy_note``.
    """
    category = action_category_for_kind(proposal.kind)
    decision = policy_decision_for_category(
        category, allowed_actions=allowed_actions, blocked_actions=blocked_actions
    )
    note_parts = [
        f"policy_mode={policy_mode}",
        f"decision={decision.decision}",
        f"action_category={category!r}",
    ]
    if decision.reasons:
        note_parts.append("reasons: " + "; ".join(decision.reasons))
    return replace(
        proposal,
        status=BeaconStatus.POLICY_REVIEWED,
        blocked_action=category in blocked_actions,
        policy_note="; ".join(note_parts),
    )


def load_allowed_actions_from_resource(resource: dict[str, object]) -> dict[str, str]:
    """Parse the allowed actions resource dict (pure)."""
    return _resource_descriptions(
        resource, section="actions", label="allowed actions", schema="beacon-allowed-actions"
    )


def load_blocked_actions_from_resource(resource: dict[str, object]) -> dict[str, str]:
    """Parse the blocked actions resource dict (pure)."""
    return _resource_descriptions(
        resource, section="actions", label="blocked actions", schema="beacon-blocked-actions"
    )


def load_trust_tiers_from_resource(resource: dict[str, object]) -> dict[str, str]:
    """Parse the trusted-source tiers resource dict (pure)."""
    return _resource_descriptions(
        resource,
        section="tiers",
        label="trusted-source tiers",
        schema="beacon-trusted-source-tiers",
    )


def _resource_descriptions(
    resource: dict[str, object], *, section: str, label: str, schema: str
) -> dict[str, str]:
    if set(resource) != {"schema", "schema_version", section}:
        raise DomainError(f"Invalid {label} resource fields")
    if resource.get("schema") != schema or resource.get("schema_version") != 1:
        raise DomainError(f"Invalid {label} resource schema")
    raw = resource.get(section)
    if not isinstance(raw, dict) or not raw:
        raise DomainError(f"Invalid {label} resource")
    result: dict[str, str] = {}
    for entry_name, entry in raw.items():
        if not isinstance(entry_name, str) or not entry_name:
            raise DomainError(f"Invalid {label} entry name")
        if not isinstance(entry, dict) or set(entry) != {"description", "provenance"}:
            raise DomainError(f"Invalid {label} entry: {entry_name}")
        description = entry.get("description")
        provenance = entry.get("provenance")
        if not isinstance(description, str) or not description.strip():
            raise DomainError(f"Invalid {label} description: {entry_name}")
        if provenance != "curated-in-repo":
            raise DomainError(f"Invalid {label} provenance: {entry_name}")
        result[entry_name] = description
    return result
