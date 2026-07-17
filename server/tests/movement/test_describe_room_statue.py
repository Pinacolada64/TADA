"""tests/movement/test_describe_room_statue.py

simple_server.py's _describe_room() shows "There is a statue of <victim>
here!" when statues.py's get_statue() finds a record for the room --
set by combat/engine.py's _player_petrified() when a player is turned
to stone. Room-description half of the SPUR wy$ room flag; the matching
GET-blocking half is commands/get.py's is_statue check
(tests/commands/test_get_statue.py).
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

for _mod in ('network_context', 'net_common', 'simple_server'):
    sys.modules.pop(_mod, None)

from simple_server import Server
from base_classes import Map, Room
from player import Player
import statues


def _make_map() -> Map:
    m = Map()
    room = Room(number=1, name='CRYPT', desc='A dusty crypt.', exits={})
    m.levels[1] = {1: room}
    m.rooms = m.levels[1]
    return m


def _client(player) -> MagicMock:
    client = MagicMock()
    client.room = 1
    client.ctx.player = player
    return client


@pytest.fixture
def server():
    return Server('127.0.0.1', 0)


@pytest.fixture(autouse=True)
def isolated_statues_file(monkeypatch):
    tmpdir = tempfile.mkdtemp(prefix='tada-describe-statue-test-')
    monkeypatch.setattr(statues, 'ROOM_STATUES_FILE', Path(tmpdir) / 'room_statues.json')
    yield


class TestDescribeRoomStatue:
    def test_shows_statue_line_when_present(self, server):
        statues.add_statue(1, 1, 'MEDUSA', 'Alice')
        server.game_map = _make_map()
        player = Player(name='Rulan')
        lines = server._describe_room(_client(player))
        assert 'There is a statue of Alice here!' in lines

    def test_no_statue_line_when_absent(self, server):
        server.game_map = _make_map()
        player = Player(name='Rulan')
        lines = server._describe_room(_client(player))
        assert not any('statue' in l.lower() for l in lines)

    def test_wrong_room_no_statue_line(self, server):
        statues.add_statue(1, 999, 'MEDUSA', 'Alice')
        server.game_map = _make_map()
        player = Player(name='Rulan')
        lines = server._describe_room(_client(player))
        assert not any('statue' in l.lower() for l in lines)

    def test_wrong_level_no_statue_line(self, server):
        statues.add_statue(2, 1, 'MEDUSA', 'Alice')
        server.game_map = _make_map()
        player = Player(name='Rulan')
        lines = server._describe_room(_client(player))
        assert not any('statue' in l.lower() for l in lines)
