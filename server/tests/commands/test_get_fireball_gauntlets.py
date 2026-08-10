"""tests/commands/test_get_fireball_gauntlets.py

Regression: commands/get.py's fireball-pickup branch did
`gauntlets = inventory.find(item_id=_GAUNTLETS_ID, ...)` and then, if
truthy, `inventory.remove(gauntlets.item)` -- but Inventory.find() always
returns a *list* of InventoryEntry (see inventory.py:184), never a bare
entry, so `.item` on it raised AttributeError. This meant any non-Wizard
player wearing gauntlets who picked up a real weapon-catalog FIREBALL/
LARGE FIREBALL/SMALL FIREBALL and rolled the 1-in-10 "gauntlets destroyed"
chance would crash instead of getting the intended protection message.

Run with:
    python -m pytest tests/commands/test_get_fireball_gauntlets.py -v
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from base_classes import PlayerClass
from commands.get import GetCommand, _room_available_items
from inventory import Inventory
from items import Item, ItemCategory


def _make_ctx(weapons: list[dict], room_weapon: int):
    server = MagicMock()
    server.items = []
    server.weapons = weapons
    server.rations = []
    server.monsters = []

    room = MagicMock()
    room.item = 0
    room.weapon = room_weapon
    room.food = 0
    room.monster = 0
    server.game_map.get_room.return_value = room

    player = MagicMock()
    player.item_history = []
    player.map_level = 1
    player.char_class = PlayerClass.FIGHTER
    player.hit_points = 20

    ctx = MagicMock()
    ctx.server = server
    ctx.player = player
    ctx.client.room = 1
    ctx.send = AsyncMock()
    ctx.send_room = AsyncMock()
    return ctx


def _fireball_weapons() -> list[dict]:
    # _room_available_items() falls back to id_number=idx+1 (weapons.json
    # dicts have no "id_number" key, only "number"), so the real FIREBALL
    # (weapons.json #14) must sit at list index 13 to reproduce the pickup.
    out = [{'number': i + 1, 'location': 1, 'name': f'FILLER{i}',
           'kind': 'standard', 'price': 1, 'weapon_class': 'bash'}
           for i in range(13)]
    out.append({'number': 14, 'location': 1, 'name': 'FIREBALL',
                'kind': 'standard', 'price': 5, 'weapon_class': 'fire'})
    return out


class TestFireballGauntlets(unittest.TestCase):

    def test_gauntlets_destroyed_roll_does_not_crash(self):
        weapons = _fireball_weapons()
        ctx = _make_ctx(weapons, room_weapon=len(weapons))
        name, entry, remove_fn = _room_available_items(ctx)[0]

        inventory = Inventory()
        inventory.add(Item(id_number=68, name='gauntlets', category=ItemCategory.ITEM))

        cmd = GetCommand()
        with patch('random.randint', return_value=1):   # force the 1-in-10 destroy roll
            asyncio.run(cmd._pick_up(ctx, inventory, name, entry, remove_fn))

        sent = [str(c.args[0]) for c in ctx.send.await_args_list]
        self.assertIn('THE GAUNTLETS TAKE THE HEAT..', sent)
        self.assertIn('THE GAUNTLETS ARE DESTROYED!!', sent)
        self.assertFalse(inventory.find(item_id=68),
                          'gauntlets should have been removed from inventory')

    def test_gauntlets_survive_roll_does_not_crash(self):
        weapons = _fireball_weapons()
        ctx = _make_ctx(weapons, room_weapon=len(weapons))
        name, entry, remove_fn = _room_available_items(ctx)[0]

        inventory = Inventory()
        inventory.add(Item(id_number=68, name='gauntlets', category=ItemCategory.ITEM))

        cmd = GetCommand()
        with patch('random.randint', return_value=5):   # avoid the destroy roll
            asyncio.run(cmd._pick_up(ctx, inventory, name, entry, remove_fn))

        sent = [str(c.args[0]) for c in ctx.send.await_args_list]
        self.assertIn('THE GAUNTLETS TAKE THE HEAT..', sent)
        self.assertNotIn('THE GAUNTLETS ARE DESTROYED!!', sent)
        self.assertTrue(inventory.find(item_id=68),
                         'gauntlets should still be in inventory')


if __name__ == '__main__':
    unittest.main(verbosity=2)
