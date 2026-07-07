"""Structured JSONL logging with mandatory redaction.

All log output goes to stderr as JSONL.  Never logs user text, prompts,
generated output, raw LLM/detector responses, or secrets.
"""

from __future__ import annotations

import json
import re
import sys
import time
from typing import Any

# ---------------------------------------------------------------------------
# Secret / credential detection patterns
# ---------------------------------------------------------------------------

# Common API key prefixes and secret patterns to redact from log messages
_SECRET_KEY_PATTERNS: list[tuple[str, str]] = [
    # Order matters: apply most-specific patterns first so broader patterns
    # don't consume tokens that later patterns need to match.
    (r"(?:sk|pk|rk)-(?:live|test)?[A-Za-z0-9_-]{20,}", "<REDACTED_KEY>"),
    (r"ghp_[A-Za-z0-9]{20,}", "<REDACTED_GH_TOKEN>"),
    (r"xox[baprs]-[A-Za-z0-9-]{20,}", "<REDACTED_SLACK>"),
    (r"AKIA[0-9A-Z]{16}", "<REDACTED_AWS_KEY>"),
    # Authorization header with Bearer token — must precede bare-Bearer pattern
    (r"Authorization:\s*Bearer\s+[A-Za-z0-9_\-\.]+", "Authorization: Bearer <REDACTED>"),
    (r"Bearer\s+[A-Za-z0-9_\-\.]+", "Bearer <REDACTED>"),
    (r"api[_-]?key[=:]\s*[^\s,;}]+", "api_key=<REDACTED>"),
    # URL credentials
    (r"://[^:@\s]+:[^@\s]+@", "://<REDACTED_CREDENTIALS>@"),
]

# Fields whose *values* are never logged even after generic redaction
_NEVER_LOG_VALUE_KEYS: set[str] = {
    "source_text",
    "style_text",
    "output_text",
    "prompt",
    "llm_response",
    "detector_response",
    "api_key",
    "secret",
    "token",
    "password",
    "credential",
}

# Additional values that should be redacted if they appear in log contexts
# Keys whose names suggest they contain secrets
_SECRET_KEY_NAME_PATTERNS: list[str] = [
    "api_key",
    "apikey",
    "secret",
    "password",
    "token",
    "credential",
    "authorization",
]


def _is_secret_key_name(key: str) -> bool:
    """Check if a key name suggests it holds a secret."""
    lower = key.lower().replace("_", "").replace("-", "")
    return any(pattern in lower for pattern in _SECRET_KEY_NAME_PATTERNS)


def _redact_string(value: str) -> str:
    """Apply all secret patterns to a string and return the redacted version."""
    result = value
    for pattern, replacement in _SECRET_KEY_PATTERNS:
        result = re.sub(pattern, replacement, result)
    return result


def redact_value(value: Any, key: str = "") -> Any:  # noqa: C901
    """Recursively redact secrets and user text from a loggable value.

    Args:
        value: The value to redact.
        key: The dictionary key this value was found under (for context).

    Returns:
        A safe, redacted version suitable for JSON serialization.
    """
    # Secret-named keys get their values fully replaced
    if key and _is_secret_key_name(key):
        return "<REDACTED_SECRET>"

    # Never-log keys get replaced entirely
    if key in _NEVER_LOG_VALUE_KEYS:
        return "<REDACTED>"

    if isinstance(value, str):
        return _redact_string(value)

    if isinstance(value, dict):
        return {str(k): redact_value(v, str(k)) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [redact_value(item, "") for item in value]

    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"

    # Numbers, booleans, None are safe
    return value


def _build_log_record(
    level: str,
    event: str,
    message: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a single JSONL log record with required fields."""
    record: dict[str, Any] = {
        "timestamp": _iso_timestamp_now(),
        "level": level,
        "event": event,
        "message": _redact_string(message),
    }
    if extra:
        for k, v in extra.items():
            record[k] = redact_value(v, key=k)
    return record


def _iso_timestamp_now() -> str:
    """Return current UTC time as ISO-8601 string."""
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"


def _emit(record: dict[str, Any]) -> None:
    """Write a single JSONL record to stderr."""
    try:
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        print(line, file=sys.stderr, flush=True)
    except Exception:
        # If logging itself fails, emit a minimal fallback
        fallback = json.dumps(
            {
                "timestamp": _iso_timestamp_now(),
                "level": "error",
                "event": "log.write_failed",
                "message": "Log record could not be serialized",
            }
        )
        print(fallback, file=sys.stderr, flush=True)


def log_debug(event: str, message: str, **extra: Any) -> None:
    """Emit a debug-level log event."""
    _emit(_build_log_record("debug", event, message, extra))


def log_info(event: str, message: str, **extra: Any) -> None:
    """Emit an info-level log event."""
    _emit(_build_log_record("info", event, message, extra))


def log_warning(event: str, message: str, **extra: Any) -> None:
    """Emit a warning-level log event."""
    _emit(_build_log_record("warning", event, message, extra))


def log_error(event: str, message: str, **extra: Any) -> None:
    """Emit an error-level log event."""
    _emit(_build_log_record("error", event, message, extra))


# ---------------------------------------------------------------------------
# Convenience helpers for domain/infra use
# ---------------------------------------------------------------------------


def safe_length(value: str | None) -> int | None:
    """Return character length of a string, or None if value is None."""
    if value is None:
        return None
    return len(value)


def safe_sha256_prefix(value: str, prefix_len: int = 8) -> str:
    """Return a short SHA-256 prefix for identification without revealing text."""
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:prefix_len]
