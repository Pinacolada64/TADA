"""tests/commands/test_get_hides_carried_static_items.py

commands/get.py's _room_available_items() hides a static room item the
player is already carrying -- SPUR.MAIN.S:244 zeroes the room's item when
it's in inventory (xi$) *or* this session's history (xt$), so neither the
description nor GET sees it. The room description (simple_server.py) already
did; GET's list (and LOOK/EXAMINE <item>, which share it) only checked the
history, so `get prospecting` offered a book LOOK said wasn't there.

Run with:
    python -m pytest tests/commands/test_get_hides_carried_static_items.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from commands.get import _room_available_items
from inventory import Inventory, InventoryEntry
from items import Item, ItemCategory


def _padded(target_number: int, name: str, **fields) -> list[dict]:
    """1-indexed catalog where element target_number is the real entry
    (_room_available_items() falls back to id_number=idx+1)."""
    out = [{'number': i + 1, 'name': f'FILLER{i}', 'price': 1} for i in range(target_number - 1)]
    out.append({'number': target_number, 'name': name, **fields})
    return out


def _make_ctx(*, items=(), weapons=(), room_item=0, room_weapon=0, carrying=()):
    server = MagicMock()
    server.items = list(items)
    server.weapons = list(weapons)
    server.rations = []
    server.monsters = []
    server.room_items = {}

    room = MagicMock()
    room.item = room_item
    room.weapon = room_weapon
    room.food = 0
    room.monster = 0
    server.game_map.get_room.return_value = room

    player = MagicMock()
    player.ration_history = []
    player.item_history = []
    player.map_level = 1
    player.inventory = Inventory()
    for item in carrying:
        player.inventory.add(item)

    ctx = MagicMock()
    ctx.server = server
    ctx.player = player
    ctx.client.room = 1
    ctx.send = AsyncMock()
    return ctx


def _names(ctx) -> list[str]:
    return [name for name, _, _ in _room_available_items(ctx)]


class TestGetHidesCarriedStaticItems(unittest.TestCase):

    def test_static_item_listed_when_not_carried(self):
        ctx = _make_ctx(items=_padded(61, 'Prospecting...', type='book'), room_item=61)
        self.assertEqual(_names(ctx), ['Prospecting...'])

    def test_static_item_hidden_while_carrying_one(self):
        book = Item(id_number=61, name='Prospecting...', category=ItemCategory.ITEM)
        ctx = _make_ctx(items=_padded(61, 'Prospecting...', type='book'), room_item=61,
                        carrying=[book])
        self.assertEqual(_names(ctx), [])

    def test_same_number_in_another_category_does_not_hide_it(self):
        """id_number is only unique within a category: carrying weapon #3
        WOOD STAFF must not hide object #3 steel armor."""
        staff = Item(id_number=3, name='WOOD STAFF', category=ItemCategory.WEAPON)
        ctx = _make_ctx(items=_padded(3, 'steel armor', type='armor'), room_item=3,
                        carrying=[staff])
        self.assertEqual(_names(ctx), ['steel armor'])

    def test_player_dropped_copy_still_listed_while_carrying_one(self):
        """Only the static item is hidden -- a copy someone dropped is a real
        object on the floor (_pick_up()'s "You already have" still applies)."""
        book = Item(id_number=61, name='Prospecting...', category=ItemCategory.ITEM)
        ctx = _make_ctx(items=_padded(61, 'Prospecting...', type='book'), room_item=61,
                        carrying=[book])
        dropped = Item(id_number=61, name='Prospecting...', category=ItemCategory.ITEM)
        ctx.server.room_items = {1: [InventoryEntry(item=dropped)]}
        self.assertEqual(_names(ctx), ['Prospecting...'])

    def test_other_static_items_in_room_unaffected(self):
        book = Item(id_number=61, name='Prospecting...', category=ItemCategory.ITEM)
        weapons = _padded(5, 'SHORT SWORD', weapon_class='slash')
        ctx = _make_ctx(items=_padded(61, 'Prospecting...', type='book'), room_item=61,
                        weapons=weapons, room_weapon=5, carrying=[book])
        self.assertEqual(_names(ctx), ['SHORT SWORD'])


if __name__ == '__main__':
    unittest.main()
