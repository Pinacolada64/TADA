"""tests/client/test_prefs_date_time_menu.py

Coverage for commands/prefs.py's 'D' (Date & Time) submenu -- folds what
used to be three separate top-level PREFS rows (Timezone, Date Format,
Time Format) plus the standalone Hourglass Display toggle into one
place.
"""
from __future__ import annotations

import unittest

from flags import PlayerFlags
from player import Player
from commands.prefs import prefs_menu, _date_time_menu


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


class TestDateTimeMenuStandalone(unittest.IsolatedAsyncioTestCase):

    async def test_shows_all_four_rows(self):
        ctx = _FakeCtx([''], Player())
        await _date_time_menu(ctx)
        text = ctx._flat()
        for word in ('Timezone', 'Date', 'Format', 'Time', 'Hourglass', 'Display'):
            self.assertIn(word, text)

    async def test_blank_returns_without_prompting_again(self):
        ctx = _FakeCtx([''], Player())
        await _date_time_menu(ctx)
        self.assertEqual(ctx._flat().count('Date & Time'), 1)

    async def test_h_toggles_hourglass(self):
        player = Player()
        player.clear_flag(PlayerFlags.HOURGLASS)
        ctx = _FakeCtx(['h', ''], player)
        await _date_time_menu(ctx)
        self.assertTrue(player.query_flag(PlayerFlags.HOURGLASS))
        self.assertIn('Hourglass display:', ctx._flat())

    async def test_h_toggle_is_idempotent_pair(self):
        player = Player()
        player.set_flag(PlayerFlags.HOURGLASS)
        ctx = _FakeCtx(['h', 'h', ''], player)
        await _date_time_menu(ctx)
        self.assertTrue(player.query_flag(PlayerFlags.HOURGLASS))

    async def test_hz_shows_timezone_help(self):
        ctx = _FakeCtx(['hz', ''], Player())
        await _date_time_menu(ctx)
        self.assertIn('Timezone', ctx._flat())

    async def test_hh_shows_hourglass_help_without_toggling(self):
        player = Player()
        player.clear_flag(PlayerFlags.HOURGLASS)
        ctx = _FakeCtx(['hh', ''], player)
        await _date_time_menu(ctx)
        self.assertIn('Hourglass Display', ctx._flat())
        self.assertFalse(player.query_flag(PlayerFlags.HOURGLASS))

    async def test_unknown_key_reprompts_with_choose_message(self):
        ctx = _FakeCtx(['zzz', ''], Player())
        await _date_time_menu(ctx)
        self.assertIn('Choose', ctx._flat())


class TestDateTimeMenuFromMainPrefs(unittest.IsolatedAsyncioTestCase):

    async def test_d_opens_submenu_from_main_menu(self):
        ctx = _FakeCtx(['d', '', ''], Player())
        await prefs_menu(ctx)
        text = ctx._flat()
        self.assertIn('Date & Time', text)
        self.assertIn('Hourglass', text)

    async def test_main_menu_no_longer_lists_z_f_h_as_top_level_keys(self):
        ctx = _FakeCtx([''], Player())
        await prefs_menu(ctx)
        text = ctx._flat()
        prompt_line = next(ln for ln in ctx.sent if isinstance(ln, str) and 'to change' in ln)
        keys = prompt_line.split(' to change')[0].split()
        for moved in ('Z', 'F', 'H'):
            self.assertNotIn(moved, keys)


if __name__ == '__main__':
    unittest.main()
