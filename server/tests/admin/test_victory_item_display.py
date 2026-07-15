"""tests/test_victory_item_display.py — display formatting for
config.py's victory_item_number setting.

Ryan: 'display item name in both editors if goal is set to item/both:
"(35) Sand Dollar"' -- item_system.format_victory_item_value() is the
shared formatter both commands/config.py and setup/server_setup.py wrap
in their own _display_value() helpers.
"""
from __future__ import annotations

import unittest

from item_system import format_victory_item_value, treasure_name_by_number


class TestTreasureNameByNumber(unittest.TestCase):
    def test_known_item_returns_title_case_name(self):
        # objects.json #35 "sand dollar" -- Ryan's own example.
        self.assertEqual(treasure_name_by_number(35), 'Sand Dollar')

    def test_zero_returns_none(self):
        self.assertIsNone(treasure_name_by_number(0))

    def test_unknown_number_returns_none(self):
        self.assertIsNone(treasure_name_by_number(999999))


class TestFormatVictoryItemValue(unittest.TestCase):
    def test_gold_type_shows_bare_number_regardless_of_value(self):
        self.assertEqual(format_victory_item_value(35, 'gold'), '35')
        self.assertEqual(format_victory_item_value(0, 'gold'), '0')

    def test_item_type_shows_name_when_set(self):
        self.assertEqual(format_victory_item_value(35, 'item'), '(35) Sand Dollar')

    def test_both_type_shows_name_when_set(self):
        self.assertEqual(format_victory_item_value(35, 'both'), '(35) Sand Dollar')

    def test_item_type_with_zero_shows_bare_zero_not_a_name(self):
        self.assertEqual(format_victory_item_value(0, 'item'), '0')

    def test_unknown_number_falls_back_gracefully(self):
        self.assertEqual(format_victory_item_value(999999, 'item'), '(999999) unknown item')


if __name__ == '__main__':
    unittest.main()
