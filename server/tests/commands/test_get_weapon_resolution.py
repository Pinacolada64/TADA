"""tests/commands/test_get_weapon_resolution.py

Regression: commands/get.py's _room_available_items() built every
room-picked weapon as a bare Item(id_number, name, category, kind) --
never a real items.Weapon -- so a weapon was already missing
sound_effect/stability/to_hit/weapon_class from the moment of pickup,
independent of any save/load round trip. Combined with the same gap in
Inventory.from_json(), this meant a freshly-picked-up weapon that got
readied and swung crashed combat's weapon_sfx() (AttributeError:
'Item' object has no attribute 'sound_effect'). The weapon branch now
builds a fully-populated Weapon via items.build_weapon_from_raw(),
mirroring shoppe/armory.py's buy-path construction exactly.

Run with:
    python -m pytest tests/commands/test_get_weapon_resolution.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from commands.get import _room_available_items
from items import ItemCategory, Weapon


def _make_ctx(room_weapon_index: int, weapons: list[dict]):
    server = MagicMock()
    server.items = []
    server.weapons = weapons
    server.rations = []
    server.monsters = []

    room = MagicMock()
    room.item = 0
    room.weapon = room_weapon_index
    room.food = 0
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


class TestWeaponPickupResolution(unittest.TestCase):

    _LONG_SWORD = {
        'number': 1, 'location': 2, 'name': 'LONG SWORD', 'kind': 'standard',
        'sound_effect': ['SWISH!', 'SLASH!'], 'stability': 50, 'to_hit': 60,
        'price': 250, 'weapon_class': 'bash/slash',
    }

    def test_room_weapon_pickup_is_a_real_weapon(self):
        ctx = _make_ctx(1, [self._LONG_SWORD])
        results = _room_available_items(ctx)

        self.assertEqual(len(results), 1)
        _, entry, _ = results[0]
        self.assertIsInstance(entry.item, Weapon)
        self.assertEqual(entry.item.category, ItemCategory.WEAPON)
        self.assertEqual(entry.item.sound_effect, ('SWISH!', 'SLASH!'))
        self.assertEqual(entry.item.weapon_class, 'bash/slash')
        self.assertEqual(entry.item.stability, 50)
        self.assertEqual(entry.item.to_hit, 60)

    def test_readied_room_weapon_gets_real_sfx(self):
        # End-to-end: the exact "get sword, ready it, attack" scenario --
        # weapon_sfx() must return the real per-weapon sound, not the
        # class-based fallback, since this weapon was never bought from
        # the armory.
        from item_system import weapon_sfx

        ctx = _make_ctx(1, [self._LONG_SWORD])
        _, entry, _ = _room_available_items(ctx)[0]

        self.assertEqual(weapon_sfx(entry.item), ('SWISH!', 'SLASH!'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
