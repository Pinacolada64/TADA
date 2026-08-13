"""tests/commands/test_use_vial.py — commands/use.py's Galadriel's Vial
branch (USE vial), SPUR.USE.S 'fl.vial'/'vial' labels: fill the empty vial
(#142) at the Fountain of Youth room (level 5, room 105), then USE the full
vial (#143) anywhere later for a full restore, converting it back to #142.
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from commands.use import UseCommand
from inventory import Inventory
from items import Item, ItemCategory


def _vial(number, name) -> Item:
    return Item(id_number=number, name=name, category=ItemCategory.ITEM)


def _make_player(vial_number, vial_name, hit_points=5, map_level=5):
    player = MagicMock()
    player.inventory = Inventory()
    player.inventory.add(_vial(vial_number, vial_name))
    player.map_level = map_level
    player.hit_points = hit_points
    player.xp_level = 1
    player.poisoned = False
    player.diseased = False
    player.ring_drain = {}
    player.stats = {}
    player.unsaved_changes = False
    return player


class _FakeCtx:
    def __init__(self, player, room_no=105):
        self.player = player
        self.client = MagicMock()
        self.client.room = room_no
        self.server = MagicMock()
        self.server.items = [
            {'number': 142, 'name': "Galadriel's vial (empty)", 'type': 'misc', 'price': 9},
            {'number': 143, 'name': "Galadriel's vial (full)", 'type': 'misc', 'price': 9},
        ]
        self.sent: list = []
        self.send = AsyncMock(side_effect=self._record)
        self.prompt = AsyncMock(return_value='')

    async def _record(self, msg, **kwargs):
        if isinstance(msg, list):
            self.sent.extend(msg)
        else:
            self.sent.append(msg)


class TestFillVial(unittest.IsolatedAsyncioTestCase):

    async def test_fills_at_fountain_room(self):
        player = _make_player(142, "Galadriel's vial (empty)", map_level=5)
        ctx = _FakeCtx(player, room_no=105)
        await UseCommand().execute(ctx, 'vial')
        self.assertTrue(any('fill the vial' in s for s in ctx.sent))
        self.assertFalse(player.inventory.find(item_id=142))
        self.assertTrue(player.inventory.find(item_id=143))

    async def test_stays_empty_elsewhere(self):
        player = _make_player(142, "Galadriel's vial (empty)", map_level=1)
        ctx = _FakeCtx(player, room_no=1)
        await UseCommand().execute(ctx, 'vial')
        self.assertTrue(any('empty' in s.lower() for s in ctx.sent))
        self.assertTrue(player.inventory.find(item_id=142))


class TestDrinkVial(unittest.IsolatedAsyncioTestCase):

    async def test_full_vial_restores_and_empties(self):
        player = _make_player(143, "Galadriel's vial (full)", hit_points=5, map_level=1)
        ctx = _FakeCtx(player, room_no=1)
        await UseCommand().execute(ctx, 'vial')
        self.assertGreater(player.hit_points, 5)
        self.assertFalse(player.inventory.find(item_id=143))
        self.assertTrue(player.inventory.find(item_id=142))

    async def test_full_vial_at_fountain_says_already_full(self):
        player = _make_player(143, "Galadriel's vial (full)", hit_points=5, map_level=5)
        ctx = _FakeCtx(player, room_no=105)
        await UseCommand().execute(ctx, 'vial')
        self.assertTrue(any('already full' in s for s in ctx.sent))
        self.assertEqual(player.hit_points, 5)
        self.assertTrue(player.inventory.find(item_id=143))


if __name__ == '__main__':
    unittest.main()
