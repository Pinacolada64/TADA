"""tests/combat/test_duel_initiative.py — combat/duel.py's
_compute_initiative()/_initiative_score() (SPUR.DUEL.S:83-86 "vw"/"zr",
tac.bash's "INITIATIVE BONUS" +/-10% branch): whoever leads by more than
10 initiative points (level*2 + weapon accuracy/damage bonus +
STR+DEX+INT) gets a flat +10 hit-chance edge for the whole duel; their
opponent gets -10. A tie (gap <= 10) grants neither side anything.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from base_classes import PlayerClass, PlayerRace, PlayerStat
from combat.duel import (
    DuelSession, DuelTactic, _compute_initiative, _initiative_score,
    _INITIATIVE_BONUS,
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


def _make_duelist(name, *, level=1, str_=10, dex=10, int_=10):
    p = Player(name=name, id=name.lower())
    p.char_class = PlayerClass.FIGHTER
    p.char_race = PlayerRace.HUMAN
    p.xp_level = level
    p.stats[PlayerStat.STR] = str_
    p.stats[PlayerStat.DEX] = dex
    p.stats[PlayerStat.INT] = int_
    p.readied_weapon = Weapon(
        id_number=1, name='LONG SWORD', stability=50,
        to_hit=60, weapon_class='bash/slash',
    )
    return p


def _make_session(a, b):
    return DuelSession(a, _FakeCtx(), b, _FakeCtx())


class TestInitiativeScore(unittest.TestCase):
    def test_higher_stats_yield_higher_score(self):
        weak = _make_duelist('Weak', str_=8, dex=8, int_=8)
        strong = _make_duelist('Strong', str_=18, dex=18, int_=18)
        weak_side = _make_session(weak, strong).a
        strong_side = _make_session(strong, weak).a
        self.assertGreater(_initiative_score(strong_side), _initiative_score(weak_side))

    def test_higher_level_yields_higher_score(self):
        low = _make_duelist('Low', level=1)
        high = _make_duelist('High', level=10)
        low_side = _make_session(low, high).a
        high_side = _make_session(high, low).a
        self.assertGreater(_initiative_score(high_side), _initiative_score(low_side))


class TestComputeInitiative(unittest.TestCase):
    def test_evenly_matched_sides_grant_no_initiative(self):
        a = _make_duelist('Ardent')
        b = _make_duelist('Belwin')
        session = _make_session(a, b)
        _compute_initiative(session)
        self.assertEqual(session.a.initiative, 0)
        self.assertEqual(session.b.initiative, 0)

    def test_clear_leader_gets_bonus_and_opponent_gets_penalty(self):
        a = _make_duelist('Ardent', level=20, str_=18, dex=18, int_=18)
        b = _make_duelist('Belwin', level=1, str_=8, dex=8, int_=8)
        session = _make_session(a, b)
        _compute_initiative(session)
        self.assertEqual(session.a.initiative, _INITIATIVE_BONUS)
        self.assertEqual(session.b.initiative, -_INITIATIVE_BONUS)

    def test_leadership_can_go_either_way(self):
        a = _make_duelist('Ardent', level=1, str_=8, dex=8, int_=8)
        b = _make_duelist('Belwin', level=20, str_=18, dex=18, int_=18)
        session = _make_session(a, b)
        _compute_initiative(session)
        self.assertEqual(session.b.initiative, _INITIATIVE_BONUS)
        self.assertEqual(session.a.initiative, -_INITIATIVE_BONUS)

    def test_small_gap_within_threshold_grants_nothing(self):
        a = _make_duelist('Ardent', level=1, str_=11, dex=10, int_=10)
        b = _make_duelist('Belwin', level=1, str_=10, dex=10, int_=10)
        session = _make_session(a, b)
        _compute_initiative(session)
        self.assertEqual(session.a.initiative, 0)
        self.assertEqual(session.b.initiative, 0)


class TestInitiativeAppliedInDuel(unittest.IsolatedAsyncioTestCase):
    async def test_initiative_boosts_accuracy_enough_to_turn_a_miss_into_a_hit(self):
        a = _make_duelist('Ardent', level=20, str_=18, dex=18, int_=18)
        b = _make_duelist('Belwin', level=1, str_=8, dex=8, int_=8)
        session = _make_session(a, b)
        _compute_initiative(session)
        self.assertEqual(session.a.initiative, _INITIATIVE_BONUS)

        # PARRY vs PARRY: _INTERACTION gives -20, so stability 50 -> a 30
        # threshold with no initiative. Roll 35: without initiative, 35 > 30
        # -> miss. With +10 initiative, threshold becomes 40, 35 <= 40 -> hit.
        session.a.tactic = DuelTactic.PARRY
        session.b.tactic = DuelTactic.PARRY
        with patch('combat.duel.random.randint', return_value=35):
            line = session._swing(session.a, session.b)
        self.assertIn('hits', line)

    async def test_initiative_penalty_turns_a_hit_into_a_miss(self):
        a = _make_duelist('Ardent', level=20, str_=18, dex=18, int_=18)
        b = _make_duelist('Belwin', level=1, str_=8, dex=8, int_=8)
        session = _make_session(a, b)
        _compute_initiative(session)
        self.assertEqual(session.b.initiative, -_INITIATIVE_BONUS)

        # PARRY vs PARRY: stability 50 -20 = 30 threshold with no penalty.
        # Roll 25: without penalty, 25 <= 30 -> hit. With -10 penalty,
        # threshold becomes 20, 25 > 20 -> miss.
        session.a.tactic = DuelTactic.PARRY
        session.b.tactic = DuelTactic.PARRY
        with patch('combat.duel.random.randint', return_value=25):
            line = session._swing(session.b, session.a)
        self.assertIn('misses', line)


if __name__ == '__main__':
    unittest.main()
