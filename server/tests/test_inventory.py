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
from items import Item, ItemCategory


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


if __name__ == '__main__':
    unittest.main(verbosity=2)
