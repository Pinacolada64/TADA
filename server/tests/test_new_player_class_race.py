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
from commands.new_player import validate_class_race_combo


class _FakePlayer:
    def __init__(self, char_class=None, char_race=None, name='Rulan'):
        self.char_class = char_class
        self.char_race = char_race
        self.name = name


class _FakeCtx:
    def __init__(self, player):
        self.player = player


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


if __name__ == '__main__':
    unittest.main(verbosity=2)
