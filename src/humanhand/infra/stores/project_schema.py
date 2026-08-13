"""Versioned SQLite schema for the local project store (EP-015, ADR-001).

Each entry in ``MIGRATIONS`` is ``(version, DDL script)``. Version 2 scopes
document-local record ids with composite keys so deterministic ids can repeat
across documents. Scripts are made of
independent statements terminated by semicolons; the migration runner executes
each statement inside its own explicit transaction so DDL is fully rollbackable.

Sensitive columns (``claims.proposition``, ``entities.name``) hold application-
layer encrypted text when the store is opened with encryption enabled. The
database schema itself never stores secrets.
"""

from __future__ import annotations

PROJECT_SCHEMA_VERSION = 2

MIGRATIONS: tuple[tuple[int, str], ...] = (
    (
        1,
        """
CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE projects (
    project_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    root TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    coverage_status TEXT NOT NULL,
    style_profile_label TEXT NOT NULL DEFAULT ''
);

CREATE TABLE documents (
    document_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(project_id),
    purpose TEXT NOT NULL DEFAULT ''
);

CREATE TABLE document_revisions (
    revision_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    parent_revision_id TEXT,
    status TEXT NOT NULL,
    base_token INTEGER NOT NULL,
    token INTEGER NOT NULL,
    structure_signature TEXT NOT NULL,
    accepted_text_sha256 TEXT NOT NULL,
    created_note TEXT NOT NULL DEFAULT ''
);

CREATE UNIQUE INDEX idx_document_revisions_document_token
ON document_revisions(document_id, token);

CREATE TABLE protected_spans (
    span_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    start_offset INTEGER NOT NULL,
    end_offset INTEGER NOT NULL
);

CREATE TABLE claims (
    claim_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    proposition TEXT NOT NULL,
    modality TEXT NOT NULL,
    negation INTEGER NOT NULL,
    attribution TEXT NOT NULL DEFAULT '',
    confidence REAL,
    status TEXT NOT NULL,
    paraphrase_scope TEXT NOT NULL
);

CREATE TABLE entities (
    entity_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL
);

CREATE TABLE relationships (
    relationship_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_id TEXT NOT NULL
);

CREATE TABLE approvals (
    approval_id TEXT PRIMARY KEY,
    target_kind TEXT NOT NULL,
    target_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    decided_by TEXT NOT NULL,
    decided_at TEXT NOT NULL
);
""",
    ),
    (
        2,
        """
DROP INDEX idx_document_revisions_document_token;

ALTER TABLE document_revisions RENAME TO document_revisions_v1;
CREATE TABLE document_revisions (
    revision_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    parent_revision_id TEXT,
    status TEXT NOT NULL,
    base_token INTEGER NOT NULL,
    token INTEGER NOT NULL,
    structure_signature TEXT NOT NULL,
    accepted_text_sha256 TEXT NOT NULL,
    created_note TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (document_id, revision_id)
);
INSERT INTO document_revisions SELECT * FROM document_revisions_v1;
DROP TABLE document_revisions_v1;
CREATE UNIQUE INDEX idx_document_revisions_document_token
ON document_revisions(document_id, token);

ALTER TABLE protected_spans RENAME TO protected_spans_v1;
CREATE TABLE protected_spans (
    span_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    start_offset INTEGER NOT NULL,
    end_offset INTEGER NOT NULL,
    PRIMARY KEY (document_id, span_id)
);
INSERT INTO protected_spans SELECT * FROM protected_spans_v1;
DROP TABLE protected_spans_v1;

ALTER TABLE claims RENAME TO claims_v1;
CREATE TABLE claims (
    claim_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    proposition TEXT NOT NULL,
    modality TEXT NOT NULL,
    negation INTEGER NOT NULL,
    attribution TEXT NOT NULL DEFAULT '',
    confidence REAL,
    status TEXT NOT NULL,
    paraphrase_scope TEXT NOT NULL,
    PRIMARY KEY (document_id, claim_id)
);
INSERT INTO claims SELECT * FROM claims_v1;
DROP TABLE claims_v1;

ALTER TABLE entities RENAME TO entities_v1;
CREATE TABLE entities (
    entity_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    PRIMARY KEY (document_id, entity_id)
);
INSERT INTO entities SELECT * FROM entities_v1;
DROP TABLE entities_v1;

ALTER TABLE relationships RENAME TO relationships_v1;
CREATE TABLE relationships (
    relationship_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_id TEXT NOT NULL,
    PRIMARY KEY (document_id, relationship_id)
);
INSERT INTO relationships SELECT * FROM relationships_v1;
DROP TABLE relationships_v1;
""",
    ),
)
