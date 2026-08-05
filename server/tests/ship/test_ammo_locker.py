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
        # objects.json #119 "phaser pak", price 2 -- real data, not
        # fabricated. Shop numbering is the table's own 1..N display
        # index (Ryan's request), not the raw objects.json number -- #119
        # is the 2nd item in the #118-121 range, so choice "2".
        player = _new_player('Rulan')
        ctx = _FakeCtx(['2', 'y', 'q'], player)
        await ammo_locker_main(ctx)
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 1000 - 40)  # price * 20
        entries = player.inventory.entries(ItemCategory.ITEM)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].item.id_number, 119)

    async def test_number_outside_ammo_range_is_refused(self):
        player = _new_player('Rulan')
        ctx = _FakeCtx(['99', 'q'], player)
        await ammo_locker_main(ctx)
        self.assertIn('Enter 1-4 or Q', ctx._flat())
        self.assertEqual(len(player.inventory.entries(ItemCategory.ITEM)), 0)

    async def test_insufficient_gold_refuses_sale(self):
        player = _new_player('Rulan')
        player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 0)
        ctx = _FakeCtx(['2', 'q'], player)
        await ammo_locker_main(ctx)
        self.assertIn('You do not have enough silver.', ctx._flat())
        self.assertEqual(len(player.inventory.entries(ItemCategory.ITEM)), 0)

    async def test_declining_purchase_keeps_gold(self):
        player = _new_player('Rulan')
        ctx = _FakeCtx(['2', 'n', 'q'], player)
        await ammo_locker_main(ctx)
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 1000)
        self.assertEqual(len(player.inventory.entries(ItemCategory.ITEM)), 0)

    async def test_display_number_matches_purchase_number(self):
        # Regression: the table's "#" column showed 1-4 (enumerate from
        # ammo_table()) but the purchase prompt only accepted the raw
        # objects.json IDs 118-121 -- what the player saw next to an item
        # wasn't what they had to type to buy it. Ryan caught this live.
        player = _new_player('Rulan')
        ctx = _FakeCtx(['q'], player)
        await ammo_locker_main(ctx)
        table_line = next(s for s in ctx.sent if 'phaser pak' in s)
        # "phaser pak" is listed 2nd -> its row's "#" cell should read 2,
        # not its objects.json number 119.
        self.assertIn('2', table_line.split('phaser pak')[0])
        self.assertNotIn('119', table_line)

    async def test_listing_shows_a_rendered_table_not_a_table_object(self):
        # Regression: an earlier draft sent the raw Table object (and with
        # arguments swapped) instead of calling .render() first -- ctx.send
        # would have received a Table, not a list[str], and every "line"
        # printed to the player would really be one un-rendered object.
        player = _new_player('Rulan')
        ctx = _FakeCtx(['q'], player)
        await ammo_locker_main(ctx)
        self.assertTrue(all(isinstance(s, str) for s in ctx.sent))
        flat = ctx._flat()
        self.assertIn('phaser pak', flat)
        self.assertIn('Rnds', flat)
        self.assertIn('Dmg', flat)

    async def test_listed_price_matches_the_price_actually_charged(self):
        # Regression: the table was showing price*10 while main()'s
        # purchase flow actually charges price*20 -- displayed cost didn't
        # match what left the player's pocket. objects.json #119 "phaser
        # pak" has price 2 -> the correct listing is 40s (price*20); the
        # price*10 bug would have shown 20s on this row instead.
        player = _new_player('Rulan')
        ctx = _FakeCtx(['q'], player)
        await ammo_locker_main(ctx)
        phaser_line = next(s for s in ctx.sent if 'phaser pak' in s)
        self.assertIn('40s', phaser_line)
        self.assertNotIn('20s', phaser_line)


if __name__ == '__main__':
    unittest.main()
