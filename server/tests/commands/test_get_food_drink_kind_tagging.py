"""tests/test_get_food_drink_kind_tagging.py

Regression: commands/get.py's _room_available_items() tagged every
server.rations pickup with category=ItemCategory.FOOD and never set
item.kind at all. commands/eat.py's _food_entries() and commands/drink.py's
_drink_entries() both filter inventory by item.kind ('food'/'drink') --
without it, a room-picked LOAF OF BREAD was invisible to 'eat' entirely
("You are not carrying any food matching...") even though it was sitting
right there in inventory, and a room-picked MINERAL WATER (rations.json's
own "kind": "drink") was tagged category=FOOD instead of DRINK on top of
that. Confirmed by direct attribute check before fixing: a freshly-picked-up
LOAF OF BREAD had no `.kind` attribute whatsoever.

Run with:
    python -m pytest tests/commands/test_get_food_drink_kind_tagging.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from commands.eat import _food_entries
from commands.get import _room_available_items
from items import ItemCategory


def _make_ctx(room_food_index: int, rations: list[dict]):
    server = MagicMock()
    server.items = []
    server.weapons = []
    server.rations = rations
    server.monsters = []

    room = MagicMock()
    room.item = 0
    room.weapon = 0
    room.food = room_food_index
    room.monster = 0
    server.game_map.get_room.return_value = room

    player = MagicMock()
    player.picked_up_items = []
    player.map_level = 1

    ctx = MagicMock()
    ctx.server = server
    ctx.player = player
    ctx.client.room = 1
    return ctx


class TestFoodDrinkKindTagging(unittest.TestCase):

    def test_food_ration_gets_kind_food(self):
        ctx = _make_ctx(1, [{'number': 5, 'name': 'LOAF OF BREAD',
                             'kind': 'food', 'price': 30}])
        results = _room_available_items(ctx)
        self.assertEqual(len(results), 1)
        _, entry, _ = results[0]
        self.assertEqual(entry.item.kind, 'food')
        self.assertEqual(entry.item.category, ItemCategory.FOOD)

    def test_drink_ration_gets_kind_drink_and_category_drink(self):
        ctx = _make_ctx(1, [{'number': 4, 'name': 'MINERAL WATER',
                             'kind': 'drink', 'price': 25}])
        results = _room_available_items(ctx)
        _, entry, _ = results[0]
        self.assertEqual(entry.item.kind, 'drink')
        self.assertEqual(entry.item.category, ItemCategory.DRINK)

    def test_eat_command_sees_picked_up_bread(self):
        # End-to-end: the exact "eat bread" scenario Ryan reported.
        ctx = _make_ctx(1, [{'number': 5, 'name': 'LOAF OF BREAD',
                             'kind': 'food', 'price': 30}])
        _, entry, _ = _room_available_items(ctx)[0]

        player = MagicMock()
        player.inventory.entries.return_value = [entry]
        matches = _food_entries(player)
        self.assertEqual(len(matches), 1)
        self.assertIn('bread', matches[0].item.name.lower())


if __name__ == '__main__':
    unittest.main(verbosity=2)
