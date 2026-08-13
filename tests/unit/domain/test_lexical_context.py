"""Unit tests for lexical eligibility contexts and precedence resolution."""

from __future__ import annotations

from humanhand.domain.document_nodes import SourceLocation
from humanhand.domain.lexical_context import (
    build_contexts,
    context_in_protected_span,
    resolve_precedence,
)
from humanhand.domain.lexical_types import LexicalPrecedence, LexicalRule
from humanhand.domain.protected_spans import (
    ProtectedSpan,
    ProtectedSpanSet,
    SpanKind,
    build_protected_span_set,
)


def _rule(
    rule_id: str,
    precedence: LexicalPrecedence = LexicalPrecedence.CURATED_RULE,
) -> LexicalRule:
    return LexicalRule(
        rule_id=rule_id,
        source_token="utilize",
        target_token="use",
        sense="general",
        precedence=precedence,
        confidence=0.9,
        provenance="curated-in-repo",
    )


def _empty_spans() -> ProtectedSpanSet:
    return build_protected_span_set(())


class TestBuildContexts:
    def test_offsets_exact_for_fixed_sentence(self) -> None:
        text = "The running train quickly accelerates."
        # Hand-computed character offsets:
        #   The(0-2) ' '(3) running(4-10) ' '(11) train(12-16) ' '(17)
        #   quickly(18-24) ' '(25) accelerates.(26-37)
        # Tokens are whitespace-separated runs, so the trailing period
        # stays attached to the final surface token.
        contexts = build_contexts(text, _empty_spans())
        assert [context.token for context in contexts] == [
            "The",
            "running",
            "train",
            "quickly",
            "accelerates.",
        ]
        assert [context.offset for context in contexts] == [0, 4, 12, 18, 26]

    def test_left_window_lowercased(self) -> None:
        text = "The running train"
        contexts = build_contexts(text, _empty_spans())
        assert contexts[0].left_window == ""
        assert contexts[1].left_window == "the"
        assert contexts[2].left_window == "the running"

    def test_right_window_keeps_case(self) -> None:
        text = "The running train"
        contexts = build_contexts(text, _empty_spans())
        assert contexts[0].right_window == "running train"
        assert contexts[2].right_window == ""

    def test_windows_capped_at_three(self) -> None:
        text = "a b c d e f g"
        contexts = build_contexts(text, _empty_spans())
        assert contexts[2].left_window == "a b"
        assert contexts[2].right_window == "d e f"
        assert contexts[3].left_window == "a b c"
        assert contexts[3].right_window == "e f g"

    def test_lemma_is_lowercase_surface(self) -> None:
        text = "Utilize quickly"
        contexts = build_contexts(text, _empty_spans())
        assert contexts[0].lemma == "utilize"
        assert contexts[1].lemma == "quickly"

    def test_pos_suffix_heuristics(self) -> None:
        text = "The running train quickly accelerates"
        contexts = build_contexts(text, _empty_spans())
        pos = {context.token: context.part_of_speech for context in contexts}
        assert pos == {
            "The": "other",
            "running": "verb",
            "train": "other",
            "quickly": "adverb",
            "accelerates": "other",
        }

    def test_empty_text_yields_no_contexts(self) -> None:
        assert build_contexts("", _empty_spans()) == ()

    def test_deterministic_repeated_calls(self) -> None:
        text = "The running train quickly accelerates."
        spans = _empty_spans()
        assert build_contexts(text, spans) == build_contexts(text, spans)


class TestProtectedSpanContext:
    def test_span_ids_cover_token_offset(self) -> None:
        # "The answer is 42." — "42" occupies offsets [14, 16).
        text = "The answer is 42."
        spans = build_protected_span_set(
            (
                ProtectedSpan(
                    span_id="",
                    kind=SpanKind.NUMBER,
                    source_location=SourceLocation(14, 16),
                    text="42",
                ),
            )
        )
        contexts = build_contexts(text, spans)
        # The token is the whitespace-separated run "42."; its offset 14
        # still lies inside the span [14, 16).
        assert contexts[3].token == "42."
        assert contexts[3].offset == 14
        assert contexts[3].protected_span_ids == ("s1",)
        assert context_in_protected_span(contexts[3]) is True
        assert contexts[0].protected_span_ids == ()
        assert context_in_protected_span(contexts[0]) is False

    def test_mid_span_token_covered(self) -> None:
        # A quotation covering "the whole phrase" protects interior tokens
        # while tokens outside the span stay unprotected.
        text = "She said the whole phrase aloud."
        spans = build_protected_span_set(
            (
                ProtectedSpan(
                    span_id="",
                    kind=SpanKind.QUOTATION,
                    source_location=SourceLocation(9, 24),
                    text="the whole phrase",
                ),
            )
        )
        contexts = build_contexts(text, spans)
        by_token = {context.token: context for context in contexts}
        assert by_token["the"].protected_span_ids == ("s1",)
        assert by_token["phrase"].protected_span_ids == ("s1",)
        assert by_token["She"].protected_span_ids == ()
        assert by_token["aloud."].protected_span_ids == ()


class TestResolvePrecedence:
    def test_protected_span_wins_over_user_preference(self) -> None:
        result = resolve_precedence(
            in_protected_span=True,
            rule=_rule("cr-1"),
            user_preference=_rule("up-1", LexicalPrecedence.USER_PREFERENCE),
            project_glossary=None,
            register_rule=None,
            domain_glossary=None,
        )
        assert result is LexicalPrecedence.PROTECTED_SPAN

    def test_user_beats_project(self) -> None:
        result = resolve_precedence(
            in_protected_span=False,
            rule=_rule("cr-1"),
            user_preference=_rule("up-1", LexicalPrecedence.USER_PREFERENCE),
            project_glossary=_rule("pg-1", LexicalPrecedence.PROJECT_GLOSSARY),
            register_rule=None,
            domain_glossary=None,
        )
        assert result is LexicalPrecedence.USER_PREFERENCE

    def test_project_beats_register(self) -> None:
        result = resolve_precedence(
            in_protected_span=False,
            rule=_rule("cr-1"),
            user_preference=None,
            project_glossary=_rule("pg-1", LexicalPrecedence.PROJECT_GLOSSARY),
            register_rule=_rule("re-1", LexicalPrecedence.REGISTER_EVIDENCE),
            domain_glossary=None,
        )
        assert result is LexicalPrecedence.PROJECT_GLOSSARY

    def test_register_beats_domain(self) -> None:
        result = resolve_precedence(
            in_protected_span=False,
            rule=_rule("cr-1"),
            user_preference=None,
            project_glossary=None,
            register_rule=_rule("re-1", LexicalPrecedence.REGISTER_EVIDENCE),
            domain_glossary=_rule("dg-1", LexicalPrecedence.DOMAIN_GLOSSARY),
        )
        assert result is LexicalPrecedence.REGISTER_EVIDENCE

    def test_domain_beats_curated(self) -> None:
        result = resolve_precedence(
            in_protected_span=False,
            rule=_rule("cr-1"),
            user_preference=None,
            project_glossary=None,
            register_rule=None,
            domain_glossary=_rule("dg-1", LexicalPrecedence.DOMAIN_GLOSSARY),
        )
        assert result is LexicalPrecedence.DOMAIN_GLOSSARY

    def test_curated_rule_alone(self) -> None:
        result = resolve_precedence(
            in_protected_span=False,
            rule=_rule("cr-1"),
            user_preference=None,
            project_glossary=None,
            register_rule=None,
            domain_glossary=None,
        )
        assert result is LexicalPrecedence.CURATED_RULE

    def test_licensed_rule_alone(self) -> None:
        result = resolve_precedence(
            in_protected_span=False,
            rule=_rule("lr-1", LexicalPrecedence.LICENSED_RESOURCE),
            user_preference=None,
            project_glossary=None,
            register_rule=None,
            domain_glossary=None,
        )
        assert result is LexicalPrecedence.LICENSED_RESOURCE

    def test_no_source_yields_no_change(self) -> None:
        result = resolve_precedence(
            in_protected_span=False,
            rule=None,
            user_preference=None,
            project_glossary=None,
            register_rule=None,
            domain_glossary=None,
        )
        assert result is LexicalPrecedence.NO_CHANGE

    def test_deterministic_repeated_calls(self) -> None:
        def call() -> LexicalPrecedence:
            return resolve_precedence(
                in_protected_span=True,
                rule=_rule("cr-1"),
                user_preference=None,
                project_glossary=_rule("pg-1", LexicalPrecedence.PROJECT_GLOSSARY),
                register_rule=None,
                domain_glossary=None,
            )

        assert call() == call()
        assert call() is LexicalPrecedence.PROTECTED_SPAN
