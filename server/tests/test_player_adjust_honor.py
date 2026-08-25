"""tests/test_player_adjust_honor.py

Covers Player.adjust_honor() (player.py) -- the single entry point added
to replace the many scattered `player.honor +/-= N; player.unsaved_changes
= True` call sites (see commands/read.py's scrap-of-paper honor penalty
for one caller). Lower Honor means more evil; higher Honor means more
good -- SPUR's convention, not a typo.
"""
from __future__ import annotations

import unittest

from player import Player


def _new_player(honor: int = 1000) -> Player:
    return Player(name='Rulan', honor=honor)


class TestAdjustHonorMutatesAndFlagsUnsaved(unittest.TestCase):
    def test_negative_adjustment_lowers_honor(self):
        player = _new_player(honor=10)
        player.unsaved_changes = False
        player.adjust_honor(-2)
        self.assertEqual(player.honor, 8)
        self.assertTrue(player.unsaved_changes)

    def test_positive_adjustment_raises_honor(self):
        player = _new_player(honor=10)
        player.unsaved_changes = False
        player.adjust_honor(5)
        self.assertEqual(player.honor, 15)
        self.assertTrue(player.unsaved_changes)


class TestAdjustHonorReturnValue(unittest.TestCase):
    def test_negative_adjustment_returns_less_honorable_message(self):
        player = _new_player(honor=10)
        result = player.adjust_honor(-2)
        self.assertIsNotNone(result)
        new_honor, message = result
        self.assertEqual(new_honor, 8)
        self.assertIn('less honorable', message)

    def test_positive_adjustment_returns_more_honorable_message(self):
        player = _new_player(honor=10)
        result = player.adjust_honor(5)
        self.assertIsNotNone(result)
        new_honor, message = result
        self.assertEqual(new_honor, 15)
        self.assertIn('more honorable', message)

    def test_negative_adjustment_message_shows_signed_delta(self):
        player = _new_player(honor=10)
        _, message = player.adjust_honor(-2)
        self.assertEqual(message, '(You feel less honorable) (-2)')

    def test_positive_adjustment_message_shows_signed_delta(self):
        player = _new_player(honor=10)
        _, message = player.adjust_honor(5)
        self.assertEqual(message, '(You feel more honorable) (+5)')

    def test_zero_adjustment_returns_none_and_does_not_mark_unsaved(self):
        player = _new_player(honor=10)
        player.unsaved_changes = False
        result = player.adjust_honor(0)
        self.assertIsNone(result)
        self.assertEqual(player.honor, 10)
        self.assertFalse(player.unsaved_changes)


class TestAdjustHonorAllowsNegativeHonor(unittest.TestCase):
    """SPUR lets Honor go negative (deeply evil characters) -- adjust_honor
    performs no clamping of its own; that's the caller's job if it wants one."""

    def test_can_go_below_zero(self):
        player = _new_player(honor=1)
        player.adjust_honor(-5)
        self.assertEqual(player.honor, -4)


if __name__ == '__main__':
    unittest.main()
