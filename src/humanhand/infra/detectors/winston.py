"""Winston AI detector stub — requires WINSTON_API_KEY."""

from __future__ import annotations

import os
from typing import Any

from humanhand.infra.detectors.base import BaseDetector, ProviderUnavailableError


class WinstonDetector(BaseDetector):
    """Winston AI-text detector adapter (stub).

    Requires the WINSTON_API_KEY environment variable. API documentation
    is needed before a real implementation can be built.
    """

    PROVIDER = "winston"

    def detect(self, text: str) -> dict[str, Any]:
        """Analyze text via Winston AI (stub — always raises).

        Args:
            text: The text to analyze.

        Raises:
            ProviderUnavailableError: Always, since the API is not documented.
        """
        if not os.getenv("WINSTON_API_KEY"):
            raise ProviderUnavailableError(
                "Winston provider requires a WINSTON_API_KEY environment variable"
            )
        raise ProviderUnavailableError(
            "Winston provider requires provider API documentation "
            "before a real implementation can be built"
        )
