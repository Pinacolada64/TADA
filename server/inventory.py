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

# SPUR.MISC6.S locker: `if zt>9 print "The locker is full!"` -- fixed 10-slot
# capacity for everyone, unlike inventory (which varies by class).
LOCKER_CAPACITY = 10

PACK_FULL_MESSAGE = "Your pack is full. You can't carry any more."

# Lazy cache for Inventory.from_json()'s item_kind backfill -- loaded once
# per process, not per call, since rations.json never changes at runtime.
_RATIONS_BY_NUMBER: dict | None = None


def _rations_by_number() -> dict:
    global _RATIONS_BY_NUMBER
    if _RATIONS_BY_NUMBER is None:
        from items import Rations
        data = Rations.read_rations('rations.json') or []
        _RATIONS_BY_NUMBER = {
            r['number']: r for r in data
            if isinstance(r, dict) and 'number' in r
        }
    return _RATIONS_BY_NUMBER


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
        # flags carries data (e.g. ammo's rounds/damage/used_with) beyond
        # what item_id/name/category can reconstruct -- dropping it meant
        # every item's flags reset to [] on the very next save/load cycle,
        # regardless of what a shop set them to at purchase time (see
        # commands/use.py's _apply_item docstring for the ammo-loading bug
        # this caused in practice).
        flags = getattr(self.item, 'flags', None)
        if flags:
            d['item_flags'] = flags
        # rations.json entries carry a "kind" (food/drink/cursed) --
        # commands/eat.py and commands/drink.py both filter inventory by
        # item.kind, so it has to survive a save/load round trip or a
        # carried ration silently stops showing up in EAT/DRINK the next
        # time the player connects (found live: Ryan reported "you have
        # nothing matching bread" for a loaf of bread that was genuinely
        # in inventory -- from_json() rebuilds every persisted item as a
        # plain Item(), which has no .kind at all unless one is passed in,
        # and to_json() never wrote one out to begin with).
        kind = getattr(self.item, 'kind', None)
        if kind:
            d['item_kind'] = kind
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
        return True

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

            item_kind = d.get('item_kind')
            item_name = d.get('item_name', '')
            if item_kind is None:
                # Heals save files written before item_kind existed (or by
                # an acquisition path that predates it, e.g. a very old
                # editplayer grant) -- without this, a ration saved back
                # then reloaded still has no .kind and silently vanishes
                # from EAT/DRINK's filter forever, even after the
                # to_json()/from_json() round-trip fix (found live: Ryan's
                # test character still couldn't eat bread that was granted
                # before that fix landed). Matched by id_number AND name
                # (case-insensitive) against rations.json, not id_number
                # alone -- item numbering is only unique within its own
                # category (weapons/items/rations each start back at 1),
                # so a bare id_number match could misidentify an unrelated
                # weapon/object that happens to share a number with a
                # ration.
                ration = _rations_by_number().get(d.get('item_id'))
                if ration and str(ration.get('name', '')).lower() == item_name.lower():
                    item_kind = ration.get('kind')
                    if item_kind == 'food':
                        category = ItemCategory.FOOD
                    elif item_kind == 'drink':
                        category = ItemCategory.DRINK

            item = Item(
                id_number=d.get('item_id', 0),
                name=item_name,
                category=category,
                flags=d.get('item_flags') or [],
                kind=item_kind,
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
