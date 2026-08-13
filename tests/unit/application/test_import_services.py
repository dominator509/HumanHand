"""Unit tests for the lane-separated import use cases with fake ports."""

from __future__ import annotations

import pytest

from humanhand.application.import_services import (
    import_source_package,
    import_style_package,
    inspect_import,
)
from humanhand.domain.canonical_document import (
    CoverageSummary,
    ImportInspection,
    build_document,
    make_inspection,
)
from humanhand.domain.document_nodes import NodeBuilder, NodeType
from humanhand.domain.file_identity import derive_identity
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.source_package import SourcePackage, StyleSamplePackage
from humanhand.domain.types import DomainError


class FakeReader:
    """Fake import file reader over in-memory bytes."""

    def __init__(self, raw: bytes) -> None:
        self._raw = raw

    def size_bytes(self, path: str | object) -> int:
        return len(self._raw)

    def read_head(self, path: str | object, max_bytes: int) -> bytes:
        return self._raw[:max_bytes]

    def read_bytes(self, path: str | object) -> bytes:
        return self._raw


class FakeInspector:
    """Fake import inspector producing a fixed inspection."""

    def __init__(self, inspection: ImportInspection) -> None:
        self._inspection = inspection
        self.calls: list[object] = []

    def inspect(
        self,
        *,
        path: str,
        raw: bytes,
        head: bytes,
        size_bytes: int,
        policy: ImportPolicy,
    ) -> ImportInspection:
        self.calls.append(policy)
        return self._inspection


def _inspection(lane: str, text: str = "In 2024 we shipped 300 units.") -> ImportInspection:
    raw = text.encode("utf-8")
    root = NodeBuilder(node_type=NodeType.DOCUMENT)
    root.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text=text))
    document = build_document(
        root=root,
        lane=lane,
        parser_name="text",
        parser_version="1",
        policy=ImportPolicy(lane=lane),
        surface_text=text,
    )
    return make_inspection(
        raw=raw,
        identity=derive_identity("sample.txt", raw),
        lane=lane,
        parser_name="text",
        parser_version="1",
        policy=ImportPolicy(lane=lane),
        findings=(),
        coverage=CoverageSummary(
            adapter="text",
            supported_structures=("paragraph",),
            unsupported_structures=(),
            status="complete",
        ),
        document=document,
    )


class TestInspectImportUseCase:
    def test_happy_path_through_ports(self) -> None:
        raw = b"hello world\n"
        inspection = _inspection("source", text="hello world")
        result = inspect_import(
            path="sample.txt",
            policy=ImportPolicy(lane="source"),
            reader=FakeReader(raw),
            inspector=FakeInspector(inspection),
        )
        assert result.inspection is inspection
        assert result.duration_ms >= 0

    def test_over_limit_fails_closed_without_reading(self) -> None:
        reader = FakeReader(b"x" * 100)
        inspection = _inspection("source")
        policy = ImportPolicy(lane="source", max_bytes=10)
        result = inspect_import(
            path="big.txt",
            policy=policy,
            reader=reader,
            inspector=FakeInspector(inspection),
        )
        assert result.inspection.document is None
        codes = [finding.code for finding in result.inspection.findings]
        assert "import.limit.bytes" in codes


class TestLaneImportUseCases:
    def test_source_use_case_builds_source_package(self) -> None:
        raw = b"In 2024 we shipped 300 units."
        inspection = _inspection("source")
        result = import_source_package(
            path="sample.txt",
            policy=ImportPolicy(lane="source"),
            reader=FakeReader(raw),
            inspector=FakeInspector(inspection),
        )
        assert isinstance(result.package, SourcePackage)
        assert result.package.package_id.startswith("src-")

    def test_style_use_case_builds_style_package(self) -> None:
        raw = b"In 2024 we shipped 300 units."
        inspection = _inspection("style")
        result = import_style_package(
            path="sample.txt",
            policy=ImportPolicy(lane="style"),
            reader=FakeReader(raw),
            inspector=FakeInspector(inspection),
        )
        assert isinstance(result.package, StyleSamplePackage)
        assert result.package.package_id.startswith("sty-")

    def test_source_use_case_rejects_style_policy(self) -> None:
        inspection = _inspection("style")
        with pytest.raises(DomainError, match="Lane mismatch"):
            import_source_package(
                path="sample.txt",
                policy=ImportPolicy(lane="style"),
                reader=FakeReader(b"x"),
                inspector=FakeInspector(inspection),
            )

    def test_style_use_case_rejects_source_policy(self) -> None:
        inspection = _inspection("source")
        with pytest.raises(DomainError, match="Lane mismatch"):
            import_style_package(
                path="sample.txt",
                policy=ImportPolicy(lane="source"),
                reader=FakeReader(b"x"),
                inspector=FakeInspector(inspection),
            )

    def test_fail_closed_inspection_yields_no_package(self) -> None:
        # An inspection without a canonical document (e.g., quarantined)
        # produces no package; the inspection itself explains why.
        raw = b"plain text pretending to be docx"
        inspection = make_inspection(
            raw=raw,
            identity=derive_identity("fake.docx", raw),
            lane="source",
            parser_name="none",
            parser_version="1",
            policy=ImportPolicy(lane="source"),
            findings=(),
            coverage=CoverageSummary(
                adapter="none",
                supported_structures=(),
                unsupported_structures=(),
                status="partial",
            ),
        )
        result = import_source_package(
            path="fake.docx",
            policy=ImportPolicy(lane="source"),
            reader=FakeReader(raw),
            inspector=FakeInspector(inspection),
        )
        assert result.package is None
        assert result.inspection is inspection
