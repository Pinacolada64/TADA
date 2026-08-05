"""tests/combat/test_duel_ammo_penalty.py

SPUR.DUEL.S:115 "rdy.wp1": a missile/energy weapon (wa=8/10) with no ammo
readied gets wd/ws/zt/zs (damage, ease-of-use, accuracy, class/race damage
bonus) all halved for the whole duel, instead of refusing the fight --
see combat/duel.py's _ammo_penalty()/_duel_needs_ammo().
"""
from __future__ import annotations

import unittest

from base_classes import PlayerClass, PlayerRace
from combat.duel import _ammo_penalty, _offense_rating, _weapon_damage
from items import Weapon
from player import Player


def _duelist(*, weapon_class: str, weapon_name: str = 'RAY GUN', ammo_rounds: int = 0):
    p = Player(name='Rulan', id='rulan')
    p.char_class = PlayerClass.FIGHTER
    p.char_race = PlayerRace.HUMAN
    p.stats = {}
    p.readied_weapon = Weapon(
        id_number=1, name=weapon_name, stability=60,
        to_hit=60, weapon_class=weapon_class,
    )
    p.ammo_rounds = ammo_rounds
    return p


class TestAmmoPenaltyGating(unittest.TestCase):
    def test_projectile_weapon_no_ammo_is_penalized(self):
        p = _duelist(weapon_class='projectile', ammo_rounds=0)
        self.assertEqual(_ammo_penalty(p, p.readied_weapon), 0.5)

    def test_energy_weapon_no_ammo_is_penalized(self):
        p = _duelist(weapon_class='energy', ammo_rounds=0)
        self.assertEqual(_ammo_penalty(p, p.readied_weapon), 0.5)

    def test_projectile_weapon_with_ammo_is_not_penalized(self):
        p = _duelist(weapon_class='projectile', ammo_rounds=6)
        self.assertEqual(_ammo_penalty(p, p.readied_weapon), 1.0)

    def test_melee_weapon_never_penalized_regardless_of_ammo(self):
        p = _duelist(weapon_class='bash/slash', ammo_rounds=0)
        self.assertEqual(_ammo_penalty(p, p.readied_weapon), 1.0)

    def test_storm_weapon_bypasses_ammo_entirely(self):
        p = _duelist(weapon_class='energy', weapon_name='STORM STAFF', ammo_rounds=0)
        self.assertEqual(_ammo_penalty(p, p.readied_weapon), 1.0)

    def test_no_weapon_readied_is_not_penalized(self):
        p = _duelist(weapon_class='projectile', ammo_rounds=0)
        self.assertEqual(_ammo_penalty(p, None), 1.0)


class TestAmmoPenaltyAppliedToStats(unittest.TestCase):
    def test_offense_rating_drops_when_unloaded(self):
        loaded   = _duelist(weapon_class='projectile', ammo_rounds=6)
        unloaded = _duelist(weapon_class='projectile', ammo_rounds=0)
        loaded_rating   = _offense_rating(loaded, loaded.readied_weapon)
        unloaded_rating = _offense_rating(unloaded, unloaded.readied_weapon)
        self.assertLessEqual(unloaded_rating, loaded_rating)

    def test_weapon_damage_drops_when_unloaded(self):
        loaded   = _duelist(weapon_class='projectile', ammo_rounds=6)
        unloaded = _duelist(weapon_class='projectile', ammo_rounds=0)
        # Average over many rolls to smooth out _weapon_damage's own dice.
        loaded_avg = sum(_weapon_damage(loaded, loaded.readied_weapon) for _ in range(500)) / 500
        unloaded_avg = sum(_weapon_damage(unloaded, unloaded.readied_weapon) for _ in range(500)) / 500
        self.assertLess(unloaded_avg, loaded_avg)


if __name__ == '__main__':
    unittest.main(verbosity=2)
