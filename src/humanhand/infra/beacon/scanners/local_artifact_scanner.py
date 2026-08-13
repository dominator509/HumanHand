"""Local advisory artifact scanner (EP-018).

Deterministic, zero-network scanning over synthetic corpus samples.

The offline default is deliberately honest: when no detector is
configured (the default), every run reports ``label="unknown"`` and
``score=None`` because no detector was consulted. No score is ever
fabricated.

When a detector object is provided — for example the real EP-006 local
detector ``humanhand.infra.detectors.local.LocalDetector``, or any
object exposing ``detect(text) -> dict`` with ``label`` and ``score``
keys — the scanner calls it once per sample and maps the label:
"human" -> "human", "ai" -> "ai", and everything else (including the
detector's "uncertain") -> "unknown". Detector failures propagate
unchanged; they are never converted into fabricated per-sample results.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Protocol, cast

from humanhand.infra.beacon.scanners.synthetic_corpus import CorpusSample

SCANNER_NAME = "local"
LABEL_UNKNOWN = "unknown"
_RUN_ID_PREFIX = "scan-"


class _DetectorClient(Protocol):
    """Minimal detector surface the scanner calls (see module docstring)."""

    def detect(self, text: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ScannerRun:
    """One advisory scan result for one corpus sample."""

    run_id: str  # deterministic hash of the scanner plus the full sample set
    scanner_name: str
    sample_id: str
    label: str  # "human" | "ai" | "unknown"
    score: float | None  # None = no detector was consulted (honest)


def _run_id_for(scanner_name: str, samples: tuple[CorpusSample, ...]) -> str:
    """Deterministic run id over scanner name plus every sample's id and text.

    Identical inputs produce the identical run id (the E2E test relies on
    this); no timestamp or randomness is involved.
    """
    payload = (
        scanner_name
        + "\x00"
        + "\x00".join(f"{sample.sample_id}\x00{sample.text}" for sample in samples)
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{_RUN_ID_PREFIX}{digest[:16]}"


def _map_detector_label(label: object) -> str:
    """Map a detector label onto the ScannerRun label vocabulary."""
    if label == "human":
        return "human"
    if label == "ai":
        return "ai"
    # "uncertain" (and anything unexpected) maps honestly to "unknown".
    return LABEL_UNKNOWN


def run_local_scan(
    samples: tuple[CorpusSample, ...], *, detector: object | None = None
) -> tuple[ScannerRun, ...]:
    """Run the deterministic advisory scan over the sample set.

    Args:
        samples: Corpus samples in deterministic order.
        detector: Optional detector object exposing ``detect(text) ->
            dict``. When None (the default offline path) every run is
            ``label="unknown"`` with ``score=None`` because no detector
            was consulted.

    Returns:
        One ScannerRun per sample, in sample order; every run shares the
        same deterministic run id.

    Raises:
        ValueError: If the sample set is empty.
        TypeError: If the detector returns a non-dict or a non-numeric
            score.
        Exception: Detector failures propagate unchanged.
    """
    if not samples:
        raise ValueError("cannot scan an empty corpus")
    client = cast(_DetectorClient | None, detector)
    run_id = _run_id_for(SCANNER_NAME, samples)
    runs: list[ScannerRun] = []
    for sample in samples:
        if client is None:
            runs.append(
                ScannerRun(
                    run_id=run_id,
                    scanner_name=SCANNER_NAME,
                    sample_id=sample.sample_id,
                    label=LABEL_UNKNOWN,
                    score=None,
                )
            )
            continue
        result = client.detect(sample.text)
        if not isinstance(result, dict):
            raise TypeError(f"detector detect() must return a dict, got {type(result).__name__}")
        score = result.get("score")
        if score is not None and not isinstance(score, (int, float)):
            raise TypeError("detector score must be a number or None")
        runs.append(
            ScannerRun(
                run_id=run_id,
                scanner_name=SCANNER_NAME,
                sample_id=sample.sample_id,
                label=_map_detector_label(result.get("label")),
                score=float(score) if score is not None else None,
            )
        )
    return tuple(runs)
