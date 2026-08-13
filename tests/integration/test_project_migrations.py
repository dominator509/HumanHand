"""Integration tests for versioned migrations and rollback (EP-015).

Covers the fresh-open path, reopen idempotence, legacy database migration,
byte-exact rollback from the sidecar backup, the missing-backup refusal, and
transactional DDL: a failing migration rolls back completely and leaves the
database at the last good version.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from humanhand.infra.stores import migration_runner as migration_runner_module
from humanhand.infra.stores.migration_runner import (
    MigrationError,
    apply_migrations,
    current_version,
    rollback_from_backup,
)
from humanhand.infra.stores.project_layout import init_layout, layout_for
from humanhand.infra.stores.project_schema import MIGRATIONS
from humanhand.infra.stores.project_store import ProjectStore


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }


def _open_connection(root: Path) -> sqlite3.Connection:
    return sqlite3.connect(str(layout_for(root).database))


_EXPECTED_TABLES = {
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


class TestApplyMigrations:
    def test_fresh_database_reaches_current_version(self, tmp_path: Path) -> None:
        init_layout(tmp_path, name="test-project")
        db = layout_for(tmp_path).database
        backup = db.with_name("project.db.bak")
        conn = _open_connection(tmp_path)
        try:
            assert current_version(conn) == 0
            final = apply_migrations(conn, backup_path=backup)
            assert final == 2
            assert current_version(conn) == 2
            assert _tables(conn) == _EXPECTED_TABLES
        finally:
            conn.close()
        assert backup.is_file()

    def test_reopen_is_noop_and_backup_persists(self, tmp_path: Path) -> None:
        init_layout(tmp_path, name="test-project")
        db = layout_for(tmp_path).database
        backup = db.with_name("project.db.bak")
        conn = _open_connection(tmp_path)
        apply_migrations(conn, backup_path=backup)
        conn.close()
        assert backup.is_file()
        backup_bytes = backup.read_bytes()
        conn = _open_connection(tmp_path)
        try:
            assert apply_migrations(conn, backup_path=backup) == 2
        finally:
            conn.close()
        assert backup.read_bytes() == backup_bytes

    def test_legacy_database_migrates(self, tmp_path: Path) -> None:
        init_layout(tmp_path, name="test-project")
        db = layout_for(tmp_path).database
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE legacy_notes (note TEXT NOT NULL)")
        conn.execute("INSERT INTO legacy_notes (note) VALUES ('keep me')")
        conn.commit()
        conn.close()
        backup = db.with_name("project.db.bak")
        conn = _open_connection(tmp_path)
        try:
            assert apply_migrations(conn, backup_path=backup) == 2
            assert {"schema_migrations", "legacy_notes"} <= _tables(conn)
            row = conn.execute("SELECT note FROM legacy_notes").fetchone()
            assert row == ("keep me",)
        finally:
            conn.close()
        assert backup.is_file()


class TestRollback:
    def test_rollback_restores_pre_migration_bytes(self, tmp_path: Path) -> None:
        init_layout(tmp_path, name="test-project")
        db = layout_for(tmp_path).database
        backup = db.with_name("project.db.bak")
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE pre (x INTEGER)")
        conn.execute("INSERT INTO pre (x) VALUES (1)")
        conn.commit()
        conn.close()
        before = db.read_bytes()
        conn = _open_connection(tmp_path)
        try:
            assert apply_migrations(conn, backup_path=backup) == 2
        finally:
            conn.close()
        after = db.read_bytes()
        assert after != before
        rollback_from_backup(db, backup)
        assert db.read_bytes() == before
        conn = sqlite3.connect(str(db))
        try:
            assert _tables(conn) == {"pre"}
            assert current_version(conn) == 0
        finally:
            conn.close()

    def test_rollback_refuses_missing_backup(self, tmp_path: Path) -> None:
        init_layout(tmp_path, name="test-project")
        db = layout_for(tmp_path).database
        with pytest.raises(MigrationError, match="Backup does not exist"):
            rollback_from_backup(db, db.with_name("project.db.bak"))


class TestMigrationFailure:
    def test_failed_migration_rolls_back_transactionally(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        init_layout(tmp_path, name="test-project")
        broken = (
            3,
            "CREATE TABLE broken (id INTEGER PRIMARY KEY); THIS IS NOT VALID SQL;",
        )
        monkeypatch.setattr(migration_runner_module, "MIGRATIONS", MIGRATIONS + (broken,))
        with pytest.raises(MigrationError):
            ProjectStore(tmp_path)
        conn = sqlite3.connect(str(layout_for(tmp_path).database))
        try:
            assert current_version(conn) == 2
            assert "broken" not in _tables(conn)
        finally:
            conn.close()


class TestUpgradeFromV1:
    def test_v1_upgrade_preserves_rows_and_refreshes_backup(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        init_layout(tmp_path, name="test-project")
        db = layout_for(tmp_path).database
        backup = db.with_name("project.db.bak")
        monkeypatch.setattr(migration_runner_module, "MIGRATIONS", (MIGRATIONS[0],))
        conn = _open_connection(tmp_path)
        try:
            assert apply_migrations(conn, backup_path=backup) == 1
            conn.execute(
                """INSERT INTO claims
                   (claim_id, document_id, proposition, modality, negation, attribution,
                    confidence, status, paraphrase_scope)
                   VALUES ('cl1', 'doc-1', 'keep me', 'asserted', 0, '', NULL,
                           'proposed', 'meaning_preserving')"""
            )
            conn.commit()
        finally:
            conn.close()

        monkeypatch.setattr(migration_runner_module, "MIGRATIONS", MIGRATIONS)
        conn = _open_connection(tmp_path)
        try:
            assert apply_migrations(conn, backup_path=backup) == 2
            assert conn.execute("SELECT proposition FROM claims").fetchone() == ("keep me",)
        finally:
            conn.close()
        backup_conn = sqlite3.connect(str(backup))
        try:
            assert current_version(backup_conn) == 1
            assert backup_conn.execute("SELECT proposition FROM claims").fetchone() == ("keep me",)
        finally:
            backup_conn.close()
