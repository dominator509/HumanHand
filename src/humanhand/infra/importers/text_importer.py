"""Clean-room TXT import adapter.

Plain TXT files are the simplest clean-room container: decoded text maps
one-to-one to paragraph nodes. The base pipeline performs limit checks,
decoding, BOM stripping, Unicode inventory, and active-content scanning;
this adapter only transforms the already-decoded text into a canonical
document tree. TXT has no unsupported structures and carries no embedded
metadata, so the adapter reports empty findings and an empty metadata
inventory, which are the correct honest results for plain text.
"""

from __future__ import annotations

from humanhand.domain.canonical_document import CoverageSummary
from humanhand.domain.document_nodes import NodeBuilder, NodeType, SourceLocation
from humanhand.domain.file_identity import FileKind
from humanhand.domain.import_findings import ImportFinding
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.metadata_inventory import MetadataInventory
from humanhand.infra.importers.base import BaseImporter


class TextImporter(BaseImporter):
    """Importer for plain UTF-8 TXT documents."""

    parser_name: str = "text"
    parser_version: str = "1"
    supported_kinds: frozenset[FileKind] = frozenset({FileKind.TXT})

    def parse(
        self, text: str, policy: ImportPolicy
    ) -> tuple[NodeBuilder | None, CoverageSummary, tuple[ImportFinding, ...], MetadataInventory]:
        """Build a paragraph-per-line document tree from decoded text.

        ``text`` is the decoded, BOM-stripped surface text handed over by
        the base pipeline; it is never re-decoded and line endings are
        preserved as-is, never normalized (the base pipeline inventories
        them). Empty and whitespace-only lines produce no nodes. When the
        text has no non-empty lines, the returned root has zero children;
        the base pipeline already emits the empty-document warning.
        """
        root = NodeBuilder(
            node_type=NodeType.DOCUMENT,
            source_location=SourceLocation(0, len(text), 1, text.count("\n") + 1),
        )
        start = 0
        line_no = 1
        for line in text.split("\n"):
            if line.strip():
                end = start + len(line)
                root.add_child(
                    NodeBuilder(
                        node_type=NodeType.PARAGRAPH,
                        text=line,
                        source_location=SourceLocation(start, end, line_no, line_no),
                    )
                )
            start += len(line) + 1
            line_no += 1
        return (
            root,
            CoverageSummary(
                adapter="text",
                supported_structures=("paragraph",),
                unsupported_structures=(),
                status="complete",
            ),
            (),
            MetadataInventory(),
        )
