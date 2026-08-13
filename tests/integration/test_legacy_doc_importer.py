"""Integration tests for the fail-closed legacy DOC converter port."""

from __future__ import annotations

from collections.abc import Generator

import pytest

from humanhand.domain.canonical_document import ImportInspection
from humanhand.domain.import_findings import FindingCode, ImportStatus
from humanhand.domain.import_policy import ImportPolicy
from humanhand.infra.importers.legacy_doc_importer import (
    inspect_legacy_doc,
    set_legacy_doc_converter,
)
from humanhand.infra.importers.pipeline import SandboxedImportInspector

_OLE2_BYTES = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 512


@pytest.fixture(autouse=True)
def _clear_converter() -> Generator[None, None, None]:
    yield
    set_legacy_doc_converter(None)


@pytest.mark.importers
class TestLegacyDocFailClosed:
    def test_no_converter_configured_fails_closed(self) -> None:
        inspection = inspect_legacy_doc(_OLE2_BYTES, "notes.doc", ImportPolicy(lane="source"))
        assert inspection.document is None
        assert inspection.status is ImportStatus.FAILED
        assert any(
            finding.code == FindingCode.CONVERTER_NOT_CONFIGURED for finding in inspection.findings
        )

    def test_registered_converter_is_honored(self) -> None:
        class FakeConverter:
            def convert(self, raw: bytes, policy: ImportPolicy) -> ImportInspection:
                from humanhand.domain.canonical_document import (
                    CoverageSummary,
                    make_inspection,
                )
                from humanhand.domain.file_identity import derive_identity

                return make_inspection(
                    raw=raw,
                    identity=derive_identity("notes.doc", raw),
                    lane=policy.lane,
                    parser_name="legacy_doc",
                    parser_version="1",
                    policy=policy,
                    findings=(),
                    coverage=CoverageSummary(
                        adapter="legacy_doc",
                        supported_structures=("converted",),
                        unsupported_structures=(),
                        status="complete",
                    ),
                )

        set_legacy_doc_converter(FakeConverter())
        inspection = inspect_legacy_doc(_OLE2_BYTES, "notes.doc", ImportPolicy(lane="source"))
        assert inspection.status is ImportStatus.OK
        assert inspection.coverage.supported_structures == ("converted",)

    def test_pipeline_routes_legacy_doc_to_the_port(self) -> None:
        inspection = SandboxedImportInspector().inspect(
            path="notes.doc",
            raw=_OLE2_BYTES,
            head=_OLE2_BYTES[:256],
            size_bytes=len(_OLE2_BYTES),
            policy=ImportPolicy(lane="source"),
        )
        assert inspection.document is None
        assert any(
            finding.code == FindingCode.CONVERTER_NOT_CONFIGURED for finding in inspection.findings
        )

    def test_mismatched_doc_still_quarantines(self) -> None:
        # Plain text with a .doc extension is a magic mismatch and must
        # quarantine before any converter consideration.
        raw = b"this is not a doc file"
        inspection = SandboxedImportInspector().inspect(
            path="fake.doc",
            raw=raw,
            head=raw,
            size_bytes=len(raw),
            policy=ImportPolicy(lane="source"),
        )
        assert inspection.document is None
        assert inspection.status is ImportStatus.QUARANTINED
        assert any(finding.code == FindingCode.MAGIC_MISMATCH for finding in inspection.findings)
