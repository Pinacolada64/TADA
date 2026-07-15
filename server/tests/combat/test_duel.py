"""tests/test_duel.py — live tactic-loop SPORT DUEL tests.

Covers combat/duel.py's DuelSession (pure player-object mutation, no ctx
I/O beyond a fake .send()) and guild_standings.py's tally persistence.
DuelCommand's challenge/accept/tactic UX is exercised indirectly through
DuelSession here; full command-level bot testing is done live (see
session notes), not duplicated as unit tests for this rough draft.
"""
from __future__ import annotations

import asyncio
import unittest
from pathlib import Path
from unittest.mock import patch

from base_classes import PlayerClass, PlayerRace
from combat.duel import (
    DuelSession, DuelTactic, _is_predictable, _offense_rating, _STREAK_LEN,
)
from items import Weapon
from player import Player


class _FakeClient:
    def __init__(self, room):
        self.room = room
        self.ctx = None


class _FakeServer:
    def __init__(self):
        self.clients: dict = {}


class _FakeCtx:
    def __init__(self, server=None, client=None):
        self.sent: list = []
        self.server = server
        self.client = client

    async def send(self, *args):
        self.sent.extend(args)


def _flat(ctx) -> str:
    return '\n'.join(str(x) for x in ctx.sent)


def _make_duelist(name, *, char_class=PlayerClass.FIGHTER, char_race=PlayerRace.HUMAN,
                   hit_points=30, weapon_number=1):
    p = Player(name=name, id=name.lower())
    p.char_class = char_class
    p.char_race = char_race
    p.hit_points = hit_points
    p.shield = 0
    p.armor = 0
    p.readied_weapon = Weapon(
        id_number=weapon_number, name='LONG SWORD', stability=50,
        to_hit=60, weapon_class='bash/slash',
    )
    return p


def _make_session():
    a = _make_duelist('Ardent')
    b = _make_duelist('Belwin')
    session = DuelSession(a, _FakeCtx(), b, _FakeCtx())
    return session, a, b


class TestOffenseRating(unittest.TestCase):
    def test_no_weapon_still_returns_a_rating(self):
        p = _make_duelist('Rulan')
        self.assertGreaterEqual(_offense_rating(p, None), 3)

    def test_rating_is_clamped_3_to_9(self):
        p = _make_duelist('Rulan')
        rating = _offense_rating(p, p.readied_weapon)
        self.assertGreaterEqual(rating, 3)
        self.assertLessEqual(rating, 9)


class TestPredictability(unittest.TestCase):
    def test_not_predictable_below_streak_len(self):
        history = [DuelTactic.ATTACK] * (_STREAK_LEN - 1)
        self.assertFalse(_is_predictable(history, DuelTactic.ATTACK))

    def test_predictable_at_streak_len(self):
        history = [DuelTactic.ATTACK] * _STREAK_LEN
        self.assertTrue(_is_predictable(history, DuelTactic.ATTACK))

    def test_mixed_history_not_predictable(self):
        history = [DuelTactic.ATTACK, DuelTactic.PARRY, DuelTactic.ATTACK]
        self.assertFalse(_is_predictable(history, DuelTactic.ATTACK))


class TestDuelSessionSubmit(unittest.IsolatedAsyncioTestCase):
    async def test_first_submission_waits_for_opponent(self):
        session, a, b = _make_session()
        await session.submit(a, DuelTactic.ATTACK)
        self.assertEqual(a.hit_points, 30)
        self.assertEqual(b.hit_points, 30)
        self.assertIn('Waiting for Belwin', ' '.join(str(x) for x in session.a.ctx.sent))

    async def test_second_submission_resolves_round(self):
        session, a, b = _make_session()
        await session.submit(a, DuelTactic.ATTACK)
        await session.submit(b, DuelTactic.PARRY)
        # Round resolved: both tactics cleared, round advanced.
        self.assertIsNone(session.a.tactic)
        self.assertIsNone(session.b.tactic)
        self.assertEqual(session.round_num, 2 if not session.done else session.round_num)

    async def test_duel_ends_when_someone_dies(self):
        session, a, b = _make_session()
        b.hit_points = 1
        # Force a guaranteed hit by stacking dice heavily via repeated rounds.
        for _ in range(50):
            if session.done:
                break
            await session.submit(a, DuelTactic.ATTACK)
            await session.submit(b, DuelTactic.PARRY)
        self.assertTrue(session.done)

    async def test_active_duel_cleared_on_both_players_when_done(self):
        session, a, b = _make_session()
        a.active_duel = session
        b.active_duel = session
        b.hit_points = 1
        for _ in range(50):
            if session.done:
                break
            await session.submit(a, DuelTactic.ATTACK)
            await session.submit(b, DuelTactic.PARRY)
        self.assertIsNone(a.active_duel)
        self.assertIsNone(b.active_duel)

    async def test_loser_left_at_min_hp_not_dead(self):
        session, a, b = _make_session()
        a.hit_points = 100
        b.hit_points = 1
        for _ in range(50):
            if session.done:
                break
            await session.submit(a, DuelTactic.ATTACK)
            await session.submit(b, DuelTactic.PARRY)
        self.assertTrue(session.done)
        loser = a if a.hit_points <= 0 or a.hit_points == 15 else b
        # Whichever side actually lost should be sitting at exactly 15 HP.
        self.assertIn(15, (a.hit_points, b.hit_points))


class TestBystanderBroadcast(unittest.IsolatedAsyncioTestCase):
    """DuelSession._broadcast_bystanders() -- terse room-wide updates for
    players watching a duel who aren't in it (Ryan: "what about
    broadcasting this to bystanders in the room through ctx.send_room()")."""

    def _build(self):
        server = _FakeServer()
        a = _make_duelist('Ardent')
        b = _make_duelist('Belwin')
        client_a = _FakeClient(room=1)
        client_b = _FakeClient(room=1)
        client_bystander = _FakeClient(room=1)
        ctx_a = _FakeCtx(server=server, client=client_a)
        ctx_b = _FakeCtx(server=server, client=client_b)
        ctx_bystander = _FakeCtx(server=server, client=client_bystander)
        client_a.ctx = ctx_a
        client_b.ctx = ctx_b
        client_bystander.ctx = ctx_bystander
        server.clients = {'a': client_a, 'b': client_b, 'c': client_bystander}
        session = DuelSession(a, ctx_a, b, ctx_b)
        return session, ctx_a, ctx_b, ctx_bystander

    async def test_bystander_in_room_receives_terse_note(self):
        session, _ctx_a, _ctx_b, ctx_bystander = self._build()
        await session._broadcast_bystanders('Ardent and Belwin begin a duel!')
        self.assertIn('Ardent and Belwin begin a duel!', _flat(ctx_bystander))

    async def test_duelists_are_excluded_from_their_own_broadcast(self):
        session, ctx_a, ctx_b, _ctx_bystander = self._build()
        await session._broadcast_bystanders('Ardent and Belwin begin a duel!')
        self.assertEqual(ctx_a.sent, [])
        self.assertEqual(ctx_b.sent, [])

    async def test_bystander_in_a_different_room_is_not_notified(self):
        session, _ctx_a, _ctx_b, ctx_bystander = self._build()
        ctx_bystander.client.room = 99
        await session._broadcast_bystanders('Ardent and Belwin begin a duel!')
        self.assertEqual(ctx_bystander.sent, [])

    async def test_round_resolution_broadcasts_a_terse_note(self):
        session, _ctx_a, _ctx_b, ctx_bystander = self._build()
        await session.submit(session.a.player, DuelTactic.ATTACK)
        await session.submit(session.b.player, DuelTactic.PARRY)
        # Terse note present, but not the full "--- Round N ---" detail.
        self.assertTrue(len(ctx_bystander.sent) > 0)
        self.assertNotIn('--- Round', _flat(ctx_bystander))


class TestGuildStandings(unittest.TestCase):
    def setUp(self):
        import guild_standings
        self._orig_file = guild_standings._STANDINGS_FILE
        guild_standings._STANDINGS_FILE = Path('run') / 'server' / 'test_guild_standings.json'
        if guild_standings._STANDINGS_FILE.exists():
            guild_standings._STANDINGS_FILE.unlink()

    def tearDown(self):
        import guild_standings
        if guild_standings._STANDINGS_FILE.exists():
            guild_standings._STANDINGS_FILE.unlink()
        guild_standings._STANDINGS_FILE = self._orig_file

    def test_record_duel_result_increments_both_sides(self):
        from guild_standings import load_standings, record_duel_result
        record_duel_result('Mark of the Claw', 'Iron Fist')
        standings = load_standings()
        self.assertEqual(standings['Mark of the Claw']['wins'], 1)
        self.assertEqual(standings['Iron Fist']['losses'], 1)

    def test_repeated_results_accumulate(self):
        from guild_standings import load_standings, record_duel_result
        record_duel_result('Mark of the Claw', 'Iron Fist')
        record_duel_result('Mark of the Claw', 'Iron Fist')
        standings = load_standings()
        self.assertEqual(standings['Mark of the Claw']['wins'], 2)
        self.assertEqual(standings['Iron Fist']['losses'], 2)


if __name__ == '__main__':
    unittest.main()
