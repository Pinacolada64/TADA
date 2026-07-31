"""tests/combat/test_duel_down.py — combat/duel.py's Down-state menu
(SPUR.DUEL.S:20-45 duel/down labels): while knocked down, only `duel
stand`/`duel roll` are submittable, and a downed target is easier to
hit -- Roll blunts that bonus, Stand doesn't.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from base_classes import PlayerClass, PlayerRace
from combat.duel import DuelSession, DuelTactic, _submit_tactic
from items import Weapon
from player import Player


class _FakeCtx:
    def __init__(self, player=None):
        self.sent: list = []
        self.player = player
        self.server = None
        self.client = None

    async def send(self, *args):
        self.sent.extend(args)


def _flat(ctx) -> str:
    return '\n'.join(str(x) for x in ctx.sent)


def _make_duelist(name):
    p = Player(name=name, id=name.lower())
    p.char_class = PlayerClass.FIGHTER
    p.char_race = PlayerRace.HUMAN
    p.hit_points = 30
    p.shield = 0
    p.armor = 0
    p.readied_weapon = Weapon(
        id_number=1, name='LONG SWORD', stability=50,
        to_hit=60, weapon_class='bash/slash',
    )
    return p


def _make_session():
    a, b = _make_duelist('Ardent'), _make_duelist('Belwin')
    ctx_a, ctx_b = _FakeCtx(a), _FakeCtx(b)
    session = DuelSession(a, ctx_a, b, ctx_b)
    a.active_duel = session
    b.active_duel = session
    return session, ctx_a, ctx_b


def _controlled_roll(first_call_value: int):
    """random.randint side_effect: the strike-chance roll (the first call
    made inside a _swing()) returns first_call_value; every call after
    that (weapon damage rolls, shield/armor rolls, etc.) returns 1, so it
    never accidentally satisfies a later threshold meant for a different
    roll."""
    state = {'n': 0}
    def side_effect(_lo, _hi):
        state['n'] += 1
        return first_call_value if state['n'] == 1 else 1
    return side_effect


class TestSubmitGating(unittest.IsolatedAsyncioTestCase):
    async def test_downed_side_cannot_submit_attack(self):
        session, ctx_a, ctx_b = _make_session()
        session.a.down = True
        result = await _submit_tactic(ctx_a, DuelTactic.ATTACK)
        self.assertFalse(result.success)
        self.assertIn("You're on the ground!", _flat(ctx_a))
        self.assertIsNone(session.a.tactic)

    async def test_downed_side_can_submit_stand(self):
        session, ctx_a, ctx_b = _make_session()
        session.a.down = True
        result = await _submit_tactic(ctx_a, DuelTactic.STAND)
        self.assertTrue(result.success)
        self.assertEqual(session.a.tactic, DuelTactic.STAND)

    async def test_downed_side_can_submit_roll(self):
        session, ctx_a, ctx_b = _make_session()
        session.a.down = True
        result = await _submit_tactic(ctx_a, DuelTactic.ROLL)
        self.assertTrue(result.success)
        self.assertEqual(session.a.tactic, DuelTactic.ROLL)

    async def test_standing_side_cannot_submit_stand_or_roll(self):
        session, ctx_a, ctx_b = _make_session()
        result = await _submit_tactic(ctx_a, DuelTactic.ROLL)
        self.assertFalse(result.success)
        self.assertIn("You're not down", _flat(ctx_a))


class TestDownResolution(unittest.IsolatedAsyncioTestCase):
    async def test_stand_clears_down_and_skips_the_swing(self):
        session, ctx_a, ctx_b = _make_session()
        session.a.down = True
        session.a.tactic = DuelTactic.STAND
        line = session._resolve_swing(session.a, session.b)
        self.assertFalse(session.a.down)
        self.assertIn('stands back up', line)

    async def test_roll_clears_down_with_its_own_flavor_line(self):
        session, ctx_a, ctx_b = _make_session()
        session.a.down = True
        session.a.tactic = DuelTactic.ROLL
        line = session._resolve_swing(session.a, session.b)
        self.assertFalse(session.a.down)
        self.assertIn('rolls out of danger', line)


class TestDownedBonusUsesSnapshot(unittest.IsolatedAsyncioTestCase):
    """SPUR yx=3/4/13/14: a downed target is easier to hit -- Roll blunts
    the bonus (+5), Stand doesn't (+20). Both must read the pre-round
    snapshot (DuelSession._was_down), not the live .down flag, since the
    downed side's own action already clears the live flag before the
    attacker's swing is evaluated (see module comment in combat/duel.py).
    """
    async def test_full_bonus_against_a_target_that_stood(self):
        session, ctx_a, ctx_b = _make_session()
        session.b.tactic = DuelTactic.STAND
        session._was_down = {id(session.b): True}
        session.b.down = False  # simulates the live flag already cleared
        with patch('combat.duel.random.randint', side_effect=_controlled_roll(65)):
            line = session._swing(session.a, session.b)
        self.assertIn('hits', line)

    async def test_blunted_bonus_against_a_target_that_rolled(self):
        session, ctx_a, ctx_b = _make_session()
        session.b.tactic = DuelTactic.ROLL
        session._was_down = {id(session.b): True}
        session.b.down = False
        with patch('combat.duel.random.randint', side_effect=_controlled_roll(65)):
            line = session._swing(session.a, session.b)
        self.assertIn('misses', line)

    async def test_no_bonus_when_never_down(self):
        session, ctx_a, ctx_b = _make_session()
        session.b.tactic = DuelTactic.ATTACK
        session._was_down = {id(session.b): False}
        with patch('combat.duel.random.randint', side_effect=_controlled_roll(65)):
            line = session._swing(session.a, session.b)
        self.assertIn('misses', line)


if __name__ == '__main__':
    unittest.main()
