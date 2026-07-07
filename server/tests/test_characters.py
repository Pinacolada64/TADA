"""tests/test_characters.py

Unit tests for characters.py's class/race compatibility check.

is_class_race_compatible() used to be a private, duplicated table inside
commands/new_player.py's validate_class_race_combo() -- moved here so
EditPlayer's class/race editors can use the exact same rule (see
tests/test_editplayer_new_features.py) instead of maintaining a second copy.

Run with:
    python -m pytest tests/test_characters.py -v
"""
from __future__ import annotations

import unittest

from base_classes import PlayerClass, PlayerRace
from characters import is_class_race_compatible


class TestIsClassRaceCompatible(unittest.TestCase):

    def test_none_class_is_always_compatible(self):
        self.assertTrue(is_class_race_compatible(None, PlayerRace.OGRE))

    def test_none_race_is_always_compatible(self):
        self.assertTrue(is_class_race_compatible(PlayerClass.WIZARD, None))

    def test_both_none_is_compatible(self):
        self.assertTrue(is_class_race_compatible(None, None))

    def test_wizard_ogre_incompatible(self):
        self.assertFalse(is_class_race_compatible(PlayerClass.WIZARD, PlayerRace.OGRE))

    def test_wizard_dwarf_incompatible(self):
        self.assertFalse(is_class_race_compatible(PlayerClass.WIZARD, PlayerRace.DWARF))

    def test_wizard_orc_incompatible(self):
        self.assertFalse(is_class_race_compatible(PlayerClass.WIZARD, PlayerRace.ORC))

    def test_wizard_elf_compatible(self):
        self.assertTrue(is_class_race_compatible(PlayerClass.WIZARD, PlayerRace.ELF))

    def test_druid_ogre_incompatible(self):
        self.assertFalse(is_class_race_compatible(PlayerClass.DRUID, PlayerRace.OGRE))

    def test_druid_orc_incompatible(self):
        self.assertFalse(is_class_race_compatible(PlayerClass.DRUID, PlayerRace.ORC))

    def test_thief_elf_incompatible(self):
        self.assertFalse(is_class_race_compatible(PlayerClass.THIEF, PlayerRace.ELF))

    def test_thief_human_compatible(self):
        self.assertTrue(is_class_race_compatible(PlayerClass.THIEF, PlayerRace.HUMAN))

    def test_archer_ogre_incompatible(self):
        self.assertFalse(is_class_race_compatible(PlayerClass.ARCHER, PlayerRace.OGRE))

    def test_archer_gnome_incompatible(self):
        self.assertFalse(is_class_race_compatible(PlayerClass.ARCHER, PlayerRace.GNOME))

    def test_archer_hobbit_incompatible(self):
        self.assertFalse(is_class_race_compatible(PlayerClass.ARCHER, PlayerRace.HOBBIT))

    def test_assassin_gnome_incompatible(self):
        self.assertFalse(is_class_race_compatible(PlayerClass.ASSASSIN, PlayerRace.GNOME))

    def test_assassin_elf_incompatible(self):
        self.assertFalse(is_class_race_compatible(PlayerClass.ASSASSIN, PlayerRace.ELF))

    def test_assassin_hobbit_incompatible(self):
        self.assertFalse(is_class_race_compatible(PlayerClass.ASSASSIN, PlayerRace.HOBBIT))

    def test_knight_ogre_incompatible(self):
        self.assertFalse(is_class_race_compatible(PlayerClass.KNIGHT, PlayerRace.OGRE))

    def test_knight_orc_incompatible(self):
        self.assertFalse(is_class_race_compatible(PlayerClass.KNIGHT, PlayerRace.ORC))

    def test_knight_human_compatible(self):
        self.assertTrue(is_class_race_compatible(PlayerClass.KNIGHT, PlayerRace.HUMAN))

    def test_class_with_no_restrictions_always_compatible(self):
        # FIGHTER has no entry in the bad-combo table at all.
        for race in PlayerRace:
            self.assertTrue(is_class_race_compatible(PlayerClass.FIGHTER, race))


if __name__ == '__main__':
    unittest.main(verbosity=2)
