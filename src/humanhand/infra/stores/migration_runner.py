"""Versioned SQLite migrations with a sidecar backup and rollback (EP-015).

The project database uses the default (non-WAL) journal mode, so a plain file
copy taken before any write is a consistent snapshot. The backup lives next to
the database (``project.db.bak``) and restores the pre-migration bytes
atomically via :func:`rollback_from_backup`. No stale ``-wal`` file can ever
replay writes on top of restored bytes.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from humanhand.infra.stores.project_schema import MIGRATIONS


class MigrationError(Exception):
    """Raised when a schema migration cannot be applied safely."""


def current_version(connection: sqlite3.Connection) -> int:
    """Return the highest applied schema version (0 when uninitialized)."""
    table = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
    ).fetchone()
    if table is None:
        return 0
    row = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    if row is None or row[0] is None:
        return 0
    return int(row[0])


def _database_path(connection: sqlite3.Connection) -> Path:
    """Resolve the on-disk path of the main database file."""
    row = connection.execute("PRAGMA database_list").fetchone()
    if row is None or row[2] is None:
        raise MigrationError("Cannot resolve the main database file path")
    return Path(str(row[2]))


def _iter_statements(sql: str) -> Iterator[str]:
    """Yield statements from ``sql``, honoring single-quoted literals."""
    statement: list[str] = []
    in_string = False
    index = 0
    while index < len(sql):
        char = sql[index]
        if in_string:
            statement.append(char)
            if char == "'":
                if index + 1 < len(sql) and sql[index + 1] == "'":
                    statement.append("'")
                    index += 1
                else:
                    in_string = False
        elif char == "'":
            in_string = True
            statement.append(char)
        elif char == ";":
            yield "".join(statement).strip()
            statement = []
        else:
            statement.append(char)
        index += 1
    tail = "".join(statement).strip()
    if tail:
        yield tail


def _utc_iso_now() -> str:
    return datetime.now(UTC).isoformat()


def apply_migrations(connection: sqlite3.Connection, *, backup_path: str | Path) -> int:
    """Apply pending migrations in order and return the final version.

    Before the first pending migration the existing database file is copied to
    ``backup_path`` (a plain file copy taken BEFORE any write; the store never
    enables WAL journaling, so the main file is a consistent snapshot at that
    point). Each migration runs inside its own explicit transaction: a failing
    migration rolls back completely (SQLite DDL is transactional) and raises
    :class:`MigrationError`, leaving the database at the last good version.
    ``applied_at`` is a UTC wall-clock timestamp recorded for diagnostics only;
    it is metadata, not canonical content.
    """
    backup = Path(backup_path)
    current = current_version(connection)
    pending = [migration for migration in MIGRATIONS if migration[0] > current]
    if not pending:
        return current
    # Snapshot the state immediately before this upgrade.  A sidecar left
    # by an older migration is stale and must not be used as the rollback
    # point for a newer schema transition.
    shutil.copyfile(_database_path(connection), backup)
    for version, sql in pending:
        try:
            connection.execute("BEGIN")
            for statement in _iter_statements(sql):
                if statement:
                    connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (version, _utc_iso_now()),
            )
            connection.commit()
        except sqlite3.Error as exc:
            with contextlib.suppress(sqlite3.Error):
                connection.rollback()
            raise MigrationError(f"Migration to version {version} failed: {exc}") from exc
    return pending[-1][0]


def rollback_from_backup(database_path: str | Path, backup_path: str | Path) -> None:
    """Restore ``database_path`` from ``backup_path`` using atomic ``os.replace``.

    Refuses when the backup does not exist. The restored file is authoritative
    because the store never enables WAL journaling, so no stale ``-wal`` file
    can replay writes on top of the restored bytes.
    """
    backup = Path(backup_path)
    if not backup.is_file():
        raise MigrationError(f"Backup does not exist: {backup}")
    os.replace(backup, Path(database_path))
