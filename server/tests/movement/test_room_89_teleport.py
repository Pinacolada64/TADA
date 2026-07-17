"""tests/test_room_89_teleport.py

Level 1 room 89 ("Teleport Room") is the confirmed cross-level hidden exit
-- SPUR.MISC.S:448 hardcodes it as a teleport, not a same-level +/-1 move
like level 5 room 140:

    if (cl=1) and (cr=89) then a=18:gosub message:cl=5:cr=41:goto travel4

This is data-driven via Room.hidden_exit_east = {"room": 41, "level": 5}
(base_classes.py's Room.hidden_exit()), resolved by Server._move() /
Server._teleport_to() -- no per-room special case in simple_server.py.

Note: SPUR.MAIN.S:174's "if (cl=1) then if (cr=89) goto travel3" is a
catch-all that (in the original) fires for *any* blocked direction out of
the room, not just east. This port intentionally simplifies that to "only
the flagged direction (east) resolves the hidden exit" for data-driven
consistency with every other hidden exit -- other directions just say
"Can't go <dir>." now, matching ordinary room behavior. Message #18's
flavor text (recovered, server/messages.json) is printed by number via
messages.py's send_message(), not embedded in level_1.json; travel4 always
prints "YOU HAVE ENTERED <level name>!" after it.

Run with:
    python -m pytest tests/test_room_89_teleport.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from simple_server import Server
from base_classes import Map, Room


def _make_map() -> Map:
    m = Map()
    room89 = Room(number=89, name='TELEPORT ROOM', desc='',
                  exits={'west': 88},
                  hidden_exit_east={'room': 41, 'level': 5, 'message_number': 18})
    room88 = Room(number=88, name='COOL ROOM', desc='', exits={'east': 89})
    m.levels[1] = {88: room88, 89: room89}
    m.rooms = m.levels[1]

    room41 = Room(number=41, name='The Desert', desc='')
    m.levels[5] = {41: room41}
    return m


def _ctx(room_no=89, level=1, server=None):
    ctx = MagicMock()
    ctx.client.room = room_no
    ctx.client.map_level = level
    ctx.player.map_level = level
    ctx.send = AsyncMock()
    ctx.send_room = AsyncMock()
    # ctx.server.messages defaults to empty rather than an unrelated
    # MagicMock, so send_message() cleanly no-ops unless a real server
    # (with real loaded messages.json data) is passed in.
    ctx.server = server if server is not None else MagicMock(messages={})
    return ctx


class TestRoom89Teleport(unittest.IsolatedAsyncioTestCase):
    async def test_east_from_room_89_teleports_to_level_5_room_41(self):
        server = Server('127.0.0.1', 0)
        server.game_map = _make_map()
        ctx = _ctx()
        await server._move(ctx, 'e')
        self.assertEqual(ctx.client.room, 41)
        self.assertEqual(ctx.player.map_level, 5)

    async def test_room_message_18_sent_before_level_banner(self):
        # Message #18's real text is loaded from server/messages.json (Server's
        # __init__ loads it via _load_game_data() same as any other data file).
        server = Server('127.0.0.1', 0)
        server.game_map = _make_map()
        ctx = _ctx(server=server)
        await server._move(ctx, 'e')
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('incredibly powerful gust of wind', sent)

    async def test_missing_message_number_is_safe(self):
        # If messages.json lookup fails for any reason, the teleport itself
        # must still go through.
        server = Server('127.0.0.1', 0)
        server.messages = {}
        server.game_map = _make_map()
        ctx = _ctx(server=server)
        await server._move(ctx, 'e')
        self.assertEqual(ctx.client.room, 41)

    async def test_teleport_message_sent(self):
        server = Server('127.0.0.1', 0)
        server.game_map = _make_map()
        ctx = _ctx()
        await server._move(ctx, 'e')
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('You have entered Land of the Wraiths!', sent)

    async def test_real_west_exit_takes_priority(self):
        # Room 89's real west exit must still work normally.
        server = Server('127.0.0.1', 0)
        server.game_map = _make_map()
        ctx = _ctx()
        await server._move(ctx, 'w')
        self.assertEqual(ctx.client.room, 88)
        self.assertEqual(ctx.player.map_level, 1)

    async def test_north_from_room_89_just_blocked(self):
        # Unlike the original SPUR catch-all, only the flagged direction
        # (east) resolves the hidden exit in this port -- see module docstring.
        server = Server('127.0.0.1', 0)
        server.game_map = _make_map()
        ctx = _ctx()
        await server._move(ctx, 'n')
        self.assertEqual(ctx.client.room, 89)
        self.assertEqual(ctx.player.map_level, 1)
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn("Can't go", sent)

    async def test_other_rooms_unaffected(self):
        server = Server('127.0.0.1', 0)
        server.game_map = _make_map()
        ctx = _ctx(room_no=88, level=1)
        await server._move(ctx, 'w')
        self.assertEqual(ctx.client.room, 88)  # unchanged, no west exit from 88
        self.assertEqual(ctx.player.map_level, 1)


if __name__ == '__main__':
    unittest.main()
