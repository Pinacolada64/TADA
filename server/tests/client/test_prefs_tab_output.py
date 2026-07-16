"""tests/client/test_prefs_tab_output.py

Covers two related additions:
  1. formatting.py's generalized |entity:count| token syntax (extends the
     existing |entity| bracket-token pipeline with an optional ':N' repeat
     count), and the new 'tab' entity built on top of it -- |tab| / |tab:N|
     expand to the player's own client_settings.tab_settings.tab_output
     (a real '\\t' or N simulated spaces, per PREFS 'K'), repeated N times.
  2. PREFS 'K' (Tab Key) now shows a "Tab test:" preview line using |tab|
     so a player can see what their current setting actually looks like,
     both before and after changing it.
"""
from __future__ import annotations

import unittest

from player import Player
from commands.prefs import _pick_tab_settings, _tab_test_line
from formatting import (
    ansi_encode, petscii_encode, plain_encode, format_lines,
    _expand_tab_tokens,
)
from terminal import ClientSettings, TabSettings


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
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


def _settings(has_tab_key: bool = True, tab_width: int = 8) -> ClientSettings:
    cs = ClientSettings()
    cs.tab_settings = TabSettings()
    cs.tab_settings.has_tab_key = has_tab_key
    if has_tab_key:
        cs.tab_settings.tab_output = '\t'
    else:
        cs.tab_settings.tab_width  = tab_width
        cs.tab_settings.tab_output = ' ' * tab_width
    return cs


class TestExpandTabTokens(unittest.TestCase):

    def test_single_tab_expands_to_tab_output(self):
        cs = _settings(has_tab_key=False, tab_width=4)
        self.assertEqual(_expand_tab_tokens('A|tab|B', cs), 'A    B')

    def test_tab_with_count_repeats_tab_output(self):
        cs = _settings(has_tab_key=False, tab_width=4)
        self.assertEqual(_expand_tab_tokens('A|tab:3|B', cs), 'A            B')

    def test_real_tab_key_expands_to_literal_tab_char(self):
        cs = _settings(has_tab_key=True)
        self.assertEqual(_expand_tab_tokens('A|tab|B', cs), 'A\tB')

    def test_no_tab_settings_falls_back_to_literal_tab_char(self):
        class _Bare:
            pass
        self.assertEqual(_expand_tab_tokens('A|tab|B', _Bare()), 'A\tB')

    def test_format_lines_expands_tab_before_wrapping(self):
        cs = _settings(has_tab_key=False, tab_width=4)
        lines = format_lines(['A|tab|B|tab:2|C'], cs)
        self.assertEqual(lines, ['A    B        C'])


class TestTokenCountSyntax(unittest.TestCase):
    """|entity:count| generalized to the existing color-token pipelines too,
    even though repeating a color escape code is a visual no-op -- exercises
    the same regex/count-handling path 'tab' relies on."""

    def test_ansi_encode_repeats_code_for_count(self):
        once  = ansi_encode('|red|x')
        twice = ansi_encode('|red:2|x')
        # The color code itself appears twice in the twice-repeated output.
        from formatting import ANSI_COLOR_CODES
        code = ANSI_COLOR_CODES['red']
        self.assertEqual(twice, code * 2 + 'x')
        self.assertEqual(once, code + 'x')

    def test_petscii_encode_repeats_control_byte_for_count(self):
        from formatting import PETSCII_CONTROL_CODES
        code = PETSCII_CONTROL_CODES['red']
        result = petscii_encode('|red:3|')
        self.assertEqual(result, bytes([code]) * 3)

    def test_plain_encode_strips_tokens_with_count(self):
        self.assertEqual(plain_encode('A|red:5|B'), 'AB')

    def test_unknown_token_with_count_left_intact_by_ansi(self):
        result = ansi_encode('|bogus:5|x')
        self.assertEqual(result, '|bogus:5|x')


class TestPrefsTabTestLine(unittest.IsolatedAsyncioTestCase):

    def test_tab_test_line_uses_tab_token(self):
        self.assertIn('|tab|', _tab_test_line())

    async def test_shown_before_prompting(self):
        ctx = _FakeCtx([''], Player())
        await _pick_tab_settings(ctx)
        self.assertIn(_tab_test_line(), ctx._flat())

    async def test_shown_again_after_enabling_real_tab_key(self):
        ctx = _FakeCtx(['y'], Player())
        await _pick_tab_settings(ctx)
        self.assertEqual(ctx._flat().count(_tab_test_line()), 2)

    async def test_shown_again_after_setting_tab_width(self):
        ctx = _FakeCtx(['n', '4'], Player())
        await _pick_tab_settings(ctx)
        self.assertEqual(ctx._flat().count(_tab_test_line()), 2)
        self.assertEqual(ctx.player.client_settings.tab_settings.tab_output, '    ')


if __name__ == '__main__':
    unittest.main(verbosity=2)
