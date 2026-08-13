"""Import inspection use case — pure orchestration over injected ports.

This module performs no file, network, or subprocess I/O. File access and
the parser-worker pipeline arrive as injected ports (wired by the CLI), and
content parsing always runs inside the bounded parser worker (ADR-004).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from humanhand.application.import_ports import ImportFileReader, ImportInspector
from humanhand.domain.canonical_document import (
    CoverageSummary,
    ImportInspection,
    make_inspection,
    measure_document,
)
from humanhand.domain.file_identity import derive_identity, identity_findings
from humanhand.domain.import_findings import (
    FindingCategory,
    FindingCode,
    FindingSeverity,
    ImportFinding,
)
from humanhand.domain.import_policy import ImportPolicy, validate_policy
from humanhand.domain.source_package import (
    LANE_SOURCE,
    LANE_STYLE,
    SourcePackage,
    StyleSamplePackage,
    build_source_package,
    build_style_sample_package,
)
from humanhand.domain.types import DomainError

_HEAD_BYTES_FOR_IDENTITY = 256


@dataclass(frozen=True)
class ImportInspectResult:
    """Result of the import inspection use case."""

    inspection: ImportInspection
    duration_ms: int


def inspect_import(
    *,
    path: str | Path,
    policy: ImportPolicy,
    reader: ImportFileReader,
    inspector: ImportInspector,
) -> ImportInspectResult:
    """Inspect one file with the clean-room pipeline.

    Missing/illegible paths raise FileIOError from the reader (mapped to
    exit codes by the CLI). Every content-level problem is a finding inside
    the returned inspection instead of an exception.
    """
    validate_policy(policy)
    started_at = time.monotonic()
    path_str = str(path)

    size_bytes = reader.size_bytes(path_str)
    if size_bytes > policy.max_bytes:
        # Size pre-check: never read an over-limit file into memory. The
        # leading bytes still identify the file honestly in the result.
        head = reader.read_head(path_str, _HEAD_BYTES_FOR_IDENTITY)
        identity = derive_identity(path_str, head, size_bytes=size_bytes)
        limit_finding = ImportFinding(
            code=FindingCode.LIMIT_BYTES,
            severity=FindingSeverity.ERROR,
            category=FindingCategory.RESOURCE_LIMIT,
            description=f"File size {size_bytes} bytes exceeds limit {policy.max_bytes}",
            evidence=f"size={size_bytes} limit={policy.max_bytes}",
        )
        inspection = make_inspection(
            raw=b"",
            identity=identity,
            lane=policy.lane,
            parser_name="none",
            parser_version="1",
            policy=policy,
            findings=identity_findings(identity) + (limit_finding,),
            coverage=CoverageSummary(
                adapter="none",
                supported_structures=(),
                unsupported_structures=(),
                status="partial",
            ),
            measurements=measure_document(None, size_bytes),
        )
        return ImportInspectResult(
            inspection=inspection,
            duration_ms=round((time.monotonic() - started_at) * 1000),
        )

    raw = reader.read_bytes(path_str)
    head = raw[:_HEAD_BYTES_FOR_IDENTITY]
    inspection = inspector.inspect(
        path=path_str,
        raw=raw,
        head=head,
        size_bytes=size_bytes,
        policy=policy,
    )
    return ImportInspectResult(
        inspection=inspection,
        duration_ms=round((time.monotonic() - started_at) * 1000),
    )


def build_import_policy(
    *,
    lane: str,
    max_bytes: int,
    max_expanded_bytes: int,
    max_nodes: int,
    timeout_seconds: float,
) -> ImportPolicy:
    """Build a validated ImportPolicy from resolved configuration values."""
    policy = ImportPolicy(
        lane=lane,
        max_bytes=max_bytes,
        max_expanded_bytes=max_expanded_bytes,
        max_nodes=max_nodes,
        timeout_seconds=timeout_seconds,
    )
    validate_policy(policy)
    return policy


@dataclass(frozen=True)
class SourceImportResult:
    """Result of the source-lane import use case.

    ``package`` is None when the inspection failed closed (quarantine,
    unsupported format, limits); the inspection still explains why.
    """

    inspection: ImportInspection
    package: SourcePackage | None
    duration_ms: int


@dataclass(frozen=True)
class StyleImportResult:
    """Result of the style-lane import use case.

    ``package`` is None when the inspection failed closed; the inspection
    still explains why. Style results never carry fact evidence.
    """

    inspection: ImportInspection
    package: StyleSamplePackage | None
    duration_ms: int


def _inspect_raw_bytes(
    *,
    path: str | Path,
    raw: bytes,
    policy: ImportPolicy,
    inspector: ImportInspector,
    lane: str,
) -> tuple[ImportInspection, int]:
    """Inspect already-read bytes with lane validation (no second read)."""
    import time as _time

    validate_policy(policy)
    if policy.lane != lane:
        raise DomainError(f"Lane mismatch: expected {lane!r}, got {policy.lane!r}")
    started_at = _time.monotonic()
    size_bytes = len(raw)
    if size_bytes > policy.max_bytes:
        identity = derive_identity(str(path), raw[:_HEAD_BYTES_FOR_IDENTITY], size_bytes=size_bytes)
        limit_finding = ImportFinding(
            code=FindingCode.LIMIT_BYTES,
            severity=FindingSeverity.ERROR,
            category=FindingCategory.RESOURCE_LIMIT,
            description=f"File size {size_bytes} bytes exceeds limit {policy.max_bytes}",
            evidence=f"size={size_bytes} limit={policy.max_bytes}",
        )
        inspection = make_inspection(
            raw=b"",
            identity=identity,
            lane=lane,
            parser_name="none",
            parser_version="1",
            policy=policy,
            findings=identity_findings(identity) + (limit_finding,),
            coverage=CoverageSummary(
                adapter="none",
                supported_structures=(),
                unsupported_structures=(),
                status="partial",
            ),
            measurements=measure_document(None, size_bytes),
        )
        return inspection, round((_time.monotonic() - started_at) * 1000)
    inspection = inspector.inspect(
        path=str(path),
        raw=raw,
        head=raw[:_HEAD_BYTES_FOR_IDENTITY],
        size_bytes=size_bytes,
        policy=policy,
    )
    return inspection, round((_time.monotonic() - started_at) * 1000)


def _run_lane_inspection(
    *,
    path: str | Path,
    policy: ImportPolicy,
    reader: ImportFileReader,
    inspector: ImportInspector,
    lane: str,
) -> tuple[ImportInspection, int]:
    validate_policy(policy)
    if policy.lane != lane:
        raise DomainError(f"Lane mismatch: expected {lane!r}, got {policy.lane!r}")
    started_at = time.monotonic()
    size_bytes = reader.size_bytes(str(path))
    if size_bytes > policy.max_bytes:
        head = reader.read_head(str(path), _HEAD_BYTES_FOR_IDENTITY)
        identity = derive_identity(str(path), head, size_bytes=size_bytes)
        limit_finding = ImportFinding(
            code=FindingCode.LIMIT_BYTES,
            severity=FindingSeverity.ERROR,
            category=FindingCategory.RESOURCE_LIMIT,
            description=f"File size {size_bytes} bytes exceeds limit {policy.max_bytes}",
            evidence=f"size={size_bytes} limit={policy.max_bytes}",
        )
        inspection = make_inspection(
            raw=b"",
            identity=identity,
            lane=lane,
            parser_name="none",
            parser_version="1",
            policy=policy,
            findings=identity_findings(identity) + (limit_finding,),
            coverage=CoverageSummary(
                adapter="none",
                supported_structures=(),
                unsupported_structures=(),
                status="partial",
            ),
            measurements=measure_document(None, size_bytes),
        )
        return inspection, round((time.monotonic() - started_at) * 1000)
    raw = reader.read_bytes(str(path))
    inspection = inspector.inspect(
        path=str(path),
        raw=raw,
        head=raw[:_HEAD_BYTES_FOR_IDENTITY],
        size_bytes=size_bytes,
        policy=policy,
    )
    return inspection, round((time.monotonic() - started_at) * 1000)


def import_source_package(
    *,
    path: str | Path,
    policy: ImportPolicy,
    reader: ImportFileReader,
    inspector: ImportInspector,
) -> SourceImportResult:
    """Import one file on the source lane and build a source package."""
    inspection, duration_ms = _run_lane_inspection(
        path=path, policy=policy, reader=reader, inspector=inspector, lane=LANE_SOURCE
    )
    package = None
    if inspection.document is not None:
        package = build_source_package(inspection)
    return SourceImportResult(inspection=inspection, package=package, duration_ms=duration_ms)


def import_style_package(
    *,
    path: str | Path,
    policy: ImportPolicy,
    reader: ImportFileReader,
    inspector: ImportInspector,
    raw_override: bytes | None = None,
) -> StyleImportResult:
    """Import one file on the style lane and build a style sample package.

    ``raw_override`` lets the caller supply the bytes it already read, so
    the vault original and the analyzed bytes are provably the same (no
    double-read TOCTOU window).
    """
    if raw_override is not None:
        inspection, duration_ms = _inspect_raw_bytes(
            path=path, raw=raw_override, policy=policy, inspector=inspector, lane=LANE_STYLE
        )
    else:
        inspection, duration_ms = _run_lane_inspection(
            path=path, policy=policy, reader=reader, inspector=inspector, lane=LANE_STYLE
        )
    package = None
    if inspection.document is not None:
        package = build_style_sample_package(inspection)
    return StyleImportResult(inspection=inspection, package=package, duration_ms=duration_ms)
