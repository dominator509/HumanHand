"""Fact anchor extraction and factual drift detection."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from humanhand.domain.types import FactAnchor, FactDiffReport


def extract_fact_anchors(text: str) -> list[FactAnchor]:
    """Extract factual anchors from text.

    Detects numbers, dates, named-entity-like spans, quoted phrases,
    citation-like markers, and claim sentences.

    Args:
        text: Source or candidate text.

    Returns:
        List of FactAnchor objects sorted by position.
    """
    if not text:
        return []

    anchors: list[FactAnchor] = []

    # Numbers (integers, decimals, percentages, currency)
    for m in re.finditer(
        r"\b\d+(?:\.\d+)?%?\b|\$\d+(?:,\d{3})*(?:\.\d+)?|\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b",
        text,
    ):
        anchors.append(FactAnchor(text=m.group(), category="number", position=m.start()))

    # Dates (ISO, US, written forms)
    for m in re.finditer(
        r"\b\d{4}-\d{2}-\d{2}\b|\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}\b|"
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
        text,
    ):
        anchors.append(FactAnchor(text=m.group(), category="date", position=m.start()))

    # Named-entity-like spans (capitalized multi-word sequences)
    for m in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,4}\b", text):
        anchors.append(FactAnchor(text=m.group(), category="entity", position=m.start()))

    # Quoted phrases
    for m in re.finditer(r'"([^"]{3,})"', text):
        anchors.append(FactAnchor(text=m.group(1), category="quote", position=m.start()))

    # Citation-like markers [1], (Author, Year), etc.
    for m in re.finditer(
        r"\[\d+(?:,\s*\d+)*\]|\([A-Z][a-z]+(?:\s+(?:et\s+al\.?|&\s+[A-Z][a-z]+))?,?\s*\d{4}[a-z]?\)",
        text,
    ):
        anchors.append(FactAnchor(text=m.group(), category="citation", position=m.start()))

    # Sort by position
    anchors.sort(key=lambda a: a.position)
    return anchors


def _anchor_similarity(a: FactAnchor, b: FactAnchor) -> float:
    """Compute similarity between two fact anchors (0.0 to 1.0)."""
    if a.category != b.category:
        return 0.0
    return SequenceMatcher(None, a.text.lower(), b.text.lower()).ratio()


def diff_facts(source: str, candidate: str) -> FactDiffReport:
    """Compare factual anchors between source and candidate text.

    Args:
        source: Original source text.
        candidate: Rewritten candidate text.

    Returns:
        FactDiffReport with omissions, additions, contradictions, and score.
    """
    source_anchors = extract_fact_anchors(source)
    candidate_anchors = extract_fact_anchors(candidate)

    source_set = list(source_anchors)
    candidate_set = list(candidate_anchors)

    omissions: list[FactAnchor] = []
    contradictions: list[tuple[FactAnchor, FactAnchor]] = []
    additions: list[FactAnchor] = []
    matched_source: set[int] = set()
    matched_candidate: set[int] = set()

    # Match source anchors to candidate anchors
    similarity_threshold = 0.7
    for si, sa in enumerate(source_set):
        best_match: tuple[int, float] | None = None
        for ci, ca in enumerate(candidate_set):
            if ci in matched_candidate:
                continue
            sim = _anchor_similarity(sa, ca)
            if sim > similarity_threshold and (best_match is None or sim > best_match[1]):
                best_match = (ci, sim)

        if best_match is not None:
            matched_source.add(si)
            matched_candidate.add(best_match[0])
            # If similarity is below 0.9, flag as potential contradiction
            if best_match[1] < 0.9:
                contradictions.append((sa, candidate_set[best_match[0]]))
        else:
            omissions.append(sa)

    # Unmatched candidate anchors are additions
    for ci, ca in enumerate(candidate_set):
        if ci not in matched_candidate:
            additions.append(ca)

    total_source = len(source_set)
    total_candidate = len(candidate_set)

    # Preservation score: proportion of source anchors preserved
    if total_source > 0:
        matched_count = len(matched_source)
        preservation = matched_count / total_source
    else:
        preservation = 1.0

    return FactDiffReport(
        omissions=tuple(omissions),
        additions=tuple(additions),
        contradictions=tuple(contradictions),
        preservation_score=round(preservation, 4),
        total_source_anchors=total_source,
        total_candidate_anchors=total_candidate,
    )
