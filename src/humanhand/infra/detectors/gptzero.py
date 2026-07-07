"""GPTZero detector stub — requires GPTZERO_API_KEY and provider API docs."""

from __future__ import annotations

import os
from typing import Any

from humanhand.infra.detectors.base import BaseDetector, ProviderUnavailableError


class GptZeroDetector(BaseDetector):
    """GPTZero AI-text detector adapter (stub).

    Requires the GPTZERO_API_KEY environment variable. API documentation
    is needed before a real implementation can be built.
    """

    PROVIDER = "gptzero"

    def detect(self, text: str) -> dict[str, Any]:
        """Analyze text via GPTZero (stub — always raises).

        Args:
            text: The text to analyze.

        Raises:
            ProviderUnavailableError: Always, since the API is not documented.
        """
        if not os.getenv("GPTZERO_API_KEY"):
            raise ProviderUnavailableError(
                "GPTZero provider requires a GPTZERO_API_KEY environment variable"
            )
        raise ProviderUnavailableError(
            "GPTZero provider requires provider API documentation "
            "before a real implementation can be built"
        )
