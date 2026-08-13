"""Unit tests for deterministic inflection preservation (EP-017)."""

from __future__ import annotations

from humanhand.domain.inflection import decline_inflection, inflect_target


class TestBaseForm:
    def test_identical_surface_and_lemma_returns_target(self) -> None:
        assert inflect_target("utilize", "utilize", "use") == "use"

    def test_case_variant_of_lemma_is_base_form(self) -> None:
        assert inflect_target("Utilize", "utilize", "use") == "Use"

    def test_all_caps_surface_is_base_form(self) -> None:
        assert inflect_target("UTILIZE", "utilize", "use") == "USE"


class TestSuffixProtocol:
    def test_ing_suffix_appends_to_target(self) -> None:
        assert inflect_target("utilizing", "utilize", "use") == "using"

    def test_ed_suffix_appends_to_target(self) -> None:
        # Mechanical protocol (documented): target + "ed", no stem modeling.
        assert inflect_target("utilized", "utilize", "use") == "used"

    def test_spelling_rule_changes_not_modeled(self) -> None:
        # The protocol is mechanical target + "ing"; the analyse ->
        # analyze spelling rule is out of scope and belongs to the
        # ruleset's own inflected entries (documented limitation).
        assert inflect_target("analysing", "analyse", "analyze") == "analyzing"

    def test_ing_form_of_base_lemma_appends_suffix(self) -> None:
        # "using" is the standard -ing form of "use"; the mechanical
        # protocol still returns target + "ing" (documented limitation).
        assert inflect_target("using", "use", "use") == "using"

    def test_lemma_ending_in_suffix_uses_base_form(self) -> None:
        # When the LEMMA itself ends in -ing, the surface equals the
        # lemma and the base-form branch applies without re-appending.
        assert inflect_target("using", "using", "sing") == "sing"


class TestDeclines:
    def test_plural_declines(self) -> None:
        assert inflect_target("utilizes", "utilize", "use") is None

    def test_irregular_form_declines(self) -> None:
        assert inflect_target("went", "go", "walk") is None

    def test_empty_surface_declines(self) -> None:
        assert inflect_target("", "utilize", "use") is None

    def test_empty_lemma_declines(self) -> None:
        assert inflect_target("using", "", "use") is None

    def test_empty_target_declines(self) -> None:
        assert inflect_target("using", "use", "") is None


class TestCasePreservation:
    def test_title_case_applied_to_suffix_form(self) -> None:
        assert inflect_target("Utilizing", "utilize", "use") == "Using"

    def test_all_caps_applied_to_suffix_form(self) -> None:
        assert inflect_target("UTILIZING", "utilize", "use") == "USING"

    def test_mixed_case_is_other(self) -> None:
        # Mixed case is documented as "other" format: passed through unchanged.
        assert inflect_target("iPhone", "iphone", "phone") == "phone"


class TestDeterminism:
    def test_repeated_calls_are_identical(self) -> None:
        first = inflect_target("UTILIZING", "utilize", "use")
        second = inflect_target("UTILIZING", "utilize", "use")
        assert first == second


class TestDeclineInflection:
    def test_all_caps_tag(self) -> None:
        assert decline_inflection("UTILIZE") == "all_caps"

    def test_title_case_tag(self) -> None:
        assert decline_inflection("Utilize") == "title_case"

    def test_ing_tag(self) -> None:
        assert decline_inflection("utilizing") == "ing"

    def test_ed_tag(self) -> None:
        assert decline_inflection("utilized") == "ed"

    def test_base_form_is_none(self) -> None:
        assert decline_inflection("utilize") is None

    def test_empty_is_none(self) -> None:
        assert decline_inflection("") is None
