"""Style evidence artifacts: immutable originals, exemplars, and packages."""

from __future__ import annotations

from dataclasses import dataclass

from humanhand.domain.style_authorship import AuthorshipMap
from humanhand.domain.style_surface import CanonicalSurfaceDocument

STYLE_EVIDENCE_PACKAGE_SCHEMA_VERSION = 1
STYLE_RULESET_VERSION = "1"


@dataclass(frozen=True)
class OriginalStyleArtifact:
    """The immutable original bytes of a style sample (ADR-003).

    The vault stores bytes once under ``artifact_id``; the domain object
    carries only the identity and integrity fields, never a second copy.
    """

    artifact_id: str
    sha256: str
    size_bytes: int
    stored: bool = False


@dataclass(frozen=True)
class StyleExemplar:
    """An approved exemplar passage quoted verbatim from the sample."""

    exemplar_id: str
    text: str
    span_id: str
    note: str = ""


@dataclass(frozen=True)
class StyleEvidencePackage:
    """Style-lane evidence package (blueprint 8.1).

    Separates original, exact surface, authorship, profiles, exemplars,
    invariants, and coverage; only approved authentic spans feed metrics.
    """

    schema_version: int
    package_id: str
    profile_label: str
    original_artifact: OriginalStyleArtifact
    exact_surface: CanonicalSurfaceDocument
    authorship: AuthorshipMap
    approved_exemplars: tuple[StyleExemplar, ...]
    parser_version: str
    ruleset_version: str
    unsupported_features: tuple[str, ...] = ()
