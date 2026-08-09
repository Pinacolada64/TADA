"""tests/shoppe/test_armory.py — shoppe/armory.py's protection() (buying
armor/shields at the regular Merchant Shoppe).

Regression coverage for the 2026-08-08 per-item durability redesign:
buying protection used to auto-equip (set player.armor/player.shield and,
for shields only, active_shield_id directly), bypassing WEAR/USE entirely
and leaving armor purchases -- unlike shield ones -- never setting
active_armor_id at all. It now just adds a fresh (condition=100), properly
typed item to inventory, same as any other purchase; equipping is an
explicit WEAR/USE step.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from base_classes import PlayerMoneyTypes
from flags import PlayerFlags
from inventory import Inventory
from item_system import ItemType
from player import Player
from shoppe.armory import protection


def _new_player(name: str = 'Rulan') -> Player:
    player = Player(name=name)
    player.clear_flag(PlayerFlags.DEBUG_MODE)
    player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 100000)
    player.inventory = Inventory()
    player.char_class = None
    player.char_race  = None
    return player


class _FakeCtx:
    def __init__(self, responses, player):
        self._q = list(responses)
        self.sent: list = []
        self.player = player

    async def send(self, *args):
        for a in args:
            if isinstance(a, list):
                self.sent.extend(a)
            else:
                self.sent.append(a)

    async def prompt(self, prompt_text: str = '', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


class TestBuyingArmorDoesNotAutoEquip(unittest.IsolatedAsyncioTestCase):

    async def test_buying_leather_armor_does_not_set_player_armor(self):
        player = _new_player()
        # listing position 9 = leather armor (objects.json #24) -- confirm, then leave
        ctx = _FakeCtx(['9', 'y', 'q'], player)
        await protection(ctx)
        self.assertIsNone(player.armor)
        self.assertIsNone(player.active_armor_id)

    async def test_buying_leather_armor_adds_a_wearable_item(self):
        player = _new_player()
        ctx = _FakeCtx(['9', 'y', 'q'], player)
        await protection(ctx)
        entries = player.inventory.find(item_id=24)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].item.type, ItemType.ARMOR)
        self.assertEqual(entries[0].item.condition, 100)

    async def test_buying_a_shield_does_not_auto_equip_either(self):
        # listing position 3 = small shield (objects.json #4) -- confirm, then leave
        player = _new_player()
        ctx = _FakeCtx(['3', 'y', 'q'], player)
        await protection(ctx)
        self.assertIsNone(player.shield)
        self.assertIsNone(player.active_shield_id)
        entries = player.inventory.find(item_id=4)
        self.assertEqual(entries[0].item.type, ItemType.SHIELD)
        self.assertEqual(entries[0].item.condition, 100)

    async def test_bought_armor_is_actually_wearable(self):
        from commands.wear import WearCommand

        player = _new_player()
        ctx = _FakeCtx(['9', 'y', 'q'], player)
        await protection(ctx)
        ctx.sent.clear()
        await WearCommand().execute(ctx, 'leather', 'armor')
        self.assertEqual(player.active_armor_id, 24)
        self.assertEqual(player.armor, 100)

    async def test_hint_message_shown_for_non_expert(self):
        player = _new_player()
        self.assertFalse(player.is_expert)
        ctx = _FakeCtx(['9', 'y', 'q'], player)
        await protection(ctx)
        self.assertIn('WEAR it to put it on.', ctx._flat())


if __name__ == '__main__':
    unittest.main(verbosity=2)
