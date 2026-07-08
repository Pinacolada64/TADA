"""tests/test_more_prompt.py

Unit tests tying PlayerFlags.MORE_PROMPT to actual pagination behavior:

  - network_context.GameContext._wants_pagination() / send() only pause
    between screenfuls (via _paginate()) when the flag is on; when off,
    the full output is sent in one shot via _send_formatted() regardless
    of length.
  - commands/prefs.py's 'M' menu key and standalone 'mp' command
    (commands/more_prompt.py) both toggle the same flag via the shared
    toggle_more_prompt() helper.

Run with:
    python -m pytest tests/test_more_prompt.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

from flags import PlayerFlags
from network_context import GameContext
from commands.more_prompt import MorePromptCommand
from commands.prefs import toggle_more_prompt


class _FakePlayer:
    def __init__(self, more_prompt: bool = True):
        self._flags = {PlayerFlags.MORE_PROMPT: more_prompt}
        self.client_settings = type('CS', (), {'screen_rows': 10, 'screen_columns': 80})()

    def query_flag(self, flag) -> bool:
        return self._flags.get(flag, False)

    def set_flag(self, flag):
        self._flags[flag] = True

    def clear_flag(self, flag):
        self._flags[flag] = False


def _make_ctx(more_prompt: bool = True) -> GameContext:
    ctx = GameContext(player=_FakePlayer(more_prompt), reader=None, writer=None,
                       server=None, client=None)
    ctx._paginate = AsyncMock()
    ctx._send_formatted = AsyncMock()
    return ctx


class TestWantsPagination(unittest.TestCase):

    def test_short_output_never_paginates(self):
        ctx = _make_ctx(more_prompt=True)
        self.assertFalse(ctx._wants_pagination(['a', 'b'], page_size=10))

    def test_long_output_paginates_when_flag_on(self):
        ctx = _make_ctx(more_prompt=True)
        lines = [f'line {i}' for i in range(20)]
        self.assertTrue(ctx._wants_pagination(lines, page_size=10))

    def test_long_output_does_not_paginate_when_flag_off(self):
        ctx = _make_ctx(more_prompt=False)
        lines = [f'line {i}' for i in range(20)]
        self.assertFalse(ctx._wants_pagination(lines, page_size=10))


class TestSendDispatchesOnFlag(unittest.IsolatedAsyncioTestCase):

    async def test_send_paginates_when_flag_on(self):
        ctx = _make_ctx(more_prompt=True)
        await ctx.send(*[f'line {i}' for i in range(20)])
        ctx._paginate.assert_awaited_once()
        ctx._send_formatted.assert_not_awaited()

    async def test_send_dumps_everything_when_flag_off(self):
        ctx = _make_ctx(more_prompt=False)
        lines = [f'line {i}' for i in range(20)]
        await ctx.send(*lines)
        ctx._paginate.assert_not_awaited()
        ctx._send_formatted.assert_awaited_once()
        (sent_lines,), _ = ctx._send_formatted.await_args
        self.assertEqual(len(sent_lines), 20)


class TestToggleMorePrompt(unittest.IsolatedAsyncioTestCase):

    async def test_toggle_off_from_on(self):
        player = _FakePlayer(more_prompt=True)
        ctx = GameContext(player=player, reader=None, writer=None, server=None, client=None)
        ctx.send = AsyncMock()
        await toggle_more_prompt(ctx)
        self.assertFalse(player.query_flag(PlayerFlags.MORE_PROMPT))

    async def test_toggle_on_from_off(self):
        player = _FakePlayer(more_prompt=False)
        ctx = GameContext(player=player, reader=None, writer=None, server=None, client=None)
        ctx.send = AsyncMock()
        await toggle_more_prompt(ctx)
        self.assertTrue(player.query_flag(PlayerFlags.MORE_PROMPT))


class TestMorePromptCommand(unittest.IsolatedAsyncioTestCase):

    async def test_execute_toggles_flag(self):
        player = _FakePlayer(more_prompt=True)
        ctx = GameContext(player=player, reader=None, writer=None, server=None, client=None)
        ctx.send = AsyncMock()
        result = await MorePromptCommand().execute(ctx)
        self.assertTrue(result.success)
        self.assertFalse(player.query_flag(PlayerFlags.MORE_PROMPT))

    def test_available_in_login_and_game(self):
        from commands.base_command import Mode
        self.assertEqual(MorePromptCommand.modes, {Mode.LOGIN, Mode.GAME})

    def test_name_and_alias(self):
        self.assertEqual(MorePromptCommand.name, 'mp')
        self.assertIn('moreprompt', MorePromptCommand.aliases)


if __name__ == '__main__':
    unittest.main(verbosity=2)
