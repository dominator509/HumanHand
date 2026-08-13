"""Unit tests for the StyleFingerprint compatibility projection."""

from __future__ import annotations

import pytest

from humanhand.domain.style import project_style_fingerprint
from humanhand.domain.style_profiles import StyleEvidenceProfile


@pytest.mark.skipif(
    not __import__("importlib.util", fromlist=["find_spec"]).find_spec(
        "humanhand.domain.style_profiles"
    ),
    reason="EP-014 profile modules not merged yet",
)
class TestProjectStyleFingerprint:
    def test_projection_from_profile(self) -> None:
        profile = _profile()
        fingerprint = project_style_fingerprint(profile)
        assert fingerprint.total_words == profile.sample_word_count
        assert fingerprint.total_sentences == (
            profile.metrics.syntax.sentence_length_distribution.count
        )
        assert fingerprint.total_paragraphs == (
            profile.metrics.rhythm.paragraph_length_distribution.count
        )
        assert fingerprint.vocabulary_richness == pytest.approx(
            round(profile.metrics.lexical.type_token_ratio, 4)
        )
        assert fingerprint.avg_word_length == pytest.approx(
            round(profile.metrics.lexical.avg_word_length, 2)
        )
        # Punctuation ratios use the true voice-text length denominator.
        total_chars = max(len(profile.voice_text), 1)
        expected_period = round(profile.metrics.punctuation.counts.get(".", 0) / total_chars, 6)
        assert fingerprint.punctuation_ratios["period"] == pytest.approx(expected_period)

    def test_projection_deterministic(self) -> None:
        first = project_style_fingerprint(_profile())
        second = project_style_fingerprint(_profile())
        assert first == second


def _profile() -> StyleEvidenceProfile:
    from humanhand.domain.style_coverage import StyleCoverageReport
    from humanhand.domain.style_invariants import extract_invariants, extract_tendencies
    from humanhand.domain.style_metrics import compute_all_metrics

    voice_text = (
        "The lighthouse keeper followed the same careful routine each evening. "
        "She checked the lens twice, wound the clockwork, and wrote the log. "
        "Fog rolled in from the north, soft and patient, and she listened for ships."
    )
    metrics = compute_all_metrics(voice_text)
    return StyleEvidenceProfile(
        schema_version=1,
        profile_id="test",
        profile_label="test",
        package_ids=("sty-test",),
        voice_text=voice_text,
        sample_word_count=metrics.word_count,
        min_words_for_sufficiency=1,
        metrics=metrics,
        hard_invariants=extract_invariants(voice_text, metrics),
        soft_tendencies=extract_tendencies(voice_text, metrics),
        coverage=StyleCoverageReport(
            package_id="test",
            visible_text_coverage=1.0,
            code_point_coverage=1.0,
            structure_coverage=1.0,
            formatting_coverage=1.0,
            unsupported_features=(),
            unresolved_span_count=0,
            status="complete",
            sample_sufficiency="sufficient",
        ),
        status="complete",
    )
