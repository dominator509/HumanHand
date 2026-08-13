"""Read-only dependency update watcher for the Research Beacon.

Watches a parsed uv.lock-shaped dict (``tomllib.load`` output) for packages in
``WATCHED_PACKAGES``. When ``known_versions`` reports a strictly newer version
for a watched package present in the lock, an observation is emitted.

Version comparison is deterministic and offline: each version string is
reduced to its numeric components (every digit run, in order) and compared
component-wise. This is a documented heuristic, not full PEP 440.

The watcher only OBSERVES; it never modifies the lock or installs anything.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TRIGGER_TYPE = "parser_exporter_dependency_update"

WATCHED_PACKAGES: frozenset[str] = frozenset(
    {"pypdf", "defusedxml", "cryptography", "reportlab", "typer", "pydantic"}
)


@dataclass(frozen=True)
class DependencyObservation:
    """One detected dependency update for a watched package."""

    package: str
    current_version: str
    latest_known: str
    trigger_type: str


def _numeric_components(version: str) -> tuple[int, ...]:
    """Reduce a version string to its numeric components, in order."""
    return tuple(int(part) for part in re.findall(r"\d+", version))


def _is_newer(candidate: str, baseline: str) -> bool:
    return _numeric_components(candidate) > _numeric_components(baseline)


def watch_dependencies(
    lock_data: dict[str, object],
    *,
    known_versions: dict[str, str] | None = None,
) -> tuple[DependencyObservation, ...]:
    """Check a parsed uv.lock dict for newer versions of watched packages.

    - ``known_versions`` is the operator-supplied registry of latest known
      versions; without it the watcher cannot detect updates and returns no
      observations (it never invents versions).
    - Malformed lock entries (non-dict, or missing string name/version) are
      ignored; only well-formed entries for watched packages are considered.
    - An observation is emitted only when the known version is strictly newer
      than the locked version. Deterministic: sorted package order.
    """
    if known_versions is None:
        return ()
    packages = lock_data.get("package")
    if not isinstance(packages, list):
        return ()
    locked: dict[str, str] = {}
    for entry in packages:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        version = entry.get("version")
        if isinstance(name, str) and isinstance(version, str):
            locked[name] = version

    candidates = WATCHED_PACKAGES.intersection(set(locked)).intersection(set(known_versions))
    observations: list[DependencyObservation] = []
    for package in sorted(candidates):
        current_version = locked[package]
        latest_known = known_versions[package]
        if _is_newer(latest_known, baseline=current_version):
            observations.append(
                DependencyObservation(
                    package=package,
                    current_version=current_version,
                    latest_known=latest_known,
                    trigger_type=TRIGGER_TYPE,
                )
            )
    return tuple(observations)
