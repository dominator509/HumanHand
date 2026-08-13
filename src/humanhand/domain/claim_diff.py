"""Deterministic diffing of source and candidate claim sets.

Matching and contradiction detection are pure string heuristics with no
model involvement. Two claims match when their canonical propositions are
identical. Contradictions are flagged only for two documented,
deterministic patterns: a changed numeric value in an otherwise identical
proposition, and a negation flip of an otherwise identical proposition.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from humanhand.domain.claims_v2 import NEGATION_MARKER_WORDS, ClaimV2, CoverageStatus

#: Numbers and percentages: $50, 1,234, 3.5, 3.5%, 50 percent, 50 pp.
_NUMBER_RE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?(?:\s*(?:%|percent|pp)\b)?")
_NEGATION_RE = re.compile(rf"\b(?:{'|'.join(NEGATION_MARKER_WORDS)})\b", re.IGNORECASE)


@dataclass(frozen=True)
class ClaimDiffReport:
    """Deterministic claim diff between source and candidate claim sets."""

    preserved: tuple[str, ...]
    omitted: tuple[str, ...]
    added: tuple[str, ...]
    contradicted_pairs: tuple[tuple[str, str], ...]
    coverage_status: CoverageStatus


def _normalize_number(match_text: str) -> str:
    """Normalize one extracted number match to a comparable value string."""
    value = match_text.strip().lower().replace(" ", "")
    value = value.replace("$", "").replace(",", "")
    value = value.replace("percent", "%").replace("pp", "%")
    return value


def _extract_numbers(text: str) -> tuple[str, ...]:
    """Extract normalized numeric values from a proposition, in order."""
    return tuple(_normalize_number(match.group(0)) for match in _NUMBER_RE.finditer(text))


def _without_numbers(text: str) -> str:
    """The proposition with every number match removed, whitespace-normalized."""
    return " ".join(_NUMBER_RE.sub("", text).split()).lower()


def _without_negation_markers(text: str) -> str:
    """The proposition with every negation marker removed, whitespace-normalized."""
    return " ".join(_NEGATION_RE.sub("", text).split()).lower()


def _contradicts(source_claim: ClaimV2, candidate_claim: ClaimV2) -> bool:
    """True when two claims contradict under the documented heuristics.

    Both patterns are pure string comparisons; there is no model and no
    semantic inference:
    1. Numeric change: both propositions contain at least one number, the
       normalized numeric values differ, and the propositions are identical
       after every number match is removed and whitespace is collapsed.
    2. Negation flip: exactly one of the two claims is negated, and the
       propositions are identical after every negation marker (whole-word,
       case-insensitive) is removed and whitespace is collapsed.
    """
    source_text = source_claim.canonical_proposition
    candidate_text = candidate_claim.canonical_proposition
    source_numbers = _extract_numbers(source_text)
    candidate_numbers = _extract_numbers(candidate_text)
    numeric_change = (
        bool(source_numbers)
        and bool(candidate_numbers)
        and source_numbers != candidate_numbers
        and _without_numbers(source_text) == _without_numbers(candidate_text)
    )
    negation_flip = source_claim.negation != candidate_claim.negation and _without_negation_markers(
        source_text
    ) == _without_negation_markers(candidate_text)
    return numeric_change or negation_flip


def diff_claims(source: tuple[ClaimV2, ...], candidate: tuple[ClaimV2, ...]) -> ClaimDiffReport:
    """Diff a source claim set against a candidate claim set.

    Matching: a source claim and a candidate claim match when their
    canonical propositions are exactly equal. Matching is a multiset match
    in source order: each source claim takes the first still-unmatched
    candidate with the same proposition, and each claim participates in at
    most one match.

    Contradiction: after matching, each still-unmatched source claim is
    paired with the first still-unmatched candidate claim that contradicts
    it under :func:`_contradicts`; each claim participates in at most one
    contradicted pair.

    Everything still unmatched on the source side is ``omitted`` and on the
    candidate side is ``added``, both in document order. ``coverage_status``
    is KNOWN when the source set is non-empty and UNKNOWN_COVERAGE
    otherwise: with no source claims there is nothing to diff against, and
    an empty source must never read as complete coverage.
    """
    matched_source = [False] * len(source)
    matched_candidate = [False] * len(candidate)

    preserved: list[str] = []
    for source_index, source_claim in enumerate(source):
        for candidate_index, candidate_claim in enumerate(candidate):
            if matched_candidate[candidate_index]:
                continue
            if source_claim.canonical_proposition == candidate_claim.canonical_proposition:
                preserved.append(source_claim.claim_id)
                matched_source[source_index] = True
                matched_candidate[candidate_index] = True
                break

    contradicted_pairs: list[tuple[str, str]] = []
    for source_index, source_claim in enumerate(source):
        if matched_source[source_index]:
            continue
        for candidate_index, candidate_claim in enumerate(candidate):
            if matched_candidate[candidate_index]:
                continue
            if _contradicts(source_claim, candidate_claim):
                contradicted_pairs.append((source_claim.claim_id, candidate_claim.claim_id))
                matched_source[source_index] = True
                matched_candidate[candidate_index] = True
                break

    omitted = [
        source_claim.claim_id
        for source_index, source_claim in enumerate(source)
        if not matched_source[source_index]
    ]
    added = [
        candidate_claim.claim_id
        for candidate_index, candidate_claim in enumerate(candidate)
        if not matched_candidate[candidate_index]
    ]
    coverage_status = CoverageStatus.KNOWN if source else CoverageStatus.UNKNOWN_COVERAGE
    return ClaimDiffReport(
        preserved=tuple(preserved),
        omitted=tuple(omitted),
        added=tuple(added),
        contradicted_pairs=tuple(contradicted_pairs),
        coverage_status=coverage_status,
    )


def claim_diff_to_payload(report: ClaimDiffReport) -> dict[str, object]:
    """Render a claim diff report as a plain JSON-ready mapping."""
    return {
        "preserved": list(report.preserved),
        "omitted": list(report.omitted),
        "added": list(report.added),
        "contradicted_pairs": [list(pair) for pair in report.contradicted_pairs],
        "coverage_status": report.coverage_status.value,
    }
