"""tests/commands/test_use_ammo.py — unit tests for commands/use.py's
ammo-loading branch (USE <ammo>).

Regression coverage: _apply_item used to be gated behind
`isinstance(item, item_system.Item)` at the USE command's call site, but
every real inventory item (everything shops actually construct, e.g.
shoppe/ollys.py's ammo purchase) is an items.Item -- a separate, unrelated
class. That isinstance check was never true for a real item, so USE-ing
shop-bought ammo silently fell through to "You play with the X.." instead
of loading rounds into the readied weapon. See commands/use.py's
_apply_item docstring for the full story.

Coverage:
  - USE-ing ammo whose flags match the readied weapon loads
    ammo_rounds/ammo_damage/ammo_max and removes the item from inventory.
  - No weapon readied -> "YOU MUST READY YOUR WEAPON FIRST!"
  - Ammo for a different weapon -> "THIS AMMO IS NOT FOR THE ..."
  - A plain non-ammo item still falls through to "You play with the X.."
    (confirms the fix didn't turn every item into an ammo carrier).
"""
from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock

nc_stub = types.ModuleType('network_context')
nc_stub.GameContext = object
sys.modules.setdefault('network_context', nc_stub)

from commands.use import UseCommand
from inventory import Inventory
from items import Item, ItemCategory, Weapon


def _magnum_ammo() -> Item:
    # Same shape objects.json #104 defines, as shoppe/ollys.py now
    # preserves it onto the purchased item (see tests/shoppe/test_ollys.py's
    # test_bought_ammo_carries_flags_for_use_command).
    return Item(
        id_number=104,
        name='.357 ammo',
        category=ItemCategory.ITEM,
        flags={'rounds': 6, 'damage': 4, 'used_with': '.357 magnum'},
    )


def _magnum_weapon() -> Weapon:
    return Weapon(id_number=11, name='.357 MAGNUM', category=ItemCategory.WEAPON,
                  weapon_class='projectile', stability=50, to_hit=70)


def _make_player(readied_weapon=None):
    player = MagicMock()
    player.inventory = Inventory()
    player.readied_weapon = readied_weapon
    player.ammo_rounds = 0
    player.ammo_damage = 0
    player.ammo_max = 0
    player.unsaved_changes = False
    return player


class _FakeCtx:
    def __init__(self, player):
        self.player = player
        self.client = MagicMock()
        self.server = MagicMock()
        self.sent: list = []
        self.send = AsyncMock(side_effect=self._record)
        self.prompt = AsyncMock(return_value=None)

    async def _record(self, msg, **kwargs):
        if isinstance(msg, list):
            self.sent.extend(msg)
        else:
            self.sent.append(msg)

    def flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


class TestUseAmmoLoadsReadiedWeapon(unittest.IsolatedAsyncioTestCase):

    async def test_matching_ammo_loads_rounds_and_consumes_item(self):
        player = _make_player(readied_weapon=_magnum_weapon())
        player.inventory.add(_magnum_ammo())
        ctx = _FakeCtx(player)

        await UseCommand().execute(ctx, '.357', 'ammo')

        self.assertEqual(player.ammo_rounds, 6)
        self.assertEqual(player.ammo_damage, 4)
        self.assertEqual(player.ammo_max, 6)
        self.assertIn('6 ROUNDS NOW READY: +4 DAMAGE', ctx.flat())
        self.assertEqual(len(player.inventory.find(name='.357 ammo')), 0)
        self.assertTrue(player.unsaved_changes)

    async def test_no_weapon_readied_rejects(self):
        player = _make_player(readied_weapon=None)
        player.inventory.add(_magnum_ammo())
        ctx = _FakeCtx(player)

        await UseCommand().execute(ctx, '.357', 'ammo')

        self.assertIn('YOU MUST READY YOUR WEAPON FIRST!', ctx.flat())
        self.assertEqual(player.ammo_rounds, 0)
        self.assertEqual(len(player.inventory.find(name='.357 ammo')), 1)

    async def test_ammo_for_a_different_weapon_rejected(self):
        wrong_weapon = Weapon(id_number=98, name='CROSSBOW', category=ItemCategory.WEAPON,
                               weapon_class='projectile', stability=50, to_hit=60)
        player = _make_player(readied_weapon=wrong_weapon)
        player.inventory.add(_magnum_ammo())
        ctx = _FakeCtx(player)

        await UseCommand().execute(ctx, '.357', 'ammo')

        self.assertIn('THIS AMMO IS NOT FOR THE CROSSBOW!', ctx.flat())
        self.assertEqual(player.ammo_rounds, 0)

    async def test_non_ammo_item_falls_through_to_generic_message(self):
        player = _make_player(readied_weapon=_magnum_weapon())
        player.inventory.add(Item(id_number=6, name='large ruby', category=ItemCategory.ITEM))
        ctx = _FakeCtx(player)

        await UseCommand().execute(ctx, 'large', 'ruby')

        self.assertIn('You play with the large ruby..', ctx.flat())


if __name__ == '__main__':
    unittest.main(verbosity=2)
