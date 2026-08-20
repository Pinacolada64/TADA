"""tests/movement/test_describe_room_nostalgic_charm.py

simple_server.py's _describe_room_parts() used to print nothing at all
for a room whose monster the player has charmed and recruited into the
party (mon_num in player.charmed_monsters) -- SPUR.MISC4.S/
t_encounter.lbl actually has a line for this case: revisiting the room
prints "The X look(s) around nostalgically.." instead. Ryan's request
(8/13/26): wire that line up instead of leaving the branch a silent
no-op.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from simple_server import Server
from base_classes import Map, Room
from player import Player

_PIXIE = {'number': 21, 'name': 'PIXIE', 'flags': {}}
_MUNCHKINS = {'number': 130, 'name': 'MUNCHKINS', 'flags': {}}


def _make_map(monster_number: int) -> Map:
    m = Map()
    room = Room(number=1, name='GLADE', desc='A quiet glade.', exits={},
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
    s.monsters = [_PIXIE, _MUNCHKINS]
    return s


class TestNostalgicCharmedMonsterLine:
    def test_shows_nostalgic_line_for_charmed_monster(self, server):
        server.game_map = _make_map(monster_number=_PIXIE['number'])
        player = Player(name='Rulan')
        player.charmed_monsters = [_PIXIE['number']]

        lines = server._describe_room(_client(player))

        assert 'The PIXIE looks around nostalgically..' in lines

    def test_pluralizes_look_for_a_plural_monster_name(self, server):
        server.game_map = _make_map(monster_number=_MUNCHKINS['number'])
        player = Player(name='Rulan')
        player.charmed_monsters = [_MUNCHKINS['number']]

        lines = server._describe_room(_client(player))

        assert 'The MUNCHKINS look around nostalgically..' in lines

    def test_no_nostalgic_line_when_not_charmed(self, server):
        server.game_map = _make_map(monster_number=_PIXIE['number'])
        player = Player(name='Rulan')

        lines = server._describe_room(_client(player))

        assert not any('nostalgically' in l for l in lines)
        assert 'There is a PIXIE here.' in lines

    def test_no_nostalgic_line_for_a_different_players_charm(self, server):
        server.game_map = _make_map(monster_number=_PIXIE['number'])
        player = Player(name='Rulan')
        player.charmed_monsters = [_MUNCHKINS['number']]  # charmed a different monster

        lines = server._describe_room(_client(player))

        assert not any('nostalgically' in l for l in lines)
        assert 'There is a PIXIE here.' in lines
