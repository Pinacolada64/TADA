"""tests/client/test_prefs_graphics_test.py

Coverage for commands/prefs.py's 'G' (Graphics Test) row -- a display-
only windowpane grid (all nine corner/tee/cross border pieces, see
table.Border) for every known border style, so a player can see which
glyphs their terminal actually renders correctly before picking one via
'B' (Border Style). Nothing is stored -- Ryan's idea, a classic BBS
"graphics test" screen.
"""
from __future__ import annotations

import unittest

from player import Player
from commands.prefs import _show_graphics_test, _windowpane_lines
from table import ASCII, SINGLE, DOUBLE, PETSCII


class _FakeCtx:
    def __init__(self, player):
        self.sent: list = []
        self.player = player

    async def send(self, *args):
        for a in args:
            self.sent.append(a)

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


class TestWindowpaneLines(unittest.TestCase):

    def test_single_style_uses_single_line_glyphs(self):
        lines = _windowpane_lines(SINGLE)
        self.assertEqual(lines[0][0], '┌')
        self.assertEqual(lines[2][4], '┼')  # middle cross (default cell_width=3)
        self.assertEqual(lines[-1][-1], '┘')

    def test_shape_is_five_lines_two_by_two_grid(self):
        lines = _windowpane_lines(ASCII, cell_width=3)
        self.assertEqual(len(lines), 5)
        # top, blank, mid, blank, bottom -- all the same visible width.
        widths = {len(ln) for ln in lines}
        self.assertEqual(len(widths), 1)

    def test_cell_width_controls_line_length(self):
        narrow = _windowpane_lines(ASCII, cell_width=1)
        wide   = _windowpane_lines(ASCII, cell_width=5)
        self.assertLess(len(narrow[0]), len(wide[0]))


class TestShowGraphicsTest(unittest.IsolatedAsyncioTestCase):

    async def test_shows_all_four_named_styles(self):
        ctx = _FakeCtx(Player())
        await _show_graphics_test(ctx)
        text = ctx._flat()
        for name in ('ASCII', 'Single', 'Double', 'PETSCII'):
            self.assertIn(name, text)

    async def test_nothing_is_stored_on_the_player(self):
        player = Player()
        before = player.client_settings.border_style
        ctx = _FakeCtx(player)
        await _show_graphics_test(ctx)
        self.assertEqual(player.client_settings.border_style, before)

    async def test_each_style_shows_its_own_distinct_glyphs(self):
        ctx = _FakeCtx(Player())
        await _show_graphics_test(ctx)
        text = ctx._flat()
        self.assertIn('┌', text)   # Single/PETSCII top-left
        self.assertIn('╔', text)   # Double top-left
        self.assertIn('+', text)   # ASCII top-left


if __name__ == '__main__':
    unittest.main()
