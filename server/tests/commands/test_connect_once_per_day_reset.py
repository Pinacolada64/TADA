"""tests/commands/test_connect_once_per_day_reset.py

Covers commands/connect.py's _maybe_reset_once_per_day() -- clearing
player.once_per_day on calendar-date rollover (TODO.md's "7/15/26"
plan). Compares calendar dates only, not a full 24h elapsed check.
"""
from __future__ import annotations

import datetime
import unittest
from unittest.mock import MagicMock

from commands.connect import _maybe_reset_once_per_day


def _player(last_connection, once_per_day=None):
    player = MagicMock()
    player.name = 'Rulan'
    player.last_connection = last_connection
    player.once_per_day = once_per_day if once_per_day is not None else ['Skip', 'pawn']
    player.unsaved_changes = False
    return player


class TestMaybeResetOncePerDay(unittest.TestCase):
    def test_clears_when_date_has_rolled_over(self):
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        player = _player(yesterday)
        _maybe_reset_once_per_day(player)
        self.assertEqual(player.once_per_day, [])
        self.assertTrue(player.unsaved_changes)

    def test_leaves_untouched_within_same_calendar_day(self):
        earlier_today = datetime.datetime.now() - datetime.timedelta(hours=1)
        player = _player(earlier_today)
        _maybe_reset_once_per_day(player)
        self.assertEqual(player.once_per_day, ['Skip', 'pawn'])
        self.assertFalse(player.unsaved_changes)

    def test_compares_calendar_date_not_full_24h(self):
        """Last connected 23 hours ago but still calendar-yesterday --
        should reset even though less than 24h elapsed, matching
        player.last_connection's documented "day rolling over, not 24h
        elapsed" semantics."""
        just_after_midnight = datetime.datetime.now().replace(hour=0, minute=1, second=0, microsecond=0)
        just_before_midnight_yesterday = just_after_midnight - datetime.timedelta(minutes=2)
        player = _player(just_before_midnight_yesterday)
        _maybe_reset_once_per_day(player)
        self.assertEqual(player.once_per_day, [])

    def test_no_op_when_already_empty(self):
        yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
        player = _player(yesterday, once_per_day=[])
        _maybe_reset_once_per_day(player)
        self.assertEqual(player.once_per_day, [])
        self.assertFalse(player.unsaved_changes)  # nothing changed, no need to mark dirty

    def test_no_op_when_last_connection_missing(self):
        player = _player(None)
        _maybe_reset_once_per_day(player)
        self.assertEqual(player.once_per_day, ['Skip', 'pawn'])
        self.assertFalse(player.unsaved_changes)

    def test_future_last_connection_does_not_reset(self):
        """Defensive: a clock-skew/edge case where last_connection is
        somehow in the future shouldn't clear anything (today > last
        is False in that case)."""
        tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
        player = _player(tomorrow)
        _maybe_reset_once_per_day(player)
        self.assertEqual(player.once_per_day, ['Skip', 'pawn'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
