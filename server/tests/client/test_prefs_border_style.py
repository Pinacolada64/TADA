"""tests/test_prefs_border_style.py

Regression test for a real bug Ryan found live: commands/prefs.py's
_pick_border_style() unpacked its options list as (num, key) where num
was actually a *list* (['1', 'a']) -- so the menu displayed the Python
repr of that list instead of just "1", and `ans == num` (comparing a
typed string to a list) could never match. Even a coincidental match
via the fallback `ans.lower() in key` branch stored the wrong-cased
value (key was 'ASCII'/'Single'/'Double', capitalized) into
client_settings.border_style, which every other lookup of that setting
(formatting.make_box()'s own border_style comparisons, _HRULE_CHAR)
expects lowercase -- so even a "successful" pick silently did nothing,
and every style preview rendered identically since make_box() never
recognized the capitalized border_style value passed to it either.

Run with:
    python -m pytest tests/test_prefs_border_style.py -v
"""
from __future__ import annotations

import unittest

from player import Player
from commands.prefs import _pick_border_style


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


def _codec():
    from formatting import ANSICodec
    return ANSICodec()


class TestPickBorderStyleMenuDisplay(unittest.IsolatedAsyncioTestCase):

    async def test_menu_shows_plain_numbers_not_list_repr(self):
        ctx = _FakeCtx([''], Player())
        await _pick_border_style(ctx, _codec())
        text = ctx._flat()
        self.assertIn('1. ASCII', text)
        self.assertIn('2. Single', text)
        self.assertIn('3. Double', text)
        self.assertNotIn("['1'", text)
        self.assertNotIn('[\'2\'', text)

    async def test_previews_are_visibly_different_per_style(self):
        """Each style's preview box top-border must actually differ --
        before the fix, every preview fell through to the same style
        since make_box() never recognized the capitalized value passed in."""
        ctx = _FakeCtx([''], Player())
        await _pick_border_style(ctx, _codec())
        text = ctx._flat()
        # ASCII uses '+', single/double use distinct Unicode box chars.
        self.assertIn('+', text)
        self.assertIn('┌', text)   # single
        self.assertIn('╔', text)   # double


class TestPickBorderStyleSelection(unittest.IsolatedAsyncioTestCase):

    async def test_number_selects_ascii(self):
        ctx = _FakeCtx(['1'], Player())
        await _pick_border_style(ctx, _codec())
        self.assertEqual(ctx.player.client_settings.border_style, 'ascii')

    async def test_number_selects_single(self):
        ctx = _FakeCtx(['2'], Player())
        await _pick_border_style(ctx, _codec())
        self.assertEqual(ctx.player.client_settings.border_style, 'single')

    async def test_number_selects_double(self):
        ctx = _FakeCtx(['3'], Player())
        await _pick_border_style(ctx, _codec())
        self.assertEqual(ctx.player.client_settings.border_style, 'double')

    async def test_shortcut_letter_selects_style(self):
        ctx = _FakeCtx(['d'], Player())
        await _pick_border_style(ctx, _codec())
        self.assertEqual(ctx.player.client_settings.border_style, 'double')

    async def test_full_name_case_insensitive_selects_style(self):
        ctx = _FakeCtx(['Double'], Player())
        await _pick_border_style(ctx, _codec())
        self.assertEqual(ctx.player.client_settings.border_style, 'double')

    async def test_stored_value_is_lowercase(self):
        """The stored value must be the lowercase form every other
        lookup of border_style expects (formatting._HRULE_CHAR,
        make_box()'s own comparisons) -- not the capitalized display name."""
        ctx = _FakeCtx(['2'], Player())
        await _pick_border_style(ctx, _codec())
        stored = ctx.player.client_settings.border_style
        self.assertEqual(stored, stored.lower())

    async def test_stored_value_is_recognized_by_hrule_char(self):
        from formatting import hrule_char
        ctx = _FakeCtx(['3'], Player())
        await _pick_border_style(ctx, _codec())

        class _FakeSettingsCtx:
            player = ctx.player
        self.assertNotEqual(hrule_char(_FakeSettingsCtx()), '-')

    async def test_blank_leaves_unchanged(self):
        ctx = _FakeCtx([''], Player())
        original = ctx.player.client_settings.border_style
        await _pick_border_style(ctx, _codec())
        self.assertEqual(ctx.player.client_settings.border_style, original)

    async def test_confirmation_message_uses_display_name(self):
        ctx = _FakeCtx(['1'], Player())
        await _pick_border_style(ctx, _codec())
        self.assertIn('Border style set to ASCII.', ctx._flat())


if __name__ == '__main__':
    unittest.main(verbosity=2)
