"""Unit tests for style fingerprint extraction."""

import pytest

from humanhand.domain.style import extract_style_fingerprint
from humanhand.domain.types import DomainError, StyleFingerprint


class TestExtractStyleFingerprint:
    def test_basic_text(self) -> None:
        text = "The quick brown fox jumps over the lazy dog. It was a sunny day."
        fp = extract_style_fingerprint(text)
        assert isinstance(fp, StyleFingerprint)
        assert fp.total_sentences >= 1
        assert fp.total_words > 0
        assert fp.avg_sentence_length > 0

    def test_multi_paragraph(self) -> None:
        text = "First paragraph here. It has two sentences.\n\nSecond paragraph. Also two here."
        fp = extract_style_fingerprint(text)
        assert fp.total_paragraphs == 2
        assert fp.total_sentences >= 3

    def test_empty_text_raises(self) -> None:
        with pytest.raises(DomainError, match="must not be empty"):
            extract_style_fingerprint("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(DomainError, match="must not be empty"):
            extract_style_fingerprint("   \n  \t  ")

    def test_punctuation_ratios(self) -> None:
        text = "Hello, world! How are you? I'm fine; thanks: really."
        fp = extract_style_fingerprint(text)
        assert "comma" in fp.punctuation_ratios
        assert fp.punctuation_ratios["comma"] > 0
        assert fp.punctuation_ratios["question"] > 0

    def test_vocabulary_richness(self) -> None:
        text = "the the the cat cat dog unique word phrasing"
        fp = extract_style_fingerprint(text)
        # Type-token ratio should be between 0 and 1
        assert 0.0 < fp.vocabulary_richness <= 1.0

    def test_formal_text_scores_higher(self) -> None:
        formal = (
            "Therefore, we must conclude that the evidence is indeed sufficient. "
            "Furthermore, the methodology was rigorous."
        )
        casual = "Yeah, I'm gonna go to the store. It's kinda cool there anyway."
        fp_formal = extract_style_fingerprint(formal)
        fp_casual = extract_style_fingerprint(casual)
        assert fp_formal.formality_score > fp_casual.formality_score

    def test_common_phrases(self) -> None:
        text = "the cat sat on the mat. the cat sat on the mat. the cat sat on the mat."
        fp = extract_style_fingerprint(text)
        assert len(fp.common_phrases) > 0
        assert "the cat" in fp.common_phrases or "cat sat" in fp.common_phrases

    def test_long_text(self) -> None:
        # Generate a longer text to ensure no performance issues
        sentences = [f"This is sentence number {i} with some variety words." for i in range(50)]
        text = " ".join(sentences)
        fp = extract_style_fingerprint(text)
        assert fp.total_sentences == 50
        assert fp.total_words > 0

    def test_single_sentence(self) -> None:
        text = "Hello."
        fp = extract_style_fingerprint(text)
        assert fp.total_sentences == 1
        assert fp.total_words == 1
        assert fp.avg_sentence_length == 1.0

    def test_formality_single_word(self) -> None:
        """Formality score should handle single-word input."""
        text = "Therefore"
        fp = extract_style_fingerprint(text)
        assert 0.0 <= fp.formality_score <= 1.0
