"""tests/test_prefs_client_type.py

Ryan: fold character creation's standalone "Client Type" step into
PREFS, reachable any time (not just once during creation), and add a
real custom screen-size option plus the previously-unwired Tab Key and
Line Ending settings from terminal.py.

Uses a real Player so client_settings/border/codec resolution all work
unmodified, matching tests/test_prefs_more_prompt.py's pattern.

Run with:
    python -m pytest tests/test_prefs_client_type.py -v
"""
from __future__ import annotations

import unittest

from player import Player
from terminal import Translation
from commands.prefs import (
    _MAX_COLS, _MAX_ROWS, _MIN_COLS, _MIN_ROWS,
    _pick_client_type, _pick_line_ending, _pick_tab_settings, prefs_menu,
)


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


class TestClientTypeStepRemoved(unittest.TestCase):

    def test_choose_client_settings_no_longer_exists(self):
        import commands.new_player as np
        self.assertFalse(hasattr(np, '_choose_client_settings'))

    def test_eleven_creation_steps_not_twelve(self):
        """12 steps (with a standalone Client Type step) -> 11 now that
        it's folded into Preferences."""
        import re
        import inspect
        import commands.new_player as np
        src = inspect.getsource(np.main_flow)
        steps_block = src[src.index('steps = ['):src.index(']', src.index('steps = ['))]
        step_titles = re.findall(r'"\s*([A-Za-z ]+)"\s*\)', steps_block)
        self.assertEqual(len(step_titles), 11)
        self.assertNotIn('Client Type', step_titles)


class TestPrefsMenuShowsNewRows(unittest.IsolatedAsyncioTestCase):

    async def test_client_type_row_shown_for_ansi(self):
        ctx = _FakeCtx([''], Player())
        await prefs_menu(ctx)
        text = ctx._flat()
        self.assertIn('Client', text)
        self.assertIn('Type', text)

    async def test_tab_key_row_shown(self):
        ctx = _FakeCtx([''], Player())
        await prefs_menu(ctx)
        self.assertIn('Tab Key', ctx._flat())

    async def test_line_ending_row_shown(self):
        ctx = _FakeCtx([''], Player())
        await prefs_menu(ctx)
        text = ctx._flat()
        self.assertIn('Line', text)
        self.assertIn('Ending', text)

    async def test_ht_hk_hl_help_available(self):
        ctx = _FakeCtx(['ht', 'hk', 'hl', ''], Player())
        await prefs_menu(ctx)
        text = ctx._flat()
        self.assertIn('Client Type', text)
        self.assertIn('Tab Key', text)
        self.assertIn('Line Ending', text)

    async def test_border_style_hidden_immediately_after_switching_to_petscii(self):
        """Live bug found testing this: codec/is_petscii used to be
        computed once before the menu loop started, so switching Client
        Type mid-session (e.g. to a Commodore preset) didn't hide the
        ANSI-only Border Style row until PREFS was reopened fresh."""
        ctx = _FakeCtx(['t', '1', ''], Player())   # Client Type -> Commodore 64 (PETSCII)
        await prefs_menu(ctx)
        # The LAST occurrence of the settings table in the transcript
        # (the redraw right before exiting) must already omit Border
        # Style -- it's PETSCII now, not still showing the stale ANSI
        # table style captured when the loop started.
        text = ctx._flat()
        last_menu_start = text.rindex('User Preferences')
        self.assertNotIn('Border', text[last_menu_start:])


class TestPickClientType(unittest.IsolatedAsyncioTestCase):

    async def test_preset_sets_screen_size_and_translation(self):
        ctx = _FakeCtx(['4'], Player())
        await _pick_client_type(ctx)
        cs = ctx.player.client_settings
        self.assertEqual((cs.screen_columns, cs.screen_rows), (80, 25))
        self.assertEqual(cs.translation, Translation.ANSI)

    async def test_commodore_preset_sets_petscii(self):
        ctx = _FakeCtx(['1'], Player())
        await _pick_client_type(ctx)
        cs = ctx.player.client_settings
        self.assertEqual((cs.screen_columns, cs.screen_rows), (40, 25))
        self.assertEqual(cs.translation, Translation.PETSCII)

    async def test_commodore_preset_produces_real_petscii_codec(self):
        """Regression test for a real bug found live: the old
        character-creation Client Type step this was folded in from
        stored the bare string 'PETSCII' instead of the Translation
        enum member, so formatting.codec_for_settings() -- which
        compares `t == Translation.PETSCII` -- silently fell through to
        PlainCodec for every player who picked a Commodore preset there."""
        from formatting import codec_for_settings, PETSCIICodec
        ctx = _FakeCtx(['1'], Player())
        await _pick_client_type(ctx)
        codec = codec_for_settings(ctx.player.client_settings)
        self.assertIsInstance(codec, PETSCIICodec)

    async def test_custom_size_within_range_accepted(self):
        ctx = _FakeCtx(['5', '100', '40', 'A'], Player())
        await _pick_client_type(ctx)
        cs = ctx.player.client_settings
        self.assertEqual((cs.screen_columns, cs.screen_rows), (100, 40))
        self.assertEqual(cs.translation, Translation.ANSI)

    async def test_custom_size_plain_text_option(self):
        ctx = _FakeCtx(['5', '100', '40', 'P'], Player())
        await _pick_client_type(ctx)
        self.assertEqual(ctx.player.client_settings.translation, Translation.ASCII)

    async def test_custom_columns_below_minimum_rejected(self):
        ctx = _FakeCtx(['5', str(_MIN_COLS - 1)], Player())
        original = (ctx.player.client_settings.screen_columns,
                    ctx.player.client_settings.screen_rows)
        await _pick_client_type(ctx)
        cs = ctx.player.client_settings
        self.assertEqual((cs.screen_columns, cs.screen_rows), original)

    async def test_custom_columns_above_maximum_rejected(self):
        ctx = _FakeCtx(['5', str(_MAX_COLS + 1)], Player())
        original = (ctx.player.client_settings.screen_columns,
                    ctx.player.client_settings.screen_rows)
        await _pick_client_type(ctx)
        cs = ctx.player.client_settings
        self.assertEqual((cs.screen_columns, cs.screen_rows), original)

    async def test_custom_rows_out_of_range_rejected(self):
        ctx = _FakeCtx(['5', '100', str(_MAX_ROWS + 1)], Player())
        original = (ctx.player.client_settings.screen_columns,
                    ctx.player.client_settings.screen_rows)
        await _pick_client_type(ctx)
        cs = ctx.player.client_settings
        self.assertEqual((cs.screen_columns, cs.screen_rows), original)

    async def test_invalid_selection_leaves_unchanged(self):
        ctx = _FakeCtx(['99'], Player())
        original = (ctx.player.client_settings.screen_columns,
                    ctx.player.client_settings.screen_rows)
        await _pick_client_type(ctx)
        cs = ctx.player.client_settings
        self.assertEqual((cs.screen_columns, cs.screen_rows), original)

    async def test_blank_leaves_unchanged(self):
        ctx = _FakeCtx([''], Player())
        original = (ctx.player.client_settings.screen_columns,
                    ctx.player.client_settings.screen_rows)
        await _pick_client_type(ctx)
        cs = ctx.player.client_settings
        self.assertEqual((cs.screen_columns, cs.screen_rows), original)


class TestPickTabSettings(unittest.IsolatedAsyncioTestCase):

    async def test_yes_sets_has_tab_key(self):
        ctx = _FakeCtx(['y'], Player())
        await _pick_tab_settings(ctx)
        self.assertTrue(ctx.player.client_settings.tab_settings.has_tab_key)

    async def test_no_then_width_sets_simulated_tab(self):
        ctx = _FakeCtx(['n', '4'], Player())
        await _pick_tab_settings(ctx)
        tab = ctx.player.client_settings.tab_settings
        self.assertFalse(tab.has_tab_key)
        self.assertEqual(tab.tab_width, 4)
        self.assertEqual(tab.tab_output, '    ')

    async def test_width_out_of_range_unchanged(self):
        ctx = _FakeCtx(['n', '999'], Player())
        await _pick_tab_settings(ctx)
        tab = ctx.player.client_settings.tab_settings
        self.assertNotEqual(tab.tab_width, 999)

    async def test_blank_leaves_unchanged(self):
        ctx = _FakeCtx([''], Player())
        player = ctx.player
        original = player.client_settings.tab_settings.has_tab_key
        await _pick_tab_settings(ctx)
        self.assertEqual(player.client_settings.tab_settings.has_tab_key, original)


class TestPickLineEnding(unittest.IsolatedAsyncioTestCase):

    async def test_select_lf(self):
        from terminal import LineEnding
        ctx = _FakeCtx(['1'], Player())
        await _pick_line_ending(ctx)
        self.assertEqual(ctx.player.client_settings.line_ending, LineEnding.LF)

    async def test_select_cr_by_name(self):
        from terminal import LineEnding
        ctx = _FakeCtx(['CR'], Player())
        await _pick_line_ending(ctx)
        self.assertEqual(ctx.player.client_settings.line_ending, LineEnding.CR)

    async def test_select_crlf_by_number(self):
        from terminal import LineEnding
        ctx = _FakeCtx(['3'], Player())
        await _pick_line_ending(ctx)
        self.assertEqual(ctx.player.client_settings.line_ending, LineEnding.CRLF)

    async def test_blank_leaves_unchanged(self):
        from terminal import LineEnding
        ctx = _FakeCtx([''], Player())
        await _pick_line_ending(ctx)
        self.assertEqual(ctx.player.client_settings.line_ending, LineEnding.LF)


if __name__ == '__main__':
    unittest.main(verbosity=2)
