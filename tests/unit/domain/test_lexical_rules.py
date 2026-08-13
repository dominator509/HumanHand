"""Unit tests for pure rule-layer matching helpers."""

from __future__ import annotations

import pytest

from humanhand.domain.lexical_rules import (
    estimate_part_of_speech,
    rule_applies,
    select_rule_for_lemma,
    token_to_lemma,
)
from humanhand.domain.lexical_types import LexicalPrecedence, LexicalRule


def _rule(
    rule_id: str,
    source: str,
    precedence: LexicalPrecedence = LexicalPrecedence.CURATED_RULE,
) -> LexicalRule:
    return LexicalRule(
        rule_id=rule_id,
        source_token=source,
        target_token="use",
        sense="general",
        precedence=precedence,
        confidence=0.9,
        provenance="curated-in-repo",
    )


class TestTokenToLemma:
    def test_lowercases(self) -> None:
        assert token_to_lemma("Utilize") == "utilize"

    def test_preserves_surface_punctuation(self) -> None:
        # Lemma derivation never strips punctuation; the surface token
        # stays traceable to its offset.
        assert token_to_lemma("running,") == "running,"


class TestRuleApplies:
    def test_exact_lemma_match(self) -> None:
        assert rule_applies(_rule("cr-1", "utilize"), "utilize") is True

    def test_mismatch(self) -> None:
        assert rule_applies(_rule("cr-1", "utilize"), "commence") is False


class TestSelectRuleForLemma:
    def test_none_when_no_match(self) -> None:
        assert select_rule_for_lemma((_rule("cr-1", "utilize"),), "xylophone") is None

    def test_returns_matching_rule(self) -> None:
        rules = (_rule("cr-1", "utilize"), _rule("cr-2", "commence"))
        selected = select_rule_for_lemma(rules, "utilize")
        assert selected is not None
        assert selected.rule_id == "cr-1"

    def test_higher_precedence_wins(self) -> None:
        rules = (
            _rule("cr-1", "utilize"),
            _rule("gl-1", "utilize", LexicalPrecedence.DOMAIN_GLOSSARY),
            _rule("up-1", "utilize", LexicalPrecedence.USER_PREFERENCE),
        )
        selected = select_rule_for_lemma(rules, "utilize")
        assert selected is not None
        assert selected.rule_id == "up-1"

    def test_tie_breaks_by_rule_id(self) -> None:
        rules = (_rule("cr-b", "utilize"), _rule("cr-a", "utilize"))
        selected = select_rule_for_lemma(rules, "utilize")
        assert selected is not None
        assert selected.rule_id == "cr-a"

    def test_deterministic_repeated_calls(self) -> None:
        rules = (_rule("cr-b", "utilize"), _rule("cr-a", "utilize"))
        first = select_rule_for_lemma(rules, "utilize")
        second = select_rule_for_lemma(rules, "utilize")
        assert first is not None and second is not None
        assert first.rule_id == second.rule_id


class TestEstimatePartOfSpeech:
    @pytest.mark.parametrize(
        ("token", "expected"),
        [
            ("running", "verb"),
            ("walked", "verb"),
            ("winged", "verb"),
            ("quickly", "adverb"),
            ("evaluation", "noun"),
            ("agreement", "noun"),
            ("kindness", "noun"),
            ("curious", "adjective"),
            ("active", "adjective"),
            ("global", "adjective"),
            ("train", "other"),
            ("the", "other"),
            ("42", "other"),
        ],
    )
    def test_suffix_heuristics(self, token: str, expected: str) -> None:
        assert estimate_part_of_speech(token) == expected
