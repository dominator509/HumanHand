"""Strict file I/O for Human Hand — read, write, and validation."""

from __future__ import annotations

from pathlib import Path

from humanhand.domain.scrub import scrub_output


class FileIOError(Exception):
    """Raised when file reading or writing fails."""


def read_text_strict(path: str | Path) -> str:
    """Read a file as strict UTF-8 text, rejecting BOM and decode errors.

    Args:
        path: Path to the input file.

    Returns:
        Decoded UTF-8 text with no BOM.

    Raises:
        FileIOError: If file not found, not readable, has BOM,
            is invalid UTF-8, or is empty/whitespace-only.
    """
    p = Path(path)

    if not p.exists():
        raise FileIOError(f"File not found: {p}")

    if not p.is_file():
        raise FileIOError(f"Not a regular file: {p}")

    try:
        raw = p.read_bytes()
    except OSError as exc:
        raise FileIOError(f"Cannot read file: {p}") from exc

    # Reject BOM
    if raw.startswith(b"\xef\xbb\xbf"):
        raise FileIOError("UTF-8 BOM detected; BOM is not accepted")

    # Strict UTF-8 decode
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise FileIOError(f"Invalid UTF-8 in file: {p}") from exc

    # Reject empty or whitespace-only input
    if not text or not text.strip():
        raise FileIOError(f"File is empty or whitespace-only: {p}")

    return text


def read_text_strict_or_stdin(path: str | Path) -> str:
    """Read from a file path or return '-' as a sentinel for stdin.

    This function does NOT read stdin — it returns the sentinel string
    "<stdin>" so the caller can handle stdin separately.

    Args:
        path: File path or the string "-".

    Returns:
        Decoded UTF-8 text, or "<stdin>" if path is "-".

    Raises:
        FileIOError: If path is "-" (sentinel — caller must handle stdin)
            or if file read fails.
    """
    path_str = str(path)
    if path_str == "-":
        return "<stdin>"
    return read_text_strict(path)


def write_clean_text(
    output_path: str | Path,
    text: str,
    input_paths: list[str | Path] | None = None,
) -> Path:
    """Scrub, normalize, and write output text. Refuses to overwrite input files.

    Args:
        output_path: Destination path for the cleaned output.
        text: Candidate output text to scrub and write.
        input_paths: Input file paths that must not be overwritten.

    Returns:
        The resolved output Path that was written.

    Raises:
        FileIOError: If output path matches any input path,
            parent directory cannot be created, or write fails.
    """
    out = Path(output_path).resolve()

    # Refuse to overwrite any input file
    if input_paths:
        for inp in input_paths:
            resolved_inp = Path(inp).resolve()
            if out == resolved_inp:
                raise FileIOError(f"Output path must not match an input path: {out}")

    # Scrub and normalize the text
    scrub_report = scrub_output(text)
    cleaned = scrub_report.cleaned_text

    # Create parent directories if they don't exist
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise FileIOError(f"Cannot create output directory: {out.parent}") from exc

    # Write as UTF-8 without BOM
    encoded = cleaned.encode("utf-8")
    try:
        out.write_bytes(encoded)
    except OSError as exc:
        raise FileIOError(f"Cannot write output file: {out}") from exc

    return out


def read_bytes(path: str | Path) -> bytes:
    """Read raw bytes from a file for hashing or inspection.

    Args:
        path: Path to the file.

    Returns:
        Raw file bytes.

    Raises:
        FileIOError: If file cannot be read.
    """
    p = Path(path)
    if not p.exists():
        raise FileIOError(f"File not found: {p}")
    try:
        return p.read_bytes()
    except OSError as exc:
        raise FileIOError(f"Cannot read file: {p}") from exc


def file_size(path: str | Path) -> int:
    """Return a regular file's size in bytes without reading it.

    Raises:
        FileIOError: If the path is missing, not a regular file, or unstatable.
    """
    p = Path(path)
    if not p.exists():
        raise FileIOError(f"File not found: {p}")
    if not p.is_file():
        raise FileIOError(f"Not a regular file: {p}")
    try:
        return p.stat().st_size
    except OSError as exc:
        raise FileIOError(f"Cannot read file: {p}") from exc


def read_head_bytes(path: str | Path, max_bytes: int) -> bytes:
    """Read at most ``max_bytes`` bytes from the start of a file.

    Used for magic-byte identity checks on files that are too large to read
    fully. Raises FileIOError like :func:`read_bytes`.
    """
    p = Path(path)
    if not p.exists():
        raise FileIOError(f"File not found: {p}")
    try:
        with p.open("rb") as handle:
            return handle.read(max_bytes)
    except OSError as exc:
        raise FileIOError(f"Cannot read file: {p}") from exc
