"""PublicDocument — approved public content only (SPEC-013, blueprint 11).

A public document is the export boundary of the pipeline: it contains
approved title, section texts, proposition claims, and an optional created
note, and NOTHING else. It carries no project ids, block ids, claim ids,
model fields, prompts, API envelopes, private receipts, import metadata,
or internal metadata.

``document_id_public`` is a NEW public-only deterministic id: the sha256
digest (24 hex chars, prefixed ``pub-``) of the stable JSON payload of the
document WITHOUT its own id (``dumps_stable`` conventions). It is derived
from public content only and is never the internal document id.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from humanhand.domain.document_serialization import dumps_stable
from humanhand.domain.types import DomainError

PUBLIC_DOCUMENT_SCHEMA_VERSION = 1
_SCHEMA_NAME = "public-document"
_PUBLIC_ID_PREFIX = "pub-"
_PUBLIC_ID_HEX_LENGTH = 24
_HEX_DIGITS = frozenset("0123456789abcdef")


@dataclass(frozen=True)
class PublicDocument:
    """Approved public content only (blueprint 11).

    Contains NO project ids, block ids, model fields, prompts, API
    envelopes, private receipts, or internal metadata.
    """

    schema_version: int
    document_id_public: str  # "pub-" + sha256(content)[:24]; never the internal id
    title: str
    sections: tuple[str, ...]  # exact section texts in order
    claims: tuple[str, ...]  # proposition strings only (no claim ids, no evidence refs)
    created_note: str


def _content_payload(
    *,
    title: str,
    sections: tuple[str, ...],
    claims: tuple[str, ...],
    created_note: str,
) -> dict[str, object]:
    """The stable payload the public id is derived from (id excluded)."""
    return {
        "schema": _SCHEMA_NAME,
        "schema_version": PUBLIC_DOCUMENT_SCHEMA_VERSION,
        "title": title,
        "sections": list(sections),
        "claims": list(claims),
        "created_note": created_note,
    }


def _derive_public_id(
    *,
    title: str,
    sections: tuple[str, ...],
    claims: tuple[str, ...],
    created_note: str,
) -> str:
    """Derive the public id: sha256 of the stable content payload, 24 hex chars."""
    digest = hashlib.sha256(
        dumps_stable(
            _content_payload(
                title=title, sections=sections, claims=claims, created_note=created_note
            )
        ).encode("utf-8")
    )
    return f"{_PUBLIC_ID_PREFIX}{digest.hexdigest()[:_PUBLIC_ID_HEX_LENGTH]}"


def build_public_document(
    *,
    title: str,
    sections: tuple[str, ...],
    claims: tuple[str, ...],
    created_note: str = "",
) -> PublicDocument:
    """Build a public document with its content-derived public id."""
    return PublicDocument(
        schema_version=PUBLIC_DOCUMENT_SCHEMA_VERSION,
        document_id_public=_derive_public_id(
            title=title, sections=sections, claims=claims, created_note=created_note
        ),
        title=title,
        sections=tuple(sections),
        claims=tuple(claims),
        created_note=created_note,
    )


def public_document_to_payload(doc: PublicDocument) -> dict[str, object]:
    """Render a public document as a stable JSON-ready payload."""
    payload = _content_payload(
        title=doc.title, sections=doc.sections, claims=doc.claims, created_note=doc.created_note
    )
    payload["document_id_public"] = doc.document_id_public
    return payload


def _expect_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise DomainError(f"Invalid public document payload: {key} must be a string")
    return value


def _expect_str_tuple(payload: dict[str, object], key: str) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise DomainError(f"Invalid public document payload: {key} must be a list of strings")
    return tuple(value)


def _validate_public_id(value: str) -> None:
    if not value.startswith(_PUBLIC_ID_PREFIX):
        raise DomainError(
            "Invalid public document payload: document_id_public must start with 'pub-'"
        )
    hex_part = value[len(_PUBLIC_ID_PREFIX) :]
    if len(hex_part) != _PUBLIC_ID_HEX_LENGTH or any(char not in _HEX_DIGITS for char in hex_part):
        raise DomainError(
            "Invalid public document payload: document_id_public must be 'pub-' plus 24 hex chars"
        )


def public_document_from_payload(payload: dict[str, object]) -> PublicDocument:
    """Deserialize and validate a public document payload (strict, fails closed).

    The public id is re-derived from the payload content and any mismatch
    raises DomainError — the id is an integrity anchor and a tampered
    document fails closed.
    """
    if payload.get("schema") != _SCHEMA_NAME:
        raise DomainError("Invalid public document payload: schema must be 'public-document'")
    if payload.get("schema_version") != PUBLIC_DOCUMENT_SCHEMA_VERSION:
        raise DomainError("Unsupported public document payload schema version")
    document_id_public = _expect_str(payload, "document_id_public")
    _validate_public_id(document_id_public)
    title = _expect_str(payload, "title")
    sections = _expect_str_tuple(payload, "sections")
    claims = _expect_str_tuple(payload, "claims")
    created_note = _expect_str(payload, "created_note")
    rebuilt = build_public_document(
        title=title, sections=sections, claims=claims, created_note=created_note
    )
    if rebuilt.document_id_public != document_id_public:
        raise DomainError(
            "Invalid public document payload: document_id_public does not match the content"
        )
    return rebuilt


def public_document_to_json(doc: PublicDocument) -> str:
    """Serialize a public document deterministically.

    Equal inputs always produce byte-identical output, including key order.
    """
    return dumps_stable(public_document_to_payload(doc))
