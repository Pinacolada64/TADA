"""tests/test_hidden_exits.py

Unit tests for hidden exits (SPUR.MISC.S:419 "->"/"<-" markers):
Server._hidden_exit_target() / Server._move().

The "->"/"<-" marker in a room's raw name only sets a boolean "exit
exists" flag in the original source -- it never stores a target room
number. The actual destination follows the same room_number +/-1
adjacency ordinary same-row exits already use in the converted data,
confirmed against level 5 room 140 "Village" -> 141 "The Chief's Treasure
Room" (Headhunter's Island's quest reward).

Level 1 room 89 "Teleport Room" also carries the hidden_exit_east flag but
is NOT a +/-1 case -- SPUR.MISC.S:448 hardcodes it as a cross-level
teleport to level 5 room 41. See tests/test_room_89_teleport.py.

Coverage:
  - moving into the flagged direction resolves to room_number +/-1
  - the flag alone doesn't help if the +/-1 room doesn't exist (level 1
    has real numbering gaps)
  - a room with no hidden-exit flag still just says "Can't go <dir>"
  - moving the *other* direction (flag present for east, tried west)
    doesn't trigger the fallback
  - normal (non-hidden) exits still take priority and are unaffected

Run with:
    python -m pytest tests/test_hidden_exits.py -v
"""
from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# See test_wild_horse_placement.py: force a clean reimport regardless of
# what stubbed sys.modules['network_context']/['net_common'] before us.
for _mod in ('network_context', 'net_common', 'simple_server'):
    sys.modules.pop(_mod, None)

from simple_server import Server
from base_classes import Map, Room


def _make_map(*, gap: bool = False) -> Map:
    """A tiny 3-room level: 10 (hidden east) -> 11 -> 12 (hidden west).

    With gap=True, room 11 is omitted entirely, so room 10's hidden east
    exit (10+1=11) points at a room that doesn't exist.
    """
    m = Map()
    rooms = {
        10: Room(number=10, name='Start', desc='', flags=['hidden_exit_east']),
        12: Room(number=12, name='End', desc='', flags=['hidden_exit_west'],
                 exits={'west': 11}),
    }
    if not gap:
        rooms[11] = Room(number=11, name='Middle', desc='', exits={'east': 12})
    m.levels[1] = rooms
    m.rooms = rooms
    return m


@pytest.fixture
def server():
    return Server('127.0.0.1', 0)


def _ctx(room_no, level=1):
    ctx = MagicMock()
    ctx.client.room = room_no
    ctx.player.map_level = level
    ctx.send = AsyncMock()
    ctx.send_room = AsyncMock()
    return ctx


class TestHiddenExitTarget:
    def test_resolves_east_to_room_plus_one(self, server):
        server.game_map = _make_map()
        room = server.game_map.get_room(1, 10)
        target = server._hidden_exit_target(room, 'e', 1)
        assert target == 11

    def test_resolves_west_to_room_minus_one(self, server):
        server.game_map = _make_map()
        room = server.game_map.get_room(1, 12)
        target = server._hidden_exit_target(room, 'w', 1)
        assert target == 11

    def test_no_flag_no_target(self, server):
        server.game_map = _make_map()
        room = server.game_map.get_room(1, 11)  # "Middle" has no hidden-exit flag
        assert server._hidden_exit_target(room, 'e', 1) is None
        assert server._hidden_exit_target(room, 'w', 1) is None

    def test_wrong_direction_for_the_flag_no_target(self, server):
        server.game_map = _make_map()
        room = server.game_map.get_room(1, 10)  # flagged east only
        assert server._hidden_exit_target(room, 'w', 1) is None

    def test_gap_in_numbering_blocks_the_move(self, server):
        server.game_map = _make_map(gap=True)
        room = server.game_map.get_room(1, 10)
        assert server._hidden_exit_target(room, 'e', 1) is None


import unittest


class TestConfirmedHiddenExitTakesPriority(unittest.IsolatedAsyncioTestCase):
    """A confirmed Room.hidden_exit_east/west field wins over the +/-1 guess."""

    async def test_confirmed_destination_used_instead_of_guess(self):
        # Room 10's +/-1 guess would be room 11 (adjacent), but a confirmed
        # field says the real destination is room 50 -- confirmed data wins.
        server = Server('127.0.0.1', 0)
        m = Map()
        rooms = {
            10: Room(number=10, name='Start', desc='',
                     hidden_exit_east=50),
            11: Room(number=11, name='Middle', desc=''),
            50: Room(number=50, name='Real Destination', desc=''),
        }
        m.levels[1] = rooms
        m.rooms = rooms
        server.game_map = m
        ctx = MagicMock()
        ctx.client.room = 10
        ctx.player.map_level = 1
        ctx.send = AsyncMock()
        ctx.send_room = AsyncMock()
        await server._move(ctx, 'e')
        self.assertEqual(ctx.client.room, 50)


class TestMoveThroughHiddenExit(unittest.IsolatedAsyncioTestCase):
    async def test_move_east_through_hidden_exit(self):
        server = Server('127.0.0.1', 0)
        server.game_map = _make_map()
        ctx = _ctx(10)
        await server._move(ctx, 'e')
        self.assertEqual(ctx.client.room, 11)

    async def test_move_blocked_when_target_room_missing(self):
        server = Server('127.0.0.1', 0)
        server.game_map = _make_map(gap=True)
        ctx = _ctx(10)
        await server._move(ctx, 'e')
        self.assertEqual(ctx.client.room, 10)  # unchanged

    async def test_normal_exit_takes_priority_over_hidden_flag(self):
        # Room 12 is flagged hidden_exit_west but also has a real west exit
        # in its exits dict -- the real exit should win, not the fallback.
        server = Server('127.0.0.1', 0)
        server.game_map = _make_map()
        ctx = _ctx(12)
        await server._move(ctx, 'w')
        self.assertEqual(ctx.client.room, 11)

    async def test_unflagged_room_says_cant_go(self):
        server = Server('127.0.0.1', 0)
        server.game_map = _make_map()
        ctx = _ctx(11)
        await server._move(ctx, 'w')
        self.assertEqual(ctx.client.room, 11)  # unchanged
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn("Can't go", sent)


if __name__ == '__main__':
    unittest.main()
