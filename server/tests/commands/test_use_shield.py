"""tests/commands/test_use_shield.py — commands/use.py's ItemType.SHIELD
branch of _apply_item().

Regression coverage: USE-ing a shield boosted player.shield's flat
percentage but never recorded player.active_shield_id, so STAT's shield
skill line and combat's shield-block-exp lookups silently tracked the
wrong (or no) shield after a normal USE, even though
commands/new_player.py's starting equipment and shoppe/armory.py's
purchase path both set it. Fixed 2026-08-08 by having the USE-shield
branch set active_shield_id too.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from commands.use import _apply_item
from inventory import Inventory
from item_system import ItemType
from items import Item, ItemCategory


def _shield(name, item_id, price=2) -> Item:
    item = Item(id_number=item_id, name=name, category=ItemCategory.ARMOR, price=price)
    item.type = ItemType.SHIELD
    return item


def _make_player():
    player = MagicMock()
    player.inventory = Inventory()
    player.shield = 0
    player.char_class = None
    player.char_race  = None
    return player


class TestUseShieldSetsActiveShieldId(unittest.TestCase):

    def test_using_a_shield_sets_active_shield_id(self):
        player = _make_player()
        shield = _shield('small shield', item_id=4)
        _apply_item(shield, player)
        self.assertEqual(player.active_shield_id, 4)
        self.assertGreater(player.shield, 0)

    def test_using_a_second_shield_updates_active_shield_id(self):
        player = _make_player()
        first  = _shield('small shield', item_id=4)
        _apply_item(first, player)
        player.shield = 0  # re-open headroom under this player's cap
        second = _shield('gold shield', item_id=5)
        _apply_item(second, player)
        self.assertEqual(player.active_shield_id, 5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
