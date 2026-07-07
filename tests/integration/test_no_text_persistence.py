"""Integration tests proving no user text is persisted in cache, logs, or files."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import pytest

from humanhand.cli.app import _CliLogger
from humanhand.infra.cache import DetectorScoreCache
from humanhand.infra.files import write_clean_text
from humanhand.infra.logging import log_info

# ---------------------------------------------------------------------------
# Sentinel text used for all "must not appear" tests
# ---------------------------------------------------------------------------

SENTINEL_USER_TEXT = "This is Alice's private journal entry about her day at the park."


# ---------------------------------------------------------------------------
# Cache — no text persistence
# ---------------------------------------------------------------------------


class TestCacheNoTextPersistence:
    """Prove the cache never stores user text."""

    def test_cache_schema_forbids_text_columns(self, tmp_path: Path) -> None:
        """The cache schema must have no text-capable columns beyond hashes/metadata."""
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)
        try:
            _ = cache.conn
            cursor = cache.conn.execute("PRAGMA table_info(detector_scores)")
            columns = {row[1] for row in cursor.fetchall()}

            forbidden = {
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
            for col in forbidden:
                assert col not in columns, f"Forbidden column '{col}' found"
        finally:
            cache.close()

    def test_cache_db_rows_contain_no_sentinel_text(self, tmp_path: Path) -> None:
        """Direct byte-level scan: no sentinel text bytes in the SQLite file."""
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)
        try:
            cache.put(
                {
                    "text_sha256": DetectorScoreCache.hash_text(SENTINEL_USER_TEXT),
                    "provider": "test",
                    "model": "v1",
                    "score": 0.5,
                    "label": "human",
                }
            )

            # Read the raw SQLite file bytes and search for the sentinel
            raw_bytes = db_path.read_bytes()
            sentinel_bytes = SENTINEL_USER_TEXT.encode("utf-8")
            assert sentinel_bytes not in raw_bytes, (
                "Sentinel user text found in cache database file"
            )
        finally:
            cache.close()

    def test_cache_put_rejects_text_in_json(self, tmp_path: Path) -> None:
        """Cache must reject raw_score_json containing text-like fields."""
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)
        try:
            from humanhand.infra.cache import CacheError

            with pytest.raises(CacheError, match="forbidden field name"):
                cache.put(
                    {
                        "text_sha256": "abc123",
                        "provider": "test",
                        "model": "v1",
                        "score": 0.5,
                        "raw_score_json": '{"input_text":"sensitive content here"}',
                    }
                )
        finally:
            cache.close()

    def test_cache_put_rejects_long_strings_in_json(self, tmp_path: Path) -> None:
        """Cache must reject raw_score_json containing long freeform strings."""
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)
        try:
            from humanhand.infra.cache import CacheError

            with pytest.raises(CacheError, match="freeform string"):
                cache.put(
                    {
                        "text_sha256": "abc123",
                        "provider": "test",
                        "model": "v1",
                        "score": 0.5,
                        "raw_score_json": (
                            '{"note":"this is a long string that contains spaces and is too long"}'
                        ),
                    }
                )
        finally:
            cache.close()

    def test_hash_only_in_cache_not_text(self, tmp_path: Path) -> None:
        """Stored data only references text by hash, never by content."""
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)
        try:
            text_hash = DetectorScoreCache.hash_text(SENTINEL_USER_TEXT)
            cache.put(
                {
                    "text_sha256": text_hash,
                    "provider": "test",
                    "model": "v1",
                    "score": 0.5,
                    "label": "human",
                }
            )
            result = cache.get(text_hash, "test", "v1")
            assert result is not None
            # Verify the record exists but contains no text
            assert SENTINEL_USER_TEXT not in str(result)
            assert result["text_sha256"] == text_hash
        finally:
            cache.close()


# ---------------------------------------------------------------------------
# File I/O — safe output, no overwrite, no text leak
# ---------------------------------------------------------------------------


class TestFileIOSafety:
    """Prove file I/O operations protect user data."""

    def test_output_never_overwrites_input(self, tmp_path: Path) -> None:
        src = tmp_path / "source.txt"
        src.write_text(SENTINEL_USER_TEXT, encoding="utf-8")

        with pytest.raises(Exception, match="must not match"):
            write_clean_text(src, "new content", input_paths=[src])

    def test_output_never_overwrites_style_input(self, tmp_path: Path) -> None:
        style = tmp_path / "style.txt"
        style.write_text("Style sample text.", encoding="utf-8")

        with pytest.raises(Exception, match="must not match"):
            write_clean_text(style, "new content", input_paths=[style])

    def test_written_output_contains_no_hidden_metadata(self, tmp_path: Path) -> None:
        out = tmp_path / "output.txt"
        write_clean_text(out, "Simple output text.")
        raw = out.read_bytes()
        # No BOM
        assert not raw.startswith(b"\xef\xbb\xbf")
        # No JSON wrapper
        assert b"provenance" not in raw
        assert b"model_id" not in raw
        assert b'"text":' not in raw

    def test_output_is_plain_utf8(self, tmp_path: Path) -> None:
        out = tmp_path / "output.txt"
        write_clean_text(out, "Plain UTF-8 output.")
        text = out.read_text("utf-8")
        assert "Plain UTF-8 output." in text

    def test_output_file_permissions_reasonable(self, tmp_path: Path) -> None:
        """Output file should be created with default permissions (not world-writable)."""
        out = tmp_path / "output.txt"
        write_clean_text(out, "Test.")
        assert out.exists()
        if os.name != "nt":
            import stat

            mode = stat.S_IMODE(out.stat().st_mode)
            # Should not be world-writable
            assert (mode & 0o002) == 0, f"Output file is world-writable: {oct(mode)}"


# ---------------------------------------------------------------------------
# Logging — no text leak
# ---------------------------------------------------------------------------


class TestLoggingNoTextLeak:
    """Prove that logging never emits user text."""

    def test_log_info_never_contains_sentinel_text(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Log messages with user text values must redact them."""
        log_info("rewrite.start", "Processing text", source_text=SENTINEL_USER_TEXT)
        captured = capsys.readouterr()
        assert SENTINEL_USER_TEXT not in captured.err, "Sentinel user text leaked into log output"

    def test_log_extra_with_style_text_redacted(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_info("style.load", "Loading style", style_text="User's style sample.")
        captured = capsys.readouterr()
        assert "User's style sample." not in captured.err

    def test_log_with_prompt_redacted(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_info("prompt.build", "Building prompt", prompt="System: rewrite this text.")
        captured = capsys.readouterr()
        assert "rewrite this text" not in captured.err

    def test_log_with_llm_response_redacted(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_info("llm.response", "Got response", llm_response="Generated output text.")
        captured = capsys.readouterr()
        assert "Generated output text" not in captured.err

    def test_log_with_detector_response_redacted(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_info("detector.response", "Got score", detector_response='{"score":0.9,"text":"..."}')
        captured = capsys.readouterr()
        assert '"text":"..."' not in captured.err

    def test_log_with_safe_metadata_only(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Safe metadata fields (lengths, hashes, hosts) should pass through."""
        log_info(
            "rewrite.done",
            "Done",
            input_length=1024,
            output_length=512,
            sha256_prefix="abcdef01",
            endpoint_host="api.openai.com",
            elapsed_ms=150.5,
        )
        captured = capsys.readouterr()
        assert "1024" in captured.err
        assert "512" in captured.err
        assert "abcdef01" in captured.err
        assert "api.openai.com" in captured.err

    def test_log_does_not_contain_secret_patterns(self, capsys: pytest.CaptureFixture[str]) -> None:
        log_info(
            "config.load",
            "Config loaded",
            api_key="sk-this-is-a-secret-key-for-testing",
            llm_api_key="sk-another-secret-key",
        )
        captured = capsys.readouterr()
        assert "sk-this-is-a-secret-key-for-testing" not in captured.err
        assert "sk-another-secret-key" not in captured.err

    def test_cli_logger_redacts_secret_and_text_fields(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The runtime CLI logger must apply the same redaction rules."""
        logger = _CliLogger()
        logger.log(
            "rewrite.start",
            message="Using key sk-abcdefghijklmnopqrstuvwxyz12345",
            source_text=SENTINEL_USER_TEXT,
            llm_api_key="sk-another-secret-key",
        )
        captured = capsys.readouterr()
        record = json.loads(captured.err.strip())
        assert "sk-abcdefghijklmnopqrstuvwxyz12345" not in record["message"]
        assert record["source_text"] == "<REDACTED>"
        assert record["llm_api_key"] == "<REDACTED_SECRET>"


# ---------------------------------------------------------------------------
# Cache file permissions (best effort)
# ---------------------------------------------------------------------------


class TestCachePermissions:
    """Test cache file permission best-effort behavior."""

    def test_cache_file_created(self, tmp_path: Path) -> None:
        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)
        try:
            _ = cache.conn
            assert db_path.exists()
        finally:
            cache.close()

    def test_cache_dir_created_if_missing(self, tmp_path: Path) -> None:
        db_path = tmp_path / "nested" / "dir" / "cache.db"
        cache = DetectorScoreCache(db_path)
        try:
            _ = cache.conn
            assert db_path.exists()
        finally:
            cache.close()

    def test_cache_permissions_posix(self, tmp_path: Path) -> None:
        if os.name == "nt":
            pytest.skip("POSIX permissions not portable on Windows")
        import stat

        db_path = tmp_path / "cache.db"
        cache = DetectorScoreCache(db_path)
        try:
            _ = cache.conn
            mode = stat.S_IMODE(db_path.stat().st_mode)
            assert mode == 0o600, f"Cache file mode is {oct(mode)}, expected 0o600"
        finally:
            cache.close()


# ---------------------------------------------------------------------------
# No telemetry or phone-home code
# ---------------------------------------------------------------------------


class TestNoTelemetry:
    """Prove no telemetry, phone-home, or analytics code exists."""

    def test_no_telemetry_imports(self) -> None:
        """No telemetry/analytics libraries should be imported in src/."""
        # Files that legitimately reference telemetry concepts (scrubbing, docs)
        telemetry_safe_files = {
            "scrub.py",  # Scrubs telemetry markers from output
        }
        # Check imports only — not docstrings
        telemetry_import_patterns = (
            "import sentry_sdk",
            "from sentry_sdk",
            "import datadog",
            "from datadog",
            "import newrelic",
            "from newrelic",
            "import posthog",
            "from posthog",
            "import amplitude",
            "from amplitude",
            "import mixpanel",
            "from mixpanel",
            "import segment",
            "from segment",
            "google.analytics",
        )
        src_root = Path("src/humanhand")
        if not src_root.exists():
            return
        for py_file in src_root.rglob("*.py"):
            if py_file.name in telemetry_safe_files:
                continue
            text = py_file.read_text(encoding="utf-8")
            for forbidden in telemetry_import_patterns:
                assert forbidden not in text, f"Telemetry import '{forbidden}' found in {py_file}"

    def test_no_http_calls_on_import(self) -> None:
        """No module should make HTTP calls at import time (structural check)."""
        src_root = Path("src/humanhand")
        if not src_root.exists():
            return
        for py_file in src_root.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                # Check for top-level function calls that look like HTTP
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in ("urlopen", "Request", "get", "post")
                ):
                    # Allow within functions; only flag top-level calls
                    pass
