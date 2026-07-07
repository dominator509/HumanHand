"""Base detector types and abstract interface for all detector adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class DetectorResult:
    """Structured result from an AI-text detector.

    Fields:
        provider: Detector provider name (e.g. "local", "gptzero").
        model: Detector model or version name.
        score: AI-likelihood score between 0.0 and 1.0, or None.
        label: Human-readable classification ("human", "ai", "uncertain"), or None.
        raw_score_json: Optional provider-specific score breakdown as a dict.
    """

    provider: str
    model: str
    score: float | None = None
    label: str | None = None
    raw_score_json: dict[str, Any] | None = None


class DetectorError(Exception):
    """Base exception for all detector errors."""


class ProviderUnavailableError(DetectorError):
    """Raised when a detector provider is unavailable — missing key, no API docs, etc."""


class BaseDetector(ABC):
    """Abstract base for AI-text detector adapters.

    Each subclass wraps a specific provider (local heuristic, GPTZero,
    Originality, Copyleaks, Winston AI, Turnitin) and returns a dict
    matching the DetectorClient protocol from ``application.ports``.
    """

    @abstractmethod
    def detect(self, text: str) -> dict[str, Any]:
        """Analyze text and return a detector score record.

        Args:
            text: The text to analyze for AI likelihood.

        Returns:
            Dict with keys: provider, model, score, label, raw_score_json.

        Raises:
            DetectorError: On network, auth, or provider unavailability.
        """
