"""Project infra: deterministic public projections (EP-015 M3).

Exposes the optional Obsidian projection and the canonical JSON projection
of a source package. Both are explicit, user-triggered, non-authoritative
exports that omit internal ids (SPEC-012: public projections omit internal
ids by default; blueprint 9.7: the Obsidian projection is optional and
never syncs).
"""

from humanhand.infra.project.canonical_json import (
    CanonicalJsonProjection,
    build_canonical_json_projection,
)
from humanhand.infra.project.obsidian_projection import (
    PLAINTEXT_WARNING,
    ObsidianProjectionError,
    ObsidianProjectionResult,
    project_to_obsidian,
    slugify,
)

__all__ = [
    "CanonicalJsonProjection",
    "ObsidianProjectionError",
    "ObsidianProjectionResult",
    "PLAINTEXT_WARNING",
    "build_canonical_json_projection",
    "project_to_obsidian",
    "slugify",
]
