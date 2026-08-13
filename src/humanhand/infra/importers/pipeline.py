"""Identity-to-worker import inspection pipeline (infra implementation).

This module owns the side-effect wiring for the import inspection use case:
file identity, adapter resolution, the bounded parser worker, and final
inspection assembly. The application layer orchestrates through it.
"""

from __future__ import annotations

from collections.abc import Callable

from humanhand.domain.canonical_document import (
    CoverageSummary,
    ImportInspection,
    make_inspection,
    measure_document,
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
)
from humanhand.domain.import_policy import ImportPolicy
from humanhand.infra.importers import get_importer_for
from humanhand.infra.importers.base import assemble_inspection
from humanhand.infra.importers.file_type import resolve_kind, unsupported_format_finding
from humanhand.infra.importers.legacy_doc_importer import inspect_legacy_doc
from humanhand.infra.sandbox.parser_supervisor import WorkerOutcome, run_worker


def _unsupported_inspection(
    *,
    raw: bytes,
    identity: FileIdentity,
    policy: ImportPolicy,
    adapter_name: str,
    adapter_version: str,
    findings: tuple[ImportFinding, ...],
    coverage_status: str,
    unsupported_structures: tuple[str, ...],
) -> ImportInspection:
    """Build a fail-closed inspection with no canonical content."""
    return make_inspection(
        raw=raw,
        identity=identity,
        lane=policy.lane,
        parser_name=adapter_name,
        parser_version=adapter_version,
        policy=policy,
        findings=findings,
        coverage=CoverageSummary(
            adapter=adapter_name,
            supported_structures=(),
            unsupported_structures=unsupported_structures,
            status=coverage_status,
        ),
        measurements=measure_document(None, len(raw)),
    )


class SandboxedImportInspector:
    """Inspect raw bytes through the bounded parser worker (ADR-004)."""

    def __init__(
        self,
        worker_runner: Callable[..., WorkerOutcome] | None = None,
    ) -> None:
        self._worker_runner = worker_runner if worker_runner is not None else run_worker

    def inspect(
        self,
        *,
        path: str,
        raw: bytes,
        head: bytes,
        size_bytes: int,
        policy: ImportPolicy,
    ) -> ImportInspection:
        """Run identity checks, the worker parse, and inspection assembly.

        ``head`` and ``size_bytes`` describe the file even when ``raw`` is
        empty (over-limit short-circuit), so identity reporting stays true.
        """
        identity = derive_identity(path, head, size_bytes=size_bytes)
        identity_issues = list(identity_findings(identity))

        # Legacy DOC never parses in-process (blueprint 7.6): route through
        # the isolated converter port before any unsupported-format check.
        if identity.declared_kind is FileKind.LEGACY_DOC and not identity.has_clear_mismatch():
            return inspect_legacy_doc(raw, path, policy)

        unsupported_finding = unsupported_format_finding(identity)
        if unsupported_finding is not None:
            identity_issues.append(unsupported_finding)

        adapter = get_importer_for(identity)
        if adapter is None:
            findings = tuple(identity_issues) + (
                ImportFinding(
                    code=FindingCode.UNSUPPORTED_FORMAT,
                    severity=FindingSeverity.ERROR,
                    category=FindingCategory.UNSUPPORTED_FEATURE,
                    description=(
                        f"No import adapter resolves kind '{resolve_kind(identity).value}'"
                    ),
                    evidence=f"kind={resolve_kind(identity).value}",
                ),
            )
            return _unsupported_inspection(
                raw=raw,
                identity=identity,
                policy=policy,
                adapter_name="none",
                adapter_version="1",
                findings=findings,
                coverage_status="unsupported_format",
                unsupported_structures=(resolve_kind(identity).value,),
            )

        hard_blocked = any(finding.severity is FindingSeverity.ERROR for finding in identity_issues)
        if hard_blocked:
            return _unsupported_inspection(
                raw=raw,
                identity=identity,
                policy=policy,
                adapter_name=adapter.parser_name,
                adapter_version=adapter.parser_version,
                findings=tuple(identity_issues),
                coverage_status=(
                    "unsupported_format" if unsupported_finding is not None else "partial"
                ),
                unsupported_structures=(
                    (identity.declared_kind.value,) if unsupported_finding is not None else ()
                ),
            )

        outcome = self._worker_runner(parser_name=adapter.parser_name, raw=raw, policy=policy)
        if outcome.result is None:
            return _unsupported_inspection(
                raw=raw,
                identity=identity,
                policy=policy,
                adapter_name=adapter.parser_name,
                adapter_version=adapter.parser_version,
                findings=tuple(identity_issues) + outcome.findings,
                coverage_status="partial",
                unsupported_structures=(),
            )

        payloads = outcome.result.model_dump()
        return assemble_inspection(
            raw=raw,
            identity=identity,
            policy=policy,
            adapter=adapter,
            payloads=payloads,
            extra_findings=tuple(identity_issues),
        )


__all__ = ["SandboxedImportInspector"]
