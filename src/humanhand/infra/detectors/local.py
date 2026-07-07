"""Local heuristic detector — deterministic, zero-network AI-text analysis."""

from __future__ import annotations

import re
from typing import Any

from humanhand.infra.detectors.base import BaseDetector, DetectorError

# ── Constants ───────────────────────────────────────────────────

# Minimum number of words required for meaningful heuristic analysis
_MIN_WORDS = 3

# Minimum number of sentences required for meaningful heuristic analysis
_MIN_SENTENCES = 2

# Regex to extract words (handles hyphenated and apostrophe words)
_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*")

# Regex to split sentences on terminal punctuation
_SENTENCE_RE = re.compile(r"[.!?]+")

# Personal pronoun patterns (I, me, my, we, our, us — excluding "it")
_PERSONAL_PRONOUN_RE = re.compile(r"\b(?:I|me|my|we|our|us)\b", re.IGNORECASE)

# Phrases statistically more common in AI-generated text
_AI_PHRASES: tuple[str, ...] = (
    "it is important to note",
    "it is essential to",
    "it is crucial to",
    "it is worth noting",
    "however, it is",
    "in conclusion",
    "in summary",
    "first and foremost",
    "lastly",
    "furthermore",
    "needless to say",
    "as previously mentioned",
    "as mentioned earlier",
    "all in all",
    "when it comes to",
    "it goes without saying",
    "in the realm of",
    "in today's",
    "on the one hand",
    "on the other hand",
    "it is noteworthy",
    "it should be noted",
    "it bears mentioning",
    "it is evident",
    "as a result",
    "consequently",
    "as can be seen",
    "it is clear that",
    "it is apparent",
)


# ── Heuristic calculations ──────────────────────────────────────


def _tokenize(text: str) -> list[str]:
    """Split text into word tokens."""
    return _WORD_RE.findall(text)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences on terminal punctuation."""
    parts = _SENTENCE_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


def _repeated_bigram_ratio(words: list[str]) -> float:
    """Fraction of bigrams that are repeats of earlier bigrams.

    AI text tends to reuse the same word pairs (e.g. "it is", "to the"),
    while human prose uses more varied bigram combinations.

    Returns 0.0 for text too short to have bigrams.
    """
    if len(words) < 3:
        return 0.0
    bigrams = [f"{words[i]} {words[i + 1]}".lower() for i in range(len(words) - 1)]
    seen: set[str] = set()
    repeats = 0
    for bg in bigrams:
        if bg in seen:
            repeats += 1
        else:
            seen.add(bg)
    return repeats / len(bigrams)


def _sentence_length_variance(sentences: list[str]) -> float:
    """Compute variance in word-count across sentences."""
    lengths = [len(s.split()) for s in sentences]
    if len(lengths) < 2:
        return 0.0
    mean = sum(lengths) / len(lengths)
    return sum((length - mean) ** 2 for length in lengths) / len(lengths)


def _personal_pronoun_count(text: str) -> int:
    """Count first-person pronoun occurrences."""
    return len(_PERSONAL_PRONOUN_RE.findall(text))


def _ai_phrase_count(text: str) -> int:
    """Count occurrences of AI-typical phrases."""
    lower = text.lower()
    return sum(lower.count(phrase) for phrase in _AI_PHRASES)


def _avg_word_length(words: list[str]) -> float:
    """Compute mean word length in characters."""
    if not words:
        return 0.0
    return sum(len(w) for w in words) / len(words)


def _compute_component_scores(
    bigram_repeat: float,
    sent_var: float,
    pronouns: int,
    ai_phrases: int,
    avg_word_len: float,
) -> dict[str, float]:
    """Normalize each heuristic metric to [0, 1] where 0 = human, 1 = AI.

    Returns a dict with the individual component scores and the combined
    score keyed as 'combined'.
    """
    # Bigram repetition: higher ratio => more repetitive => AI-like
    # Ratio > 0.15 is strongly repetitive, ratio < 0.02 is natural
    bigram_score = min(bigram_repeat / 0.15, 1.0)

    # Sentence length variance: lower => more uniform => AI-like
    # Variance < 5 is very uniform, variance > 40 is very varied
    var_score = 1.0 - min(sent_var / 40.0, 1.0) if sent_var < 40.0 else 0.0

    # Personal pronouns: more => human voice
    # 0 pronouns => neutral, 5+ pronouns => strongly human
    pronoun_score = max(0.0, 1.0 - (pronouns / 5.0)) * 0.35

    # AI phrases: more => AI-like
    # 0 phrases => 0, 6+ phrases => strongly AI
    ai_phrase_score = min(ai_phrases / 6.0, 1.0)

    # Average word length: shorter => simpler => AI-like
    # Below 4.0 chars => AI-like, above 5.5 chars => human-like
    if avg_word_len <= 3.0:
        word_len_score = 1.0
    elif avg_word_len >= 6.0:
        word_len_score = 0.0
    else:
        word_len_score = 1.0 - ((avg_word_len - 3.0) / 3.0)

    combined = (
        bigram_score * 0.15
        + var_score * 0.10
        + pronoun_score * 0.20
        + ai_phrase_score * 0.45
        + word_len_score * 0.10
    )

    return {
        "bigram_score": bigram_score,
        "variance_score": var_score,
        "pronoun_score": pronoun_score,
        "ai_phrase_score": ai_phrase_score,
        "word_len_score": word_len_score,
        "combined": max(0.0, min(1.0, combined)),
    }


def _classify(score: float) -> str:
    """Map a numeric score to a human-readable label."""
    if score < 0.35:
        return "human"
    if score < 0.65:
        return "uncertain"
    return "ai"


# ── Detector class ──────────────────────────────────────────────


class LocalDetector(BaseDetector):
    """Deterministic local heuristic detector.

    Analyzes text structure for AI-like patterns without any network
    calls or API keys. Always returns provider='local', model='heuristic'.
    """

    PROVIDER = "local"
    MODEL = "heuristic"

    def detect(self, text: str) -> dict[str, Any]:
        """Analyze text using local heuristic and return a score record.

        Args:
            text: The text to analyze.

        Returns:
            Dict with keys: provider, model, score, label, raw_score_json.

        Raises:
            DetectorError: If analysis fails unexpectedly.
        """
        try:
            words = _tokenize(text)
            sentences = _split_sentences(text)

            # Insufficient text for meaningful heuristic analysis
            if len(words) < _MIN_WORDS or len(sentences) < _MIN_SENTENCES:
                return {
                    "provider": self.PROVIDER,
                    "model": self.MODEL,
                    "score": 0.5,
                    "label": "uncertain",
                    "raw_score_json": {
                        "status_code": "insufficient_text",
                        "word_count": len(words),
                        "sentence_count": len(sentences),
                    },
                }

            bigram_repeat = _repeated_bigram_ratio(words)
            sent_var = _sentence_length_variance(sentences)
            pronouns = _personal_pronoun_count(text)
            ai_phrases = _ai_phrase_count(text)
            avg_wlen = _avg_word_length(words)

            components = _compute_component_scores(
                bigram_repeat,
                sent_var,
                pronouns,
                ai_phrases,
                avg_wlen,
            )
            score = components["combined"]
            label = _classify(score)

            return {
                "provider": self.PROVIDER,
                "model": self.MODEL,
                "score": score,
                "label": label,
                "raw_score_json": {
                    "metrics": {
                        "bigram_repeat_ratio": round(bigram_repeat, 4),
                        "sentence_length_variance": round(sent_var, 4),
                        "personal_pronoun_count": pronouns,
                        "ai_phrase_count": ai_phrases,
                        "avg_word_length": round(avg_wlen, 4),
                    },
                    "scores": {
                        "bigram_score": round(components["bigram_score"], 4),
                        "variance_score": round(components["variance_score"], 4),
                        "pronoun_score": round(components["pronoun_score"], 4),
                        "ai_phrase_score": round(components["ai_phrase_score"], 4),
                        "word_len_score": round(components["word_len_score"], 4),
                    },
                    "weights": {
                        "bigram_repeat": 0.15,
                        "variance": 0.10,
                        "pronoun": 0.20,
                        "ai_phrase": 0.45,
                        "word_len": 0.10,
                    },
                },
            }
        except Exception as exc:
            raise DetectorError(f"Local detector analysis failed: {exc}") from exc
