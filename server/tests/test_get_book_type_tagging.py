"""tests/test_get_book_type_tagging.py

Regression: commands/get.py's _room_available_items() constructed picked-up
items with only a generic ItemCategory (ITEM/WEAPON/FOOD) and never
preserved objects.json's own "type" field (e.g. "book"). Without it,
commands/read.py's book list (which keys off ItemType.BOOK) could never
show a book found in a room -- only the two hardcoded special ids (scrap
of paper, brass claim tag) were reachable at all. Confirmed by direct
encode/attribute check before fixing: a freshly-picked-up "Scroll of
Endurance" had no `.type` attribute whatsoever.

Run with:
    python -m pytest tests/test_get_book_type_tagging.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from commands.get import _room_available_items
from item_system import ItemType


def _make_ctx(room_item_index: int, items: list[dict]):
    server = MagicMock()
    server.items = items
    server.weapons = []
    server.rations = []

    room = MagicMock()
    room.item = room_item_index
    room.weapon = 0
    room.food = 0
    server.game_map.get_room.return_value = room

    player = MagicMock()
    player.picked_up_items = []
    player.map_level = 1

    ctx = MagicMock()
    ctx.server = server
    ctx.player = player
    ctx.client.room = 1
    return ctx


class TestBookTypeTagging(unittest.TestCase):

    def test_book_item_gets_tagged_as_book(self):
        ctx = _make_ctx(1, [{'number': 89, 'name': 'Scroll of Endurance',
                             'type': 'book', 'price': 6}])
        results = _room_available_items(ctx)
        self.assertEqual(len(results), 1)
        _, entry, _ = results[0]
        self.assertEqual(entry.item.type, ItemType.BOOK)

    def test_treasure_item_gets_tagged_as_treasure_not_book(self):
        ctx = _make_ctx(1, [{'number': 1, 'name': 'compass',
                             'type': 'compass', 'price': 5}])
        results = _room_available_items(ctx)
        _, entry, _ = results[0]
        self.assertEqual(entry.item.type, ItemType.COMPASS)
        self.assertNotEqual(entry.item.type, ItemType.BOOK)

    def test_unknown_type_string_does_not_crash(self):
        ctx = _make_ctx(1, [{'number': 1, 'name': 'mystery',
                             'type': 'not-a-real-type', 'price': 1}])
        results = _room_available_items(ctx)
        _, entry, _ = results[0]
        self.assertIsNone(getattr(entry.item, 'type', None))

    def test_missing_type_field_does_not_crash(self):
        ctx = _make_ctx(1, [{'number': 1, 'name': 'no-type-item', 'price': 1}])
        results = _room_available_items(ctx)
        _, entry, _ = results[0]
        self.assertIsNone(getattr(entry.item, 'type', None))


if __name__ == '__main__':
    unittest.main(verbosity=2)
