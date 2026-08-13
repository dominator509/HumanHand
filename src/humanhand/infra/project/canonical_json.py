"""Deterministic public-safe JSON projection of a source package.

Rendered for archiving and inspection. The payload contains ONLY
public-safe fields: package schema/id/status, document node structure
(positions/types/text; internal node ids omitted), claims
(proposition/modality/negation/status; claim ids omitted), and citations
(kind + text; citation ids and source locations omitted). Evidence refs,
protected-span ids, and private metadata are never included (SPEC-012:
public projections omit internal ids by default).

Claims are derived from ``humanhand.domain.claims_v2.build_claims_from_package``
(which returns ``(claims, coverage_status)``; the claims half is used).
If that module were absent, ``build_canonical_json_projection`` would fall
back to an empty claims tuple and render ``claims: []`` honestly; callers
may supply claims explicitly via the ``claims`` argument.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass

from humanhand.domain.document_serialization import dumps_stable
from humanhand.domain.source_package import SourcePackage
from humanhand.domain.types import DomainError

CANONICAL_JSON_PROJECTION_SCHEMA_VERSION = 1


def _string_or_empty(value: object) -> str:
    """Render a claim field as text, treating None as an empty string."""
    return "" if value is None else str(value)


def _enum_string(value: object) -> str:
    """Render an enum-like value as its string form; None becomes empty."""
    if value is None:
        return ""
    return str(getattr(value, "value", value))


def _claim_public_payload(claim: object) -> dict[str, object]:
    """Render one claim's public-safe fields (no claim id, no evidence refs).

    Reads the ClaimV2 attributes duck-typed: ``canonical_proposition``
    (with a ``proposition`` fallback for earlier interfaces), modality and
    status via their enum ``value``, negation as bool. Output keys follow
    the SPEC-012 public claim shape (proposition/modality/negation/status);
    claim ids and evidence refs are never included.
    """
    proposition = getattr(claim, "canonical_proposition", None)
    if proposition is None:
        proposition = getattr(claim, "proposition", None)
    return {
        "proposition": _string_or_empty(proposition),
        "modality": _enum_string(getattr(claim, "modality", None)),
        "negation": bool(getattr(claim, "negation", False)),
        "status": _enum_string(getattr(claim, "status", None)),
    }


def _derive_claims(package: SourcePackage) -> tuple[object, ...]:
    """Derive claims via ``build_claims_from_package`` when the module exists.

    Observed signature of ``humanhand.domain.claims_v2.build_claims_from_package``:
    it returns ``(claims, coverage_status)``; the claims half is used here.
    Honest fallback: while ``humanhand.domain.claims_v2`` is absent, return
    an empty tuple instead of failing; callers then render ``claims: []``.
    """
    try:
        module = importlib.import_module("humanhand.domain.claims_v2")
    except ImportError:
        return ()
    builder = module.build_claims_from_package
    claims, _coverage_status = builder(package)
    return tuple(claims)


@dataclass(frozen=True)
class CanonicalJsonProjection:
    """Deterministic JSON rendering of a source package for archiving.

    Contains ONLY public-safe fields: package schema/id/status, document
    node structure (ids omitted — positions/types/text only), claims
    (proposition, modality, negation, status — claim ids omitted),
    citations (kind + text only). Internal ids, evidence refs, and private
    metadata are NOT included (SPEC-012: public projections omit internal
    ids by default).
    """

    schema_version: int
    package_schema: str
    package_schema_version: int
    package_id: str
    package_status: str
    document_lane: str
    parser_name: str
    parser_version: str
    policy_version: str
    revision_policy: str
    document_nodes: tuple[tuple[int, str, str], ...]
    claims: tuple[dict[str, object], ...]
    citations: tuple[tuple[str, str], ...]

    def to_payload(self) -> dict[str, object]:
        """Render the projection as a plain JSON-ready mapping."""
        return {
            "schema": "canonical-json-projection",
            "schema_version": self.schema_version,
            "package": {
                "schema": self.package_schema,
                "schema_version": self.package_schema_version,
                "package_id": self.package_id,
                "status": self.package_status,
            },
            "document": {
                "lane": self.document_lane,
                "parser": {
                    "name": self.parser_name,
                    "version": self.parser_version,
                },
                "policy_version": self.policy_version,
                "revision_policy": self.revision_policy,
                "nodes": [
                    {
                        "position": position,
                        "type": node_type,
                        "text": text,
                    }
                    for position, node_type, text in self.document_nodes
                ],
            },
            "claims": [dict(claim) for claim in self.claims],
            "citations": [{"kind": kind, "text": text} for kind, text in self.citations],
        }

    def to_json(self) -> str:
        """Render as deterministic UTF-8 JSON with one trailing newline."""
        return dumps_stable(self.to_payload())


def build_canonical_json_projection(
    package: SourcePackage, claims: tuple[object, ...] | None = None
) -> CanonicalJsonProjection:
    """Build the public-safe JSON projection of a source package.

    When ``claims`` is None, claims are derived from
    ``humanhand.domain.claims_v2.build_claims_from_package`` when that
    module exists; otherwise the projection carries an empty claims tuple
    (documented honest fallback while the parallel module is absent).
    """
    if claims is None:
        claims = _derive_claims(package)
    raw_package = package.to_payload()
    schema_version = raw_package["schema_version"]
    if not isinstance(schema_version, int):
        raise DomainError("Source package payload has a non-integer schema_version")
    document = package.document
    return CanonicalJsonProjection(
        schema_version=CANONICAL_JSON_PROJECTION_SCHEMA_VERSION,
        package_schema=str(raw_package["schema"]),
        package_schema_version=schema_version,
        package_id=str(raw_package["package_id"]),
        package_status=str(raw_package["status"]),
        document_lane=document.lane,
        parser_name=document.parser_name,
        parser_version=document.parser_version,
        policy_version=document.policy_version,
        revision_policy=document.revision_policy,
        document_nodes=tuple(
            (node.position, node.node_type.value, node.text) for node in document.nodes
        ),
        claims=tuple(_claim_public_payload(claim) for claim in claims),
        citations=tuple((citation.kind, citation.text) for citation in package.evidence.citations),
    )
