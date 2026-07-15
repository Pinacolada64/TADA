"""tests/test_leave_combat_on_move.py

Server._move()/_leave_combat_on_move(): a player who moves out of a room
they're fighting in is dropped from that fight's CombatSession.attackers.

Without this, a bystander who joined a fight then walked away stayed in
attackers -- e.g. still getting the "monster is slain!" notice, still
eligible for a stray-round hit -- despite no longer being in the room.
Mainly relevant to bystanders: the fight's leader is normally occupied by
CombatSession._run_loop()'s own prompt for the fight's duration and can't
reach _move() mid-fight.

Run with:
    python -m pytest tests/test_leave_combat_on_move.py -v
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

# See test_wild_horse_placement.py: force a clean reimport regardless of
# what stubbed sys.modules['network_context']/['net_common'] before us.
for _mod in ('network_context', 'net_common', 'simple_server'):
    sys.modules.pop(_mod, None)

from simple_server import Server
from base_classes import Map, Room


def _make_map() -> Map:
    m = Map()
    rooms = {
        1: Room(number=1, name='Start', desc='', exits={'east': 2}),
        2: Room(number=2, name='End', desc='', exits={'west': 1}),
    }
    m.levels[1] = rooms
    m.rooms = rooms
    return m


def _ctx(room_no=1, level=1):
    ctx = MagicMock()
    ctx.client.room = room_no
    ctx.player.map_level = level
    ctx.send = AsyncMock()
    ctx.send_room = AsyncMock()
    return ctx


class _FakeSession:
    def __init__(self, attackers):
        self.attackers = list(attackers)
        self._done = asyncio.Event()

    def _remove_attacker(self, ctx):
        if ctx in self.attackers:
            self.attackers.remove(ctx)


class TestLeaveCombatOnMove(unittest.IsolatedAsyncioTestCase):
    async def test_bystander_removed_from_attackers_on_move(self):
        server = Server('127.0.0.1', 0)
        server.game_map = _make_map()
        leader  = _ctx(room_no=1)
        joiner  = _ctx(room_no=1)
        session = _FakeSession([leader, joiner])
        server.active_combats = {1: session}

        await server._move(joiner, 'e')

        self.assertNotIn(joiner, session.attackers)
        self.assertIn(leader, session.attackers)

    async def test_moving_player_not_in_attackers_is_a_no_op(self):
        server = Server('127.0.0.1', 0)
        server.game_map = _make_map()
        leader   = _ctx(room_no=1)
        onlooker = _ctx(room_no=1)   # in the room, never joined the fight
        session  = _FakeSession([leader])
        server.active_combats = {1: session}

        await server._move(onlooker, 'e')

        self.assertEqual(session.attackers, [leader])

    async def test_finished_combat_session_left_untouched(self):
        server = Server('127.0.0.1', 0)
        server.game_map = _make_map()
        joiner  = _ctx(room_no=1)
        session = _FakeSession([joiner])
        session._done.set()   # fight already over
        server.active_combats = {1: session}

        await server._move(joiner, 'e')

        # Nothing to clean up for a finished fight -- left as-is either way.
        self.assertIn(joiner, session.attackers)

    async def test_no_active_combat_in_room_is_safe(self):
        server = Server('127.0.0.1', 0)
        server.game_map = _make_map()
        server.active_combats = {}
        ctx = _ctx(room_no=1)

        await server._move(ctx, 'e')   # must not raise

        self.assertEqual(ctx.client.room, 2)

    async def test_blocked_move_does_not_remove_attacker(self):
        # No west exit from room 1 -- move fails, attacker list untouched.
        server = Server('127.0.0.1', 0)
        server.game_map = _make_map()
        joiner  = _ctx(room_no=1)
        session = _FakeSession([joiner])
        server.active_combats = {1: session}

        await server._move(joiner, 'w')

        self.assertIn(joiner, session.attackers)


if __name__ == '__main__':
    unittest.main()
