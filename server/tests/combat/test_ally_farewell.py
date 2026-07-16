"""tests/combat/test_ally_farewell.py — ally_events/farewell.py: per-ally
quit-time farewell lines (SPUR.SUB.S's "quit"/"al.quote" labels, skip
branch only).
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from bar.ally_data import Ally, AllyFlags


def _make_ally(name='Grog', flags=None):
    return Ally(name=name, gender='m', strength=15, to_hit=4, flags=flags)


def _make_player(party=None, name='Testerson'):
    player = MagicMock()
    player.name = name
    player.party = party if party is not None else []
    return player


class TestNoAllies(unittest.TestCase):
    def test_empty_party_returns_no_lines(self):
        from ally_events.farewell import farewell_lines
        self.assertEqual(farewell_lines(_make_player(party=[])), [])


class TestMortalAlly(unittest.TestCase):
    def test_mortal_line_substitutes_ally_name_no_title(self):
        from ally_events.farewell import farewell_lines
        ally = _make_ally('Grog')
        with patch('random.choice', side_effect=lambda pool: pool[0]):
            lines = farewell_lines(_make_player(party=[ally]))
        self.assertEqual(len(lines), 1)
        self.assertIn('Grog', lines[0])
        self.assertNotIn('THE GOD', lines[0])
        self.assertNotIn('THE GODDESS', lines[0])

    def test_mortal_pool_includes_the_classic_lines(self):
        """Ryan asked to keep the original stubbed placeholder lines as
        part of the mortal-tier pool rather than discard them."""
        from ally_events.farewell import _load_quotes
        pool = _load_quotes()['mortal']
        self.assertTrue(any('watch for your return' in q for q in pool))
        self.assertTrue(any('who will watch you' in q for q in pool))
        self.assertTrue(any('looks sad as you leave' in q for q in pool))


class TestDivineAllies(unittest.TestCase):
    def test_goddess_gets_title_prefix(self):
        from ally_events.farewell import farewell_lines
        ally = _make_ally('Persephone', flags=[AllyFlags.GODDESS])
        lines = farewell_lines(_make_player(party=[ally]))
        self.assertEqual(len(lines), 1)
        self.assertIn('THE GODDESS Persephone', lines[0])
        self.assertIn('tawny hair', lines[0])

    def test_god_gets_title_prefix(self):
        from ally_events.farewell import farewell_lines
        ally = _make_ally('Ares', flags=[AllyFlags.GOD])
        lines = farewell_lines(_make_player(party=[ally]))
        self.assertEqual(len(lines), 1)
        self.assertIn('THE GOD Ares', lines[0])

    def test_god_line_substitutes_player_name(self):
        from ally_events.farewell import farewell_lines
        ally = _make_ally('Ares', flags=[AllyFlags.GOD])
        lines = farewell_lines(_make_player(party=[ally], name='Killerella'))
        self.assertIn('Killerella', lines[0])


class TestMultipleAllies(unittest.TestCase):
    def test_one_line_per_party_member_in_order(self):
        """Unlike SPUR's fixed 3-slot cap, every party member gets a line."""
        from ally_events.farewell import farewell_lines
        grog = _make_ally('Grog')
        persephone = _make_ally('Persephone', flags=[AllyFlags.GODDESS])
        ares = _make_ally('Ares', flags=[AllyFlags.GOD])
        lasso = _make_ally('Lasso')
        player = _make_player(party=[grog, persephone, ares, lasso])
        lines = farewell_lines(player)
        self.assertEqual(len(lines), 4)
        self.assertIn('Grog', lines[0])
        self.assertIn('THE GODDESS Persephone', lines[1])
        self.assertIn('THE GOD Ares', lines[2])
        self.assertIn('Lasso', lines[3])


if __name__ == '__main__':
    unittest.main()
