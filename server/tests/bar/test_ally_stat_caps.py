"""tests/bar/test_ally_stat_caps.py

The canonical ally stat ceilings (bar/ally_data.py) and the SPUR-faithful
Fat Olaf MAINTAIN ceiling (bar/fat_olaf.py).

SPUR limits (via SPUR-code/SPUR.SYSOP.S ed.a.str / ed.a.hit and SPUR.BAR.S):
  - sysop could set ally strength 1-20, to-hit 1-9
  - Fat Olaf's hire adds a flat +5  (buy: a1 = x2 + 5)  -> 25 is the true max
  - SPUR has no ally-HP stat; the port's hit_points = strength * 2 -> 50 max
  - MAINTAIN only restores a drained ally back up to its catalog strength
    (or 15 for a free spirit) -- never grows it past that
"""
import json
import unittest

from bar.ally_data import (
    ALLY_HP_MAX,
    ALLY_STRENGTH_MAX,
    ALLY_TO_HIT_MAX,
    ALLY_TO_HIT_MIN,
    Ally,
    AllyStatus,
    base_ally_strength,
    clamp_ally_stats,
    _ALLIES_FILE,
)


def _ally(strength=10, to_hit=4, hp=20, name='ROBIN'):
    a = Ally(name, 'm', strength, to_hit, [])
    a.status = AllyStatus.SERVANT
    a.hit_points = hp
    return a


class TestCanonicalCeilings(unittest.TestCase):

    def test_values_match_spur(self):
        self.assertEqual(ALLY_STRENGTH_MAX, 25)
        self.assertEqual(ALLY_TO_HIT_MIN, 0)
        self.assertEqual(ALLY_TO_HIT_MAX, 9)
        self.assertEqual(ALLY_HP_MAX, 50)


class TestClampAllyStats(unittest.TestCase):

    def test_in_range_is_untouched(self):
        a = _ally(strength=12, to_hit=5, hp=24)
        self.assertFalse(clamp_ally_stats(a))
        self.assertEqual((a.strength, a.to_hit, a.hit_points), (12, 5, 24))

    def test_runaway_values_are_pulled_back(self):
        a = _ally(strength=180, to_hit=40, hp=999)
        self.assertTrue(clamp_ally_stats(a))
        self.assertEqual(a.strength, ALLY_STRENGTH_MAX)
        self.assertEqual(a.to_hit, ALLY_TO_HIT_MAX)
        self.assertEqual(a.hit_points, ALLY_HP_MAX)

    def test_floor_is_enforced(self):
        a = _ally(strength=0, to_hit=-3, hp=-10)
        self.assertTrue(clamp_ally_stats(a))
        self.assertEqual(a.strength, 1)
        self.assertEqual(a.to_hit, ALLY_TO_HIT_MIN)
        self.assertEqual(a.hit_points, 0)


class TestBaseAllyStrength(unittest.TestCase):

    def test_reads_pristine_value_from_json(self):
        raw = {e['name']: e['strength'] for e in json.loads(_ALLIES_FILE.read_text())}
        # pick any real catalog ally and confirm we get its json strength back
        name, strength = next(iter(raw.items()))
        self.assertEqual(base_ally_strength(name), strength)

    def test_unknown_name_returns_none(self):
        self.assertIsNone(base_ally_strength('NOT A REAL ALLY 12345'))


class TestMaintainCeiling(unittest.TestCase):

    def test_catalog_ally_ceiling_is_base_plus_hire_bonus(self):
        from bar.fat_olaf import _HIRE_STR_BONUS, _maintain_ceiling
        name = next(iter(json.loads(_ALLIES_FILE.read_text())))['name']
        base = base_ally_strength(name)
        a = _ally(name=name, strength=1)
        expected = min(base + _HIRE_STR_BONUS, ALLY_STRENGTH_MAX)
        self.assertEqual(_maintain_ceiling(a), expected)

    def test_free_spirit_ceiling_is_fifteen(self):
        from bar.fat_olaf import _FREE_SPIRIT_STR_CEIL, _maintain_ceiling
        a = _ally(name='SOME CHARMED THING', strength=1)
        self.assertEqual(_maintain_ceiling(a), _FREE_SPIRIT_STR_CEIL)

    def test_ceiling_never_exceeds_strength_max(self):
        from bar.fat_olaf import _maintain_ceiling
        for entry in json.loads(_ALLIES_FILE.read_text()):
            a = _ally(name=entry['name'], strength=1)
            self.assertLessEqual(_maintain_ceiling(a), ALLY_STRENGTH_MAX)


if __name__ == '__main__':
    unittest.main()
