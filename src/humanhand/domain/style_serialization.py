"""Deterministic serialization for style evidence packages."""

from __future__ import annotations

import json
from typing import Any

from humanhand.domain.document_nodes import SourceLocation
from humanhand.domain.document_serialization import dumps_stable
from humanhand.domain.style_artifacts import (
    STYLE_EVIDENCE_PACKAGE_SCHEMA_VERSION,
    OriginalStyleArtifact,
    StyleEvidencePackage,
    StyleExemplar,
)
from humanhand.domain.style_authorship import (
    AuthorshipClass,
    AuthorshipMap,
    AuthorshipSpan,
    ExcludedSpan,
)
from humanhand.domain.style_surface import (
    CanonicalSurfaceDocument,
    SurfaceStatistics,
)
from humanhand.domain.types import DomainError

_SCHEMA_NAME = "style-evidence-package"


def _location_payload(location: SourceLocation) -> dict[str, int]:
    return {
        "start_offset": location.start_offset,
        "end_offset": location.end_offset,
        "line_start": location.line_start,
        "line_end": location.line_end,
    }


def _expect(payload: dict[str, object], key: str, expected: type[Any], what: str) -> Any:
    value = payload.get(key)
    if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
        raise DomainError(f"Invalid style package JSON: {what} has wrong type")
    return value


def _location_from_payload(payload: dict[str, object], what: str) -> SourceLocation:
    """Build a strictly typed source location without coercing JSON values."""
    location = SourceLocation(
        start_offset=_expect(payload, "start_offset", int, f"{what}.start_offset"),
        end_offset=_expect(payload, "end_offset", int, f"{what}.end_offset"),
        line_start=_expect(payload, "line_start", int, f"{what}.line_start"),
        line_end=_expect(payload, "line_end", int, f"{what}.line_end"),
    )
    if (
        location.start_offset < 0
        or location.end_offset < location.start_offset
        or location.line_start < 1
        or location.line_end < location.line_start
    ):
        raise DomainError(f"Invalid style package JSON: {what} is out of range")
    return location


def package_to_payload(package: StyleEvidencePackage) -> dict[str, object]:
    """Render a style evidence package as its stable JSON payload."""
    spans = []
    for span in package.authorship.spans:
        spans.append(
            {
                "span_id": span.span_id,
                "source_location": _location_payload(span.source_location),
                "text": span.text,
                "authorship_class": span.authorship_class.value,
                "review_status": span.review_status,
                "decided_by": span.decided_by,
            }
        )
    excluded = []
    for excluded_span in package.authorship.excluded:
        excluded.append(
            {
                "span_id": excluded_span.span_id,
                "source_location": _location_payload(excluded_span.source_location),
                "reason": excluded_span.reason,
            }
        )
    return {
        "schema": _SCHEMA_NAME,
        "schema_version": package.schema_version,
        "package_id": package.package_id,
        "profile_label": package.profile_label,
        "original_artifact": {
            "artifact_id": package.original_artifact.artifact_id,
            "sha256": package.original_artifact.sha256,
            "size_bytes": package.original_artifact.size_bytes,
            "stored": package.original_artifact.stored,
        },
        "exact_surface": {
            "artifact_id": package.exact_surface.artifact_id,
            "surface_text": package.exact_surface.surface_text,
            "sha256": package.exact_surface.sha256,
            "statistics": {
                "code_points": package.exact_surface.statistics.code_points,
                "bytes_utf8": package.exact_surface.statistics.bytes_utf8,
                "lines": package.exact_surface.statistics.lines,
                "paragraphs": package.exact_surface.statistics.paragraphs,
                "headings": package.exact_surface.statistics.headings,
                "list_items": package.exact_surface.statistics.list_items,
                "table_cells": package.exact_surface.statistics.table_cells,
                "quotations": package.exact_surface.statistics.quotations,
                "code_blocks": package.exact_surface.statistics.code_blocks,
                "hyperlinks": package.exact_surface.statistics.hyperlinks,
            },
            "node_count": package.exact_surface.node_count,
        },
        "authorship": {"spans": spans, "excluded": excluded},
        "unsupported_features": list(package.unsupported_features),
        "approved_exemplars": [
            {
                "exemplar_id": item.exemplar_id,
                "text": item.text,
                "span_id": item.span_id,
                "note": item.note,
            }
            for item in package.approved_exemplars
        ],
        "parser_version": package.parser_version,
        "ruleset_version": package.ruleset_version,
    }


def package_to_json(package: StyleEvidencePackage) -> str:
    return dumps_stable(package_to_payload(package))


def package_from_json(text: str) -> StyleEvidencePackage:
    """Deserialize and validate a style evidence package JSON string."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DomainError("Invalid style package JSON: not valid JSON") from exc
    if not isinstance(payload, dict):
        raise DomainError("Invalid style package JSON: top level must be an object")
    if payload.get("schema") != _SCHEMA_NAME:
        raise DomainError("Invalid style package JSON: schema mismatch")
    if payload.get("schema_version") != STYLE_EVIDENCE_PACKAGE_SCHEMA_VERSION:
        raise DomainError("Unsupported style package schema version")

    original_payload = _expect(payload, "original_artifact", dict, "original_artifact")
    surface_payload = _expect(payload, "exact_surface", dict, "exact_surface")
    stats_payload = _expect(surface_payload, "statistics", dict, "statistics")
    authorship_payload = _expect(payload, "authorship", dict, "authorship")

    spans: list[AuthorshipSpan] = []
    raw_spans = authorship_payload.get("spans") or []
    if not isinstance(raw_spans, list):
        raise DomainError("Invalid style package JSON: spans must be a list")
    for index, raw in enumerate(raw_spans, start=1):
        if not isinstance(raw, dict):
            raise DomainError("Invalid style package JSON: span must be an object")
        location_payload = _expect(raw, "source_location", dict, "source_location")
        try:
            authorship_class = AuthorshipClass(
                _expect(raw, "authorship_class", str, "authorship_class")
            )
        except ValueError as exc:
            raise DomainError("Invalid style package JSON: unknown authorship class") from exc
        review_status = _expect(raw, "review_status", str, f"spans[{index}].review_status")
        if review_status not in {"unresolved", "resolved"}:
            raise DomainError("Invalid style package JSON: unknown review status")
        if authorship_class is AuthorshipClass.UNKNOWN and review_status == "resolved":
            raise DomainError("Invalid style package JSON: unknown authorship cannot be resolved")
        spans.append(
            AuthorshipSpan(
                span_id=_expect(raw, "span_id", str, f"spans[{index}].span_id"),
                source_location=_location_from_payload(
                    location_payload, f"spans[{index}].source_location"
                ),
                text=_expect(raw, "text", str, f"spans[{index}].text"),
                authorship_class=authorship_class,
                review_status=review_status,
                decided_by=_expect(raw, "decided_by", str, f"spans[{index}].decided_by"),
            )
        )

    excluded: list[ExcludedSpan] = []
    raw_excluded = authorship_payload.get("excluded") or []
    if not isinstance(raw_excluded, list):
        raise DomainError("Invalid style package JSON: excluded must be a list")
    for raw in raw_excluded:
        if not isinstance(raw, dict):
            raise DomainError("Invalid style package JSON: excluded span must be an object")
        location_payload = _expect(raw, "source_location", dict, "source_location")
        excluded.append(
            ExcludedSpan(
                span_id=_expect(raw, "span_id", str, "excluded.span_id"),
                source_location=_location_from_payload(
                    location_payload, "excluded.source_location"
                ),
                reason=_expect(raw, "reason", str, "excluded.reason"),
            )
        )

    exemplars: list[StyleExemplar] = []
    raw_exemplars = payload.get("approved_exemplars") or []
    if not isinstance(raw_exemplars, list):
        raise DomainError("Invalid style package JSON: exemplars must be a list")
    for raw in raw_exemplars:
        if not isinstance(raw, dict):
            raise DomainError("Invalid style package JSON: exemplar must be an object")
        exemplars.append(
            StyleExemplar(
                exemplar_id=_expect(raw, "exemplar_id", str, "exemplar.exemplar_id"),
                text=_expect(raw, "text", str, "exemplar.text"),
                span_id=_expect(raw, "span_id", str, "exemplar.span_id"),
                note=_expect(raw, "note", str, "exemplar.note"),
            )
        )

    stored = original_payload.get("stored", False)
    if not isinstance(stored, bool):
        raise DomainError("Invalid style package JSON: stored has wrong type")
    raw_unsupported = payload.get("unsupported_features", [])
    if not isinstance(raw_unsupported, list) or not all(
        isinstance(item, str) for item in raw_unsupported
    ):
        raise DomainError("Invalid style package JSON: unsupported_features must be strings")

    return StyleEvidencePackage(
        schema_version=STYLE_EVIDENCE_PACKAGE_SCHEMA_VERSION,
        package_id=_expect(payload, "package_id", str, "package_id"),
        profile_label=_expect(payload, "profile_label", str, "profile_label"),
        original_artifact=OriginalStyleArtifact(
            artifact_id=_expect(original_payload, "artifact_id", str, "artifact_id"),
            sha256=_expect(original_payload, "sha256", str, "sha256"),
            size_bytes=_expect(original_payload, "size_bytes", int, "size_bytes"),
            stored=stored,
        ),
        exact_surface=CanonicalSurfaceDocument(
            artifact_id=_expect(surface_payload, "artifact_id", str, "surface.artifact_id"),
            surface_text=_expect(surface_payload, "surface_text", str, "surface_text"),
            sha256=_expect(surface_payload, "sha256", str, "surface.sha256"),
            statistics=SurfaceStatistics(
                code_points=_expect(stats_payload, "code_points", int, "code_points"),
                bytes_utf8=_expect(stats_payload, "bytes_utf8", int, "bytes_utf8"),
                lines=_expect(stats_payload, "lines", int, "lines"),
                paragraphs=_expect(stats_payload, "paragraphs", int, "paragraphs"),
                headings=_expect(stats_payload, "headings", int, "headings"),
                list_items=_expect(stats_payload, "list_items", int, "list_items"),
                table_cells=_expect(stats_payload, "table_cells", int, "table_cells"),
                quotations=_expect(stats_payload, "quotations", int, "quotations"),
                code_blocks=_expect(stats_payload, "code_blocks", int, "code_blocks"),
                hyperlinks=_expect(stats_payload, "hyperlinks", int, "hyperlinks"),
            ),
            node_count=_expect(surface_payload, "node_count", int, "node_count"),
        ),
        authorship=AuthorshipMap(spans=tuple(spans), excluded=tuple(excluded)),
        approved_exemplars=tuple(exemplars),
        unsupported_features=tuple(raw_unsupported),
        parser_version=_expect(payload, "parser_version", str, "parser_version"),
        ruleset_version=_expect(payload, "ruleset_version", str, "ruleset_version"),
    )
