"""inventory.py — Unified inventory for players and containers."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
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
        data = Rations.read_rations(Path(__file__).parent / 'rations.json') or []
        _RATIONS_BY_NUMBER = {
            r['number']: r for r in data
            if isinstance(r, dict) and 'number' in r
        }
    return _RATIONS_BY_NUMBER


# Same lazy-cache pattern as _rations_by_number(), for item_type's backfill
# below -- objects.json never changes at runtime either.
_OBJECTS_BY_NUMBER: dict | None = None


def _objects_by_number() -> dict:
    global _OBJECTS_BY_NUMBER
    if _OBJECTS_BY_NUMBER is None:
        import json
        try:
            raw = json.loads((Path(__file__).parent / 'objects.json').read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            raw = {}
        items = raw.get('items', []) if isinstance(raw, dict) else raw
        _OBJECTS_BY_NUMBER = {
            o['number']: o for o in items
            if isinstance(o, dict) and 'number' in o
        }
    return _OBJECTS_BY_NUMBER


def class_inventory_limit(char_class) -> int:
    """Return the default slot limit for a given PlayerClass (or class name string)."""
    return _CLASS_LIMITS.get(str(char_class), _DEFAULT_LIMIT)


@dataclass
class InventoryEntry:
    item: 'BaseItem'
    quantity: int = 1
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
        # item_type (item_system.ItemType -- armor/book/compass/cursed/
        # shield/treasure) is a *separate* property from item_kind above
        # (rations' food/drink/cursed) -- they cover different, mostly
        # non-overlapping item categories and both are real, independently
        # used fields (commands/eat.py/drink.py filter on .kind;
        # commands/wear.py/use.py/read.py filter on .type), not a typo of
        # one another. Dropping .type meant an editplayer-granted armor/
        # shield item (or any objects.json item with a type) silently
        # stopped being WEAR/USE/READ-able after one save/load round trip
        # even though it was still sitting right there in inventory --
        # found live testing commands/wear.py's active_armor_id addition
        # (2026-08-08): a freshly-granted "leather armor" worked fine
        # in-session, but a second copy stacked onto a reloaded entry from
        # an earlier session fell through USE's fallback "You play with
        # the X.." branch because .type had never survived the trip.
        item_type = getattr(self.item, 'type', None)
        if item_type:
            d['item_type'] = str(item_type)
        # condition (0-100) is armor/shield's per-item durability -- the
        # 2026-08-08 redesign that replaced a single flat player.armor/
        # player.shield aggregate with a real value living on the actual
        # equipped piece (see player.py's equipped_entry()/
        # refresh_equipped_rating()). Unlike item_type above, a missing
        # value has no canonical source to backfill from (condition is
        # inherently per-instance, not derivable from objects.json) --
        # from_json() just defaults a legacy entry to 100 (fresh).
        condition = getattr(self.item, 'condition', None)
        if condition is not None:
            d['item_condition'] = condition
        # charges lives on the item itself (Spell.charges) -- e.g. a Wizard's
        # learned spell -- not tracked separately per carried entry.
        charges = getattr(self.item, 'charges', None)
        if charges is not None:
            d['charges'] = charges
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

    def add(self, item: 'BaseItem', quantity: int = 1) -> bool:
        """Add item to inventory, stacking if an entry with the same id_number exists.

        Returns False when the inventory is full and no existing stack was found.

        Armor/shield items never stack, even across a matching id_number --
        each physical piece carries its own condition (2026-08-08 durability
        redesign), and merging two pieces into one quantity>1 entry would
        make them share a single condition value, which doesn't mean
        anything once they can wear down independently.
        """
        self._prune()
        from item_system import ItemType
        is_durable = getattr(item, 'type', None) in (ItemType.ARMOR, ItemType.SHIELD)
        item_id = getattr(item, 'id_number', None)
        if item_id is not None and not is_durable:
            for entry in self._entries:
                if getattr(entry.item, 'id_number', None) == item_id:
                    entry.quantity += quantity
                    return True

        if self.capacity is not None and len(self._entries) >= self.capacity:
            return False

        entry = InventoryEntry(item=item, quantity=quantity)
        # Auto-create sub-inventory for containers
        if getattr(item, 'capacity', 0) > 0:
            entry.contents = Inventory(capacity=item.capacity)
        self._entries.append(entry)
        return True

    def remove(self, item: 'BaseItem', quantity: int = 1) -> bool:
        """Decrement quantity; remove entry when it reaches zero.

        Returns False if the item is not present or there is insufficient quantity.

        Matches by object identity first, falling back to id_number. Armor/
        shield items no longer stack (see add()), so two entries can share
        an id_number while being different physical pieces -- an id-only
        match would risk removing the wrong one (e.g. a spare instead of
        the one actually destroyed in combat). Every real call site already
        passes the entry's own item object (looked up via find()/
        equipped_entry()/etc.), so the identity match is the common case;
        the id_number fallback only matters for a caller passing a fresh
        lookalike item rather than the stored one.
        """
        self._prune()
        for i, entry in enumerate(self._entries):
            if entry.item is item:
                return self._remove_at(i, quantity)
        item_id = getattr(item, 'id_number', None)
        for i, entry in enumerate(self._entries):
            if item_id is not None and getattr(entry.item, 'id_number', None) == item_id:
                return self._remove_at(i, quantity)
        return False

    def _remove_at(self, index: int, quantity: int) -> bool:
        entry = self._entries[index]
        if entry.quantity < quantity:
            return False
        entry.quantity -= quantity
        if entry.quantity == 0:
            self._entries.pop(index)
        return True

    # -----------------------------------------------------------------------
    # Query
    # -----------------------------------------------------------------------

    def _prune(self) -> None:
        """Drop any entry that's reached quantity <= 0.

        remove() itself always pops an entry the moment it hits zero, so
        this should be a no-op in the normal case -- it's a defensive
        backstop against zombie entries created by other code that
        mutates entry.quantity directly (found live: ally.items'
        consumption path decremented a *shared* entry -- see the
        InventoryEntry-aliasing bug fixed in commands/give.py -- down to
        0 and only popped it from the ally's own list, leaving a
        quantity:0 "cloth armor" permanently stuck in the player's own
        _entries, still showing in `inv` and blocking every future GIVE
        of it with a false "insufficient quantity"). Called from every
        read/write entry point below so a zombie self-heals the next
        time this Inventory is touched, rather than needing a save-file
        edit.
        """
        self._entries = [e for e in self._entries if e.quantity > 0]

    def find(self, *, name: str | None = None, item_id: int | None = None,
             category: str | None = None) -> list[InventoryEntry]:
        """Return all entries matching the given criteria (AND logic)."""
        self._prune()
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
        self._prune()
        if category is None:
            return list(self._entries)
        return [e for e in self._entries
                if str(getattr(e.item, 'category', '')) == category]

    def is_full(self) -> bool:
        self._prune()
        return self.capacity is not None and len(self._entries) >= self.capacity

    def slot_count(self) -> int:
        self._prune()
        return len(self._entries)

    def __len__(self) -> int:
        self._prune()
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
    def from_json(cls, data: list | None, capacity: int | None = None,
                  weapons_data: list | None = None) -> 'Inventory':
        """Reconstruct an Inventory from serialized data.

        Item objects are reconstructed as lightweight Items; weapons and
        spells are resolved back to fully-populated Weapon/Spell instances
        -- weapons via weapons_data (the server's raw weapons.json list,
        see items.resolve_weapon()), spells via items.resolve_spell()
        (spell data is a static, hardcoded list, so no data plumbing is
        needed for that one). Other categories (armor has no dedicated
        dataclass yet) still reconstruct as lightweight Items; full
        resolution for those can be done later when it is available.
        """
        from items import Item, ItemCategory
        from item_system import ItemType
        inv = cls(capacity=capacity)
        for d in (data or []):
            cat_str = d.get('item_category', '')
            try:
                category = ItemCategory(cat_str) if cat_str else ItemCategory.ITEM
            except ValueError:
                category = ItemCategory.ITEM

            item_type_str = d.get('item_type')
            if item_type_str is None:
                # Same "heal old save files" backfill as item_kind below,
                # but against objects.json instead of rations.json -- any
                # entry saved before item_type started round-tripping
                # (2026-08-08) would otherwise permanently lose WEAR/USE/
                # READ eligibility. Matched by id_number AND name for the
                # same reason as the item_kind backfill: id_number alone
                # isn't unique across categories.
                obj = _objects_by_number().get(d.get('item_id'))
                if obj and str(obj.get('name', '')).lower() == d.get('item_name', '').lower():
                    item_type_str = obj.get('type')
            item_type = None
            if item_type_str:
                try:
                    item_type = ItemType(item_type_str)
                except ValueError:
                    pass

            # condition (0-100, per-item durability) has no canonical
            # source to backfill from the way item_type/item_kind do --
            # a legacy entry (or a fresh armor/shield with no value yet)
            # just defaults to 100 (fresh). Left None for non-armor/shield
            # items, matching to_json()'s "only write if not None" guard.
            item_condition = d.get('item_condition')
            if item_condition is None and item_type in (ItemType.ARMOR, ItemType.SHIELD):
                item_condition = 100

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

            if category == ItemCategory.WEAPON:
                from items import resolve_weapon
                item = resolve_weapon(d.get('item_id', 0), item_name, weapons_data,
                                       flags=d.get('item_flags') or [], kind=item_kind)
            elif category == ItemCategory.SPELL:
                from items import resolve_spell
                item = resolve_spell(d.get('item_id', 0), item_name,
                                      flags=d.get('item_flags') or [],
                                      charges=d.get('charges', 1) or 1)
            else:
                item = Item(
                    id_number=d.get('item_id', 0),
                    name=item_name,
                    category=category,
                    flags=d.get('item_flags') or [],
                    kind=item_kind,
                    type=item_type,
                    condition=item_condition,
                )
            entry = InventoryEntry(
                item=item,
                quantity=d.get('quantity', 1),
            )
            if 'contents' in d:
                entry.contents = cls.from_json(d['contents'], weapons_data=weapons_data)
            inv._entries.append(entry)
        return inv
