"""Detector provider adapters — local heuristic and third-party stubs."""

from __future__ import annotations

from humanhand.infra.detectors.base import (
    BaseDetector,
    DetectorError,
    DetectorResult,
    ProviderUnavailableError,
)
from humanhand.infra.detectors.copyleaks import CopyleaksDetector
from humanhand.infra.detectors.gptzero import GptZeroDetector
from humanhand.infra.detectors.local import LocalDetector
from humanhand.infra.detectors.originality import OriginalityDetector
from humanhand.infra.detectors.turnitin import TurnitinDetector
from humanhand.infra.detectors.winston import WinstonDetector

__all__ = [
    "BaseDetector",
    "CopyleaksDetector",
    "DetectorError",
    "DetectorResult",
    "GptZeroDetector",
    "LocalDetector",
    "OriginalityDetector",
    "ProviderUnavailableError",
    "TurnitinDetector",
    "WinstonDetector",
    "create_detector",
]

_DETECTOR_REGISTRY: dict[str, type[BaseDetector]] = {
    "local": LocalDetector,
    "gptzero": GptZeroDetector,
    "originality": OriginalityDetector,
    "copyleaks": CopyleaksDetector,
    "winston": WinstonDetector,
    "turnitin": TurnitinDetector,
}


def create_detector(provider: str) -> BaseDetector:
    """Create a detector instance by provider name.

    Args:
        provider: One of the known detector provider names.

    Returns:
        An instance of the matching BaseDetector subclass.

    Raises:
        ValueError: If the provider name is not recognised.
    """
    cls = _DETECTOR_REGISTRY.get(provider)
    if cls is None:
        raise ValueError(f"Unknown detector provider: {provider}")
    return cls()
