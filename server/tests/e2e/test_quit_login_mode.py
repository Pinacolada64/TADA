"""tests/test_quit_login_mode.py

Regression test for a real gap: simple_server.py's _login() loop has
always checked result.data.get('quit') to drop the connection cleanly,
and the login banner has always advertised "or 'quit' to leave" -- but
QuitCommand.modes was {Mode.GAME} only, so typing 'quit' at the bare
login prompt (before 'connect'/'new') always failed with "not available
right now". commands/base_command.py's own Mode docstring already
documented the intent ("LOGIN -- before authentication (connect, new,
quit)"), just never wired up.

Fix: QuitCommand.modes = {Mode.ANY}; execute() checks the live
CommandProcessor's current_mode and, for Mode.LOGIN, skips the "Leave
SPUR [Y/N]?" confirmation and session bonuses/farewells/stat-restore
(there's no authenticated player state to save yet) and just
disconnects. Mode.GAME behavior is unchanged.

Run with:
    python -m pytest tests/test_quit_login_mode.py -v
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from commands.base_command import Mode
from commands.quit import QuitCommand


def _make_ctx(current_mode):
    ctx = MagicMock()
    ctx.client.command_processor.current_mode = current_mode
    ctx.send      = AsyncMock()
    ctx.send_room = AsyncMock()
    ctx.prompt    = AsyncMock(return_value='Y')
    return ctx


class TestQuitModeIsAny(unittest.TestCase):

    def test_modes_is_any(self):
        self.assertEqual(QuitCommand.modes, {Mode.ANY})

    def test_is_available_in_login_mode(self):
        cmd = QuitCommand()
        self.assertTrue(cmd.is_available_in(Mode.LOGIN))

    def test_is_available_in_game_mode(self):
        cmd = QuitCommand()
        self.assertTrue(cmd.is_available_in(Mode.GAME))


class TestQuitDuringLogin(unittest.IsolatedAsyncioTestCase):

    async def test_login_mode_skips_confirmation_prompt(self):
        ctx = _make_ctx(Mode.LOGIN)
        result = await QuitCommand().execute(ctx)
        ctx.prompt.assert_not_awaited()
        self.assertTrue(result.success)
        self.assertTrue(result.data.get('quit'))

    async def test_login_mode_sends_goodbye(self):
        ctx = _make_ctx(Mode.LOGIN)
        await QuitCommand().execute(ctx)
        ctx.send.assert_awaited_once_with('Goodbye!')

    async def test_login_mode_does_not_touch_player_state(self):
        """No confirmation, no session bonus/farewell/stat-restore text --
        there's no authenticated player yet to have any of that."""
        ctx = _make_ctx(Mode.LOGIN)
        await QuitCommand().execute(ctx)
        ctx.send_room.assert_not_awaited()


class TestQuitDuringGameUnchanged(unittest.IsolatedAsyncioTestCase):

    async def test_game_mode_still_asks_confirmation(self):
        ctx = _make_ctx(Mode.GAME)
        from player import Player
        ctx.player = Player(name='Rulan')
        await QuitCommand().execute(ctx)
        ctx.prompt.assert_awaited_once()

    async def test_game_mode_declining_confirmation_does_not_quit(self):
        ctx = _make_ctx(Mode.GAME)
        ctx.prompt = AsyncMock(return_value='N')
        from player import Player
        ctx.player = Player(name='Rulan')
        result = await QuitCommand().execute(ctx)
        self.assertFalse(result.data.get('quit'))

    async def test_missing_command_processor_defaults_to_game_mode(self):
        """A ctx without a live command_processor (e.g. some test
        fixtures) must not crash -- falls back to the fuller Mode.GAME
        behavior rather than silently skipping it."""
        ctx = MagicMock(spec=['player', 'send', 'send_room', 'prompt', 'client'])
        ctx.client = MagicMock(spec=[])   # no .command_processor attribute
        ctx.send      = AsyncMock()
        ctx.send_room = AsyncMock()
        ctx.prompt    = AsyncMock(return_value='Y')
        from player import Player
        ctx.player = Player(name='Rulan')
        await QuitCommand().execute(ctx)
        ctx.prompt.assert_awaited_once()


if __name__ == '__main__':
    unittest.main(verbosity=2)
