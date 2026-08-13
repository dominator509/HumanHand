"""Fail-closed legacy DOC inspection via an isolated converter port.

HumanHand never parses binary DOC in its own process (blueprint 7.6). This
module provides the conversion adapter interface and the default
fail-closed behavior: with no approved converter configured, every legacy
DOC import produces an explicit finding and no canonical document.
"""

from __future__ import annotations

from typing import Protocol

from humanhand.domain.canonical_document import ImportInspection
from humanhand.domain.file_identity import FileKind
from humanhand.domain.import_findings import (
    FindingCategory,
    FindingCode,
    FindingSeverity,
    ImportFinding,
)
from humanhand.domain.import_policy import ImportPolicy
from humanhand.infra.importers.base import fail_closed_inspection, identity_precheck


class LegacyDocConverter(Protocol):
    """Isolated converter for legacy DOC files (future approved adapters)."""

    def convert(self, raw: bytes, policy: ImportPolicy) -> ImportInspection:
        """Convert legacy DOC bytes into a full ImportInspection."""
        ...


_converter: LegacyDocConverter | None = None


def set_legacy_doc_converter(converter: LegacyDocConverter | None) -> None:
    """Register or clear the approved legacy DOC converter (wiring seam).

    Production has no approved converter today; tests register fakes.
    """
    global _converter
    _converter = converter


def get_legacy_doc_converter() -> LegacyDocConverter | None:
    """Return the currently configured converter, if any."""
    return _converter


def inspect_legacy_doc(raw: bytes, path: str, policy: ImportPolicy) -> ImportInspection:
    """Inspect a legacy DOC file through the converter port, failing closed.

    Without a configured converter the import reports
    ``import.converter.not_configured`` and returns no canonical document.
    """
    identity, findings, unsupported_finding = identity_precheck(path, raw)
    # The converter port replaces the generic unsupported-format verdict
    # for declared legacy DOC files; every other identity check (magic
    # mismatch, binary content) still fails closed before conversion.
    if unsupported_finding is not None and identity.declared_kind is FileKind.LEGACY_DOC:
        findings = [
            finding for finding in findings if finding.code != FindingCode.UNSUPPORTED_FORMAT
        ]
        unsupported_finding = None
    hard_blocked = any(finding.severity is FindingSeverity.ERROR for finding in findings)
    if hard_blocked:
        return fail_closed_inspection(
            raw=raw,
            identity=identity,
            findings=findings,
            unsupported_finding=unsupported_finding,
            policy=policy,
            parser_name="legacy_doc",
            parser_version="1",
        )

    converter = _converter
    if converter is None:
        findings.append(
            ImportFinding(
                code=FindingCode.CONVERTER_NOT_CONFIGURED,
                severity=FindingSeverity.ERROR,
                category=FindingCategory.UNSUPPORTED_FEATURE,
                description=(
                    "Legacy DOC import requires an approved isolated converter, "
                    "and none is configured"
                ),
                evidence="converter=none",
            )
        )
        return fail_closed_inspection(
            raw=raw,
            identity=identity,
            findings=findings,
            unsupported_finding=unsupported_finding,
            policy=policy,
            parser_name="legacy_doc",
            parser_version="1",
        )
    return converter.convert(raw, policy)
