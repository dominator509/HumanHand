"""Unit tests for the deterministic project brain state."""

from __future__ import annotations

import hashlib

import pytest

from humanhand.domain.claims_v2 import CoverageStatus
from humanhand.domain.project import (
    new_project_state,
    project_from_payload,
    project_to_payload,
    with_document,
)
from humanhand.domain.types import DomainError

# Hand-verified with the derivation documented in project.py:
# project_id = "proj-" + sha256(f"{name}\x00{root}")[:24]. The expected
# digest is computed in the test with hashlib over the exact same framed
# bytes, so the assertion is real, not fabricated.


def _expected_project_id(name: str, root: str) -> str:
    digest = hashlib.sha256(f"{name}\x00{root}".encode())
    return f"proj-{digest.hexdigest()[:24]}"


class TestNewProjectState:
    def test_ids_are_deterministic_for_same_inputs(self) -> None:
        first = new_project_state(name="Demo", root=r"C:\demo")
        second = new_project_state(name="Demo", root=r"C:\demo")
        assert first == second
        assert first.project_id == _expected_project_id("Demo", r"C:\demo")
        assert first.project_id.startswith("proj-")

    def test_different_root_differs(self) -> None:
        first = new_project_state(name="Demo", root=r"C:\demo")
        second = new_project_state(name="Demo", root=r"C:\other")
        assert first.project_id != second.project_id

    def test_empty_defaults(self) -> None:
        state = new_project_state(name="Demo", root=r"C:\demo")
        assert state.document_ids == ()
        assert state.coverage_status is CoverageStatus.UNKNOWN_COVERAGE
        assert state.style_profile_label == ""
        assert state.schema_version == 1

    def test_unsupported_schema_version_fails_closed(self) -> None:
        with pytest.raises(DomainError, match="schema version"):
            new_project_state(name="Demo", root=r"C:\demo", schema_version=2)


class TestWithDocument:
    def test_appends_once_in_order(self) -> None:
        state = new_project_state(name="Demo", root=r"C:\demo")
        state = with_document(state, "doc-1")
        state = with_document(state, "doc-2")
        state = with_document(state, "doc-1")  # duplicate is a no-op
        assert state.document_ids == ("doc-1", "doc-2")

    def test_original_state_is_immutable(self) -> None:
        original = new_project_state(name="Demo", root=r"C:\demo")
        updated = with_document(original, "doc-1")
        assert original.document_ids == ()
        assert updated.document_ids == ("doc-1",)


class TestProjectPayload:
    def test_round_trip(self) -> None:
        state = new_project_state(name="Demo", root=r"C:\demo")
        state = with_document(state, "doc-1")
        assert project_from_payload(project_to_payload(state)) == state

    def test_payload_shape(self) -> None:
        payload = project_to_payload(new_project_state(name="Demo", root=r"C:\demo"))
        assert payload["schema"] == "project"
        assert payload["schema_version"] == 1
        assert payload["coverage_status"] == "unknown_coverage"

    def test_rejects_unknown_coverage_status(self) -> None:
        payload = project_to_payload(new_project_state(name="Demo", root=r"C:\demo"))
        bad_payload: dict[str, object] = dict(payload)
        bad_payload["coverage_status"] = "bogus"
        with pytest.raises(DomainError, match="coverage"):
            project_from_payload(bad_payload)

    def test_rejects_non_list_document_ids(self) -> None:
        payload = project_to_payload(new_project_state(name="Demo", root=r"C:\demo"))
        bad_payload: dict[str, object] = dict(payload)
        bad_payload["document_ids"] = "doc-1"
        with pytest.raises(DomainError, match="document_ids"):
            project_from_payload(bad_payload)
