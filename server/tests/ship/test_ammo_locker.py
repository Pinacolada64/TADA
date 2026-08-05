"""tests/ship/test_ammo_locker.py

Covers ship/ammo_locker.py -- the ship's ammo locker (SPUR.SHIP.S
`ammo`/`ammo1`/`ammo2`), selling energy-weapon ammo (objects.json
#118-121) at price*20 gold.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from base_classes import PlayerMoneyTypes
from flags import PlayerFlags
from inventory import Inventory
from items import ItemCategory
from player import Player
from ship.ammo_locker import main as ammo_locker_main


def _new_player(name: str) -> Player:
    player = Player(name=name)
    player.clear_flag(PlayerFlags.DEBUG_MODE)
    player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 1000)
    player.inventory = Inventory()
    return player


class _FakeCtx:
    def __init__(self, responses, player):
        self._q = list(responses)
        self.sent: list = []
        self.player = player
        self.server = SimpleNamespace(items=[])

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


class TestAmmoLockerPurchase(unittest.IsolatedAsyncioTestCase):
    async def test_buys_phaser_pak_for_price_times_twenty(self):
        # objects.json #119 "phaser pak", price 2 -- real data, not fabricated.
        player = _new_player('Rulan')
        ctx = _FakeCtx(['119', 'y', 'q'], player)
        await ammo_locker_main(ctx)
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 1000 - 40)  # price * 20
        entries = player.inventory.entries(ItemCategory.ITEM)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].item.id_number, 119)

    async def test_number_outside_ammo_range_is_refused(self):
        player = _new_player('Rulan')
        ctx = _FakeCtx(['1', 'q'], player)
        await ammo_locker_main(ctx)
        self.assertIn('Enter 118 - 121 or Q', ctx._flat())
        self.assertEqual(len(player.inventory.entries(ItemCategory.ITEM)), 0)

    async def test_insufficient_gold_refuses_sale(self):
        player = _new_player('Rulan')
        player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 0)
        ctx = _FakeCtx(['119', 'q'], player)
        await ammo_locker_main(ctx)
        self.assertIn('You do not have enough gold.', ctx._flat())
        self.assertEqual(len(player.inventory.entries(ItemCategory.ITEM)), 0)

    async def test_declining_purchase_keeps_gold(self):
        player = _new_player('Rulan')
        ctx = _FakeCtx(['119', 'n', 'q'], player)
        await ammo_locker_main(ctx)
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 1000)
        self.assertEqual(len(player.inventory.entries(ItemCategory.ITEM)), 0)


if __name__ == '__main__':
    unittest.main()
