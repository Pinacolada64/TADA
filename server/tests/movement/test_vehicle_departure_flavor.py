"""tests/movement/test_vehicle_departure_flavor.py

simple_server.py's VEHICLE_DEPARTURE_* flavor (SPUR.MAIN.S's travel1)
and the NO_ERROR_EXIT_* bypass (SPUR.MAIN.S's block.s -- see TODO.md's
"RoomFlag.BLOCK_MOVE_*..." entry). Unlike VEHICLE_EXIT_* (commands/
movement.py's own pre-move gate, see test_vehicle_exit_gate.py), neither
of these can block a move -- they only add flavor text or, for
NO_ERROR_EXIT_*, suppress the normal failure message without relocating
the player.
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from simple_server import Server


def run(coro):
    return asyncio.run(coro)


def _room(flags):
    room = MagicMock()
    room.flags = flags
    return room


class TestVehicleDepartureFlavor(unittest.TestCase):

    def setUp(self):
        self.server = Server('127.0.0.1', 0)

    def test_no_marker_returns_none(self):
        room = _room([])
        self.assertIsNone(self.server._vehicle_departure_flavor(room, 'e', 5, MagicMock()))

    def test_matching_direction_below_level_6_says_boat(self):
        room = _room(['vehicle_departure_east'])
        flavor = self.server._vehicle_departure_flavor(room, 'e', 5, MagicMock())
        self.assertEqual(flavor, 'You get out of the boat..')

    def test_matching_direction_level_6_says_spacesuit(self):
        room = _room(['vehicle_departure_east'])
        flavor = self.server._vehicle_departure_flavor(room, 'e', 6, MagicMock())
        self.assertEqual(flavor, 'You get out of your spacesuit..')

    def test_non_matching_direction_returns_none(self):
        room = _room(['vehicle_departure_east'])
        self.assertIsNone(self.server._vehicle_departure_flavor(room, 'w', 6, MagicMock()))


class TestNoErrorExitBypassIntegration(unittest.IsolatedAsyncioTestCase):
    """Against the real level 6 data -- room 806 (Outer Space) carries
    'no_error_exit_west' with no real west exit backing it; confirms the
    bypass suppresses "Can't go there." and redisplays the room without
    relocating."""

    async def test_no_error_exit_room_exists_in_level_6(self):
        server = Server('127.0.0.1', 0)
        room = server.game_map.get_room(6, 806)
        self.assertIsNotNone(room)
        self.assertIn('no_error_exit_west', room.flags)
        # No real west exit backing the flag -- that's the whole point.
        self.assertIsNone(room.get_exit('w'))

    async def test_bypass_redisplays_room_without_relocating(self):
        server = Server('127.0.0.1', 0)
        ctx = MagicMock()
        ctx.server = server
        ctx.client.room = 806
        ctx.player.map_level = 6
        ctx.player.map_room = 806
        ctx.send = AsyncMock()

        await server._move(ctx, 'w')

        # Player never actually moved.
        self.assertEqual(ctx.client.room, 806)
        self.assertEqual(ctx.player.map_room, 806)
        # And didn't see the generic failure message.
        sent = str(ctx.send.call_args_list)
        self.assertNotIn("Can't go", sent)

    async def test_normal_blocked_direction_still_shows_failure_message(self):
        # Room 1 has no no_error_exit_* flags at all -- a direction with
        # no real exit there should still hit the plain failure message,
        # confirming the bypass is opt-in per room/direction, not global.
        server = Server('127.0.0.1', 0)
        room = server.game_map.get_room(1, 1)
        no_error_exit_flags = {f for f in (room.flags or []) if f.startswith('no_error_exit')}
        direction_words = {'n': 'north', 's': 'south', 'e': 'east', 'w': 'west'}
        blocked_dir = next(
            (d for d in ('n', 's', 'e', 'w')
             if not room.get_exit(d) and f'no_error_exit_{direction_words[d]}' not in no_error_exit_flags),
            None,
        )
        if blocked_dir is None:
            self.skipTest('room 1 has an exit (or no_error_exit bypass) in every direction; nothing to test here')

        ctx = MagicMock()
        ctx.server = server
        ctx.client.room = 1
        ctx.player.map_level = 1
        ctx.player.map_room = 1
        ctx.send = AsyncMock()

        await server._move(ctx, blocked_dir)

        sent = str(ctx.send.call_args_list)
        self.assertIn("Can't go", sent)


if __name__ == '__main__':
    unittest.main(verbosity=2)
