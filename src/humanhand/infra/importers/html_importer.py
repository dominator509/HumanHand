"""Clean-room HTML importer producing canonical document structures.

Parses HTML with the stdlib ``html.parser.HTMLParser`` only — no third-party
library, no network, no filesystem access. The adapter transforms decoded
text into canonical nodes, metadata items, and fail-closed findings; the
shared container pipeline owns byte decoding, limit checks, and payload
assembly.

Design notes (deterministic by construction):

- ``handle_*`` callbacks fire before the parser advances its position, so
  ``getpos()`` inside any callback reports the raw start offset of the
  current token. Span offsets index the raw decoded HTML text (the visible
  text is a projection of it), while ``surface_text`` is the concatenated
  visible text: block texts joined with ``"\\n"``, inline spaces preserved
  exactly, and dropped-element content excluded.
- With ``convert_charrefs=True`` the parser hands ``handle_data`` the
  *unescaped* chunk, whose length differs from the raw markup span, so node
  text is accumulated verbatim and spans come from token offsets only.
- Whitespace-only data runs are dropped (they never become text); runs
  inside ``<pre>`` are preserved so code text stays exact.
- ``script``/``style``/``iframe``/``object``/``embed`` content is consumed
  as raw text and never becomes content. The elements themselves produce
  findings; ``style`` is a presentation warning, the rest are active-content
  errors.
- Attribute scanning runs unconditionally on every start tag, so event
  handlers and remote/javascript/vbscript/data URLs are flagged even inside
  dropped elements or unusual markup.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass
from html.parser import HTMLParser

from humanhand.domain.active_content import scheme_host_only
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
from humanhand.domain.metadata_inventory import MetadataInventory, MetadataItem
from humanhand.domain.unicode_policy import inventory_unicode
from humanhand.infra.importers.base import (
    ContainerImporter,
    DecodeResult,
    assemble_rich_payloads,
    decode_text,
)

# Every structure the parser can recognize, in a stable order.
_SUPPORTED_STRUCTURES = (
    "heading",
    "paragraph",
    "list",
    "list_item",
    "quotation",
    "code_block",
    "table",
    "hyperlink",
    "image_placeholder",
    "html_meta",
    "html_comment",
)

# Elements whose content is raw text and never becomes canonical content.
_DROP_TAGS = frozenset({"script", "style", "iframe", "object", "embed"})

# Block-level tags mapped to their canonical node types.
_BLOCK_TAG_TYPES: dict[str, NodeType] = {
    "h1": NodeType.HEADING,
    "h2": NodeType.HEADING,
    "h3": NodeType.HEADING,
    "h4": NodeType.HEADING,
    "h5": NodeType.HEADING,
    "h6": NodeType.HEADING,
    "p": NodeType.PARAGRAPH,
    "ul": NodeType.LIST,
    "ol": NodeType.LIST,
    "li": NodeType.LIST_ITEM,
    "blockquote": NodeType.QUOTATION,
    "pre": NodeType.CODE_BLOCK,
    "table": NodeType.TABLE,
    "tr": NodeType.TABLE_ROW,
    "td": NodeType.TABLE_CELL,
    "th": NodeType.TABLE_CELL,
}

# Node types that receive plain text directly (others promote to PARAGRAPH).
_TEXT_NODE_TYPES = frozenset(
    {
        NodeType.HEADING,
        NodeType.PARAGRAPH,
        NodeType.LIST_ITEM,
        NodeType.QUOTATION,
        NodeType.CODE_BLOCK,
        NodeType.TABLE_CELL,
    }
)

_REMOTE_SCHEME_PREFIXES = ("http://", "https://", "//")

# Mirrors domain/active_content.py: captures the authority fragment so
# evidence can be reduced to scheme and host only.
_SCHEME_HOST_RE = re.compile(r"[a-z][a-z0-9+.-]*://[^/\s\"'<>()?#]{0,64}", re.IGNORECASE)

_EVENT_HANDLER_NAME_RE = re.compile(r"on[a-z]+")


def _line_starts_of(text: str) -> list[int]:
    """Return 0-based offsets where each line begins (``\\n``-only split).

    The parser's position tracker counts only ``\\n`` as a line break, so
    the offset mapping must use the same convention to stay exact.
    """
    starts = [0]
    starts.extend(index + 1 for index, char in enumerate(text) if char == "\n")
    return starts


def _line_of(line_starts: list[int], offset: int) -> int:
    """Return the 1-based line number containing the character at ``offset``."""
    return bisect_right(line_starts, offset)


def _attr_value(attrs: list[tuple[str, str | None]], name: str) -> str | None:
    """Return the value of the named attribute, or None when absent."""
    for attr_name, value in attrs:
        if attr_name == name:
            return value
    return None


@dataclass
class _Sink:
    """One open block: its builder node, accumulated text parts, and span."""

    node: NodeBuilder
    parts: list[str]
    start: int
    promoted: bool = False


class _HtmlTreeBuilder(HTMLParser):
    """Deterministic HTMLParser subclass building canonical node structures."""

    def __init__(self, text: str) -> None:
        super().__init__(convert_charrefs=True)
        self._text = text
        self._line_starts = _line_starts_of(text)
        root = NodeBuilder(
            node_type=NodeType.DOCUMENT,
            source_location=SourceLocation(0, len(text), 1, text.count("\n") + 1),
        )
        self._root = root
        self._doc_sink = _Sink(node=root, parts=[], start=0)
        self._sinks: list[_Sink] = [self._doc_sink]
        self._links: list[NodeBuilder] = []
        self._link_parts: list[list[str]] = []
        self._link_starts: list[int] = []
        self._in_title = False
        self._title_parts: list[str] = []
        self._dropped: list[str] = []
        self._style_seen = False
        self._findings: list[ImportFinding] = []
        self._metadata: list[MetadataItem] = []
        self._comment_count = 0

    @property
    def root(self) -> NodeBuilder:
        return self._root

    @property
    def findings(self) -> tuple[ImportFinding, ...]:
        return tuple(self._findings)

    @property
    def metadata(self) -> MetadataInventory:
        return MetadataInventory(items=tuple(self._metadata))

    @property
    def coverage(self) -> CoverageSummary:
        has_active = any(
            finding.severity is FindingSeverity.ERROR
            and finding.category
            in {FindingCategory.ACTIVE_CONTENT, FindingCategory.EXTERNAL_RELATIONSHIP}
            for finding in self._findings
        )
        unsupported = ("style_element",) if self._style_seen else ()
        status = "partial" if (self._style_seen or has_active) else "complete"
        return CoverageSummary(
            adapter="html",
            supported_structures=_SUPPORTED_STRUCTURES,
            unsupported_structures=unsupported,
            status=status,
        )

    def _current_offset(self) -> int:
        """Raw character offset of the token the parser is currently on."""
        line_no, column = self.getpos()
        if line_no < 1:
            line_no = 1
        if line_no > len(self._line_starts):
            line_no = len(self._line_starts)
        return min(self._line_starts[line_no - 1] + column, len(self._text))

    def _markup_end(self, start: int) -> int:
        """Offset just past the ``>`` ending the markup token at ``start``.

        Quote-aware: ``>`` inside a quoted attribute value does not end the
        token. Returns ``len(text)`` when no closing ``>`` exists.
        """
        text = self._text
        index = start
        quote: str | None = None
        while index < len(text):
            char = text[index]
            if quote is not None:
                if char == quote:
                    quote = None
            elif char in ('"', "'"):
                quote = char
            elif char == ">":
                return index + 1
            index += 1
        return len(text)

    def _location(self, start: int, end: int) -> SourceLocation:
        line_end = self._line_of(start) if end <= start else self._line_of(end - 1)
        return SourceLocation(
            start_offset=start,
            end_offset=end,
            line_start=self._line_of(start),
            line_end=line_end,
        )

    def _line_of(self, offset: int) -> int:
        return _line_of(self._line_starts, offset)

    def _scan_attributes(self, tag: str, attrs: list[tuple[str, str | None]], start: int) -> None:
        """Flag event handlers and javascript/vbscript/data/remote URLs."""
        del tag  # the element name does not change the attribute rules
        for name, value in attrs:
            if value is None:
                continue
            if _EVENT_HANDLER_NAME_RE.fullmatch(name) is not None:
                self._findings.append(
                    ImportFinding(
                        code=FindingCode.ACTIVE_CONTENT_EVENT_HANDLER,
                        severity=FindingSeverity.ERROR,
                        category=FindingCategory.ACTIVE_CONTENT,
                        description=f"HTML event handler attribute at offset {start}",
                        evidence="html_event_handler",
                    )
                )
                continue
            if name not in {"src", "href"}:
                continue
            lowered = value.strip().lower()
            if lowered.startswith("javascript:"):
                self._findings.append(
                    ImportFinding(
                        code=FindingCode.ACTIVE_CONTENT_JAVASCRIPT_LINK,
                        severity=FindingSeverity.ERROR,
                        category=FindingCategory.ACTIVE_CONTENT,
                        description=f"javascript: link at offset {start}",
                        evidence="javascript_link",
                    )
                )
            elif lowered.startswith("vbscript:"):
                self._findings.append(
                    ImportFinding(
                        code=FindingCode.ACTIVE_CONTENT_VBSCRIPT_LINK,
                        severity=FindingSeverity.ERROR,
                        category=FindingCategory.ACTIVE_CONTENT,
                        description=f"vbscript: link at offset {start}",
                        evidence="vbscript_link",
                    )
                )
            elif lowered.startswith("data:"):
                self._findings.append(
                    ImportFinding(
                        code=FindingCode.ACTIVE_CONTENT_DATA_URI,
                        severity=FindingSeverity.ERROR,
                        category=FindingCategory.ACTIVE_CONTENT,
                        description=f"data: URI at offset {start}",
                        evidence="data_uri",
                    )
                )
            elif lowered.startswith(_REMOTE_SCHEME_PREFIXES):
                self._findings.append(
                    ImportFinding(
                        code=FindingCode.EXTERNAL_REMOTE_RESOURCE,
                        severity=FindingSeverity.ERROR,
                        category=FindingCategory.EXTERNAL_RELATIONSHIP,
                        description=f"remote resource reference at offset {start}",
                        evidence=scheme_host_only(value),
                    )
                )

    def _handle_drop(self, tag: str, start: int) -> None:
        """Record the drop element's finding and start ignoring its content."""
        self._close_promoted(start)
        if tag == "script":
            self._findings.append(
                ImportFinding(
                    code=FindingCode.ACTIVE_CONTENT_SCRIPT,
                    severity=FindingSeverity.ERROR,
                    category=FindingCategory.ACTIVE_CONTENT,
                    description=f"HTML script element at offset {start}",
                    evidence="html_script",
                )
            )
        elif tag == "iframe":
            self._findings.append(
                ImportFinding(
                    code=FindingCode.ACTIVE_CONTENT_IFRAME,
                    severity=FindingSeverity.ERROR,
                    category=FindingCategory.ACTIVE_CONTENT,
                    description=f"HTML iframe element at offset {start}",
                    evidence="iframe",
                )
            )
        elif tag in {"object", "embed"}:
            self._findings.append(
                ImportFinding(
                    code=FindingCode.ACTIVE_CONTENT_EMBED_OBJECT,
                    severity=FindingSeverity.ERROR,
                    category=FindingCategory.ACTIVE_CONTENT,
                    description=f"HTML object/embed element at offset {start}",
                    evidence="embed_object",
                )
            )
        elif tag == "style":
            self._style_seen = True
            self._findings.append(
                ImportFinding(
                    code=FindingCode.UNSUPPORTED_FEATURE,
                    severity=FindingSeverity.WARNING,
                    category=FindingCategory.UNSUPPORTED_FEATURE,
                    description="HTML style element is presentation, not content",
                    evidence="style_element",
                )
            )
        self._dropped.append(tag)

    def _ensure_text_sink(self, start: int) -> None:
        """Promote bare text to a PARAGRAPH when no text block is open."""
        top = self._sinks[-1]
        if top.node.node_type in _TEXT_NODE_TYPES:
            return
        node = NodeBuilder(node_type=NodeType.PARAGRAPH)
        top.node.add_child(node)
        self._sinks.append(_Sink(node=node, parts=[], start=start, promoted=True))

    def _in_code_block(self) -> bool:
        return self._sinks[-1].node.node_type is NodeType.CODE_BLOCK

    def _close_promoted(self, end: int) -> None:
        """Close a promoted (tag-less) paragraph when a block boundary arrives."""
        if self._sinks[-1].promoted:
            self._close_sink(self._sinks.pop(), end)

    def _close_sink(self, sink: _Sink, end: int) -> None:
        sink.node.text = "".join(sink.parts)
        sink.node.source_location = self._location(sink.start, end)

    def _pop_block(self, node_type: NodeType, end: int) -> None:
        """Pop the topmost open block of ``node_type`` (and anything above it)."""
        for index in range(len(self._sinks) - 1, 0, -1):
            if self._sinks[index].node.node_type is not node_type:
                continue
            while len(self._sinks) > index:
                self._close_sink(self._sinks.pop(), end)
            return

    def _open_block(self, tag: str, start: int) -> None:
        self._close_promoted(start)
        node_type = _BLOCK_TAG_TYPES[tag]
        node = NodeBuilder(node_type=node_type)
        if node_type is NodeType.HEADING:
            node.attributes = {"level": tag[1]}
        self._sinks[-1].node.add_child(node)
        self._sinks.append(_Sink(node=node, parts=[], start=start))

    def _handle_meta(self, attrs: list[tuple[str, str | None]]) -> None:
        name = _attr_value(attrs, "name")
        content = _attr_value(attrs, "content")
        if name is not None and content is not None:
            self._metadata.append(MetadataItem(key=name, kind="html_meta", value=content))

    def _handle_image(self, attrs: list[tuple[str, str | None]], start: int) -> None:
        src = _attr_value(attrs, "src")
        attributes: dict[str, str] = {}
        if src is not None:
            attributes = {"url": src}
        node = NodeBuilder(
            node_type=NodeType.IMAGE_PLACEHOLDER,
            attributes=attributes,
            source_location=self._location(start, self._markup_end(start)),
        )
        self._sinks[-1].node.add_child(node)

    def _open_link(self, href: str, start: int) -> None:
        self._links.append(NodeBuilder(node_type=NodeType.HYPERLINK, attributes={"url": href}))
        self._link_parts.append([])
        self._link_starts.append(start)

    def _close_link(self, end: int) -> None:
        link = self._links.pop()
        link.text = "".join(self._link_parts.pop())
        link.source_location = self._location(self._link_starts.pop(), end)
        self._sinks[-1].node.add_child(link)

    def _finish_title(self) -> None:
        self._metadata.append(
            MetadataItem(key="title", kind="html_title", value="".join(self._title_parts))
        )
        self._title_parts = []
        self._in_title = False

    def _finalize_all(self) -> None:
        end = len(self._text)
        while len(self._sinks) > 1:
            self._close_sink(self._sinks.pop(), end)
        if self._in_title:
            self._finish_title()
        while self._links:
            self._close_link(end)

    def surface_text(self) -> str:
        """Concatenate the visible text: block texts in pre-order, ``"\\n"``-joined.

        Inline spaces are preserved exactly (each block's accumulated parts
        are joined verbatim); hyperlink nodes are excluded because their text
        is already part of the containing block's text.
        """
        parts: list[str] = []
        self._collect_surface_text(self._root, parts)
        return "\n".join(parts)

    def _collect_surface_text(self, node: NodeBuilder, parts: list[str]) -> None:
        if node.node_type is not NodeType.HYPERLINK and node.text:
            parts.append(node.text)
        for child in node.children:
            self._collect_surface_text(child, parts)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        start = self._current_offset()
        self._scan_attributes(tag, attrs, start)
        if tag in _DROP_TAGS:
            self._handle_drop(tag, start)
            return
        if self._dropped:
            return
        if tag == "title":
            self._in_title = True
            self._title_parts = []
            return
        if tag == "meta":
            self._handle_meta(attrs)
            return
        if tag == "img":
            self._handle_image(attrs, start)
            return
        if tag == "a":
            href = _attr_value(attrs, "href")
            if href is not None:
                self._open_link(href, start)
            return
        node_type = _BLOCK_TAG_TYPES.get(tag)
        if node_type is not None:
            self._open_block(tag, start)

    def handle_endtag(self, tag: str) -> None:
        start = self._current_offset()
        if self._dropped and tag == self._dropped[-1]:
            self._dropped.pop()
            return
        if tag == "title" and self._in_title:
            self._finish_title()
            return
        if tag == "a" and self._links:
            self._close_link(self._markup_end(start))
            return
        node_type = _BLOCK_TAG_TYPES.get(tag)
        if node_type is not None:
            self._pop_block(node_type, self._markup_end(start))

    def handle_data(self, data: str) -> None:
        if self._dropped:
            return
        if self._in_title:
            self._title_parts.append(data)
            return
        if data.strip() == "" and not self._in_code_block():
            return
        start = self._current_offset()
        self._ensure_text_sink(start)
        self._sinks[-1].parts.append(data)
        for parts in self._link_parts:
            parts.append(data)

    def handle_comment(self, data: str) -> None:
        self._comment_count += 1
        self._metadata.append(
            MetadataItem(
                key=f"html_comment_{self._comment_count}",
                kind="html_comment",
                value=data,
            )
        )

    def close(self) -> None:
        super().close()
        self._finalize_all()


class HtmlImporter(ContainerImporter):
    """Clean-room HTML container importer (EP-013)."""

    parser_name: str = "html"
    parser_version: str = "1"
    supported_kinds: frozenset[FileKind] = frozenset({FileKind.HTML})

    def parse_payloads(self, raw: bytes, policy: ImportPolicy) -> dict[str, object]:
        """Parse raw HTML bytes into the shared worker payload envelope.

        Mirrors the base text pipeline: limit checks, strict UTF-8 decode,
        then deterministic HTML structure parsing. Active-content findings
        come from this parser's structural scan (``active=()``); content of
        dropped elements never reaches the document.
        """
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

        decoded = DecodeResult(
            surface_text="", text="", inventory=inventory_unicode(""), findings=()
        )
        limit_blocked = any(finding.severity is FindingSeverity.ERROR for finding in findings)
        if not limit_blocked:
            decoded = decode_text(raw, policy)
            findings.extend(decoded.findings)

        metadata = MetadataInventory()
        coverage = CoverageSummary(
            adapter=self.parser_name,
            supported_structures=(),
            unsupported_structures=(),
            status="partial",
        )

        root: NodeBuilder | None = None
        surface_text = decoded.surface_text
        parse_blocked = any(
            finding.severity is FindingSeverity.ERROR
            and finding.category in {FindingCategory.ENCODING, FindingCategory.RESOURCE_LIMIT}
            for finding in findings
        )
        if not parse_blocked and decoded.text:
            builder = _HtmlTreeBuilder(decoded.text)
            try:
                builder.feed(decoded.text)
                builder.close()
            except Exception:
                # The parser's documented failure mode is
                # ``html.parser.HTMLParseError`` (a subclass of Exception,
                # deprecated and absent from typeshed). Malformed markup
                # fails closed with a deterministic finding instead of
                # crashing the worker; partial findings collected before
                # the failure are preserved so evidence is never silently
                # dropped.
                findings.extend(builder.findings)
                findings.append(
                    ImportFinding(
                        code=FindingCode.UNSUPPORTED_FEATURE,
                        severity=FindingSeverity.ERROR,
                        category=FindingCategory.STRUCTURE,
                        description="HTML parse error",
                        evidence="html_parse_error",
                    )
                )
            else:
                root = builder.root
                findings.extend(builder.findings)
                coverage = builder.coverage
                metadata = builder.metadata
                surface_text = builder.surface_text()

        # Unicode findings must index the extracted surface text (the same
        # coordinate space as node spans), not the raw markup; fall back to
        # the decoded inventory only when no extraction happened.
        inventory = (
            inventory_unicode(surface_text, bom_name=decoded.inventory.bom_name)
            if surface_text
            else decoded.inventory
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
            metadata=metadata,
            active=(),
            unicode_inventory=inventory,
        )
