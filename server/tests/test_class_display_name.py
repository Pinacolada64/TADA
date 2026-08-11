"""tests/test_class_display_name.py

Wires up base_classes.py's long-standing PlayerClass.WIZARD TODO: a female
Wizard displays as "Witch" everywhere the class name is shown to players,
while every mechanical check keeps comparing against PlayerClass.WIZARD
(a StrEnum member can't vary its value per player, so the gendered swap
has to live in a display helper instead -- see tada_utilities.py).
"""
import unittest

from base_classes import Gender, PlayerClass
from tada_utilities import class_display_name, player_class_display_name


class TestClassDisplayName(unittest.TestCase):

    def test_female_wizard_displays_as_witch(self):
        self.assertEqual(class_display_name(PlayerClass.WIZARD, Gender.FEMALE), 'Witch')

    def test_male_wizard_displays_as_wizard(self):
        self.assertEqual(class_display_name(PlayerClass.WIZARD, Gender.MALE), 'Wizard')

    def test_unspecified_gender_defaults_to_wizard(self):
        self.assertEqual(class_display_name(PlayerClass.WIZARD, None), 'Wizard')

    def test_non_wizard_classes_unaffected_by_gender(self):
        self.assertEqual(class_display_name(PlayerClass.FIGHTER, Gender.FEMALE), 'Fighter')
        self.assertEqual(class_display_name(PlayerClass.DRUID, Gender.FEMALE), 'Druid')

    def test_none_class_returns_none(self):
        self.assertIsNone(class_display_name(None, Gender.FEMALE))

    def test_works_with_plain_string_class_value(self):
        # bar/zelda.py's _study_player() reads char_class back from a JSON
        # dict, which may already be a bare string rather than the enum --
        # PlayerClass is a StrEnum, so string/enum equality still holds.
        self.assertEqual(class_display_name('Wizard', Gender.FEMALE), 'Witch')


class TestPlayerClassDisplayName(unittest.TestCase):

    def test_reads_char_class_and_gender_off_object(self):
        class FakePlayer:
            char_class = PlayerClass.WIZARD
            gender = Gender.FEMALE
        self.assertEqual(player_class_display_name(FakePlayer()), 'Witch')

    def test_missing_attributes_return_none(self):
        class Empty:
            pass
        self.assertIsNone(player_class_display_name(Empty()))


if __name__ == '__main__':
    unittest.main()
