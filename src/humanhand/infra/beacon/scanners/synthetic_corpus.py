"""Synthetic control corpus for the scanner observatory (EP-018).

The corpus is a set of original, invented text samples grouped into the
blueprint 13.5 control groups (authentic human writing, public-domain
historical style, base-model synthetic writing, current Human Hand
output, and mixed human/AI coauthored samples). No real user data is ever
included; every sample in the repository fixture is invented for this
corpus.

The corpus lives under ``tests/fixtures/beacon/synthetic-corpus`` and is
described by ``corpus-manifest.json``: a ``{"schema_version": 1,
"samples": [{"sample_id": ..., "group": ..., "file": ...}, ...]}``
document. Loading is deterministic: samples are returned in manifest
order, and duplicate sample ids are rejected.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from humanhand.infra.files import read_text_strict

# Control-group labels (blueprint 13.5). The authoritative set: a manifest
# entry naming any other group is rejected rather than guessed at.
ALLOWED_GROUPS = frozenset(
    {
        "authentic_human",
        "public_domain_style",
        "base_model_synthetic",
        "humanhand_output",
        "coauthored",
    }
)

EXPECTED_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CorpusSample:
    """One synthetic sample: an id, a control-group label, and its text."""

    sample_id: str
    group: str  # one of ALLOWED_GROUPS
    text: str


def load_synthetic_corpus(root: str | Path) -> tuple[CorpusSample, ...]:
    """Load the corpus manifest and its named text files.

    Args:
        root: Directory containing ``corpus-manifest.json`` and the named
            text files.

    Returns:
        Samples in deterministic manifest order.

    Raises:
        FileIOError: If the manifest or any named text file is missing,
            unreadable, contains a UTF-8 BOM, is not valid UTF-8, or is
            empty or whitespace-only.
        ValueError: If the manifest shape is invalid, a sample id is
            duplicated, or a group is not in ALLOWED_GROUPS.
    """
    root_path = Path(root)
    manifest_path = root_path / "corpus-manifest.json"
    manifest = json.loads(read_text_strict(manifest_path))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise ValueError(
            f"corpus manifest {manifest_path} must be an object with "
            f"schema_version {EXPECTED_SCHEMA_VERSION}"
        )
    entries = manifest.get("samples")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"corpus manifest {manifest_path} must contain a non-empty 'samples' list")
    samples: list[CorpusSample] = []
    seen_ids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"corpus manifest {manifest_path} entries must be objects")
        sample_id = entry.get("sample_id")
        group = entry.get("group")
        file_name = entry.get("file")
        if not isinstance(sample_id, str) or not sample_id:
            raise ValueError(f"corpus manifest {manifest_path} entries need a non-empty sample_id")
        if not isinstance(group, str) or group not in ALLOWED_GROUPS:
            raise ValueError(f"corpus sample {sample_id!r} uses unknown group {group!r}")
        if not isinstance(file_name, str) or not file_name:
            raise ValueError(f"corpus sample {sample_id!r} must name a file")
        if sample_id in seen_ids:
            raise ValueError(f"corpus manifest {manifest_path} duplicates sample id {sample_id!r}")
        seen_ids.add(sample_id)
        text = read_text_strict(root_path / file_name)
        samples.append(CorpusSample(sample_id=sample_id, group=group, text=text))
    return tuple(samples)
