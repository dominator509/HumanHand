"""Advanced deterministic style metrics for the Style Fidelity Vault (EP-014).

Deterministic measurements from blueprint section 8.4 built on the legacy
fingerprint conventions of :mod:`humanhand.domain.style`: pure stdlib,
deterministic, no wall clock, no randomness.

Documented heuristics and limitations
-------------------------------------
- Sentence splitting reuses the legacy simple splitter (``(?<=[.!?])\\s+``).
  No abbreviation detection: "Mr. Smith" splits after "Mr.", and a quote
  directly after sentence punctuation (``said."``) prevents a split.
- Word tokenization reuses the legacy tokenizer
  ``[a-zA-Z0-9]+(?:'[a-zA-Z]+)?``, lowercased except for the capitalization
  metrics.
- Percentiles use numpy-style linear interpolation: sorted values with index
  ``(n - 1) * q`` for quantile ``q``; an integer index returns that element,
  a fractional index linearly interpolates between neighbours.
- MATTR is the moving-average TTR over a sliding 100-word window; texts with
  fewer than 100 words report the plain whole-text TTR.
- Clauses are sentence segments split on ``,`` ``;`` ``:`` em dash and en
  dash. Conjunction boundaries (and/but/or) are deliberately not split.
- fragment_count counts sentences with at most 2 words (finite-verb proxy).
- run_on_count counts sentences with at least 5 clauses and at least 45
  words.
- passive_marker_count counts consecutive word-token pairs (be-form, word
  ending in "ed" or "en") within a sentence; punctuation between the two
  tokens is ignored.
- technical_term_ratio uses words of length >= 12 as the proxy.
- Every count dict is built in a fixed documented order or sorted by key, so
  iteration order is deterministic.
"""

from __future__ import annotations

import math
import re
import statistics
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from humanhand.domain.style import _compute_formality

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[a-zA-Z0-9]+(?:'[a-zA-Z]+)?")
_CLAUSE_SPLIT_RE = re.compile(r"[,:;—–]")
_LEADING_NON_WORD_RE = re.compile(r"^[^a-zA-Z0-9]+")
_LEADING_NON_LETTER_RE = re.compile(r"^[^a-zA-Z]+")
_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")

_PUNCT_ALPHABET = ".,;:!?\"'()—–-/"

_MATTR_WINDOW = 100
_FRAGMENT_MAX_WORDS = 2
_RUN_ON_MIN_CLAUSES = 5
_RUN_ON_MIN_WORDS = 45
_TECHNICAL_MIN_LENGTH = 12

_BE_FORMS = frozenset({"am", "is", "are", "was", "were", "be", "been", "being"})

_FUNCTION_WORDS = frozenset(
    {
        # determiners
        "the",
        "a",
        "an",
        "this",
        "that",
        "these",
        "those",
        "some",
        "any",
        "no",
        "every",
        "each",
        "either",
        "neither",
        "both",
        "all",
        "many",
        "much",
        "few",
        "several",
        "most",
        "more",
        "less",
        "little",
        "other",
        "another",
        "such",
        "what",
        "which",
        "whose",
        "whichever",
        "whatever",
        # prepositions
        "of",
        "in",
        "to",
        "for",
        "with",
        "on",
        "at",
        "from",
        "by",
        "about",
        "as",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "under",
        "over",
        "against",
        "among",
        "within",
        "without",
        "toward",
        "upon",
        "per",
        "via",
        "despite",
        "across",
        "behind",
        "along",
        # conjunctions
        "and",
        "or",
        "but",
        "nor",
        "so",
        "yet",
        "while",
        "whereas",
        "although",
        "though",
        "because",
        "since",
        "unless",
        "if",
        "when",
        "where",
        "than",
        "whether",
        "until",
        # pronouns
        "i",
        "me",
        "my",
        "mine",
        "myself",
        "you",
        "your",
        "yours",
        "yourself",
        "he",
        "him",
        "his",
        "himself",
        "she",
        "her",
        "hers",
        "herself",
        "it",
        "its",
        "itself",
        "we",
        "us",
        "our",
        "ours",
        "ourselves",
        "they",
        "them",
        "their",
        "theirs",
        "themselves",
        "one",
        "ones",
        "who",
        "whom",
        "there",
        # auxiliary and modal verbs
        "am",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "having",
        "do",
        "does",
        "did",
        "doing",
        "will",
        "would",
        "shall",
        "should",
        "can",
        "could",
        "may",
        "might",
        "must",
        "need",
        "dare",
        "ought",
        "not",
        # adverbs and miscellany
        "very",
        "too",
        "also",
        "just",
        "only",
        "even",
        "still",
        "already",
        "ever",
        "never",
        "here",
        "how",
        "why",
    }
)

_PRONOUN_CLASSES: dict[str, frozenset[str]] = {
    "first_singular": frozenset({"i", "me", "my", "mine", "myself"}),
    "second_person": frozenset({"you", "your", "yours", "yourself", "yourselves"}),
    "third_person": frozenset(
        {
            "he",
            "she",
            "it",
            "him",
            "her",
            "his",
            "hers",
            "its",
            "they",
            "them",
            "their",
            "theirs",
            "himself",
            "herself",
            "itself",
            "themselves",
        }
    ),
    "first_plural": frozenset({"we", "us", "our", "ours", "ourselves"}),
}

_TRANSITIONS = (
    "however",
    "therefore",
    "moreover",
    "furthermore",
    "nevertheless",
    "thus",
    "consequently",
    "in addition",
    "for example",
    "for instance",
    "on the other hand",
    "in contrast",
    "similarly",
    "meanwhile",
    "finally",
)

_HEDGES = frozenset(
    {
        "maybe",
        "perhaps",
        "possibly",
        "seems",
        "appears",
        "tends",
        "likely",
        "roughly",
        "approximately",
        "somewhat",
        "quite",
        "rather",
    }
)

_BOOSTERS = frozenset(
    {
        "certainly",
        "clearly",
        "obviously",
        "definitely",
        "undoubtedly",
        "absolutely",
        "indeed",
        "always",
        "never",
        "must",
    }
)


@dataclass(frozen=True)
class Distribution:
    """Deterministic summary of a numeric sample.

    ``stdev`` is the sample standard deviation (n-1 denominator); it is 0.0
    for samples with fewer than 2 values.
    """

    count: int
    minimum: float
    p10: float
    p25: float
    median: float
    p75: float
    p90: float
    maximum: float
    mean: float
    stdev: float


@dataclass(frozen=True)
class LexicalMetrics:
    """Lexical richness and word-level measurements."""

    word_count: int
    avg_word_length: float
    unique_word_count: int
    type_token_ratio: float
    mattr: float
    hapax_legomena_ratio: float
    function_word_ratio: float
    function_word_counts: dict[str, int]
    contraction_frequency: float
    contraction_forms: dict[str, int]
    pronoun_distribution: dict[str, int]


@dataclass(frozen=True)
class SyntaxMetrics:
    """Sentence-, clause-, and syntax-heuristic measurements."""

    sentence_length_distribution: Distribution
    clause_length_distribution: Distribution
    sentence_opening_ngrams: dict[str, int]
    fragment_count: int
    run_on_count: int
    passive_marker_count: int


@dataclass(frozen=True)
class RhythmMetrics:
    """Paragraph rhythm and transition measurements."""

    paragraph_length_distribution: Distribution
    paragraph_opening_ngrams: dict[str, int]
    paragraph_closing_ngrams: dict[str, int]
    transition_counts: dict[str, int]


@dataclass(frozen=True)
class PunctuationMetrics:
    """Punctuation counts, sequences, and conventions."""

    counts: dict[str, int]
    sequences: dict[str, int]
    dash_convention: str
    quote_convention: str
    apostrophe_convention: str


@dataclass(frozen=True)
class CapitalizationMetrics:
    """Capitalization pattern measurements."""

    sentence_initial_capitalization_ratio: float
    all_caps_word_ratio: float
    title_case_word_ratio: float


@dataclass(frozen=True)
class QuestionExclamationMetrics:
    """Question and exclamation frequencies."""

    question_frequency: float
    exclamation_frequency: float
    question_count: int
    exclamation_count: int


@dataclass(frozen=True)
class RegisterMetrics:
    """Register measurements for a named register subprofile."""

    name: str
    formality_score: float
    hedge_count: int
    booster_count: int
    technical_term_ratio: float


@dataclass(frozen=True)
class StyleMetricsBundle:
    """All advanced deterministic style metrics for one text."""

    word_count: int
    lexical: LexicalMetrics
    syntax: SyntaxMetrics
    rhythm: RhythmMetrics
    punctuation: PunctuationMetrics
    capitalization: CapitalizationMetrics
    questions: QuestionExclamationMetrics
    register: RegisterMetrics


def distribution(values: Sequence[int | float]) -> Distribution:
    """Compute a deterministic percentile summary of a numeric sample.

    Percentiles use numpy-style linear interpolation: for sorted values and
    quantile ``q`` the index is ``(n - 1) * q``; an integer index returns
    that element, a fractional index linearly interpolates between
    neighbours. Empty samples yield a zero-valued distribution.
    """
    sorted_values = sorted(float(v) for v in values)
    count = len(sorted_values)
    if count == 0:
        return Distribution(
            count=0,
            minimum=0.0,
            p10=0.0,
            p25=0.0,
            median=0.0,
            p75=0.0,
            p90=0.0,
            maximum=0.0,
            mean=0.0,
            stdev=0.0,
        )
    mean = sum(sorted_values) / count
    stdev = statistics.stdev(sorted_values) if count >= 2 else 0.0
    return Distribution(
        count=count,
        minimum=sorted_values[0],
        p10=_percentile(sorted_values, 0.10),
        p25=_percentile(sorted_values, 0.25),
        median=_percentile(sorted_values, 0.50),
        p75=_percentile(sorted_values, 0.75),
        p90=_percentile(sorted_values, 0.90),
        maximum=sorted_values[-1],
        mean=mean,
        stdev=stdev,
    )


def compute_lexical_metrics(text: str) -> LexicalMetrics:
    """Compute lexical richness, function words, and contractions."""
    words = _tokenize(text)
    word_count = len(words)
    unique_count = len(set(words))
    type_token_ratio = unique_count / word_count if word_count else 0.0
    hapax_count = sum(1 for w, c in Counter(words).items() if c == 1)
    hapax_legomena_ratio = hapax_count / word_count if word_count else 0.0
    function_counts = dict(sorted(Counter(w for w in words if w in _FUNCTION_WORDS).items()))
    function_count = sum(function_counts.values())
    contractions = [w for w in words if "'" in w]
    return LexicalMetrics(
        word_count=word_count,
        avg_word_length=sum(len(w) for w in words) / word_count if word_count else 0.0,
        unique_word_count=unique_count,
        type_token_ratio=type_token_ratio,
        mattr=_mattr(words),
        hapax_legomena_ratio=hapax_legomena_ratio,
        function_word_ratio=function_count / word_count if word_count else 0.0,
        function_word_counts=function_counts,
        contraction_frequency=len(contractions) / word_count if word_count else 0.0,
        contraction_forms=dict(sorted(Counter(contractions).items())),
        pronoun_distribution=_pronoun_distribution(words),
    )


def compute_syntax_metrics(text: str) -> SyntaxMetrics:
    """Compute sentence, clause, opening-ngram, and syntax-heuristic metrics."""
    sentences = _split_sentences(text)
    sentence_lengths = [len(_tokenize(s)) for s in sentences]
    clause_lengths: list[int] = []
    opening_counter: Counter[str] = Counter()
    fragment_count = 0
    run_on_count = 0
    passive_count = 0
    for sentence in sentences:
        clauses = [seg for seg in _CLAUSE_SPLIT_RE.split(sentence) if seg.strip()]
        clause_lengths.extend(len(_tokenize(clause)) for clause in clauses)
        tokens = _tokenize(sentence)
        if tokens:
            opening_counter[tokens[0]] += 1
            if len(tokens) >= 2:
                opening_counter[f"{tokens[0]} {tokens[1]}"] += 1
        if len(tokens) <= _FRAGMENT_MAX_WORDS:
            fragment_count += 1
        if len(clauses) >= _RUN_ON_MIN_CLAUSES and len(tokens) >= _RUN_ON_MIN_WORDS:
            run_on_count += 1
        passive_count += _count_passive_markers(tokens)
    return SyntaxMetrics(
        sentence_length_distribution=distribution(sentence_lengths),
        clause_length_distribution=distribution(clause_lengths),
        sentence_opening_ngrams=dict(sorted(opening_counter.items())),
        fragment_count=fragment_count,
        run_on_count=run_on_count,
        passive_marker_count=passive_count,
    )


def compute_rhythm_metrics(text: str) -> RhythmMetrics:
    """Compute paragraph rhythm, opening/closing ngrams, and transitions."""
    paragraphs = _split_paragraphs(text)
    paragraph_lengths = [len(_split_sentences(p)) for p in paragraphs]
    opening_counter: Counter[str] = Counter()
    closing_counter: Counter[str] = Counter()
    for paragraph in paragraphs:
        tokens = _tokenize(paragraph)
        if not tokens:
            continue
        opening_counter[tokens[0]] += 1
        if len(tokens) >= 2:
            opening_counter[f"{tokens[0]} {tokens[1]}"] += 1
        closing_counter[tokens[-1]] += 1
        if len(tokens) >= 2:
            closing_counter[f"{tokens[-2]} {tokens[-1]}"] += 1
    transition_counts: dict[str, int] = {}
    for sentence in _split_sentences(text):
        normalized = _sentence_start(sentence)
        for transition in _TRANSITIONS:
            if not normalized.startswith(transition):
                continue
            remainder = normalized[len(transition) :]
            if remainder == "" or not remainder[0].isalnum():
                transition_counts[transition] = transition_counts.get(transition, 0) + 1
                break
    return RhythmMetrics(
        paragraph_length_distribution=distribution(paragraph_lengths),
        paragraph_opening_ngrams=dict(sorted(opening_counter.items())),
        paragraph_closing_ngrams=dict(sorted(closing_counter.items())),
        transition_counts=dict(sorted(transition_counts.items())),
    )


def compute_punctuation_metrics(text: str) -> PunctuationMetrics:
    """Compute punctuation counts, sequences, and conventions."""
    counts: dict[str, int] = {}
    for char in _PUNCT_ALPHABET:
        char_count = text.count(char)
        if char_count:
            counts[char] = char_count
    sequences: dict[str, int] = {}
    run: list[str] = []
    for char in text:
        if char in _PUNCT_ALPHABET:
            run.append(char)
        else:
            _record_punct_pairs(run, sequences)
            run = []
    _record_punct_pairs(run, sequences)
    return PunctuationMetrics(
        counts=counts,
        sequences=dict(sorted(sequences.items())),
        dash_convention=_dash_convention(text),
        quote_convention=_quote_convention(text),
        apostrophe_convention=_apostrophe_convention(text),
    )


def compute_capitalization_metrics(text: str) -> CapitalizationMetrics:
    """Compute sentence-initial, all-caps, and title-case ratios."""
    sentences = _split_sentences(text)
    sentence_count = len(sentences)
    initial_caps = 0
    for sentence in sentences:
        stripped = _LEADING_NON_LETTER_RE.sub("", sentence)
        if stripped and stripped[0].isupper():
            initial_caps += 1
    words = _tokenize_preserve_case(text)
    word_count = len(words)
    all_caps = sum(1 for w in words if len(w) >= 2 and w == w.upper())
    title_case = sum(1 for w in words if len(w) >= 2 and w[0].isupper() and w[1:].islower())
    return CapitalizationMetrics(
        sentence_initial_capitalization_ratio=(
            initial_caps / sentence_count if sentence_count else 0.0
        ),
        all_caps_word_ratio=all_caps / word_count if word_count else 0.0,
        title_case_word_ratio=title_case / word_count if word_count else 0.0,
    )


def compute_question_exclamation_metrics(text: str) -> QuestionExclamationMetrics:
    """Count sentences carrying question and exclamation marks."""
    sentences = _split_sentences(text)
    sentence_count = len(sentences)
    question_count = sum(1 for s in sentences if "?" in s)
    exclamation_count = sum(1 for s in sentences if "!" in s)
    return QuestionExclamationMetrics(
        question_frequency=question_count / sentence_count if sentence_count else 0.0,
        exclamation_frequency=exclamation_count / sentence_count if sentence_count else 0.0,
        question_count=question_count,
        exclamation_count=exclamation_count,
    )


def compute_register_metrics(text: str, name: str = "default") -> RegisterMetrics:
    """Compute register measurements for a named register subprofile.

    ``formality_score`` reuses the exact marker logic of
    ``humanhand.domain.style._compute_formality``; for empty input it reports
    0.0 (no evidence) instead of the neutral sigmoid value.
    """
    words = _tokenize(text)
    hedge_count = sum(1 for w in words if w in _HEDGES)
    booster_count = sum(1 for w in words if w in _BOOSTERS)
    technical_count = sum(1 for w in words if len(w) >= _TECHNICAL_MIN_LENGTH)
    return RegisterMetrics(
        name=name,
        formality_score=_compute_formality(words) if words else 0.0,
        hedge_count=hedge_count,
        booster_count=booster_count,
        technical_term_ratio=technical_count / len(words) if words else 0.0,
    )


def compute_all_metrics(text: str, register_name: str = "default") -> StyleMetricsBundle:
    """Compute every advanced style metric family for one text.

    Empty or whitespace-only input returns a valid zero-valued bundle.
    """
    return StyleMetricsBundle(
        word_count=len(_tokenize(text)),
        lexical=compute_lexical_metrics(text),
        syntax=compute_syntax_metrics(text),
        rhythm=compute_rhythm_metrics(text),
        punctuation=compute_punctuation_metrics(text),
        capitalization=compute_capitalization_metrics(text),
        questions=compute_question_exclamation_metrics(text),
        register=compute_register_metrics(text, register_name),
    )


def _percentile(sorted_values: list[float], quantile: float) -> float:
    """Numpy-style linear percentile on an already-sorted sample."""
    position = (len(sorted_values) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] + fraction * (sorted_values[upper] - sorted_values[lower])


def _mattr(words: list[str]) -> float:
    """Moving-average TTR over a sliding 100-word window."""
    if not words:
        return 0.0
    if len(words) <= _MATTR_WINDOW:
        return len(set(words)) / len(words)
    window_count = len(words) - _MATTR_WINDOW + 1
    total = sum(
        len(set(words[start : start + _MATTR_WINDOW])) / _MATTR_WINDOW
        for start in range(window_count)
    )
    return total / window_count


def _pronoun_distribution(words: list[str]) -> dict[str, int]:
    """Count word tokens per documented pronoun class (fixed key order)."""
    counts = dict.fromkeys(_PRONOUN_CLASSES, 0)
    for word in words:
        for key, members in _PRONOUN_CLASSES.items():
            if word in members:
                counts[key] += 1
    return counts


def _count_passive_markers(tokens: list[str]) -> int:
    """Count be-form pairs directly followed by a word ending in "ed"/"en"."""
    count = 0
    for first, second in zip(tokens, tokens[1:], strict=False):
        if first in _BE_FORMS and (second.endswith("ed") or second.endswith("en")):
            count += 1
    return count


def _record_punct_pairs(run: list[str], sequences: dict[str, int]) -> None:
    """Record adjacent punctuation pairs of one consecutive-punctuation run."""
    for first, second in zip(run, run[1:], strict=False):
        pair = first + second
        sequences[pair] = sequences.get(pair, 0) + 1


def _dash_convention(text: str) -> str:
    """Classify dash usage as em/en/hyphen/mixed/none."""
    present = [
        name
        for name, count in (
            ("em", text.count("—")),
            ("en", text.count("–")),
            ("hyphen", text.count("-")),
        )
        if count > 0
    ]
    if not present:
        return "none"
    if len(present) == 1:
        return present[0]
    return "mixed"


def _quote_convention(text: str) -> str:
    """Classify quotation marks as straight/curly double or single, or none.

    A straight apostrophe inside a word token (``don't``) is not counted as a
    single-quote character; the apostrophe convention handles those.
    """
    double_straight = text.count('"')
    double_curly = text.count("“") + text.count("”")
    single_curly = text.count("‘") + text.count("’")
    in_token_apostrophes = sum(1 for w in _tokenize(text) if "'" in w)
    single_straight = max(text.count("'") - in_token_apostrophes, 0)
    uses_double = double_straight > 0 or double_curly > 0
    uses_single = single_straight > 0 or single_curly > 0
    if uses_double and uses_single:
        return "mixed"
    if uses_double:
        if double_straight > 0 and double_curly > 0:
            return "mixed"
        return "double_straight" if double_straight > 0 else "double_curly"
    if uses_single:
        if single_straight > 0 and single_curly > 0:
            return "mixed"
        return "single_straight" if single_straight > 0 else "single_curly"
    return "none"


def _apostrophe_convention(text: str) -> str:
    """Classify apostrophe usage as straight/curly/mixed/none."""
    straight = sum(1 for w in _tokenize(text) if "'" in w)
    curly = text.count("’")
    if straight > 0 and curly > 0:
        return "mixed"
    if straight > 0:
        return "straight"
    if curly > 0:
        return "curly"
    return "none"


def _tokenize(text: str) -> list[str]:
    """Lowercased word tokens (legacy tokenizer from style.py)."""
    return _WORD_RE.findall(text.lower())


def _tokenize_preserve_case(text: str) -> list[str]:
    """Word tokens with original case preserved."""
    return _WORD_RE.findall(text)


def _split_sentences(text: str) -> list[str]:
    """Split into sentences with the legacy simple splitter (no abbreviations)."""
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s.strip()]


def _split_paragraphs(text: str) -> list[str]:
    """Split into paragraphs by blank lines (same rule as style.py)."""
    return [p.strip() for p in _PARAGRAPH_SPLIT_RE.split(text.strip()) if p.strip()]


def _sentence_start(sentence: str) -> str:
    """Lowercased sentence with leading non-word characters removed."""
    return _LEADING_NON_WORD_RE.sub("", sentence.lower())
