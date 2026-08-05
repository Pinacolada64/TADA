"""tests/ship/test_armory.py

Covers ship/armory.py -- the ship's narrower armory rack (SPUR.SHIP.S
`weapons0`/`protect`): only energy weapons (weapons.json #58-60) and
sci-fi armor/shields (objects.json #113-116), unlike the regular Merchant
Shoppe's armory (shoppe/armory.py), which this port already generalized
to sell from the full catalog everywhere.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from base_classes import PlayerMoneyTypes
from flags import PlayerFlags
from inventory import Inventory
from items import ItemCategory
from player import Player
from ship.armory import main as ship_armory_main, protection as ship_protection


def _new_player(name: str) -> Player:
    player = Player(name=name)
    player.clear_flag(PlayerFlags.DEBUG_MODE)
    player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 100000)
    player.inventory = Inventory()
    return player


class _FakeCtx:
    def __init__(self, responses, player):
        self._q = list(responses)
        self.sent: list = []
        self.player = player
        self.server = SimpleNamespace(items=[])

    async def send(self, *args):
        for a in args:
            if isinstance(a, list):
                self.sent.extend(a)
            else:
                self.sent.append(a)

    async def prompt(self, prompt_text: str = '', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


class TestShipArmoryWeaponRack(unittest.IsolatedAsyncioTestCase):
    async def test_weapon_listing_only_shows_energy_weapons(self):
        player = _new_player('Rulan')
        ctx = _FakeCtx(['w', 'b', '?', 'q', 'q'], player)
        await ship_armory_main(ctx)
        flat = ctx._flat()
        self.assertIn('LIGHT SABRE', flat)
        self.assertIn('HAND PHASER', flat)
        self.assertIn('PLASMA RIFLE', flat)
        # a regular-shop weapon (e.g. Excalibur) must not appear
        self.assertNotIn('EXCALIBUR', flat.upper())

    async def test_can_buy_light_sabre(self):
        player = _new_player('Rulan')
        # W)eaponry -> B)uy -> weapon #58 -> no trial -> confirm -> Q -> Q
        ctx = _FakeCtx(['w', 'b', '58', 'n', 'y', 'q', 'q'], player)
        await ship_armory_main(ctx)
        entries = player.inventory.entries('Weapon')
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].item.id_number, 58)

    async def test_regular_shop_weapon_number_is_not_purchasable(self):
        # #1 is a regular-shop-only weapon, out of the ship's #58-60 range.
        player = _new_player('Rulan')
        ctx = _FakeCtx(['w', 'b', '1', 'q', 'q'], player)
        await ship_armory_main(ctx)
        self.assertEqual(len(player.inventory.entries('Weapon')), 0)


class TestShipArmoryProtectionRack(unittest.IsolatedAsyncioTestCase):
    async def test_protection_listing_only_shows_sci_fi_gear(self):
        player = _new_player('Rulan')
        ctx = _FakeCtx(['?', 'q'], player)
        await ship_protection(ctx)
        flat = ctx._flat()
        for name in ('battle armor', 'battle shield', 'power armor', 'lazer shield'):
            self.assertIn(name, flat)

    async def test_can_buy_power_armor(self):
        # objects.json order within #113-116 is battle armor, battle
        # shield, power armor, lazer shield -- choice 3 is power armor.
        player = _new_player('Rulan')
        ctx = _FakeCtx(['3', 'y'], player)
        await ship_protection(ctx)
        entries = player.inventory.entries(ItemCategory.ARMOR)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].item.name, 'power armor')
        self.assertEqual(entries[0].item.id_number, 115)


if __name__ == '__main__':
    unittest.main()
