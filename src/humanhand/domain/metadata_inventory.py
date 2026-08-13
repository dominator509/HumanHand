"""Deterministic metadata inventory — document-embedded metadata only."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetadataItem:
    """One metadata entry discovered inside a container.

    ``key`` and ``value`` are the container's own metadata strings. Metadata
    is a separate channel from document content and never enters canonical
    text unless explicitly promoted.
    """

    key: str
    kind: str
    value: str


@dataclass(frozen=True)
class MetadataInventory:
    """Ordered, first-seen metadata inventory for an import."""

    items: tuple[MetadataItem, ...] = ()

    def to_payload(self) -> dict[str, object]:
        """Render the inventory as a plain JSON-ready mapping."""
        return {
            "count": len(self.items),
            "items": [
                {"key": item.key, "kind": item.kind, "value": item.value} for item in self.items
            ],
        }


def inventory_from_items(items: tuple[MetadataItem, ...]) -> MetadataInventory:
    """Build an inventory, preserving first-seen order and rejecting duplicates."""
    seen: set[tuple[str, str]] = set()
    unique: list[MetadataItem] = []
    for item in items:
        key = (item.kind, item.key)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return MetadataInventory(items=tuple(unique))
