"""Turnitin detector stub — no API documentation available yet."""

from __future__ import annotations

from typing import Any

from humanhand.infra.detectors.base import BaseDetector, ProviderUnavailableError


class TurnitinDetector(BaseDetector):
    """Turnitin AI-text detector adapter (stub).

    No API documentation is currently available for Turnitin's AI
    detection endpoint. This stub always raises ProviderUnavailableError
    regardless of environment variables.
    """

    PROVIDER = "turnitin"

    def detect(self, text: str) -> dict[str, Any]:
        """Analyze text via Turnitin (stub — always raises).

        Args:
            text: The text to analyze.

        Raises:
            ProviderUnavailableError: Always — API docs unavailable.
        """
        raise ProviderUnavailableError(
            "Turnitin provider is not yet available — "
            "API documentation is needed before a real implementation can be built"
        )
