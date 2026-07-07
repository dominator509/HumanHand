"""CLI error message catalog — friendly one-line messages for stable exit codes.

All messages must be safe for screen readers, avoid technical jargon where
possible, and never contain user text, secrets, or file contents.
"""

from __future__ import annotations

# ── Error message templates ─────────────────────────────────────

ERROR_MESSAGES: dict[str, str] = {
    # Input errors (exit code 1)
    "empty_source": "Source text must not be empty",
    "empty_style": "Style sample must not be empty",
    "source_too_large": "Source text exceeds the maximum allowed size",
    "style_too_large": "Style sample exceeds the maximum allowed size",
    "missing_argument": "A required argument is missing",
    "bom_detected": "File contains a UTF-8 BOM, which is not accepted",
    "invalid_utf8": "File contains invalid UTF-8 characters",
    "whitespace_only": "File contains only whitespace",
    # Config errors (exit code 2)
    "config_invalid": "Configuration is invalid",
    "unknown_provider": "Unknown detector provider",
    "missing_llm_url": "LLM endpoint URL is not configured",
    "unsafe_endpoint": (
        "HTTP is not allowed for remote endpoints — use HTTPS or set HUMANHAND_ALLOW_INSECURE=1"
    ),
    # I/O errors (exit code 3)
    "file_not_found": "File not found",
    "not_a_file": "Path is not a regular file",
    "cannot_read": "Cannot read file",
    "cannot_write": "Cannot write output file",
    "output_is_input": "Output path must not match any input path",
    # External errors (exit code 4)
    "llm_unavailable": "LLM service is unavailable",
    "llm_timeout": "LLM request timed out",
    "llm_error": "LLM request failed",
    "detector_unavailable": "Detector provider is not available",
    "provider_no_key": "Provider requires an API key that is not configured",
    "provider_no_docs": "Provider is not yet available — API documentation is needed",
    # Schema errors (exit code 5)
    "schema_invalid": "Response from external service did not match the expected format",
    "fact_drift": "Could not preserve source facts after multiple repair attempts",
    # Internal errors (exit code 6)
    "internal_error": "An unexpected internal error occurred",
}


def get_error_message(key: str, fallback: str | None = None) -> str:
    """Return a user-friendly error message for the given key.

    Args:
        key: Error message key from the catalog.
        fallback: Message to return if key is not found. Defaults to a
            generic internal error message.

    Returns:
        A one-line user-facing error message.
    """
    return ERROR_MESSAGES.get(key, fallback or ERROR_MESSAGES["internal_error"])


def error_for_exception(exc: Exception) -> str:
    """Map a known exception type to a user-friendly message key.

    Args:
        exc: The exception to map.

    Returns:
        A message key suitable for ``get_error_message``.
    """
    name = type(exc).__name__
    mapping: dict[str, str] = {
        "FileIOError": "file_not_found",
        "FileNotFoundError": "file_not_found",
        "LlmError": "llm_error",
        "DetectorError": "detector_unavailable",
        "ProviderUnavailableError": "provider_no_docs",
        "ValueError": "missing_argument",
        "KeyError": "schema_invalid",
        "TypeError": "schema_invalid",
        "RewriteQualityError": "fact_drift",
    }
    return mapping.get(name, "internal_error")
