"""Claim V2 — deterministic fact-integrity claims built from source packages.

Claim V2 supersedes the V1 fact-anchor heuristics in
:mod:`humanhand.domain.facts`: each protected span of a source package
becomes exactly one claim whose canonical proposition is the span's exact
protected text, with deterministic modality and negation flags and no
invented attribution or confidence values.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from humanhand.domain.protected_spans import ProtectedSpan, SpanKind
from humanhand.domain.source_package import SourcePackage
from humanhand.domain.types import DomainError


class Modality(StrEnum):
    """How a claim is asserted in its source text."""

    ASSERTED = "asserted"
    HEDGED = "hedged"
    CONDITIONAL = "conditional"
    REPORTED = "reported"


class ClaimStatus(StrEnum):
    """Review state of one claim."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CONTRADICTED = "contradicted"


class CoverageStatus(StrEnum):
    """Whether claim coverage of the source package is established."""

    KNOWN = "known"
    UNKNOWN_COVERAGE = "unknown_coverage"


#: Whole-word negation markers (case-insensitive) shared by claim
#: extraction and claim diffing.
NEGATION_MARKER_WORDS: tuple[str, ...] = (
    "not",
    "no",
    "never",
    "none",
    "neither",
    "cannot",
    "isn't",
    "aren't",
    "wasn't",
    "weren't",
    "doesn't",
    "don't",
    "didn't",
)

_MODAL_MARKER_WORDS: tuple[str, ...] = (
    "may",
    "might",
    "could",
    "perhaps",
    "possibly",
    "likely",
    "appears",
    "suggests",
)

_MODAL_RE = re.compile(rf"\b(?:{'|'.join(_MODAL_MARKER_WORDS)})\b", re.IGNORECASE)
_CONDITIONAL_RE = re.compile(r"^(?:if)\b|\b(?:unless|when)\b", re.IGNORECASE)
_NEGATION_RE = re.compile(rf"\b(?:{'|'.join(NEGATION_MARKER_WORDS)})\b", re.IGNORECASE)

#: Span kinds that become claims. UNIT and ENTITY spans never become
#: claims on their own.
_CLAIM_SPAN_KINDS: frozenset[SpanKind] = frozenset(
    {
        SpanKind.NUMBER,
        SpanKind.DATE,
        SpanKind.QUOTATION,
        SpanKind.CITATION,
        SpanKind.KEY_TERM,
    }
)


@dataclass(frozen=True)
class ClaimV2:
    """One deterministic claim derived from a protected source span.

    ``attribution`` is never invented: extraction leaves it empty until a
    later stage attaches an attribution from actual evidence. ``confidence``
    is None (unknown) for the same reason.
    """

    claim_id: str
    canonical_proposition: str
    modality: Modality
    negation: bool
    attribution: str
    source_evidence_refs: tuple[str, ...]
    confidence: float | None
    status: ClaimStatus = ClaimStatus.PROPOSED
    contradictions: tuple[str, ...] = ()
    allowed_paraphrase_scope: str = "exact"


def _modality_for_span(span: ProtectedSpan) -> Modality:
    """Determine a span's claim modality under the documented precedence.

    Precedence, first match wins:
    1. QUOTATION spans are always REPORTED: modal words inside a quotation
       belong to the quoted speaker, not to the claim's own voice.
    2. A span whose text starts with ``if``, or contains an ``unless`` or
       ``when`` clause, is CONDITIONAL.
    3. A span containing any modal marker word (may, might, could, perhaps,
       possibly, likely, appears, suggests; whole words, case-insensitive)
       is HEDGED.
    4. Otherwise ASSERTED.
    """
    if span.kind is SpanKind.QUOTATION:
        return Modality.REPORTED
    if _CONDITIONAL_RE.search(span.text) is not None:
        return Modality.CONDITIONAL
    if _MODAL_RE.search(span.text) is not None:
        return Modality.HEDGED
    return Modality.ASSERTED


def _contains_negation(text: str) -> bool:
    """True when the text contains any negation marker as a whole word."""
    return _NEGATION_RE.search(text) is not None


def build_claims_from_package(
    package: SourcePackage,
    *,
    coverage_status: CoverageStatus = CoverageStatus.UNKNOWN_COVERAGE,
) -> tuple[tuple[ClaimV2, ...], CoverageStatus]:
    """Extract claims deterministically from a source package's evidence.

    Rules (deterministic, no model):
    - Each protected span with kind NUMBER, DATE, QUOTATION, CITATION, or
      KEY_TERM becomes one claim whose canonical proposition is the span's
      exact protected text. Other span kinds (UNIT, ENTITY) never become
      claims on their own.
    - Modality follows the precedence in :func:`_modality_for_span`:
      QUOTATION -> REPORTED; ``if``/``unless``/``when`` -> CONDITIONAL;
      modal marker words -> HEDGED; otherwise ASSERTED.
    - Negation is True when the proposition contains any negation marker
      (not, no, never, none, neither, cannot, isn't, aren't, wasn't,
      weren't, doesn't, don't, didn't) as a whole word, case-insensitive.
    - Attribution is always "" and confidence is always None: extraction
      never invents an attribution or a confidence value.
    - ``claim_id`` is ``cl{n}`` with n starting at 1, assigned in span
      document order (the order of the package's protected span set).
    - ``source_evidence_refs`` is the single source span id and
      ``allowed_paraphrase_scope`` is "exact" (the span text must not be
      paraphrased beyond exact reuse of the protected text).
    - ``coverage_status`` is returned unchanged. With zero protected spans
      the caller MUST pass UNKNOWN_COVERAGE (the default) so that an empty
      claim set never reads as complete coverage; the function never
      guesses the status on the caller's behalf.
    """
    claims: list[ClaimV2] = []
    for span in package.evidence.protected_spans.spans:
        if span.kind not in _CLAIM_SPAN_KINDS:
            continue
        claims.append(
            ClaimV2(
                claim_id=f"cl{len(claims) + 1}",
                canonical_proposition=span.text,
                modality=_modality_for_span(span),
                negation=_contains_negation(span.text),
                attribution="",
                source_evidence_refs=(span.span_id,),
                confidence=None,
            )
        )
    return tuple(claims), coverage_status


def claims_to_payload(
    claims: tuple[ClaimV2, ...], coverage_status: CoverageStatus
) -> dict[str, object]:
    """Render claims and their coverage status as a plain JSON-ready mapping."""
    return {
        "coverage_status": coverage_status.value,
        "claims": [
            {
                "claim_id": claim.claim_id,
                "canonical_proposition": claim.canonical_proposition,
                "modality": claim.modality.value,
                "negation": claim.negation,
                "attribution": claim.attribution,
                "source_evidence_refs": list(claim.source_evidence_refs),
                "confidence": claim.confidence,
                "status": claim.status.value,
                "contradictions": list(claim.contradictions),
                "allowed_paraphrase_scope": claim.allowed_paraphrase_scope,
            }
            for claim in claims
        ],
    }


def claims_from_payload(payload: dict[str, object]) -> tuple[tuple[ClaimV2, ...], CoverageStatus]:
    """Deserialize and strictly validate a claims payload.

    Raises DomainError on a missing or malformed ``claims`` list, a missing
    ``coverage_status``, any unknown enum value (modality, status,
    coverage status), or any field of the wrong type.
    """
    raw_coverage = payload.get("coverage_status")
    if not isinstance(raw_coverage, str):
        raise DomainError("Claims payload must include a coverage_status string")
    try:
        coverage_status = CoverageStatus(raw_coverage)
    except ValueError as exc:
        raise DomainError(f"Unknown coverage status: {raw_coverage!r}") from exc
    raw_claims = payload.get("claims")
    if not isinstance(raw_claims, list):
        raise DomainError("Claims payload must include a claims list")
    claims: list[ClaimV2] = []
    for item in raw_claims:
        if not isinstance(item, dict):
            raise DomainError("Each claim must be an object")
        claim_id = item.get("claim_id")
        if not isinstance(claim_id, str):
            raise DomainError("claim_id must be a string")
        proposition = item.get("canonical_proposition")
        if not isinstance(proposition, str):
            raise DomainError("canonical_proposition must be a string")
        raw_modality = item.get("modality")
        if not isinstance(raw_modality, str):
            raise DomainError("modality must be a string")
        try:
            modality = Modality(raw_modality)
        except ValueError as exc:
            raise DomainError(f"Unknown modality: {raw_modality!r}") from exc
        negation = item.get("negation")
        if not isinstance(negation, bool):
            raise DomainError("negation must be a boolean")
        attribution = item.get("attribution")
        if not isinstance(attribution, str):
            raise DomainError("attribution must be a string")
        raw_refs = item.get("source_evidence_refs")
        if not isinstance(raw_refs, list) or not all(isinstance(ref, str) for ref in raw_refs):
            raise DomainError("source_evidence_refs must be a list of strings")
        raw_confidence = item.get("confidence")
        if raw_confidence is not None and (
            not isinstance(raw_confidence, (int, float)) or isinstance(raw_confidence, bool)
        ):
            raise DomainError("confidence must be a number or null")
        raw_status = item.get("status")
        if not isinstance(raw_status, str):
            raise DomainError("status must be a string")
        try:
            status = ClaimStatus(raw_status)
        except ValueError as exc:
            raise DomainError(f"Unknown claim status: {raw_status!r}") from exc
        raw_contradictions = item.get("contradictions")
        if not isinstance(raw_contradictions, list) or not all(
            isinstance(ref, str) for ref in raw_contradictions
        ):
            raise DomainError("contradictions must be a list of strings")
        scope = item.get("allowed_paraphrase_scope")
        if not isinstance(scope, str):
            raise DomainError("allowed_paraphrase_scope must be a string")
        claims.append(
            ClaimV2(
                claim_id=claim_id,
                canonical_proposition=proposition,
                modality=modality,
                negation=negation,
                attribution=attribution,
                source_evidence_refs=tuple(raw_refs),
                confidence=float(raw_confidence) if raw_confidence is not None else None,
                status=status,
                contradictions=tuple(raw_contradictions),
                allowed_paraphrase_scope=scope,
            )
        )
    return tuple(claims), coverage_status
