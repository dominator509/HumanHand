"""Research Beacon evidence records and the trust-tier sufficiency rule (blueprint 13.2).

Evidence records carry only a ``snippet_sha256`` digest; the snippet text
itself lives in the snapshot store and never in the domain record. Only
public ``https://`` URLs are accepted.

The documented source-kind to trust-tier mapping is:

- ``official_spec`` -> Tier 1 (official standard/vendor specification)
- ``paper`` -> Tier 2 (peer-reviewed primary research)
- ``release_notes`` -> Tier 3 (primary preprint or official release notes)
- ``advisory`` -> Tier 4 (reputable vendor or security advisory analysis)
- ``community`` -> Tier 5 (community report used only as a lead)

The mapping is the documented default; the explicit ``tier`` field on the
record is authoritative (for example a preprint paper carries
``source_kind="paper"`` with tier 3).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from humanhand.domain.beacon_types import EvidenceTrustTier
from humanhand.domain.types import DomainError

_EVIDENCE_ID_PREFIX = "ev-"
_EVIDENCE_ID_HEX_LENGTH = 24
_SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")

#: Documented source-kind to default trust-tier mapping (blueprint 13.2).
_SOURCE_KIND_TIER: dict[str, EvidenceTrustTier] = {
    "official_spec": EvidenceTrustTier.TIER_1_OFFICIAL_SPEC,
    "paper": EvidenceTrustTier.TIER_2_PEER_REVIEWED,
    "release_notes": EvidenceTrustTier.TIER_3_PREPRINT_OR_RELEASE_NOTES,
    "advisory": EvidenceTrustTier.TIER_4_TECHNICAL_ANALYSIS,
    "community": EvidenceTrustTier.TIER_5_COMMUNITY_LEAD,
}


def tier_for_source_kind(source_kind: str) -> EvidenceTrustTier:
    """Return the documented default tier for a source kind.

    Unknown source kinds raise DomainError (fail closed).
    """
    if source_kind not in _SOURCE_KIND_TIER:
        raise DomainError(f"Unknown evidence source kind: {source_kind!r}")
    return _SOURCE_KIND_TIER[source_kind]


@dataclass(frozen=True)
class BeaconEvidence:
    """One piece of traceable public evidence.

    ``evidence_id`` is ``"ev-" + sha256(content fields)[:24]``. Only public
    URLs are permitted; ``snippet_sha256`` is the sha256 hex digest of the
    captured snippet text (the snippet itself lives in the snapshot store).
    """

    evidence_id: str
    trigger_id: str
    tier: EvidenceTrustTier
    source_kind: str
    summary: str
    url: str
    snippet_sha256: str


def create_evidence(
    *,
    trigger_id: str,
    tier: EvidenceTrustTier,
    source_kind: str,
    summary: str,
    url: str,
    snippet_sha256: str,
) -> BeaconEvidence:
    """Create an evidence record with a deterministic id derived from its content."""
    if not trigger_id:
        raise DomainError("Evidence trigger_id must not be empty")
    if not summary.strip():
        raise DomainError("Evidence summary must not be empty")
    if not url.startswith("https://"):
        raise DomainError("Evidence url must be a public https:// URL")
    if _SHA256_HEX_PATTERN.fullmatch(snippet_sha256) is None:
        raise DomainError("Evidence snippet_sha256 must be 64 lowercase hex characters")
    tier_for_source_kind(source_kind)  # fail closed on unknown source kinds
    encoded = "\x00".join(
        (trigger_id, tier.value, source_kind, url, snippet_sha256, summary)
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()[:_EVIDENCE_ID_HEX_LENGTH]
    return BeaconEvidence(
        evidence_id=f"{_EVIDENCE_ID_PREFIX}{digest}",
        trigger_id=trigger_id,
        tier=tier,
        source_kind=source_kind,
        summary=summary,
        url=url,
        snippet_sha256=snippet_sha256,
    )


@dataclass(frozen=True)
class EvidenceSet:
    """An immutable set of evidence for one proposal."""

    items: tuple[BeaconEvidence, ...]

    def __post_init__(self) -> None:
        if len({item.evidence_id for item in self.items}) != len(self.items):
            raise DomainError("EvidenceSet contains duplicate evidence ids")


def high_impact_sufficient(evidence: EvidenceSet, *, high_impact: bool) -> bool:
    """Blueprint 13.2 sufficiency rule, implemented exactly.

    High-impact proposals need ONE Tier-1 source OR TWO independent Tier-2/3
    sources. Independence is defined deterministically as distinct public
    URLs. Non-high-impact proposals need at least one Tier 1-4 source.
    """
    if high_impact:
        if any(item.tier is EvidenceTrustTier.TIER_1_OFFICIAL_SPEC for item in evidence.items):
            return True
        tier_two_or_three = [
            item
            for item in evidence.items
            if item.tier
            in (
                EvidenceTrustTier.TIER_2_PEER_REVIEWED,
                EvidenceTrustTier.TIER_3_PREPRINT_OR_RELEASE_NOTES,
            )
        ]
        return len({item.url for item in tier_two_or_three}) >= 2
    return any(
        item.tier
        in (
            EvidenceTrustTier.TIER_1_OFFICIAL_SPEC,
            EvidenceTrustTier.TIER_2_PEER_REVIEWED,
            EvidenceTrustTier.TIER_3_PREPRINT_OR_RELEASE_NOTES,
            EvidenceTrustTier.TIER_4_TECHNICAL_ANALYSIS,
        )
        for item in evidence.items
    )


_EVIDENCE_SCHEMA_NAME = "beacon-evidence"
EVIDENCE_SCHEMA_VERSION = 1


def evidence_to_payload(evidence: BeaconEvidence) -> dict[str, object]:
    """Render one evidence record as a stable JSON-ready payload."""
    return {
        "schema": _EVIDENCE_SCHEMA_NAME,
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "evidence_id": evidence.evidence_id,
        "trigger_id": evidence.trigger_id,
        "tier": evidence.tier.value,
        "source_kind": evidence.source_kind,
        "summary": evidence.summary,
        "url": evidence.url,
        "snippet_sha256": evidence.snippet_sha256,
    }


def _expect_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise DomainError(f"Invalid beacon evidence payload: {key} must be a string")
    return value


def evidence_from_payload(payload: dict[str, object]) -> BeaconEvidence:
    """Deserialize and validate an evidence payload (strict, fails closed).

    Rejects payloads whose ``evidence_id`` does not match the deterministic
    id recomputed from the payload content.
    """
    if payload.get("schema") != _EVIDENCE_SCHEMA_NAME:
        raise DomainError("Invalid beacon evidence payload: schema must be 'beacon-evidence'")
    if payload.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        raise DomainError("Unsupported beacon evidence payload schema version")
    tier_value = _expect_str(payload, "tier")
    try:
        tier = EvidenceTrustTier(tier_value)
    except ValueError as exc:
        raise DomainError(f"Invalid beacon evidence payload: unknown tier {tier_value!r}") from exc
    evidence = create_evidence(
        trigger_id=_expect_str(payload, "trigger_id"),
        tier=tier,
        source_kind=_expect_str(payload, "source_kind"),
        summary=_expect_str(payload, "summary"),
        url=_expect_str(payload, "url"),
        snippet_sha256=_expect_str(payload, "snippet_sha256"),
    )
    if evidence.evidence_id != _expect_str(payload, "evidence_id"):
        raise DomainError("Invalid beacon evidence payload: evidence_id does not match content")
    return evidence
