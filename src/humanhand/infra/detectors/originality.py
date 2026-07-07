"""Originality.ai detector stub — requires ORIGINALITY_API_KEY."""

from __future__ import annotations

import os
from typing import Any

from humanhand.infra.detectors.base import BaseDetector, ProviderUnavailableError


class OriginalityDetector(BaseDetector):
    """Originality.ai AI-text detector adapter (stub).

    Requires the ORIGINALITY_API_KEY environment variable. API documentation
    is needed before a real implementation can be built.
    """

    PROVIDER = "originality"

    def detect(self, text: str) -> dict[str, Any]:
        """Analyze text via Originality.ai (stub — always raises).

        Args:
            text: The text to analyze.

        Raises:
            ProviderUnavailableError: Always, since the API is not documented.
        """
        if not os.getenv("ORIGINALITY_API_KEY"):
            raise ProviderUnavailableError(
                "Originality provider requires an ORIGINALITY_API_KEY environment variable"
            )
        raise ProviderUnavailableError(
            "Originality provider requires provider API documentation "
            "before a real implementation can be built"
        )
