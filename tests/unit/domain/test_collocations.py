"""Unit tests for conservative collocation safety checks (EP-017)."""

from __future__ import annotations

from humanhand.domain.collocations import check_doubled_tokens, collocation_preserved


def _check(replacement: str, left: str = "", right: str = "") -> bool:
    """Replace the marker "xyz" in left+"xyz"+right and ask for safety."""
    text = left + "xyz" + right
    return collocation_preserved(
        text,
        offset=len(left),
        length=3,
        replacement=replacement,
        left_window=left,
        right_window=right,
    )


class TestForbiddenBigrams:
    def test_pre_existing_doubled_the_declines(self) -> None:
        assert _check("use", left="the the ") is False

    def test_creation_of_doubled_article_declines(self) -> None:
        assert _check("a", left="a ") is False

    def test_forbidden_bigram_across_right_neighbor(self) -> None:
        assert _check("of", right=" of it") is False

    def test_punctuation_insensitive_forbidden_bigram(self) -> None:
        assert _check("the.", right=" the") is False


class TestDoubledNeighbors:
    def test_repeats_preceding_token_declines(self) -> None:
        assert _check("use", left="We use ") is False

    def test_repeats_following_token_declines(self) -> None:
        assert _check("use", right=" use it") is False

    def test_repeats_preceding_token_case_insensitive(self) -> None:
        assert _check("Use", left="We use ") is False

    def test_repeats_following_token_with_punctuation(self) -> None:
        assert _check("use", right=" use.") is False

    def test_doubled_replacement_internal_declines(self) -> None:
        assert _check("use use") is False

    def test_clean_replacement_passes(self) -> None:
        assert _check("use", left="We ", right=" the tool") is True


class TestDeclines:
    def test_empty_replacement_declines(self) -> None:
        assert _check("") is False

    def test_leading_whitespace_replacement_declines(self) -> None:
        assert _check(" use") is False

    def test_trailing_whitespace_replacement_declines(self) -> None:
        assert _check("use ") is False

    def test_pure_punctuation_replacement_declines(self) -> None:
        assert _check("...") is False

    def test_negative_offset_declines(self) -> None:
        assert (
            collocation_preserved(
                "abc", offset=-1, length=1, replacement="x", left_window="", right_window=""
            )
            is False
        )

    def test_zero_length_declines(self) -> None:
        assert (
            collocation_preserved(
                "abc", offset=0, length=0, replacement="x", left_window="", right_window=""
            )
            is False
        )

    def test_span_beyond_text_declines(self) -> None:
        assert (
            collocation_preserved(
                "abc", offset=2, length=2, replacement="x", left_window="", right_window=""
            )
            is False
        )


class TestCheckDoubledTokens:
    def test_no_doubles(self) -> None:
        assert check_doubled_tokens("a b c") == ()

    def test_single_double(self) -> None:
        assert check_doubled_tokens("the the end") == ("the",)

    def test_case_insensitive(self) -> None:
        assert check_doubled_tokens("The the") == ("the",)

    def test_punctuation_insensitive(self) -> None:
        assert check_doubled_tokens("the the.") == ("the",)

    def test_deduplicated_first_occurrence_order(self) -> None:
        assert check_doubled_tokens("a b b c c c") == ("b", "c")

    def test_empty_window(self) -> None:
        assert check_doubled_tokens("") == ()
