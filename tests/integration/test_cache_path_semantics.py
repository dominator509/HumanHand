"""Regression tests for directory-versus-database cache path semantics."""

from __future__ import annotations

from pathlib import Path

from humanhand.infra.cache import CACHE_DB_FILENAME, DetectorScoreCache


def test_existing_directory_resolves_to_database_file(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cache = DetectorScoreCache(cache_dir)
    try:
        assert cache.db_path == cache_dir / CACHE_DB_FILENAME
        cache.put(
            {
                "text_sha256": "a" * 64,
                "provider": "local",
                "model": "heuristic-v1",
                "score": 0.25,
                "label": "uncertain",
            }
        )
    finally:
        cache.close()
    assert (cache_dir / CACHE_DB_FILENAME).is_file()


def test_nonexistent_extensionless_path_is_a_cache_directory(tmp_path: Path) -> None:
    configured = tmp_path / "humanhand-cache"
    cache = DetectorScoreCache(configured)
    try:
        _ = cache.conn
    finally:
        cache.close()
    assert cache.db_path == configured / CACHE_DB_FILENAME
    assert cache.db_path.is_file()


def test_explicit_sqlite_path_remains_a_file(tmp_path: Path) -> None:
    configured = tmp_path / "scores.sqlite3"
    cache = DetectorScoreCache(configured)
    try:
        _ = cache.conn
    finally:
        cache.close()
    assert cache.db_path == configured
    assert configured.is_file()
