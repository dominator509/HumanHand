"""Project state — the deterministic project brain (SPEC-012, blueprint 9.3).

A project is identified by the sha256 digest of its name and absolute root
path: ``project_id = "proj-" + sha256(f"{name}\\x00{root}")[:24]``. The
digest is a pure function of ``(name, root)``, so equal inputs always
produce the same id. Coverage starts as UNKNOWN_COVERAGE (the honest
default: an empty project has no established claim coverage) and is never
guessed by this module.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace

from humanhand.domain.claims_v2 import CoverageStatus
from humanhand.domain.types import DomainError

PROJECT_SCHEMA_VERSION = 1
_SCHEMA_NAME = "project"


@dataclass(frozen=True)
class ProjectState:
    """Immutable state of one project."""

    project_id: str  # "proj-" + sha256(f"{name}\x00{root}")[:24], deterministic
    name: str
    root: str  # absolute path string of the project root
    schema_version: int
    document_ids: tuple[str, ...]
    coverage_status: CoverageStatus  # from claims_v2; never guessed
    style_profile_label: str


def _derive_project_id(*, name: str, root: str) -> str:
    """Deterministic project id: sha256 over NUL-framed name and root."""
    digest = hashlib.sha256()
    digest.update(name.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(root.encode("utf-8"))
    return f"proj-{digest.hexdigest()[:24]}"


def new_project_state(*, name: str, root: str, schema_version: int = 1) -> ProjectState:
    """Create an empty project state (no documents, unknown coverage).

    ``project_id`` is derived deterministically from ``name`` and
    ``root``. The schema version must be the supported one; an unknown
    version fails closed instead of creating a state that could never
    round-trip.
    """
    if schema_version != PROJECT_SCHEMA_VERSION:
        raise DomainError(f"Unsupported project schema version: {schema_version}")
    return ProjectState(
        project_id=_derive_project_id(name=name, root=root),
        name=name,
        root=root,
        schema_version=PROJECT_SCHEMA_VERSION,
        document_ids=(),
        coverage_status=CoverageStatus.UNKNOWN_COVERAGE,
        style_profile_label="",
    )


def with_document(state: ProjectState, document_id: str) -> ProjectState:
    """Return a state with ``document_id`` appended once, in order.

    Adding an id that is already present is a no-op, so repeated calls
    never duplicate ids.
    """
    if document_id in state.document_ids:
        return state
    return replace(state, document_ids=state.document_ids + (document_id,))


def project_to_payload(state: ProjectState) -> dict[str, object]:
    """Render the project state as a stable JSON-ready payload."""
    return {
        "schema": _SCHEMA_NAME,
        "schema_version": state.schema_version,
        "project_id": state.project_id,
        "name": state.name,
        "root": state.root,
        "document_ids": list(state.document_ids),
        "coverage_status": state.coverage_status.value,
        "style_profile_label": state.style_profile_label,
    }


def _expect_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise DomainError(f"Invalid project payload: {key} must be a string")
    return value


def project_from_payload(payload: dict[str, object]) -> ProjectState:
    """Deserialize and validate a project payload (strict, fails closed).

    The project id is parsed from the payload as given; it is not
    re-derived here because the digest contract belongs to
    :func:`new_project_state` (the capsule module re-derives and verifies
    its own id the same way).
    """
    if payload.get("schema") != _SCHEMA_NAME:
        raise DomainError("Invalid project payload: schema must be 'project'")
    if payload.get("schema_version") != PROJECT_SCHEMA_VERSION:
        raise DomainError("Unsupported project payload schema version")
    project_id = _expect_str(payload, "project_id")
    name = _expect_str(payload, "name")
    root = _expect_str(payload, "root")
    raw_document_ids = payload.get("document_ids")
    if not isinstance(raw_document_ids, list):
        raise DomainError("Invalid project payload: document_ids must be a list")
    if not all(isinstance(item, str) for item in raw_document_ids):
        raise DomainError("Invalid project payload: document_ids must contain only strings")
    raw_coverage = _expect_str(payload, "coverage_status")
    try:
        coverage_status = CoverageStatus(raw_coverage)
    except ValueError as exc:
        raise DomainError(
            f"Invalid project payload: unknown coverage_status {raw_coverage!r}"
        ) from exc
    return ProjectState(
        project_id=project_id,
        name=name,
        root=root,
        schema_version=PROJECT_SCHEMA_VERSION,
        document_ids=tuple(raw_document_ids),
        coverage_status=coverage_status,
        style_profile_label=_expect_str(payload, "style_profile_label"),
    )
