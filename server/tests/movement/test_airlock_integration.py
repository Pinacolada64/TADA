"""tests/movement/test_airlock_integration.py

End-to-end coverage of the one real instance of SPUR's boat/vehicle-
launch mechanic in the converted game: level 6's Air Lock (room 277,
VEHICLE_EXIT_WEST -- requires a spacesuit to leave heading back into the
vacuum) and Outer Space (room 276, VEHICLE_DEPARTURE_EAST -- "you get
out of your spacesuit" flavor leaving back toward the ship). Both rooms'
raw exit_e/exit_w flags are 0 in the original SPUR data (see TODO.md's
"SPUR boat/vehicle-launch exit flavor text" entry) -- the east/west
exits connecting them exist only because this session added them,
completing what looked like an abandoned SPUR set-piece.

Drives the real MoveCommand (commands/movement.py) against a real
Server/game_map (simple_server.py), not mocks, so both halves of the
split (movement.py's pre-move gate, simple_server.py's post-resolution
flavor) are exercised together exactly as a player would trigger them.
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from commands.movement import MoveCommand
from inventory import Inventory
from items import Item, ItemCategory
from simple_server import Server

_SPACESUIT_ID = 122
_AIR_LOCK_ROOM = 277
_OUTER_SPACE_ROOM = 276


def run(coro):
    return asyncio.run(coro)


def _make_ctx(server, *, room, item_ids=()):
    ctx = MagicMock()
    ctx.server = server
    ctx.client.room = room
    ctx.player.map_level = 6
    ctx.player.map_room = room
    ctx.player.inventory = Inventory()
    for item_id in item_ids:
        ctx.player.inventory.add(Item(id_number=item_id, name=f'item{item_id}', category=ItemCategory.ITEM))
    ctx.player.query_flag = MagicMock(return_value=False)  # not mounted
    ctx.send = AsyncMock()
    return ctx


class TestAirlockData(unittest.TestCase):
    """The room data itself -- confirms the completion is actually in place."""

    def setUp(self):
        self.server = Server('127.0.0.1', 0)

    def test_air_lock_has_vehicle_exit_west(self):
        room = self.server.game_map.get_room(6, _AIR_LOCK_ROOM)
        self.assertIn('vehicle_exit_west', room.flags)
        self.assertEqual(room.get_exit('w'), _OUTER_SPACE_ROOM)

    def test_outer_space_has_vehicle_departure_east(self):
        room = self.server.game_map.get_room(6, _OUTER_SPACE_ROOM)
        self.assertIn('vehicle_departure_east', room.flags)
        self.assertEqual(room.get_exit('e'), _AIR_LOCK_ROOM)


class TestLeavingAirLockWithoutSpacesuit(unittest.IsolatedAsyncioTestCase):

    async def test_blocked_and_not_relocated(self):
        server = Server('127.0.0.1', 0)
        ctx = _make_ctx(server, room=_AIR_LOCK_ROOM)

        result = await MoveCommand().execute(ctx, 'w')

        self.assertFalse(result.success)
        self.assertEqual(ctx.client.room, _AIR_LOCK_ROOM)
        self.assertIn('Not without a spacesuit!', str(ctx.send.call_args))


class TestLeavingAirLockWithSpacesuit(unittest.IsolatedAsyncioTestCase):

    async def test_succeeds_and_relocates_to_outer_space(self):
        server = Server('127.0.0.1', 0)
        ctx = _make_ctx(server, room=_AIR_LOCK_ROOM, item_ids=[_SPACESUIT_ID])

        result = await MoveCommand().execute(ctx, 'w')

        self.assertTrue(result.success)
        self.assertEqual(ctx.client.room, _OUTER_SPACE_ROOM)
        sent = str(ctx.send.call_args_list)
        self.assertIn('You put on your spacesuit', sent)


class TestReturningToAirLock(unittest.IsolatedAsyncioTestCase):
    """No item gate on this side (VEHICLE_DEPARTURE_* only) -- the flavor
    line plays regardless of inventory, matching SPUR's own travel1
    (no item check on that path, see RoomFlag.VEHICLE_DEPARTURE_*)."""

    async def test_succeeds_without_a_spacesuit_and_shows_flavor(self):
        server = Server('127.0.0.1', 0)
        ctx = _make_ctx(server, room=_OUTER_SPACE_ROOM)

        result = await MoveCommand().execute(ctx, 'e')

        self.assertTrue(result.success)
        self.assertEqual(ctx.client.room, _AIR_LOCK_ROOM)
        sent = str(ctx.send.call_args_list)
        self.assertIn('You get out of your spacesuit', sent)


if __name__ == '__main__':
    unittest.main(verbosity=2)
