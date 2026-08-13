"""Deterministic style comparison of a document against a voice profile (EP-014).

Blueprint 8.6: a comparison reports evidence coverage, hard invariant
violations, metric distances, outlier sentences and paragraphs, lexical
preference conflicts, formatting conflicts, confidence, and sample
sufficiency — and never draws an authorship conclusion. Everything is
computed from the profile and the document surface with pure stdlib.

Documented formulas
-------------------
- Metric distances (7 documented keys): ``sentence_mean``,
  ``sentence_stdev``, ``type_token_ratio``, ``function_word_ratio``,
  ``contraction_frequency``, ``punctuation_per_100_chars``, and
  ``question_frequency``. Each distance is
  ``abs(profile - document) / max(profile, document, 1.0)`` clipped to
  ``[0, 1]``; identical values always yield exactly 0.0.
- Hard invariant violations: only DASH_TYPE, CONTRACTION_POLICY,
  PERSON_POLICY, and QUOTATION_CONVENTION are comparable. A violation is
  recorded when the profile invariant status is PASS and the document
  value differs, with evidence ``profile=<value> document=<value>``.
- Outliers: sentences and paragraphs whose length is more than two sample
  standard deviations from the profile mean (z-score > 2). When the
  profile shows no length variance there is no scale, so no outliers are
  scored. Outliers are reported as lengths (never prose) in document
  order, capped at 10 sentences and 5 paragraphs.
- Lexical preference conflicts: profile preferred-terminology bigrams
  absent from the document, case-insensitive, in first-seen order.
- Formatting conflicts: ``dash: <profile> vs <document>`` and
  ``quotation: <profile> vs <document>`` strings.
- confidence = min(1.0, document_words / 5000) * (1 - mean(distances)).
- evidence_coverage = min(1.0, document_words / 1000).
- authorship_status derives from the profile coverage: ``resolved`` when
  every span is resolved, else ``unresolved``. No authorship conclusion
  is ever drawn about the compared document.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from humanhand.domain.canonical_document import CanonicalDocument
from humanhand.domain.style import _split_paragraphs, _split_sentences, _tokenize_words
from humanhand.domain.style_coverage import StyleCoverageReport
from humanhand.domain.style_invariants import (
    InvariantKind,
    InvariantStatus,
    StyleInvariant,
    extract_invariants,
)
from humanhand.domain.style_metrics import StyleMetricsBundle, compute_all_metrics
from humanhand.domain.style_profiles import StyleEvidenceProfile
from humanhand.domain.types import DomainError

STYLE_COMPARISON_SCHEMA_VERSION = 1

_METRIC_PATH_KEYS = (
    "sentence_mean",
    "sentence_stdev",
    "type_token_ratio",
    "function_word_ratio",
    "contraction_frequency",
    "punctuation_per_100_chars",
    "question_frequency",
)

_COMPARABLE_KINDS = (
    InvariantKind.DASH_TYPE,
    InvariantKind.CONTRACTION_POLICY,
    InvariantKind.PERSON_POLICY,
    InvariantKind.QUOTATION_CONVENTION,
)

_SENTENCE_OUTLIER_LIMIT = 10
_PARAGRAPH_OUTLIER_LIMIT = 5
_OUTLIER_Z_THRESHOLD = 2.0

_CONFIDENCE_WORDS = 5000.0
_EVIDENCE_WORDS = 1000.0


@dataclass(frozen=True)
class StyleComparisonReport:
    """Deterministic comparison of one document against one voice profile.

    The report is an evidence record, not a verdict: it carries coverage,
    distances, violations, conflicts, and confidence, and never an
    authorship conclusion (blueprint 8.6, SPEC-011).
    """

    schema_version: int
    profile_id: str
    coverage: StyleCoverageReport
    authorship_status: str  # "resolved" | "unresolved" (profile evidence, not a verdict)
    hard_invariant_violations: tuple[StyleInvariant, ...]
    metric_distances: dict[str, float]
    outlier_sentences: tuple[str, ...]  # lengths in document order
    outlier_paragraphs: tuple[str, ...]  # sentence counts in document order
    lexical_preference_conflicts: tuple[str, ...]
    formatting_conflicts: tuple[str, ...]
    confidence: float
    evidence_coverage: float
    sample_sufficiency: str  # "sufficient" | "insufficient"


def compare_profile(
    profile: StyleEvidenceProfile,
    document: CanonicalDocument,
    *,
    min_words_for_sufficiency: int = 1000,
) -> StyleComparisonReport:
    """Compare a document against a profile without concluding authorship.

    Args:
        profile: The voice profile to compare against.
        document: The canonical document (surface text) to compare.
        min_words_for_sufficiency: Minimum document word count for the
            comparison sample to be considered sufficient.

    Returns:
        A deterministic :class:`StyleComparisonReport`.
    """
    document_text = document.surface_text
    document_metrics = compute_all_metrics(document_text)
    document_invariants = extract_invariants(document_text, document_metrics)
    document_word_count = document_metrics.word_count

    violations, formatting = _invariant_violations(profile.hard_invariants, document_invariants)
    distances = _metric_distances(profile, document_text, document_metrics)
    outlier_sentences = _sentence_outliers(document_text, profile.metrics)
    outlier_paragraphs = _paragraph_outliers(document_text, profile.metrics)
    lexical_conflicts = _lexical_conflicts(profile.hard_invariants, document_text)

    mean_distance = _mean(distances.values())
    confidence = min(1.0, document_word_count / _CONFIDENCE_WORDS) * (1.0 - mean_distance)
    evidence_coverage = min(1.0, document_word_count / _EVIDENCE_WORDS)
    sample_sufficiency = (
        "sufficient" if document_word_count >= min_words_for_sufficiency else "insufficient"
    )
    authorship_status = "resolved" if profile.coverage.unresolved_span_count == 0 else "unresolved"
    return StyleComparisonReport(
        schema_version=STYLE_COMPARISON_SCHEMA_VERSION,
        profile_id=profile.profile_id,
        coverage=profile.coverage,
        authorship_status=authorship_status,
        hard_invariant_violations=violations,
        metric_distances=distances,
        outlier_sentences=outlier_sentences,
        outlier_paragraphs=outlier_paragraphs,
        lexical_preference_conflicts=lexical_conflicts,
        formatting_conflicts=formatting,
        confidence=confidence,
        evidence_coverage=evidence_coverage,
        sample_sufficiency=sample_sufficiency,
    )


def _metric_distances(
    profile: StyleEvidenceProfile,
    document_text: str,
    document_metrics: StyleMetricsBundle,
) -> dict[str, float]:
    """Compute the seven documented unit distances in fixed key order."""
    distances: dict[str, float] = {}
    for key in _METRIC_PATH_KEYS:
        profile_value = _metric_value(profile.metrics, key, profile.voice_text)
        document_value = _metric_value(document_metrics, key, document_text)
        distances[key] = _distance(profile_value, document_value)
    return distances


def _metric_value(metrics: StyleMetricsBundle, key: str, text: str) -> float:
    """Read one documented metric path from a metrics bundle.

    Raises:
        DomainError: If ``key`` is not one of the documented paths.
    """
    if key == "sentence_mean":
        return metrics.syntax.sentence_length_distribution.mean
    if key == "sentence_stdev":
        return metrics.syntax.sentence_length_distribution.stdev
    if key == "type_token_ratio":
        return metrics.lexical.type_token_ratio
    if key == "function_word_ratio":
        return metrics.lexical.function_word_ratio
    if key == "contraction_frequency":
        return metrics.lexical.contraction_frequency
    if key == "punctuation_per_100_chars":
        total_punctuation = sum(metrics.punctuation.counts.values())
        return total_punctuation / max(len(text), 1) * 100.0
    if key == "question_frequency":
        return metrics.questions.question_frequency
    raise DomainError(f"Unknown comparison metric path: {key}")


def _distance(profile_value: float, document_value: float) -> float:
    """Unit distance between two metric values, clipped to [0, 1]."""
    return min(abs(profile_value - document_value) / max(profile_value, document_value, 1.0), 1.0)


def _invariant_violations(
    profile_invariants: tuple[StyleInvariant, ...],
    document_invariants: tuple[StyleInvariant, ...],
) -> tuple[tuple[StyleInvariant, ...], tuple[str, ...]]:
    """Compare the comparable invariants, returning violations and conflicts."""
    profile_by_kind = {invariant.kind: invariant for invariant in profile_invariants}
    document_by_kind = {invariant.kind: invariant for invariant in document_invariants}
    violations: list[StyleInvariant] = []
    formatting: list[str] = []
    for kind in _COMPARABLE_KINDS:
        profile_invariant = profile_by_kind.get(kind)
        document_invariant = document_by_kind.get(kind)
        if profile_invariant is None or document_invariant is None:
            continue
        if profile_invariant.status is not InvariantStatus.PASS:
            continue
        if profile_invariant.value == document_invariant.value:
            continue
        evidence = f"profile={profile_invariant.value} document={document_invariant.value}"
        violations.append(
            StyleInvariant(
                kind=kind,
                value=profile_invariant.value,
                status=InvariantStatus.VIOLATED,
                evidence=evidence,
            )
        )
        if kind is InvariantKind.DASH_TYPE:
            formatting.append(f"dash: {profile_invariant.value} vs {document_invariant.value}")
        elif kind is InvariantKind.QUOTATION_CONVENTION:
            formatting.append(f"quotation: {profile_invariant.value} vs {document_invariant.value}")
    return tuple(violations), tuple(formatting)


def _sentence_outliers(text: str, metrics: StyleMetricsBundle) -> tuple[str, ...]:
    """Sentence lengths (in words) more than 2 profile stdevs from the mean."""
    distribution = metrics.syntax.sentence_length_distribution
    lengths = [len(_tokenize_words(sentence)) for sentence in _split_sentences(text)]
    return _outlier_counts(lengths, distribution.mean, distribution.stdev, _SENTENCE_OUTLIER_LIMIT)


def _paragraph_outliers(text: str, metrics: StyleMetricsBundle) -> tuple[str, ...]:
    """Paragraph sentence counts more than 2 profile stdevs from the mean."""
    distribution = metrics.rhythm.paragraph_length_distribution
    lengths = [len(_split_sentences(paragraph)) for paragraph in _split_paragraphs(text)]
    return _outlier_counts(lengths, distribution.mean, distribution.stdev, _PARAGRAPH_OUTLIER_LIMIT)


def _outlier_counts(lengths: list[int], mean: float, stdev: float, limit: int) -> tuple[str, ...]:
    """Score lengths by |z|, keep the most extreme within the cap, output in order."""
    if stdev <= 0.0:
        return ()
    scored = [(index, abs((length - mean) / stdev), length) for index, length in enumerate(lengths)]
    candidates = [item for item in scored if item[1] > _OUTLIER_Z_THRESHOLD]
    selected = sorted(candidates, key=lambda item: (-item[1], -item[2]))[:limit]
    selected.sort(key=lambda item: item[0])
    return tuple(str(lengths[item[0]]) for item in selected)


def _lexical_conflicts(
    invariants: tuple[StyleInvariant, ...], document_text: str
) -> tuple[str, ...]:
    """Profile preferred-terminology bigrams missing from the document."""
    lowered = document_text.lower()
    conflicts: list[str] = []
    seen: set[str] = set()
    for invariant in invariants:
        if invariant.kind is not InvariantKind.PREFERRED_TERMINOLOGY:
            continue
        for term in invariant.value.split("|"):
            candidate = term.strip()
            if not candidate or candidate.lower() in lowered or candidate in seen:
                continue
            seen.add(candidate)
            conflicts.append(candidate)
        break
    return tuple(conflicts)


def _mean(values: Iterable[float]) -> float:
    """Arithmetic mean; 0.0 for an empty sample."""
    total = 0.0
    count = 0
    for value in values:
        total += value
        count += 1
    if count == 0:
        return 0.0
    return total / count
