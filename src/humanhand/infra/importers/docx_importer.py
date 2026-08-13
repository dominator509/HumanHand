"""Fail-closed DOCX inspection adapter for the clean-room ingress pipeline.

The adapter opens the DOCX package as a bounded ZIP container, inventories
its parts, extracts paragraph and table text mechanically, and emits
fail-closed findings for macros, tracked changes, comments, and external
relationships. Nothing here opens files, touches the network, or executes
content.

Honest scope of this adapter:

- Paragraph text is extracted from ``<w:t>`` run contents, joined per
  ``<w:p>`` paragraph. Heading styles are NOT detected: heading paragraphs
  are imported as plain paragraphs.
- Tables are detected (``w:tbl`` -> TABLE, ``w:tr`` -> TABLE_ROW,
  ``w:tc`` -> TABLE_CELL) with each cell's run text concatenated. Table
  nodes carry a whole-document-body source span: the paragraph/table
  interleaving order inside ``document.xml`` is not reconstructed.
- ``inspect()`` is inherited from ``ContainerImporter``; with DOCX
  registered in ``file_type`` the identity gate routes DOCX normally and
  all identity checks (magic mismatch, binary content) fail closed.
"""

from __future__ import annotations

import re

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
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.metadata_inventory import MetadataInventory
from humanhand.infra.importers.base import (
    ContainerImporter,
    assemble_rich_payloads,
)
from humanhand.infra.importers.container_utils import evidence_name, open_zip_bounded
from humanhand.infra.importers.docx_parts import (
    COMMENTS_PART,
    DocxTableCell,
    document_body_text,
    document_tables,
    embedded_object_names,
    external_relationships,
    has_macros,
    has_tracked_changes,
    inventory_parts,
    macro_part_name,
)

# Mirrors active_content._SCHEME_HOST_RE: evidence carries at most the
# URL scheme and host, never credentials or document text.
_SCHEME_HOST_RE = re.compile(r"[a-z][a-z0-9+.-]*://[^/\s\"'<>()?#]{0,64}", re.IGNORECASE)


class DocxImporter(ContainerImporter):
    """Inspect DOCX packages into the shared payload envelope."""

    parser_name = "docx"
    parser_version = "1"
    supported_kinds = frozenset({FileKind.DOCX})

    def parse_payloads(self, raw: bytes, policy: ImportPolicy) -> dict[str, object]:
        """Parse DOCX bytes into the shared worker payload envelope.

        The container is opened through the bounded ZIP helper; every part
        read and XML parse inside it is bounded by the policy. The raw
        bytes are never written and never leave the caller's memory.
        """
        findings: list[ImportFinding] = []
        archive, open_findings = open_zip_bounded(raw, policy)
        if archive is None:
            findings.extend(open_findings)
            coverage = CoverageSummary(
                adapter=self.parser_name,
                supported_structures=(),
                unsupported_structures=("container",),
                status="partial",
            )
            return assemble_rich_payloads(
                raw=raw,
                policy=policy,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                surface_text="",
                root=None,
                findings=findings,
                coverage=coverage,
                metadata=MetadataInventory(),
                active=(),
            )
        try:
            body_text, body_findings = document_body_text(archive, policy)
            findings.extend(body_findings)

            metadata_items, part_findings = inventory_parts(archive, policy)
            findings.extend(part_findings)

            tables, table_findings = document_tables(archive, policy)
            findings.extend(table_findings)

            if has_macros(archive):
                part = macro_part_name(archive)
                findings.append(
                    ImportFinding(
                        code=FindingCode.ACTIVE_CONTENT_MACRO,
                        severity=FindingSeverity.ERROR,
                        category=FindingCategory.ACTIVE_CONTENT,
                        description="Document contains embedded macros",
                        evidence=f"part={evidence_name(part)}" if part else "part=unknown",
                    )
                )

            for embedded_name in embedded_object_names(archive.namelist()):
                findings.append(
                    ImportFinding(
                        code=FindingCode.ACTIVE_CONTENT_EMBED_OBJECT,
                        severity=FindingSeverity.ERROR,
                        category=FindingCategory.ACTIVE_CONTENT,
                        description="Document contains an embedded OLE object",
                        evidence=f"part={evidence_name(embedded_name)}",
                    )
                )

            tracked, tracked_findings = has_tracked_changes(archive, policy)
            findings.extend(tracked_findings)
            if tracked:
                findings.append(
                    ImportFinding(
                        code=FindingCode.REVISION_TRACKED_CHANGES,
                        severity=FindingSeverity.ERROR,
                        category=FindingCategory.REVISION,
                        description="Document contains tracked changes",
                        evidence="tracked_changes",
                    )
                )

            if COMMENTS_PART in archive.namelist():
                findings.append(
                    ImportFinding(
                        code=FindingCode.REVISION_COMMENTS,
                        severity=FindingSeverity.WARNING,
                        category=FindingCategory.REVISION,
                        description="Document contains comments",
                        evidence="comments",
                    )
                )

            external_urls, relationship_findings = external_relationships(archive, policy)
            findings.extend(relationship_findings)
            for url in external_urls:
                findings.append(
                    ImportFinding(
                        code=FindingCode.EXTERNAL_REMOTE_RESOURCE,
                        severity=FindingSeverity.ERROR,
                        category=FindingCategory.EXTERNAL_RELATIONSHIP,
                        description="Document references an external remote resource",
                        evidence=scheme_host_only(url),
                    )
                )

            root = self._build_root(body_text, tables, body_findings)
            if root is None:
                coverage = CoverageSummary(
                    adapter=self.parser_name,
                    supported_structures=(),
                    unsupported_structures=("document.xml",),
                    status="partial",
                )
            else:
                supported = ("paragraph",) + (("table",) if tables else ())
                coverage = CoverageSummary(
                    adapter=self.parser_name,
                    supported_structures=supported,
                    unsupported_structures=(),
                    status="complete",
                )

            metadata = MetadataInventory(items=tuple(metadata_items))
            return assemble_rich_payloads(
                raw=raw,
                policy=policy,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                surface_text=body_text,
                root=root,
                findings=findings,
                coverage=coverage,
                metadata=metadata,
                active=(),
            )
        finally:
            archive.close()

    @staticmethod
    def _build_root(
        body_text: str,
        tables: list[list[list[DocxTableCell]]],
        body_findings: list[ImportFinding],
    ) -> NodeBuilder | None:
        """Build the document tree, or None when the body is unreadable.

        Paragraph nodes carry exact spans into the body surface text;
        table nodes derive their spans from their exact cell spans.
        """
        if any(finding.severity is FindingSeverity.ERROR for finding in body_findings):
            return None
        root = NodeBuilder(node_type=NodeType.DOCUMENT)
        cursor = 0
        for line in body_text.split("\n"):
            if line:
                root.add_child(
                    NodeBuilder(
                        node_type=NodeType.PARAGRAPH,
                        text=line,
                        source_location=SourceLocation(
                            start_offset=cursor, end_offset=cursor + len(line)
                        ),
                    )
                )
            cursor += len(line) + 1
        for table in tables:
            table_locations = [
                cell.source_location
                for row in table
                for cell in row
                if cell.source_location is not None
            ]
            table_location = (
                SourceLocation(
                    min(location.start_offset for location in table_locations),
                    max(location.end_offset for location in table_locations),
                )
                if table_locations
                else None
            )
            table_node = root.add_child(
                NodeBuilder(
                    node_type=NodeType.TABLE,
                    source_location=table_location,
                )
            )
            for row in table:
                row_locations = [
                    cell.source_location for cell in row if cell.source_location is not None
                ]
                row_location = (
                    SourceLocation(
                        min(location.start_offset for location in row_locations),
                        max(location.end_offset for location in row_locations),
                    )
                    if row_locations
                    else None
                )
                row_node = table_node.add_child(
                    NodeBuilder(
                        node_type=NodeType.TABLE_ROW,
                        source_location=row_location,
                    )
                )
                for cell in row:
                    row_node.add_child(
                        NodeBuilder(
                            node_type=NodeType.TABLE_CELL,
                            text=cell.text,
                            source_location=cell.source_location,
                        )
                    )
        return root
