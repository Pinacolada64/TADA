"""tests/test_room_combat_broadcast.py

_describe_room() should call out a player fighting a monster by name,
rather than blending them into the plain "X is here" list -- so someone
walking into the room immediately sees a fight already in progress.
"""
from __future__ import annotations

import asyncio
import sys
from unittest.mock import MagicMock

import pytest

# See test_wild_horse_placement.py: force a clean reimport regardless of
# what stubbed sys.modules['network_context']/['net_common'] before us.
for _mod in ('network_context', 'net_common', 'simple_server'):
    sys.modules.pop(_mod, None)

from simple_server import Server
from base_classes import Map, Room


def _make_map() -> Map:
    m = Map()
    room = Room(number=1, name='CAVERN', desc='A damp cavern.')
    m.levels[1] = {1: room}
    m.rooms = m.levels[1]
    return m


def _client(name, room_no=1):
    c = MagicMock()
    c.room = room_no
    c.virtual_location = None
    c.ctx.player.name = name
    return c


def _fake_session(monster_name, attacker_names, done=False):
    session = MagicMock()
    session.monster = {'name': monster_name}
    done_event = asyncio.Event()
    if done:
        done_event.set()
    session._done = done_event
    session.attackers = []
    for name in attacker_names:
        a_ctx = MagicMock()
        a_ctx.player.name = name
        session.attackers.append(a_ctx)
    return session


@pytest.fixture
def server():
    s = Server('127.0.0.1', 0)
    s.game_map = _make_map()
    return s


def _viewer_client():
    viewer = MagicMock()
    viewer.room = 1
    viewer.virtual_location = None
    viewer.ctx.player.map_level = 1
    viewer.ctx.player.name = 'Viewer'
    return viewer


class TestRoomCombatBroadcast:
    def test_fighter_called_out_by_name(self, server):
        railbender = _client('Railbender')
        server.clients = {'a': railbender}
        server.active_combats = {1: _fake_session('TROLL', ['Railbender'])}
        lines = server._describe_room(_viewer_client())
        assert 'Railbender is fighting TROLL here!' in lines

    def test_fighter_not_listed_as_plain_bystander(self, server):
        railbender = _client('Railbender')
        server.clients = {'a': railbender}
        server.active_combats = {1: _fake_session('TROLL', ['Railbender'])}
        lines = server._describe_room(_viewer_client())
        assert not any('Railbender is here' in line for line in lines)

    def test_multiple_fighters_use_oxford_comma_list(self, server):
        server.clients = {'a': _client('Railbender'), 'b': _client('Rulan')}
        server.active_combats = {1: _fake_session('TROLL', ['Railbender', 'Rulan'])}
        lines = server._describe_room(_viewer_client())
        assert 'Railbender and Rulan are fighting TROLL here!' in lines

    def test_bystander_still_listed_normally(self, server):
        server.clients = {
            'a': _client('Railbender'),
            'b': _client('Bystander'),
        }
        server.active_combats = {1: _fake_session('TROLL', ['Railbender'])}
        lines = server._describe_room(_viewer_client())
        assert any('Bystander is here' in line for line in lines)
        assert not any('Bystander' in line and 'fighting' in line for line in lines)

    def test_no_active_combat_shows_plain_list(self, server):
        server.clients = {'a': _client('Railbender')}
        server.active_combats = {}
        lines = server._describe_room(_viewer_client())
        assert any('Railbender is here' in line for line in lines)

    def test_finished_combat_not_shown_as_fighting(self, server):
        server.clients = {'a': _client('Railbender')}
        server.active_combats = {1: _fake_session('TROLL', ['Railbender'], done=True)}
        lines = server._describe_room(_viewer_client())
        assert any('Railbender is here' in line for line in lines)
        assert not any('fighting' in line for line in lines)
