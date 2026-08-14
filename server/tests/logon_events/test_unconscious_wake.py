"""tests/test_unconscious_wake.py

Covers logon_events/unconscious_wake.py: clearing PlayerFlags.UNCONSCIOUS
and defeated_by at login, and printing SPUR.LOGON.S rd.user's wake-up
line ("You slowly awaken from your duel loss...", TADA-extended to name
the opponent when known).
"""
from __future__ import annotations

import unittest

from flags import PlayerFlags
from logon_events.unconscious_wake import wake_lines
from player import Player


class TestWakeLines(unittest.TestCase):
    def test_none_when_not_unconscious(self):
        player = Player(name='Rulan')
        self.assertIsNone(wake_lines(player))

    def test_wakes_and_names_the_opponent(self):
        player = Player(name='Rulan')
        player.set_flag(PlayerFlags.UNCONSCIOUS)
        player.defeated_by = 'Belwin'

        lines = wake_lines(player)

        self.assertEqual(lines, ['You slowly awaken from your duel loss to Belwin...'])
        self.assertFalse(player.query_flag(PlayerFlags.UNCONSCIOUS))
        self.assertIsNone(player.defeated_by)
        self.assertTrue(player.unsaved_changes)

    def test_wakes_without_naming_anyone_if_opponent_unknown(self):
        player = Player(name='Rulan')
        player.set_flag(PlayerFlags.UNCONSCIOUS)
        player.defeated_by = None

        lines = wake_lines(player)

        self.assertEqual(lines, ['You slowly awaken from your duel loss...'])
        self.assertFalse(player.query_flag(PlayerFlags.UNCONSCIOUS))


if __name__ == '__main__':
    unittest.main()
