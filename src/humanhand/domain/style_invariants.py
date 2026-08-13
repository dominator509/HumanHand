"""Style invariant and soft-tendency extraction (blueprint 8.5).

Hard invariants are observed conventions, never judgments. Extraction
records what a sample does (for example ``double_curly`` quotation or
``contractions_present``); violations are only detectable by later
comparison against a target profile, never by extraction alone. The one
deliberate exception is HEADING_CAPITALIZATION, which is not extractable
from plain text at all and is therefore always UNKNOWN.

Metrics come from :mod:`humanhand.domain.style_metrics` as a
``StyleMetricsBundle`` produced by ``compute_all_metrics(text)``. This
module reads only the bundle fields named in the EP-014 contract:

- ``metrics.punctuation.quote_convention`` (str)
- ``metrics.punctuation.dash_convention`` (str)
- ``metrics.lexical.contraction_frequency`` (float)
- ``metrics.lexical.pronoun_distribution`` (Mapping[str, int])
- ``metrics.lexical.type_token_ratio`` (float)
- ``metrics.rhythm.paragraph_length_distribution`` (Distribution)
- ``metrics.rhythm.transition_counts`` (Mapping[str, int])
- ``metrics.syntax.sentence_length_distribution`` (Distribution)

Distributions are the ``Distribution`` summary from style_metrics; this
module reads only ``count``, ``minimum``, ``maximum``, ``p10``, ``p90``,
and ``mean`` from them. Preferred terminology, punctuation density, and
the bigram counter are computed locally from the text so they never
depend on metric internals.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from humanhand.domain.style_metrics import Distribution, StyleMetricsBundle

# Matches bracket-number citations such as "[12]" or "[12, 34, 5]".
_BRACKET_NUMBER_RE = re.compile(r"\[\d+(?:,\s*\d+)*\]")
# Matches (Author, Year) citations such as "(Smith, 2019)" or "(Smith, 2019a)".
_AUTHOR_YEAR_RE = re.compile(r"\([A-Z][A-Za-z' -]+,\s*\d{4}[a-z]?\)")
# Word tokenizer identical to the one in humanhand.domain.style.
_WORD_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+(?:'[a-zA-Z]+)?")
# Punctuation characters counted for density (documented character set).
_PUNCTUATION_CHARS = frozenset(".,;:!?…—–-()[]{}\"'’‘“”«»")


class InvariantKind(StrEnum):
    """Hard invariant kinds from blueprint 8.5."""

    QUOTATION_CONVENTION = "quotation_convention"
    CITATION_PRESENTATION = "citation_presentation"
    HEADING_CAPITALIZATION = "heading_capitalization"
    CONTRACTION_POLICY = "contraction_policy"
    PREFERRED_TERMINOLOGY = "preferred_terminology"
    PROHIBITED_PHRASES = "prohibited_phrases"
    PARAGRAPH_RANGE = "paragraph_range"
    SENTENCE_PERCENTILE_RANGE = "sentence_percentile_range"
    DASH_TYPE = "dash_type"
    PERSON_POLICY = "person_policy"


class InvariantStatus(StrEnum):
    """Extraction status of one style invariant."""

    PASS = "pass"  # nosec B105 - enum status value, not a credential
    VIOLATED = "violated"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class StyleInvariant:
    """One observed hard invariant with deterministic evidence."""

    kind: InvariantKind
    value: str  # the observed convention, e.g. "double_curly", "5..18"
    status: InvariantStatus
    evidence: str  # counts or examples, never document prose


@dataclass(frozen=True)
class StyleTendency:
    """One soft tendency with a deterministic strength."""

    name: str
    value: str
    strength: str  # "weak" | "moderate" | "strong"
    evidence: str


def extract_invariants(text: str, metrics: StyleMetricsBundle) -> tuple[StyleInvariant, ...]:
    """Extract the ten hard invariants from a sample and its metrics.

    Every invariant is returned exactly once in enum-definition order.
    Extraction never flags a violation: statuses are PASS for everything
    that is observable, UNKNOWN only for heading capitalization, and
    VIOLATED is never produced here (violations require comparison).

    Args:
        text: The style sample surface text.
        metrics: Deterministic metrics bundle for ``text``.

    Returns:
        Ten :class:`StyleInvariant` records.
    """
    quotation = metrics.punctuation.quote_convention
    dash = metrics.punctuation.dash_convention

    bracket_count = len(_BRACKET_NUMBER_RE.findall(text))
    author_year_count = len(_AUTHOR_YEAR_RE.findall(text))
    citation_value = (
        f"bracket_numbers={bracket_count},author_year={author_year_count}"
        if bracket_count or author_year_count
        else "none"
    )
    citation_evidence = f"bracket_numbers={bracket_count},author_year={author_year_count}"

    contraction_frequency = metrics.lexical.contraction_frequency
    contraction_value = "contractions_present" if contraction_frequency > 0 else "no_contractions"

    terminology_value, terminology_evidence = _preferred_terminology(text)
    paragraph_value, paragraph_evidence = _paragraph_range(
        metrics.rhythm.paragraph_length_distribution
    )
    sentence_value, sentence_evidence = _sentence_percentile_range(
        metrics.syntax.sentence_length_distribution
    )
    person_value, person_evidence = _person_policy(metrics.lexical.pronoun_distribution)

    return (
        StyleInvariant(
            kind=InvariantKind.QUOTATION_CONVENTION,
            value=quotation,
            status=InvariantStatus.PASS,
            evidence=quotation,
        ),
        StyleInvariant(
            kind=InvariantKind.CITATION_PRESENTATION,
            value=citation_value,
            status=InvariantStatus.PASS,
            evidence=citation_evidence,
        ),
        StyleInvariant(
            kind=InvariantKind.HEADING_CAPITALIZATION,
            value="",
            status=InvariantStatus.UNKNOWN,
            evidence="not_extractable_from_plain_text",
        ),
        StyleInvariant(
            kind=InvariantKind.CONTRACTION_POLICY,
            value=contraction_value,
            status=InvariantStatus.PASS,
            evidence=f"{contraction_frequency:.4f}",
        ),
        StyleInvariant(
            kind=InvariantKind.PREFERRED_TERMINOLOGY,
            value=terminology_value,
            status=InvariantStatus.PASS,
            evidence=terminology_evidence,
        ),
        StyleInvariant(
            kind=InvariantKind.PROHIBITED_PHRASES,
            value="",
            status=InvariantStatus.PASS,
            evidence="none_configured",
        ),
        StyleInvariant(
            kind=InvariantKind.PARAGRAPH_RANGE,
            value=paragraph_value,
            status=InvariantStatus.PASS,
            evidence=paragraph_evidence,
        ),
        StyleInvariant(
            kind=InvariantKind.SENTENCE_PERCENTILE_RANGE,
            value=sentence_value,
            status=InvariantStatus.PASS,
            evidence=sentence_evidence,
        ),
        StyleInvariant(
            kind=InvariantKind.DASH_TYPE,
            value=dash,
            status=InvariantStatus.PASS,
            evidence=dash,
        ),
        StyleInvariant(
            kind=InvariantKind.PERSON_POLICY,
            value=person_value,
            status=InvariantStatus.PASS,
            evidence=person_evidence,
        ),
    )


def extract_tendencies(text: str, metrics: StyleMetricsBundle) -> tuple[StyleTendency, ...]:
    """Extract the four soft tendencies (blueprint 8.5).

    Tendencies are deterministic summaries that guide comparison scores
    but never block output. They are returned in a fixed order:
    sentence-length band, top transition, punctuation density, and
    lexical richness.

    Sentence-length band: ``short`` when the mean is below 12 words,
    ``medium`` in 12..25, ``long`` above 25. Strength measures how deep
    the mean sits inside its band: distance to the nearest band edge
    divided by half the band width; strong at >= 2/3, moderate at >= 1/3,
    weak near an edge. Bands are [0, 12), [12, 25], and (25, 40] with 40
    the nominal outer edge of the long band; values outside the nominal
    span are treated as deep (strong).

    Top transition: the transition with the highest count from
    ``metrics.rhythm.transition_counts``, ties broken alphabetically.
    Strength by share of the total: strong at >= 1/3, moderate at >= 1/6,
    weak below.

    Punctuation density: punctuation characters per 100 characters
    counted locally with the documented character set; ``low`` below 8,
    ``moderate`` in 8..16, ``high`` above 16. Strength uses the same
    edge-distance formula with bands [0, 8], [8, 16], (16, 24].

    Lexical richness: ``low`` when type_token_ratio is below 0.35,
    ``moderate`` in 0.35..0.55, ``high`` above 0.55. Strength uses the
    same edge-distance formula with bands [0, 0.35], [0.35, 0.55],
    (0.55, 1.0].

    Args:
        text: The style sample surface text.
        metrics: Deterministic metrics bundle for ``text``.

    Returns:
        Four :class:`StyleTendency` records.
    """
    return (
        _sentence_length_tendency(metrics.syntax.sentence_length_distribution),
        _top_transition_tendency(metrics.rhythm.transition_counts),
        _punctuation_density_tendency(text),
        _lexical_richness_tendency(metrics.lexical.type_token_ratio),
    )


def _preferred_terminology(text: str) -> tuple[str, str]:
    """Return (value, evidence) for the top three lowercased bigrams.

    Bigrams are counted over the whole lowercased token stream of the
    text (the same approach as ``domain/style.py``). Ties keep
    first-seen order, which is deterministic for a fixed input.
    """
    words = _WORD_TOKEN_RE.findall(text.lower())
    bigrams = Counter(" ".join(words[i : i + 2]) for i in range(len(words) - 1))
    top = bigrams.most_common(3)
    value = "|".join(term for term, _count in top)
    evidence = "counts=" + ",".join(str(count) for _term, count in top) if top else "counts=0"
    return value, evidence


def _paragraph_range(paragraph_length_distribution: Distribution) -> tuple[str, str]:
    """Return (value, evidence) for the min..max sentences per paragraph."""
    if paragraph_length_distribution.count == 0:
        return "none", "paragraphs=0"
    low = _fmt_number(paragraph_length_distribution.minimum)
    high = _fmt_number(paragraph_length_distribution.maximum)
    return (
        f"{low}..{high}",
        f"paragraphs={paragraph_length_distribution.count}",
    )


def _sentence_percentile_range(
    sentence_length_distribution: Distribution,
) -> tuple[str, str]:
    """Return (value, evidence) for the p10..p90 sentence length range."""
    if sentence_length_distribution.count == 0:
        return "none", "sentences=0"
    p10 = _fmt_number(sentence_length_distribution.p10)
    p90 = _fmt_number(sentence_length_distribution.p90)
    return (
        f"{p10}..{p90}",
        f"sentences={sentence_length_distribution.count}",
    )


def _fmt_number(value: float) -> str:
    """Format a number as int when whole, else with one decimal."""
    rounded = round(value, 1)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.1f}"


def _person_policy(pronoun_distribution: Mapping[str, int]) -> tuple[str, str]:
    """Return (value, evidence) summarizing pronoun usage per category."""
    keys = sorted(pronoun_distribution)
    if not keys:
        return "none", "categories=0"
    value = "|".join(
        f"{key}=present" if pronoun_distribution[key] > 0 else f"{key}=absent" for key in keys
    )
    evidence = ",".join(f"{key}={pronoun_distribution[key]}" for key in keys)
    return value, evidence


def _sentence_length_tendency(
    sentence_length_distribution: Distribution,
) -> StyleTendency:
    """Sentence-length band tendency (formula documented in module docstring)."""
    mean = sentence_length_distribution.mean
    count = sentence_length_distribution.count
    if mean < 12.0:
        band = "short"
        strength = _band_strength(mean, 0.0, 12.0)
    elif mean <= 25.0:
        band = "medium"
        strength = _band_strength(mean, 12.0, 25.0)
    else:
        band = "long"
        strength = _band_strength(mean, 25.0, 40.0)
    return StyleTendency(
        name="sentence_length_band",
        value=band,
        strength=strength,
        evidence=f"mean={mean:.2f},sentences={count}",
    )


def _top_transition_tendency(transition_counts: Mapping[str, int]) -> StyleTendency:
    """Top transition tendency; ties break alphabetically, strength by share."""
    if not transition_counts:
        return StyleTendency(
            name="top_transition",
            value="none",
            strength="weak",
            evidence="transitions=0",
        )
    ordered = sorted(transition_counts.items(), key=lambda item: (-item[1], item[0]))
    top_key, top_count = ordered[0]
    total = sum(transition_counts.values())
    share = top_count / total if total else 0.0
    if share >= 1.0 / 3.0:
        strength = "strong"
    elif share >= 1.0 / 6.0:
        strength = "moderate"
    else:
        strength = "weak"
    return StyleTendency(
        name="top_transition",
        value=top_key,
        strength=strength,
        evidence=f"{top_key}={top_count},transitions={total}",
    )


def _punctuation_density_tendency(text: str) -> StyleTendency:
    """Punctuation density per 100 characters, counted locally."""
    total = sum(1 for char in text if char in _PUNCTUATION_CHARS)
    density = total / max(len(text), 1) * 100.0
    if density < 8.0:
        band = "low"
        strength = _band_strength(density, 0.0, 8.0)
    elif density <= 16.0:
        band = "moderate"
        strength = _band_strength(density, 8.0, 16.0)
    else:
        band = "high"
        strength = _band_strength(density, 16.0, 24.0)
    return StyleTendency(
        name="punctuation_density",
        value=band,
        strength=strength,
        evidence=f"density={density:.2f},chars={len(text)}",
    )


def _lexical_richness_tendency(type_token_ratio: float) -> StyleTendency:
    """Lexical richness band from the type-token ratio."""
    if type_token_ratio < 0.35:
        band = "low"
        strength = _band_strength(type_token_ratio, 0.0, 0.35)
    elif type_token_ratio <= 0.55:
        band = "moderate"
        strength = _band_strength(type_token_ratio, 0.35, 0.55)
    else:
        band = "high"
        strength = _band_strength(type_token_ratio, 0.55, 1.0)
    return StyleTendency(
        name="lexical_richness",
        value=band,
        strength=strength,
        evidence=f"ttr={type_token_ratio:.4f}",
    )


def _band_strength(value: float, low: float, high: float) -> str:
    """Strength from distance to the nearest band edge (documented formula).

    ``value`` is expected inside ``[low, high]``. Distance to the nearest
    edge is clamped to half the band width, so values at the edges are
    weak and values deep inside (or beyond the nominal span) are strong.
    """
    half_width = (high - low) / 2.0
    distance = min(value - low, high - value)
    distance = min(max(distance, 0.0), half_width)
    ratio = distance / half_width if half_width > 0 else 1.0
    if ratio >= 2.0 / 3.0:
        return "strong"
    if ratio >= 1.0 / 3.0:
        return "moderate"
    return "weak"
