"""tests/commands/test_cast_enchant.py — commands/cast.py's _cast_enchant()
(ENCHANT ARMOR / ENCHANT SHIELD).

Regression coverage for the 2026-08-08 per-item durability redesign:
_cast_enchant() used to bump the flat player.armor/player.shield mirror
directly. It now targets the equipped item's own .condition (via
player.py's equipped_entry()/refresh_equipped_rating()), same write path
as WEAR/USE/UNWEAR/combat degradation -- and fails gracefully with no
effect if nothing is equipped in that slot, since there's no item to
enchant.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from commands.cast import _cast_enchant
from inventory import Inventory
from item_system import ItemType
from items import Item, ItemCategory


def _make_player():
    player = MagicMock()
    player.inventory = Inventory()
    player.char_class = None
    player.char_race  = None
    player.active_armor_id  = None
    player.active_shield_id = None
    player.armor  = 0
    player.shield = 0
    return player


def _equip(player, slot: str, item_id: int, condition: int, name: str = 'test item'):
    itype = ItemType.ARMOR if slot == 'armor' else ItemType.SHIELD
    item = Item(id_number=item_id, name=name, category=ItemCategory.ITEM,
                type=itype, condition=condition)
    player.inventory.add(item)
    setattr(player, f'active_{slot}_id', item_id)
    setattr(player, slot, condition)


class TestEnchantNothingEquipped(unittest.TestCase):

    def test_armor_enchant_with_nothing_equipped_fails_gracefully(self):
        player = _make_player()
        outcome, msg = _cast_enchant(player, 'Y', magnitude=15, bonus=0, success=True)
        self.assertEqual(outcome, 'backfire')
        self.assertIn('nothing enchant-able', msg)
        self.assertEqual(player.armor, 0)

    def test_shield_enchant_with_nothing_equipped_fails_gracefully(self):
        player = _make_player()
        outcome, msg = _cast_enchant(player, 'Z', magnitude=15, bonus=0, success=True)
        self.assertEqual(outcome, 'backfire')
        self.assertIn('nothing enchant-able', msg)


class TestEnchantSuccess(unittest.TestCase):

    def test_success_bumps_the_equipped_items_condition(self):
        player = _make_player()
        _equip(player, 'armor', item_id=24, condition=50)
        outcome, msg = _cast_enchant(player, 'Y', magnitude=15, bonus=0, success=True)
        self.assertEqual(outcome, 'success')
        entry = player.inventory.find(item_id=24)[0]
        self.assertEqual(entry.item.condition, 65)
        self.assertEqual(player.armor, 65)
        self.assertIn('65%', msg)

    def test_success_is_capped_at_100(self):
        player = _make_player()
        _equip(player, 'armor', item_id=24, condition=95)
        _cast_enchant(player, 'Y', magnitude=15, bonus=0, success=True)
        entry = player.inventory.find(item_id=24)[0]
        self.assertEqual(entry.item.condition, 100)

    def test_success_already_at_cap_collapses_to_backfire(self):
        # Mirrors _cast_stat()'s shape: a successful cast at the cap still
        # weakens instead of doing nothing.
        player = _make_player()
        _equip(player, 'shield', item_id=4, condition=100)
        outcome, msg = _cast_enchant(player, 'Z', magnitude=15, bonus=0, success=True)
        self.assertEqual(outcome, 'backfire')
        entry = player.inventory.find(item_id=4)[0]
        self.assertEqual(entry.item.condition, 85)
        self.assertEqual(player.shield, 85)


class TestEnchantBackfire(unittest.TestCase):

    def test_backfire_weakens_the_equipped_items_condition(self):
        player = _make_player()
        _equip(player, 'shield', item_id=4, condition=50)
        outcome, msg = _cast_enchant(player, 'Z', magnitude=15, bonus=0, success=False)
        self.assertEqual(outcome, 'backfire')
        entry = player.inventory.find(item_id=4)[0]
        self.assertEqual(entry.item.condition, 35)
        self.assertEqual(player.shield, 35)

    def test_backfire_below_magnitude_leaves_no_message(self):
        player = _make_player()
        _equip(player, 'shield', item_id=4, condition=5)
        outcome, msg = _cast_enchant(player, 'Z', magnitude=15, bonus=0, success=False)
        self.assertEqual(outcome, 'backfire')
        self.assertEqual(msg, '')
        entry = player.inventory.find(item_id=4)[0]
        self.assertEqual(entry.item.condition, 5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
