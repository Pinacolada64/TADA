"""tests/ship/test_general_store.py

Covers ship/main.py's General Store wiring -- SPUR.SHIP.S's own `general`
subroutine stocks rations.json #70-75 (sci-fi rations like FORMULAE H2O),
distinct from the regular Merchant Shoppe's #1-10 (shoppe/main.py's
_general_store). Both reuse the same shoppe/main.py implementation via
its new `numbers` filter.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from base_classes import PlayerMoneyTypes
from flags import PlayerFlags
from inventory import Inventory
from player import Player
from ship.main import _general_store as ship_general_store
from shoppe.main import _general_store as regular_general_store


def _new_player(name: str) -> Player:
    player = Player(name=name)
    player.clear_flag(PlayerFlags.DEBUG_MODE)
    player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 100000)
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


class TestShipGeneralStoreStocksSciFiRations(unittest.IsolatedAsyncioTestCase):
    async def test_formulae_h2o_is_stocked_on_the_ship(self):
        player = _new_player('Rulan')
        ctx = _FakeCtx([''], player)
        await ship_general_store(ctx)
        self.assertIn('FORMULAE H2O', ctx._flat())

    async def test_regular_shop_rations_are_not_stocked_on_the_ship(self):
        # #1-10 (e.g. TEA) is the regular shop's own range -- must not leak onto the ship.
        player = _new_player('Rulan')
        ctx = _FakeCtx([''], player)
        await ship_general_store(ctx)
        self.assertNotIn('TEA', ctx._flat())

    async def test_regular_shop_does_not_stock_formulae_h2o(self):
        player = _new_player('Rulan')
        ctx = _FakeCtx([''], player)
        await regular_general_store(ctx)
        self.assertNotIn('FORMULAE H2O', ctx._flat())

    async def test_can_buy_formulae_h2o_on_the_ship(self):
        player = _new_player('Rulan')
        # #73 FORMULAE H2O is 4th in the #70-75 range -> choice "4".
        ctx = _FakeCtx(['4'], player)
        await ship_general_store(ctx)
        bought = [e.item.name for e in player.inventory.entries()]
        self.assertIn('FORMULAE H2O', bought)


if __name__ == '__main__':
    unittest.main()
