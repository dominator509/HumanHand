"""Integration tests for EP-019 accepted revision content storage."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from humanhand.domain.canonical_document import CanonicalDocument, build_document
from humanhand.domain.document_nodes import NodeBuilder, NodeType, SourceLocation
from humanhand.domain.document_serialization import document_to_json
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.project import new_project_state
from humanhand.domain.protected_spans import ProtectedSpan, SpanKind
from humanhand.domain.revisions import create_initial_revision
from humanhand.domain.structure_signature import compute_structure_signature
from humanhand.infra.stores.integrated_project_store import IntegratedProjectStore
from humanhand.infra.stores.project_layout import layout_for
from humanhand.infra.stores.project_store import ProjectStoreError
from humanhand.infra.stores.test_key_provider import TestKeyProvider


def _document(text: str = "The deadline is August 30, 2026.") -> CanonicalDocument:
    root = NodeBuilder(node_type=NodeType.DOCUMENT)
    root.add_child(
        NodeBuilder(
            node_type=NodeType.PARAGRAPH,
            text=text,
            source_location=SourceLocation(0, len(text)),
        )
    )
    return build_document(
        root=root,
        lane="source",
        parser_name="test",
        parser_version="1",
        policy=ImportPolicy(lane="source"),
        surface_text=text,
    )


def _persist_initial(
    store: IntegratedProjectStore,
    root: Path,
    document: CanonicalDocument,
) -> tuple[str, str]:
    project = new_project_state(name="test-project", root=str(root))
    document_id = "src-test"
    digest = hashlib.sha256(document.surface_text.encode("utf-8")).hexdigest()
    revision = create_initial_revision(
        document_id=document_id,
        structure_signature=compute_structure_signature(document),
        accepted_text_sha256=digest,
    )
    with store.atomic():
        store.create_project(project)
        store.add_document(document_id, project.project_id)
        store.save_revision(revision)
        store.save_revision_content(
            revision=revision,
            accepted_text=document.surface_text,
            canonical_document_json=document_to_json(document),
            style_profile_id="dom-professional",
        )
    return document_id, revision.revision_id


def test_revision_content_round_trip_and_latest_accepted(tmp_path: Path) -> None:
    document = _document()
    store = IntegratedProjectStore(tmp_path)
    try:
        document_id, revision_id = _persist_initial(store, tmp_path, document)
        loaded = store.load_revision_content(document_id)
        assert loaded is not None
        assert loaded.revision_id == revision_id
        assert loaded.accepted_text == document.surface_text
        assert loaded.canonical_document == document
        assert loaded.style_profile_id == "dom-professional"
        assert store.latest_accepted_revision(document_id) is not None
    finally:
        store.close()


def test_revision_content_is_write_once_but_idempotent(tmp_path: Path) -> None:
    document = _document()
    store = IntegratedProjectStore(tmp_path)
    try:
        document_id, revision_id = _persist_initial(store, tmp_path, document)
        revision = store.current_revision(document_id)
        assert revision is not None
        store.save_revision_content(
            revision=revision,
            accepted_text=document.surface_text,
            canonical_document_json=document_to_json(document),
            style_profile_id="dom-professional",
        )
        with pytest.raises(ProjectStoreError, match="immutable"):
            store.save_revision_content(
                revision=revision,
                accepted_text=document.surface_text,
                canonical_document_json=document_to_json(document),
                style_profile_id="different-profile",
            )
        assert store.load_revision_content(document_id, revision_id) is not None
    finally:
        store.close()


def test_revision_content_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    document = _document()
    store = IntegratedProjectStore(tmp_path)
    try:
        project = new_project_state(name="test-project", root=str(tmp_path))
        revision = create_initial_revision(
            document_id="src-test",
            structure_signature=compute_structure_signature(document),
            accepted_text_sha256="0" * 64,
        )
        store.create_project(project)
        store.add_document("src-test", project.project_id)
        store.save_revision(revision)
        with pytest.raises(ProjectStoreError, match="hash"):
            store.save_revision_content(
                revision=revision,
                accepted_text=document.surface_text,
                canonical_document_json=document_to_json(document),
            )
    finally:
        store.close()


def test_encrypted_store_contains_no_plain_revision_or_span_text(tmp_path: Path) -> None:
    document = _document("Confidential sentinel sentence 7843.")
    provider = TestKeyProvider()
    store = IntegratedProjectStore(
        tmp_path,
        encryption_enabled=True,
        key_provider=provider,
    )
    try:
        document_id, _revision_id = _persist_initial(store, tmp_path, document)
        span = ProtectedSpan(
            span_id="s1",
            kind=SpanKind.KEY_TERM,
            source_location=SourceLocation(0, 12),
            text="Confidential",
        )
        store.save_protected_spans(document_id, (span,))
        loaded = store.load_revision_content(document_id)
        assert loaded is not None
        assert loaded.accepted_text == document.surface_text
        assert store.load_protected_spans(document_id)[0]["text"] == "Confidential"
    finally:
        store.close()

    db_path = layout_for(tmp_path).database
    connection = sqlite3.connect(str(db_path))
    try:
        accepted = connection.execute("SELECT accepted_text FROM revision_contents").fetchone()
        protected = connection.execute("SELECT text FROM protected_spans").fetchone()
    finally:
        connection.close()
    assert accepted is not None and "Confidential sentinel" not in str(accepted[0])
    assert protected is not None and "Confidential" not in str(protected[0])
