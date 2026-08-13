"""Shared clean-room import pipeline for text-based adapters.

Importers in this package never open files, never touch the network, and
never execute active content. They transform decoded text into domain
canonical structures using deterministic rules only.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

from humanhand.domain.active_content import (
    ActiveContentFinding,
    ActiveContentKind,
    active_content_findings,
    scan_active_content,
)
from humanhand.domain.canonical_document import (
    CoverageSummary,
    ImportInspection,
    ResourceMeasurements,
    build_document,
    make_inspection,
    measure_document,
)
from humanhand.domain.document_nodes import NodeBuilder
from humanhand.domain.document_serialization import (
    document_from_json,
    document_to_payload,
    finding_from_payload,
    finding_to_payload,
)
from humanhand.domain.file_identity import (
    FileIdentity,
    FileKind,
    derive_identity,
    identity_findings,
)
from humanhand.domain.import_findings import (
    FindingCategory,
    FindingCode,
    FindingSeverity,
    ImportFinding,
    classify_status,
)
from humanhand.domain.import_policy import ImportPolicy, check_limits
from humanhand.domain.metadata_inventory import MetadataInventory, MetadataItem
from humanhand.domain.types import DomainError
from humanhand.domain.unicode_policy import (
    NormalizationForm,
    UnicodeInventory,
    detect_bom_bytes,
    inventory_unicode,
    strip_bom,
    unicode_findings,
)
from humanhand.infra.importers.file_type import unsupported_format_finding

CONTAINER_KINDS = frozenset(
    {
        FileKind.DOCX,
        FileKind.PDF,
        FileKind.HTML,
        FileKind.RTF,
        FileKind.ODT,
        FileKind.LEGACY_DOC,
    }
)


@dataclass(frozen=True)
class DecodeResult:
    """Decoded text plus its deterministic inventory and findings."""

    surface_text: str
    text: str
    inventory: UnicodeInventory
    findings: tuple[ImportFinding, ...]


def decode_text(raw: bytes, policy: ImportPolicy) -> DecodeResult:
    """Decode raw bytes per policy and inventory their Unicode properties.

    Decode failures become findings and yield empty text; the caller must
    not parse empty text after a blocking finding.
    """
    if not raw:
        finding = ImportFinding(
            code=FindingCode.STRUCTURE_EMPTY,
            severity=FindingSeverity.WARNING,
            category=FindingCategory.STRUCTURE,
            description="Input file is empty",
            evidence="size=0",
        )
        return DecodeResult(
            surface_text="",
            text="",
            inventory=inventory_unicode(""),
            findings=(finding,),
        )

    bom_name = detect_bom_bytes(raw)
    if bom_name in {"utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"}:
        finding = ImportFinding(
            code=FindingCode.ENCODING_UTF16_UNSUPPORTED,
            severity=FindingSeverity.ERROR,
            category=FindingCategory.ENCODING,
            description=(
                f"{bom_name} encoded input is not supported by the current import policy "
                f"(required encoding: {policy.required_encoding})"
            ),
            evidence=f"bom={bom_name}",
        )
        return DecodeResult(
            surface_text="",
            text="",
            inventory=inventory_unicode("", bom_name=bom_name),
            findings=(finding,),
        )

    encoding = "ascii" if policy.required_encoding == "ascii" else "utf-8"
    try:
        surface_text = raw.decode(encoding, errors="strict")
    except UnicodeDecodeError as exc:
        finding = ImportFinding(
            code=FindingCode.ENCODING_INVALID_UTF8,
            severity=FindingSeverity.ERROR,
            category=FindingCategory.ENCODING,
            description=f"Input is not valid {encoding}",
            evidence=f"decode_error={exc.reason}",
        )
        return DecodeResult(
            surface_text="",
            text="",
            inventory=inventory_unicode("", bom_name=bom_name),
            findings=(finding,),
        )

    # The BOM code point is container framing, not content: strip it from the
    # surface view so node spans index exactly the surface text. Its presence
    # is preserved via bom_name in the inventory and the encoding finding.
    text = strip_bom(surface_text)
    # Inventory the stripped text so every offset lives in the same
    # coordinate space as node spans and the surface view.
    inventory = inventory_unicode(text, bom_name=bom_name)
    # Unicode findings are emitted once by assemble_rich_payloads from this
    # inventory; returning them here as well would double-report them.
    return DecodeResult(
        surface_text=text,
        text=text,
        inventory=inventory,
        findings=(),
    )


def _active_to_payload(item: ActiveContentFinding) -> dict[str, object]:
    return {
        "description": item.description,
        "evidence": item.evidence,
        "kind": item.kind.value,
        "offset": item.offset,
    }


def _expect_int_value(value: object, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise DomainError(f"Invalid import payload: {what} must be a number")
    return int(value)


def _expect_int_list(payload: dict[str, object], key: str) -> tuple[int, ...]:
    raw = payload.get(key) or []
    if not isinstance(raw, list):
        raise DomainError(f"Invalid import payload: {key} must be a list")
    return tuple(_expect_int_value(item, key) for item in raw)


def _expect_str_list(payload: dict[str, object], key: str) -> tuple[str, ...]:
    raw = payload.get(key) or []
    if not isinstance(raw, list):
        raise DomainError(f"Invalid import payload: {key} must be a list")
    return tuple(str(item) for item in raw)


def _active_from_payload(payload: dict[str, object]) -> ActiveContentFinding:
    return ActiveContentFinding(
        kind=ActiveContentKind(str(payload["kind"])),
        offset=_expect_int_value(payload["offset"], "active offset"),
        description=str(payload["description"]),
        evidence=str(payload["evidence"]),
    )


def _unicode_from_payload(payload: dict[str, object]) -> UnicodeInventory:
    return UnicodeInventory(
        has_bom=bool(payload.get("has_bom", False)),
        bom_name=str(payload.get("bom_name", "")),
        normalization_form=NormalizationForm(str(payload["normalization_form"])),
        control_char_offsets=_expect_int_list(payload, "control_char_offsets"),
        surrogate_offsets=_expect_int_list(payload, "surrogate_offsets"),
        non_nfc_offsets=_expect_int_list(payload, "non_nfc_offsets"),
        line_ending=str(payload.get("line_ending", "lf")),
        codepoint_count=_expect_int_value(payload.get("codepoint_count", 0), "codepoint_count"),
    )


def _metadata_from_payload(payload: dict[str, object]) -> tuple[MetadataItem, ...]:
    items = payload.get("items") or []
    if not isinstance(items, list):
        return ()
    result: list[MetadataItem] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        result.append(
            MetadataItem(key=str(item["key"]), kind=str(item["kind"]), value=str(item["value"]))
        )
    return tuple(result)


class ParserAdapter(Protocol):
    """Shape every importer adapter exposes to the shared pipeline."""

    parser_name: str
    parser_version: str
    supported_kinds: frozenset[FileKind]

    def parse_payloads(self, raw: bytes, policy: ImportPolicy) -> dict[str, object]:
        """Parse raw bytes into the shared worker payload envelope."""
        ...


def assemble_inspection(
    *,
    raw: bytes,
    identity: FileIdentity,
    policy: ImportPolicy,
    adapter: ParserAdapter,
    payloads: dict[str, object],
    extra_findings: tuple[ImportFinding, ...] = (),
) -> ImportInspection:
    """Assemble an ImportInspection from identity plus parse payloads.

    Payloads have the shape produced by :meth:`BaseImporter.parse_payloads`
    (which the parser worker also emits), so both the in-process and the
    sandboxed paths share this single assembly implementation.
    """
    findings_payload = payloads["findings"]
    content_findings: tuple[ImportFinding, ...] = ()
    if isinstance(findings_payload, list):
        content_findings = tuple(
            finding_from_payload(item, "worker finding")
            for item in findings_payload
            if isinstance(item, dict)
        )
    all_findings = extra_findings + content_findings

    document = None
    document_payload = payloads["document"]
    if document_payload is not None:
        document = document_from_json(json.dumps(document_payload, ensure_ascii=False))

    unicode_payload = payloads["unicode"]
    unicode_inventory = (
        _unicode_from_payload(unicode_payload) if isinstance(unicode_payload, dict) else None
    )
    measurements_payload = payloads["measurements"]
    if isinstance(measurements_payload, dict):
        peak_value = measurements_payload.get("peak_memory_bytes")
        measurements = ResourceMeasurements(
            size_bytes=len(raw),
            expanded_bytes=_expect_int_value(
                measurements_payload["expanded_bytes"], "expanded_bytes"
            ),
            node_count=_expect_int_value(measurements_payload["node_count"], "node_count"),
            tree_depth=_expect_int_value(measurements_payload["tree_depth"], "tree_depth"),
            peak_memory_bytes=(
                _expect_int_value(peak_value, "peak_memory_bytes")
                if peak_value is not None
                else None
            ),
        )
    else:
        measurements = measure_document(document, len(raw))

    coverage_payload = payloads["coverage"]
    coverage = CoverageSummary(
        adapter=str(coverage_payload["adapter"]) if isinstance(coverage_payload, dict) else "",
        supported_structures=_expect_str_list(coverage_payload, "supported_structures")
        if isinstance(coverage_payload, dict)
        else (),
        unsupported_structures=_expect_str_list(coverage_payload, "unsupported_structures")
        if isinstance(coverage_payload, dict)
        else (),
        status=str(coverage_payload["status"]) if isinstance(coverage_payload, dict) else "partial",
    )

    metadata_payload = payloads["metadata"]
    metadata = MetadataInventory(
        items=_metadata_from_payload(metadata_payload) if isinstance(metadata_payload, dict) else ()
    )

    active_payload = payloads["active_content"]
    active: tuple[ActiveContentFinding, ...] = ()
    if isinstance(active_payload, list):
        active = tuple(
            _active_from_payload(item) for item in active_payload if isinstance(item, dict)
        )

    return make_inspection(
        raw=raw,
        identity=identity,
        lane=policy.lane,
        parser_name=adapter.parser_name,
        parser_version=adapter.parser_version,
        policy=policy,
        findings=all_findings,
        coverage=coverage,
        metadata=metadata,
        unicode_inventory=unicode_inventory,
        active_content=active,
        measurements=measurements,
        document=document,
    )


def assemble_rich_payloads(
    *,
    raw: bytes,
    policy: ImportPolicy,
    parser_name: str,
    parser_version: str,
    surface_text: str,
    root: NodeBuilder | None,
    findings: list[ImportFinding],
    coverage: CoverageSummary,
    metadata: MetadataInventory,
    active: tuple[ActiveContentFinding, ...],
    unicode_inventory: UnicodeInventory | None = None,
) -> dict[str, object]:
    """Build, measure, and envelope a parsed container's shared payloads.

    Text and rich-format adapters both emit through this tail so the
    worker protocol has exactly one payload shape.
    """
    if unicode_inventory is None:
        unicode_inventory = inventory_unicode(surface_text)
    findings.extend(unicode_findings(unicode_inventory))
    findings.extend(active_content_findings(active))

    document_payload: dict[str, object] | None = None
    measurements = measure_document(None, len(raw)).to_payload()
    if root is not None:
        try:
            document = build_document(
                root=root,
                lane=policy.lane,
                parser_name=parser_name,
                parser_version=parser_version,
                policy=policy,
                surface_text=surface_text,
                findings=tuple(findings),
            )
        except DomainError as exc:
            findings.append(
                ImportFinding(
                    code=FindingCode.LIMIT_NODES,
                    severity=FindingSeverity.ERROR,
                    category=FindingCategory.RESOURCE_LIMIT,
                    description=str(exc),
                    evidence="build_document",
                )
            )
        else:
            measured = measure_document(document, len(raw))
            findings.extend(
                check_limits(
                    policy,
                    size_bytes=len(raw),
                    expanded_bytes=measured.expanded_bytes,
                    node_count=measured.node_count,
                    depth=measured.tree_depth,
                )
            )
            measurements = measured.to_payload()
            still_blocked = any(
                finding.severity is FindingSeverity.ERROR
                and finding.category is FindingCategory.RESOURCE_LIMIT
                for finding in findings
            )
            if not still_blocked:
                document_payload = document_to_payload(document)

    return {
        "status": classify_status(tuple(findings)).value,
        "findings": [finding_to_payload(finding) for finding in findings],
        "unicode": unicode_inventory.to_payload(),
        "active_content": [_active_to_payload(item) for item in active],
        "metadata": metadata.to_payload(),
        "coverage": {
            "adapter": coverage.adapter,
            "status": coverage.status,
            "supported_structures": list(coverage.supported_structures),
            "unsupported_structures": list(coverage.unsupported_structures),
        },
        "measurements": measurements,
        "document": document_payload,
    }


def identity_precheck(
    path: str, raw: bytes
) -> tuple[FileIdentity, list[ImportFinding], ImportFinding | None]:
    """Run identity checks shared by every importer's in-process path."""
    identity = derive_identity(path, raw)
    findings = list(identity_findings(identity))
    unsupported_finding = unsupported_format_finding(identity)
    if unsupported_finding is not None:
        findings.append(unsupported_finding)
    return identity, findings, unsupported_finding


def fail_closed_inspection(
    *,
    raw: bytes,
    identity: FileIdentity,
    findings: list[ImportFinding],
    unsupported_finding: ImportFinding | None,
    policy: ImportPolicy,
    parser_name: str,
    parser_version: str,
) -> ImportInspection:
    """Build the blocked inspection used before any content parsing."""
    return make_inspection(
        raw=raw,
        identity=identity,
        lane=policy.lane,
        parser_name=parser_name,
        parser_version=parser_version,
        policy=policy,
        findings=tuple(findings),
        coverage=CoverageSummary(
            adapter=parser_name,
            supported_structures=(),
            unsupported_structures=(
                (identity.declared_kind.value,) if unsupported_finding is not None else ()
            ),
            status=("unsupported_format" if unsupported_finding is not None else "partial"),
        ),
        measurements=measure_document(None, len(raw)),
    )


class BaseImporter(ABC):
    """Common fail-closed pipeline for text-based import adapters.

    Subclasses implement :meth:`parse` only. The pipeline performs limit
    checks, decoding, active-content scanning, document construction, and
    inspection assembly in a fixed deterministic order.
    """

    parser_name: str = "base"
    parser_version: str = "1"
    supported_kinds: frozenset[FileKind] = frozenset()

    @abstractmethod
    def parse(
        self, text: str, policy: ImportPolicy
    ) -> tuple[NodeBuilder | None, CoverageSummary, tuple[ImportFinding, ...], MetadataInventory]:
        """Parse decoded text into a document tree, coverage, findings, metadata.

        Returns a ``None`` tree when the document cannot be represented; the
        accompanying findings must explain why.
        """

    def parse_payloads(self, raw: bytes, policy: ImportPolicy) -> dict[str, object]:
        """Run the content pipeline and return serializable payloads.

        This is the parser-worker entry path: it touches only content bytes
        and the policy, never the filesystem, network, or model code.
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

        active = scan_active_content(decoded.text)

        metadata = MetadataInventory()
        coverage = CoverageSummary(
            adapter=self.parser_name,
            supported_structures=(),
            unsupported_structures=(),
            status="partial",
        )

        root: NodeBuilder | None = None
        parse_blocked = any(
            finding.severity is FindingSeverity.ERROR
            and finding.category in {FindingCategory.ENCODING, FindingCategory.RESOURCE_LIMIT}
            for finding in findings
        )
        if not parse_blocked and decoded.text:
            root, coverage, parse_findings, metadata = self.parse(decoded.text, policy)
            findings.extend(parse_findings)

        return assemble_rich_payloads(
            raw=raw,
            policy=policy,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            surface_text=decoded.surface_text,
            root=root,
            findings=findings,
            coverage=coverage,
            metadata=metadata,
            active=active,
            unicode_inventory=decoded.inventory,
        )

    def inspect(self, raw: bytes, path: str, policy: ImportPolicy) -> ImportInspection:
        """Inspect a file's bytes and build a full ImportInspection.

        Identity and container checks run before any content parsing; the
        input bytes are never written and never leave the caller's memory.
        """
        identity, findings, unsupported_finding = identity_precheck(path, raw)
        hard_blocked = any(finding.severity is FindingSeverity.ERROR for finding in findings)
        if hard_blocked:
            return fail_closed_inspection(
                raw=raw,
                identity=identity,
                findings=findings,
                unsupported_finding=unsupported_finding,
                policy=policy,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
            )
        payloads = self.parse_payloads(raw, policy)
        return assemble_inspection(
            raw=raw,
            identity=identity,
            policy=policy,
            adapter=self,
            payloads=payloads,
        )


class ContainerImporter(ABC):
    """Common fail-closed pipeline for rich-format container adapters.

    Subclasses implement :meth:`parse_payloads` directly (containers are
    not decoded as plain text). Identity checks and inspection assembly
    are shared with the text pipeline; content parsing always runs inside
    the bounded parser worker in product paths.
    """

    parser_name: str = "container"
    parser_version: str = "1"
    supported_kinds: frozenset[FileKind] = frozenset()

    @abstractmethod
    def parse_payloads(self, raw: bytes, policy: ImportPolicy) -> dict[str, object]:
        """Parse a container's raw bytes into the shared payload envelope."""

    def inspect(self, raw: bytes, path: str, policy: ImportPolicy) -> ImportInspection:
        """Inspect a container's bytes and build a full ImportInspection."""
        identity, findings, unsupported_finding = identity_precheck(path, raw)
        hard_blocked = any(finding.severity is FindingSeverity.ERROR for finding in findings)
        if hard_blocked:
            return fail_closed_inspection(
                raw=raw,
                identity=identity,
                findings=findings,
                unsupported_finding=unsupported_finding,
                policy=policy,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
            )
        payloads = self.parse_payloads(raw, policy)
        return assemble_inspection(
            raw=raw,
            identity=identity,
            policy=policy,
            adapter=self,
            payloads=payloads,
        )
