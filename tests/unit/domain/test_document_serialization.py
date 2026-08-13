"""Unit tests for deterministic canonical JSON serialization."""

from __future__ import annotations

import json
from typing import Any

import pytest

from humanhand.domain.canonical_document import (
    CanonicalDocument,
    CoverageSummary,
    ImportInspection,
    build_document,
    make_inspection,
)
from humanhand.domain.document_nodes import NodeBuilder, NodeType
from humanhand.domain.document_serialization import (
    document_from_json,
    document_to_json,
    document_to_payload,
    inspection_from_json,
    inspection_to_json,
    inspection_to_payload,
)
from humanhand.domain.file_identity import derive_identity
from humanhand.domain.import_findings import (
    FindingCategory,
    FindingCode,
    FindingSeverity,
    ImportFinding,
    ImportStatus,
)
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.types import DomainError


def _document() -> CanonicalDocument:
    root = NodeBuilder(node_type=NodeType.DOCUMENT)
    root.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text="Hello world."))
    return build_document(
        root=root,
        lane="source",
        parser_name="text",
        parser_version="1",
        policy=ImportPolicy(lane="source"),
        surface_text="Hello world.",
        findings=(
            ImportFinding(
                code=FindingCode.ENCODING_BOM,
                severity=FindingSeverity.WARNING,
                category=FindingCategory.ENCODING,
                description="BOM present: utf-8",
                evidence="bom=utf-8",
            ),
        ),
    )


class TestDocumentToJson:
    def test_byte_identical_replay(self) -> None:
        first = document_to_json(_document())
        second = document_to_json(_document())
        assert first == second
        assert first.endswith("\n")

    def test_keys_sorted_and_ascii_preserved(self) -> None:
        rendered = document_to_json(_document())
        payload = json.loads(rendered)
        assert list(payload.keys()) == sorted(payload.keys())
        assert payload["schema"] == "canonical-document"
        assert payload["schema_version"] == 1
        assert payload["lane"] == "source"
        assert payload["parser"] == {"name": "text", "version": "1"}
        assert payload["nodes"][0]["type"] == "document"
        assert payload["nodes"][1]["text"] == "Hello world."
        assert payload["nodes"][1]["text_canonical"] == "Hello world."
        # No wall-clock or random identifiers inside canonical content.
        assert "timestamp" not in rendered
        assert "created_at" not in rendered

    def test_non_ascii_text_is_not_escaped(self) -> None:
        root = NodeBuilder(node_type=NodeType.DOCUMENT)
        root.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text="café"))
        document = build_document(
            root=root,
            lane="source",
            parser_name="text",
            parser_version="1",
            policy=ImportPolicy(lane="source"),
            surface_text="café",
        )
        rendered = document_to_json(document)
        assert "café" in rendered
        assert "caf\\u00e9" not in rendered

    def test_surface_and_canonical_text_fields(self) -> None:
        decomposed = "café"
        root = NodeBuilder(node_type=NodeType.DOCUMENT)
        root.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text=decomposed))
        document = build_document(
            root=root,
            lane="source",
            parser_name="text",
            parser_version="1",
            policy=ImportPolicy(lane="source"),
            surface_text=decomposed,
        )
        payload = document_to_payload(document)
        assert payload["surface_text"] == decomposed
        assert payload["canonical_text"] == "café"
        nodes = payload["nodes"]
        assert isinstance(nodes, list)
        node = nodes[1]
        assert isinstance(node, dict)
        assert node["text"] == decomposed
        assert node["text_canonical"] == "café"


class TestDocumentFromJson:
    def test_round_trip(self) -> None:
        original = _document()
        restored = document_from_json(document_to_json(original))
        assert restored.lane == "source"
        assert restored.parser_name == "text"
        assert len(restored.nodes) == 2
        assert restored.findings[0].code == FindingCode.ENCODING_BOM
        # Re-serializing the restored document is byte-identical.
        assert document_to_json(restored) == document_to_json(original)

    def test_rejects_invalid_json(self) -> None:
        with pytest.raises(DomainError, match="not valid JSON"):
            document_from_json("{not json")

    def test_rejects_wrong_schema(self) -> None:
        payload = document_to_payload(_document())
        payload["schema"] = "other"
        with pytest.raises(DomainError, match="schema"):
            document_from_json(json.dumps(payload))

    def test_rejects_unknown_schema_version(self) -> None:
        payload = document_to_payload(_document())
        payload["schema_version"] = 999
        with pytest.raises(DomainError, match="version"):
            document_from_json(json.dumps(payload))

    def test_rejects_unknown_node_type(self) -> None:
        payload: Any = json.loads(document_to_json(_document()))
        payload["nodes"][1]["type"] = "quantum_block"
        with pytest.raises(DomainError, match="node type"):
            document_from_json(json.dumps(payload))

    def test_rejects_bad_parent_reference(self) -> None:
        payload: Any = json.loads(document_to_json(_document()))
        payload["nodes"][1]["parent_id"] = "n999"
        with pytest.raises(DomainError, match="parent_id"):
            document_from_json(json.dumps(payload))

    def test_rejects_duplicate_node_ids(self) -> None:
        payload: Any = json.loads(document_to_json(_document()))
        payload["nodes"][1]["id"] = payload["nodes"][0]["id"]
        with pytest.raises(DomainError, match="duplicate"):
            document_from_json(json.dumps(payload))


class TestBundledSchemaStaysInSync:
    """The packaged canonical-document JSON Schema must not drift."""

    def test_schema_file_exists_and_parses(self) -> None:
        from pathlib import Path

        schema_path = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "humanhand"
            / "resources"
            / "schemas"
            / "canonical-document.schema.json"
        )
        payload = json.loads(schema_path.read_text(encoding="utf-8"))
        assert payload["$id"].endswith("canonical-document.schema.json")
        assert payload["properties"]["schema"]["const"] == "canonical-document"

    def test_schema_node_types_match_domain_enum(self) -> None:
        from pathlib import Path

        from humanhand.domain.document_nodes import NodeType

        schema_path = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "humanhand"
            / "resources"
            / "schemas"
            / "canonical-document.schema.json"
        )
        payload = json.loads(schema_path.read_text(encoding="utf-8"))
        schema_types = set(payload["properties"]["nodes"]["items"]["properties"]["type"]["enum"])
        domain_types = {node_type.value for node_type in NodeType}
        assert schema_types == domain_types


class TestInspectionSerialization:
    def _inspection(self) -> ImportInspection:
        raw = b"Hello world.\n"
        return make_inspection(
            raw=raw,
            identity=derive_identity("sample.txt", raw),
            lane="source",
            parser_name="text",
            parser_version="1",
            policy=ImportPolicy(lane="source"),
            findings=(),
            coverage=CoverageSummary(
                adapter="text",
                supported_structures=("paragraph",),
                unsupported_structures=(),
                status="complete",
            ),
        )

    def test_content_opt_in(self) -> None:
        inspection = self._inspection()
        payload_without = inspection_to_payload(inspection)
        assert payload_without["document"] is None
        payload_with = inspection_to_payload(inspection, include_content=True)
        assert payload_with["document"] is None  # no document attached
        # Attach a document and verify opt-in behavior.
        document = _document()
        with_document = make_inspection(
            raw=b"Hello world.\n",
            identity=derive_identity("sample.txt", b"Hello world.\n"),
            lane="source",
            parser_name="text",
            parser_version="1",
            policy=ImportPolicy(lane="source"),
            findings=(),
            coverage=CoverageSummary(
                adapter="text",
                supported_structures=("paragraph",),
                unsupported_structures=(),
                status="complete",
            ),
            document=document,
        )
        assert inspection_to_payload(with_document)["document"] is None
        assert inspection_to_payload(with_document, include_content=True)["document"] is not None

    def test_round_trip_inspection(self) -> None:
        inspection = self._inspection()
        restored = inspection_from_json(inspection_to_json(inspection))
        assert restored.status is ImportStatus.OK
        assert restored.import_id == inspection.import_id
        assert restored.file_identity.extension == "txt"

    def test_rejects_invalid_inspection_json(self) -> None:
        with pytest.raises(DomainError, match="not valid JSON"):
            inspection_from_json("{not json")
        with pytest.raises(DomainError, match="top level"):
            inspection_from_json("[]")
        with pytest.raises(DomainError, match="schema"):
            inspection_from_json('{"schema": "other"}')

    def test_metadata_values_gated_by_include_content(self) -> None:
        from humanhand.domain.metadata_inventory import MetadataInventory, MetadataItem

        inspection = make_inspection(
            raw=b"x",
            identity=derive_identity("sample.md", b"x"),
            lane="source",
            parser_name="markdown",
            parser_version="1",
            policy=ImportPolicy(lane="source"),
            findings=(),
            coverage=CoverageSummary(
                adapter="markdown",
                supported_structures=("front_matter",),
                unsupported_structures=(),
                status="complete",
            ),
            metadata=MetadataInventory(
                items=(MetadataItem(key="title", kind="front_matter", value="Secret doc"),)
            ),
        )
        payload_gated = inspection_to_payload(inspection)
        items = payload_gated["metadata"]
        assert isinstance(items, dict)
        raw_items = items["items"]
        assert isinstance(raw_items, list)
        assert raw_items[0]["value"] is None
        payload_open = inspection_to_payload(inspection, include_content=True)
        open_items = payload_open["metadata"]
        assert isinstance(open_items, dict)
        open_raw_items = open_items["items"]
        assert isinstance(open_raw_items, list)
        assert open_raw_items[0]["value"] == "Secret doc"

    def test_unicode_inventory_rendered(self) -> None:
        from humanhand.domain.unicode_policy import NormalizationForm, UnicodeInventory

        inspection = make_inspection(
            raw=b"Hello",
            identity=derive_identity("sample.txt", b"Hello"),
            lane="source",
            parser_name="text",
            parser_version="1",
            policy=ImportPolicy(lane="source"),
            findings=(),
            coverage=CoverageSummary(
                adapter="text",
                supported_structures=("paragraph",),
                unsupported_structures=(),
                status="complete",
            ),
            unicode_inventory=UnicodeInventory(
                has_bom=True,
                bom_name="utf-8",
                normalization_form=NormalizationForm.NFC,
                control_char_offsets=(),
                surrogate_offsets=(),
                non_nfc_offsets=(),
                line_ending="lf",
                codepoint_count=5,
            ),
        )
        payload = inspection_to_payload(inspection)
        unicode_payload = payload["unicode"]
        assert unicode_payload is not None
        assert isinstance(unicode_payload, dict)
        assert unicode_payload["has_bom"] is True
        assert unicode_payload["bom_name"] == "utf-8"
