"""Conservative collocation safety checks (stdlib only, deterministic).

A replacement is "collocation-safe" when inserting it cannot create a
forbidden adjacent-bigram pattern or a doubled token next to its
neighbors. The module declines (returns False) on any doubt, so
callers treat False as a strict no-op.

Forbidden bigrams (documented tiny list)
----------------------------------------
The curated list below contains double-article and doubled-token
patterns that a replacement must never create. It is intentionally
tiny; any OTHER doubled token is still caught by the generic
doubled-token check:

    ("a", "a") ("of", "of") ("the", "the") ("to", "to") ("use", "use")

Matching is case-insensitive and ignores leading/trailing ASCII
punctuation on tokens ("the." and "the" compare equal), so "the the."
is declined too.

Window semantics (documented)
-----------------------------
The caller passes ``left_window`` and ``right_window``; the joined
window is ``left_window + replacement + right_window``. The forbidden
scan covers the whole joined window, so a pre-existing forbidden
pattern inside the window also declines (conservative by design; the
pipeline passes a bounded window so the scope is local). The doubled-
token check is limited to the replacement itself and its immediate
neighbors: the last token of the left window, the replacement's own
tokens, and the first token of the right window.
"""

from __future__ import annotations

import string

# Documented tiny list of forbidden adjacent bigrams. Every entry is a
# doubled-token or double-article pattern that a replacement must not
# create.
_FORBIDDEN_BIGRAMS: frozenset[tuple[str, str]] = frozenset(
    {
        ("a", "a"),
        ("of", "of"),
        ("the", "the"),
        ("to", "to"),
        ("use", "use"),
    }
)

_PUNCTUATION_CHARS = string.punctuation


def _tokens(window: str) -> tuple[str, ...]:
    """Whitespace tokens with leading/trailing ASCII punctuation stripped.

    Tokens that collapse to empty (pure punctuation) are dropped so
    that e.g. "the." and "the" compare equal.
    """
    cleaned: list[str] = []
    for raw in window.split():
        token = raw.strip(_PUNCTUATION_CHARS)
        if token:
            cleaned.append(token)
    return tuple(cleaned)


def check_doubled_tokens(window: str) -> tuple[str, ...]:
    """Return doubled adjacent tokens found in ``window`` (deterministic).

    Detection is case-insensitive and punctuation-insensitive (same
    tokenization as the collocation check); results are deduplicated
    and returned in first-occurrence order.
    """
    tokens = _tokens(window)
    found: list[str] = []
    seen: set[str] = set()
    for left, right in zip(tokens, tokens[1:], strict=False):
        key = left.lower()
        if key == right.lower() and key not in seen:
            seen.add(key)
            found.append(key)
    return tuple(found)


def collocation_preserved(
    text: str,
    offset: int,
    length: int,
    replacement: str,
    *,
    left_window: str,
    right_window: str,
) -> bool:
    """Return True when ``replacement`` is collocation-safe.

    Declines (False) when: the replacement is empty or has leading or
    trailing whitespace; the replaced span (``offset``/``length``) is
    not inside ``text``; the joined window contains a forbidden bigram
    from the documented tiny list; or the replacement creates a
    doubled token with its neighbors. Deterministic; False on any
    doubt (no-op contract).
    """
    if not replacement or replacement != replacement.strip():
        return False
    if offset < 0 or length <= 0 or offset + length > len(text):
        return False
    joined_tokens = _tokens(left_window + replacement + right_window)
    for left, right in zip(joined_tokens, joined_tokens[1:], strict=False):
        if (left.lower(), right.lower()) in _FORBIDDEN_BIGRAMS:
            return False
    lowered_replacement = [token.lower() for token in _tokens(replacement)]
    if not lowered_replacement:
        return False
    left_neighbors = _tokens(left_window)
    right_neighbors = _tokens(right_window)
    if left_neighbors and lowered_replacement[0] == left_neighbors[-1].lower():
        return False
    if right_neighbors and lowered_replacement[-1] == right_neighbors[0].lower():
        return False
    for left, right in zip(lowered_replacement, lowered_replacement[1:], strict=False):
        if left == right:
            return False
    return True
