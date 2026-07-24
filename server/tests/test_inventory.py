"""tests/test_inventory.py — unit tests for inventory.py's JSON round-trip.

Regression coverage: InventoryEntry.to_json()/Inventory.from_json() used to
drop item.flags entirely, so any item's flags (e.g. ammo's
rounds/damage/used_with) silently reset to [] on the very next save/load
cycle -- independent of whatever a shop set them to at purchase time. This
is what actually broke commands/use.py's ammo-loading branch in practice
(see that module's _apply_item docstring): even with the correct flags at
purchase time, Player.__init__ reloading from disk erased them before USE
ever got a chance to read them.
"""
from __future__ import annotations

import unittest

from inventory import Inventory
from items import Item, ItemCategory, Rations


class TestInventoryFlagsRoundTrip(unittest.TestCase):

    def test_item_flags_survive_to_json_from_json(self):
        inv = Inventory()
        ammo = Item(id_number=104, name='.357 ammo', category=ItemCategory.ITEM,
                    flags={'rounds': 6, 'damage': 4, 'used_with': '.357 magnum'})
        inv.add(ammo)

        restored = Inventory.from_json(inv.to_json())
        entry = restored.find(name='.357 ammo')[0]

        self.assertEqual(entry.item.flags, {'rounds': 6, 'damage': 4, 'used_with': '.357 magnum'})

    def test_item_without_flags_round_trips_to_empty_list(self):
        inv = Inventory()
        inv.add(Item(id_number=6, name='large ruby', category=ItemCategory.ITEM))

        restored = Inventory.from_json(inv.to_json())
        entry = restored.find(name='large ruby')[0]

        self.assertEqual(entry.item.flags, [])
        self.assertNotIn('item_flags', inv.to_json()[0])


class TestInventoryKindRoundTrip(unittest.TestCase):
    """Regression: Ryan reported "you have nothing matching bread" for a
    loaf of bread genuinely in inventory -- from_json() rebuilt every
    persisted item as a plain Item(), which has no .kind at all unless
    explicitly passed in, and to_json() never wrote one out to begin
    with. commands/eat.py's/commands/drink.py's food/drink filters both
    key off item.kind == 'food'/'drink', so any ration silently
    stopped showing up in EAT/DRINK the moment a player reconnected
    (Inventory.from_json() runs on every Player load, including a plain
    reconnect, not just a full server restart).
    """

    def test_rations_kind_survives_to_json_from_json(self):
        inv = Inventory()
        bread = Rations(number=5, name='LOAF OF BREAD', kind='food', price=30)
        inv.add(bread)

        restored = Inventory.from_json(inv.to_json())
        entry = restored.find(name='LOAF OF BREAD')[0]

        self.assertEqual(entry.item.kind, 'food')

    def test_drink_kind_survives_to_json_from_json(self):
        inv = Inventory()
        water = Rations(number=12, name='MINERAL WATER', kind='drink', price=10)
        inv.add(water)

        restored = Inventory.from_json(inv.to_json())
        entry = restored.find(name='MINERAL WATER')[0]

        self.assertEqual(entry.item.kind, 'drink')

    def test_item_without_kind_round_trips_to_none(self):
        inv = Inventory()
        inv.add(Item(id_number=6, name='large ruby', category=ItemCategory.ITEM))

        restored = Inventory.from_json(inv.to_json())
        entry = restored.find(name='large ruby')[0]

        self.assertIsNone(entry.item.kind)
        self.assertNotIn('item_kind', inv.to_json()[0])


class TestInventoryKindBackfill(unittest.TestCase):
    """Regression: the to_json()/from_json() round-trip fix above only
    protects an item that already has .kind *at save time*. Ryan's own
    test character still couldn't eat a loaf of bread after that fix
    shipped, because that bread had been saved (with no item_kind field
    at all) by an older build, before item.kind existed on it in the
    first place -- from_json() had nothing to preserve. from_json() now
    falls back to looking the item up in rations.json by number when
    item_kind is missing, healing any pre-existing save on next load.
    """

    def _legacy_entry(self, item_id: int, name: str, category: str = 'Item') -> dict:
        """A save record shaped exactly like one written before item_kind
        existed -- no 'item_kind' key at all."""
        return {'item_id': item_id, 'item_name': name, 'item_category': category, 'quantity': 1}

    def test_legacy_bread_entry_heals_kind_and_category(self):
        restored = Inventory.from_json([self._legacy_entry(5, 'LOAF OF BREAD')])
        entry = restored.find(name='LOAF OF BREAD')[0]

        self.assertEqual(entry.item.kind, 'food')
        self.assertEqual(entry.item.category, ItemCategory.FOOD)

    def test_legacy_drink_entry_heals_kind_and_category(self):
        restored = Inventory.from_json([self._legacy_entry(1, 'TEA')])
        entry = restored.find(name='TEA')[0]

        self.assertEqual(entry.item.kind, 'drink')
        self.assertEqual(entry.item.category, ItemCategory.DRINK)

    def test_healed_bread_is_visible_to_eat_command_filter(self):
        from commands.eat import _food_entries

        restored = Inventory.from_json([self._legacy_entry(5, 'LOAF OF BREAD')])
        player = type('P', (), {'inventory': restored})()
        matches = _food_entries(player)

        self.assertEqual(len(matches), 1)

    def test_number_match_alone_is_not_enough_without_name_match(self):
        """rations.json #1 is TEA, but item numbering is only unique
        within its own category -- a legacy weapon or misc item that
        happens to share id_number 1 with a ration must NOT be
        misidentified as that ration just because the number matches."""
        restored = Inventory.from_json([self._legacy_entry(1, 'RUSTY DAGGER', category='Weapon')])
        entry = restored.find(name='RUSTY DAGGER')[0]

        self.assertIsNone(entry.item.kind)

    def test_unknown_item_id_is_left_alone(self):
        restored = Inventory.from_json([self._legacy_entry(99999, 'MYSTERY BOX')])
        entry = restored.find(name='MYSTERY BOX')[0]

        self.assertIsNone(entry.item.kind)


if __name__ == '__main__':
    unittest.main(verbosity=2)
