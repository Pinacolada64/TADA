"""tests/combat/test_duel_verbose.py — combat/duel.py's `duel verbose`
(SPUR.DUEL.S:47-49 "verbose", zq): a per-side toggle that doesn't
consume a turn, adding a modifier-breakdown commentary line to that
side's own view of each swing/bash.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from base_classes import PlayerClass, PlayerRace
from combat.duel import DuelSession, DuelTactic, _toggle_verbose
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


class TestToggle(unittest.IsolatedAsyncioTestCase):
    async def test_not_in_a_duel(self):
        ctx = _FakeCtx(_make_duelist('Loner'))
        result = await _toggle_verbose(ctx)
        self.assertFalse(result.success)
        self.assertIn("You're not in a duel.", _flat(ctx))

    async def test_toggles_on_then_off_without_consuming_a_turn(self):
        session, ctx_a, ctx_b = _make_session()

        result = await _toggle_verbose(ctx_a)
        self.assertTrue(result.success)
        self.assertTrue(session.a.verbose)
        self.assertIn('Duel commentary - ON', _flat(ctx_a))
        self.assertIsNone(session.a.tactic)   # didn't submit a tactic

        result = await _toggle_verbose(ctx_a)
        self.assertFalse(session.a.verbose)
        self.assertIn('Duel commentary - OFF', _flat(ctx_a))

    async def test_each_side_has_an_independent_flag(self):
        session, ctx_a, ctx_b = _make_session()
        await _toggle_verbose(ctx_a)
        self.assertTrue(session.a.verbose)
        self.assertFalse(session.b.verbose)


class TestCommentaryDelivery(unittest.IsolatedAsyncioTestCase):
    async def test_verbose_side_sees_commentary_non_verbose_side_does_not(self):
        session, ctx_a, ctx_b = _make_session()
        session.a.verbose = True

        with patch('combat.duel.random.randint', return_value=1):
            await session.submit(session.a.player, DuelTactic.ATTACK)
            await session.submit(session.b.player, DuelTactic.PARRY)

        self.assertIn('[commentary]', _flat(ctx_a))
        self.assertNotIn('[commentary]', _flat(ctx_b))

    async def test_no_one_verbose_means_no_commentary_sent(self):
        session, ctx_a, ctx_b = _make_session()

        with patch('combat.duel.random.randint', return_value=1):
            await session.submit(session.a.player, DuelTactic.ATTACK)
            await session.submit(session.b.player, DuelTactic.PARRY)

        self.assertNotIn('[commentary]', _flat(ctx_a))
        self.assertNotIn('[commentary]', _flat(ctx_b))


if __name__ == '__main__':
    unittest.main()
