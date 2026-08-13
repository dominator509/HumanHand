"""Unit tests for the deterministic metadata inventory."""

from __future__ import annotations

from humanhand.domain.metadata_inventory import (
    MetadataInventory,
    MetadataItem,
    inventory_from_items,
)


class TestMetadataInventory:
    def test_empty_default(self) -> None:
        inventory = MetadataInventory()
        assert inventory.items == ()
        assert inventory.to_payload() == {"count": 0, "items": []}

    def test_first_seen_order_preserved(self) -> None:
        inventory = inventory_from_items(
            (
                MetadataItem(key="title", kind="front_matter", value="Doc"),
                MetadataItem(key="author", kind="front_matter", value="Ana"),
            )
        )
        assert [item.key for item in inventory.items] == ["title", "author"]

    def test_duplicates_removed(self) -> None:
        inventory = inventory_from_items(
            (
                MetadataItem(key="title", kind="front_matter", value="Doc"),
                MetadataItem(key="title", kind="front_matter", value="Duplicate"),
            )
        )
        assert len(inventory.items) == 1
        assert inventory.items[0].value == "Doc"

    def test_payload_shape(self) -> None:
        inventory = inventory_from_items(
            (MetadataItem(key="block_id", kind="obsidian_property", value="^abc123"),)
        )
        payload = inventory.to_payload()
        assert payload["count"] == 1
        assert payload["items"] == [
            {"key": "block_id", "kind": "obsidian_property", "value": "^abc123"}
        ]
