"""tests/shoppe/test_pawn.py

Covers shoppe/pawn.py -- Ye Olde Pawn Shoppe. Regression test for the
bug Ryan found live: Inventory.from_json() rebuilds each carried item
as a "lightweight" Item (id_number/name/category/flags/kind only, never
price), so entry.item.price is always 0 for any item that survived a
save/load round trip -- which in practice is every item a real player
carries. That silently made every sale hit the "I'll give ya nothing"
branch. Fixed by looking the real price up from ctx.server.items by
number, same pattern as shoppe/armory.py's weapon sell-back.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from base_classes import PlayerMoneyTypes
from flags import PlayerFlags
from inventory import Inventory
from items import Item, ItemCategory
from player import Player
from shoppe.pawn import main as pawn_main


def _new_player(name: str) -> Player:
    # Player.query_flag(PlayerFlags.DEBUG_MODE) defaults True -- clear it
    # so debug_toggle_once_per_day()'s "Add to once-per-day activities?"
    # debug prompt stays a no-op, matching a real player's default state,
    # rather than consuming the test's own scripted responses.
    player = Player(name=name)
    player.clear_flag(PlayerFlags.DEBUG_MODE)
    return player


class _FakeCtx:
    def __init__(self, responses, player, items=None):
        self._q = list(responses)
        self.sent: list = []
        self.player = player
        self.server = SimpleNamespace(items=items or [])

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


def _player_with_reloaded_item(item_id: int, name: str) -> Player:
    """Simulates a real player: inventory rebuilt via Inventory.from_json(),
    which is exactly what drops .price -- not a freshly ctx.player.inventory.add()'d
    item, which would still have it and wouldn't reproduce the bug."""
    player = _new_player('Rulan')
    player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 0)
    player.inventory = Inventory.from_json([
        {'item_id': item_id, 'item_name': name, 'item_category': str(ItemCategory.ITEM)},
    ])
    return player


class TestPawnSellsReloadedItemsForRealPrice(unittest.IsolatedAsyncioTestCase):
    async def test_reloaded_item_price_is_looked_up_from_the_item_database(self):
        # id 1 == 'compass', price 5 in objects.json -- confirmed real
        # data, not a fabricated fixture, so this also catches a stale/
        # renumbered objects.json out from under the test.
        player = _player_with_reloaded_item(1, 'compass')
        ctx = _FakeCtx(['s', '1', 'y', 'q'], player,
                       items=[{'number': 1, 'name': 'compass', 'price': 5}])
        await pawn_main(ctx)
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 50)  # price * 10
        self.assertIn("I'll give ya 50 silver for the compass,", ctx._flat())

    async def test_reloaded_items_own_zeroed_price_is_not_used(self):
        player = _player_with_reloaded_item(1, 'compass')
        self.assertEqual(getattr(player.inventory.entries(ItemCategory.ITEM)[0].item, 'price', 0), 0,
                          'test setup sanity check: from_json() should not restore price')

    async def test_unknown_item_id_falls_back_to_entrys_own_price(self):
        # Item not found in ctx.server.items at all (e.g. removed from
        # objects.json, or a freshly-picked-up item that still has its
        # own real .price) -- falls back rather than always zeroing out.
        player = _new_player('Rulan')
        player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 0)
        item = Item(id_number=9999, name='mystery trinket', category=ItemCategory.ITEM, price=7)
        player.inventory = Inventory()
        player.inventory.add(item)
        ctx = _FakeCtx(['s', '1', 'y', 'q'], player, items=[])
        await pawn_main(ctx)
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 70)

    async def test_zero_price_item_still_refuses_the_sale(self):
        player = _player_with_reloaded_item(2, 'worthless junk')
        ctx = _FakeCtx(['s', '1', 'q'], player,
                       items=[{'number': 2, 'name': 'worthless junk', 'price': 0}])
        await pawn_main(ctx)
        self.assertIn("I'll give ya nothing for the worthless junk.", ctx._flat())
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 0)


if __name__ == '__main__':
    unittest.main()
