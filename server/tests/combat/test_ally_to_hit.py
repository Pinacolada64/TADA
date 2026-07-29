"""tests/combat/test_ally_to_hit.py — ally.to_hit now drives ally_attacks().

SPUR's p.a1 never consulted an ally's own to-hit rating (flat d10 vs a
hardcoded threshold of 4); this port ties the roll to the ally's actual
to_hit value instead. Ryan's request.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from combat.resolution import ally_attacks


def _monster():
    return {'name': 'Goblin', 'strength': 5}


class TestAllyToHit(unittest.TestCase):
    def test_default_to_hit_matches_old_flat_threshold(self):
        """No to_hit passed -> falls back to the old flat SPUR threshold
        of 4 (miss if roll > 4), so existing callers are unaffected."""
        with patch('combat.resolution.random.randint', return_value=4):
            result = ally_attacks('Grog', 15, _monster())
        self.assertTrue(result.hit)

        with patch('combat.resolution.random.randint', return_value=5):
            result = ally_attacks('Grog', 15, _monster())
        self.assertFalse(result.hit)

    def test_high_to_hit_lands_a_roll_that_would_otherwise_miss(self):
        with patch('combat.resolution.random.randint', return_value=7):
            result = ally_attacks('Grog', 15, _monster(), to_hit=7)
        self.assertTrue(result.hit)

    def test_low_to_hit_misses_a_roll_that_would_otherwise_land(self):
        with patch('combat.resolution.random.randint', return_value=3):
            result = ally_attacks('Grog', 15, _monster(), to_hit=2)
        self.assertFalse(result.hit)

    def test_light_armor_bonus_still_applies_on_top_of_to_hit(self):
        # roll=8, armor_bonus=2 -> effective roll 6; to_hit=6 -> hit.
        with patch('combat.resolution.random.randint', return_value=8):
            result = ally_attacks('Grog', 15, _monster(),
                                   has_light_armor=True, to_hit=6)
        self.assertTrue(result.hit)


if __name__ == '__main__':
    unittest.main()
