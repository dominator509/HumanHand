"""Unit tests for advanced deterministic style metrics (EP-014).

Numeric assertions are hand-computed literals; each one carries a comment
with its derivation. Values marked "verified by token dump" were confirmed
against the real module output before writing the assertion.
"""

from humanhand.domain.style import extract_style_fingerprint
from humanhand.domain.style_metrics import (
    compute_all_metrics,
    compute_capitalization_metrics,
    compute_lexical_metrics,
    compute_punctuation_metrics,
    compute_question_exclamation_metrics,
    compute_register_metrics,
    compute_rhythm_metrics,
    compute_syntax_metrics,
    distribution,
)


def test_distribution_known_sample() -> None:
    d = distribution([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    assert d.count == 10
    assert d.minimum == 1.0
    assert d.maximum == 10.0
    # numpy-style linear percentile, index (n-1)*q = 4.5 -> 5 + 0.5*(6-5)
    assert d.median == 5.5
    # index 2.25 -> 3 + 0.25*(4-3)
    assert d.p25 == 3.25
    # index 0.9 -> 1 + 0.9*(2-1)
    assert d.p10 == 1.9
    # index 6.75 -> 7 + 0.75*(8-7)
    assert d.p75 == 7.75
    # index 8.1 -> 9 + 0.1*(10-9)
    assert d.p90 == 9.1
    assert d.mean == 5.5
    # sample stdev of 1..10: sqrt(82.5/9) = 3.02765...
    assert abs(d.stdev - 3.0277) < 0.01


def test_distribution_empty() -> None:
    d = distribution([])
    assert d.count == 0
    for field in (d.minimum, d.p10, d.p25, d.median, d.p75, d.p90, d.maximum, d.mean, d.stdev):
        assert field == 0.0


def test_lexical_basic() -> None:
    m = compute_lexical_metrics("The cat sat. The cat ran.")
    assert m.word_count == 6
    assert m.unique_word_count == 4
    # 4 unique / 6 tokens = 0.6667 (hand-computed)
    assert round(m.type_token_ratio, 4) == 0.6667
    # "sat" and "ran" occur once each: 2 / 6 = 0.3333 (hand-computed)
    assert round(m.hapax_legomena_ratio, 4) == 0.3333
    # only function word is "the" (twice): 2 / 6 = 0.3333 (hand-computed)
    assert round(m.function_word_ratio, 4) == 0.3333
    assert m.function_word_counts == {"the": 2}
    # 6 words < 100-word window -> MATTR equals whole-text TTR
    assert round(m.mattr, 4) == 0.6667
    assert m.contraction_frequency == 0.0
    assert m.contraction_forms == {}
    assert m.pronoun_distribution == {
        "first_singular": 0,
        "second_person": 0,
        "third_person": 0,
        "first_plural": 0,
    }


def test_lexical_avg_word_length() -> None:
    m = compute_lexical_metrics("The quick brown fox.")
    # token lengths 3, 5, 5, 3 -> mean 16/4 = 4.0 (hand-computed)
    assert m.avg_word_length == 4.0
    assert compute_lexical_metrics("").avg_word_length == 0.0


def test_lexical_contractions() -> None:
    m = compute_lexical_metrics("don't can't won't")
    assert m.word_count == 3
    # 3 contractions / 3 words = 1.0 (hand-computed)
    assert m.contraction_frequency == 1.0
    assert m.contraction_forms == {"can't": 1, "don't": 1, "won't": 1}


def test_pronoun_distribution() -> None:
    m = compute_lexical_metrics("I told you that we would go.")
    # i -> first_singular, you -> second_person, we -> first_plural (hand-verified)
    assert m.pronoun_distribution == {
        "first_singular": 1,
        "second_person": 1,
        "third_person": 0,
        "first_plural": 1,
    }


def test_mattr_sliding_window() -> None:
    sentence = (
        "The quick brown fox jumps over the lazy dog and chases the playful cat "
        "through the sunny park. "
    )
    text = sentence * 8  # 18 words per sentence x 8 = 144 words > 100-word window
    m = compute_lexical_metrics(text)
    # 144 words verified by token dump before writing this assertion
    assert m.word_count == 144
    assert 0.0 < m.mattr < 1.0


def test_determinism() -> None:
    text = (
        "The cat sat on the mat, and the dog barked loudly. "
        "It was a strange sight! Could anyone explain this? "
        "However, nobody moved an inch."
    )
    first = compute_all_metrics(text)
    second = compute_all_metrics(text)
    assert first == second


def test_syntax_sentence_lengths() -> None:
    text = "The quick brown fox jumps over the lazy dog. It was a sunny day. The cat sat quietly."
    s = compute_syntax_metrics(text)
    assert s.sentence_length_distribution.count == 3
    assert s.sentence_length_distribution.minimum == 4.0
    assert s.sentence_length_distribution.maximum == 9.0
    # sentences are 9, 5, and 4 words -> (9 + 5 + 4) / 3 = 6.0; my first
    # hand-count said 6 words for "It was a sunny day." but the real token
    # list has 5, so the assertion uses the verified 6.0
    assert s.sentence_length_distribution.mean == 6.0


def test_syntax_clause_lengths() -> None:
    s = compute_syntax_metrics("The cat sat, and the dog ran; quickly.")
    assert s.clause_length_distribution.count == 3
    assert s.clause_length_distribution.minimum == 1.0
    assert s.clause_length_distribution.maximum == 4.0
    # clauses: "The cat sat" (3), " and the dog ran" (4), " quickly." (1)
    # mean = 8/3 = 2.6667 (hand-computed)
    assert round(s.clause_length_distribution.mean, 4) == 2.6667


def test_syntax_fragments() -> None:
    s = compute_syntax_metrics("Hello. Go now. The cat sat.")
    # "Hello." (1 word) and "Go now." (2 words) are fragments (hand-verified)
    assert s.fragment_count == 2
    assert s.run_on_count == 0


def test_syntax_run_on() -> None:
    text = (
        "The committee reviewed the lengthy proposal document very carefully, "
        "then discussed the annual budget in considerable detail, "
        "finally voted on the matter at hand without delay, "
        "the chair summarized the entire committee decision clearly, "
        "everyone agreed to proceed with the proposed plan, and "
        "the meeting ended."
    )
    s = compute_syntax_metrics(text)
    # 46 words across 6 comma-separated clauses; the count was verified by
    # dumping the real token list (my first hand-count of 45 missed the final
    # "and"), so the assertion uses the verified 46.
    assert s.sentence_length_distribution.maximum == 46.0
    assert s.clause_length_distribution.count == 6
    assert s.run_on_count == 1
    assert compute_syntax_metrics("The cat sat quietly.").run_on_count == 0


def test_syntax_passive_markers() -> None:
    s = compute_syntax_metrics("The door was opened by the clerk. The window is closed.")
    # "was opened" and "is closed" -> 2 (hand-verified)
    assert s.passive_marker_count == 2
    assert compute_syntax_metrics("The dog was here.").passive_marker_count == 0


def test_syntax_sentence_openings() -> None:
    s = compute_syntax_metrics("The cat sat. The cat ran. Quickly, the dog left.")
    assert s.sentence_opening_ngrams["the"] == 2
    assert s.sentence_opening_ngrams["the cat"] == 2
    assert s.sentence_opening_ngrams["quickly"] == 1
    assert s.sentence_opening_ngrams["quickly the"] == 1


def test_rhythm_paragraphs_and_transitions() -> None:
    text = (
        "However, the plan failed. Therefore we moved on.\n\n"
        "Finally, the team regrouped. In addition, morale improved."
    )
    r = compute_rhythm_metrics(text)
    assert r.paragraph_length_distribution.count == 2
    # both paragraphs contain exactly 2 sentences (hand-verified)
    assert r.paragraph_length_distribution.mean == 2.0
    assert r.transition_counts == {
        "finally": 1,
        "however": 1,
        "in addition": 1,
        "therefore": 1,
    }
    assert r.paragraph_opening_ngrams["however"] == 1
    assert r.paragraph_opening_ngrams["finally the"] == 1
    assert r.paragraph_closing_ngrams["moved on"] == 1
    assert r.paragraph_closing_ngrams["morale improved"] == 1


def test_punctuation_dash_conventions() -> None:
    assert compute_punctuation_metrics("Word—word.").dash_convention == "em"
    assert compute_punctuation_metrics("Word–word.").dash_convention == "en"
    assert compute_punctuation_metrics("Word - word.").dash_convention == "hyphen"
    assert compute_punctuation_metrics("Word—word, then - done.").dash_convention == "mixed"
    assert compute_punctuation_metrics("Just words here.").dash_convention == "none"


def test_punctuation_quote_conventions() -> None:
    assert (
        compute_punctuation_metrics('He said "hello" to me.').quote_convention == "double_straight"
    )
    assert compute_punctuation_metrics("She said “hello” to me.").quote_convention == "double_curly"
    assert compute_punctuation_metrics("He said 'hi' to me.").quote_convention == "single_straight"
    assert compute_punctuation_metrics("She said ‘hi’ to me.").quote_convention == "single_curly"
    assert (
        compute_punctuation_metrics('"Hello," she said. He said ‘hi’.').quote_convention == "mixed"
    )


def test_punctuation_apostrophe_conventions() -> None:
    assert compute_punctuation_metrics("don't stop").apostrophe_convention == "straight"
    assert compute_punctuation_metrics("don’t stop").apostrophe_convention == "curly"
    assert compute_punctuation_metrics("don't don’t").apostrophe_convention == "mixed"
    assert compute_punctuation_metrics("plain words").apostrophe_convention == "none"


def test_punctuation_counts_and_sequences() -> None:
    m = compute_punctuation_metrics('Hello, world! What? "Fine."')
    assert m.counts[","] == 1
    assert m.counts["!"] == 1
    assert m.counts["?"] == 1
    assert m.counts['"'] == 2
    assert m.counts["."] == 1
    # the only adjacent punctuation pair is the closing '."' at the end
    assert m.sequences == {'."': 1}
    m2 = compute_punctuation_metrics('What?! "No!"')
    # "?!" from "What?!" and '!"' from 'No!"' (hand-verified)
    assert m2.sequences == {"?!": 1, '!"': 1}


def test_capitalization() -> None:
    m = compute_capitalization_metrics("Hello world. ALL CAPS here. Mixed Case Words.")
    assert m.sentence_initial_capitalization_ratio == 1.0
    # ALL and CAPS -> 2 of 8 words = 0.25 (hand-computed)
    assert round(m.all_caps_word_ratio, 4) == 0.25
    # Hello, Mixed, Case, Words -> 4 of 8 = 0.5 (hand-computed)
    assert round(m.title_case_word_ratio, 4) == 0.5


def test_questions_and_exclamations() -> None:
    q = compute_question_exclamation_metrics("What is this? Really?")
    assert q.question_count == 2
    # both sentences carry a question mark (hand-verified)
    assert q.question_frequency == 1.0
    assert q.exclamation_count == 0
    assert q.exclamation_frequency == 0.0
    e = compute_question_exclamation_metrics("Wow!")
    assert e.exclamation_count == 1
    assert e.exclamation_frequency == 1.0
    assert e.question_count == 0
    mixed = compute_question_exclamation_metrics("Is it done? Yes! Maybe.")
    assert mixed.question_count == 1
    assert mixed.exclamation_count == 1
    # 1 of 3 sentences carries each mark = 0.3333 (hand-computed)
    assert round(mixed.question_frequency, 4) == 0.3333
    assert round(mixed.exclamation_frequency, 4) == 0.3333


def test_register_hedges_and_boosters() -> None:
    m = compute_register_metrics(
        "Perhaps the results are likely correct, and certainly the process seems sound."
    )
    # hedges: perhaps, likely, seems -> 3 (hand-verified)
    assert m.hedge_count == 3
    # boosters: certainly -> 1 (hand-verified)
    assert m.booster_count == 1
    # no token has length >= 12
    assert m.technical_term_ratio == 0.0
    # no formal or casual markers -> raw 0 -> sigmoid(0) = 0.5 (hand-computed)
    assert m.formality_score == 0.5
    assert m.name == "default"
    named = compute_register_metrics("Hello.", name="legal")
    assert named.name == "legal"


def test_empty_text_zero_bundle() -> None:
    bundle = compute_all_metrics("")
    assert bundle.word_count == 0
    assert bundle.lexical.word_count == 0
    assert bundle.lexical.avg_word_length == 0.0
    assert bundle.lexical.type_token_ratio == 0.0
    assert bundle.lexical.mattr == 0.0
    assert bundle.lexical.hapax_legomena_ratio == 0.0
    assert bundle.lexical.function_word_ratio == 0.0
    assert bundle.lexical.contraction_frequency == 0.0
    assert bundle.lexical.function_word_counts == {}
    assert bundle.lexical.contraction_forms == {}
    assert bundle.lexical.pronoun_distribution == {
        "first_singular": 0,
        "second_person": 0,
        "third_person": 0,
        "first_plural": 0,
    }
    for d in (
        bundle.syntax.sentence_length_distribution,
        bundle.syntax.clause_length_distribution,
    ):
        assert d.count == 0
        assert d.mean == 0.0 and d.median == 0.0 and d.stdev == 0.0
    assert bundle.syntax.sentence_opening_ngrams == {}
    assert bundle.syntax.fragment_count == 0
    assert bundle.syntax.run_on_count == 0
    assert bundle.syntax.passive_marker_count == 0
    assert bundle.rhythm.paragraph_length_distribution.count == 0
    assert bundle.rhythm.paragraph_opening_ngrams == {}
    assert bundle.rhythm.paragraph_closing_ngrams == {}
    assert bundle.rhythm.transition_counts == {}
    assert bundle.punctuation.counts == {}
    assert bundle.punctuation.sequences == {}
    assert bundle.punctuation.dash_convention == "none"
    assert bundle.punctuation.quote_convention == "none"
    assert bundle.punctuation.apostrophe_convention == "none"
    assert bundle.capitalization.sentence_initial_capitalization_ratio == 0.0
    assert bundle.capitalization.all_caps_word_ratio == 0.0
    assert bundle.capitalization.title_case_word_ratio == 0.0
    assert bundle.questions.question_count == 0
    assert bundle.questions.exclamation_count == 0
    assert bundle.questions.question_frequency == 0.0
    assert bundle.questions.exclamation_frequency == 0.0
    assert bundle.register.hedge_count == 0
    assert bundle.register.booster_count == 0
    assert bundle.register.formality_score == 0.0
    assert bundle.register.technical_term_ratio == 0.0
    # whitespace-only input yields the same zero bundle
    assert compute_all_metrics("   \n  ") == bundle


def test_cross_check_legacy_fingerprint() -> None:
    text = (
        "The quick brown fox jumps over the lazy dog. "
        "It was a beautiful sunny day in the park. "
        "She walked slowly along the winding path. "
        "The birds sang loudly in the tall trees. "
        "He stopped to admire the view."
    )
    legacy = extract_style_fingerprint(text)
    mine = compute_syntax_metrics(text).sentence_length_distribution.mean
    assert legacy.total_sentences == 5
    # legacy avg 7.8 (rounded) vs raw mean 7.8; diff must stay under 0.01
    assert abs(legacy.avg_sentence_length - mine) < 0.01
