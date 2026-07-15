"""Tests for starting_equipment.py -- beginner shield/armor/weapon assignment."""
import unittest
from unittest.mock import patch

from base_classes import PlayerClass, PlayerRace
from starting_equipment import (
    _INTACTNESS_MAX,
    _INTACTNESS_MIN,
    roll_armor,
    roll_shield,
    starter_weapon_number,
)


class TestEligibilityGating(unittest.TestCase):
    def test_wizard_never_gets_shield(self):
        with patch('starting_equipment.random.random', return_value=0.0):
            self.assertIsNone(roll_shield(PlayerClass.WIZARD, PlayerRace.HUMAN))

    def test_wizard_never_gets_armor(self):
        with patch('starting_equipment.random.random', return_value=0.0):
            self.assertIsNone(roll_armor(PlayerClass.WIZARD, PlayerRace.HUMAN))

    def test_archer_never_gets_shield(self):
        with patch('starting_equipment.random.random', return_value=0.0):
            self.assertIsNone(roll_shield(PlayerClass.ARCHER, PlayerRace.HUMAN))

    def test_archer_can_get_armor(self):
        with patch('starting_equipment.random.random', return_value=0.0):
            self.assertIsNotNone(roll_armor(PlayerClass.ARCHER, PlayerRace.HUMAN))

    def test_pixie_never_gets_shield_or_armor(self):
        with patch('starting_equipment.random.random', return_value=0.0):
            self.assertIsNone(roll_shield(PlayerClass.FIGHTER, PlayerRace.PIXIE))
            self.assertIsNone(roll_armor(PlayerClass.FIGHTER, PlayerRace.PIXIE))

    def test_eligible_class_race_can_get_both(self):
        with patch('starting_equipment.random.random', return_value=0.0):
            self.assertIsNotNone(roll_shield(PlayerClass.FIGHTER, PlayerRace.HUMAN))
            self.assertIsNotNone(roll_armor(PlayerClass.FIGHTER, PlayerRace.HUMAN))


class TestCoinFlipAndIntactness(unittest.TestCase):
    def test_failed_roll_returns_none(self):
        with patch('starting_equipment.random.random', return_value=0.99):
            self.assertIsNone(roll_shield(PlayerClass.FIGHTER, PlayerRace.HUMAN))
            self.assertIsNone(roll_armor(PlayerClass.FIGHTER, PlayerRace.HUMAN))

    def test_intactness_within_spec_bounds(self):
        """<70% per spec -- roll_shield's returned value must be < 70."""
        with patch('starting_equipment.random.random', return_value=0.0):
            for _ in range(200):
                val = roll_shield(PlayerClass.FIGHTER, PlayerRace.HUMAN)
                self.assertIsNotNone(val)
                self.assertGreaterEqual(val, _INTACTNESS_MIN)
                self.assertLessEqual(val, _INTACTNESS_MAX)
                self.assertLess(val, 70)


class TestStarterWeaponTable(unittest.TestCase):
    def test_every_class_has_a_starter_weapon(self):
        for pc in PlayerClass:
            self.assertIsNotNone(
                starter_weapon_number(pc), f'{pc} has no starter weapon entry'
            )

    def test_wizard_gets_wood_staff(self):
        self.assertEqual(starter_weapon_number(PlayerClass.WIZARD), 3)

    def test_archer_gets_long_bow(self):
        self.assertEqual(starter_weapon_number(PlayerClass.ARCHER), 6)


if __name__ == '__main__':
    unittest.main()
