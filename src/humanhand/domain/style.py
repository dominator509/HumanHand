"""Style fingerprint extraction — deterministic human writing trait analysis."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

from humanhand.domain.types import DomainError, StyleFingerprint


def extract_style_fingerprint(text: str) -> StyleFingerprint:
    """Extract deterministic style traits from a human writing sample.

    Args:
        text: A non-empty human writing sample.

    Returns:
        StyleFingerprint with computed traits.

    Raises:
        DomainError: If text is empty or whitespace-only.
    """
    if not text or not text.strip():
        raise DomainError("Style sample must not be empty")

    sentences = _split_sentences(text)
    paragraphs = _split_paragraphs(text)
    words = _tokenize_words(text)
    word_count = len(words)

    # Sentence metrics
    sentence_lengths = [_count_words_in_sentence(s) for s in sentences]
    avg_sent_len = _mean(sentence_lengths)
    sent_len_var = _variance(sentence_lengths, avg_sent_len)

    # Paragraph metrics
    para_lengths = [_count_sentences_in_paragraph(p) for p in paragraphs]
    avg_para_len = _mean(para_lengths)

    # Word metrics
    avg_word_len = _mean([len(w) for w in words]) if words else 0.0

    # Punctuation ratios
    punct_ratios = _compute_punctuation_ratios(text)

    # Vocabulary richness: type-token ratio
    vocab_richness = _type_token_ratio(words) if words else 0.0

    # Common phrases (frequent 2-3 word sequences)
    common_phrases = _extract_common_phrases(words, top_n=10)

    # Formality score: ratio of formal markers to casual markers
    formality = _compute_formality(words)

    return StyleFingerprint(
        avg_sentence_length=round(avg_sent_len, 2),
        sentence_length_variance=round(sent_len_var, 2),
        avg_paragraph_length=round(avg_para_len, 2),
        punctuation_ratios=punct_ratios,
        vocabulary_richness=round(vocab_richness, 4),
        common_phrases=common_phrases,
        formality_score=round(formality, 4),
        avg_word_length=round(avg_word_len, 2),
        total_sentences=len(sentences),
        total_paragraphs=len(paragraphs),
        total_words=word_count,
    )


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using basic punctuation boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if s.strip()]


def _split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs by blank lines."""
    paragraphs = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in paragraphs if p.strip()]


def _tokenize_words(text: str) -> list[str]:
    """Extract lowercase word tokens, stripping punctuation."""
    return re.findall(r"[a-zA-Z0-9]+(?:'[a-zA-Z]+)?", text.lower())


def _count_words_in_sentence(sentence: str) -> int:
    return len(_tokenize_words(sentence))


def _count_sentences_in_paragraph(paragraph: str) -> int:
    return len(_split_sentences(paragraph))


def _mean(values: Sequence[float | int]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _variance(values: Sequence[float | int], mean: float | None = None) -> float:
    if len(values) < 2:
        return 0.0
    if mean is None:
        mean = _mean(values)
    return sum((x - mean) ** 2 for x in values) / (len(values) - 1)


def _compute_punctuation_ratios(text: str) -> dict[str, float]:
    """Compute ratios of common punctuation marks per character."""
    total_chars = max(len(text), 1)
    ratios: dict[str, float] = {}
    targets = {
        "comma": ",",
        "period": ".",
        "question": "?",
        "exclamation": "!",
        "semicolon": ";",
        "colon": ":",
        "dash": "—",
        "quote": '"',
        "apostrophe": "'",
        "parenthesis": "()",
    }
    for name, char in targets.items():
        count = text.count(char)
        ratios[name] = round(count / total_chars, 6)
    return ratios


def _type_token_ratio(words: list[str]) -> float:
    """Compute vocabulary richness as unique/total word ratio."""
    if not words:
        return 0.0
    return len(set(words)) / len(words)


def _extract_common_phrases(words: list[str], top_n: int = 10) -> tuple[str, ...]:
    """Extract most common 2- and 3-word phrases."""
    bigrams = [" ".join(words[i : i + 2]) for i in range(len(words) - 1)]
    trigrams = [" ".join(words[i : i + 3]) for i in range(len(words) - 2)]
    all_phrases = bigrams + trigrams
    counter = Counter(all_phrases)
    return tuple(phrase for phrase, _ in counter.most_common(top_n))


def _compute_formality(words: list[str]) -> float:
    """Estimate formality based on formal vs casual word markers.

    Returns a value between 0.0 (very casual) and 1.0 (very formal).
    """
    formal_markers = {
        "therefore",
        "consequently",
        "furthermore",
        "nevertheless",
        "however",
        "thus",
        "accordingly",
        "moreover",
        "hence",
        "whereas",
        "regarding",
        "concerning",
        "indeed",
        "nonetheless",
        "subsequently",
    }
    casual_markers = {
        "yeah",
        "gonna",
        "wanna",
        "kinda",
        "sorta",
        "gotta",
        "dunno",
        "lemme",
        "ain't",
        "y'know",
        "stuff",
        "thingy",
        "cool",
        "awesome",
        "anyway",
    }
    total_words = max(len(words), 1)
    formal_count = sum(1 for w in words if w in formal_markers)
    casual_count = sum(1 for w in words if w in casual_markers)
    raw = (formal_count - casual_count) / total_words
    # Normalize to [0, 1] using sigmoid
    formality = 1.0 / (1.0 + math.exp(-5 * raw))
    return formality
