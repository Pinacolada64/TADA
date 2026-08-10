"""tests/client/test_prefs_terminal_menu.py

Coverage for commands/prefs.py's 'T' (Terminal Settings) submenu --
folds what used to be three separate top-level PREFS rows (Client Type,
Tab Key, Line Ending) into one place.
"""
from __future__ import annotations

import unittest

from player import Player
from commands.prefs import prefs_menu, _terminal_menu


class _FakeCtx:
    def __init__(self, responses, player):
        self._q = list(responses)
        self.sent: list = []
        self.player = player

    async def send(self, *args):
        for a in args:
            self.sent.append(a)

    async def prompt(self, prompt_text: str = '', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        if prompt_text:
            self.sent.append(prompt_text)
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


class TestTerminalMenuStandalone(unittest.IsolatedAsyncioTestCase):

    async def test_shows_all_three_rows(self):
        ctx = _FakeCtx([''], Player())
        await _terminal_menu(ctx)
        text = ctx._flat()
        for word in ('Client', 'Type', 'Tab', 'Key', 'Line', 'Ending'):
            self.assertIn(word, text)

    async def test_blank_returns_without_prompting_again(self):
        ctx = _FakeCtx([''], Player())
        await _terminal_menu(ctx)
        self.assertEqual(ctx._flat().count('Terminal Settings'), 1)

    async def test_hk_shows_tab_key_help(self):
        ctx = _FakeCtx(['hk', ''], Player())
        await _terminal_menu(ctx)
        self.assertIn('Tab', ctx._flat())

    async def test_hl_shows_line_ending_help(self):
        ctx = _FakeCtx(['hl', ''], Player())
        await _terminal_menu(ctx)
        self.assertIn('CRLF', ctx._flat())

    async def test_unknown_key_reprompts_with_choose_message(self):
        ctx = _FakeCtx(['zzz', ''], Player())
        await _terminal_menu(ctx)
        self.assertIn('Choose', ctx._flat())


class TestTerminalMenuFromMainPrefs(unittest.IsolatedAsyncioTestCase):

    async def test_t_opens_submenu_from_main_menu(self):
        ctx = _FakeCtx(['t', '', ''], Player())
        await prefs_menu(ctx)
        text = ctx._flat()
        self.assertIn('Terminal Settings', text)
        self.assertIn('Tab', text)

    async def test_main_menu_no_longer_lists_k_l_as_top_level_keys(self):
        ctx = _FakeCtx([''], Player())
        await prefs_menu(ctx)
        text = ctx._flat()
        prompt_line = next(ln for ln in ctx.sent if isinstance(ln, str) and 'to change' in ln)
        keys = prompt_line.split(' to change')[0].split()
        for moved in ('K', 'L'):
            self.assertNotIn(moved, keys)


if __name__ == '__main__':
    unittest.main()
