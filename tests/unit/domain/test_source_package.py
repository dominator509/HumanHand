"""Unit tests for lane-separated import packages and source evidence."""

from __future__ import annotations

import dataclasses

import pytest

from humanhand.domain.canonical_document import (
    CoverageSummary,
    build_document,
    make_inspection,
)
from humanhand.domain.document_nodes import NodeBuilder, NodeType
from humanhand.domain.file_identity import derive_identity
from humanhand.domain.import_findings import ImportStatus
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.protected_spans import SpanKind
from humanhand.domain.source_evidence import build_source_evidence
from humanhand.domain.source_package import (
    LANE_SOURCE,
    LANE_STYLE,
    SourcePackage,
    StyleSamplePackage,
    build_source_package,
    build_style_sample_package,
    source_package_from_json,
    style_sample_package_from_json,
)
from humanhand.domain.types import DomainError


def _document(lane: str = LANE_SOURCE, text: str = "In 2024 we shipped 300 units.") -> object:
    root = NodeBuilder(node_type=NodeType.DOCUMENT)
    root.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text=text))
    return build_document(
        root=root,
        lane=lane,
        parser_name="text",
        parser_version="1",
        policy=ImportPolicy(lane=lane),
        surface_text=text,
    )


def _inspection(lane: str, text: str = "In 2024 we shipped 300 units.") -> object:
    raw = text.encode("utf-8")
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
        document=_document(lane, text),  # type: ignore[arg-type]
    )


class TestBuildSourcePackage:
    def test_builds_from_source_inspection(self) -> None:
        inspection = _inspection(LANE_SOURCE)
        package = build_source_package(inspection)  # type: ignore[arg-type]
        assert isinstance(package, SourcePackage)
        assert package.status is ImportStatus.OK
        assert package.package_id.startswith("src-")
        assert package.revision_policy == "review_required"

    def test_package_id_is_deterministic(self) -> None:
        first = build_source_package(_inspection(LANE_SOURCE))  # type: ignore[arg-type]
        second = build_source_package(_inspection(LANE_SOURCE))  # type: ignore[arg-type]
        assert first.package_id == second.package_id

    def test_style_package_ids_differ_from_source(self) -> None:
        source = build_source_package(_inspection(LANE_SOURCE))  # type: ignore[arg-type]
        style = build_style_sample_package(_inspection(LANE_STYLE))  # type: ignore[arg-type]
        assert source.package_id != style.package_id

    def test_rejects_style_lane_for_source_package(self) -> None:
        with pytest.raises(DomainError, match="source"):
            build_source_package(_inspection(LANE_STYLE))  # type: ignore[arg-type]

    def test_rejects_source_lane_for_style_package(self) -> None:
        with pytest.raises(DomainError, match="style"):
            build_style_sample_package(_inspection(LANE_SOURCE))  # type: ignore[arg-type]

    def test_rejects_cross_lane_document_in_source_builder(self) -> None:
        # Inspection says source, but the embedded document is style-lane:
        # the builder must refuse (defense in depth for ADR-002).
        from humanhand.domain.canonical_document import make_inspection

        raw = b"x"
        mismatched = make_inspection(
            raw=raw,
            identity=derive_identity("s.txt", raw),
            lane=LANE_SOURCE,
            parser_name="text",
            parser_version="1",
            policy=ImportPolicy(lane=LANE_SOURCE),
            findings=(),
            coverage=CoverageSummary(
                adapter="text",
                supported_structures=("paragraph",),
                unsupported_structures=(),
                status="complete",
            ),
            document=_document(LANE_STYLE),  # type: ignore[arg-type]
        )
        with pytest.raises(DomainError, match="not a source-lane document"):
            build_source_package(mismatched)

    def test_rejects_cross_lane_document_in_style_builder(self) -> None:
        from humanhand.domain.canonical_document import make_inspection

        raw = b"x"
        mismatched = make_inspection(
            raw=raw,
            identity=derive_identity("s.txt", raw),
            lane=LANE_STYLE,
            parser_name="text",
            parser_version="1",
            policy=ImportPolicy(lane=LANE_STYLE),
            findings=(),
            coverage=CoverageSummary(
                adapter="text",
                supported_structures=("paragraph",),
                unsupported_structures=(),
                status="complete",
            ),
            document=_document(LANE_SOURCE),  # type: ignore[arg-type]
        )
        with pytest.raises(DomainError, match="not a style-lane document"):
            build_style_sample_package(mismatched)

    def test_from_json_rejects_cross_lane_document(self) -> None:
        # A source-package payload wrapping a style-lane document must not
        # deserialize, and its package_id is re-derived rather than trusted.
        import json

        style_package = build_style_sample_package(_inspection(LANE_STYLE))  # type: ignore[arg-type]
        smuggled = style_package.to_payload()
        smuggled["schema"] = "source-package"
        smuggled["schema_version"] = 1
        smuggled["lane"] = LANE_SOURCE
        smuggled["package_id"] = "src-000000000000000000000000"
        smuggled["findings"] = []
        smuggled["evidence"] = {
            "protected_spans": {"count": 0, "spans": []},
            "quotations": [],
            "citations": [],
        }
        with pytest.raises(DomainError, match="not source-lane"):
            source_package_from_json(json.dumps(smuggled))

    def test_from_json_rejects_tampered_package_id(self) -> None:
        import json

        package = build_source_package(_inspection(LANE_SOURCE))  # type: ignore[arg-type]
        payload = package.to_payload()
        payload["package_id"] = "src-000000000000000000000000"
        restored = source_package_from_json(json.dumps(payload))
        assert restored.package_id == package.package_id
        assert restored.package_id != "src-000000000000000000000000"

    def test_style_package_has_no_evidence_fields(self) -> None:
        """ADR-002: the style lane type structurally cannot carry fact evidence."""
        field_names = {field.name for field in dataclasses.fields(StyleSamplePackage)}
        assert "evidence" not in field_names
        assert "quotations" not in field_names
        assert "citations" not in field_names
        assert "protected_spans" not in field_names

    def test_source_package_round_trip(self) -> None:
        package = build_source_package(_inspection(LANE_SOURCE))  # type: ignore[arg-type]
        restored = source_package_from_json(package.to_json())
        assert restored.package_id == package.package_id
        assert restored.status is package.status
        # Evidence is re-derived deterministically from the document.
        assert len(restored.evidence.protected_spans.spans) == len(
            package.evidence.protected_spans.spans
        )
        assert restored.to_json() == package.to_json()

    def test_style_package_round_trip(self) -> None:
        package = build_style_sample_package(_inspection(LANE_STYLE))  # type: ignore[arg-type]
        restored = style_sample_package_from_json(package.to_json())
        assert restored.package_id == package.package_id
        assert restored.authorship_status == "unreviewed"
        assert restored.to_json() == package.to_json()

    def test_source_package_rejects_wrong_schema(self) -> None:
        package = build_source_package(_inspection(LANE_SOURCE))  # type: ignore[arg-type]
        payload = package.to_payload()
        payload["schema"] = "style-sample-package"
        import json

        with pytest.raises(DomainError, match="source-package"):
            source_package_from_json(json.dumps(payload))


class TestBuildSourceEvidence:
    def test_extracts_dates_numbers_and_citations(self) -> None:
        document = _document(text="On 2024-05-01 we shipped 300 units [12].")
        evidence = build_source_evidence(document)  # type: ignore[arg-type]
        kinds = {span.kind for span in evidence.protected_spans.spans}
        assert SpanKind.DATE in kinds
        assert SpanKind.NUMBER in kinds
        assert SpanKind.CITATION in kinds
        assert evidence.citations

    def test_extracts_month_first_date(self) -> None:
        document = _document(text="The deadline is August 30, 2026.")
        evidence = build_source_evidence(document)  # type: ignore[arg-type]
        dates = [s.text for s in evidence.protected_spans.spans if s.kind is SpanKind.DATE]
        assert dates == ["August 30, 2026"]

    def test_quotation_spans_and_evidence_agree(self) -> None:
        text = 'He said "this is a reasonably long quoted sentence" [1].'
        document = _document(text=text)
        evidence = build_source_evidence(document)  # type: ignore[arg-type]
        assert any(span.kind is SpanKind.QUOTATION for span in evidence.protected_spans.spans)
        assert any(citation.kind == "bracket_number" for citation in evidence.citations)

    def test_payload_shape(self) -> None:
        evidence = build_source_evidence(_document())  # type: ignore[arg-type]
        payload = evidence.to_payload()
        assert "protected_spans" in payload
        assert "quotations" in payload
        assert "citations" in payload
