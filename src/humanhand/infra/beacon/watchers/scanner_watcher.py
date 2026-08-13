"""Read-only scanner drift watcher for the Research Beacon (blueprint 13.5).

Statistical detector results are advisory. This watcher only OBSERVES repeated
runs over the synthetic control corpus; it never optimizes detector scores and
never tunes outputs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

TRIGGER_TYPE = "repeated_synthetic_scanner_drift"

SYNTHETIC_CORPUS_NAME = "synthetic_control_corpus"


@dataclass(frozen=True)
class ScannerObservation:
    """One detected drift between consecutive runs over the same corpus."""

    corpus_name: str
    drift: float
    trigger_type: str


def _mean(values: tuple[float, ...]) -> float | None:
    """Mean of one run's values; None when the run has no values."""
    if not values:
        return None
    return math.fsum(values) / len(values)


def watch_scanner_drift(
    runs: tuple[tuple[float, ...], ...],
    *,
    threshold: float = 0.1,
) -> tuple[ScannerObservation, ...]:
    """Emit an observation for each consecutive run pair whose mean
    difference exceeds ``threshold``.

    - Every inner tuple is one run's detector scores over the same synthetic
      control corpus (``SYNTHETIC_CORPUS_NAME``).
    - Runs with no values are skipped (their mean is undefined).
    - Deterministic: identical input produces identical observations, in run
      order.
    """
    observations: list[ScannerObservation] = []
    for previous, current in zip(runs, runs[1:], strict=False):
        previous_mean = _mean(previous)
        current_mean = _mean(current)
        if previous_mean is None or current_mean is None:
            continue
        drift = abs(previous_mean - current_mean)
        if drift > threshold:
            observations.append(
                ScannerObservation(
                    corpus_name=SYNTHETIC_CORPUS_NAME,
                    drift=drift,
                    trigger_type=TRIGGER_TYPE,
                )
            )
    return tuple(observations)
