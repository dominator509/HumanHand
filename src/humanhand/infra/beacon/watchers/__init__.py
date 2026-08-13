"""Research Beacon local watchers (offline, read-only observations).

Both watchers operate strictly on local inputs: a parsed uv.lock dict and
synthetic scanner run tuples. Neither performs network access.
"""

from humanhand.infra.beacon.watchers.dependency_watcher import (
    DependencyObservation,
    watch_dependencies,
)
from humanhand.infra.beacon.watchers.scanner_watcher import (
    ScannerObservation,
    watch_scanner_drift,
)

__all__ = [
    "DependencyObservation",
    "ScannerObservation",
    "watch_dependencies",
    "watch_scanner_drift",
]
