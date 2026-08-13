"""Deterministic relationship extraction between registered entities.

Relationships are extracted with pure string rules: within each claim
proposition, the two earliest occurrences of registered entity names
define a subject/object pair, and the exact words between them become the
predicate. No semantics, no model, and no invented predicates.
"""

from __future__ import annotations

from dataclasses import dataclass

from humanhand.domain.claims_v2 import build_claims_from_package
from humanhand.domain.entities import Entity, EntityRegistry
from humanhand.domain.source_package import SourcePackage


@dataclass(frozen=True)
class Relationship:
    """One deterministic relationship between two registered entities."""

    relationship_id: str
    subject_id: str
    predicate: str
    object_id: str
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class RelationshipSet:
    """Immutable, deterministic set of extracted relationships."""

    relationships: tuple[Relationship, ...]


def build_relationships(
    package: SourcePackage,
    registry: EntityRegistry,
    *,
    max_relationships: int = 200,
) -> RelationshipSet:
    """Extract relationships deterministically from a source package.

    Rules (deterministic, no model):
    - For each claim proposition that contains at least two registered
      entity names, the subject is the entity of the earliest occurrence
      and the object is the earliest occurrence of a different entity name.
      Occurrences are located by exact, case-sensitive substring search;
      ties in position keep registry order, and each position contributes
      at most one occurrence.
    - The predicate is the exact words strictly between the two
      occurrences, lowercased and joined with single spaces; punctuation
      stays as written and nothing is invented. When no words sit between
      the two occurrences (adjacent entities), the predicate is empty and
      no relationship is created.
    - ``relationship_id`` is ``r{n}`` in first-seen claim order;
      ``evidence_refs`` is the claim's source span ids.
    - The set is capped at ``max_relationships`` in first-seen order.
    """
    claims, _ = build_claims_from_package(package)
    relationships: list[Relationship] = []
    for claim in claims:
        occurrences: list[tuple[int, Entity]] = []
        for entity in registry.entities:
            position = claim.canonical_proposition.find(entity.name)
            if position >= 0:
                occurrences.append((position, entity))
        occurrences.sort(key=lambda item: item[0])
        distinct: list[tuple[int, Entity]] = []
        seen_positions: set[int] = set()
        for position, entity in occurrences:
            if position in seen_positions:
                continue
            seen_positions.add(position)
            distinct.append((position, entity))
        if len(distinct) < 2:
            continue
        first_position, first_entity = distinct[0]
        second_pair: tuple[int, Entity] | None = None
        for position, entity in distinct[1:]:
            if entity.entity_id != first_entity.entity_id:
                second_pair = (position, entity)
                break
        if second_pair is None:
            continue
        second_position, second_entity = second_pair
        between = claim.canonical_proposition[
            first_position + len(first_entity.name) : second_position
        ]
        predicate = " ".join(between.split()).lower()
        if not predicate:
            continue
        if len(relationships) >= max_relationships:
            break
        relationships.append(
            Relationship(
                relationship_id=f"r{len(relationships) + 1}",
                subject_id=first_entity.entity_id,
                predicate=predicate,
                object_id=second_entity.entity_id,
                evidence_refs=claim.source_evidence_refs,
            )
        )
    return RelationshipSet(relationships=tuple(relationships))


def relationships_to_payload(relationships: RelationshipSet) -> dict[str, object]:
    """Render a relationship set as a plain JSON-ready mapping."""
    return {
        "relationships": [
            {
                "relationship_id": relationship.relationship_id,
                "subject_id": relationship.subject_id,
                "predicate": relationship.predicate,
                "object_id": relationship.object_id,
                "evidence_refs": list(relationship.evidence_refs),
            }
            for relationship in relationships.relationships
        ],
    }
