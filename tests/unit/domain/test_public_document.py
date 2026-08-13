"""Unit tests for the public document boundary."""

from __future__ import annotations

import pytest

from humanhand.domain.public_document import (
    PublicDocument,
    build_public_document,
    public_document_from_payload,
    public_document_to_json,
    public_document_to_payload,
)
from humanhand.domain.types import DomainError


def _sample_doc() -> PublicDocument:
    return build_public_document(
        title="Quarterly report",
        sections=("Executive summary", "Detailed findings"),
        claims=("Revenue grew 12%.", "Two new sites opened."),
        created_note="Approved 2026-08-01",
    )


def _collect_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(str(key))
            keys.update(_collect_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(_collect_keys(item))
    return keys


class TestPublicId:
    def test_id_format(self) -> None:
        doc = _sample_doc()
        assert doc.document_id_public.startswith("pub-")
        assert len(doc.document_id_public) == 4 + 24

    def test_id_is_deterministic(self) -> None:
        assert _sample_doc().document_id_public == _sample_doc().document_id_public

    def test_id_changes_with_content(self) -> None:
        other = build_public_document(
            title="Quarterly report",
            sections=("Executive summary",),
            claims=("Revenue grew 12%.",),
        )
        assert other.document_id_public != _sample_doc().document_id_public

    def test_id_is_public_only_shape(self) -> None:
        doc = _sample_doc()
        assert "proj-" not in doc.document_id_public
        assert "rev-" not in doc.document_id_public


class TestPayload:
    def test_round_trip(self) -> None:
        doc = _sample_doc()
        assert public_document_from_payload(public_document_to_payload(doc)) == doc

    def test_no_internal_keys_anywhere(self) -> None:
        doc = _sample_doc()
        payload = public_document_to_payload(doc)
        forbidden = ("project_id", "claim_id", "block_id")
        assert _collect_keys(payload).isdisjoint(forbidden)

    def test_payload_shape(self) -> None:
        payload = public_document_to_payload(_sample_doc())
        assert payload["schema"] == "public-document"
        assert payload["schema_version"] == 1
        assert payload["sections"] == ["Executive summary", "Detailed findings"]
        assert payload["claims"] == ["Revenue grew 12%.", "Two new sites opened."]

    def test_byte_identical_json_twice(self) -> None:
        doc = _sample_doc()
        assert public_document_to_json(doc) == public_document_to_json(doc)

    def test_json_has_exactly_one_trailing_newline(self) -> None:
        text = public_document_to_json(_sample_doc())
        assert text.endswith("\n")
        assert not text.endswith("\n\n")

    def test_rejects_tampered_id(self) -> None:
        payload = public_document_to_payload(_sample_doc())
        bad: dict[str, object] = dict(payload)
        bad["document_id_public"] = "pub-" + "0" * 24
        with pytest.raises(DomainError, match="document_id_public"):
            public_document_from_payload(bad)

    def test_rejects_bad_id_format(self) -> None:
        payload = public_document_to_payload(_sample_doc())
        bad: dict[str, object] = dict(payload)
        bad["document_id_public"] = "internal-id-123"
        with pytest.raises(DomainError, match="document_id_public"):
            public_document_from_payload(bad)

    def test_rejects_non_list_sections(self) -> None:
        payload = public_document_to_payload(_sample_doc())
        bad: dict[str, object] = dict(payload)
        bad["sections"] = "not a list"
        with pytest.raises(DomainError, match="sections"):
            public_document_from_payload(bad)
