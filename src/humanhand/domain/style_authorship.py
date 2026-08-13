"""Authorship review model for the Style Fidelity Vault.

Authorship classification is NEVER inferred automatically. The only
deterministic pre-classification is structural: spans covering QUOTATION
nodes map to the QUOTATION class. Every other span starts UNKNOWN and
requires an explicit, recorded review decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from humanhand.domain.document_nodes import SourceLocation


class AuthorshipClass(StrEnum):
    """Authorship classes from blueprint 8.3."""

    AUTHENTIC_USER_PROSE = "authentic_user_prose"
    USER_REVISION = "user_revision"
    QUOTATION = "quotation"
    EXTERNAL_SOURCE = "external_source"
    BOILERPLATE = "boilerplate"
    FORM_FIELD = "form_field"
    SIGNATURE = "signature"
    REVIEWER_TEXT = "reviewer_text"
    AI_ASSISTED = "ai_assisted"
    UNKNOWN = "unknown"
    EXCLUDE = "exclude"


# Classes that may enter the default voice profile (blueprint 8.3).
VOICE_PROFILE_CLASSES = frozenset(
    {AuthorshipClass.AUTHENTIC_USER_PROSE, AuthorshipClass.USER_REVISION}
)


@dataclass(frozen=True)
class AuthorshipSpan:
    """One reviewable text region of a style sample."""

    span_id: str
    source_location: SourceLocation
    text: str
    authorship_class: AuthorshipClass = AuthorshipClass.UNKNOWN
    review_status: str = "unresolved"  # "unresolved" | "resolved"
    decided_by: str = ""  # "structural" | "cli" | ""

    @property
    def is_resolved(self) -> bool:
        return (
            self.review_status == "resolved"
            and self.authorship_class is not AuthorshipClass.UNKNOWN
        )

    @property
    def is_voice_profile_eligible(self) -> bool:
        return self.is_resolved and self.authorship_class in VOICE_PROFILE_CLASSES


@dataclass(frozen=True)
class ExcludedSpan:
    """A span the reviewer explicitly excluded from the voice profile."""

    span_id: str
    source_location: SourceLocation
    reason: str


@dataclass(frozen=True)
class AuthorshipMap:
    """Immutable authorship state for one style evidence package."""

    spans: tuple[AuthorshipSpan, ...]
    excluded: tuple[ExcludedSpan, ...]

    @property
    def unresolved_spans(self) -> tuple[AuthorshipSpan, ...]:
        return tuple(span for span in self.spans if not span.is_resolved)

    @property
    def is_fully_resolved(self) -> bool:
        return not self.unresolved_spans

    def by_id(self, span_id: str) -> AuthorshipSpan:
        for span in self.spans:
            if span.span_id == span_id:
                return span
        raise KeyError(span_id)


def build_span(
    *,
    span_id: str,
    start_offset: int,
    end_offset: int,
    text: str,
    line_start: int = 1,
    line_end: int = 1,
    authorship_class: AuthorshipClass = AuthorshipClass.UNKNOWN,
) -> AuthorshipSpan:
    """Build one authorship span with a valid source location."""
    return AuthorshipSpan(
        span_id=span_id,
        source_location=SourceLocation(
            start_offset=start_offset,
            end_offset=end_offset,
            line_start=line_start,
            line_end=line_end,
        ),
        text=text,
        authorship_class=authorship_class,
    )


def approved_voice_text(authorship: AuthorshipMap) -> str:
    """Concatenated text of approved voice-profile spans, in document order.

    Only resolved AUTHENTIC_USER_PROSE / USER_REVISION spans contribute
    (blueprint 8.3). This is the single domain-side voice filter used by
    both the vault use cases and the profile builder.
    """
    parts = [span.text for span in authorship.spans if span.is_voice_profile_eligible]
    return "\n\n".join(parts)
