"""tests/combat/test_duel_guild_support.py — combat/duel.py's
_guild_support() (SPUR.DUEL.S:113-136 "follow"): a room-local headcount
of online guildmates, capped at 5, added flatly to accuracy and damage
for the whole duel.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from base_classes import Guild, PlayerClass, PlayerRace
from combat.duel import DuelSession, DuelTactic, _guild_support
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
    def __init__(self, player, server=None, client=None):
        self.player = player
        self.server = server
        self.client = client
        self.sent: list = []
        if client is not None:
            client.ctx = self

    async def send(self, *args):
        self.sent.extend(args)


def _flat(ctx) -> str:
    return '\n'.join(str(x) for x in ctx.sent)


def _make_duelist(name, *, guild=Guild.CIVILIAN):
    p = Player(name=name, id=name.lower())
    p.char_class = PlayerClass.FIGHTER
    p.char_race = PlayerRace.HUMAN
    p.guild = guild
    p.readied_weapon = Weapon(
        id_number=1, name='LONG SWORD', stability=50,
        to_hit=60, weapon_class='bash/slash',
    )
    return p


def _add_online(server, name, *, guild, room):
    player = _make_duelist(name, guild=guild)
    client = _FakeClient(room=room)
    ctx = _FakeCtx(player, server, client)
    server.clients[name] = client
    return player, ctx


class TestGuildSupportHeadcount(unittest.TestCase):
    def test_no_server_or_room_returns_zero(self):
        player = _make_duelist('Ardent', guild=Guild.CLAW)
        side = _make_side(player, _FakeCtx(player))
        self.assertEqual(_guild_support(side), 0)

    def test_civilian_gets_no_support_even_with_guildmates_in_room(self):
        server = _FakeServer()
        player, ctx = _add_online(server, 'Ardent', guild=Guild.CIVILIAN, room=1)
        _add_online(server, 'Bystander', guild=Guild.CIVILIAN, room=1)
        side = _make_side(player, ctx)
        self.assertEqual(_guild_support(side), 0)

    def test_outlaw_gets_no_support(self):
        server = _FakeServer()
        player, ctx = _add_online(server, 'Ardent', guild=Guild.OUTLAW, room=1)
        _add_online(server, 'Fence', guild=Guild.OUTLAW, room=1)
        side = _make_side(player, ctx)
        self.assertEqual(_guild_support(side), 0)

    def test_counts_only_same_guild_in_same_room(self):
        server = _FakeServer()
        player, ctx = _add_online(server, 'Ardent', guild=Guild.CLAW, room=1)
        _add_online(server, 'Claw1', guild=Guild.CLAW, room=1)
        _add_online(server, 'Claw2', guild=Guild.CLAW, room=1)
        _add_online(server, 'ClawElsewhere', guild=Guild.CLAW, room=2)  # different room
        _add_online(server, 'Rival', guild=Guild.FIST, room=1)          # different guild
        side = _make_side(player, ctx)
        self.assertEqual(_guild_support(side), 2)

    def test_does_not_count_self(self):
        server = _FakeServer()
        player, ctx = _add_online(server, 'Ardent', guild=Guild.SWORD, room=1)
        side = _make_side(player, ctx)
        self.assertEqual(_guild_support(side), 0)

    def test_capped_at_five(self):
        server = _FakeServer()
        player, ctx = _add_online(server, 'Ardent', guild=Guild.FIST, room=1)
        for i in range(7):
            _add_online(server, f'Fist{i}', guild=Guild.FIST, room=1)
        side = _make_side(player, ctx)
        self.assertEqual(_guild_support(side), 5)


def _make_side(player, ctx):
    from combat.duel import _DuelSide
    return _DuelSide(player=player, ctx=ctx)


class TestSupportAppliedInDuel(unittest.IsolatedAsyncioTestCase):
    async def test_support_boosts_accuracy_enough_to_turn_a_miss_into_a_hit(self):
        server = _FakeServer()
        a, ctx_a = _add_online(server, 'Ardent', guild=Guild.CLAW, room=1)
        b, ctx_b = _add_online(server, 'Belwin', guild=Guild.CIVILIAN, room=1)
        for i in range(3):
            _add_online(server, f'Claw{i}', guild=Guild.CLAW, room=1)  # 3 supporters

        session = DuelSession(a, ctx_a, b, ctx_b)
        session.a.support = _guild_support(session.a)
        self.assertEqual(session.a.support, 3)

        # PARRY vs PARRY: _INTERACTION gives -20, so stability 50 -> a 30
        # threshold with no support. Roll 32: without support, 32 > 30 ->
        # miss. With support (+3), threshold becomes 33, 32 <= 33 -> hit.
        session.a.tactic = DuelTactic.PARRY
        session.b.tactic = DuelTactic.PARRY
        with patch('combat.duel.random.randint', return_value=32):
            line = session._swing(session.a, session.b)
        self.assertIn('hits', line)

    async def test_zero_support_leaves_outcome_unchanged(self):
        server = _FakeServer()
        a, ctx_a = _add_online(server, 'Ardent', guild=Guild.CIVILIAN, room=1)
        b, ctx_b = _add_online(server, 'Belwin', guild=Guild.CIVILIAN, room=1)
        session = DuelSession(a, ctx_a, b, ctx_b)
        session.a.support = _guild_support(session.a)
        self.assertEqual(session.a.support, 0)
        session.a.tactic = DuelTactic.PARRY
        session.b.tactic = DuelTactic.PARRY
        with patch('combat.duel.random.randint', return_value=32):
            line = session._swing(session.a, session.b)
        self.assertIn('misses', line)


if __name__ == '__main__':
    unittest.main()
