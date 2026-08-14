"""Optional SQLite detector-score cache — stores metadata only, never user text.

The cache constructor accepts either an explicit SQLite file path or a cache
directory. Directory-like paths resolve to ``detector_scores.db`` so callers
that configure a cache directory and callers that configure a database file
share one unambiguous boundary.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any


class CacheError(Exception):
    """Raised when cache operations fail safely."""


SCHEMA_VERSION = 1
CACHE_DB_FILENAME = "detector_scores.db"
_SQLITE_SUFFIXES = frozenset({".db", ".sqlite", ".sqlite3"})

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS detector_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text_sha256 TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    schema_version INTEGER NOT NULL DEFAULT 1,
    score REAL,
    label TEXT,
    raw_score_json TEXT,
    created_at REAL NOT NULL,
    expires_at REAL,
    UNIQUE(text_sha256, provider, model, schema_version)
);
"""

CREATE_INDEX_HASH_SQL = """
CREATE INDEX IF NOT EXISTS idx_detector_scores_hash
ON detector_scores(text_sha256, provider, model, schema_version);
"""

# Columns that MUST NOT appear in the schema (safety check)
FORBIDDEN_CACHE_COLUMNS = {
    "source_text",
    "style_text",
    "output_text",
    "prompt_text",
    "llm_response",
    "detector_response",
    "user_text",
    "raw_text",
    "api_key",
    "secret",
}

FORBIDDEN_JSON_FIELD_TOKENS = {
    "text",
    "content",
    "prompt",
    "input",
    "source",
    "style",
    "output",
    "response",
    "message",
}


def _resolve_db_path(value: str | Path) -> Path:
    """Resolve a configured cache location to an SQLite database file.

    Existing directories and nonexistent extensionless paths are interpreted
    as cache directories. Existing files and paths ending in a conventional
    SQLite suffix are interpreted as explicit database files. The rule is
    deterministic and fixes the health-before-verify failure where ``health``
    created the configured cache directory before ``verify`` opened SQLite.
    """
    path = Path(value)
    if path.exists():
        return path / CACHE_DB_FILENAME if path.is_dir() else path
    if path.suffix.lower() in _SQLITE_SUFFIXES:
        return path
    return path / CACHE_DB_FILENAME


def _validate_no_text_columns(conn: sqlite3.Connection) -> None:
    """Safety check: assert no forbidden text columns exist in the schema."""
    cursor = conn.execute("PRAGMA table_info(detector_scores)")
    columns = {row[1] for row in cursor.fetchall()}
    violations = columns & FORBIDDEN_CACHE_COLUMNS
    if violations:
        raise CacheError(
            f"Cache schema contains forbidden text columns: {', '.join(sorted(violations))}"
        )


def _set_permissions(db_path: Path) -> None:
    """Best-effort set cache file permissions to 0600."""
    with contextlib.suppress(OSError):
        os.chmod(db_path, 0o600)  # Owner read/write only


def _validate_text_free_json(value: Any, path: str = "root") -> None:
    """Reject JSON structures that could plausibly contain user text."""
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key).lower()
            if any(token in key_text for token in FORBIDDEN_JSON_FIELD_TOKENS):
                raise CacheError(f"raw_score_json contains forbidden field name at {path}: {key}")
            _validate_text_free_json(item, f"{path}.{key}")
        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_text_free_json(item, f"{path}[{index}]")
        return

    if isinstance(value, str):
        if len(value) > 64 or any(ch.isspace() for ch in value):
            raise CacheError("raw_score_json contains unsupported freeform string data")
        return

    if value is None or isinstance(value, bool | int | float):
        return

    raise CacheError(f"raw_score_json contains unsupported value type at {path}")


def _normalize_raw_score_json(raw_score_json: Any) -> str | None:
    """Validate and compact raw score JSON so it stays text-free."""
    if raw_score_json is None:
        return None

    data = raw_score_json
    if isinstance(raw_score_json, str):
        try:
            data = json.loads(raw_score_json)
        except json.JSONDecodeError as exc:
            raise CacheError("raw_score_json must be valid JSON") from exc

    _validate_text_free_json(data)
    return json.dumps(data, separators=(",", ":"), sort_keys=True)


class DetectorScoreCache:
    """Optional SQLite cache for detector score metadata.

    Stores scores keyed by text hash, provider, model, and schema version.
    Never stores user text, prompts, or raw responses.
    """

    def __init__(self, db_path: str | Path) -> None:
        """Initialize cache connection.

        Args:
            db_path: Explicit SQLite database path or cache directory. A
                directory-like path resolves to ``detector_scores.db``.
        """
        self._db_path = _resolve_db_path(db_path)
        self._conn: sqlite3.Connection | None = None

    @property
    def db_path(self) -> Path:
        """Resolved SQLite database path, exposed for diagnostics and tests."""
        return self._db_path

    @property
    def conn(self) -> sqlite3.Connection:
        """Get or lazily create the database connection and schema."""
        if self._conn is None:
            conn: sqlite3.Connection | None = None
            try:
                self._db_path.parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(str(self._db_path))
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute(CREATE_TABLE_SQL)
                conn.execute(CREATE_INDEX_HASH_SQL)
                conn.commit()
                _validate_no_text_columns(conn)
                _set_permissions(self._db_path)
            except (OSError, sqlite3.Error) as exc:
                with contextlib.suppress(sqlite3.Error):
                    if conn is not None:
                        conn.close()
                raise CacheError("Cache initialization error") from exc
            self._conn = conn
        return self._conn

    def get(
        self,
        text_sha256: str,
        provider: str,
        model: str,
        schema_version: int = SCHEMA_VERSION,
    ) -> dict[str, Any] | None:
        """Retrieve a cached detector score record.

        Args:
            text_sha256: SHA-256 hex digest of the text.
            provider: Detector provider name.
            model: Detector model name.
            schema_version: Cache schema version.

        Returns:
            Dict with score metadata, or None if not found.
        """
        try:
            cursor = self.conn.execute(
                """SELECT text_sha256, provider, model, schema_version,
                          score, label, raw_score_json, created_at, expires_at
                   FROM detector_scores
                   WHERE text_sha256 = ? AND provider = ? AND model = ?
                   AND schema_version = ?""",
                (text_sha256, provider, model, schema_version),
            )
            row = cursor.fetchone()
            if row is None:
                return None

            return {
                "text_sha256": row[0],
                "provider": row[1],
                "model": row[2],
                "schema_version": row[3],
                "score": row[4],
                "label": row[5],
                "raw_score_json": row[6],
                "created_at": row[7],
                "expires_at": row[8],
            }
        except sqlite3.Error as exc:
            raise CacheError(f"Cache read error: {exc}") from exc

    def put(self, record: dict[str, Any]) -> None:
        """Store a detector score record.

        Args:
            record: Dict with keys: text_sha256, provider, model,
                score, label, raw_score_json, expires_at (optional).
        """
        try:
            normalized_raw_score_json = _normalize_raw_score_json(record.get("raw_score_json"))
            self.conn.execute(
                """INSERT OR REPLACE INTO detector_scores
                   (text_sha256, provider, model, schema_version,
                    score, label, raw_score_json, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record["text_sha256"],
                    record["provider"],
                    record["model"],
                    record.get("schema_version", SCHEMA_VERSION),
                    record.get("score"),
                    record.get("label"),
                    normalized_raw_score_json,
                    time.time(),
                    record.get("expires_at"),
                ),
            )
            self.conn.commit()
        except KeyError as exc:
            raise CacheError(f"Cache record missing required field: {exc.args[0]}") from exc
        except sqlite3.Error as exc:
            raise CacheError(f"Cache write error: {exc}") from exc

    def close(self) -> None:
        """Close the cache connection."""
        if self._conn is not None:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
            finally:
                self._conn = None

    @staticmethod
    def hash_text(text: str) -> str:
        """Compute SHA-256 hex digest of normalized text."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def hash_prefix(text: str, length: int = 8) -> str:
        """Compute a short SHA-256 prefix for logging."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]
