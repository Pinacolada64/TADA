"""tests/test_tada_utilities_frame_text.py

Unit tests for tada_utilities.py's frame_text()/tip() -- specifically
the bracket-highlighting bug Ryan found: [bracketed text] loses its
literal '[' ']' characters when highlight_brackets() runs (replaced by
the codec's invisible highlight_on()/off() markers), so a box line
containing brackets that was padded *before* highlighting ends up 2
visible columns short of the border width once ctx.send()'s own
format_lines()->highlight_brackets() pass runs on it downstream.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from terminal import Translation
from formatting import format_lines, _visible_len
import tada_utilities as tu


def _ctx(screen_columns=42, translation=Translation.ANSI):
    ctx = MagicMock()
    ctx.player.client_settings.screen_columns = screen_columns
    ctx.player.client_settings.translation = translation
    return ctx


class TestFrameTextBracketAlignment(unittest.TestCase):
    def test_border_lines_match_body_width_with_brackets(self):
        ctx = _ctx()
        lines = tu.frame_text(ctx, 'Once [DIG] exists, Olly can help.', title='Note:')
        widths = {_visible_len(l) for l in lines}
        self.assertEqual(len(widths), 1, f'border/body width mismatch: {lines}')

    def test_border_lines_stay_aligned_through_the_full_send_pipeline(self):
        # frame_text()'s own raw output can look self-consistent (it pads
        # against whatever it wrapped, brackets and all) -- the real bug
        # only shows up once ctx.send()'s own format_lines() ->
        # highlight_brackets() pass runs on the already-built box lines,
        # which is what actually happens for a real player.
        ctx = _ctx()
        lines = tu.frame_text(ctx, 'Once [DIG] exists, Olly can help.', title='Note:')
        formatted = format_lines(lines, ctx.player.client_settings, None)
        widths = {_visible_len(l) for l in formatted}
        self.assertEqual(len(widths), 1, f'visible width mismatch after send pipeline: {formatted}')
        self.assertEqual(widths.pop(), ctx.player.client_settings.screen_columns)

    def test_multiple_bracket_pairs_still_align(self):
        ctx = _ctx()
        lines = tu.frame_text(
            ctx, 'Use [ATTACK] then [FLEE] if it goes badly.', title='Combat')
        formatted = format_lines(lines, ctx.player.client_settings, None)
        widths = {_visible_len(l) for l in formatted}
        self.assertEqual(len(widths), 1, f'visible width mismatch: {formatted}')

    def test_no_brackets_still_aligns(self):
        ctx = _ctx()
        lines = tu.frame_text(ctx, 'A plain sentence with no brackets at all.', title='Plain')
        formatted = format_lines(lines, ctx.player.client_settings, None)
        widths = {_visible_len(l) for l in formatted}
        self.assertEqual(len(widths), 1, f'visible width mismatch: {formatted}')

    def test_tip_is_empty_for_expert_players(self):
        ctx = _ctx()
        ctx.player.is_expert = True
        self.assertEqual(tu.tip(ctx, 'Note:', 'Once [DIG] exists...'), [])

    def test_tip_returns_frame_text_for_non_expert(self):
        ctx = _ctx()
        ctx.player.is_expert = False
        result = tu.tip(ctx, 'Note:', 'Once [DIG] exists...')
        self.assertTrue(result)
        widths = {_visible_len(l) for l in result}
        self.assertEqual(len(widths), 1)


if __name__ == '__main__':
    unittest.main()
