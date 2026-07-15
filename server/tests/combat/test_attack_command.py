"""tests/test_attack_command.py

AttackCommand.execute(): joining/continuing an existing fight.

Regression coverage for a real bug: an already-joined bystander re-typing
'attack' to take their next swing was blocked with "You're already in this
fight!" instead of swinging again. CombatSession.join() gives a bystander
exactly one swing per call ("Bystanders fire one swing then wait; the
leader's loop drives the fight." -- combat/engine.py), so re-typing
'attack' each round is how a bystander keeps fighting, not an error.
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from commands.attack import AttackCommand


class _FakeSession:
    def __init__(self, monster_name='TROLL'):
        self.monster = {'name': monster_name}
        self.attackers = []
        self._done = asyncio.Event()
        self.join = AsyncMock(side_effect=self._join)

    async def _join(self, ctx):
        if ctx not in self.attackers:
            self.attackers.append(ctx)


def _make_ctx(session=None, room_no=1, hit_points=30):
    player = MagicMock()
    player.hit_points = hit_points

    server = MagicMock()
    server.active_combats = {room_no: session} if session else {}

    client = MagicMock()
    client.room = room_no

    ctx = MagicMock()
    ctx.player = player
    ctx.server = server
    ctx.client = client
    ctx.send = AsyncMock()
    return ctx


class TestAttackJoinsExistingFight(unittest.IsolatedAsyncioTestCase):
    async def test_bystander_first_attack_joins(self):
        session = _FakeSession()
        ctx = _make_ctx(session=session)
        cmd = AttackCommand()
        res = await cmd.execute(ctx)
        self.assertTrue(res.success)
        session.join.assert_awaited_once_with(ctx)

    async def test_already_joined_bystander_swings_again_not_blocked(self):
        session = _FakeSession()
        ctx = _make_ctx(session=session)
        cmd = AttackCommand()

        await cmd.execute(ctx)   # first swing, joins
        await cmd.execute(ctx)   # second swing, already in attackers

        self.assertEqual(session.join.await_count, 2)
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertNotIn("already in this fight", sent.lower())

    async def test_dead_player_cannot_attack(self):
        session = _FakeSession()
        ctx = _make_ctx(session=session, hit_points=-1)
        cmd = AttackCommand()
        res = await cmd.execute(ctx)
        self.assertFalse(res.success)
        session.join.assert_not_awaited()

    async def test_name_mismatch_rejected_even_when_already_joined(self):
        session = _FakeSession(monster_name='TROLL')
        ctx = _make_ctx(session=session)
        cmd = AttackCommand()

        await cmd.execute(ctx)                    # joins fighting the troll
        res = await cmd.execute(ctx, 'goblin')     # wrong name this time

        self.assertFalse(res.success)
        self.assertEqual(session.join.await_count, 1)  # not called a 2nd time


if __name__ == '__main__':
    unittest.main()
