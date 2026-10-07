"""tests/combat/test_monster_hp.py

combat/engine.py's _monster_hp(): a monster hit down to exactly 0 HP is
dead. It used to read as 5 ("strength or hit_points or 5" -- 0 is falsy),
so the monster "healed" instead of dying and only an overshoot below 0
ever killed it.

Run with:
    .venv/bin/python3 -m pytest tests/combat/test_monster_hp.py -v
"""
from __future__ import annotations

import unittest


class TestMonsterHpZero(unittest.TestCase):

    def test_zero_strength_reads_as_zero(self):
        from combat.engine import _monster_hp, _set_monster_hp
        monster = {'strength': 4}
        _set_monster_hp(monster, 4 - 4)
        self.assertEqual(_monster_hp(monster), 0)      # was 5: the monster "healed"

    def test_fallbacks_still_apply_when_missing(self):
        from combat.engine import _monster_hp
        self.assertEqual(_monster_hp({'hit_points': 7}), 7)
        self.assertEqual(_monster_hp({'hit_points': 0}), 0)
        self.assertEqual(_monster_hp({}), 5)


if __name__ == '__main__':
    unittest.main()
