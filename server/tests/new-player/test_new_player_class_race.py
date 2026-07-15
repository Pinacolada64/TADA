"""tests/test_new_player_class_race.py

Unit tests for commands/new_player.py's validate_class_race_combo(), which
now delegates to characters.is_class_race_compatible() (see
tests/test_characters.py for the underlying table) instead of keeping its
own duplicated copy. This file only covers the thin wrapper: that it
returns the right (ok, message) shape and the Verus-flavored quip text.

Run with:
    python -m pytest tests/test_new_player_class_race.py -v
"""
from __future__ import annotations

import unittest

from base_classes import PlayerClass, PlayerRace
from commands.new_player import validate_class_race_combo, _choose_race


class _FakePlayer:
    def __init__(self, char_class=None, char_race=None, name='Rulan'):
        self.char_class = char_class
        self.char_race = char_race
        self.name = name


class _FakeCtx:
    def __init__(self, player, responses=None):
        self.player = player
        self._q = list(responses or [])
        self.sent: list = []

    async def send(self, *args):
        for a in args:
            self.sent.append(a)

    async def prompt(self, prompt_text: str = '', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        out = []
        for item in self.sent:
            if isinstance(item, (list, tuple)):
                out.extend(str(x) for x in item)
            else:
                out.append(str(item))
        return '\n'.join(out)


class TestValidateClassRaceCombo(unittest.TestCase):

    def test_compatible_combo_returns_ok(self):
        ctx = _FakeCtx(_FakePlayer(PlayerClass.FIGHTER, PlayerRace.HUMAN))
        ok, msg = validate_class_race_combo(ctx)
        self.assertTrue(ok)
        self.assertIsNone(msg)

    def test_incompatible_combo_returns_verus_message(self):
        ctx = _FakeCtx(_FakePlayer(PlayerClass.WIZARD, PlayerRace.OGRE))
        ok, msg = validate_class_race_combo(ctx)
        self.assertFalse(ok)
        self.assertIn('Verus remarks', msg)
        self.assertIn('Ogre', msg)
        self.assertIn('Wizard', msg)

    def test_class_not_yet_set_is_ok(self):
        ctx = _FakeCtx(_FakePlayer(None, PlayerRace.OGRE))
        ok, msg = validate_class_race_combo(ctx)
        self.assertTrue(ok)

    def test_race_not_yet_set_is_ok(self):
        ctx = _FakeCtx(_FakePlayer(PlayerClass.WIZARD, None))
        ok, msg = validate_class_race_combo(ctx)
        self.assertTrue(ok)


class TestChooseRaceDisplay(unittest.IsolatedAsyncioTestCase):
    """Regression test: the race menu showed PlayerRace's .name (ALL CAPS,
    e.g. 'HALF_ELF') instead of its .value ('Half-Elf') -- every other
    menu in character creation (class, guild) already used Title Case
    display strings, so this stood out as a visual bug an alpha tester
    reported after seeing the new-character-creation transcript."""

    async def test_race_menu_shows_title_case_value_not_enum_name(self):
        ctx = _FakeCtx(_FakePlayer(char_class=PlayerClass.FIGHTER), responses=['1'])
        await _choose_race(ctx)
        text = ctx._flat()
        self.assertIn('Human', text)
        self.assertNotIn('HUMAN', text)

    async def test_race_menu_shows_hyphenated_half_elf_not_enum_name(self):
        ctx = _FakeCtx(_FakePlayer(char_class=PlayerClass.FIGHTER), responses=['9'])
        await _choose_race(ctx)
        text = ctx._flat()
        self.assertIn('Half-Elf', text)
        self.assertNotIn('HALF_ELF', text)

    async def test_selection_still_stores_real_enum_member(self):
        player = _FakePlayer(char_class=PlayerClass.FIGHTER)
        ctx = _FakeCtx(player, responses=['1'])
        await _choose_race(ctx)
        self.assertIs(player.char_race, PlayerRace.HUMAN)


if __name__ == '__main__':
    unittest.main(verbosity=2)
