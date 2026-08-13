"""tests/commands/test_drink_fountain_pool.py — commands/drink.py's
Fountain of Youth (level 5, room 105) and generic "POOL OF WATER" floor
object (SPUR.SUB.S 'fountain'/'pool' labels).
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from commands.drink import DrinkCommand
from inventory import Inventory


def _make_player(hit_points=5, map_level=5, drink=5):
    player = MagicMock()
    player.inventory = Inventory()
    player.map_level = map_level
    player.hit_points = hit_points
    player.xp_level = 1
    player.poisoned = False
    player.diseased = False
    player.ring_drain = {}
    player.stats = {}
    player.drink = drink
    player.unsaved_changes = False
    return player


def _room(food=0, desc=''):
    room = MagicMock()
    room.food = food
    room.desc = desc
    return room


class _FakeCtx:
    def __init__(self, player, room_no=105, room=None):
        self.player = player
        self.client = MagicMock()
        self.client.room = room_no
        self.server = MagicMock()
        self.server.game_map.get_room = MagicMock(return_value=room)
        self.sent: list = []
        self.send = AsyncMock(side_effect=self._record)
        self.prompt = AsyncMock(return_value='')

    async def _record(self, msg, **kwargs):
        if isinstance(msg, list):
            self.sent.extend(msg)
        else:
            self.sent.append(msg)


class TestFountainOfYouth(unittest.IsolatedAsyncioTestCase):

    async def test_full_restore_at_fountain_room(self):
        player = _make_player(hit_points=5, map_level=5)
        player.has_item = MagicMock(return_value=False)
        ctx = _FakeCtx(player, room_no=105)
        await DrinkCommand().execute(ctx)
        self.assertGreater(player.hit_points, 5)

    async def test_no_effect_outside_fountain_room(self):
        player = _make_player(hit_points=5, map_level=1)
        player.has_item = MagicMock(return_value=False)
        ctx = _FakeCtx(player, room_no=1, room=_room())
        await DrinkCommand().execute(ctx)
        self.assertEqual(player.hit_points, 5)

    async def test_charges_amulet_of_life_if_carried_uncharged(self):
        from flags import PlayerFlags
        player = _make_player(hit_points=5, map_level=5)
        player.has_item = MagicMock(return_value=True)
        player.query_flag = MagicMock(return_value=False)
        player.set_flag = MagicMock()
        ctx = _FakeCtx(player, room_no=105)
        await DrinkCommand().execute(ctx)
        player.set_flag.assert_any_call(PlayerFlags.AMULET_OF_LIFE_ENERGIZED)


class TestPoolOfWater(unittest.IsolatedAsyncioTestCase):

    async def test_auto_quenches_thirst(self):
        player = _make_player(drink=2, map_level=1)
        room = _room(food=51)
        ctx = _FakeCtx(player, room_no=1, room=room)
        await DrinkCommand().execute(ctx)
        self.assertGreater(player.drink, 2)
        self.assertTrue(any('drink your fill' in s for s in ctx.sent))

    async def test_no_effect_in_ordinary_room(self):
        player = _make_player(drink=2, map_level=1)
        room = _room(food=0)
        ctx = _FakeCtx(player, room_no=1, room=room)
        await DrinkCommand().execute(ctx)
        self.assertEqual(player.drink, 2)


if __name__ == '__main__':
    unittest.main()
