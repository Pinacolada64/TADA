"""tests/test_rc_rt_movement.py

Regression test for a real live bug (level 1 room 20, "VOLCANO ROOM"):
rc/rt exits with a real destination room (rt > 0 -- a labyrinth ladder,
pit, etc.) were unconditionally routed into the shoppe by
commands/movement.py, exactly the same as rt==0 (the actual shoppe
elevator). Room.exits_txt() displayed "Down to #23" correctly (see
tests/test_rc_rt.py), but the movement resolution itself
(commands/movement.py's MoveCommand, simple_server.py's Server._move())
never consulted rt at all -- only rc -- so every rc/rt room in every
level's data with a nonzero rt silently went to the shoppe instead of
its real destination.

Run with:
    python -m pytest tests/test_rc_rt_movement.py -v
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# See test_wild_horse_placement.py: force a clean reimport regardless of
# what stubbed sys.modules['network_context']/['net_common'] before us.
for _mod in ('network_context', 'net_common', 'simple_server'):
    sys.modules.pop(_mod, None)

from simple_server import Server
from base_classes import Map, Room
from commands.movement import MoveCommand


def _make_map() -> Map:
    m = Map()
    rooms = {
        # Real shoppe elevator: rc=2, no rt (rt defaults to 0).
        1:  Room(number=1,  name='Merchant Lobby', desc='', exits={'south': 13, 'rc': 2}),
        # A real down staircase with a destination room (level 1 room 20 -> 23).
        20: Room(number=20, name='Volcano Room', desc='',
                 exits={'north': 8, 'east': 21, 'south': 32, 'rc': 2, 'rt': 23}),
        23: Room(number=23, name='Labyrinth', desc='', exits={}),
    }
    m.levels[1] = rooms
    m.rooms = rooms
    return m


def _ctx(room_no=20, level=1):
    ctx = MagicMock()
    ctx.client.room = room_no
    ctx.player.map_level = level
    ctx.player.map_room = room_no
    ctx.player.unsaved_changes = False
    ctx.send = AsyncMock()
    ctx.send_room = AsyncMock()
    ctx.prompt = AsyncMock(return_value=None)
    return ctx


class TestServerMoveConsultsRcRt(unittest.IsolatedAsyncioTestCase):
    """Server._move() -- the low-level move resolver."""

    async def test_down_with_nonzero_rt_moves_to_that_room(self):
        server = Server('127.0.0.1', 0, 0)
        server.game_map = _make_map()
        ctx = _ctx(room_no=20)

        with patch.object(Server, '_show_room', new=AsyncMock()):
            await server._move(ctx, 'd')

        self.assertEqual(ctx.client.room, 23)
        self.assertEqual(ctx.player.map_room, 23)

    async def test_up_with_nonzero_rt_moves_to_that_room(self):
        server = Server('127.0.0.1', 0, 0)
        game_map = _make_map()
        game_map.levels[1][30] = Room(number=30, name='Up Room', desc='',
                                       exits={'rc': 1, 'rt': 20})
        server.game_map = game_map
        ctx = _ctx(room_no=30)

        with patch.object(Server, '_show_room', new=AsyncMock()):
            await server._move(ctx, 'u')

        self.assertEqual(ctx.client.room, 20)

    async def test_shoppe_room_with_zero_rt_is_not_moved_by_move(self):
        """rt==0 (the shoppe) is intercepted in MoveCommand before _move()
        is ever called -- _move() itself has nothing to resolve it to, so
        it should report no exit rather than silently doing something else."""
        server = Server('127.0.0.1', 0, 0)
        server.game_map = _make_map()
        ctx = _ctx(room_no=1)

        await server._move(ctx, 'd')

        self.assertEqual(ctx.client.room, 1)   # unchanged -- no real exit
        ctx.send.assert_awaited()


class TestMoveCommandRcRt(unittest.IsolatedAsyncioTestCase):
    """MoveCommand.execute() -- only rt==0 goes to the shoppe; a nonzero
    rt must fall through to a real move instead."""

    def _make_move_ctx(self, room_no, level=1):
        ctx = MagicMock()
        ctx.client.room = room_no
        ctx.player.map_level = level
        ctx.player.map_room = room_no
        ctx.player.query_flag = MagicMock(return_value=False)
        ctx.send = AsyncMock()
        ctx.send_room = AsyncMock()
        ctx.server.game_map = _make_map()
        ctx.server._move = AsyncMock()
        return ctx

    async def test_rt_zero_enters_shoppe_not_move(self):
        ctx = self._make_move_ctx(room_no=1)
        with patch('commands.movement._enter_shoppe', new=AsyncMock()) as mock_shoppe:
            await MoveCommand().execute(ctx, 'd')
        mock_shoppe.assert_awaited_once()
        ctx.server._move.assert_not_awaited()

    async def test_rt_nonzero_does_not_enter_shoppe(self):
        ctx = self._make_move_ctx(room_no=20)
        with patch('commands.movement._enter_shoppe', new=AsyncMock()) as mock_shoppe:
            await MoveCommand().execute(ctx, 'd')
        mock_shoppe.assert_not_awaited()
        ctx.server._move.assert_awaited_once_with(ctx, 'd')


class TestBlockedMoveIntoMissingRoom(unittest.IsolatedAsyncioTestCase):
    """Server._move() must refuse to move the player into a room number
    with no actual data (e.g. level 3 rooms 39/86's rc/rt targets -- see
    MECHANICS.md's "Flee / Travel" section) instead of leaving them
    stranded on a "You are nowhere" room, and should log it so a real
    broken exit is diagnosable rather than silently swallowed."""

    def _make_map_with_dangling_exit(self) -> Map:
        m = Map()
        rooms = {
            39: Room(number=39, name='Labyrinth', desc='',
                     exits={'north': 1, 'rc': 1, 'rt': 100}),   # 100 doesn't exist
        }
        m.levels[3] = rooms
        m.rooms = rooms
        return m

    async def test_move_is_blocked_and_room_unchanged(self):
        from simple_server import _BLOCKED_ROOM_MESSAGES

        server = Server('127.0.0.1', 0, 0)
        server.game_map = self._make_map_with_dangling_exit()
        ctx = _ctx(room_no=39, level=3)

        await server._move(ctx, 'u')

        self.assertEqual(ctx.client.room, 39)   # unchanged
        ctx.send.assert_awaited_once()
        sent_message = ctx.send.await_args.args[0]
        self.assertIn(sent_message, _BLOCKED_ROOM_MESSAGES)

    async def test_logs_a_warning(self):
        server = Server('127.0.0.1', 0, 0)
        server.game_map = self._make_map_with_dangling_exit()
        ctx = _ctx(room_no=39, level=3)

        with self.assertLogs('root', level='WARNING') as cm:
            await server._move(ctx, 'u')

        self.assertTrue(any('no data' in msg for msg in cm.output))

    async def test_does_not_call_show_room(self):
        server = Server('127.0.0.1', 0, 0)
        server.game_map = self._make_map_with_dangling_exit()
        ctx = _ctx(room_no=39, level=3)

        with patch.object(Server, '_show_room', new=AsyncMock()) as mock_show:
            await server._move(ctx, 'u')

        mock_show.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
