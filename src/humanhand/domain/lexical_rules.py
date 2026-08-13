"""Pure rule-layer helpers for deterministic lexical matching.

Rule matching is intentionally mechanical: an exact lowercase lemma match,
then deterministic precedence/rule-id selection. No model, no statistics,
and no guesswork beyond the documented suffix POS heuristic.
"""

from __future__ import annotations

from humanhand.domain.lexical_types import (
    PRECEDENCE_ORDER,
    LexicalRule,
)


def token_to_lemma(token: str) -> str:
    """Lowercase the surface token; no stemming, no punctuation stripping.

    The lemma is exactly the lowercased surface token so spellings stay
    traceable to their offsets. Punctuation handling belongs to the
    proposal stage, not to lemma derivation.
    """
    return token.lower()


def rule_applies(rule: LexicalRule, lemma: str) -> bool:
    """True when the rule's source lemma matches the given lemma."""
    return rule.source_token == lemma


def select_rule_for_lemma(rules: tuple[LexicalRule, ...], lemma: str) -> LexicalRule | None:
    """Deterministically select the strongest matching rule.

    Matching rules are ordered by precedence (strongest first, SPEC-014);
    ties resolve by lexicographically smallest rule id. Returns None when
    no rule matches.
    """
    matches = [rule for rule in rules if rule_applies(rule, lemma)]
    if not matches:
        return None
    precedence_rank = {value: index for index, value in enumerate(PRECEDENCE_ORDER)}
    return min(
        matches,
        key=lambda rule: (precedence_rank[rule.precedence], rule.rule_id),
    )


def estimate_part_of_speech(token: str) -> str:
    """Deterministic suffix-only POS heuristic.

    Documented mapping, and nothing beyond these suffixes is guessed:
    -ing / -ed -> verb; -ly -> adverb; -tion / -ment / -ness -> noun;
    -ous / -ive / -al -> adjective; anything else -> other.
    """
    lower = token.lower()
    if lower.endswith(("ing", "ed")):
        return "verb"
    if lower.endswith("ly"):
        return "adverb"
    if lower.endswith(("tion", "ment", "ness")):
        return "noun"
    if lower.endswith(("ous", "ive", "al")):
        return "adjective"
    return "other"


__all__ = [
    "estimate_part_of_speech",
    "rule_applies",
    "select_rule_for_lemma",
    "token_to_lemma",
]
