"""Integration tests for strict file I/O operations."""

import tempfile
from pathlib import Path

import pytest

from humanhand.infra.files import (
    FileIOError,
    read_bytes,
    read_text_strict,
    read_text_strict_or_stdin,
    write_clean_text,
)


class TestReadTextStrict:
    def test_read_valid_utf8(self) -> None:
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
            f.write(b"Hello, world!\n")
            path = f.name

        try:
            text = read_text_strict(path)
            assert text == "Hello, world!\n"
        finally:
            Path(path).unlink()

    def test_read_file_not_found(self) -> None:
        with pytest.raises(FileIOError, match="File not found"):
            read_text_strict("nonexistent_file_xyz.txt")

    def test_read_directory_not_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileIOError, match="Not a regular file"):
            read_text_strict(tmp_path)

    def test_reject_bom(self) -> None:
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
            f.write(b"\xef\xbb\xbfHello\n")
            path = f.name

        try:
            with pytest.raises(FileIOError, match="BOM"):
                read_text_strict(path)
        finally:
            Path(path).unlink()

    def test_reject_invalid_utf8(self) -> None:
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
            f.write(b"Hello\xff\xfeWorld\n")
            path = f.name

        try:
            with pytest.raises(FileIOError, match="Invalid UTF-8"):
                read_text_strict(path)
        finally:
            Path(path).unlink()

    def test_reject_empty_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
            f.write(b"")
            path = f.name

        try:
            with pytest.raises(FileIOError, match="empty"):
                read_text_strict(path)
        finally:
            Path(path).unlink()

    def test_reject_whitespace_only(self) -> None:
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
            f.write(b"   \n\t  \n  ")
            path = f.name

        try:
            with pytest.raises(FileIOError, match="empty"):
                read_text_strict(path)
        finally:
            Path(path).unlink()

    def test_read_with_newlines(self) -> None:
        content = "Line one\nLine two\nLine three\n"
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
            f.write(content.encode("utf-8"))
            path = f.name

        try:
            text = read_text_strict(path)
            assert text == content
        finally:
            Path(path).unlink()

    def test_read_unicode_content(self) -> None:
        content = "Café au lait — résumé\n"
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
            f.write(content.encode("utf-8"))
            path = f.name

        try:
            text = read_text_strict(path)
            assert text == content
        finally:
            Path(path).unlink()


class TestReadTextStrictOrStdin:
    def test_stdin_sentinel(self) -> None:
        result = read_text_strict_or_stdin("-")
        assert result == "<stdin>"

    def test_file_path(self) -> None:
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
            f.write(b"content\n")
            path = f.name

        try:
            text = read_text_strict_or_stdin(path)
            assert text == "content\n"
        finally:
            Path(path).unlink()


class TestWriteCleanText:
    def test_write_clean_output(self, tmp_path: Path) -> None:
        out_path = tmp_path / "output.txt"
        result = write_clean_text(out_path, "Clean text")
        assert result == out_path.resolve()
        assert out_path.exists()
        written = out_path.read_text("utf-8")
        assert written.endswith("\n")
        assert not written.startswith("\xef\xbb\xbf")

    def test_normalizes_crlf(self, tmp_path: Path) -> None:
        out_path = tmp_path / "output.txt"
        write_clean_text(out_path, "Line one.\r\nLine two.\r\n")
        written = out_path.read_text("utf-8")
        assert "\r\n" not in written

    def test_exactly_one_trailing_newline(self, tmp_path: Path) -> None:
        out_path = tmp_path / "output.txt"
        write_clean_text(out_path, "text\n\n\n")
        written = out_path.read_text("utf-8")
        assert written.endswith("\n")
        assert not written.endswith("\n\n")

    def test_refuse_overwrite_input(self, tmp_path: Path) -> None:
        inp_path = tmp_path / "input.txt"
        inp_path.write_text("input content", encoding="utf-8")

        with pytest.raises(FileIOError, match="must not match"):
            write_clean_text(inp_path, "new content", input_paths=[inp_path])

    def test_refuse_overwrite_any_input(self, tmp_path: Path) -> None:
        inp1 = tmp_path / "source.txt"
        inp2 = tmp_path / "style.txt"
        inp1.write_text("source", encoding="utf-8")
        inp2.write_text("style", encoding="utf-8")

        with pytest.raises(FileIOError, match="must not match"):
            write_clean_text(inp2, "new", input_paths=[inp1, inp2])

    def test_scrub_removes_bom(self, tmp_path: Path) -> None:
        out_path = tmp_path / "output.txt"
        write_clean_text(out_path, "﻿Scrubbed content")
        written = out_path.read_text("utf-8")
        assert not written.startswith("﻿")

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        out_path = tmp_path / "sub" / "nested" / "output.txt"
        write_clean_text(out_path, "content")
        assert out_path.exists()

    def test_no_bom_in_output(self, tmp_path: Path) -> None:
        out_path = tmp_path / "output.txt"
        write_clean_text(out_path, "Hello")
        raw = out_path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf")


class TestReadBytes:
    def test_read_bytes(self, tmp_path: Path) -> None:
        p = tmp_path / "data.bin"
        p.write_bytes(b"\x00\x01\x02")
        result = read_bytes(p)
        assert result == b"\x00\x01\x02"

    def test_read_bytes_not_found(self) -> None:
        with pytest.raises(FileIOError, match="File not found"):
            read_bytes("nonexistent_binary_file.xyz")
