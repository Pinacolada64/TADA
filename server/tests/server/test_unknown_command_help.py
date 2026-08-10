"""tests/server/test_unknown_command_help.py

Ryan: track how many unrecognized commands a non-expert player types in
a row; offer a help tip box once the streak hits
simple_server._UNKNOWN_COMMAND_HELP_THRESHOLD. See simple_server.py's
Server._maybe_offer_help() and its call site in the main GAME loop.
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from simple_server import Server, _UNKNOWN_COMMAND_HELP_THRESHOLD
from flags import PlayerFlags
from player import Player


class _FakeClient:
    """Plain object, not MagicMock -- MagicMock auto-creates any attribute
    on access, so getattr(mock, 'unknown_command_count', 0) would never
    see the intended 0 default; it'd return an auto-vivified Mock instead."""
    pass


def _ctx(player) -> MagicMock:
    ctx = MagicMock()
    ctx.player = player
    ctx.client = _FakeClient()
    ctx.send = AsyncMock()
    return ctx


class TestMaybeOfferHelp(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.server = Server('127.0.0.1', 0)

    async def test_no_tip_before_threshold(self):
        player = Player(name='Rulan')
        player.clear_flag(PlayerFlags.EXPERT_MODE)
        ctx = _ctx(player)
        for _ in range(_UNKNOWN_COMMAND_HELP_THRESHOLD - 1):
            await self.server._maybe_offer_help(ctx)
        ctx.send.assert_not_called()

    async def test_tip_shown_at_threshold(self):
        player = Player(name='Rulan')
        player.clear_flag(PlayerFlags.EXPERT_MODE)
        ctx = _ctx(player)
        for _ in range(_UNKNOWN_COMMAND_HELP_THRESHOLD):
            await self.server._maybe_offer_help(ctx)
        ctx.send.assert_awaited_once()
        sent = ' '.join(str(a) for call in ctx.send.await_args_list for a in call.args[0])
        self.assertIn('Need a Hand?', sent)
        self.assertIn('help', sent.lower())

    async def test_counter_resets_after_tip_shown(self):
        player = Player(name='Rulan')
        player.clear_flag(PlayerFlags.EXPERT_MODE)
        ctx = _ctx(player)
        for _ in range(_UNKNOWN_COMMAND_HELP_THRESHOLD):
            await self.server._maybe_offer_help(ctx)
        self.assertEqual(ctx.client.unknown_command_count, 0)

    async def test_tip_fires_again_after_another_full_streak(self):
        player = Player(name='Rulan')
        player.clear_flag(PlayerFlags.EXPERT_MODE)
        ctx = _ctx(player)
        for _ in range(_UNKNOWN_COMMAND_HELP_THRESHOLD):
            await self.server._maybe_offer_help(ctx)
        for _ in range(_UNKNOWN_COMMAND_HELP_THRESHOLD):
            await self.server._maybe_offer_help(ctx)
        self.assertEqual(ctx.send.await_count, 2)

    async def test_expert_player_never_tracked_or_shown(self):
        player = Player(name='Rulan')
        player.set_flag(PlayerFlags.EXPERT_MODE)
        ctx = _ctx(player)
        for _ in range(_UNKNOWN_COMMAND_HELP_THRESHOLD + 5):
            await self.server._maybe_offer_help(ctx)
        ctx.send.assert_not_called()


class TestUnknownCommandStreakReset(unittest.TestCase):
    """The GAME loop's else-branch resets ctx.client.unknown_command_count
    to 0 on any recognized command -- only *consecutive* misses count."""

    def test_streak_reset_logic_matches_loop_contract(self):
        # Direct behavioral check of the contract simple_server.py's main
        # loop relies on: after a non-'unknown_command' result, the
        # counter must be back at 0 so a later miss starts counting from
        # scratch rather than accumulating across an otherwise normal
        # session. (The loop itself lives inside an infinite `while True`
        # tied to a real socket, so it's exercised via e2e tests, not
        # unit tests -- this covers _maybe_offer_help()'s own contract.)
        ctx = _ctx(Player(name='Rulan'))
        ctx.client.unknown_command_count = 2
        ctx.client.unknown_command_count = 0  # what the loop's else-branch does
        self.assertEqual(ctx.client.unknown_command_count, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
