"""Clean-room Markdown parser producing canonical document structures.

Implements the supported Markdown subset for EP-012 with deterministic,
line-based rules and stdlib ``re`` only — no third-party parsing library.
The parser never touches the filesystem or the network; the base pipeline
owns byte decoding, limit checks, active-content scanning, and document
construction.
"""

from __future__ import annotations

import re
from bisect import bisect_right
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
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.metadata_inventory import MetadataInventory, MetadataItem
from humanhand.infra.importers.base import BaseImporter

# Every structure the parser can recognize, in a stable order.
_SUPPORTED_STRUCTURES = (
    "front_matter",
    "heading",
    "setext_heading",
    "paragraph",
    "code_block",
    "indented_code_block",
    "list",
    "quotation",
    "table",
    "section_break",
    "hyperlink",
    "image_placeholder",
    "html_comment",
    "block_id",
)

_FENCE_OPEN_RE = re.compile(r"^(```|~~~)(.*)$")
_FENCE_CLOSE_RE = re.compile(r"^(```|~~~)\s*$")
_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_SETEXT_LEVEL1_RE = re.compile(r"^=+$")
_SETEXT_LEVEL2_RE = re.compile(r"^-+$")
_HORIZONTAL_RULE_RE = re.compile(r"^(\s*)(\*{3,}|-{3,}|_{3,})\s*$")
_UNORDERED_ITEM_RE = re.compile(r"^[-*+]\s+(.*)$")
_ORDERED_ITEM_RE = re.compile(r"^\d+[.)]\s+(.*)$")
_NESTED_UNORDERED_ITEM_RE = re.compile(r"^  [-*+]\s+(.*)$")
_NESTED_ORDERED_ITEM_RE = re.compile(r"^  \d+[.)]\s+(.*)$")
_INDENTED_CODE_RE = re.compile(r"^ {4}(.*)$")
_RAW_HTML_RE = re.compile(r"^<[a-zA-Z]")
_HTML_COMMENT_RE = re.compile(r"^\s*<!--(.*)-->\s*$")
_BLOCK_ID_RE = re.compile(r"(?<!\S)\^([a-zA-Z0-9-]+)\s*$")
_INLINE_LINK_RE = re.compile(r"!?\[([^\]]*)\]\(([^)]+)\)")
_FRONT_MATTER_ITEM_RE = re.compile(r"^([^:]+):\s*(.*)$")
_DELIMITER_ROW_RE = re.compile(r"^\|?[\s:|-]+\|?$")


def _is_delimiter_row(content: str) -> bool:
    """True when a ``|`` row is a GFM delimiter row.

    GFM requires every cell of a delimiter row to contain at least one
    hyphen (colons optional). Rows like ``| : |`` or ``| |`` therefore
    remain data rows instead of being silently consumed as structure.
    """
    if _DELIMITER_ROW_RE.match(content) is None:
        return False
    inner = content[1:].rstrip()
    if inner.endswith("|"):
        inner = inner[:-1]
    cells = [cell.strip() for cell in inner.split("|")]
    if not cells:
        return False
    return all(re.fullmatch(r":?-+:?", cell) is not None for cell in cells)


@dataclass(frozen=True)
class _Line:
    """One content line: exact text plus its span and 1-based number."""

    content: str
    start: int
    end: int
    number: int


def _split_lines(text: str) -> tuple[list[_Line], list[int]]:
    """Split text into content lines with spans; return lines and line starts.

    A trailing newline does not produce a phantom empty line. ``end`` is the
    offset just past the last content character of the line.
    """
    line_starts = [0]
    line_starts.extend(index + 1 for index, char in enumerate(text) if char == "\n")
    if line_starts[-1] == len(text):
        line_starts.pop()
    last_end = len(text) - 1 if text.endswith("\n") else len(text)
    lines: list[_Line] = []
    for position, start in enumerate(line_starts):
        end = line_starts[position + 1] - 1 if position + 1 < len(line_starts) else last_end
        lines.append(_Line(content=text[start:end], start=start, end=end, number=position + 1))
    return lines, line_starts


def _line_at(line_starts: list[int], offset: int) -> int:
    """Return the 1-based line number containing the character at ``offset``."""
    return bisect_right(line_starts, offset)


def _span_of(lines: list[_Line], first: int, last: int) -> SourceLocation:
    """Build a source span covering lines ``first`` through ``last`` inclusive."""
    return SourceLocation(
        start_offset=lines[first].start,
        end_offset=lines[last].end,
        line_start=lines[first].number,
        line_end=lines[last].number,
    )


def _is_list_marker(content: str) -> bool:
    """True when the line starts a level-0 unordered or ordered list item."""
    return (
        _UNORDERED_ITEM_RE.match(content) is not None or _ORDERED_ITEM_RE.match(content) is not None
    )


def _is_nested_item(content: str) -> bool:
    """True when the line starts a 2-space-indented (nested) list item."""
    return (
        _NESTED_UNORDERED_ITEM_RE.match(content) is not None
        or _NESTED_ORDERED_ITEM_RE.match(content) is not None
    )


def _is_paragraph_line(content: str, index: int, comment_indices: set[int]) -> bool:
    """True when the line belongs to a contiguous paragraph run."""
    if content == "":
        return False
    if index in comment_indices:
        return False
    if _ATX_HEADING_RE.match(content) is not None:
        return False
    if _FENCE_OPEN_RE.match(content) is not None:
        return False
    if content.startswith(">"):
        return False
    if _is_list_marker(content):
        return False
    if content.startswith("|"):
        return False
    if content.startswith("    "):
        return False
    if _HORIZONTAL_RULE_RE.match(content) is not None:
        return False
    if _SETEXT_LEVEL1_RE.match(content) is not None:
        return False
    if _SETEXT_LEVEL2_RE.match(content) is not None:
        return False
    return _RAW_HTML_RE.match(content) is None


def _consume_front_matter(lines: list[_Line], metadata_items: list[MetadataItem]) -> int:
    """Consume a leading ``---``-delimited front matter block.

    Returns the index of the first line after the block, or 0 when the text
    does not start with a closed front matter block. ``key: value`` lines
    inside the block become ``front_matter`` metadata items.
    """
    if not lines or lines[0].content != "---":
        return 0
    close_index: int | None = None
    for index in range(1, len(lines)):
        if lines[index].content == "---":
            close_index = index
            break
    if close_index is None:
        return 0
    for line in lines[1:close_index]:
        match = _FRONT_MATTER_ITEM_RE.match(line.content)
        if match is not None:
            metadata_items.append(
                MetadataItem(
                    key=match.group(1).strip(),
                    kind="front_matter",
                    value=match.group(2).strip(),
                )
            )
    return close_index + 1


def _prescan(lines: list[_Line], start: int, metadata_items: list[MetadataItem]) -> set[int]:
    """Extract comment-only lines and trailing block ids outside fenced code.

    Returns the set of line indices whose whole content is an HTML comment;
    those lines are consumed as metadata and never become body nodes. Block
    ids are recorded as metadata while their lines remain body content.
    Fenced code interiors are skipped so code text is never misread as
    markup metadata.
    """
    comment_lines: set[int] = set()
    comment_number = 0
    in_fence = False
    for index in range(start, len(lines)):
        content = lines[index].content
        if in_fence:
            if _FENCE_CLOSE_RE.match(content) is not None:
                in_fence = False
            continue
        if _FENCE_OPEN_RE.match(content) is not None:
            in_fence = True
            continue
        comment_match = _HTML_COMMENT_RE.match(content)
        if comment_match is not None:
            comment_number += 1
            comment_lines.add(index)
            metadata_items.append(
                MetadataItem(
                    key=f"html_comment_{comment_number}",
                    kind="html_comment",
                    value=comment_match.group(1),
                )
            )
            continue
        block_id_match = _BLOCK_ID_RE.search(content)
        if block_id_match is not None:
            block_id = block_id_match.group(1)
            metadata_items.append(MetadataItem(key=block_id, kind="block_id", value=block_id))
    return comment_lines


def _deprefix_quote(content: str) -> str:
    """Strip the leading ``>`` and at most one following space."""
    if content.startswith(">"):
        content = content[1:]
    if content.startswith(" "):
        content = content[1:]
    return content


def _atx_heading(lines: list[_Line], index: int, atx: re.Match[str]) -> NodeBuilder:
    """Build a HEADING node (with TEXT_RUN child) from an ATX heading line."""
    span = _span_of(lines, index, index)
    heading = NodeBuilder(
        node_type=NodeType.HEADING,
        attributes={"level": str(len(atx.group(1)))},
        source_location=span,
    )
    heading.add_child(
        NodeBuilder(node_type=NodeType.TEXT_RUN, text=atx.group(2), source_location=span)
    )
    return heading


def _fenced_code(lines: list[_Line], index: int, root: NodeBuilder) -> int:
    """Consume a fenced code block and return the index of the next line."""
    open_match = _FENCE_OPEN_RE.match(lines[index].content)
    if open_match is None:
        raise AssertionError("fenced code block must start with an opening fence")
    language = open_match.group(2).strip()
    inner: list[str] = []
    cursor = index + 1
    while cursor < len(lines) and _FENCE_CLOSE_RE.match(lines[cursor].content) is None:
        inner.append(lines[cursor].content)
        cursor += 1
    last = cursor if cursor < len(lines) else len(lines) - 1
    root.add_child(
        NodeBuilder(
            node_type=NodeType.CODE_BLOCK,
            text="\n".join(inner),
            attributes={"language": language},
            source_location=_span_of(lines, index, last),
        )
    )
    return last + 1


def _indented_code(lines: list[_Line], index: int, root: NodeBuilder) -> int:
    """Consume an indented (4-space) code block and return the next index."""
    inner: list[str] = []
    cursor = index
    while cursor < len(lines):
        match = _INDENTED_CODE_RE.match(lines[cursor].content)
        if match is None:
            break
        inner.append(match.group(1))
        cursor += 1
    root.add_child(
        NodeBuilder(
            node_type=NodeType.CODE_BLOCK,
            text="\n".join(inner),
            attributes={"language": ""},
            source_location=_span_of(lines, index, cursor - 1),
        )
    )
    return cursor


def _block_quote(lines: list[_Line], index: int, root: NodeBuilder) -> int:
    """Consume consecutive block quote lines and build a QUOTATION node."""
    inner: list[str] = []
    cursor = index
    while cursor < len(lines) and lines[cursor].content.startswith(">"):
        inner.append(_deprefix_quote(lines[cursor].content))
        cursor += 1
    span = _span_of(lines, index, cursor - 1)
    quotation = NodeBuilder(node_type=NodeType.QUOTATION, source_location=span)
    quotation.add_child(
        NodeBuilder(node_type=NodeType.PARAGRAPH, text="\n".join(inner), source_location=span)
    )
    root.add_child(quotation)
    return cursor


def _item_content(content: str) -> str:
    """Return the list item text after the marker and separating whitespace."""
    for pattern in (
        _UNORDERED_ITEM_RE,
        _ORDERED_ITEM_RE,
        _NESTED_UNORDERED_ITEM_RE,
        _NESTED_ORDERED_ITEM_RE,
    ):
        match = pattern.match(content)
        if match is not None:
            return match.group(1)
    raise AssertionError("list item content must start with a list marker")


def _list_item(lines: list[_Line], index: int) -> NodeBuilder:
    """Build a LIST_ITEM node holding one PARAGRAPH with the item text."""
    span = _span_of(lines, index, index)
    item = NodeBuilder(node_type=NodeType.LIST_ITEM, source_location=span)
    item.add_child(
        NodeBuilder(
            node_type=NodeType.PARAGRAPH,
            text=_item_content(lines[index].content),
            source_location=span,
        )
    )
    return item


def _close_list_item(
    list_node: NodeBuilder,
    item: NodeBuilder | None,
    item_index: int,
    nested_indices: list[int],
    lines: list[_Line],
) -> None:
    """Attach any nested items as a child LIST and append the item."""
    if item is None:
        return
    if nested_indices:
        item.source_location = _span_of(lines, item_index, nested_indices[-1])
        nested_list = NodeBuilder(
            node_type=NodeType.LIST,
            source_location=_span_of(lines, nested_indices[0], nested_indices[-1]),
        )
        for nested_index in nested_indices:
            nested_list.add_child(_list_item(lines, nested_index))
        item.add_child(nested_list)
    list_node.add_child(item)


def _list_group(lines: list[_Line], index: int, root: NodeBuilder) -> int:
    """Consume a contiguous run of list item lines and build a LIST node."""
    level_zero: list[int] = []
    nested: list[int] = []
    cursor = index
    while cursor < len(lines):
        content = lines[cursor].content
        if _is_list_marker(content):
            level_zero.append(cursor)
            cursor += 1
        elif _is_nested_item(content):
            nested.append(cursor)
            cursor += 1
        else:
            break
    list_node = NodeBuilder(
        node_type=NodeType.LIST,
        source_location=_span_of(lines, index, cursor - 1),
    )
    level_zero_set = set(level_zero)
    current_item: NodeBuilder | None = None
    current_item_index = -1
    current_nested: list[int] = []
    for item_index in sorted(level_zero + nested):
        if item_index in level_zero_set:
            _close_list_item(list_node, current_item, current_item_index, current_nested, lines)
            current_item = _list_item(lines, item_index)
            current_item_index = item_index
            current_nested = []
        else:
            current_nested.append(item_index)
    _close_list_item(list_node, current_item, current_item_index, current_nested, lines)
    root.add_child(list_node)
    return cursor


def _table_row(lines: list[_Line], index: int) -> NodeBuilder:
    """Build a TABLE_ROW node with trimmed TABLE_CELL children."""
    content = lines[index].content
    span = _span_of(lines, index, index)
    row = NodeBuilder(node_type=NodeType.TABLE_ROW, source_location=span)
    inner = content[1:].rstrip()
    if inner.endswith("|"):
        inner = inner[:-1]
    base = lines[index].start + 1
    position = 0
    for part in inner.split("|"):
        start = base + position
        end = start + len(part)
        row.add_child(
            NodeBuilder(
                node_type=NodeType.TABLE_CELL,
                text=part.strip(),
                source_location=SourceLocation(
                    start, end, lines[index].number, lines[index].number
                ),
            )
        )
        position += len(part) + 1
    return row


def _table(lines: list[_Line], index: int, root: NodeBuilder) -> int:
    """Consume consecutive ``|`` rows and build a TABLE node.

    A row matching the GFM delimiter pattern is consumed as structure and
    never becomes a data row.
    """
    row_indices: list[int] = []
    cursor = index
    while cursor < len(lines) and lines[cursor].content.startswith("|"):
        if not _is_delimiter_row(lines[cursor].content):
            row_indices.append(cursor)
        cursor += 1
    table = NodeBuilder(
        node_type=NodeType.TABLE,
        source_location=_span_of(lines, index, cursor - 1),
    )
    for row_index in row_indices:
        table.add_child(_table_row(lines, row_index))
    root.add_child(table)
    return cursor


def _raw_html(
    lines: list[_Line], index: int, root: NodeBuilder, findings: list[ImportFinding]
) -> int:
    """Consume a raw HTML block, flag it, and keep its text as a PARAGRAPH."""
    contents: list[str] = []
    cursor = index
    while cursor < len(lines) and _RAW_HTML_RE.match(lines[cursor].content) is not None:
        contents.append(lines[cursor].content)
        cursor += 1
    findings.append(
        ImportFinding(
            code=FindingCode.UNSUPPORTED_FEATURE,
            severity=FindingSeverity.WARNING,
            category=FindingCategory.UNSUPPORTED_FEATURE,
            description="Raw HTML block is not part of the supported Markdown subset",
            evidence=f"line={lines[index].number}",
        )
    )
    root.add_child(
        NodeBuilder(
            node_type=NodeType.PARAGRAPH,
            text="\n".join(contents),
            source_location=_span_of(lines, index, cursor - 1),
        )
    )
    return cursor


def _attach_inline(
    paragraph: NodeBuilder, text: str, span: SourceLocation, line_starts: list[int]
) -> None:
    """Attach HYPERLINK and IMAGE_PLACEHOLDER children for inline occurrences."""
    for match in _INLINE_LINK_RE.finditer(text):
        start = span.start_offset + match.start()
        end = span.start_offset + match.end()
        location = SourceLocation(
            start,
            end,
            _line_at(line_starts, start),
            _line_at(line_starts, end - 1),
        )
        if match.group(0).startswith("!"):
            paragraph.add_child(
                NodeBuilder(
                    node_type=NodeType.IMAGE_PLACEHOLDER,
                    attributes={"url": match.group(2)},
                    source_location=location,
                )
            )
        else:
            paragraph.add_child(
                NodeBuilder(
                    node_type=NodeType.HYPERLINK,
                    text=match.group(1),
                    attributes={"url": match.group(2)},
                    source_location=location,
                )
            )


def _paragraph(
    lines: list[_Line],
    line_starts: list[int],
    index: int,
    root: NodeBuilder,
    comment_indices: set[int],
) -> int:
    """Consume a paragraph run; convert it to a setext heading when underlined."""
    contents: list[str] = []
    cursor = index
    while cursor < len(lines) and _is_paragraph_line(
        lines[cursor].content, cursor, comment_indices
    ):
        contents.append(lines[cursor].content)
        cursor += 1
    text = "\n".join(contents)
    if cursor < len(lines) and _SETEXT_LEVEL1_RE.match(lines[cursor].content) is not None:
        span = _span_of(lines, index, cursor)
        heading = NodeBuilder(
            node_type=NodeType.HEADING, attributes={"level": "1"}, source_location=span
        )
        heading.add_child(NodeBuilder(node_type=NodeType.TEXT_RUN, text=text, source_location=span))
        root.add_child(heading)
        return cursor + 1
    if cursor < len(lines) and _SETEXT_LEVEL2_RE.match(lines[cursor].content) is not None:
        span = _span_of(lines, index, cursor)
        heading = NodeBuilder(
            node_type=NodeType.HEADING, attributes={"level": "2"}, source_location=span
        )
        heading.add_child(NodeBuilder(node_type=NodeType.TEXT_RUN, text=text, source_location=span))
        root.add_child(heading)
        return cursor + 1
    span = _span_of(lines, index, cursor - 1)
    paragraph = NodeBuilder(node_type=NodeType.PARAGRAPH, text=text, source_location=span)
    _attach_inline(paragraph, text, span, line_starts)
    root.add_child(paragraph)
    return cursor


class MarkdownImporter(BaseImporter):
    """Deterministic clean-room parser for the supported Markdown subset."""

    parser_name = "markdown"
    parser_version = "1"
    supported_kinds = frozenset({FileKind.MARKDOWN})

    def parse(
        self, text: str, policy: ImportPolicy
    ) -> tuple[NodeBuilder | None, CoverageSummary, tuple[ImportFinding, ...], MetadataInventory]:
        """Parse decoded Markdown text into canonical node and metadata structures.

        ``text`` is already decoded and BOM-stripped by the base pipeline.
        The parser performs no I/O: every span, line number, and finding is
        derived deterministically from the input text alone.
        """
        lines, line_starts = _split_lines(text)
        metadata_items: list[MetadataItem] = []
        findings: list[ImportFinding] = []

        root = NodeBuilder(
            node_type=NodeType.DOCUMENT,
            source_location=SourceLocation(0, len(text), 1, text.count("\n") + 1),
        )

        index = _consume_front_matter(lines, metadata_items)
        comment_indices = _prescan(lines, index, metadata_items)

        while index < len(lines):
            line = lines[index]
            content = line.content
            if index in comment_indices or content == "":
                index += 1
                continue
            atx = _ATX_HEADING_RE.match(content)
            if atx is not None:
                root.add_child(_atx_heading(lines, index, atx))
                index += 1
                continue
            if _FENCE_OPEN_RE.match(content) is not None:
                index = _fenced_code(lines, index, root)
                continue
            if content.startswith(">"):
                index = _block_quote(lines, index, root)
                continue
            if _is_list_marker(content):
                index = _list_group(lines, index, root)
                continue
            if content.startswith("|"):
                index = _table(lines, index, root)
                continue
            if content.startswith("    "):
                index = _indented_code(lines, index, root)
                continue
            if _HORIZONTAL_RULE_RE.match(content) is not None:
                root.add_child(
                    NodeBuilder(
                        node_type=NodeType.SECTION_BREAK,
                        source_location=_span_of(lines, index, index),
                    )
                )
                index += 1
                continue
            if _RAW_HTML_RE.match(content) is not None:
                index = _raw_html(lines, index, root, findings)
                continue
            if (
                _SETEXT_LEVEL1_RE.match(content) is not None
                or _SETEXT_LEVEL2_RE.match(content) is not None
            ):
                # A bare underline line with no preceding paragraph stays text.
                root.add_child(
                    NodeBuilder(
                        node_type=NodeType.PARAGRAPH,
                        text=content,
                        source_location=_span_of(lines, index, index),
                    )
                )
                index += 1
                continue
            index = _paragraph(lines, line_starts, index, root, comment_indices)

        has_raw_html = any(finding.code == FindingCode.UNSUPPORTED_FEATURE for finding in findings)
        coverage = CoverageSummary(
            adapter=self.parser_name,
            supported_structures=_SUPPORTED_STRUCTURES,
            unsupported_structures=("raw_html",) if has_raw_html else (),
            status="partial" if has_raw_html else "complete",
        )
        return (
            root,
            coverage,
            tuple(findings),
            MetadataInventory(items=tuple(metadata_items)),
        )
