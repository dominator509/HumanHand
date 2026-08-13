"""Bundle-relative loading of the curated lexicon resources.

The domain layer stays pure; file I/O for the bundled resources lives here.
"""

from __future__ import annotations

import json
from pathlib import Path

from humanhand.domain.lexical_types import (
    RulesetVersion,
    protected_terms_from_resource,
    ruleset_from_resource,
)
from humanhand.domain.types import DomainError

_LEXICONS_DIR = Path(__file__).resolve().parent.parent.parent / "resources" / "lexicons"


def _load_resource(name: str) -> dict[str, object]:
    payload = json.loads((_LEXICONS_DIR / name).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Lexicon resource {name!r} must be an object")
    return payload


def load_bundled_rules() -> RulesetVersion:
    """Load the curated core-en rules resource (no network)."""
    return ruleset_from_resource(_load_resource("core-en-rules.json"))


def load_protected_terms(domain: str) -> frozenset[str]:
    """Load a protected-terms resource for general/medical/legal."""
    names = {
        "general": "protected-general-terms.json",
        "medical": "protected-medical-terms.json",
        "legal": "protected-legal-terms.json",
    }
    if domain not in names:
        raise DomainError(f"Unknown protected-term domain {domain!r}")
    return protected_terms_from_resource(_load_resource(names[domain]))
