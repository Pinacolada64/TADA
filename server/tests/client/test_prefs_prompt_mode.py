"""tests/client/test_prefs_prompt_mode.py

Coverage for commands/prefs.py's 'P' (Prompt Mode) row -- toggles the
same PlayerFlags.PROMPT_MODE as the standalone 'pm' command (commands/
prompt_mode.py). Also covers the root-menu mnemonic selectors ('xm',
'mp', 'pm') that let a player type a toggle's real in-game command name
at the prefs prompt instead of its single-letter key.
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


class TestPrefsPromptModeKey(unittest.IsolatedAsyncioTestCase):

    async def test_menu_shows_current_state(self):
        player = Player()
        player.set_flag(PlayerFlags.PROMPT_MODE)
        ctx = _FakeCtx([''], player)
        await prefs_menu(ctx)
        flat = ctx._flat()
        self.assertIn('Prompt', flat)
        self.assertIn('Mode', flat)

    async def test_p_toggles_off_then_menu_reflects_it(self):
        player = Player()
        player.set_flag(PlayerFlags.PROMPT_MODE)
        ctx = _FakeCtx(['p', ''], player)
        ok = await prefs_menu(ctx)
        self.assertTrue(ok)
        self.assertFalse(player.query_flag(PlayerFlags.PROMPT_MODE))
        self.assertIn('Prompt Mode: |red|Off|reset|', ctx._flat())

    async def test_p_toggles_on_from_off(self):
        player = Player()
        player.clear_flag(PlayerFlags.PROMPT_MODE)
        ctx = _FakeCtx(['p', ''], player)
        await prefs_menu(ctx)
        self.assertTrue(player.query_flag(PlayerFlags.PROMPT_MODE))
        self.assertIn('Prompt Mode: |green|On|reset|', ctx._flat())

    async def test_p_marks_unsaved_changes(self):
        player = Player()
        player.unsaved_changes = False
        ctx = _FakeCtx(['p', ''], player)
        await prefs_menu(ctx)
        self.assertTrue(player.unsaved_changes)

    async def test_hp_explains_prompt_mode_without_changing_it(self):
        player = Player()
        player.clear_flag(PlayerFlags.PROMPT_MODE)
        ctx = _FakeCtx(['hp', ''], player)
        await prefs_menu(ctx)
        self.assertIn('Prompt Mode', ctx._flat())
        self.assertFalse(player.query_flag(PlayerFlags.PROMPT_MODE))


class TestPrefsRootMnemonics(unittest.IsolatedAsyncioTestCase):
    """'xm'/'mp'/'pm' select the same row as their single-letter key."""

    async def test_pm_toggles_prompt_mode_same_as_p(self):
        player = Player()
        player.clear_flag(PlayerFlags.PROMPT_MODE)
        ctx = _FakeCtx(['pm', ''], player)
        await prefs_menu(ctx)
        self.assertTrue(player.query_flag(PlayerFlags.PROMPT_MODE))

    async def test_mp_toggles_more_prompt_same_as_m(self):
        player = Player()
        player.clear_flag(PlayerFlags.MORE_PROMPT)
        ctx = _FakeCtx(['mp', ''], player)
        await prefs_menu(ctx)
        self.assertTrue(player.query_flag(PlayerFlags.MORE_PROMPT))

    async def test_xm_toggles_expert_mode_same_as_x(self):
        player = Player()
        player.clear_flag(PlayerFlags.EXPERT_MODE)
        ctx = _FakeCtx(['xm', ''], player)
        await prefs_menu(ctx)
        self.assertTrue(player.query_flag(PlayerFlags.EXPERT_MODE))

    async def test_mnemonic_does_not_shadow_help_lookup(self):
        # 'hp'/'hm'/'hx' must still resolve as help lookups, not get
        # caught by the mnemonic table (none of them are mnemonic keys).
        player = Player()
        ctx = _FakeCtx(['hp', ''], player)
        await prefs_menu(ctx)
        self.assertIn('Prompt Mode', ctx._flat())
        self.assertFalse(player.query_flag(PlayerFlags.PROMPT_MODE))


class TestPrefsQuestionMarkOverview(unittest.IsolatedAsyncioTestCase):
    """'?' now renders via commands.help.format_summary_table -- cyan
    keys, zebra-striped (dark_gray/mid_gray) descriptions -- same look
    as 'help #summary'."""

    async def test_shows_cyan_keys_and_zebra_striped_descriptions(self):
        ctx = _FakeCtx(['?', ''], Player())
        await prefs_menu(ctx)
        flat = ctx._flat()
        self.assertIn('|cyan|X|reset|', flat)
        self.assertIn('|cyan|P|reset|', flat)
        self.assertIn('|mid_gray|', flat)
        self.assertIn('|dark_gray|', flat)

    async def test_every_root_key_appears(self):
        ctx = _FakeCtx(['?', ''], Player())
        await prefs_menu(ctx)
        flat = ctx._flat()
        for key in ('X', 'M', 'P', 'C', 'N', 'T', 'D', 'W'):
            self.assertIn(f'|cyan|{key}|reset|', flat)

    async def test_h_key_hint_and_return_key_line_still_present(self):
        ctx = _FakeCtx(['?', ''], Player())
        await prefs_menu(ctx)
        flat = ctx._flat()
        self.assertIn('h<key>', flat)
        self.assertIn('save and exit', flat)


if __name__ == '__main__':
    unittest.main()
