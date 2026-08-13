"""Lexical eligibility contexts — deterministic per-token proposal input.

One :class:`LexicalContext` is built per whitespace-separated token
occurrence with exact character offsets, bounded windows, protected-span
coverage, and the documented suffix POS heuristic (SPEC-014 / ADR-007).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from humanhand.domain.lexical_rules import estimate_part_of_speech, token_to_lemma
from humanhand.domain.lexical_types import LexicalPrecedence, LexicalRule
from humanhand.domain.protected_spans import ProtectedSpanSet

_TOKEN_RE = re.compile(r"\S+")
_WINDOW_SIZE = 3


@dataclass(frozen=True)
class LexicalContext:
    """Deterministic eligibility context for one token occurrence."""

    token: str
    lemma: str
    offset: int
    left_window: str
    right_window: str
    protected_span_ids: tuple[str, ...]
    part_of_speech: str


def build_contexts(text: str, spans: ProtectedSpanSet) -> tuple[LexicalContext, ...]:
    """Build one context per whitespace-separated token occurrence.

    Offsets are exact character offsets into ``text``. A token offset is
    covered by a span when ``span.start_offset <= offset < span.end_offset``
    using the real span objects' source locations. Windows hold up to three
    neighboring surface tokens; the left window is lowercased and the right
    window keeps original casing. Deterministic for equal inputs.
    """
    tokens: list[tuple[str, int]] = [
        (match.group(0), match.start()) for match in _TOKEN_RE.finditer(text)
    ]
    contexts: list[LexicalContext] = []
    for index, (surface, offset) in enumerate(tokens):
        left_window = " ".join(
            tokens[i][0].lower() for i in range(max(0, index - _WINDOW_SIZE), index)
        )
        right_window = " ".join(
            tokens[i][0] for i in range(index + 1, min(len(tokens), index + 1 + _WINDOW_SIZE))
        )
        covered_ids = tuple(
            span.span_id
            for span in spans.spans
            if span.source_location.start_offset <= offset < span.source_location.end_offset
        )
        contexts.append(
            LexicalContext(
                token=surface,
                lemma=token_to_lemma(surface),
                offset=offset,
                left_window=left_window,
                right_window=right_window,
                protected_span_ids=covered_ids,
                part_of_speech=estimate_part_of_speech(surface),
            )
        )
    return tuple(contexts)


def context_in_protected_span(context: LexicalContext) -> bool:
    """True when the context's token sits inside at least one protected span."""
    return len(context.protected_span_ids) > 0


def resolve_precedence(
    *,
    in_protected_span: bool,
    rule: LexicalRule | None,
    user_preference: LexicalRule | None,
    project_glossary: LexicalRule | None,
    register_rule: LexicalRule | None,
    domain_glossary: LexicalRule | None,
) -> LexicalPrecedence:
    """Resolve the effective precedence for one candidate change (SPEC-014).

    A protected span wins over everything. Otherwise the strongest
    explicitly supplied source wins: user preference, project glossary,
    register evidence, domain glossary, then the base rule's own
    precedence (curated or licensed). NO_CHANGE when no rule applies.
    """
    if in_protected_span:
        return LexicalPrecedence.PROTECTED_SPAN
    if user_preference is not None:
        return LexicalPrecedence.USER_PREFERENCE
    if project_glossary is not None:
        return LexicalPrecedence.PROJECT_GLOSSARY
    if register_rule is not None:
        return LexicalPrecedence.REGISTER_EVIDENCE
    if domain_glossary is not None:
        return LexicalPrecedence.DOMAIN_GLOSSARY
    if rule is not None:
        return rule.precedence
    return LexicalPrecedence.NO_CHANGE
