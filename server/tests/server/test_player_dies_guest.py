"""tests/server/test_player_dies_guest.py

Regression test: Server._player_dies() (simple_server.py) called
player.map_level unguarded inside mark_visited(), which GuestPlayer
doesn't have. Since _player_dies() is called directly from _game_loop's
own call chain (not through Command.execute()), an uncaught
AttributeError there isn't caught by command_processor.py's try/except
-- it propagates out of handle_connection() and kills the guest's whole
connection, same bug class as _maybe_offer_help's ctx.player.is_expert
(see test_unknown_command_help.py's test_guest_player_does_not_crash).

Found via a live-testing audit, 2026-08-19: a guest who takes lethal
damage in combat reaches this path.
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from simple_server import Server
from network_context import GuestPlayer
from player import Player


def _ctx(player) -> MagicMock:
    ctx = MagicMock()
    ctx.player = player
    ctx.client = MagicMock()
    ctx.client.room = 5
    ctx.send = AsyncMock()
    return ctx


class TestPlayerDiesGuest(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.server = Server('127.0.0.1', 0)

    async def test_guest_player_does_not_crash(self):
        player = GuestPlayer()
        player.hit_points = 0
        ctx = _ctx(player)

        # Must not raise -- this is the actual regression.
        await self.server._player_dies(ctx)

        self.assertEqual(player.hit_points, 10)
        self.assertEqual(player.map_room, 1)

    async def test_real_player_still_gets_visited_room_tracking(self):
        """The GuestPlayer guard must not accidentally skip this for a
        real Player -- mark_visited still needs to run for them."""
        player = Player(name='Rulan')
        player.hit_points = 0
        ctx = _ctx(player)

        await self.server._player_dies(ctx)

        self.assertEqual(player.hit_points, 10)
        self.assertEqual(player.map_room, 1)
        self.assertTrue(player.unsaved_changes)


if __name__ == '__main__':
    unittest.main(verbosity=2)
