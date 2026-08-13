"""Scanner observatory package: synthetic control corpus and local scanner."""

from humanhand.infra.beacon.scanners.local_artifact_scanner import (
    SCANNER_NAME,
    ScannerRun,
    run_local_scan,
)
from humanhand.infra.beacon.scanners.synthetic_corpus import (
    ALLOWED_GROUPS,
    CorpusSample,
    load_synthetic_corpus,
)

__all__ = [
    "ALLOWED_GROUPS",
    "CorpusSample",
    "SCANNER_NAME",
    "ScannerRun",
    "load_synthetic_corpus",
    "run_local_scan",
]
