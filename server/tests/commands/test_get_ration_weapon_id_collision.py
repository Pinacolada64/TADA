"""tests/commands/test_get_ration_weapon_id_collision.py

Regression: id_number is only unique *within* its own category
(weapons/items/rations each number independently -- see items.py:364).
commands/get.py's _FIREBALL_IDS = {14, 15, 39} check in _pick_up()
compared item_id alone with no category guard, so ration #39 TOMATOES
collided with weapon #39 SMALL FIREBALL and getting tomatoes wrongly
printed the "Yelp! You burn your fingers!" fireball message.

Run with:
    python -m pytest tests/commands/test_get_ration_weapon_id_collision.py -v
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from base_classes import PlayerClass
from commands.get import GetCommand, _room_available_items


def _make_ctx(rations: list[dict]):
    server = MagicMock()
    server.items = []
    server.weapons = []
    server.rations = rations
    server.monsters = []

    room = MagicMock()
    room.item = 0
    room.weapon = 0
    # _room_available_items() falls back to id_number=idx+1 (rations.json
    # dicts have no "id_number" key, only "number"), so the room's food
    # slot must be the array position matching rations.json's real
    # TOMATOES entry (index 38, "number": 39) to reproduce the collision.
    room.food = len(rations)
    room.monster = 0
    server.game_map.get_room.return_value = room

    player = MagicMock()
    player.ration_history = []
    player.map_level = 1
    player.char_class = PlayerClass.FIGHTER
    player.hit_points = 20

    ctx = MagicMock()
    ctx.server = server
    ctx.player = player
    ctx.client.room = 1
    ctx.send = AsyncMock()
    return ctx


class TestRationWeaponIdCollision(unittest.TestCase):

    def test_getting_tomatoes_does_not_trigger_fireball_burn(self):
        rations = [{'number': i + 1, 'name': f'FILLER{i}', 'kind': 'food', 'price': 1}
                   for i in range(38)]
        rations.append({'number': 39, 'name': 'TOMATOES', 'kind': 'food', 'price': 5})
        ctx = _make_ctx(rations)
        name, entry, remove_fn = _room_available_items(ctx)[0]

        inventory = MagicMock()
        inventory.is_full.return_value = False
        inventory.find.return_value = []

        cmd = GetCommand()
        asyncio.run(cmd._pick_up(ctx, inventory, name, entry, remove_fn))

        sent = [str(call.args[0]) for call in ctx.send.await_args_list]
        self.assertFalse(any('burn your fingers' in line for line in sent),
                          f'unexpected fireball burn message in: {sent}')
        self.assertEqual(ctx.player.hit_points, 20)


if __name__ == '__main__':
    unittest.main(verbosity=2)
