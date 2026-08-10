"""tests/client/test_prefs_colors_graphics_menu.py

Coverage for commands/prefs.py's 'C' (Colors & Graphics) submenu --
folds what used to be five separate top-level PREFS rows (Colors, Menu
Colors, Table Colors, Border Style, Graphics Test) into one place.
"""
from __future__ import annotations

import unittest

from player import Player
from commands.prefs import prefs_menu, _colors_graphics_menu


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


class TestColorsGraphicsMenuStandalone(unittest.IsolatedAsyncioTestCase):

    async def test_shows_all_five_rows(self):
        # 40-column default screen wraps multi-word labels across
        # separate table cells ("Menu" / "Colors" on different lines
        # with a "|" border between them), so check each word rather
        # than an exact multi-word substring.
        ctx = _FakeCtx([''], Player())
        await _colors_graphics_menu(ctx)
        text = ctx._flat()
        for word in ('Colors', 'Menu', 'Table', 'Border', 'Style', 'Graphics', 'Test'):
            self.assertIn(word, text)

    async def test_blank_returns_without_prompting_again(self):
        ctx = _FakeCtx([''], Player())
        await _colors_graphics_menu(ctx)
        # Only one menu display's worth of prompts -- if it looped, the
        # queue-exhaustion None would still return cleanly, but the
        # sent log would carry a second copy of the menu.
        self.assertEqual(ctx._flat().count('Colors & Graphics'), 1)

    async def test_g_opens_graphics_test_and_returns_to_submenu(self):
        ctx = _FakeCtx(['g', ''], Player())
        await _colors_graphics_menu(ctx)
        self.assertIn('Graphics Test', ctx._flat())
        self.assertIn('Special Glyphs', ctx._flat())

    async def test_hb_shows_border_style_help(self):
        ctx = _FakeCtx(['hb', ''], Player())
        await _colors_graphics_menu(ctx)
        self.assertIn('Border Style', ctx._flat())

    async def test_hg_shows_graphics_test_help(self):
        ctx = _FakeCtx(['hg', ''], Player())
        await _colors_graphics_menu(ctx)
        self.assertIn('windowpane', ctx._flat().lower())

    async def test_unknown_key_reprompts_with_choose_message(self):
        ctx = _FakeCtx(['zzz', ''], Player())
        await _colors_graphics_menu(ctx)
        self.assertIn('Choose', ctx._flat())


class TestColorsGraphicsMenuFromMainPrefs(unittest.IsolatedAsyncioTestCase):

    async def test_c_opens_submenu_from_main_menu(self):
        ctx = _FakeCtx(['c', '', ''], Player())
        await prefs_menu(ctx)
        text = ctx._flat()
        self.assertIn('Colors & Graphics', text)
        self.assertIn('Table', text)

    async def test_main_menu_no_longer_lists_b_s_a_g_as_top_level_keys(self):
        ctx = _FakeCtx([''], Player())
        await prefs_menu(ctx)
        text = ctx._flat()
        # The main menu's own prompt line lists its valid keys space-
        # separated -- none of the moved single-letter keys should be
        # among them (still fine if 'C' itself appears, that's expected).
        prompt_line = next(ln for ln in ctx.sent if isinstance(ln, str) and 'to change' in ln)
        keys = prompt_line.split(' to change')[0].split()
        for moved in ('B', 'S', 'A', 'G'):
            self.assertNotIn(moved, keys)


if __name__ == '__main__':
    unittest.main()
