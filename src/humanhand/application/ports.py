"""Application ports — Protocols for infra implementations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from humanhand.domain.types import PromptContract


class FileReader(Protocol):
    """Protocol for reading text files with strict validation."""

    def read(self, path: str | Path) -> str:
        """Read and return text from path, raising on BOM/encoding/empty errors."""
        ...


class FileWriter(Protocol):
    """Protocol for writing clean output text."""

    def write(
        self,
        output_path: str | Path,
        text: str,
        input_paths: list[str | Path] | None = None,
    ) -> Path:
        """Scrub, normalize, and write text. Returns the output path."""
        ...


class DetectorCache(Protocol):
    """Protocol for detector score cache with no user text storage."""

    def get(
        self, text_hash: str, provider: str, model: str, schema_version: int
    ) -> dict[str, Any] | None:
        """Retrieve a cached detector score record, or None on miss."""
        ...

    def put(self, record: dict[str, Any]) -> None:
        """Store a detector score record. Must not contain user text."""
        ...

    def close(self) -> None:
        """Close the cache connection."""
        ...


class LlmClient(Protocol):
    """Protocol for OpenAI-compatible LLM client."""

    def rewrite(self, prompt_contract: PromptContract) -> str:
        """Send a rewrite/repair prompt and return the generated text.

        Args:
            prompt_contract: The prompt to send.

        Returns:
            Generated text from the LLM.

        Raises:
            LlmError: On network, auth, or schema validation failure.
        """
        ...


class DetectorClient(Protocol):
    """Protocol for AI-text detector provider."""

    def detect(self, text: str) -> dict[str, Any]:
        """Analyze text and return a detector score record.

        Args:
            text: The text to analyze for AI likelihood.

        Returns:
            Dict with keys: provider, model, score, label, raw_score_json.

        Raises:
            DetectorError: On network, auth, or provider unavailability.
        """
        ...


class Logger(Protocol):
    """Protocol for structured JSONL logging to stderr."""

    def log(self, event: str, level: str = "info", **fields: Any) -> None:
        """Emit a structured log event.

        Args:
            event: Stable event name, e.g. 'rewrite.start'.
            level: 'debug', 'info', 'warning', or 'error'.
            **fields: Additional redacted log fields.
        """
        ...
