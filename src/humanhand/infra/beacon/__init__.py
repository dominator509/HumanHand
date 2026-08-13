"""Research Beacon infrastructure package (blueprint 13.3-13.5).

The beacon observes parser/exporter dependencies and repeated scanner drift
locally, stores immutable evidence snapshots, and can query a configured
OpenAI-compatible research endpoint through a real, schema-validated adapter.
"""

from humanhand.infra.beacon.model_selector import PREFERRED_MODELS, select_model
from humanhand.infra.beacon.proposal_store import ProposalStore, ProposalStoreError
from humanhand.infra.beacon.snapshot_store import (
    SnapshotStore,
    SnapshotStoreError,
    dumps_stable,
)
from humanhand.infra.beacon.source_registry import (
    DEFAULT_SOURCES,
    RegisteredSource,
    sources_for_trigger,
)
from humanhand.infra.beacon.watchers import (
    DependencyObservation,
    ScannerObservation,
    watch_dependencies,
    watch_scanner_drift,
)
from humanhand.infra.beacon.xai_research_client import (
    XaiResearchClient,
    XaiResearchError,
)

__all__ = [
    "DEFAULT_SOURCES",
    "DependencyObservation",
    "PREFERRED_MODELS",
    "ProposalStore",
    "ProposalStoreError",
    "RegisteredSource",
    "ScannerObservation",
    "SnapshotStore",
    "SnapshotStoreError",
    "XaiResearchClient",
    "XaiResearchError",
    "dumps_stable",
    "select_model",
    "sources_for_trigger",
    "watch_dependencies",
    "watch_scanner_drift",
]
