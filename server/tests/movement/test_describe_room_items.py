"""tests/movement/test_describe_room_items.py

Regression: simple_server.py's _describe_room() checked
`inventory.find(item_id=item_id) is not None` to decide whether a room
item should be hidden because the player already carries it. Inventory.
find() always returns a list (empty when nothing matches), never None --
so that check was always True for any player with a real (non-None)
inventory, silently suppressing every room item for every player.
Found investigating Room 1's "Adventurer's Guide" (objects.json #62,
level_1.json room 1's "item": 62) never showing up.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

for _mod in ('network_context', 'net_common', 'simple_server'):
    sys.modules.pop(_mod, None)

from simple_server import Server
from base_classes import Map, Room
from inventory import Inventory
from items import Item, ItemCategory
from player import Player


def _make_map(*, item=0, food=0, weapon=0) -> Map:
    m = Map()
    room = Room(number=1, name='MERCHANT LOBBY', desc='The store entrance.',
                exits={}, item=item, food=food, weapon=weapon)
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


class TestRoomItemVisibility:
    def test_item_shown_to_player_with_empty_inventory(self, server):
        server.game_map = _make_map(item=62)  # objects.json #62: Adventurer's Guide
        player = Player(name='Rulan')
        player.inventory = Inventory(capacity=10)
        lines = server._describe_room(_client(player))
        assert any("Adventurer's Guide" in l for l in lines)

    def test_item_hidden_once_player_carries_it(self, server):
        server.game_map = _make_map(item=62)
        player = Player(name='Rulan')
        player.inventory = Inventory(capacity=10)
        player.inventory.add(Item(id_number=62, name="Adventurer's Guide",
                                   category=ItemCategory.ITEM))
        lines = server._describe_room(_client(player))
        assert not any("Adventurer's Guide" in l for l in lines)

    def test_item_hidden_once_picked_up_and_not_returned(self, server):
        server.game_map = _make_map(item=62)
        player = Player(name='Rulan')
        player.inventory = Inventory(capacity=10)
        player.picked_up_items = [62]
        lines = server._describe_room(_client(player))
        assert not any("Adventurer's Guide" in l for l in lines)

    def test_unrelated_inventory_contents_do_not_hide_the_item(self, server):
        """A player carrying some other item must still see this room's
        item -- the old `is not None` bug hid every room item regardless
        of what (if anything) matched."""
        server.game_map = _make_map(item=62)
        player = Player(name='Rulan')
        player.inventory = Inventory(capacity=10)
        player.inventory.add(Item(id_number=1, name='compass', category=ItemCategory.ITEM))
        lines = server._describe_room(_client(player))
        assert any("Adventurer's Guide" in l for l in lines)

    def test_no_item_in_room_shows_no_you_see_line(self, server):
        server.game_map = _make_map(item=0)
        player = Player(name='Rulan')
        player.inventory = Inventory(capacity=10)
        lines = server._describe_room(_client(player))
        assert not any(l.startswith('You see') for l in lines)
