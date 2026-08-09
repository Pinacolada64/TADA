"""tests/combat/test_equipment_degradation.py — combat degradation writing
to the equipped item's real .condition, not just the flat player.armor/
player.shield mirror (2026-08-08 per-item durability redesign).

Regression coverage: combat/engine.py's _apply_monster_damage() and
combat/duel.py's _apply_degradation() used to decrement/zero player.armor/
player.shield directly -- the hit that was supposed to wear down or break
a specific physical item never touched the item itself, so it stayed at
full condition in the pack even after being "destroyed" in combat.
player.py's apply_equipment_degradation() (shared by both call sites) now
routes every degrade/destroy through the actual InventoryEntry.
"""
from __future__ import annotations

import types
import unittest
from unittest.mock import MagicMock

from combat.duel import _apply_degradation
from combat.engine import CombatSession
from inventory import Inventory
from item_system import ItemType
from items import Item, ItemCategory
from player import apply_equipment_degradation


def _shield(item_id=4, condition=50) -> Item:
    item = Item(id_number=item_id, name='small shield', category=ItemCategory.ITEM)
    item.type = ItemType.SHIELD
    item.condition = condition
    return item


def _armor(item_id=24, condition=50) -> Item:
    item = Item(id_number=item_id, name='leather armor', category=ItemCategory.ITEM)
    item.type = ItemType.ARMOR
    item.condition = condition
    return item


def _equipped_player(shield_condition=50, armor_condition=50):
    player = MagicMock()
    player.inventory = Inventory()
    player.char_class = None
    player.char_race  = None
    shield = _shield(condition=shield_condition)
    armor  = _armor(condition=armor_condition)
    player.inventory.add(shield)
    player.inventory.add(armor)
    player.active_shield_id = shield.id_number
    player.active_armor_id  = armor.id_number
    player.shield = shield_condition
    player.armor  = armor_condition
    return player


class TestApplyEquipmentDegradation(unittest.TestCase):

    def test_degrade_decrements_the_items_own_condition(self):
        player = _equipped_player(shield_condition=50)
        apply_equipment_degradation(player, 'shield', degraded=15, destroyed=False)
        entry = player.inventory.find(item_id=4)[0]
        self.assertEqual(entry.item.condition, 35)
        self.assertEqual(player.shield, 35)

    def test_degrade_floors_at_zero(self):
        player = _equipped_player(shield_condition=5)
        apply_equipment_degradation(player, 'shield', degraded=99, destroyed=False)
        entry = player.inventory.find(item_id=4)[0]
        self.assertEqual(entry.item.condition, 0)

    def test_destroyed_removes_the_item_and_clears_active_id(self):
        player = _equipped_player(armor_condition=10)
        apply_equipment_degradation(player, 'armor', degraded=10, destroyed=True)
        self.assertEqual(player.inventory.find(item_id=24), [])
        self.assertIsNone(player.active_armor_id)
        self.assertEqual(player.armor, 0)

    def test_destroyed_shield_leaves_armor_untouched(self):
        player = _equipped_player(shield_condition=5, armor_condition=80)
        apply_equipment_degradation(player, 'shield', degraded=5, destroyed=True)
        self.assertIsNone(player.active_shield_id)
        self.assertEqual(player.active_armor_id, 24)
        self.assertEqual(player.armor, 80)


class _FakeAttackResult:
    hit = True
    damage = 3
    fire_damage = 0
    shield_blocked = 5
    shield_degraded = 15
    shield_destroyed = False
    armor_blocked = 0
    armor_degraded = 0
    armor_destroyed = False
    experience_drained = 0
    dex_lost = False
    strength_lost = False


class TestEngineDegradesTheEquippedItem(unittest.TestCase):
    """combat/engine.py's _apply_monster_damage() -- integration through
    the real CombatSession method, not just the shared helper directly."""

    def test_shield_block_degrades_the_equipped_shield_item(self):
        player = _equipped_player(shield_condition=50)
        player.gain_shield_proficiency = MagicMock()
        ctx = types.SimpleNamespace(player=player)
        session = CombatSession.__new__(CombatSession)
        session._apply_monster_damage(ctx, _FakeAttackResult())
        entry = player.inventory.find(item_id=4)[0]
        self.assertEqual(entry.item.condition, 35)
        self.assertEqual(player.shield, 35)


class TestDuelDegradesTheEquippedItem(unittest.TestCase):
    """combat/duel.py's _apply_degradation()."""

    def test_shield_destroyed_in_duel_removes_it(self):
        player = _equipped_player(shield_condition=8)
        _apply_degradation(player, shield_degraded=8, armor_degraded=0,
                            shield_destroyed=True, armor_destroyed=False)
        self.assertEqual(player.inventory.find(item_id=4), [])
        self.assertIsNone(player.active_shield_id)

    def test_armor_degraded_in_duel_updates_the_item(self):
        player = _equipped_player(armor_condition=60)
        _apply_degradation(player, shield_degraded=0, armor_degraded=25,
                            shield_destroyed=False, armor_destroyed=False)
        entry = player.inventory.find(item_id=24)[0]
        self.assertEqual(entry.item.condition, 35)
        self.assertEqual(player.armor, 35)


if __name__ == '__main__':
    unittest.main(verbosity=2)
