"""tests/ship/test_salvage_bay.py

Covers ship/salvage_bay.py -- the Ship's Salvage Bay (SPUR.SHIP.S
`salvage`/`sal.1`/`pwn.1`). Only salvage parts (objects.json #146) can be
sold here, at price*40, and the bay itself is gated to once per session.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from base_classes import PlayerMoneyTypes
from flags import PlayerFlags
from inventory import Inventory
from items import Item, ItemCategory
from player import Player
from ship.salvage_bay import main as salvage_bay_main


def _new_player(name: str) -> Player:
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


def _player_with_item(item_id: int, name: str) -> Player:
    player = _new_player('Rulan')
    player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 0)
    player.inventory = Inventory()
    player.inventory.add(Item(id_number=item_id, name=name, category=ItemCategory.ITEM))
    return player


class TestSalvageBaySellsOnlySalvageParts(unittest.IsolatedAsyncioTestCase):
    async def test_salvage_parts_sell_for_forty_times_price(self):
        player = _player_with_item(146, 'salvage parts')
        ctx = _FakeCtx(['s', '1', 'y', 'q'], player,
                       items=[{'number': 146, 'name': 'salvage parts', 'price': 5}])
        await salvage_bay_main(ctx)
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 200)  # price * 40
        self.assertIn('SALVAGE VALUE 200 GOLD FOR THE salvage parts,', ctx._flat())
        self.assertIn('ACKNOWLEDGED.', ctx._flat())
        self.assertEqual(len(player.inventory.entries(ItemCategory.ITEM)), 0)

    async def test_non_salvage_item_is_refused(self):
        player = _player_with_item(1, 'compass')
        ctx = _FakeCtx(['s', '1', 'q'], player,
                       items=[{'number': 1, 'name': 'compass', 'price': 5}])
        await salvage_bay_main(ctx)
        self.assertIn('NON-SALVAGE STATUS. DOES NOT COMPUTE.', ctx._flat())
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 0)
        # item was never removed
        self.assertEqual(len(player.inventory.entries(ItemCategory.ITEM)), 1)

    async def test_declining_the_sale_keeps_the_item(self):
        player = _player_with_item(146, 'salvage parts')
        ctx = _FakeCtx(['s', '1', 'n', 'q'], player,
                       items=[{'number': 146, 'name': 'salvage parts', 'price': 5}])
        await salvage_bay_main(ctx)
        self.assertIn('bzzz..', ctx._flat())
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 0)
        self.assertEqual(len(player.inventory.entries(ItemCategory.ITEM)), 1)

    async def test_no_items_bails_immediately(self):
        player = _new_player('Rulan')
        player.inventory = Inventory()
        ctx = _FakeCtx(['s'], player)
        await salvage_bay_main(ctx)
        self.assertIn('No Items!!', ctx._flat())


class TestSalvageBayOncePerSession(unittest.IsolatedAsyncioTestCase):
    async def test_second_visit_this_session_is_refused(self):
        player = _player_with_item(146, 'salvage parts')
        ctx = _FakeCtx(['q'], player)
        await salvage_bay_main(ctx)  # first visit sets the flag
        ctx2 = _FakeCtx(['s'], player)
        await salvage_bay_main(ctx2)
        self.assertIn('The salvage computer does not respond.', ctx2._flat())

    async def test_flag_is_recorded_in_once_per_day(self):
        player = _player_with_item(146, 'salvage parts')
        ctx = _FakeCtx(['q'], player)
        await salvage_bay_main(ctx)
        self.assertIn('ship_salvage_bay', player.once_per_day)


if __name__ == '__main__':
    unittest.main()
