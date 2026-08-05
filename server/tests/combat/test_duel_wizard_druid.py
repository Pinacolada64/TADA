"""tests/combat/test_duel_wizard_druid.py — combat/duel.py's Wizard
spell-casting and Druid self-heal (SPUR.DUEL.S "wiz.a"/"wiz.b",
"druid.a"/"druid.b"): a Wizard gets one guaranteed-hit spell bolt per
duel, and a Druid under a comfortable HP ceiling has a chance to turn any
incoming hit into a heal instead.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from base_classes import PlayerClass, PlayerRace
from combat.duel import (
    DuelSession, DuelTactic, _DRUID_HEAL_HP_CEILING, _wizard_bolt_damage,
)
from items import Weapon
from player import Player


class _FakeCtx:
    def __init__(self):
        self.sent: list = []
        self.server = None
        self.client = None

    async def send(self, *args):
        self.sent.extend(args)


def _make_duelist(name, *, char_class=PlayerClass.FIGHTER, hit_points=30, staff=False):
    p = Player(name=name, id=name.lower())
    p.char_class = char_class
    p.char_race = PlayerRace.HUMAN
    p.hit_points = hit_points
    p.shield = 0
    p.armor = 0
    p.readied_weapon = Weapon(
        id_number=1, name='STAFF OF POWER' if staff else 'LONG SWORD',
        stability=50, to_hit=60, weapon_class='bash/slash',
    )
    return p


def _make_session(a, b):
    return DuelSession(a, _FakeCtx(), b, _FakeCtx())


class TestWizardBoltDamage(unittest.TestCase):
    def test_no_staff_bonus_without_staff_weapon(self):
        sword = Weapon(id_number=1, name='LONG SWORD', stability=50, to_hit=60, weapon_class='bash/slash')
        with patch('combat.duel.random.randint', return_value=100):
            self.assertEqual(_wizard_bolt_damage(sword), 8.0)  # 100/20 + 3

    def test_staff_bonus_when_wielding_a_staff(self):
        staff = Weapon(id_number=1, name='STAFF OF POWER', stability=50, to_hit=60, weapon_class='bash/slash')
        with patch('combat.duel.random.randint', return_value=100):
            self.assertEqual(_wizard_bolt_damage(staff), 11.0)  # 100/20 + 3 + 3


class TestWizardCastingInDuel(unittest.IsolatedAsyncioTestCase):
    async def test_non_wizard_never_casts(self):
        a = _make_duelist('Ardent', char_class=PlayerClass.FIGHTER)
        b = _make_duelist('Belwin')
        session = _make_session(a, b)
        session.a.tactic = DuelTactic.ATTACK
        session.b.tactic = DuelTactic.PARRY
        with patch('combat.duel.random.randint', return_value=1):  # would trigger casting if eligible
            line = session._swing(session.a, session.b)
        self.assertNotIn('Energy flashes', line)
        self.assertFalse(session.a.cast_used)

    async def test_wizard_casts_and_bypasses_hit_roll(self):
        a = _make_duelist('Ardent', char_class=PlayerClass.WIZARD)
        b = _make_duelist('Belwin', hit_points=30)
        session = _make_session(a, b)
        session.a.tactic = DuelTactic.ATTACK
        session.b.tactic = DuelTactic.PARRY
        # First randint call is the cast-chance roll (<=30 triggers);
        # second is the bolt-damage roll; neither reaches a stability
        # hit-roll, since the spell branch returns before it.
        with patch('combat.duel.random.randint', side_effect=[10, 100]):
            line = session._swing(session.a, session.b)
        self.assertIn('Energy flashes', line)
        self.assertIn('hits', line)
        self.assertTrue(session.a.cast_used)
        self.assertEqual(b.hit_points, 30 - 8)  # 100/20+3 = 8, no staff

    async def test_cast_is_one_shot_per_duel(self):
        a = _make_duelist('Ardent', char_class=PlayerClass.WIZARD)
        b = _make_duelist('Belwin')
        session = _make_session(a, b)
        session.a.cast_used = True
        session.a.tactic = DuelTactic.ATTACK
        session.b.tactic = DuelTactic.PARRY
        with patch('combat.duel.random.randint', return_value=1):  # would trigger if not already used
            line = session._swing(session.a, session.b)
        self.assertNotIn('Energy flashes', line)

    async def test_staff_amplifies_the_bolt(self):
        a = _make_duelist('Ardent', char_class=PlayerClass.WIZARD, staff=True)
        b = _make_duelist('Belwin', hit_points=30)
        session = _make_session(a, b)
        session.a.tactic = DuelTactic.ATTACK
        session.b.tactic = DuelTactic.PARRY
        with patch('combat.duel.random.randint', side_effect=[10, 100]):
            line = session._swing(session.a, session.b)
        self.assertIn('staff amplifies', line)
        self.assertEqual(b.hit_points, 30 - 11)  # 100/20+3+3 = 11


class TestDruidSelfHeal(unittest.IsolatedAsyncioTestCase):
    async def test_druid_below_ceiling_can_heal_instead_of_taking_damage(self):
        a = _make_duelist('Ardent', char_class=PlayerClass.FIGHTER)
        b = _make_duelist('Belwin', char_class=PlayerClass.DRUID, hit_points=10)
        session = _make_session(a, b)
        with patch('combat.duel.random.randint', return_value=1):  # guarantee the 10% heal roll
            line = session._apply_final_damage(session.a, session.b, 5)
        self.assertIn('channels nature and heals', line)
        self.assertEqual(b.hit_points, 15)

    async def test_druid_at_or_above_ceiling_takes_damage_normally(self):
        a = _make_duelist('Ardent', char_class=PlayerClass.FIGHTER)
        b = _make_duelist('Belwin', char_class=PlayerClass.DRUID, hit_points=30)
        session = _make_session(a, b)
        # 30 + 5 = 35, not under _DRUID_HEAL_HP_CEILING -- heal never rolled.
        with patch('combat.duel.random.randint', return_value=1):
            line = session._apply_final_damage(session.a, session.b, 5)
        self.assertIn('hits', line)
        self.assertEqual(b.hit_points, 25)

    async def test_non_druid_never_heals(self):
        a = _make_duelist('Ardent', char_class=PlayerClass.FIGHTER)
        b = _make_duelist('Belwin', char_class=PlayerClass.FIGHTER, hit_points=10)
        session = _make_session(a, b)
        with patch('combat.duel.random.randint', return_value=1):  # would heal if Druid
            line = session._apply_final_damage(session.a, session.b, 5)
        self.assertIn('hits', line)
        self.assertEqual(b.hit_points, 5)

    async def test_heal_roll_failure_still_takes_damage(self):
        a = _make_duelist('Ardent', char_class=PlayerClass.FIGHTER)
        b = _make_duelist('Belwin', char_class=PlayerClass.DRUID, hit_points=10)
        session = _make_session(a, b)
        with patch('combat.duel.random.randint', return_value=100):  # fails the 10% heal roll
            line = session._apply_final_damage(session.a, session.b, 5)
        self.assertIn('hits', line)
        self.assertEqual(b.hit_points, 5)

    async def test_heal_ceiling_uses_less_than_not_less_or_equal(self):
        a = _make_duelist('Ardent', char_class=PlayerClass.FIGHTER)
        # hit_points + damage == ceiling exactly -> not eligible (SPUR "if h+w1<26")
        b = _make_duelist('Belwin', char_class=PlayerClass.DRUID,
                           hit_points=_DRUID_HEAL_HP_CEILING - 5)
        session = _make_session(a, b)
        with patch('combat.duel.random.randint', return_value=1):
            line = session._apply_final_damage(session.a, session.b, 5)
        self.assertIn('hits', line)


if __name__ == '__main__':
    unittest.main()
