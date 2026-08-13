"""SQLite project store under ``<root>/.humanhand/project.db`` (EP-015, ADR-001).

- Opens (creating the layout when missing) and applies versioned migrations
  with a sidecar backup (``project.db.bak`` next to the database).
- Enforces ADR-001: nothing is written outside the layout.
- Optimistic revision enforcement: :meth:`ProjectStore.save_revision` raises
  ``RevisionConflictError`` when a stored revision for the document already has
  ``token >= proposed.base_token`` (no stale overwrite).
- Encrypted fields: when encryption is enabled (constructor flag, default
  False), claim propositions and entity names pass through
  ``EncryptedFieldCodec.encode`` on write and ``decode`` on read. Master keys
  are never stored in schema rows.
- The v2 schema holds scalar columns only and scopes document-local ids with
  composite keys. The ``structure_signature`` TEXT
  column stores the revision structure signature as deterministic JSON text
  (mirroring the ``document-revision`` payload contract, including the
  ``schema``/``schema_version`` keys on load). Claims and entities persist the
  mandated columns only; structured fields without columns in the v1 schema
  (``source_evidence_refs``, ``contradictions``, ``aliases``,
  ``evidence_refs``) are not persisted in v1. The only timestamps stored are
  in approvals and migrations (diagnostic wall clock, not canonical content).
"""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from humanhand.infra.stores.migration_runner import apply_migrations
from humanhand.infra.stores.project_layout import init_layout, layout_for

if TYPE_CHECKING:
    from humanhand.domain.project import ProjectState
    from humanhand.domain.revisions import DocumentRevision
    from humanhand.infra.stores.encrypted_fields import EncryptedFieldCodec
    from humanhand.infra.stores.key_provider import KeyProvider

#: Mirrors the ``humanhand.domain.revisions`` document-revision payload
#: contract. The round-trip tests verify these against the real domain module.
_REVISION_SCHEMA_NAME = "document-revision"
_REVISION_SCHEMA_VERSION = 1

#: Mirrors the ``humanhand.domain.project`` project payload contract.
_PROJECT_SCHEMA_NAME = "project"
_PROJECT_SCHEMA_VERSION = 1

_REVISION_COLUMNS = (
    "revision_id",
    "document_id",
    "parent_revision_id",
    "status",
    "base_token",
    "token",
    "structure_signature",
    "accepted_text_sha256",
    "created_note",
)

_PROJECT_COLUMNS = (
    "project_id",
    "name",
    "root",
    "schema_version",
    "coverage_status",
    "style_profile_label",
)


class ProjectStoreError(Exception):
    """Raised when project store invariants are violated."""


def _set_permissions(db_path: Path) -> None:
    """Best-effort set database file permissions to 0600 where supported."""
    with contextlib.suppress(OSError):
        os.chmod(db_path, 0o600)


def _attr_str(obj: object, name: str) -> str:
    value = getattr(obj, name, None)
    if not isinstance(value, str):
        raise ProjectStoreError(f"Object missing required string attribute: {name}")
    return value


def _attr_enum_value(obj: object, name: str) -> str:
    """Read ``name`` as text, accepting a plain string or an enum member."""
    value = getattr(obj, name, None)
    if isinstance(value, str):
        return value
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    raise ProjectStoreError(f"Object attribute {name} must be a string or enum")


def _attr_optional_str(obj: object, name: str) -> str:
    value = getattr(obj, name, None)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ProjectStoreError(f"Object attribute {name} must be a string")
    return value


def _attr_bool(obj: object, name: str) -> int:
    value = getattr(obj, name, None)
    if not isinstance(value, bool):
        raise ProjectStoreError(f"Object missing required bool attribute: {name}")
    return 1 if value else 0


def _attr_int(obj: object, name: str) -> int:
    value = getattr(obj, name, None)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProjectStoreError(f"Object missing required int attribute: {name}")
    return value


def _attr_float_optional(obj: object, name: str) -> float | None:
    value = getattr(obj, name, None)
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        raise ProjectStoreError(f"Object attribute {name} must be numeric")
    return float(value)


def _span_kind(obj: object) -> str:
    """Read ``kind`` as text, accepting a plain string or an enum member."""
    value = getattr(obj, "kind", None)
    if isinstance(value, str):
        return value
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    raise ProjectStoreError("Protected span missing required attribute: kind")


def _span_offset(obj: object, name: str) -> int:
    """Read ``name`` directly, or from a ``source_location`` sub-object."""
    value = getattr(obj, name, None)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    location = getattr(obj, "source_location", None)
    if location is not None:
        nested = getattr(location, name, None)
        if isinstance(nested, int) and not isinstance(nested, bool):
            return nested
    raise ProjectStoreError(f"Protected span missing required attribute: {name}")


def _utc_iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_structure_signature(stored: str) -> dict[str, object]:
    """Parse the JSON-serialized structure signature from the TEXT column."""
    try:
        parsed = json.loads(stored)
    except (TypeError, ValueError) as exc:
        raise ProjectStoreError("Stored structure signature is corrupt") from exc
    if not isinstance(parsed, dict):
        raise ProjectStoreError("Stored structure signature is corrupt")
    return parsed


class ProjectStore:
    """SQLite project store under ``<root>/.humanhand/project.db``."""

    def __init__(
        self,
        root: str | Path,
        *,
        encryption_enabled: bool = False,
        key_provider: KeyProvider | None = None,
    ) -> None:
        self._layout = layout_for(root)
        if not self._layout.project_toml.exists():
            root_path = Path(root)
            init_layout(root_path, name=root_path.name or "humanhand-project")
        self._db_path = self._layout.database
        self._backup_path = self._db_path.with_name(self._db_path.name + ".bak")
        conn = sqlite3.connect(str(self._db_path))
        self._conn: sqlite3.Connection | None = conn
        self._atomic_depth = 0
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            apply_migrations(conn, backup_path=self._backup_path)
            _set_permissions(self._db_path)
        except Exception:
            conn.close()
            self._conn = None
            raise
        self._codec: EncryptedFieldCodec | None = None
        if encryption_enabled:
            if key_provider is None:
                from humanhand.infra.stores.key_provider import resolve_key_provider

                key_provider = resolve_key_provider(None)
            from humanhand.infra.stores.encrypted_fields import EncryptedFieldCodec

            self._codec = EncryptedFieldCodec(provider=key_provider)

    @property
    def _connection(self) -> sqlite3.Connection:
        conn = self._conn
        if conn is None:
            raise ProjectStoreError("Project store is closed")
        return conn

    @property
    def schema_version(self) -> int:
        """Current applied project-database migration version."""
        from humanhand.infra.stores.migration_runner import current_version

        return current_version(self._connection)

    @contextmanager
    def atomic(self) -> Iterator[None]:
        """Group store writes into one all-or-nothing transaction."""
        if self._atomic_depth:
            raise ProjectStoreError("Nested project-store transactions are not supported")
        connection = self._connection
        connection.execute("BEGIN IMMEDIATE")
        self._atomic_depth = 1
        try:
            yield
        except BaseException:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            self._atomic_depth = 0

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        """Commit one write unless it belongs to :meth:`atomic`."""
        connection = self._connection
        if self._atomic_depth:
            yield connection
            return
        with connection:
            yield connection

    # ── Payload helpers ───────────────────────────────────────────

    @staticmethod
    def _require_string(payload: dict[str, object], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str):
            raise ProjectStoreError(f"Payload missing required string key: {key}")
        return value

    @staticmethod
    def _require_int(payload: dict[str, object], key: str) -> int:
        value = payload.get(key)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ProjectStoreError(f"Payload missing required int key: {key}")
        return value

    @staticmethod
    def _optional_string(payload: dict[str, object], key: str) -> str:
        value = payload.get(key)
        if value is None:
            return ""
        if not isinstance(value, str):
            raise ProjectStoreError(f"Payload key {key} must be a string")
        return value

    @staticmethod
    def _optional_nullable(payload: dict[str, object], key: str) -> str | None:
        value = payload.get(key)
        if value is None:
            return None
        if not isinstance(value, str):
            raise ProjectStoreError(f"Payload key {key} must be a string")
        return value

    # ── Projects ──────────────────────────────────────────────────

    def create_project(self, state: ProjectState) -> None:
        from humanhand.domain.project import project_to_payload

        payload = project_to_payload(state)
        with self._write() as connection:
            connection.execute(
                """INSERT INTO projects
                   (project_id, name, root, schema_version, coverage_status, style_profile_label)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    self._require_string(payload, "project_id"),
                    self._require_string(payload, "name"),
                    self._require_string(payload, "root"),
                    self._require_int(payload, "schema_version"),
                    self._require_string(payload, "coverage_status"),
                    self._optional_string(payload, "style_profile_label"),
                ),
            )

    def load_project(self, project_id: str) -> ProjectState:
        from humanhand.domain.project import project_from_payload

        conn = self._connection
        row = conn.execute(
            f"""SELECT {", ".join(_PROJECT_COLUMNS)} FROM projects WHERE project_id = ?""",  # nosec B608 - constant column list, parameterized values
            (project_id,),
        ).fetchone()
        if row is None:
            raise ProjectStoreError(f"Project not found: {project_id}")
        # The v1 schema has no document_ids column; the documents table is the
        # store's record, so document order is rebuilt from it.
        document_ids = [
            str(doc[0])
            for doc in conn.execute(
                "SELECT document_id FROM documents WHERE project_id = ? ORDER BY document_id",
                (project_id,),
            ).fetchall()
        ]
        payload: dict[str, object] = {
            "schema": _PROJECT_SCHEMA_NAME,
            "schema_version": _PROJECT_SCHEMA_VERSION,
            "project_id": row[0],
            "name": row[1],
            "root": row[2],
            "document_ids": document_ids,
            "coverage_status": row[4],
            "style_profile_label": row[5],
        }
        return project_from_payload(payload)

    # ── Documents ─────────────────────────────────────────────────

    def add_document(self, document_id: str, project_id: str, *, purpose: str = "") -> None:
        try:
            with self._write() as connection:
                connection.execute(
                    "INSERT INTO documents (document_id, project_id, purpose) VALUES (?, ?, ?)",
                    (document_id, project_id, purpose),
                )
        except sqlite3.Error as exc:
            raise ProjectStoreError(f"Document add error: {exc}") from exc

    # ── Revisions ─────────────────────────────────────────────────

    def save_revision(self, revision: DocumentRevision) -> None:
        """Persist a revision, rejecting stale bases (optimistic concurrency).

        Raises ``RevisionConflictError`` when a stored revision for the
        document already has ``token >= proposed.base_token``.
        """
        from humanhand.domain.revisions import RevisionConflictError, revision_to_payload

        payload = revision_to_payload(revision)
        document_id = self._require_string(payload, "document_id")
        base_token = self._require_int(payload, "base_token")
        token = self._require_int(payload, "token")
        signature = payload.get("structure_signature")
        if not isinstance(signature, dict):
            raise ProjectStoreError("Revision payload missing structure_signature object")
        structure_signature_json = json.dumps(signature, sort_keys=True)
        try:
            with self._write() as connection:
                row = connection.execute(
                    "SELECT MAX(token) FROM document_revisions WHERE document_id = ?",
                    (document_id,),
                ).fetchone()
                stored_max = row[0] if row is not None else None
                if stored_max is None and base_token != 0:
                    raise RevisionConflictError(
                        f"Stale revision rejected: no stored base for token {base_token}"
                    )
                parent_revision_id = self._optional_nullable(payload, "parent_revision_id")
                if stored_max is None and parent_revision_id is not None:
                    raise RevisionConflictError(
                        "Stale revision rejected: initial revision must not have a parent"
                    )
                if stored_max is not None and int(stored_max) != base_token:
                    raise RevisionConflictError(
                        f"Stale revision rejected: stored token {stored_max} "
                        f"!= base_token {base_token}"
                    )
                if stored_max is not None:
                    head = connection.execute(
                        """SELECT revision_id FROM document_revisions
                           WHERE document_id = ? AND token = ?""",
                        (document_id, int(stored_max)),
                    ).fetchone()
                    if head is None or str(head[0]) != parent_revision_id:
                        raise RevisionConflictError(
                            "Stale revision rejected: parent revision does not match stored head"
                        )
                connection.execute(
                    """INSERT INTO document_revisions
                       (revision_id, document_id, parent_revision_id, status, base_token, token,
                        structure_signature, accepted_text_sha256, created_note)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        self._require_string(payload, "revision_id"),
                        document_id,
                        self._optional_nullable(payload, "parent_revision_id"),
                        self._require_string(payload, "status"),
                        base_token,
                        token,
                        structure_signature_json,
                        self._require_string(payload, "accepted_text_sha256"),
                        self._optional_string(payload, "created_note"),
                    ),
                )
        except sqlite3.Error as exc:
            raise ProjectStoreError(f"Revision save error: {exc}") from exc

    def _revision_from_row(self, row: sqlite3.Row) -> DocumentRevision:
        from humanhand.domain.revisions import revision_from_payload

        payload: dict[str, object] = {
            "schema": _REVISION_SCHEMA_NAME,
            "schema_version": _REVISION_SCHEMA_VERSION,
            "revision_id": row[0],
            "document_id": row[1],
            "parent_revision_id": row[2],
            "status": row[3],
            "base_token": row[4],
            "token": row[5],
            "structure_signature": _parse_structure_signature(str(row[6])),
            "accepted_text_sha256": row[7],
            "created_note": row[8],
        }
        return revision_from_payload(payload)

    def current_revision(self, document_id: str) -> DocumentRevision | None:
        row = self._connection.execute(
            f"""SELECT {", ".join(_REVISION_COLUMNS)} FROM document_revisions
                WHERE document_id = ? ORDER BY token DESC LIMIT 1""",  # nosec B608 - constant column list, parameterized values
            (document_id,),
        ).fetchone()
        if row is None:
            return None
        return self._revision_from_row(row)

    def list_revisions(self, document_id: str) -> tuple[DocumentRevision, ...]:
        rows = self._connection.execute(
            f"""SELECT {", ".join(_REVISION_COLUMNS)} FROM document_revisions
                WHERE document_id = ? ORDER BY token ASC""",  # nosec B608 - constant column list, parameterized values
            (document_id,),
        ).fetchall()
        return tuple(self._revision_from_row(row) for row in rows)

    # ── Claims ────────────────────────────────────────────────────

    def save_claims(self, document_id: str, claims: tuple[object, ...]) -> None:
        """Replace the document's claims (typed against ``ClaimV2`` at runtime).

        Domain fields map onto the mandated v1 columns: the canonical
        proposition goes to ``proposition`` and ``allowed_paraphrase_scope``
        to ``paraphrase_scope``. Propositions pass through the encrypted-field
        codec when encryption is enabled. ``source_evidence_refs`` and
        ``contradictions`` have no columns in the v1 schema and are not
        persisted.
        """
        with self._write() as connection:
            connection.execute("DELETE FROM claims WHERE document_id = ?", (document_id,))
            for claim in claims:
                connection.execute(
                    """INSERT INTO claims
                       (claim_id, document_id, proposition, modality, negation, attribution,
                        confidence, status, paraphrase_scope)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        _attr_str(claim, "claim_id"),
                        document_id,
                        self._encode(_attr_str(claim, "canonical_proposition")),
                        _attr_enum_value(claim, "modality"),
                        _attr_bool(claim, "negation"),
                        _attr_optional_str(claim, "attribution"),
                        _attr_float_optional(claim, "confidence"),
                        _attr_enum_value(claim, "status"),
                        _attr_str(claim, "allowed_paraphrase_scope"),
                    ),
                )

    def load_claims(self, document_id: str) -> tuple[dict[str, object], ...]:
        rows = self._connection.execute(
            """SELECT claim_id, document_id, proposition, modality, negation, attribution,
                      confidence, status, paraphrase_scope
               FROM claims WHERE document_id = ? ORDER BY claim_id""",
            (document_id,),
        ).fetchall()
        claims: list[dict[str, object]] = []
        for row in rows:
            claims.append(
                {
                    "claim_id": row[0],
                    "document_id": row[1],
                    "proposition": self._decode(str(row[2])),
                    "modality": row[3],
                    "negation": row[4],
                    "attribution": row[5],
                    "confidence": row[6],
                    "status": row[7],
                    "paraphrase_scope": row[8],
                }
            )
        return tuple(claims)

    # ── Entities ──────────────────────────────────────────────────

    def save_entities(self, document_id: str, entities: tuple[object, ...]) -> None:
        """Replace the document's entities. Names use the codec when enabled.

        ``aliases`` and ``evidence_refs`` have no columns in the v1 schema and
        are not persisted.
        """
        with self._write() as connection:
            connection.execute("DELETE FROM entities WHERE document_id = ?", (document_id,))
            for entity in entities:
                connection.execute(
                    """INSERT INTO entities (entity_id, document_id, name, entity_type)
                       VALUES (?, ?, ?, ?)""",
                    (
                        _attr_str(entity, "entity_id"),
                        document_id,
                        self._encode(_attr_str(entity, "name")),
                        _attr_enum_value(entity, "entity_type"),
                    ),
                )

    def load_entities(self, document_id: str) -> tuple[dict[str, object], ...]:
        rows = self._connection.execute(
            """SELECT entity_id, document_id, name, entity_type
               FROM entities WHERE document_id = ? ORDER BY entity_id""",
            (document_id,),
        ).fetchall()
        entities: list[dict[str, object]] = []
        for row in rows:
            entities.append(
                {
                    "entity_id": row[0],
                    "document_id": row[1],
                    "name": self._decode(str(row[2])),
                    "entity_type": row[3],
                }
            )
        return tuple(entities)

    # ── Protected spans ───────────────────────────────────────────

    def save_protected_spans(self, document_id: str, spans: tuple[object, ...]) -> None:
        """Replace the document's protected spans (no encrypted columns in v1)."""
        with self._write() as connection:
            connection.execute("DELETE FROM protected_spans WHERE document_id = ?", (document_id,))
            for span in spans:
                connection.execute(
                    """INSERT INTO protected_spans
                       (span_id, document_id, kind, text, start_offset, end_offset)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        _attr_str(span, "span_id"),
                        document_id,
                        _span_kind(span),
                        _attr_str(span, "text"),
                        _span_offset(span, "start_offset"),
                        _span_offset(span, "end_offset"),
                    ),
                )

    def load_protected_spans(self, document_id: str) -> tuple[dict[str, object], ...]:
        rows = self._connection.execute(
            """SELECT span_id, document_id, kind, text, start_offset, end_offset
               FROM protected_spans WHERE document_id = ? ORDER BY span_id""",
            (document_id,),
        ).fetchall()
        spans: list[dict[str, object]] = []
        for row in rows:
            spans.append(
                {
                    "span_id": row[0],
                    "document_id": row[1],
                    "kind": row[2],
                    "text": row[3],
                    "start_offset": row[4],
                    "end_offset": row[5],
                }
            )
        return tuple(spans)

    # ── Relationships ────────────────────────

    def save_relationships(self, document_id: str, relationships: tuple[object, ...]) -> None:
        """Replace one document's deterministic relationship records."""
        with self._write() as connection:
            connection.execute("DELETE FROM relationships WHERE document_id = ?", (document_id,))
            for relationship in relationships:
                connection.execute(
                    """INSERT INTO relationships
                       (relationship_id, document_id, subject_id, predicate, object_id)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        _attr_str(relationship, "relationship_id"),
                        document_id,
                        _attr_str(relationship, "subject_id"),
                        _attr_str(relationship, "predicate"),
                        _attr_str(relationship, "object_id"),
                    ),
                )

    def load_relationships(self, document_id: str) -> tuple[dict[str, object], ...]:
        rows = self._connection.execute(
            """SELECT relationship_id, document_id, subject_id, predicate, object_id
               FROM relationships WHERE document_id = ? ORDER BY relationship_id""",
            (document_id,),
        ).fetchall()
        return tuple(
            {
                "relationship_id": row[0],
                "document_id": row[1],
                "subject_id": row[2],
                "predicate": row[3],
                "object_id": row[4],
            }
            for row in rows
        )

    # ── Approvals ─────────────────────────────────────────────────

    def record_approval(
        self, *, target_kind: str, target_id: str, decision: str, decided_by: str
    ) -> None:
        with self._write() as connection:
            connection.execute(
                """INSERT INTO approvals
                   (approval_id, target_kind, target_id, decision, decided_by, decided_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    uuid.uuid4().hex,
                    target_kind,
                    target_id,
                    decision,
                    decided_by,
                    _utc_iso_now(),
                ),
            )

    def list_approvals(self) -> tuple[dict[str, object], ...]:
        rows = self._connection.execute(
            """SELECT approval_id, target_kind, target_id, decision, decided_by, decided_at
               FROM approvals ORDER BY decided_at, approval_id"""
        ).fetchall()
        approvals: list[dict[str, object]] = []
        for row in rows:
            approvals.append(
                {
                    "approval_id": row[0],
                    "target_kind": row[1],
                    "target_id": row[2],
                    "decision": row[3],
                    "decided_by": row[4],
                    "decided_at": row[5],
                }
            )
        return tuple(approvals)

    # ── Encrypted fields ──────────────────────────────────────────

    def _encode(self, plaintext: str) -> str:
        codec = self._codec
        if codec is None:
            return plaintext
        return codec.encode(plaintext)

    def _decode(self, stored: str) -> str:
        codec = self._codec
        if codec is None:
            return stored
        return codec.decode(stored)

    # ── Lifecycle ─────────────────────────────────────────────────

    def close(self) -> None:
        """Close the database connection (idempotent)."""
        conn = self._conn
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass
            finally:
                self._conn = None
