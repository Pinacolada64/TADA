"""tests/shoppe/test_armory_stock.py — the Weapons Master's buy list only
offers the first ten weapons (the smith's own stock, SPUR's cb$="2" rows
#1-10). Higher-level weapons are for players to discover by exploring, so
they're neither listed by '?' nor buyable by typing their number.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from shoppe.armory import _buy as armory_buy
from tests.shoppe.test_shop_inventory_wiring import _FakeCtx, _new_player

_WEAPONS = json.loads((Path(__file__).parent / '..' / '..' / 'weapons.json').read_text())


class TestArmoryStock(unittest.IsolatedAsyncioTestCase):
    async def test_list_shows_only_first_ten(self):
        player = _new_player()
        ctx = _FakeCtx(['?', 'q'], player)
        await armory_buy(ctx, player, player.inventory, _WEAPONS)
        listed = [line for line in ctx.sent if isinstance(line, str) and line.endswith('s')
                  and line.strip()[:1].isdigit()]
        self.assertEqual(len(listed), 10)
        flat = ctx._flat()
        for w in _WEAPONS[:10]:
            self.assertIn(w['name'], flat)
        for w in _WEAPONS[10:]:
            self.assertNotIn(w['name'], flat)

    async def test_unlisted_weapon_number_is_not_for_sale(self):
        player = _new_player()
        high = _WEAPONS[13]  # well past the shop's own stock
        ctx = _FakeCtx([str(high['number']), 'q'], player)
        await armory_buy(ctx, player, player.inventory, _WEAPONS)
        self.assertIn('Weapon not available for sale!', ctx._flat())
        self.assertEqual(player.inventory.entries('Weapon'), [])

    async def test_listed_weapon_still_buyable(self):
        player = _new_player()
        first = _WEAPONS[0]
        ctx = _FakeCtx([str(first['number']), 'n', 'y', 'q'], player)
        await armory_buy(ctx, player, player.inventory, _WEAPONS)
        ids = [e.item.id_number for e in player.inventory.entries('Weapon')]
        self.assertEqual(ids, [first['number']])


if __name__ == '__main__':
    unittest.main()
