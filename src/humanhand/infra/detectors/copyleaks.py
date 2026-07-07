"""Copyleaks detector stub — requires COPYLEAKS_API_KEY."""

from __future__ import annotations

import os
from typing import Any

from humanhand.infra.detectors.base import BaseDetector, ProviderUnavailableError


class CopyleaksDetector(BaseDetector):
    """Copyleaks AI-text detector adapter (stub).

    Requires the COPYLEAKS_API_KEY environment variable. API documentation
    is needed before a real implementation can be built.
    """

    PROVIDER = "copyleaks"

    def detect(self, text: str) -> dict[str, Any]:
        """Analyze text via Copyleaks (stub — always raises).

        Args:
            text: The text to analyze.

        Raises:
            ProviderUnavailableError: Always, since the API is not documented.
        """
        if not os.getenv("COPYLEAKS_API_KEY"):
            raise ProviderUnavailableError(
                "Copyleaks provider requires a COPYLEAKS_API_KEY environment variable"
            )
        raise ProviderUnavailableError(
            "Copyleaks provider requires provider API documentation "
            "before a real implementation can be built"
        )
