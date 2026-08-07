"""tests/commands/test_use_grenade_communicator_id_collision.py

Regression: id_number is only unique within its own category
(weapons/items/rations each number independently -- items.py:364).
commands/use.py's grenade (#16) and communicator (#66) branches compared
item_id alone with no category guard, colliding with:

  - ration #16 CUBE OF SUGAR vs objects.json #16 hand grenade
  - ration #66 VORPAL POTION vs objects.json #66 communicator

so USE-ing either ration wrongly hurled it as a grenade / tried to beam
the player to level 6.

Run with:
    python -m pytest tests/commands/test_use_grenade_communicator_id_collision.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from commands.use import UseCommand
from inventory import Inventory
from items import Item, ItemCategory


def _make_player():
    player = MagicMock()
    player.inventory = Inventory()
    player.unsaved_changes = False
    return player


class _FakeCtx:
    def __init__(self, player):
        self.player = player
        self.client = MagicMock()
        self.server = MagicMock()
        self.server.active_combats = {}
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


class TestGrenadeRationCollision(unittest.IsolatedAsyncioTestCase):

    async def test_cube_of_sugar_not_hurled_as_grenade(self):
        player = _make_player()
        sugar = Item(id_number=16, name='CUBE OF SUGAR', category=ItemCategory.FOOD, kind='food')
        player.inventory.add(sugar)
        ctx = _FakeCtx(player)

        await UseCommand().execute(ctx, 'cube', 'of', 'sugar')

        self.assertNotIn('You hurl the grenade!', ctx.flat())
        self.assertEqual(len(player.inventory.find(item_id=16)), 1,
                         'CUBE OF SUGAR should not have been consumed')

    async def test_real_grenade_still_hurled(self):
        player = _make_player()
        grenade = Item(id_number=16, name='hand grenade', category=ItemCategory.ITEM)
        player.inventory.add(grenade)
        ctx = _FakeCtx(player)

        await UseCommand().execute(ctx, 'hand', 'grenade')

        self.assertIn('You hurl the grenade!', ctx.flat())


class TestCommunicatorRationCollision(unittest.IsolatedAsyncioTestCase):

    async def test_vorpal_potion_does_not_trigger_beam_aboard(self):
        player = _make_player()
        potion = Item(id_number=66, name='VORPAL POTION', category=ItemCategory.DRINK, kind='drink')
        player.inventory.add(potion)
        ctx = _FakeCtx(player)

        await UseCommand().execute(ctx, 'vorpal', 'potion')

        combined = ctx.flat().lower()
        self.assertNotIn('beam', combined)
        self.assertNotIn('malfunction', combined)


if __name__ == '__main__':
    unittest.main(verbosity=2)
