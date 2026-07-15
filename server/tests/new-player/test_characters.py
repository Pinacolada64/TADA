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

from base_classes import Alignment, PlayerClass, PlayerRace
from characters import (
    apply_natural_alignment,
    is_class_race_compatible,
    natural_alignment_for_race,
)


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


class _FakePlayer:
    def __init__(self, char_race=None, natural_alignment=None):
        self.char_race = char_race
        self.natural_alignment = natural_alignment
        self.unsaved_changes = False


class TestNaturalAlignmentForRace(unittest.TestCase):
    """SPUR.MISC5.S:196-199 -- alignment depends only on race, never class."""

    def test_ogre_is_evil(self):
        self.assertEqual(natural_alignment_for_race(PlayerRace.OGRE), Alignment.EVIL)

    def test_orc_is_evil(self):
        self.assertEqual(natural_alignment_for_race(PlayerRace.ORC), Alignment.EVIL)

    def test_pixie_is_good(self):
        self.assertEqual(natural_alignment_for_race(PlayerRace.PIXIE), Alignment.GOOD)

    def test_elf_is_good(self):
        self.assertEqual(natural_alignment_for_race(PlayerRace.ELF), Alignment.GOOD)

    def test_human_is_neutral(self):
        self.assertEqual(natural_alignment_for_race(PlayerRace.HUMAN), Alignment.NEUTRAL)

    def test_unset_race_is_neutral(self):
        self.assertEqual(natural_alignment_for_race(None), Alignment.NEUTRAL)


class TestApplyNaturalAlignment(unittest.TestCase):

    def test_sets_alignment_and_reports_changed(self):
        player = _FakePlayer(char_race=PlayerRace.OGRE)
        changed, alignment = apply_natural_alignment(player)
        self.assertTrue(changed)
        self.assertEqual(alignment, Alignment.EVIL)
        self.assertEqual(player.natural_alignment, Alignment.EVIL)

    def test_no_change_reports_unchanged(self):
        player = _FakePlayer(char_race=PlayerRace.OGRE, natural_alignment=Alignment.EVIL)
        changed, alignment = apply_natural_alignment(player)
        self.assertFalse(changed)
        self.assertEqual(alignment, Alignment.EVIL)

    def test_switching_race_updates_alignment(self):
        player = _FakePlayer(char_race=PlayerRace.OGRE, natural_alignment=Alignment.EVIL)
        player.char_race = PlayerRace.ELF
        changed, alignment = apply_natural_alignment(player)
        self.assertTrue(changed)
        self.assertEqual(alignment, Alignment.GOOD)
        self.assertEqual(player.natural_alignment, Alignment.GOOD)

    def test_class_change_alone_is_a_no_op(self):
        # apply_natural_alignment only looks at char_race, so calling it
        # after a class-only edit (nothing about char_race changed) reports
        # unchanged rather than flipping anything.
        player = _FakePlayer(char_race=PlayerRace.HUMAN, natural_alignment=Alignment.NEUTRAL)
        changed, alignment = apply_natural_alignment(player)
        self.assertFalse(changed)
        self.assertEqual(alignment, Alignment.NEUTRAL)


if __name__ == '__main__':
    unittest.main(verbosity=2)
