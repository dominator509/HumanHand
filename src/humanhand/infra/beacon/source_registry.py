"""Research Beacon source registry (blueprint 13.2/13.3).

``DEFAULT_SOURCES`` is the frozen, evidence-verified registry of external
research sources the beacon may consult. Every URL was verified against the
live site during EP-018 implementation; nothing here is guessed or
placeholder content.

Tier strings match the stable ``EvidenceTrustTier`` serialized values.
"""

from __future__ import annotations

from dataclasses import dataclass

# Evidence tier constants (documented strings; see module docstring).
TIER_OFFICIAL_SPECIFICATION = "tier1_official_spec"
TIER_PEER_REVIEWED_RESEARCH = "tier2_peer_reviewed"
TIER_PREPRINT_OR_RELEASE_NOTES = "tier3_preprint_or_release_notes"
TIER_TECHNICAL_ANALYSIS = "tier4_technical_analysis"
TIER_COMMUNITY_LEAD = "tier5_community_lead"


@dataclass(frozen=True)
class RegisteredSource:
    """One registered, evidence-verified research source."""

    name: str
    url: str
    tier: str


DEFAULT_SOURCES: tuple[RegisteredSource, ...] = (
    RegisteredSource(
        name="ecma-376",
        url="https://ecma-international.org/publications-and-standards/standards/ecma-376/",
        tier=TIER_OFFICIAL_SPECIFICATION,
    ),
    RegisteredSource(
        name="iso-iec-29500-1",
        url="https://www.iso.org/standard/71691.html",
        tier=TIER_OFFICIAL_SPECIFICATION,
    ),
    RegisteredSource(
        name="iso-32000-2",
        url="https://www.iso.org/standard/75839.html",
        tier=TIER_OFFICIAL_SPECIFICATION,
    ),
    RegisteredSource(
        name="oasis-opendocument-1.2",
        url="https://docs.oasis-open.org/office/v1.2/os/OpenDocument-v1.2-os.html",
        tier=TIER_OFFICIAL_SPECIFICATION,
    ),
    RegisteredSource(
        name="whatwg-html",
        url="https://html.spec.whatwg.org/multipage/",
        tier=TIER_OFFICIAL_SPECIFICATION,
    ),
    RegisteredSource(
        name="nvd",
        url="https://nvd.nist.gov/",
        tier=TIER_OFFICIAL_SPECIFICATION,
    ),
    RegisteredSource(
        name="pypdf-docs",
        url="https://pypdf.readthedocs.io/en/stable/",
        tier=TIER_PREPRINT_OR_RELEASE_NOTES,
    ),
    RegisteredSource(
        name="xai-docs",
        url="https://docs.x.ai/",
        tier=TIER_PREPRINT_OR_RELEASE_NOTES,
    ),
    RegisteredSource(
        name="arxiv",
        url="https://arxiv.org/",
        tier=TIER_PREPRINT_OR_RELEASE_NOTES,
    ),
    RegisteredSource(
        name="owasp-xxe-cheatsheet",
        url=(
            "https://cheatsheetseries.owasp.org/cheatsheets/"
            "XML_External_Entity_Prevention_Cheat_Sheet.html"
        ),
        tier=TIER_TECHNICAL_ANALYSIS,
    ),
)

_SOURCES_BY_NAME: dict[str, RegisteredSource] = {source.name: source for source in DEFAULT_SOURCES}

# Trigger -> source names (blueprint 13.1). Scanner drift never consults
# external sources; unknown triggers fail closed to an empty selection.
_TRIGGER_SOURCE_NAMES: dict[str, tuple[str, ...]] = {
    "parser_exporter_dependency_update": ("pypdf-docs", "nvd"),
    "style_profile_regression": ("arxiv", "nvd"),
    "training_memorization_research_update": ("arxiv", "ecma-376"),
    "security_advisory": (
        "nvd",
        "owasp-xxe-cheatsheet",
        "iso-iec-29500-1",
        "iso-32000-2",
    ),
}


def sources_for_trigger(trigger_type: str) -> tuple[RegisteredSource, ...]:
    """Return the registered sources relevant to a beacon trigger type.

    Deterministic: sources are returned in ``DEFAULT_SOURCES`` order. Unknown
    trigger types (including ``repeated_synthetic_scanner_drift``, which is
    locally observed) yield an empty tuple.
    """
    names = _TRIGGER_SOURCE_NAMES.get(trigger_type, ())
    return tuple(_SOURCES_BY_NAME[name] for name in names)
