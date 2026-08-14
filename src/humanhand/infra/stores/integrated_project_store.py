"""Integrated project store for accepted document revisions (EP-019).

The EP-015 :class:`~humanhand.infra.stores.project_store.ProjectStore`
persists revision metadata, facts, entities, relationships, and approvals.
This extension persists the actual accepted text and canonical document JSON
for every immutable revision. It closes the central integration gap: context,
finalization, and export load the accepted project revision directly.

Sensitive content uses the parent store's application-layer codec whenever
encryption is enabled. Revision-content rows are write-once: an idempotent
repeat with identical values is accepted, while a conflicting repeat fails
closed. Protected-span text is also encoded here so strict/regulated workflows
do not retain those source fragments in plaintext.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from humanhand.domain.canonical_document import CanonicalDocument
from humanhand.domain.document_serialization import document_from_json
from humanhand.domain.protected_spans import ProtectedSpan
from humanhand.domain.revisions import DocumentRevision, RevisionStatus
from humanhand.infra.stores.project_store import ProjectStore, ProjectStoreError


@dataclass(frozen=True)
class StoredRevisionContent:
    """The content associated with one immutable project revision."""

    document_id: str
    revision_id: str
    accepted_text: str
    canonical_document_json: str
    style_profile_id: str
    finalization_run_id: str

    @property
    def canonical_document(self) -> CanonicalDocument:
        """Parse and integrity-check the stored canonical document."""
        document = document_from_json(self.canonical_document_json)
        if document.surface_text != self.accepted_text:
            raise ProjectStoreError(
                "Stored revision content is corrupt: canonical surface does not match accepted text"
            )
        return document


class IntegratedProjectStore(ProjectStore):
    """ProjectStore plus accepted content and style-profile integration."""

    def latest_accepted_revision(self, document_id: str) -> DocumentRevision | None:
        """Return the highest-token ACCEPTED revision for ``document_id``."""
        accepted = [
            revision
            for revision in self.list_revisions(document_id)
            if revision.status is RevisionStatus.ACCEPTED
        ]
        return max(accepted, key=lambda revision: revision.token, default=None)

    def save_revision_content(
        self,
        *,
        revision: DocumentRevision,
        accepted_text: str,
        canonical_document_json: str,
        style_profile_id: str = "",
        finalization_run_id: str = "",
    ) -> None:
        """Persist one immutable revision-content row.

        The content hash must equal ``revision.accepted_text_sha256`` and the
        canonical document's exact surface must equal ``accepted_text``.
        Existing identical rows are idempotent; conflicting rows fail closed.
        """
        if not accepted_text:
            raise ProjectStoreError("Revision content must not be empty")
        digest = hashlib.sha256(accepted_text.encode("utf-8")).hexdigest()
        if digest != revision.accepted_text_sha256:
            raise ProjectStoreError(
                "Revision content hash does not match revision.accepted_text_sha256"
            )
        try:
            document = document_from_json(canonical_document_json)
        except Exception as exc:
            raise ProjectStoreError("Revision canonical document JSON is invalid") from exc
        if document.surface_text != accepted_text:
            raise ProjectStoreError(
                "Revision canonical document surface does not match accepted text"
            )
        if revision.document_id == "":
            raise ProjectStoreError("Revision document_id must not be empty")

        revision_row = self._connection.execute(
            """SELECT accepted_text_sha256 FROM document_revisions
               WHERE document_id = ? AND revision_id = ?""",
            (revision.document_id, revision.revision_id),
        ).fetchone()
        if revision_row is None:
            raise ProjectStoreError("Revision metadata must be stored before revision content")
        if str(revision_row[0]) != digest:
            raise ProjectStoreError("Stored revision metadata hash does not match content")

        existing = self._connection.execute(
            """SELECT accepted_text, canonical_document_json, style_profile_id,
                      finalization_run_id
               FROM revision_contents
               WHERE document_id = ? AND revision_id = ?""",
            (revision.document_id, revision.revision_id),
        ).fetchone()
        values = (
            accepted_text,
            canonical_document_json,
            style_profile_id,
            finalization_run_id,
        )
        if existing is not None:
            decoded = (
                self._decode(str(existing[0])),
                self._decode(str(existing[1])),
                str(existing[2]),
                str(existing[3]),
            )
            if decoded != values:
                raise ProjectStoreError(
                    "Revision content is immutable and already exists with different values"
                )
            return

        with self._write() as connection:
            connection.execute(
                """INSERT INTO revision_contents
                   (document_id, revision_id, accepted_text, canonical_document_json,
                    style_profile_id, finalization_run_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    revision.document_id,
                    revision.revision_id,
                    self._encode(accepted_text),
                    self._encode(canonical_document_json),
                    style_profile_id,
                    finalization_run_id,
                ),
            )

    def load_revision_content(
        self, document_id: str, revision_id: str | None = None
    ) -> StoredRevisionContent | None:
        """Load one revision's content, or the latest accepted content."""
        selected_revision_id = revision_id
        if selected_revision_id is None:
            revision = self.latest_accepted_revision(document_id)
            if revision is None:
                return None
            selected_revision_id = revision.revision_id
        row = self._connection.execute(
            """SELECT document_id, revision_id, accepted_text,
                      canonical_document_json, style_profile_id, finalization_run_id
               FROM revision_contents
               WHERE document_id = ? AND revision_id = ?""",
            (document_id, selected_revision_id),
        ).fetchone()
        if row is None:
            return None
        content = StoredRevisionContent(
            document_id=str(row[0]),
            revision_id=str(row[1]),
            accepted_text=self._decode(str(row[2])),
            canonical_document_json=self._decode(str(row[3])),
            style_profile_id=str(row[4]),
            finalization_run_id=str(row[5]),
        )
        revision = next(
            (
                item
                for item in self.list_revisions(document_id)
                if item.revision_id == selected_revision_id
            ),
            None,
        )
        if revision is None:
            raise ProjectStoreError("Stored revision content has no revision metadata")
        digest = hashlib.sha256(content.accepted_text.encode("utf-8")).hexdigest()
        if digest != revision.accepted_text_sha256:
            raise ProjectStoreError("Stored revision content failed its sha256 integrity check")
        _ = content.canonical_document
        return content

    def save_protected_spans(
        self, document_id: str, spans: tuple[ProtectedSpan, ...]
    ) -> None:
        """Replace protected spans while encoding their exact source text."""
        with self._write() as connection:
            connection.execute("DELETE FROM protected_spans WHERE document_id = ?", (document_id,))
            for span in spans:
                connection.execute(
                    """INSERT INTO protected_spans
                       (span_id, document_id, kind, text, start_offset, end_offset)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        span.span_id,
                        document_id,
                        span.kind.value,
                        self._encode(span.text),
                        span.source_location.start_offset,
                        span.source_location.end_offset,
                    ),
                )

    def load_protected_spans(self, document_id: str) -> tuple[dict[str, object], ...]:
        """Load protected spans, decoding text when encryption is active."""
        rows = self._connection.execute(
            """SELECT span_id, document_id, kind, text, start_offset, end_offset
               FROM protected_spans WHERE document_id = ? ORDER BY span_id""",
            (document_id,),
        ).fetchall()
        return tuple(
            {
                "span_id": row[0],
                "document_id": row[1],
                "kind": row[2],
                "text": self._decode(str(row[3])),
                "start_offset": row[4],
                "end_offset": row[5],
            }
            for row in rows
        )

    def bind_style_profile(self, project_id: str, profile_label: str) -> None:
        """Bind a reviewed style profile label to a project."""
        label = profile_label.strip()
        if not label:
            raise ProjectStoreError("Style profile label must not be empty")
        with self._write() as connection:
            cursor = connection.execute(
                "UPDATE projects SET style_profile_label = ? WHERE project_id = ?",
                (label, project_id),
            )
            if cursor.rowcount != 1:
                raise ProjectStoreError(f"Project not found: {project_id}")

    def project_style_profile(self, project_id: str) -> str:
        """Return the bound profile label, or an empty string when unbound."""
        row = self._connection.execute(
            "SELECT style_profile_label FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if row is None:
            raise ProjectStoreError(f"Project not found: {project_id}")
        return str(row[0])
