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
        part of the mortal-tier pool rather than discard them. The
        "I will watch.."/"Yeah? And who.." pair later split out into the
        "mortal_exchange" paired sequence (see TestPairedExchange)."""
        from ally_events.farewell import _load_quotes
        pool = _load_quotes()['mortal']
        self.assertTrue(any('looks sad as you leave' in q for q in pool))
        self.assertFalse(any('watch for your return' in q for q in pool))
        self.assertFalse(any('who will watch you' in q for q in pool))


class TestDivineAllies(unittest.TestCase):
    def test_goddess_gets_title_prefix(self):
        from ally_events.farewell import farewell_lines
        ally = _make_ally('Persephone', flags=[AllyFlags.GODDESS])
        with patch('random.choice', side_effect=lambda pool: pool[0]):
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
        with patch('random.choice', side_effect=lambda pool: pool[0]):
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


class TestPronounSubstitution(unittest.TestCase):
    def test_percent_p_resolves_per_ally_gender(self):
        from ally_events.farewell import _substitute
        male_ally = _make_ally('Grog', flags=None)
        female_ally = _make_ally('Xena', flags=None)
        female_ally.gender = 'f'
        self.assertEqual(
            _substitute('%n cleans %p gear.', 'Tester', 'Grog', male_ally),
            'Grog cleans his gear.',
        )
        self.assertEqual(
            _substitute('%n cleans %p gear.', 'Tester', 'Xena', female_ally),
            'Xena cleans her gear.',
        )

    def test_all_pronoun_tokens_resolve(self):
        from ally_events.farewell import _substitute
        ally = _make_ally('Grog', flags=None)
        result = _substitute('%s %o %p %P %r', 'Tester', 'Grog', ally)
        self.assertEqual(result, 'he him his his himself')

    def test_percent_n_substitutes_ally_display_name(self):
        from ally_events.farewell import _substitute
        ally = _make_ally('Grog', flags=None)
        result = _substitute('%n waves at $.', 'Tester', 'THE GOD Grog', ally)
        self.assertEqual(result, 'THE GOD Grog waves at Tester.')


class TestPairedExchange(unittest.TestCase):
    def test_first_two_mortals_get_the_exchange_when_it_fires(self):
        from ally_events.farewell import farewell_lines
        grog  = _make_ally('Grog')
        lasso = _make_ally('Lasso')
        with patch('random.random', return_value=0.0):
            lines = farewell_lines(_make_player(party=[grog, lasso]))
        self.assertEqual(len(lines), 2)
        self.assertIn('watch for your return', lines[0])
        self.assertIn('Grog', lines[0])
        self.assertIn('who will watch you', lines[1])
        self.assertIn('Lasso', lines[1])

    def test_exchange_never_fires_below_the_roll_threshold(self):
        from ally_events.farewell import farewell_lines
        grog  = _make_ally('Grog')
        lasso = _make_ally('Lasso')
        with patch('random.random', return_value=0.999), \
             patch('random.choice', side_effect=lambda pool: pool[0]):
            lines = farewell_lines(_make_player(party=[grog, lasso]))
        self.assertEqual(len(lines), 2)
        self.assertNotIn('watch for your return', lines[0])
        self.assertNotIn('who will watch you', lines[1])

    def test_exchange_never_fires_with_only_one_mortal_ally(self):
        from ally_events.farewell import farewell_lines
        grog = _make_ally('Grog')
        with patch('random.random', return_value=0.0):
            lines = farewell_lines(_make_player(party=[grog]))
        self.assertEqual(len(lines), 1)
        self.assertNotIn('watch for your return', lines[0])

    def test_a_third_mortal_ally_still_gets_a_normal_line(self):
        from ally_events.farewell import farewell_lines
        grog  = _make_ally('Grog')
        lasso = _make_ally('Lasso')
        bork  = _make_ally('Bork')
        with patch('random.random', return_value=0.0), \
             patch('random.choice', side_effect=lambda pool: pool[0]):
            lines = farewell_lines(_make_player(party=[grog, lasso, bork]))
        self.assertEqual(len(lines), 3)
        self.assertIn('watch for your return', lines[0])
        self.assertIn('who will watch you', lines[1])
        self.assertNotIn('watch for your return', lines[2])
        self.assertNotIn('who will watch you', lines[2])
        self.assertIn('Bork', lines[2])


if __name__ == '__main__':
    unittest.main()
