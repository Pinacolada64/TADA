"""tests/test_debug_room_flags_display.py

Unit tests for the debug-mode room-flags line in
simple_server.py's _describe_room(): when player.is_debug is truthy,
non-empty room.flags are appended as a "[DEBUG] Room flags: ..." line
right after the "Ye may travel" exits line. Not shown to non-debug
players, and omitted entirely for flagless rooms.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

# See test_wild_horse_placement.py: force a clean reimport regardless of
# what stubbed sys.modules['network_context']/['net_common'] before us.
for _mod in ('network_context', 'net_common', 'simple_server'):
    sys.modules.pop(_mod, None)

from simple_server import Server
from base_classes import Map, Room


def _make_map(*, flags=None) -> Map:
    m = Map()
    room = Room(number=89, name='TELEPORT ROOM', desc='A humming room.',
                exits={'west': 88}, flags=flags or [])
    m.levels[1] = {89: room}
    m.rooms = m.levels[1]
    return m


@pytest.fixture
def server():
    return Server('127.0.0.1', 0)


def _client(*, is_debug):
    client = MagicMock()
    client.room = 89
    client.ctx.player.map_level = 1
    client.ctx.player.is_debug = is_debug
    return client


class TestDebugRoomFlagsDisplay:
    def test_debug_player_sees_room_flags(self, server):
        server.game_map = _make_map(flags=['hidden_exit_east'])
        client = _client(is_debug=True)
        lines = server._describe_room(client)
        assert '[DEBUG] Room flags: hidden_exit_east' in lines

    def test_non_debug_player_does_not_see_room_flags(self, server):
        server.game_map = _make_map(flags=['hidden_exit_east'])
        client = _client(is_debug=False)
        lines = server._describe_room(client)
        assert not any('[DEBUG]' in line for line in lines)

    def test_debug_player_no_flags_no_debug_line(self, server):
        server.game_map = _make_map(flags=[])
        client = _client(is_debug=True)
        lines = server._describe_room(client)
        assert not any('[DEBUG]' in line for line in lines)

    def test_debug_line_lists_multiple_flags(self, server):
        server.game_map = _make_map(flags=['hidden_exit_east', 'no_monster'])
        client = _client(is_debug=True)
        lines = server._describe_room(client)
        assert '[DEBUG] Room flags: hidden_exit_east, no_monster' in lines
