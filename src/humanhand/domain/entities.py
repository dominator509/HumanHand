"""Deterministic entity extraction from source packages.

Entities are extracted with pure string rules: capitalized multi-word
phrases in claim propositions and quotation attributions, plus author
names from author-year citations. No semantic guesswork and no model;
entity types are never invented beyond what the rules prove.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from humanhand.domain.claims_v2 import build_claims_from_package
from humanhand.domain.source_package import SourcePackage
from humanhand.domain.types import DomainError

#: Two or more consecutive capitalized words (e.g. "Acme Corporation").
_CAPITALIZED_PHRASE_RE = re.compile(r"[A-Z][a-z]+(?: [A-Z][a-z]+)+")


class EntityType(StrEnum):
    """Deterministic entity kinds."""

    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    DATE = "date"
    PRODUCT = "product"
    CONCEPT = "concept"
    OTHER = "other"


@dataclass(frozen=True)
class Entity:
    """One extracted entity with its evidence references."""

    entity_id: str
    name: str
    entity_type: EntityType = EntityType.OTHER
    aliases: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class EntityRegistry:
    """Immutable, deterministic registry of extracted entities."""

    entities: tuple[Entity, ...]

    def by_id(self, entity_id: str) -> Entity:
        """Return the entity with the given id, or raise KeyError."""
        for entity in self.entities:
            if entity.entity_id == entity_id:
                return entity
        raise KeyError(entity_id)

    def by_name(self, name: str) -> Entity | None:
        """Return the entity with the exact (case-sensitive) name, or None."""
        for entity in self.entities:
            if entity.name == name:
                return entity
        return None


def build_entities_from_package(
    package: SourcePackage, *, max_entities: int = 100
) -> EntityRegistry:
    """Extract entities deterministically from a source package.

    Rules (deterministic, no model):
    - Capitalized multi-word sequences (regex ``[A-Z][a-z]+(?: [A-Z][a-z]+)+``)
      in claim propositions, then in quotation attributions, are entity
      candidates of type OTHER. The type is never guessed.
    - Author names from author-year citations (kind ``author_year``; the
      text before the first comma, e.g. "Smith" in "Smith, 2020") are
      entity candidates of type PERSON; the citation itself is the only
      evidence for that typing.
    - Any candidate whose name appears (exact substring, case-sensitive)
      inside an author-year citation text is typed PERSON on the strength
      of that citation alone. This is attribution evidence, not inference
      beyond what the citation says.
    - ``entity_id`` is ``e{n}`` in first-seen order (claims in document
      order, then quotation attributions, then citation names); duplicates
      by exact name keep the first-seen slot.
    - ``aliases`` is always empty (never invented).
    - ``evidence_refs`` lists every protected span id whose text mentions
      the entity name (exact, case-sensitive substring match).
    - The registry is capped at ``max_entities`` in first-seen order.
    """
    candidates: list[tuple[str, EntityType]] = []
    claims, _ = build_claims_from_package(package)
    for claim in claims:
        for match in _CAPITALIZED_PHRASE_RE.finditer(claim.canonical_proposition):
            candidates.append((match.group(0), EntityType.OTHER))
    for quotation in package.evidence.quotations:
        for match in _CAPITALIZED_PHRASE_RE.finditer(quotation.attribution):
            candidates.append((match.group(0), EntityType.OTHER))

    author_year_texts: list[str] = []
    for citation in package.evidence.citations:
        if citation.kind != "author_year":
            continue
        author_year_texts.append(citation.text)
        name_part = citation.text.split(",", 1)[0].strip()
        if name_part:
            candidates.append((name_part, EntityType.PERSON))

    first_seen: dict[str, EntityType] = {}
    for name, entity_type in candidates:
        if name not in first_seen:
            first_seen[name] = entity_type

    for name in first_seen:
        if any(name in text for text in author_year_texts):
            first_seen[name] = EntityType.PERSON

    ordered_names = list(first_seen.keys())[:max_entities]
    span_texts = tuple((span.span_id, span.text) for span in package.evidence.protected_spans.spans)
    entities: list[Entity] = []
    for index, name in enumerate(ordered_names, start=1):
        evidence_refs = tuple(span_id for span_id, text in span_texts if name in text)
        entities.append(
            Entity(
                entity_id=f"e{index}",
                name=name,
                entity_type=first_seen[name],
                aliases=(),
                evidence_refs=evidence_refs,
            )
        )
    return EntityRegistry(entities=tuple(entities))


def registry_to_payload(registry: EntityRegistry) -> dict[str, object]:
    """Render an entity registry as a plain JSON-ready mapping."""
    return {
        "entities": [
            {
                "entity_id": entity.entity_id,
                "name": entity.name,
                "entity_type": entity.entity_type.value,
                "aliases": list(entity.aliases),
                "evidence_refs": list(entity.evidence_refs),
            }
            for entity in registry.entities
        ],
    }


def registry_from_payload(payload: dict[str, object]) -> EntityRegistry:
    """Deserialize and strictly validate an entity registry payload.

    Raises DomainError on a missing or malformed ``entities`` list or on
    any unknown entity type.
    """
    raw_entities = payload.get("entities")
    if not isinstance(raw_entities, list):
        raise DomainError("Entity registry payload must include an entities list")
    entities: list[Entity] = []
    for item in raw_entities:
        if not isinstance(item, dict):
            raise DomainError("Each entity must be an object")
        entity_id = item.get("entity_id")
        if not isinstance(entity_id, str):
            raise DomainError("entity_id must be a string")
        name = item.get("name")
        if not isinstance(name, str):
            raise DomainError("name must be a string")
        raw_entity_type = item.get("entity_type")
        if not isinstance(raw_entity_type, str):
            raise DomainError("entity_type must be a string")
        try:
            entity_type = EntityType(raw_entity_type)
        except ValueError as exc:
            raise DomainError(f"Unknown entity type: {raw_entity_type!r}") from exc
        aliases = item.get("aliases")
        if not isinstance(aliases, list) or not all(isinstance(a, str) for a in aliases):
            raise DomainError("aliases must be a list of strings")
        evidence_refs = item.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not all(
            isinstance(ref, str) for ref in evidence_refs
        ):
            raise DomainError("evidence_refs must be a list of strings")
        entities.append(
            Entity(
                entity_id=entity_id,
                name=name,
                entity_type=entity_type,
                aliases=tuple(aliases),
                evidence_refs=tuple(evidence_refs),
            )
        )
    return EntityRegistry(entities=tuple(entities))
