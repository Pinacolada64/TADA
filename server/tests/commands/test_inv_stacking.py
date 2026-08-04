"""tests/commands/test_inv_stacking.py — INV command display of stacked
items. Adding a second copy of an already-carried item (same id_number)
should stack onto the existing slot (Inventory.add()) rather than create
a second slot, and INV should render that as "2x <name>" (commands/inv.py's
_format_entry()), not two separate lines.
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from commands.inv import InvCommand
from inventory import Inventory
from items import Item, ItemCategory
from party import Party


def _make_player():
    player = MagicMock()
    player.inventory = Inventory(capacity=10)
    player.max_inventory_size = 10
    player.party = Party()
    return player


def _make_ctx(player):
    ctx = MagicMock()
    ctx.player = player
    ctx.send = AsyncMock()
    return ctx


def _sent_text(ctx):
    out = []
    for call in ctx.send.await_args_list:
        for a in call.args:
            if isinstance(a, list):
                out.extend(str(x) for x in a)
            else:
                out.append(str(a))
    return '\n'.join(out)


class TestInvCommandStacking(unittest.IsolatedAsyncioTestCase):
    async def test_second_copy_shows_as_2x_not_a_second_line(self):
        player = _make_player()
        player.inventory.add(Item(id_number=1, name='Torch', category=ItemCategory.ITEM))
        player.inventory.add(Item(id_number=1, name='Torch', category=ItemCategory.ITEM))

        ctx = _make_ctx(player)
        await InvCommand().execute(ctx)
        text = _sent_text(ctx)

        self.assertIn('2x Torch', text)
        self.assertEqual(text.count('Torch'), 1)
        self.assertEqual(len(player.inventory), 1)

    async def test_single_copy_shows_no_quantity_prefix(self):
        player = _make_player()
        player.inventory.add(Item(id_number=1, name='Torch', category=ItemCategory.ITEM))

        ctx = _make_ctx(player)
        await InvCommand().execute(ctx)
        text = _sent_text(ctx)

        self.assertIn('Torch', text)
        self.assertNotIn('1x Torch', text)


if __name__ == '__main__':
    unittest.main()
