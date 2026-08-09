"""tests/new-player/test_starting_armor_shield_items.py — commands/new_
player.py's _assign_equipment() backing a successful shield/armor roll
with a real, WEAR/USE-able inventory item.

Regression coverage for the 2026-08-08 per-item durability redesign:
previously only the shield roll got a real item (STARTER_SHIELD_ITEM_
NUMBER, objects.json #4) with active_shield_id set -- a successful armor
roll was just a bare player.armor number with nothing behind it at all.
Under the new model that's a real problem, not just an inconsistency: the
first combat hit that degrades armor with no equipped_entry() to charge
it to just zeroes player.armor outright instead of gradually wearing it
down (see player.py's apply_equipment_degradation()). Both halves now
mirror each other via STARTER_ARMOR_ITEM_NUMBER (objects.json #2).
"""
from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from base_classes import PlayerClass, PlayerRace
from commands.new_player import _assign_equipment
from inventory import Inventory
from item_system import ItemType
from player import Player

_OBJECTS = [
    {'number': 2, 'name': 'cloth armor', 'type': 'armor', 'price': 2},
    {'number': 4, 'name': 'small shield', 'type': 'shield', 'price': 2},
]


def run(coro):
    return asyncio.run(coro)


def _ctx():
    player = Player(name='Rulan', char_class=PlayerClass.FIGHTER, char_race=PlayerRace.HUMAN)
    player.inventory = Inventory(capacity=14)
    ctx = SimpleNamespace(
        player=player,
        server=SimpleNamespace(items=_OBJECTS, weapons=[]),
        send=AsyncMock(),
    )
    return ctx


class TestStartingShieldItem(unittest.TestCase):
    def test_successful_roll_backs_player_shield_with_a_real_item(self):
        with patch('starting_equipment.random.random', return_value=0.0), \
             patch('starting_equipment._roll_intactness', return_value=42):
            ctx = _ctx()
            run(_assign_equipment(ctx))
        self.assertEqual(ctx.player.active_shield_id, 4)
        entries = ctx.player.inventory.find(item_id=4)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].item.type, ItemType.SHIELD)
        self.assertEqual(entries[0].item.condition, 42)
        self.assertEqual(ctx.player.shield, 42)


class TestStartingArmorItem(unittest.TestCase):
    def test_successful_roll_backs_player_armor_with_a_real_item(self):
        with patch('starting_equipment.random.random', return_value=0.0), \
             patch('starting_equipment._roll_intactness', return_value=37):
            ctx = _ctx()
            run(_assign_equipment(ctx))
        self.assertEqual(ctx.player.active_armor_id, 2)
        entries = ctx.player.inventory.find(item_id=2)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].item.type, ItemType.ARMOR)
        self.assertEqual(entries[0].item.condition, 37)
        self.assertEqual(ctx.player.armor, 37)

    def test_starting_armor_survives_a_later_combat_degrade(self):
        """The concrete failure mode this fix prevents: without a real
        item behind it, the first degrade would zero player.armor outright
        instead of wearing it down by the hit amount."""
        from player import apply_equipment_degradation

        with patch('starting_equipment.random.random', return_value=0.0), \
             patch('starting_equipment._roll_intactness', return_value=50):
            ctx = _ctx()
            run(_assign_equipment(ctx))
        apply_equipment_degradation(ctx.player, 'armor', degraded=10, destroyed=False)
        self.assertEqual(ctx.player.armor, 40)


if __name__ == '__main__':
    unittest.main()
