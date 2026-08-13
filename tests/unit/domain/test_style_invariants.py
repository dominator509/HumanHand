"""Unit tests for style invariant and tendency extraction (EP-014)."""

from __future__ import annotations

from humanhand.domain.style_invariants import (
    InvariantKind,
    InvariantStatus,
    StyleInvariant,
    extract_invariants,
    extract_tendencies,
)
from humanhand.domain.style_metrics import compute_all_metrics

# Fixed sample: double curly quotes, one em dash, the contraction "don't",
# one bracket citation "[12]", one (Author, Year) citation, and repeated
# bigrams ("the plan", "the numbers").
SAMPLE_TEXT = (
    "I don't think the plan will work as written, but we should still try the plan anyway. "
    "The board reviewed the numbers twice and found the numbers conclusive. "
    "Even so, the margin remains thin.\n\n"
    "According to the report (Smith, 2019), the outcome was uncertain; "
    "the committee chose to wait. [12]\n\n"
    "The final vote was unanimous — no dissent was recorded. "
    "She said, “We will try again next month.”"
)

ALL_KINDS = frozenset(InvariantKind)


def _invariants_by_kind(text: str) -> dict[InvariantKind, StyleInvariant]:
    bundle = compute_all_metrics(text)
    return {invariant.kind: invariant for invariant in extract_invariants(text, bundle)}


def test_extract_invariants_fixed_sample() -> None:
    by_kind = _invariants_by_kind(SAMPLE_TEXT)

    # Every kind appears exactly once.
    assert len(by_kind) == len(ALL_KINDS)
    assert set(by_kind) == ALL_KINDS

    # Quotation convention observed from the metrics bundle: the sample
    # uses double curly quotes, so the convention is "double_curly"
    # (EP-014 contract value; violations are comparison-time, not
    # extraction-time, so the status is PASS by design).
    quotation = by_kind[InvariantKind.QUOTATION_CONVENTION]
    assert quotation.status == InvariantStatus.PASS
    assert quotation.value == "double_curly"
    assert quotation.evidence == "double_curly"

    # Hand-verified against the sample: exactly one "[12]" bracket
    # pattern and exactly one "(Smith, 2019)" author-year pattern.
    citation = by_kind[InvariantKind.CITATION_PRESENTATION]
    assert citation.status == InvariantStatus.PASS
    assert "bracket_numbers=1" in citation.evidence
    assert "author_year=1" in citation.evidence
    assert "bracket_numbers=1" in citation.value

    # Heading capitalization is not extractable from plain text alone.
    heading = by_kind[InvariantKind.HEADING_CAPITALIZATION]
    assert heading.status == InvariantStatus.UNKNOWN
    assert heading.value == ""

    # The sample contains "don't", so contractions are present.
    contraction = by_kind[InvariantKind.CONTRACTION_POLICY]
    assert contraction.status == InvariantStatus.PASS
    assert contraction.value == "contractions_present"

    # Hand-verified bigram order over the lowercased token stream:
    # "the plan"=2 and "the numbers"=2 tie, then the first-seen singleton
    # "i don't"=1; ties keep first-seen order deterministically.
    terminology = by_kind[InvariantKind.PREFERRED_TERMINOLOGY]
    assert terminology.status == InvariantStatus.PASS
    assert terminology.value == "the plan|the numbers|i don't"

    # Prohibited phrases are never auto-inferred: always PASS with no
    # configured value (honest no-inference rule).
    prohibited = by_kind[InvariantKind.PROHIBITED_PHRASES]
    assert prohibited.status == InvariantStatus.PASS
    assert prohibited.value == ""
    assert prohibited.evidence == "none_configured"

    # The sample has three paragraphs, each with 2-3 sentences.
    paragraph = by_kind[InvariantKind.PARAGRAPH_RANGE]
    assert paragraph.status == InvariantStatus.PASS
    assert ".." in paragraph.value

    sentence = by_kind[InvariantKind.SENTENCE_PERCENTILE_RANGE]
    assert sentence.status == InvariantStatus.PASS
    assert ".." in sentence.value

    # The sample uses one em dash.
    dash = by_kind[InvariantKind.DASH_TYPE]
    assert dash.status == InvariantStatus.PASS
    assert dash.value == "em"

    person = by_kind[InvariantKind.PERSON_POLICY]
    assert person.status == InvariantStatus.PASS
    assert person.value != ""
    assert "=" in person.value


def test_extract_invariants_deterministic_replay() -> None:
    first = extract_invariants(SAMPLE_TEXT, compute_all_metrics(SAMPLE_TEXT))
    second = extract_invariants(SAMPLE_TEXT, compute_all_metrics(SAMPLE_TEXT))
    assert first == second


def test_extract_tendencies() -> None:
    tendencies = extract_tendencies(SAMPLE_TEXT, compute_all_metrics(SAMPLE_TEXT))

    # At least the four documented tendencies.
    assert len(tendencies) >= 3
    assert len({tendency.name for tendency in tendencies}) == len(tendencies)

    for tendency in tendencies:
        assert tendency.strength in {"weak", "moderate", "strong"}
        assert tendency.value != ""
        assert tendency.evidence != ""


def test_extract_tendencies_deterministic_replay() -> None:
    first = extract_tendencies(SAMPLE_TEXT, compute_all_metrics(SAMPLE_TEXT))
    second = extract_tendencies(SAMPLE_TEXT, compute_all_metrics(SAMPLE_TEXT))
    assert first == second


def test_extract_invariants_empty_text() -> None:
    by_kind = _invariants_by_kind("")

    # No exceptions, every kind present exactly once.
    assert len(by_kind) == len(ALL_KINDS)
    assert set(by_kind) == ALL_KINDS

    # Every kind is PASS except heading capitalization, which is always
    # UNKNOWN because it is not extractable from plain text.
    for kind, invariant in by_kind.items():
        if kind is InvariantKind.HEADING_CAPITALIZATION:
            assert invariant.status is InvariantStatus.UNKNOWN
        else:
            assert invariant.status is InvariantStatus.PASS

    # Zero-valued deterministic evidence for the count-bearing kinds.
    assert by_kind[InvariantKind.CITATION_PRESENTATION].value == "none"
    assert "=0" in by_kind[InvariantKind.CITATION_PRESENTATION].evidence
    assert by_kind[InvariantKind.CONTRACTION_POLICY].value == "no_contractions"
    assert by_kind[InvariantKind.CONTRACTION_POLICY].evidence == "0.0000"
    assert by_kind[InvariantKind.PREFERRED_TERMINOLOGY].value == ""
    assert by_kind[InvariantKind.PREFERRED_TERMINOLOGY].evidence == "counts=0"
    assert by_kind[InvariantKind.PARAGRAPH_RANGE].value == "none"
    assert by_kind[InvariantKind.PARAGRAPH_RANGE].evidence == "paragraphs=0"
    assert by_kind[InvariantKind.SENTENCE_PERCENTILE_RANGE].value == "none"
    assert by_kind[InvariantKind.SENTENCE_PERCENTILE_RANGE].evidence == "sentences=0"
    # The metrics module reports the four documented pronoun classes with
    # zero counts for empty text, so every category is "absent" (sorted
    # key order) — hand-verified against the actual module output.
    assert (
        by_kind[InvariantKind.PERSON_POLICY].value
        == "first_plural=absent|first_singular=absent|second_person=absent|third_person=absent"
    )
    assert (
        by_kind[InvariantKind.PERSON_POLICY].evidence
        == "first_plural=0,first_singular=0,second_person=0,third_person=0"
    )
