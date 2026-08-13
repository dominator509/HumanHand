"""Unit tests for deterministic Unicode policy and inventory."""

from __future__ import annotations

import pytest

from humanhand.domain.import_findings import FindingCode, FindingSeverity
from humanhand.domain.unicode_policy import (
    NormalizationForm,
    UnicodePolicy,
    canonical_text_view,
    detect_bom_bytes,
    inventory_unicode,
    strip_bom,
    unicode_findings,
)


class TestDetectBomBytes:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (b"\xef\xbb\xbfhello", "utf-8"),
            (b"\xff\xfex\x00", "utf-16-le"),
            (b"\xfe\xff\x00x", "utf-16-be"),
            (b"\xff\xfe\x00\x00x", "utf-32-le"),
            (b"\x00\x00\xfe\xffx", "utf-32-be"),
            (b"hello", ""),
            (b"", ""),
            (b"# plain", ""),
        ],
    )
    def test_detects_or_omits(self, raw: bytes, expected: str) -> None:
        assert detect_bom_bytes(raw) == expected


class TestInventoryUnicode:
    def test_clean_nfc_text(self) -> None:
        inventory = inventory_unicode("Hello world.\n")
        assert inventory.has_bom is False
        assert inventory.bom_name == ""
        assert inventory.is_nfc is True
        assert inventory.normalization_form is NormalizationForm.NFC
        assert inventory.control_char_offsets == ()
        assert inventory.surrogate_offsets == ()
        assert inventory.non_nfc_offsets == ()
        assert inventory.line_ending == "lf"
        assert inventory.codepoint_count == 13

    def test_decomposed_text_is_not_nfc(self) -> None:
        text = "café"
        inventory = inventory_unicode(text)
        assert inventory.is_nfc is False
        assert inventory.normalization_form is NormalizationForm.NFD
        # Offsets 3 and 4 are the "e" + combining accent pair that composes
        # to "é" in the NFC view.
        assert inventory.non_nfc_offsets == (3, 4)
        assert canonical_text_view(text) == "café"

    def test_control_characters_inventoried(self) -> None:
        inventory = inventory_unicode("ab\x07cd")
        assert inventory.control_char_offsets == (2,)

    def test_tabs_and_newlines_are_not_flagged(self) -> None:
        inventory = inventory_unicode("a\tb\nc\rd")
        assert inventory.control_char_offsets == ()

    def test_lone_surrogate_inventoried(self) -> None:
        inventory = inventory_unicode("ab\ud800cd")
        assert inventory.surrogate_offsets == (2,)

    def test_line_ending_kinds(self) -> None:
        assert inventory_unicode("a\nb\n").line_ending == "lf"
        assert inventory_unicode("a\r\nb\r\n").line_ending == "crlf"
        assert inventory_unicode("a\rb\r").line_ending == "cr"
        assert inventory_unicode("a\nb\r\nc").line_ending == "mixed"

    def test_bom_name_recorded(self) -> None:
        inventory = inventory_unicode("﻿hello", bom_name="utf-8")
        assert inventory.has_bom is True
        assert inventory.bom_name == "utf-8"

    def test_payload_shape(self) -> None:
        payload = inventory_unicode("ab\x07").to_payload()
        assert payload["control_char_count"] == 1
        assert payload["control_char_offsets"] == [2]
        assert payload["normalization_form"] == "nfc"


class TestStripBom:
    def test_strips_utf8_bom(self) -> None:
        assert strip_bom("﻿hello") == "hello"

    def test_keeps_plain_text(self) -> None:
        assert strip_bom("hello") == "hello"


class TestUnicodeFindings:
    def test_clean_text_no_findings(self) -> None:
        assert unicode_findings(inventory_unicode("plain")) == ()

    def test_bom_finding(self) -> None:
        findings = unicode_findings(inventory_unicode("﻿x", bom_name="utf-8"))
        assert [finding.code for finding in findings] == [FindingCode.ENCODING_BOM]
        assert findings[0].severity is FindingSeverity.WARNING

    def test_control_char_finding(self) -> None:
        findings = unicode_findings(inventory_unicode("a\x07b"))
        assert [finding.code for finding in findings] == [FindingCode.UNICODE_CONTROL_CHARS]

    def test_surrogate_finding_is_error(self) -> None:
        findings = unicode_findings(inventory_unicode("a\ud800b"))
        assert [finding.code for finding in findings] == [FindingCode.UNICODE_SURROGATES]
        assert findings[0].severity is FindingSeverity.ERROR

    def test_not_nfc_finding(self) -> None:
        findings = unicode_findings(inventory_unicode("café"))
        assert [finding.code for finding in findings] == [FindingCode.UNICODE_NOT_NFC]

    def test_mixed_line_endings_finding(self) -> None:
        findings = unicode_findings(inventory_unicode("a\nb\r\nc"))
        assert [finding.code for finding in findings] == [FindingCode.LINE_ENDINGS_MIXED]


class TestUnicodePolicyDefaults:
    def test_defaults(self) -> None:
        policy = UnicodePolicy()
        assert policy.required_encoding == "utf-8"
        assert policy.allow_bom is False
        assert policy.reject_control_chars is False
        assert policy.canonical_normalization == "nfc"
