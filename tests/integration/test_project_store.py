"""Integration tests for the SQLite project store (EP-015, ADR-001).

The store is exercised with the real domain types (``ClaimV2``, ``Entity``,
``ProtectedSpan``, ``DocumentRevision``). The ``humanhand.domain.project``
module is a parallel-agent contract that may not be present yet; the project
round-trip class is skip-gated until it is.
"""

from __future__ import annotations

import hashlib
import importlib
import os
import sqlite3
import stat
import tomllib
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from humanhand.domain.claims_v2 import ClaimStatus, ClaimV2, Modality
from humanhand.domain.document_nodes import SourceLocation
from humanhand.domain.entities import Entity, EntityType
from humanhand.domain.protected_spans import ProtectedSpan, SpanKind
from humanhand.domain.relationships import Relationship
from humanhand.domain.revisions import (
    RevisionConflictError,
    accept_revision,
    create_initial_revision,
    propose_next_revision,
    revision_to_payload,
)
from humanhand.domain.structure_signature import StructureSignature
from humanhand.infra.stores.migration_runner import current_version
from humanhand.infra.stores.project_layout import init_layout, layout_for, read_project_toml
from humanhand.infra.stores.project_store import ProjectStore, ProjectStoreError
from humanhand.infra.stores.test_key_provider import TestKeyProvider


def _load_optional_module(module_name: str) -> ModuleType | None:
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


_project_domain = _load_optional_module("humanhand.domain.project")

_requires_project_domain = pytest.mark.skipif(
    _project_domain is None, reason="humanhand.domain.project not available"
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _signature(text: str) -> StructureSignature:
    return StructureSignature(
        signature=_sha(text),
        section_order=("Methods",),
        node_type_counts={"paragraph": 2, "sentence": 4},
        total_nodes=6,
    )


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    init_layout(tmp_path, name="test-project")
    return tmp_path


class TestProjectLayout:
    def test_layout_paths(self, project_root: Path) -> None:
        layout = layout_for(project_root)
        assert layout.humanhand_dir == project_root / ".humanhand"
        assert layout.project_toml == project_root / ".humanhand" / "project.toml"
        assert layout.database == project_root / ".humanhand" / "project.db"
        assert layout.blobs_dir == project_root / ".humanhand" / "blobs"
        assert layout.reports_dir == project_root / ".humanhand" / "reports"
        assert layout.exports_dir == project_root / ".humanhand" / "exports"
        assert layout.source_dir == project_root / "source"
        assert layout.style_dir == project_root / "style"
        assert layout.working_dir == project_root / "working"

    def test_init_layout_idempotent(self, tmp_path: Path) -> None:
        first = init_layout(tmp_path, name="first")
        second = init_layout(tmp_path, name="second")
        assert first == second
        assert first.project_toml.read_text(encoding="utf-8") == (
            '[humanhand]\nname = "first"\nschema_version = 1\n'
        )

    def test_init_layout_never_overwrites_toml(self, tmp_path: Path) -> None:
        init_layout(tmp_path, name="original")
        init_layout(tmp_path, name="second")
        meta = read_project_toml(tmp_path)
        assert meta["name"] == "original"
        assert meta["schema_version"] == "1"

    def test_init_layout_rejects_file_root(self, tmp_path: Path) -> None:
        file_root = tmp_path / "not-a-directory"
        file_root.write_text("x", encoding="utf-8")
        with pytest.raises(FileExistsError):
            init_layout(file_root, name="test")

    def test_read_project_toml_missing_returns_empty(self, tmp_path: Path) -> None:
        assert read_project_toml(tmp_path / "absent") == {}

    def test_read_project_toml_corrupt_raises(self, tmp_path: Path) -> None:
        init_layout(tmp_path, name="test")
        layout_for(tmp_path).project_toml.write_text("not [valid toml", encoding="utf-8")
        with pytest.raises(tomllib.TOMLDecodeError):
            read_project_toml(tmp_path)

    def test_no_files_outside_layout(self, project_root: Path) -> None:
        ProjectStore(project_root).close()
        assert {entry.name for entry in project_root.iterdir()} == {
            ".humanhand",
            "source",
            "style",
            "working",
        }
        assert {entry.name for entry in (project_root / ".humanhand").iterdir()} == {
            "blobs",
            "exports",
            "project.db",
            "project.db.bak",
            "project.toml",
            "reports",
        }


class TestProjectStoreBasics:
    def test_open_creates_layout_and_applies_schema(self, tmp_path: Path) -> None:
        store = ProjectStore(tmp_path)
        assert store.schema_version == 2
        store.close()
        db = tmp_path / ".humanhand" / "project.db"
        assert db.is_file()
        assert db.with_name("project.db.bak").is_file()
        conn = sqlite3.connect(str(db))
        try:
            assert current_version(conn) == 2
            tables = {
                str(row[0])
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            assert tables == {
                "schema_migrations",
                "projects",
                "documents",
                "document_revisions",
                "protected_spans",
                "claims",
                "entities",
                "relationships",
                "approvals",
            }
        finally:
            conn.close()

    def test_reopen_is_noop(self, tmp_path: Path) -> None:
        ProjectStore(tmp_path).close()
        backup = tmp_path / ".humanhand" / "project.db.bak"
        assert backup.is_file()
        backup_bytes = backup.read_bytes()
        ProjectStore(tmp_path).close()
        assert backup.read_bytes() == backup_bytes

    def test_add_document(self, tmp_path: Path) -> None:
        project = _project_domain
        assert project is not None
        store = ProjectStore(tmp_path)
        state = project.new_project_state(name="test-project", root=str(tmp_path))
        store.create_project(state)
        store.add_document("doc-1", state.project_id, purpose="rewrite")
        store.close()
        conn = sqlite3.connect(str(tmp_path / ".humanhand" / "project.db"))
        try:
            row = conn.execute("SELECT document_id, project_id, purpose FROM documents").fetchone()
            assert row == ("doc-1", state.project_id, "rewrite")
        finally:
            conn.close()

    def test_add_document_requires_existing_project(self, tmp_path: Path) -> None:
        store = ProjectStore(tmp_path)
        with pytest.raises(ProjectStoreError, match="Document add error"):
            store.add_document("doc-1", "no-such-project")
        store.close()

    def test_operations_after_close_raise(self, tmp_path: Path) -> None:
        store = ProjectStore(tmp_path)
        store.close()
        with pytest.raises(ProjectStoreError, match="closed"):
            store.add_document("doc-1", "proj-1")
        with pytest.raises(ProjectStoreError, match="closed"):
            store.list_approvals()
        store.close()  # idempotent


@_requires_project_domain
class TestProjectRoundTrip:
    def test_create_and_load_project(self, project_root: Path) -> None:
        project = _project_domain
        assert project is not None
        state = project.new_project_state(name="test-project", root=str(project_root))
        store = ProjectStore(project_root)
        store.create_project(state)
        loaded = store.load_project(state.project_id)
        store.close()
        assert project.project_to_payload(loaded) == project.project_to_payload(state)

    def test_load_missing_project_raises(self, project_root: Path) -> None:
        store = ProjectStore(project_root)
        with pytest.raises(ProjectStoreError, match="Project not found"):
            store.load_project("absent-project")
        store.close()


class TestRevisions:
    def _initial(self, document_id: str = "doc-1") -> Any:
        return create_initial_revision(
            document_id=document_id,
            structure_signature=_signature("structure-1"),
            accepted_text_sha256=_sha("accepted-text-1"),
        )

    def test_save_and_load_revision(self, project_root: Path) -> None:
        revision = self._initial()
        store = ProjectStore(project_root)
        store.save_revision(revision)
        loaded = store.current_revision("doc-1")
        store.close()
        assert loaded is not None
        assert revision_to_payload(loaded) == revision_to_payload(revision)

    def test_stale_revision_conflicts(self, project_root: Path) -> None:
        first = self._initial()
        store = ProjectStore(project_root)
        store.save_revision(first)
        second = propose_next_revision(
            current=first,
            structure_signature=_signature("structure-2"),
            accepted_text_sha256=_sha("accepted-text-2"),
            note="second",
        )
        store.save_revision(accept_revision(proposed=second, expected_current=first))
        stale = propose_next_revision(
            current=first,
            structure_signature=_signature("stale-structure"),
            accepted_text_sha256=_sha("stale-text"),
            note="stale",
        )
        with pytest.raises(RevisionConflictError):
            store.save_revision(stale)
        head = store.current_revision("doc-1")
        store.close()
        assert head is not None
        assert revision_to_payload(head)["token"] == 2

    def test_list_revisions_ordered(self, project_root: Path) -> None:
        store = ProjectStore(project_root)
        first = self._initial()
        store.save_revision(first)
        second = propose_next_revision(
            current=first,
            structure_signature=_signature("structure-2"),
            accepted_text_sha256=_sha("accepted-text-2"),
            note="second",
        )
        store.save_revision(accept_revision(proposed=second, expected_current=first))
        revisions = store.list_revisions("doc-1")
        store.close()
        tokens = [revision_to_payload(revision)["token"] for revision in revisions]
        assert tokens == [1, 2]

    def test_revision_ids_are_scoped_to_document(self, project_root: Path) -> None:
        store = ProjectStore(project_root)
        store.save_revision(self._initial("doc-1"))
        store.save_revision(self._initial("doc-2"))
        assert store.current_revision("doc-1") is not None
        assert store.current_revision("doc-2") is not None
        store.close()


class TestClaimsEntitiesSpans:
    def test_local_ids_can_repeat_across_documents(self, project_root: Path) -> None:
        store = ProjectStore(project_root)
        claim = ClaimV2("cl1", "one", Modality.ASSERTED, False, "", ("s1",), None)
        entity = Entity(entity_id="e1", name="Example")
        span = ProtectedSpan(
            span_id="s1",
            kind=SpanKind.DATE,
            source_location=SourceLocation(start_offset=0, end_offset=4),
            text="2026",
        )
        relationship = Relationship("r1", "e1", "supports", "e2")
        for document_id in ("doc-1", "doc-2"):
            store.save_claims(document_id, (claim,))
            store.save_entities(document_id, (entity,))
            store.save_protected_spans(document_id, (span,))
            store.save_relationships(document_id, (relationship,))
        assert len(store.load_claims("doc-1")) == 1
        assert len(store.load_claims("doc-2")) == 1
        assert len(store.load_relationships("doc-1")) == 1
        assert len(store.load_relationships("doc-2")) == 1
        store.close()

    def test_atomic_write_rolls_back_all_records(self, project_root: Path) -> None:
        project = _project_domain
        assert project is not None
        store = ProjectStore(project_root)
        state = project.new_project_state(name="test-project", root=str(project_root))
        with pytest.raises(RuntimeError, match="injected failure"), store.atomic():
            store.create_project(state)
            store.add_document("doc-1", state.project_id)
            store.save_claims(
                "doc-1",
                (ClaimV2("cl1", "one", Modality.ASSERTED, False, "", ("s1",), None),),
            )
            raise RuntimeError("injected failure")
        with pytest.raises(ProjectStoreError, match="Project not found"):
            store.load_project(state.project_id)
        assert store.load_claims("doc-1") == ()
        store.close()

    def test_claim_round_trip(self, project_root: Path) -> None:
        store = ProjectStore(project_root)
        store.save_claims(
            "doc-1",
            (
                ClaimV2(
                    claim_id="cl-1",
                    canonical_proposition="The comet returns every 76 years.",
                    modality=Modality.ASSERTED,
                    negation=False,
                    attribution="Kepler",
                    source_evidence_refs=("s1",),
                    confidence=0.9,
                    status=ClaimStatus.PROPOSED,
                    allowed_paraphrase_scope="exact",
                ),
                ClaimV2(
                    claim_id="cl-2",
                    canonical_proposition="No evidence supports that.",
                    modality=Modality.HEDGED,
                    negation=True,
                    attribution="",
                    source_evidence_refs=("s2",),
                    confidence=None,
                ),
            ),
        )
        loaded = store.load_claims("doc-1")
        store.close()
        assert len(loaded) == 2
        first = dict(loaded[0])
        assert first["claim_id"] == "cl-1"
        assert first["proposition"] == "The comet returns every 76 years."
        assert first["modality"] == "asserted"
        assert first["negation"] == 0
        assert first["attribution"] == "Kepler"
        assert first["confidence"] == 0.9
        assert first["status"] == "proposed"
        assert first["paraphrase_scope"] == "exact"
        second = dict(loaded[1])
        assert second["negation"] == 1
        assert second["confidence"] is None

    def test_claims_replace_per_document(self, project_root: Path) -> None:
        store = ProjectStore(project_root)
        store.save_claims(
            "doc-1",
            (ClaimV2("cl-1", "one", Modality.ASSERTED, False, "", ("s1",), None),),
        )
        store.save_claims(
            "doc-1",
            (ClaimV2("cl-2", "two", Modality.ASSERTED, False, "", ("s1",), None),),
        )
        loaded = store.load_claims("doc-1")
        store.close()
        assert [claim["claim_id"] for claim in loaded] == ["cl-2"]

    def test_entity_round_trip(self, project_root: Path) -> None:
        store = ProjectStore(project_root)
        store.save_entities(
            "doc-1",
            (
                Entity(
                    entity_id="e-1",
                    name="Halley's Comet",
                    entity_type=EntityType.OTHER,
                ),
            ),
        )
        loaded = store.load_entities("doc-1")
        store.close()
        assert len(loaded) == 1
        assert loaded[0]["entity_id"] == "e-1"
        assert loaded[0]["name"] == "Halley's Comet"
        assert loaded[0]["entity_type"] == "other"

    def test_protected_span_round_trip(self, project_root: Path) -> None:
        store = ProjectStore(project_root)
        store.save_protected_spans(
            "doc-1",
            (
                ProtectedSpan(
                    span_id="s-1",
                    kind=SpanKind.DATE,
                    source_location=SourceLocation(start_offset=10, end_offset=14),
                    text="1927",
                ),
            ),
        )
        loaded = store.load_protected_spans("doc-1")
        store.close()
        assert len(loaded) == 1
        assert loaded[0]["span_id"] == "s-1"
        assert loaded[0]["kind"] == "date"
        assert loaded[0]["text"] == "1927"
        assert loaded[0]["start_offset"] == 10
        assert loaded[0]["end_offset"] == 14


class TestApprovals:
    def test_record_and_list_approvals(self, project_root: Path) -> None:
        store = ProjectStore(project_root)
        store.record_approval(
            target_kind="revision", target_id="rev-1", decision="accepted", decided_by="user-a"
        )
        store.record_approval(
            target_kind="revision", target_id="rev-2", decision="rejected", decided_by="user-a"
        )
        approvals = store.list_approvals()
        store.close()
        assert len(approvals) == 2
        assert {approval["target_id"] for approval in approvals} == {"rev-1", "rev-2"}
        assert all(approval["decided_at"] != "" for approval in approvals)


class TestEncryptedFields:
    def test_proposition_and_name_are_encrypted(self, project_root: Path) -> None:
        store = ProjectStore(project_root, encryption_enabled=True, key_provider=TestKeyProvider())
        store.save_claims(
            "doc-1",
            (
                ClaimV2(
                    claim_id="cl-1",
                    canonical_proposition="Top-secret proposition text",
                    modality=Modality.ASSERTED,
                    negation=False,
                    attribution="",
                    source_evidence_refs=("s1",),
                    confidence=None,
                ),
            ),
        )
        store.save_entities(
            "doc-1",
            (Entity(entity_id="e-1", name="Sensitive Entity Name"),),
        )
        conn = sqlite3.connect(str(project_root / ".humanhand" / "project.db"))
        try:
            row = conn.execute("SELECT proposition FROM claims WHERE claim_id = 'cl-1'").fetchone()
            assert row is not None
            assert row[0].startswith("encv1:")
            assert "Top-secret proposition text" not in str(row[0])
            name_row = conn.execute("SELECT name FROM entities WHERE entity_id = 'e-1'").fetchone()
            assert name_row is not None
            assert "Sensitive Entity Name" not in str(name_row[0])
        finally:
            conn.close()
        claims = store.load_claims("doc-1")
        entities = store.load_entities("doc-1")
        store.close()
        assert claims[0]["proposition"] == "Top-secret proposition text"
        assert entities[0]["name"] == "Sensitive Entity Name"


class TestPermissions:
    @pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
    def test_database_permissions_0600(self, project_root: Path) -> None:
        store = ProjectStore(project_root)
        store.close()
        mode = stat.S_IMODE((project_root / ".humanhand" / "project.db").stat().st_mode)
        assert mode == 0o600
