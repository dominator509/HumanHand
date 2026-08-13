"""Integration tests for the public-safe canonical JSON projection."""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from humanhand.domain.canonical_document import (
    CoverageSummary,
    build_document,
    make_inspection,
)
from humanhand.domain.document_nodes import NodeBuilder, NodeType
from humanhand.domain.file_identity import derive_identity
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.source_package import LANE_SOURCE, SourcePackage, build_source_package
from humanhand.infra.project.canonical_json import build_canonical_json_projection


def _source_package(text: str = "In 2024 we shipped 300 units.") -> SourcePackage:
    """Build a real SourcePackage; mirrors the unit-test _inspection helper."""
    root = NodeBuilder(node_type=NodeType.DOCUMENT)
    root.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text=text))
    document = build_document(
        root=root,
        lane=LANE_SOURCE,
        parser_name="text",
        parser_version="1",
        policy=ImportPolicy(lane=LANE_SOURCE),
        surface_text=text,
    )
    raw = text.encode("utf-8")
    inspection = make_inspection(
        raw=raw,
        identity=derive_identity("sample.txt", raw),
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
        document=document,
    )
    return build_source_package(inspection)


def _all_key_names(value: object) -> set[str]:
    """Collect every dict key name anywhere in a JSON-ready structure."""
    names: set[str] = set()
    if isinstance(value, dict):
        names.update(value.keys())
        for child in value.values():
            names.update(_all_key_names(child))
    elif isinstance(value, list):
        for child in value:
            names.update(_all_key_names(child))
    return names


_FORBIDDEN_KEYS = {
    "id",
    "node_id",
    "parent_id",
    "span_id",
    "claim_id",
    "entity_id",
    "citation_id",
    "import_id",
}


class TestCanonicalJsonProjection:
    def test_payload_omits_internal_ids(self) -> None:
        payload = build_canonical_json_projection(_source_package()).to_payload()
        names = _all_key_names(payload)
        # Observed: no key is named like an internal id; the only
        # id-shaped key is "package_id" (contract: package schema/id/status
        # are included).
        assert names.isdisjoint(_FORBIDDEN_KEYS)
        assert "package_id" in names

    def test_rendering_is_byte_identical(self) -> None:
        first = build_canonical_json_projection(_source_package())
        second = build_canonical_json_projection(_source_package())
        # Observed: equal packages render byte-identical JSON (sort_keys),
        # and re-rendering one projection is byte-identical too.
        assert first.to_json() == second.to_json()
        assert first.to_json() == first.to_json()
        assert json.loads(first.to_json()) == first.to_payload()

    def test_node_entries_are_position_type_text_only(self) -> None:
        payload = build_canonical_json_projection(_source_package()).to_payload()
        document = payload["document"]
        assert isinstance(document, dict)
        nodes = document["nodes"]
        assert isinstance(nodes, list)
        assert nodes  # a document root plus one paragraph
        for node in nodes:
            assert isinstance(node, dict)
            # Observed: ids are omitted; only position/type/text remain.
            assert set(node.keys()) == {"position", "type", "text"}

    def test_claims_are_derived_when_claims_module_present(self) -> None:
        # Observed on this snapshot: humanhand.domain.claims_v2 exists, so
        # claims are derived for real. The text parser yields one protected
        # NUMBER span "300 units", which becomes one asserted, non-negated,
        # proposed claim (no claim id rendered).
        payload = build_canonical_json_projection(_source_package()).to_payload()
        assert payload["claims"] == [
            {
                "proposition": "300 units",
                "modality": "asserted",
                "negation": False,
                "status": "proposed",
            }
        ]

    def test_claims_fall_back_to_empty_when_module_import_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Honest fallback path: if humanhand.domain.claims_v2 could not be
        # imported, the projection renders claims: [] instead of failing.
        def _raise_import_error(name: str) -> object:
            raise ImportError(name)

        monkeypatch.setattr("importlib.import_module", _raise_import_error)
        payload = build_canonical_json_projection(_source_package()).to_payload()
        assert payload["claims"] == []

    def test_explicit_claims_render_public_fields_only(self) -> None:
        # Stand-in object exposing the ClaimV2 attribute names; the real
        # module has not landed in this snapshot, so the projection is
        # exercised duck-typed, exactly as it will receive ClaimV2.
        @dataclass(frozen=True)
        class _ClaimStandIn:
            proposition: str
            modality: str
            negation: bool
            status: str

        claim = _ClaimStandIn(
            proposition="The sky is blue",
            modality="assertive",
            negation=False,
            status="accepted",
        )
        payload = build_canonical_json_projection(_source_package(), claims=(claim,)).to_payload()
        # Observed: only the four public fields render; no claim id.
        assert payload["claims"] == [
            {
                "proposition": "The sky is blue",
                "modality": "assertive",
                "negation": False,
                "status": "accepted",
            }
        ]

    def test_citations_render_kind_and_text_only(self) -> None:
        payload = build_canonical_json_projection(
            _source_package(text="On 2024-05-01 we shipped 300 units [12].")
        ).to_payload()
        # Observed: the bracket_number citation renders kind + text; the
        # internal citation id "c1" is omitted.
        assert payload["citations"] == [{"kind": "bracket_number", "text": "[12]"}]
