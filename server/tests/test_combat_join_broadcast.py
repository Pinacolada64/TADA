"""tests/test_combat_join_broadcast.py

CombatSession.join(): when a bystander joins a fight already underway,
the room should be told who's joining whom against what monster --
"<participant> joins <originator> in fighting the <monster>!" -- not just
a silent addition to session.attackers.
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from combat.engine import CombatSession


class _FakePlayer:
    def __init__(self, name):
        self.name = name
        self.hit_points = 30
        self.unsaved_changes = False
        self.stats = {}
        self.shield = 0
        self.armor = 0
        self.ammo_rounds = 0


class _FakeClient:
    room = 1


class _FakeCtx:
    def __init__(self, player):
        self.player = player
        self.client = _FakeClient()
        self.server = MagicMock()
        self._sent: list[str] = []
        self._room_sent: list[tuple] = []

    async def send(self, msg, **kwargs):
        self._sent.append(str(msg))

    async def send_room(self, msg, **kwargs):
        self._room_sent.append((msg, kwargs))


def _no_op_swing_result():
    result = MagicMock()
    result.damage = 0
    result.ammo_used = False
    result.hit = False
    result.weapon_id = None
    return result


class TestCombatJoinBroadcast(unittest.IsolatedAsyncioTestCase):
    async def test_joiner_announced_against_leader_and_monster(self):
        leader_ctx = _FakeCtx(_FakePlayer('Railbender'))
        joiner_ctx = _FakeCtx(_FakePlayer('Rulan'))

        session = CombatSession({'name': 'TROLL', 'strength': 0, 'flags': {}}, room_no=1)
        session.leader = leader_ctx
        session.attackers = [leader_ctx]

        with patch.object(session, '_swing', return_value=_no_op_swing_result()), \
             patch('combat.engine._add_exp', new=AsyncMock()), \
             patch.object(session, '_narrate_player_swing', new=AsyncMock()), \
             patch.object(session, '_monster_dies', new=AsyncMock()):
            await session.join(joiner_ctx)

        self.assertEqual(len(joiner_ctx._room_sent), 1)
        msg, kwargs = joiner_ctx._room_sent[0]
        self.assertEqual(msg, 'Rulan joins Railbender in fighting the TROLL!')
        self.assertTrue(kwargs.get('exclude_self'))

    async def test_leader_joining_their_own_fight_is_not_announced(self):
        # start() calls _join_attacker() directly, never join() -- but guard
        # against the degenerate case defensively (leader is ctx).
        leader_ctx = _FakeCtx(_FakePlayer('Railbender'))
        session = CombatSession({'name': 'TROLL', 'strength': 0, 'flags': {}}, room_no=1)
        session.leader = leader_ctx
        session.attackers = [leader_ctx]

        with patch.object(session, '_swing', return_value=_no_op_swing_result()), \
             patch('combat.engine._add_exp', new=AsyncMock()), \
             patch.object(session, '_narrate_player_swing', new=AsyncMock()), \
             patch.object(session, '_monster_dies', new=AsyncMock()):
            await session.join(leader_ctx)

        self.assertEqual(leader_ctx._room_sent, [])

    async def test_no_broadcast_when_no_leader_set(self):
        joiner_ctx = _FakeCtx(_FakePlayer('Rulan'))
        session = CombatSession({'name': 'TROLL', 'strength': 0, 'flags': {}}, room_no=1)
        session.leader = None
        session.attackers = []

        with patch.object(session, '_swing', return_value=_no_op_swing_result()), \
             patch('combat.engine._add_exp', new=AsyncMock()), \
             patch.object(session, '_narrate_player_swing', new=AsyncMock()), \
             patch.object(session, '_monster_dies', new=AsyncMock()):
            await session.join(joiner_ctx)

        self.assertEqual(joiner_ctx._room_sent, [])

    async def test_already_dead_monster_sends_no_broadcast(self):
        leader_ctx = _FakeCtx(_FakePlayer('Railbender'))
        joiner_ctx = _FakeCtx(_FakePlayer('Rulan'))
        session = CombatSession({'name': 'TROLL', 'strength': 0, 'flags': {}}, room_no=1)
        session.leader = leader_ctx
        session._done.set()

        await session.join(joiner_ctx)

        self.assertEqual(joiner_ctx._room_sent, [])
        self.assertIn('That monster is already dead.', joiner_ctx._sent)


if __name__ == '__main__':
    unittest.main()
