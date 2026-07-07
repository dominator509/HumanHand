"""HTTPS enforcement and HTTP helpers."""

from __future__ import annotations

from urllib.parse import urlparse

import httpx


class HttpError(Exception):
    """Raised when an HTTP operation fails."""


def validate_endpoint(url: str, allow_insecure: bool = False) -> str:
    """Validate and normalize an endpoint URL.

    Rejects non-HTTPS URLs unless ``allow_insecure`` is True or the host is
    localhost / 127.0.0.1 / ::1.

    Args:
        url: The endpoint URL to validate.
        allow_insecure: If True, HTTP is allowed for non-localhost endpoints.

    Returns:
        Normalized base URL, guaranteed to end with ``/v1``.

    Raises:
        HttpError: If the URL is invalid, missing scheme/host, or insecure.
    """
    parsed = urlparse(url)

    if not parsed.scheme:
        raise HttpError(f"Missing scheme in endpoint URL: {url}")
    if not parsed.netloc:
        raise HttpError(f"Missing host in endpoint URL: {url}")

    if parsed.scheme == "http":
        host = parsed.hostname or ""
        if not allow_insecure and host not in ("localhost", "127.0.0.1", "::1"):
            raise HttpError(
                "HTTP is not allowed for non-localhost endpoints. "
                "Set HUMANHAND_ALLOW_INSECURE=1 or use an HTTPS endpoint."
            )

    # Normalize the path component to end with /v1
    path = parsed.path.rstrip("/")
    if not path.endswith("/v1"):
        path = path + "/v1"

    # Reconstruct the URL preserving query and fragment
    normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
    if parsed.query:
        normalized = f"{normalized}?{parsed.query}"
    if parsed.fragment:
        normalized = f"{normalized}#{parsed.fragment}"

    return normalized


def build_client(
    base_url: str,
    api_key: str | None,
    timeout: float = 30.0,
) -> httpx.Client:
    """Create an ``httpx.Client`` with JSON headers and optional Bearer auth.

    Args:
        base_url: The base URL for the API.
        api_key: Optional Bearer token sent as ``Authorization`` header.
        timeout: Request timeout in seconds.

    Returns:
        A configured ``httpx.Client`` instance.

    Raises:
        HttpError: If the client cannot be created.
    """
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        return httpx.Client(
            base_url=base_url,
            headers=headers,
            timeout=httpx.Timeout(timeout),
        )
    except Exception as exc:
        raise HttpError(f"Cannot create HTTP client: {exc}") from exc
