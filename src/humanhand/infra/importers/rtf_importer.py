"""Clean-room RTF text adapter (EP-013).

Deterministic, stdlib-only RTF reader that extracts plain text and builds
canonical paragraph nodes. The parser never touches the filesystem or the
network; ``parse_payloads`` runs only on content bytes plus the policy.
Design choices, all documented so the behavior is auditable:

- Decoding: RTF's default ANSI code page is Windows-1252, so the raw bytes
  are decoded as ``cp1252`` with ``errors="replace"`` (defensive; Python's
  cp1252 codec maps every byte value, including the five slots that Windows
  cp1252 leaves undefined). Code page declarations such as ``\\ansicpgN`` are
  not honored; the cp1252 default applies. A leading UTF-8 BOM is stripped
  first and inventoried as an ``ENCODING_BOM`` warning. UTF-16/32 BOMs are
  rejected with ``ENCODING_UTF16_UNSUPPORTED``, mirroring the fail-closed
  behavior of the base text pipeline.
- Tokenizer: hand-rolled single-pass scan over the decoded text. A control
  word is ``\\word`` plus an optional signed digit parameter, delimited by a
  space (consumed and discarded) or by any other character (consumed now and
  reprocessed as a regular character, per the RTF rule). Control symbols
  ``\\'hh`` (one cp1252 byte), ``\\{``, ``\\}``, ``\\\\`` and ``\\x`` are
  recognized; group braces ``{`` ``}`` balance. Literal CR/LF characters in
  the file are ignored as whitespace, matching common RTF reader behavior;
  use ``\\par`` for paragraph breaks.
- Unicode: ``\\uN`` appends the code point (negative parameters are signed
  16-bit values adjusted by +65536 per the RTF rule; values above U+10FFFF
  become U+FFFD). The single ANSI fallback character immediately following
  ``\\uN`` is skipped because this reader supports Unicode — the real RTF
  ``\\u`` rule. The fallback is a text character or a ``\\'hh`` escape; any
  other token ends the pending skip.
- Destinations: the contents of known destination groups (``fonttbl``,
  ``colortbl``, ``stylesheet``, ``info``, ``generator``, plus ``object`` and
  ``field``) and of ``{\\*...}`` ignorable groups are skipped: they are
  formatting, metadata, or instructions, not body text.
- Paragraphs: ``\\par``, ``\\line``, ``\\cell`` and ``\\row`` end the current
  paragraph. The canonical AST has no RTF table nodes, so table cell and row
  boundaries are represented as paragraph breaks; the cell text itself still
  flows into paragraphs.
- Findings: embedded objects (``\\object``, ``\\objdata``, ``\\embedd``,
  ``\\result``) produce an ``ACTIVE_CONTENT_EMBED_OBJECT`` error; dynamic
  fields (``\\field``, ``\\fldinst``) and tables (``\\trowd``) produce
  ``UNSUPPORTED_FEATURE`` warnings. Each condition is reported once per
  document, in first-seen order.
- Coverage: ``paragraph`` is supported. ``table``, ``field`` and ``object``
  are listed as unsupported when detected. Status is ``complete`` when no
  unsupported structure or active content is present — a plain-text RTF is
  fully representable as paragraphs — and ``partial`` otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass

from humanhand.domain.canonical_document import CoverageSummary
from humanhand.domain.document_nodes import NodeBuilder, NodeType, SourceLocation
from humanhand.domain.file_identity import FileKind
from humanhand.domain.import_findings import (
    FindingCategory,
    FindingCode,
    FindingSeverity,
    ImportFinding,
)
from humanhand.domain.import_policy import ImportPolicy, check_limits
from humanhand.domain.metadata_inventory import MetadataInventory
from humanhand.domain.unicode_policy import (
    UnicodeInventory,
    detect_bom_bytes,
    inventory_unicode,
)
from humanhand.infra.importers.base import ContainerImporter, assemble_rich_payloads

_ANSI_CODEC = "cp1252"

_BLOCKED_BOMS = frozenset({"utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"})

# Destination groups whose contents are formatting, metadata, or
# instructions, never body text.
_SKIP_DESTINATIONS = frozenset(
    {
        "fonttbl",
        "colortbl",
        "stylesheet",
        "info",
        "generator",
        "object",
        "field",
        "fldinst",
    }
)

# Control words that end the current paragraph.
_BREAK_WORDS = frozenset({"par", "line", "cell", "row"})

# Control words marking embedded objects (active content).
_OBJECT_WORDS = frozenset({"object", "objdata", "embedd", "result"})

# Control words marking dynamic fields.
_FIELD_WORDS = frozenset({"field", "fldinst"})

_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")

_EMBED_OBJECT_DESCRIPTION = "RTF contains an embedded object"
_FIELD_DESCRIPTION = "RTF contains dynamic fields"
_TABLE_DESCRIPTION = "RTF table structure is not represented in the canonical AST"


def _unicode_char(parameter: int) -> str:
    """Map an RTF ``\\uN`` parameter to its Unicode character.

    Negative parameters are signed 16-bit values: add 65536 per the RTF
    rule. Values above U+10FFFF cannot exist as characters and become U+FFFD.
    """
    codepoint = parameter if parameter >= 0 else parameter + 0x10000
    if codepoint > 0x10FFFF:
        return "�"
    return chr(codepoint)


def _read_letters(text: str, start: int) -> tuple[str, int]:
    """Return the lowercase-letter run starting at ``start`` and its end."""
    index = start
    while index < len(text) and "a" <= text[index] <= "z":
        index += 1
    return text[start:index], index


def _peek_group_word(text: str, open_index: int) -> tuple[str | None, bool]:
    """Look at the token naming a group opened at ``open_index``.

    Returns ``(word, ignorable)`` where ``word`` is the control word naming
    the group (None when the group is not named by a control word) and
    ``ignorable`` is True for ``{\\*...}`` groups. The read is
    non-consuming: the caller re-parses the tokens normally when the group
    is not skipped.
    """
    index = open_index + 1
    if text.startswith("\\*", index):
        index += 2
        if index < len(text) and text[index] == "\\":
            word, _ = _read_letters(text, index + 1)
            return (word if word else None), True
        return None, True
    if index < len(text) and text[index] == "\\":
        word, _ = _read_letters(text, index + 1)
        return (word if word else None), False
    return None, False


@dataclass(frozen=True)
class _Paragraph:
    """One extracted paragraph: text plus its span in the surface text."""

    text: str
    start: int
    end: int
    line_start: int
    line_end: int


@dataclass(frozen=True)
class _ParseResult:
    """Deterministic result of one RTF scan."""

    surface_text: str
    paragraphs: tuple[_Paragraph, ...]
    findings: tuple[ImportFinding, ...]
    unsupported: tuple[str, ...]


class _RtfScanner:
    """Deterministic single-pass RTF tokenizer over decoded text."""

    def __init__(self, text: str) -> None:
        self._text = text
        self._surface: list[str] = []
        self._para_start = 0
        self._para_line = 1
        self._newlines = 0
        self._skip_fallback = False
        self._paragraphs: list[_Paragraph] = []
        self._findings: list[ImportFinding] = []
        self._seen: set[str] = set()
        self._unsupported: list[str] = []

    def run(self) -> _ParseResult:
        """Scan the whole text and return the extracted plain-text result."""
        text = self._text
        index = 0
        skip_depth = 0
        while index < len(text):
            char = text[index]
            if char in "\r\n":
                # Literal CR/LF are whitespace, not text; they also end any
                # pending \uN fallback skip (the fallback is a character).
                self._skip_fallback = False
                index += 1
                continue
            if skip_depth:
                if char == "{":
                    skip_depth += 1
                elif char == "}":
                    skip_depth -= 1
                index += 1
                continue
            if char == "{":
                self._skip_fallback = False
                word, ignorable = _peek_group_word(text, index)
                if ignorable or (word is not None and word in _SKIP_DESTINATIONS):
                    if word is not None:
                        self._note_word(word)
                    skip_depth = 1
                index += 1
                continue
            if char == "}":
                self._skip_fallback = False
                index += 1
                continue
            if char == "\\":
                index = self._control(text, index)
                continue
            index = self._text_run(text, index)
        self._emit()
        return _ParseResult(
            surface_text="".join(self._surface),
            paragraphs=tuple(self._paragraphs),
            findings=tuple(self._findings),
            unsupported=tuple(self._unsupported),
        )

    def _control(self, text: str, index: int) -> int:
        """Process the control construct starting at ``index`` (a backslash)."""
        if index + 1 >= len(text):
            return len(text)
        kind = text[index + 1]
        if kind == "{":
            self._skip_fallback = False
            self._append_text("{")
            return index + 2
        if kind == "}":
            self._skip_fallback = False
            self._append_text("}")
            return index + 2
        if kind == "\\":
            self._skip_fallback = False
            self._append_text("\\")
            return index + 2
        if kind == "'":
            # \'hh — one cp1252 byte; skipped when it is the \uN fallback.
            hex_part = text[index + 2 : index + 4]
            if len(hex_part) == 2 and hex_part[0] in _HEX_DIGITS and hex_part[1] in _HEX_DIGITS:
                byte_value = int(hex_part, 16)
                if not self._skip_fallback:
                    self._append_text(bytes((byte_value,)).decode(_ANSI_CODEC, errors="replace"))
                self._skip_fallback = False
                return index + 4
            self._skip_fallback = False
            return index + 2
        if not ("a" <= kind <= "z"):
            # A control symbol: backslash plus one non-alphabetic character.
            self._skip_fallback = False
            return index + 2
        word, word_end = _read_letters(text, index + 1)
        cursor = word_end
        negative = False
        if cursor < len(text) and text[cursor] == "-":
            negative = True
            cursor += 1
        digits_start = cursor
        while cursor < len(text) and text[cursor].isdigit():
            cursor += 1
        parameter: int | None = None
        if cursor > digits_start:
            parameter = int(text[digits_start:cursor])
            if negative:
                parameter = -parameter
        # Delimiter: a space is consumed and discarded; any other character
        # is consumed now and reprocessed as a regular character by the next
        # loop iteration (the returned index points at it).
        if cursor < len(text) and text[cursor] == " ":
            cursor += 1
        self._skip_fallback = False
        if word == "u":
            if parameter is not None:
                self._append_text(_unicode_char(parameter))
                self._skip_fallback = True
            return cursor
        if word in _BREAK_WORDS:
            self._break_paragraph()
            return cursor
        if word in _OBJECT_WORDS or word in _FIELD_WORDS or word == "trowd":
            self._note_word(word)
        return cursor

    def _text_run(self, text: str, index: int) -> int:
        """Consume a literal text run and append it to the surface text."""
        cursor = index
        while cursor < len(text) and text[cursor] not in "\\{}" and text[cursor] not in "\r\n":
            cursor += 1
        run = text[index:cursor]
        if self._skip_fallback:
            # The real RTF \u rule: the single ANSI fallback character after
            # \uN is skipped because this reader supports Unicode.
            self._skip_fallback = False
            if run:
                run = run[1:]
        self._append_text(run)
        return cursor

    def _append_text(self, text: str) -> None:
        for char in text:
            self._surface.append(char)

    def _emit(self) -> None:
        """Emit the current paragraph (empty buffer emits nothing)."""
        text = "".join(self._surface[self._para_start :])
        if text:
            self._paragraphs.append(
                _Paragraph(
                    text=text,
                    start=self._para_start,
                    end=self._para_start + len(text),
                    line_start=self._para_line,
                    line_end=self._para_line,
                )
            )

    def _break_paragraph(self) -> None:
        """Emit the current paragraph and move to the next one."""
        self._emit()
        self._surface.append("\n")
        self._para_start = len(self._surface)
        self._newlines += 1
        self._para_line = self._newlines + 1

    def _note_word(self, word: str) -> None:
        """Record findings and coverage for structural control words."""
        if word in _OBJECT_WORDS:
            self._add_finding(
                "rtf_object",
                FindingCode.ACTIVE_CONTENT_EMBED_OBJECT,
                FindingSeverity.ERROR,
                FindingCategory.ACTIVE_CONTENT,
                _EMBED_OBJECT_DESCRIPTION,
                "rtf_object",
            )
            self._add_unsupported("object")
        elif word in _FIELD_WORDS:
            self._add_finding(
                "rtf_field",
                FindingCode.UNSUPPORTED_FEATURE,
                FindingSeverity.WARNING,
                FindingCategory.UNSUPPORTED_FEATURE,
                _FIELD_DESCRIPTION,
                "rtf_field",
            )
            self._add_unsupported("field")
        elif word == "trowd":
            self._add_finding(
                "rtf_table",
                FindingCode.UNSUPPORTED_FEATURE,
                FindingSeverity.WARNING,
                FindingCategory.UNSUPPORTED_FEATURE,
                _TABLE_DESCRIPTION,
                "rtf_table",
            )
            self._add_unsupported("table")

    def _add_finding(
        self,
        key: str,
        code: str,
        severity: FindingSeverity,
        category: FindingCategory,
        description: str,
        evidence: str,
    ) -> None:
        if key in self._seen:
            return
        self._seen.add(key)
        self._findings.append(
            ImportFinding(
                code=code,
                severity=severity,
                category=category,
                description=description,
                evidence=evidence,
            )
        )

    def _add_unsupported(self, structure: str) -> None:
        if structure not in self._unsupported:
            self._unsupported.append(structure)


class RtfImporter(ContainerImporter):
    """Clean-room importer for RTF containers (EP-013)."""

    parser_name: str = "rtf"
    parser_version: str = "1"
    supported_kinds: frozenset[FileKind] = frozenset({FileKind.RTF})

    def parse_payloads(self, raw: bytes, policy: ImportPolicy) -> dict[str, object]:
        """Parse RTF bytes into the shared worker payload envelope."""
        findings: list[ImportFinding] = []
        findings.extend(
            check_limits(
                policy,
                size_bytes=len(raw),
                expanded_bytes=len(raw),
                node_count=0,
                depth=0,
            )
        )
        blocked = any(finding.severity is FindingSeverity.ERROR for finding in findings)

        bom_name = ""
        decode_bytes = raw
        if not blocked:
            bom_name = detect_bom_bytes(raw)
            if bom_name in _BLOCKED_BOMS:
                findings.append(
                    ImportFinding(
                        code=FindingCode.ENCODING_UTF16_UNSUPPORTED,
                        severity=FindingSeverity.ERROR,
                        category=FindingCategory.ENCODING,
                        description=(
                            f"{bom_name} encoded input is not supported by the current import "
                            f"policy (required encoding: {policy.required_encoding})"
                        ),
                        evidence=f"bom={bom_name}",
                    )
                )
                blocked = True
            elif bom_name == "utf-8":
                # The BOM is container framing, not content.
                decode_bytes = raw[3:]

        surface_text = ""
        inventory: UnicodeInventory = inventory_unicode("", bom_name=bom_name)
        root: NodeBuilder | None = None
        coverage = CoverageSummary(
            adapter=self.parser_name,
            supported_structures=(),
            unsupported_structures=(),
            status="partial",
        )
        if not blocked:
            source_text = decode_bytes.decode(_ANSI_CODEC, errors="replace")
            result = _RtfScanner(source_text).run()
            # The document surface is the extracted plain text, not the raw
            # RTF source; node spans index exactly this view.
            surface_text = result.surface_text
            inventory = inventory_unicode(surface_text, bom_name=bom_name)
            findings.extend(result.findings)
            coverage = CoverageSummary(
                adapter=self.parser_name,
                supported_structures=("paragraph",),
                unsupported_structures=result.unsupported,
                status="partial" if result.unsupported else "complete",
            )
            root = NodeBuilder(
                node_type=NodeType.DOCUMENT,
                source_location=SourceLocation(
                    0, len(surface_text), 1, surface_text.count("\n") + 1
                ),
            )
            for paragraph in result.paragraphs:
                root.add_child(
                    NodeBuilder(
                        node_type=NodeType.PARAGRAPH,
                        text=paragraph.text,
                        source_location=SourceLocation(
                            paragraph.start,
                            paragraph.end,
                            paragraph.line_start,
                            paragraph.line_end,
                        ),
                    )
                )

        return assemble_rich_payloads(
            raw=raw,
            policy=policy,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            surface_text=surface_text,
            root=root,
            findings=findings,
            coverage=coverage,
            metadata=MetadataInventory(),
            active=(),
            unicode_inventory=inventory,
        )
