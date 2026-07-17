"""tests/movement/test_describe_room_statue.py

simple_server.py's _describe_room() shows "There is a statue of <victim>
here!" wherever a 'petrify'-flagged monster is present (alive or dead,
not charmed away) and has petrified at least one player before --
SPUR.MAIN.S's `statue` subroutine, which reads just the first line of
that monster's own memorial file (combat.engine.first_statue_victim()).
Room-description half; the matching GET-blocking half is
commands/get.py's is_statue check (tests/commands/test_get_statue.py).
"""
from __future__ import annotations

import sys
import tempfile
from unittest.mock import MagicMock

import pytest

for _mod in ('network_context', 'net_common', 'simple_server'):
    sys.modules.pop(_mod, None)

from simple_server import Server
from base_classes import Map, Room
from combat.engine import _record_statue
from player import Player

_MEDUSA = {'number': 99, 'name': 'MEDUSA', 'flags': {'petrify': True}}


def _make_map(monster_number: int = 0) -> Map:
    m = Map()
    room = Room(number=1, name='CRYPT', desc='A dusty crypt.', exits={},
               monster=monster_number)
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
    s = Server('127.0.0.1', 0)
    s.monsters = [_MEDUSA]
    return s


@pytest.fixture(autouse=True)
def isolated_memorial_file(monkeypatch):
    import net_common
    tmpdir = tempfile.mkdtemp(prefix='tada-describe-statue-test-')
    monkeypatch.setattr(net_common, 'run_server_dir', tmpdir)
    yield


class TestDescribeRoomStatue:
    def test_shows_statue_line_when_monster_has_a_victim(self, server):
        _record_statue('MEDUSA', 'Alice')
        server.game_map = _make_map(monster_number=_MEDUSA['number'])
        player = Player(name='Rulan')
        lines = server._describe_room(_client(player))
        assert 'There is a statue of Alice here!' in lines

    def test_no_statue_line_when_monster_has_no_victims_yet(self, server):
        server.game_map = _make_map(monster_number=_MEDUSA['number'])
        player = Player(name='Rulan')
        lines = server._describe_room(_client(player))
        assert not any('statue' in l.lower() for l in lines)

    def test_no_statue_line_when_no_monster_in_room(self, server):
        _record_statue('MEDUSA', 'Alice')
        server.game_map = _make_map(monster_number=0)
        player = Player(name='Rulan')
        lines = server._describe_room(_client(player))
        assert not any('statue' in l.lower() for l in lines)

    def test_no_statue_line_when_monster_lacks_petrify_flag(self, server):
        _record_statue('GOBLIN', 'Alice')
        server.monsters = [{'number': 99, 'name': 'GOBLIN', 'flags': {}}]
        server.game_map = _make_map(monster_number=99)
        player = Player(name='Rulan')
        lines = server._describe_room(_client(player))
        assert not any('statue' in l.lower() for l in lines)

    def test_no_statue_line_when_charmed_away(self, server):
        _record_statue('MEDUSA', 'Alice')
        server.game_map = _make_map(monster_number=_MEDUSA['number'])
        player = Player(name='Rulan')
        player.charmed_monsters = [_MEDUSA['number']]
        lines = server._describe_room(_client(player))
        assert not any('statue' in l.lower() for l in lines)
