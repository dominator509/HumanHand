"""Bounded container primitives for rich-format importers (ZIP and XML).

Every access path enforces the import policy's expanded-size and count
limits before any parsing, so hostile archives fail closed with findings
instead of exhausting memory.
"""

from __future__ import annotations

import io
import zipfile
from typing import Any

# defusedxml ships no type stubs; its API is stdlib-compatible.
from defusedxml import ElementTree as _DefusedElementTree  # type: ignore[import-untyped]

from humanhand.domain.import_findings import (
    FindingCategory,
    FindingCode,
    FindingSeverity,
    ImportFinding,
)
from humanhand.domain.import_policy import ImportPolicy

# Plain assignment (not an aliased import) so downstream modules can
# `from container_utils import ET` without an explicit-export complaint.
ET = _DefusedElementTree

DEFAULT_MAX_ARCHIVE_ENTRIES = 10_000
MAX_EVIDENCE_NAME_CHARS = 64


def evidence_name(name: str) -> str:
    """Bound an archive entry name before it enters finding evidence.

    Entry names are attacker-controlled; evidence must stay short and
    free of arbitrary injected text (finding evidence never carries
    document content).
    """
    cleaned = name.replace(chr(13), " ").replace(chr(10), " ")
    if len(cleaned) <= MAX_EVIDENCE_NAME_CHARS:
        return cleaned
    return cleaned[: MAX_EVIDENCE_NAME_CHARS - 3] + "..."


def open_zip_bounded(
    raw: bytes, policy: ImportPolicy
) -> tuple[zipfile.ZipFile | None, tuple[ImportFinding, ...]]:
    """Open a ZIP container with entry-count and expanded-size limits.

    Returns ``(None, findings)`` when the container is not a valid ZIP or
    breaches a limit; findings carry the exact reason.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        finding = ImportFinding(
            code=FindingCode.UNSUPPORTED_FEATURE,
            severity=FindingSeverity.ERROR,
            category=FindingCategory.STRUCTURE,
            description="Not a valid ZIP container",
            evidence="bad_zip",
        )
        return None, (finding,)

    infos = archive.infolist()
    findings: list[ImportFinding] = []
    duplicate_count = len(infos) - len({info.filename for info in infos})
    if duplicate_count:
        findings.append(
            ImportFinding(
                code=FindingCode.CONTAINER_DUPLICATE_ENTRY,
                severity=FindingSeverity.ERROR,
                category=FindingCategory.STRUCTURE,
                description="Archive contains duplicate entry names",
                evidence=f"duplicates={duplicate_count}",
            )
        )
    if len(infos) > DEFAULT_MAX_ARCHIVE_ENTRIES:
        findings.append(
            ImportFinding(
                code=FindingCode.LIMIT_ARCHIVE_ENTRIES,
                severity=FindingSeverity.ERROR,
                category=FindingCategory.RESOURCE_LIMIT,
                description=(
                    f"Archive has {len(infos)} entries, exceeding limit "
                    f"{DEFAULT_MAX_ARCHIVE_ENTRIES}"
                ),
                evidence=f"entries={len(infos)}",
            )
        )
    expanded_bytes = sum(info.file_size for info in infos)
    if expanded_bytes > policy.max_expanded_bytes:
        findings.append(
            ImportFinding(
                code=FindingCode.LIMIT_EXPANDED_BYTES,
                severity=FindingSeverity.ERROR,
                category=FindingCategory.RESOURCE_LIMIT,
                description=(
                    f"Archive expands to {expanded_bytes} bytes, exceeding limit "
                    f"{policy.max_expanded_bytes}"
                ),
                evidence=f"expanded={expanded_bytes}",
            )
        )
    if findings:
        archive.close()
        return None, tuple(findings)
    return archive, ()


def read_zip_entry_bounded(
    archive: zipfile.ZipFile,
    name: str,
    policy: ImportPolicy,
) -> tuple[bytes, tuple[ImportFinding, ...]]:
    """Read one ZIP entry, enforcing the expanded-size limit.

    Returns ``(b"", findings)`` on any failure; the findings explain why.
    """
    try:
        info = archive.getinfo(name)
    except KeyError:
        finding = ImportFinding(
            code=FindingCode.UNSUPPORTED_FEATURE,
            severity=FindingSeverity.ERROR,
            category=FindingCategory.STRUCTURE,
            description=f"Container is missing required part: {name}",
            evidence=f"missing={name}",
        )
        return b"", (finding,)
    if info.file_size > policy.max_expanded_bytes:
        finding = ImportFinding(
            code=FindingCode.LIMIT_EXPANDED_BYTES,
            severity=FindingSeverity.ERROR,
            category=FindingCategory.RESOURCE_LIMIT,
            description=f"Part {name} expands beyond the import limit",
            evidence=f"part={name} size={info.file_size}",
        )
        return b"", (finding,)
    try:
        return archive.read(name), ()
    except (zipfile.BadZipFile, OSError, RuntimeError):
        finding = ImportFinding(
            code=FindingCode.UNSUPPORTED_FEATURE,
            severity=FindingSeverity.ERROR,
            category=FindingCategory.STRUCTURE,
            description=f"Cannot read container part: {name}",
            evidence=f"unreadable={name}",
        )
        return b"", (finding,)


def parse_xml_bounded(
    data: bytes, policy: ImportPolicy, what: str
) -> tuple[Any | None, tuple[ImportFinding, ...]]:
    """Parse untrusted XML with defusedxml plus a size cap.

    ``ET`` here is ``defusedxml.ElementTree``, which rejects entity
    expansion attacks before Expat sees them; failures become findings,
    never exceptions. All container adapters must parse XML through this
    function (or this module's ``ET``) — never stdlib ElementTree.
    """
    if len(data) > policy.max_expanded_bytes:
        finding = ImportFinding(
            code=FindingCode.LIMIT_EXPANDED_BYTES,
            severity=FindingSeverity.ERROR,
            category=FindingCategory.RESOURCE_LIMIT,
            description=f"XML part {what} exceeds the import limit",
            evidence=f"part={what} size={len(data)}",
        )
        return None, (finding,)
    try:
        return ET.fromstring(data), ()
    except ET.ParseError:
        finding = ImportFinding(
            code=FindingCode.UNSUPPORTED_FEATURE,
            severity=FindingSeverity.ERROR,
            category=FindingCategory.STRUCTURE,
            description=f"XML part {what} is not well-formed",
            evidence=f"malformed={what}",
        )
        return None, (finding,)
