"""tests/commands/test_ammo_carriers.py — ammo carrier auto-load mechanic.

Olly's own listing (shoppe/ollys.py) has always claimed "Appropriate ammo
will automatically be placed in the carrier when it is purchased. Buying
more than one will do no good." -- until now that was just flavor text
with no code behind it (a carrier behaved exactly like a loose, stacking
ammo box). Covers:

  - Buying a carrier arrives full and marks the item with a 'capacity'
    flag (shoppe/ollys.py).
  - Buying a second carrier of the same type is refused.
  - Buying raw ammo matching an owned carrier tops the carrier off
    instead of taking a new pack slot, capped at capacity.
  - USE-ing a carrier empties it into the weapon but leaves it in
    inventory (commands/use.py); USE-ing an empty carrier is rejected.
  - Inventory display (commands/inv.py) shows loose ammo as
    "[N rounds xM]" and a carrier as "[current/capacity rounds]".
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

from base_classes import PlayerMoneyTypes
from commands.inv import _format_entry
from commands.use import UseCommand
from inventory import Inventory, InventoryEntry
from items import Item, ItemCategory, Weapon
from player import Player
from shoppe.ollys import _ammo_section, _load_objects


class _FakeCtx:
    def __init__(self, responses, player):
        self._q = list(responses)
        self.sent: list = []
        self.player = player
        self.client = None
        self.server = None
        self.send = AsyncMock(side_effect=self._record)

    async def _record(self, *args, **kwargs):
        for a in args:
            if isinstance(a, list):
                self.sent.extend(a)
            else:
                self.sent.append(a)

    async def prompt(self, prompt_text: str = '', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None

    def flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


def _funded_player(silver: int = 1000) -> Player:
    player = Player(name='Rulan')
    player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, silver)
    return player


class TestCarrierPurchase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.objects_by_num = {o['number']: o for o in _load_objects()}
        # shop-local numbering: cartridge box is #15 (see test_ollys.py)

    async def test_carrier_arrives_full_and_flagged(self):
        player = _funded_player()
        ctx = _FakeCtx(['15', 'y', 'q'], player)
        await _ammo_section(ctx, player, player.inventory, self.objects_by_num)
        entry = player.inventory.find(name='cartridge box')[0]
        self.assertEqual(entry.item.flags['capacity'], 10)
        self.assertEqual(entry.item.flags['rounds'], 10)

    async def test_buying_second_carrier_of_same_type_refused(self):
        player = _funded_player()
        ctx = _FakeCtx(['15', 'y', '15', 'q'], player)
        await _ammo_section(ctx, player, player.inventory, self.objects_by_num)
        self.assertEqual(len(player.inventory.find(name='cartridge box')), 1)
        self.assertIn('buying another would do no good', ctx.flat())
        # Only charged once.
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 950)

    async def test_matching_ammo_tops_off_owned_carrier_instead_of_stacking(self):
        player = _funded_player()
        # Buy the carrier first (#15), then raw "balls" ammo (#6, used_with musket).
        ctx = _FakeCtx(['15', 'y', 'q'], player)
        await _ammo_section(ctx, player, player.inventory, self.objects_by_num)
        # Drain the carrier partway so the top-off has somewhere to go.
        carrier = player.inventory.find(name='cartridge box')[0]
        carrier.item.flags['rounds'] = 2

        ctx2 = _FakeCtx(['6', 'y', 'q'], player)
        await _ammo_section(ctx2, player, player.inventory, self.objects_by_num)

        # No new "balls" stack was created -- it went into the carrier.
        self.assertEqual(len(player.inventory.find(name='balls')), 0)
        self.assertEqual(carrier.item.flags['rounds'], 10)  # capped at capacity
        self.assertIn('loaded straight into your cartridge box', ctx2.flat())

    async def test_ammo_purchase_refused_when_carrier_already_full(self):
        player = _funded_player()
        ctx = _FakeCtx(['15', 'y', 'q'], player)
        await _ammo_section(ctx, player, player.inventory, self.objects_by_num)
        starting_silver = player.get_silver(PlayerMoneyTypes.IN_HAND)

        ctx2 = _FakeCtx(['6', 'q'], player)
        await _ammo_section(ctx2, player, player.inventory, self.objects_by_num)
        self.assertIn('already full', ctx2.flat())
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), starting_silver)

    async def test_no_owned_carrier_ammo_still_stacks_loose(self):
        player = _funded_player()
        ctx = _FakeCtx(['3', 'y', 'q'], player)  # arrows, no bow carrier exists
        await _ammo_section(ctx, player, player.inventory, self.objects_by_num)
        entry = player.inventory.find(name='arrows')[0]
        self.assertNotIn('capacity', entry.item.flags)


class TestCarrierUse(unittest.IsolatedAsyncioTestCase):
    def _carrier_item(self, rounds=10, capacity=10):
        return Item(
            id_number=147,
            name='cartridge box',
            category=ItemCategory.ITEM,
            flags={'rounds': rounds, 'damage': 2, 'used_with': 'musket', 'capacity': capacity},
        )

    def _musket(self):
        return Weapon(id_number=20, name='MUSKET', category=ItemCategory.WEAPON,
                       weapon_class='projectile', stability=50, to_hit=60)

    async def test_use_carrier_loads_weapon_and_stays_in_pack(self):
        player = Player(name='Rulan')
        player.readied_weapon = self._musket()
        player.inventory.add(self._carrier_item())
        ctx = _FakeCtx([], player)

        await UseCommand().execute(ctx, 'cartridge', 'box')

        self.assertEqual(player.ammo_rounds, 10)
        self.assertEqual(player.ammo_damage, 2)
        # Carrier is still in the pack, now empty.
        entries = player.inventory.find(name='cartridge box')
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].item.flags['rounds'], 0)

    async def test_use_empty_carrier_rejected(self):
        player = Player(name='Rulan')
        player.readied_weapon = self._musket()
        player.inventory.add(self._carrier_item(rounds=0))
        ctx = _FakeCtx([], player)

        await UseCommand().execute(ctx, 'cartridge', 'box')

        self.assertIn('IS EMPTY', ctx.flat())
        self.assertEqual(player.ammo_rounds, 0)


class TestInventoryAmmoDisplay(unittest.TestCase):
    def test_loose_ammo_shows_rounds_and_box_count(self):
        item = Item(id_number=100, name='arrows', category=ItemCategory.ITEM,
                    flags={'rounds': 4, 'damage': 1, 'used_with': ' bow'})
        entry = InventoryEntry(item=item, quantity=6)
        self.assertIn('[4 rounds x6]', _format_entry(entry, 1))

    def test_carrier_shows_current_over_capacity(self):
        item = Item(id_number=147, name='cartridge box', category=ItemCategory.ITEM,
                    flags={'rounds': 4, 'damage': 2, 'used_with': 'musket', 'capacity': 10})
        entry = InventoryEntry(item=item, quantity=1)
        self.assertIn('[4/10 rounds]', _format_entry(entry, 1))

    def test_non_ammo_item_unaffected(self):
        item = Item(id_number=6, name='large ruby', category=ItemCategory.ITEM)
        entry = InventoryEntry(item=item, quantity=2)
        formatted = _format_entry(entry, 1)
        self.assertIn('2x large ruby', formatted)
        self.assertNotIn('rounds', formatted)


if __name__ == '__main__':
    unittest.main(verbosity=2)
