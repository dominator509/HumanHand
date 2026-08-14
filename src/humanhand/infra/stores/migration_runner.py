"""Versioned SQLite migrations with sidecar backup and rollback.

The legacy ``ProjectStore`` remains at compatibility schema version 2. The
EP-019 ``IntegratedProjectStore`` explicitly requests the current version 3,
which adds immutable accepted revision content. This preserves the established
base-store contract while providing a clean upgrade seam for the production
workflow.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from humanhand.infra.stores.project_schema import MIGRATIONS, PROJECT_SCHEMA_VERSION

LEGACY_PROJECT_STORE_SCHEMA_VERSION = 2


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


def apply_migrations(
    connection: sqlite3.Connection,
    *,
    backup_path: str | Path,
    target_version: int = LEGACY_PROJECT_STORE_SCHEMA_VERSION,
) -> int:
    """Apply migrations through ``target_version`` and return the final version.

    The default is the established schema-v2 ``ProjectStore`` contract.
    Integrated production callers request ``PROJECT_SCHEMA_VERSION``
    explicitly. A target outside the known range fails closed. Opening a newer
    database with an older target is read-compatible and returns the existing
    version without attempting a downgrade.
    """
    if not 1 <= target_version <= PROJECT_SCHEMA_VERSION:
        raise MigrationError(
            f"Unsupported migration target {target_version}; current is {PROJECT_SCHEMA_VERSION}"
        )
    backup = Path(backup_path)
    current = current_version(connection)
    if current >= target_version:
        return current
    pending = [
        migration
        for migration in MIGRATIONS
        if current < migration[0] <= target_version
    ]
    if not pending:
        return current

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
    """Restore ``database_path`` from ``backup_path`` using atomic ``os.replace``."""
    backup = Path(backup_path)
    if not backup.is_file():
        raise MigrationError(f"Backup does not exist: {backup}")
    os.replace(backup, Path(database_path))
