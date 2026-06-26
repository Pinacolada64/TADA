"""inventory.py — Unified inventory for players and containers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from items import BaseItem, ItemCategory


# Per-class slot limits: number of distinct item stacks a character can carry.
_CLASS_LIMITS: dict[str, int] = {
    'Wizard':   8,
    'Druid':    10,
    'Fighter':  14,
    'Paladin':  12,
    'Ranger':   12,
    'Thief':    10,
    'Archer':   10,
    'Assassin': 10,
    'Knight':   14,
}
_DEFAULT_LIMIT = 10


def class_inventory_limit(char_class) -> int:
    """Return the default slot limit for a given PlayerClass (or class name string)."""
    return _CLASS_LIMITS.get(str(char_class), _DEFAULT_LIMIT)


@dataclass
class InventoryEntry:
    item: 'BaseItem'
    quantity: int = 1
    # For spells: overrides item.charges so each carried copy tracks separately.
    # None means the item manages its own charge state.
    charges: int | None = None
    # For container items (bags of holding): their own sub-inventory.
    contents: 'Inventory | None' = None

    @property
    def is_container(self) -> bool:
        return (
            getattr(self.item, 'capacity', 0) > 0
            and self.contents is not None
        )

    def to_json(self) -> dict:
        d: dict = {
            'item_id':       getattr(self.item, 'id_number', None),
            'item_name':     getattr(self.item, 'name', ''),
            'item_category': str(getattr(self.item, 'category', '')),
            'quantity':      self.quantity,
        }
        if self.charges is not None:
            d['charges'] = self.charges
        if self.contents is not None:
            d['contents'] = self.contents.to_json()
        return d


class Inventory:
    """A player's (or container's) item collection.

    Slots hold InventoryEntry objects; identical items (same id_number) stack.
    capacity=None means no slot limit.
    """

    def __init__(self, capacity: int | None = None):
        self._entries: list[InventoryEntry] = []
        self.capacity = capacity

    # -----------------------------------------------------------------------
    # Mutation
    # -----------------------------------------------------------------------

    def add(self, item: 'BaseItem', quantity: int = 1,
            charges: int | None = None) -> bool:
        """Add item to inventory, stacking if an entry with the same id_number exists.

        Returns False when the inventory is full and no existing stack was found.
        """
        item_id = getattr(item, 'id_number', None)
        if item_id is not None:
            for entry in self._entries:
                if getattr(entry.item, 'id_number', None) == item_id:
                    entry.quantity += quantity
                    return True

        if self.capacity is not None and len(self._entries) >= self.capacity:
            return False

        entry = InventoryEntry(item=item, quantity=quantity, charges=charges)
        # Auto-create sub-inventory for containers
        if getattr(item, 'capacity', 0) > 0:
            entry.contents = Inventory(capacity=item.capacity)
        self._entries.append(entry)
        return True

    def remove(self, item: 'BaseItem', quantity: int = 1) -> bool:
        """Decrement quantity; remove entry when it reaches zero.

        Returns False if the item is not present or there is insufficient quantity.
        """
        item_id = getattr(item, 'id_number', None)
        for i, entry in enumerate(self._entries):
            if item_id is not None and getattr(entry.item, 'id_number', None) == item_id:
                if entry.quantity < quantity:
                    return False
                entry.quantity -= quantity
                if entry.quantity == 0:
                    self._entries.pop(i)
                return True
        return False

    # -----------------------------------------------------------------------
    # Query
    # -----------------------------------------------------------------------

    def find(self, *, name: str | None = None, item_id: int | None = None,
             category: str | None = None) -> list[InventoryEntry]:
        """Return all entries matching the given criteria (AND logic)."""
        results = []
        for entry in self._entries:
            if item_id is not None and getattr(entry.item, 'id_number', None) != item_id:
                continue
            if name is not None and getattr(entry.item, 'name', '').lower() != name.lower():
                continue
            if category is not None and str(getattr(entry.item, 'category', '')) != category:
                continue
            results.append(entry)
        return results

    def entries(self, category: str | None = None) -> list[InventoryEntry]:
        """All entries, optionally filtered by category string."""
        if category is None:
            return list(self._entries)
        return [e for e in self._entries
                if str(getattr(e.item, 'category', '')) == category]

    def is_full(self) -> bool:
        return self.capacity is not None and len(self._entries) >= self.capacity

    def slot_count(self) -> int:
        return len(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries)

    def __bool__(self) -> bool:
        return bool(self._entries)

    # -----------------------------------------------------------------------
    # Serialization
    # -----------------------------------------------------------------------

    def to_json(self) -> list[dict]:
        return [e.to_json() for e in self._entries]

    @classmethod
    def from_json(cls, data: list | None, capacity: int | None = None) -> 'Inventory':
        """Reconstruct an Inventory from serialized data.

        Item objects are reconstructed as lightweight Items; full resolution
        against the item database can be done later when it is available.
        """
        from items import Item, ItemCategory
        inv = cls(capacity=capacity)
        for d in (data or []):
            cat_str = d.get('item_category', '')
            try:
                category = ItemCategory(cat_str) if cat_str else ItemCategory.ITEM
            except ValueError:
                category = ItemCategory.ITEM
            item = Item(
                id_number=d.get('item_id', 0),
                name=d.get('item_name', ''),
                category=category,
            )
            entry = InventoryEntry(
                item=item,
                quantity=d.get('quantity', 1),
                charges=d.get('charges'),
            )
            if 'contents' in d:
                entry.contents = cls.from_json(d['contents'])
            inv._entries.append(entry)
        return inv
