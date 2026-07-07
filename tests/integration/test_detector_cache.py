"""Integration tests for detector score cache — no user text stored."""

from pathlib import Path

import pytest

from humanhand.infra.cache import SCHEMA_VERSION, CacheError, DetectorScoreCache


class TestDetectorScoreCache:
    def test_cache_create_and_get(self, tmp_path: Path) -> None:
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)

        try:
            record = {
                "text_sha256": "abc123def456",
                "provider": "local",
                "model": "heuristic-v1",
                "score": 0.85,
                "label": "human",
                "raw_score_json": '{"confidence": 0.85}',
            }
            cache.put(record)

            result = cache.get("abc123def456", "local", "heuristic-v1")
            assert result is not None
            assert result["score"] == 0.85
            assert result["label"] == "human"
            assert result["text_sha256"] == "abc123def456"
        finally:
            cache.close()

    def test_cache_miss(self, tmp_path: Path) -> None:
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)

        try:
            result = cache.get("nonexistent", "local", "v1")
            assert result is None
        finally:
            cache.close()

    def test_cache_update_existing(self, tmp_path: Path) -> None:
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)

        try:
            cache.put(
                {
                    "text_sha256": "key123",
                    "provider": "local",
                    "model": "v1",
                    "score": 0.5,
                }
            )
            cache.put(
                {
                    "text_sha256": "key123",
                    "provider": "local",
                    "model": "v1",
                    "score": 0.9,
                }
            )
            result = cache.get("key123", "local", "v1")
            assert result is not None
            assert result["score"] == 0.9
        finally:
            cache.close()

    def test_no_text_columns(self, tmp_path: Path) -> None:
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)

        try:
            # Force schema creation
            _ = cache.conn
            cursor = cache.conn.execute("PRAGMA table_info(detector_scores)")
            columns = {row[1] for row in cursor.fetchall()}

            forbidden = {
                "source_text",
                "style_text",
                "output_text",
                "prompt_text",
                "llm_response",
            }
            for col in forbidden:
                assert col not in columns, f"Forbidden column '{col}' found in cache schema"
        finally:
            cache.close()

    def test_lazy_schema_creation(self, tmp_path: Path) -> None:
        db_path = tmp_path / "cache.db"
        assert not db_path.exists()
        cache = DetectorScoreCache(db_path)

        try:
            _ = cache.conn  # Triggers schema creation
            assert db_path.exists()
        finally:
            cache.close()

    def test_multiple_providers(self, tmp_path: Path) -> None:
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)

        try:
            cache.put(
                {
                    "text_sha256": "hash1",
                    "provider": "gptzero",
                    "model": "v1",
                    "score": 0.7,
                }
            )
            cache.put(
                {
                    "text_sha256": "hash1",
                    "provider": "originality",
                    "model": "v2",
                    "score": 0.8,
                }
            )

            r1 = cache.get("hash1", "gptzero", "v1")
            r2 = cache.get("hash1", "originality", "v2")
            assert r1 is not None
            assert r2 is not None
            assert r1["score"] == 0.7
            assert r2["score"] == 0.8
        finally:
            cache.close()

    def test_close_idempotent(self, tmp_path: Path) -> None:
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)
        cache.close()
        cache.close()  # Should not raise

    def test_hash_text(self) -> None:
        result = DetectorScoreCache.hash_text("hello")
        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 hex is 64 chars

    def test_hash_deterministic(self) -> None:
        h1 = DetectorScoreCache.hash_text("hello")
        h2 = DetectorScoreCache.hash_text("hello")
        assert h1 == h2

    def test_hash_different_for_different_text(self) -> None:
        h1 = DetectorScoreCache.hash_text("hello")
        h2 = DetectorScoreCache.hash_text("world")
        assert h1 != h2

    def test_hash_prefix(self) -> None:
        prefix = DetectorScoreCache.hash_prefix("test text", length=8)
        assert len(prefix) == 8

    def test_schema_version_column(self, tmp_path: Path) -> None:
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)

        try:
            cache.put(
                {
                    "text_sha256": "hash_sv",
                    "provider": "test",
                    "model": "v1",
                    "score": 0.5,
                    "schema_version": SCHEMA_VERSION,
                }
            )
            result = cache.get("hash_sv", "test", "v1", schema_version=SCHEMA_VERSION)
            assert result is not None
            assert result["schema_version"] == SCHEMA_VERSION
        finally:
            cache.close()

    def test_raw_score_json_stored(self, tmp_path: Path) -> None:
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)

        try:
            cache.put(
                {
                    "text_sha256": "hash_json",
                    "provider": "test",
                    "model": "v1",
                    "score": 0.9,
                    "raw_score_json": '{"breakdown": {"ai": 0.1, "human": 0.9}}',
                }
            )
            result = cache.get("hash_json", "test", "v1")
            assert result is not None
            assert "breakdown" in result["raw_score_json"]
        finally:
            cache.close()

    def test_raw_score_json_with_text_field_rejected(self, tmp_path: Path) -> None:
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)

        try:
            with pytest.raises(CacheError, match="forbidden field name"):
                cache.put(
                    {
                        "text_sha256": "hash_bad",
                        "provider": "test",
                        "model": "v1",
                        "score": 0.4,
                        "raw_score_json": '{"submitted_text":"hello world"}',
                    }
                )
        finally:
            cache.close()

    def test_raw_score_json_with_freeform_string_rejected(self, tmp_path: Path) -> None:
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)

        try:
            with pytest.raises(CacheError, match="freeform string"):
                cache.put(
                    {
                        "text_sha256": "hash_bad_string",
                        "provider": "test",
                        "model": "v1",
                        "score": 0.4,
                        "raw_score_json": '{"note":"this looks like user prose"}',
                    }
                )
        finally:
            cache.close()

    def test_corrupt_cache_raises_safe_error(self, tmp_path: Path) -> None:
        db_path = tmp_path / "cache.db"
        db_path.write_bytes(b"not a sqlite database")
        cache = DetectorScoreCache(db_path)

        try:
            with pytest.raises(CacheError, match="Cache initialization error"):
                _ = cache.conn
        finally:
            cache.close()

    def test_cache_permissions_best_effort_posix(self, tmp_path: Path) -> None:
        import os
        import stat

        if os.name == "nt":
            pytest.skip("POSIX permissions are not portable on Windows")

        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)

        try:
            _ = cache.conn
            mode = stat.S_IMODE(db_path.stat().st_mode)
            assert mode == 0o600
        finally:
            cache.close()

    def test_forbidden_column_in_schema_detected(self, tmp_path: Path) -> None:
        """Line 75: _validate_no_text_columns raises CacheError when a forbidden column exists."""
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)
        try:
            _ = cache.conn  # Create schema
            cache.conn.execute("ALTER TABLE detector_scores ADD COLUMN source_text TEXT")
            cache.conn.commit()
            cache.close()

            cache2 = DetectorScoreCache(db_path)
            with pytest.raises(CacheError, match="forbidden text columns"):
                _ = cache2.conn
        finally:
            cache.close()

    def test_raw_score_json_list_with_forbidden_field(self, tmp_path: Path) -> None:
        """Lines 97-99: List in raw_score_json containing dict with forbidden field name."""
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)
        try:
            with pytest.raises(CacheError, match="forbidden field name"):
                cache.put(
                    {
                        "text_sha256": "hash_list_bad",
                        "provider": "test",
                        "model": "v1",
                        "score": 0.5,
                        "raw_score_json": [{"text": "hello"}],
                    }
                )
        finally:
            cache.close()

    def test_raw_score_json_unsupported_type(self, tmp_path: Path) -> None:
        """Line 109: Unsupported value type in raw_score_json raises CacheError."""
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)
        try:
            with pytest.raises(CacheError, match="unsupported value type"):
                cache.put(
                    {
                        "text_sha256": "hash_bad_type",
                        "provider": "test",
                        "model": "v1",
                        "score": 0.5,
                        "raw_score_json": {"nested": set()},
                    }
                )
        finally:
            cache.close()

    def test_raw_score_json_invalid_json_string(self, tmp_path: Path) -> None:
        """Lines 121-122: Invalid JSON string for raw_score_json raises CacheError."""
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)
        try:
            with pytest.raises(CacheError, match="raw_score_json must be valid JSON"):
                cache.put(
                    {
                        "text_sha256": "hash_bad_json",
                        "provider": "test",
                        "model": "v1",
                        "score": 0.5,
                        "raw_score_json": "{invalid json}",
                    }
                )
        finally:
            cache.close()

    def test_cache_write_error_closed_connection(self, tmp_path: Path) -> None:
        """Line 241: sqlite3.Error during put() is wrapped as CacheError."""
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)
        try:
            _ = cache.conn
            cache.conn.close()  # Close underlying connection but keep the reference
            with pytest.raises(CacheError, match="Cache write error"):
                cache.put(
                    {
                        "text_sha256": "hash_write_err",
                        "provider": "test",
                        "model": "v1",
                        "score": 0.5,
                    }
                )
        finally:
            cache.close()

    def test_cache_read_error_closed_connection(self, tmp_path: Path) -> None:
        """Lines 208-209: sqlite3.Error during get() is wrapped as CacheError."""
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)
        try:
            _ = cache.conn
            cache.conn.close()  # Close underlying connection but keep the reference
            with pytest.raises(CacheError, match="Cache read error"):
                cache.get("some_hash", "test", "v1")
        finally:
            cache.close()

    def test_put_missing_required_field(self, tmp_path: Path) -> None:
        """Line 239: Missing required field in put() raises CacheError."""
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)
        try:
            with pytest.raises(CacheError, match="required field"):
                cache.put(
                    {
                        "provider": "test",
                        "model": "v1",
                        "score": 0.5,
                        # Missing text_sha256
                    }
                )
        finally:
            cache.close()

    def test_raw_score_json_valid_list(self, tmp_path: Path) -> None:
        """Line 99: List in raw_score_json with all-valid items is accepted."""
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)
        try:
            cache.put(
                {
                    "text_sha256": "hash_valid_list",
                    "provider": "test",
                    "model": "v1",
                    "score": 0.5,
                    "raw_score_json": {"categories": ["cat_a", "cat_b"]},
                }
            )
            result = cache.get("hash_valid_list", "test", "v1")
            assert result is not None
            assert "cat_a" in result["raw_score_json"]
        finally:
            cache.close()

    def test_close_sqlite_error(self, tmp_path: Path) -> None:
        """Lines 248-249: sqlite3.Error during close is handled gracefully."""
        import sqlite3

        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)
        _ = cache.conn  # Initialize

        class _FailingConn:
            """Wrapper that raises on close to test defensive error handling."""

            def close(self) -> None:
                raise sqlite3.Error("mock close error")

        cache._conn = _FailingConn()  # type: ignore[assignment]

        # Must not raise despite close failing
        cache.close()
        assert cache._conn is None
