"""Deterministic Unicode policy and text inventory for clean-room imports."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from humanhand.domain.import_findings import (
    FindingCategory,
    FindingCode,
    FindingSeverity,
    ImportFinding,
)

_NORMALIZATION_FORMS: tuple[Literal["NFC", "NFD", "NFKC", "NFKD"], ...] = (
    "NFC",
    "NFD",
    "NFKC",
    "NFKD",
)

_UTF32_LE_BOM = b"\xff\xfe\x00\x00"
_UTF32_BE_BOM = b"\x00\x00\xfe\xff"
_UTF16_LE_BOM = b"\xff\xfe"
_UTF16_BE_BOM = b"\xfe\xff"
_UTF8_BOM = b"\xef\xbb\xbf"


class NormalizationForm(StrEnum):
    """Detected Unicode normalization forms."""

    NFC = "nfc"
    NFD = "nfd"
    NFKC = "nfkc"
    NFKD = "nfkd"
    OTHER = "other"


_FORM_TO_ENUM: dict[str, NormalizationForm] = {
    "NFC": NormalizationForm.NFC,
    "NFD": NormalizationForm.NFD,
    "NFKC": NormalizationForm.NFKC,
    "NFKD": NormalizationForm.NFKD,
}


@dataclass(frozen=True)
class UnicodePolicy:
    """Deterministic encoding/normalization policy for an import."""

    required_encoding: str = "utf-8"
    allow_bom: bool = False
    reject_control_chars: bool = False
    canonical_normalization: str = "nfc"


def detect_bom_bytes(raw: bytes) -> str:
    """Detect a byte-order mark deterministically at the byte level.

    Returns one of ``utf-8``, ``utf-16-le``, ``utf-16-be``, ``utf-32-le``,
    ``utf-32-be``, or ``""`` when no BOM is present.
    """
    if raw.startswith(_UTF32_LE_BOM):
        return "utf-32-le"
    if raw.startswith(_UTF32_BE_BOM):
        return "utf-32-be"
    if raw.startswith(_UTF8_BOM):
        return "utf-8"
    if raw.startswith(_UTF16_LE_BOM):
        return "utf-16-le"
    if raw.startswith(_UTF16_BE_BOM):
        return "utf-16-be"
    return ""


def _normalization_form(text: str) -> NormalizationForm:
    for form in _NORMALIZATION_FORMS:
        if unicodedata.is_normalized(form, text):
            return _FORM_TO_ENUM[form]
    return NormalizationForm.OTHER


def _control_char_offsets(text: str) -> tuple[int, ...]:
    return tuple(
        index
        for index, char in enumerate(text)
        if unicodedata.category(char) == "Cc" and char not in ("\t", "\n", "\r")
    )


def _surrogate_offsets(text: str) -> tuple[int, ...]:
    return tuple(index for index, char in enumerate(text) if 0xD800 <= ord(char) <= 0xDFFF)


def _non_nfc_offsets(text: str) -> tuple[int, ...]:
    if unicodedata.is_normalized("NFC", text):
        return ()
    composed = unicodedata.normalize("NFC", text)
    min_length = min(len(text), len(composed))
    offsets = [index for index in range(min_length) if text[index] != composed[index]]
    if len(text) > len(composed):
        offsets.extend(range(len(composed), len(text)))
    return tuple(offsets)


def _line_ending(text: str) -> str:
    if "\n" not in text and "\r" not in text:
        return "none"
    has_crlf = "\r\n" in text
    has_lone_lf = any(
        char == "\n" and (index == 0 or text[index - 1] != "\r") for index, char in enumerate(text)
    )
    has_lone_cr = any(
        char == "\r" and (index + 1 >= len(text) or text[index + 1] != "\n")
        for index, char in enumerate(text)
    )
    kinds = sum((has_crlf, has_lone_lf, has_lone_cr))
    if kinds > 1:
        return "mixed"
    if has_crlf:
        return "crlf"
    if has_lone_lf:
        return "lf"
    if has_lone_cr:
        return "cr"
    return "none"


@dataclass(frozen=True)
class UnicodeInventory:
    """Deterministic inventory of a decoded text's Unicode properties.

    Offsets are character offsets into the decoded text. No document text is
    retained here; offsets and counts only. BOM state is populated from
    byte-level detection by the caller (see :func:`detect_bom_bytes`).
    """

    has_bom: bool
    bom_name: str
    normalization_form: NormalizationForm
    control_char_offsets: tuple[int, ...]
    surrogate_offsets: tuple[int, ...]
    non_nfc_offsets: tuple[int, ...]
    line_ending: str
    codepoint_count: int

    @property
    def is_nfc(self) -> bool:
        return self.normalization_form is NormalizationForm.NFC

    def to_payload(self) -> dict[str, object]:
        """Render the inventory as a plain JSON-ready mapping."""
        return {
            "has_bom": self.has_bom,
            "bom_name": self.bom_name,
            "normalization_form": self.normalization_form.value,
            "control_char_count": len(self.control_char_offsets),
            "control_char_offsets": list(self.control_char_offsets),
            "surrogate_count": len(self.surrogate_offsets),
            "surrogate_offsets": list(self.surrogate_offsets),
            "non_nfc_count": len(self.non_nfc_offsets),
            "non_nfc_offsets": list(self.non_nfc_offsets),
            "line_ending": self.line_ending,
            "codepoint_count": self.codepoint_count,
        }


def inventory_unicode(text: str, *, bom_name: str = "") -> UnicodeInventory:
    """Build a deterministic Unicode inventory for decoded text.

    Args:
        text: Decoded text (BOM may still be present as a leading U+FEFF).
        bom_name: Byte-level BOM name from :func:`detect_bom_bytes`, or ``""``.
    """
    return UnicodeInventory(
        has_bom=bool(bom_name),
        bom_name=bom_name,
        normalization_form=_normalization_form(text),
        control_char_offsets=_control_char_offsets(text),
        surrogate_offsets=_surrogate_offsets(text),
        non_nfc_offsets=_non_nfc_offsets(text),
        line_ending=_line_ending(text),
        codepoint_count=len(text),
    )


def canonical_text_view(text: str) -> str:
    """Return the deterministic NFC canonical text view of ``text``."""
    return unicodedata.normalize("NFC", text)


def strip_bom(text: str) -> str:
    """Remove a leading BOM code point (U+FEFF) when present."""
    if text.startswith("﻿"):
        return text[1:]
    return text


def unicode_findings(inventory: UnicodeInventory) -> tuple[ImportFinding, ...]:
    """Return deterministic findings for a Unicode inventory."""
    findings: list[ImportFinding] = []
    if inventory.has_bom:
        findings.append(
            ImportFinding(
                code=FindingCode.ENCODING_BOM,
                severity=FindingSeverity.WARNING,
                category=FindingCategory.ENCODING,
                description=f"BOM present: {inventory.bom_name}",
                evidence=f"bom={inventory.bom_name}",
            )
        )
    if inventory.control_char_offsets:
        findings.append(
            ImportFinding(
                code=FindingCode.UNICODE_CONTROL_CHARS,
                severity=FindingSeverity.WARNING,
                category=FindingCategory.ENCODING,
                description=f"{len(inventory.control_char_offsets)} control character(s) present",
                evidence=f"first_offset={inventory.control_char_offsets[0]}",
            )
        )
    if inventory.surrogate_offsets:
        findings.append(
            ImportFinding(
                code=FindingCode.UNICODE_SURROGATES,
                severity=FindingSeverity.ERROR,
                category=FindingCategory.ENCODING,
                description=f"{len(inventory.surrogate_offsets)} surrogate code point(s) present",
                evidence=f"first_offset={inventory.surrogate_offsets[0]}",
            )
        )
    if not inventory.is_nfc:
        findings.append(
            ImportFinding(
                code=FindingCode.UNICODE_NOT_NFC,
                severity=FindingSeverity.WARNING,
                category=FindingCategory.ENCODING,
                description=f"Text is {inventory.normalization_form.value}, not NFC",
                evidence=f"form={inventory.normalization_form.value}",
            )
        )
    if inventory.line_ending == "mixed":
        findings.append(
            ImportFinding(
                code=FindingCode.LINE_ENDINGS_MIXED,
                severity=FindingSeverity.WARNING,
                category=FindingCategory.STRUCTURE,
                description="Mixed line endings present",
                evidence="line_ending=mixed",
            )
        )
    return tuple(findings)
