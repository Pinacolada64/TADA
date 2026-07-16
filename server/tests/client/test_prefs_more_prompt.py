"""tests/test_prefs_more_prompt.py

End-to-end test of the prefs menu's 'M' key (More Prompt), using a real
Player so client_settings/border/codec resolution all work unmodified.

Run with:
    python -m pytest tests/test_prefs_more_prompt.py -v
"""
from __future__ import annotations

import unittest

from flags import PlayerFlags
from player import Player
from commands.prefs import prefs_menu


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


class TestPrefsMorePromptKey(unittest.IsolatedAsyncioTestCase):

    async def test_menu_shows_current_state(self):
        player = Player()
        player.set_flag(PlayerFlags.MORE_PROMPT)
        ctx = _FakeCtx([''], player)
        await prefs_menu(ctx)
        # The "Setting" column may wrap "More Prompt" across two display
        # lines (with table border characters in between), so check for
        # both words rather than the exact phrase.
        flat = ctx._flat()
        self.assertIn('More', flat)
        self.assertIn('Prompt', flat)

    async def test_m_toggles_off_then_menu_reflects_it(self):
        player = Player()
        player.set_flag(PlayerFlags.MORE_PROMPT)
        ctx = _FakeCtx(['m', ''], player)
        ok = await prefs_menu(ctx)
        self.assertTrue(ok)
        self.assertFalse(player.query_flag(PlayerFlags.MORE_PROMPT))
        self.assertIn('More Prompt: |red|Off|reset|', ctx._flat())

    async def test_m_toggles_on_from_off(self):
        player = Player()
        player.clear_flag(PlayerFlags.MORE_PROMPT)
        ctx = _FakeCtx(['m', ''], player)
        await prefs_menu(ctx)
        self.assertTrue(player.query_flag(PlayerFlags.MORE_PROMPT))


class TestPrefsHelpColumn(unittest.IsolatedAsyncioTestCase):
    """The 'Help' column's h<key> entries (e.g. 'hx', 'hm') explain what
    each setting does, then return to the menu without changing anything."""

    async def test_menu_lists_help_column_and_entries(self):
        ctx = _FakeCtx([''], Player())
        await prefs_menu(ctx)
        flat = ctx._flat()
        self.assertIn('Help', flat)
        for entry in ('hx', 'hh', 'hm', 'hb', 'hc'):
            self.assertIn(entry, flat)

    async def test_hx_explains_expert_mode_without_changing_it(self):
        player = Player()
        player.clear_flag(PlayerFlags.EXPERT_MODE)
        ctx = _FakeCtx(['hx', ''], player)
        ok = await prefs_menu(ctx)
        self.assertTrue(ok)
        self.assertIn('Expert Mode', ctx._flat())
        self.assertFalse(player.query_flag(PlayerFlags.EXPERT_MODE))

    async def test_hm_explains_more_prompt_without_changing_it(self):
        player = Player()
        player.set_flag(PlayerFlags.MORE_PROMPT)
        ctx = _FakeCtx(['hm', ''], player)
        await prefs_menu(ctx)
        self.assertIn('More Prompt', ctx._flat())
        self.assertTrue(player.query_flag(PlayerFlags.MORE_PROMPT))

    async def test_hb_explains_border_style(self):
        ctx = _FakeCtx(['hb', ''], Player())
        await prefs_menu(ctx)
        self.assertIn('Border Style', ctx._flat())

    async def test_hc_explains_colors(self):
        ctx = _FakeCtx(['hc', ''], Player())
        await prefs_menu(ctx)
        self.assertIn('Colors', ctx._flat())

    async def test_hh_explains_hourglass(self):
        ctx = _FakeCtx(['hh', ''], Player())
        await prefs_menu(ctx)
        self.assertIn('Hourglass Display', ctx._flat())

    async def test_unknown_help_key_falls_through_to_error_message(self):
        ctx = _FakeCtx(['hq', ''], Player())
        ok = await prefs_menu(ctx)
        self.assertTrue(ok)
        self.assertIn('Choose', ctx._flat())


class TestPrefsMenuFromNewPlayerWording(unittest.IsolatedAsyncioTestCase):
    """Regression test: an alpha tester was worried pressing Return at this
    menu during character creation would quit creation entirely, instead
    of just saving preferences and moving to the next step. The "Enter to
    ..." line's wording now depends on from_new_player."""

    async def test_default_wording_says_save_and_exit(self):
        ctx = _FakeCtx([''], Player())
        await prefs_menu(ctx)
        self.assertIn('save settings and exit', ctx._flat())
        self.assertNotIn('continue creating your character', ctx._flat())

    async def test_from_new_player_wording_says_continue_creating(self):
        ctx = _FakeCtx([''], Player())
        await prefs_menu(ctx, from_new_player=True)
        self.assertIn('continue creating your character', ctx._flat())
        self.assertNotIn('save settings and exit', ctx._flat())


if __name__ == '__main__':
    unittest.main(verbosity=2)
