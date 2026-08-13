"""Unit tests for the style authorship review model."""

from __future__ import annotations

from humanhand.domain.document_nodes import SourceLocation
from humanhand.domain.style_authorship import (
    VOICE_PROFILE_CLASSES,
    AuthorshipClass,
    AuthorshipMap,
    AuthorshipSpan,
    ExcludedSpan,
    build_span,
)


def _span(
    span_id: str = "a1",
    authorship_class: AuthorshipClass = AuthorshipClass.UNKNOWN,
    review_status: str = "unresolved",
) -> AuthorshipSpan:
    return AuthorshipSpan(
        span_id=span_id,
        source_location=SourceLocation(0, 10),
        text="hello world",
        authorship_class=authorship_class,
        review_status=review_status,
    )


class TestAuthorshipSpan:
    def test_defaults_unresolved(self) -> None:
        span = build_span(span_id="a1", start_offset=0, end_offset=5, text="hello")
        assert span.authorship_class is AuthorshipClass.UNKNOWN
        assert span.is_resolved is False
        assert span.is_voice_profile_eligible is False

    def test_voice_profile_eligibility(self) -> None:
        approved = _span(
            authorship_class=AuthorshipClass.AUTHENTIC_USER_PROSE,
            review_status="resolved",
        )
        assert approved.is_voice_profile_eligible is True
        resolved_but_quotation = _span(
            authorship_class=AuthorshipClass.QUOTATION, review_status="resolved"
        )
        assert resolved_but_quotation.is_voice_profile_eligible is False
        unresolved_authentic = _span(authorship_class=AuthorshipClass.USER_REVISION)
        assert unresolved_authentic.is_voice_profile_eligible is False

    def test_voice_profile_classes_exactly_two(self) -> None:
        assert {
            AuthorshipClass.AUTHENTIC_USER_PROSE,
            AuthorshipClass.USER_REVISION,
        } == VOICE_PROFILE_CLASSES


class TestAuthorshipMap:
    def test_unresolved_and_resolution(self) -> None:
        mapping = AuthorshipMap(
            spans=(
                _span("a1"),
                _span(
                    "a2",
                    authorship_class=AuthorshipClass.BOILERPLATE,
                    review_status="resolved",
                ),
            ),
            excluded=(),
        )
        assert [span.span_id for span in mapping.unresolved_spans] == ["a1"]
        assert mapping.is_fully_resolved is False

    def test_by_id(self) -> None:
        mapping = AuthorshipMap(spans=(_span("a1"), _span("a2")), excluded=())
        assert mapping.by_id("a2").span_id == "a2"
        try:
            mapping.by_id("nope")
        except KeyError:
            pass
        else:
            raise AssertionError("expected KeyError")

    def test_excluded_spans_are_separate(self) -> None:
        excluded = ExcludedSpan(
            span_id="a3", source_location=SourceLocation(0, 2), reason="boilerplate"
        )
        mapping = AuthorshipMap(spans=(_span("a1"),), excluded=(excluded,))
        assert mapping.excluded[0].reason == "boilerplate"
        assert "a3" not in {span.span_id for span in mapping.spans}
