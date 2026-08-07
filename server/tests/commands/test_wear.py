"""tests/commands/test_wear.py — commands/wear.py: WEAR (armor + the ring
of invisibility toggle).

Run with:
    python -m pytest tests/commands/test_wear.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from commands.wear import WearCommand, _wearable_entries
from flags import PlayerFlags
from inventory import Inventory
from items import Item, ItemCategory


def _item(name, item_id=1, category=None, kind=''):
    return Item(id_number=item_id, name=name,
               category=category or ItemCategory.ITEM, kind=kind)


def _make_player():
    player = MagicMock()
    player.name = 'Rulan'
    player.inventory = Inventory()
    player.stats = {'Constitution': 10}
    player.is_expert = False
    player.query_flag = MagicMock(return_value=False)
    return player


class _FakeCtx:
    def __init__(self, player):
        self.player = player
        self._sent: list[str] = []

    async def send(self, msg, **kwargs):
        if isinstance(msg, list):
            self._sent.extend(str(m) for m in msg)
        else:
            self._sent.append(str(msg))

    async def prompt(self, *args, **kwargs):
        return ''

    def sent(self) -> str:
        return '\n'.join(self._sent)


class TestWearableEntriesRingCollision(unittest.TestCase):
    # Regression: id_number is only unique within its own category
    # (weapons/items/rations each number independently -- items.py:364).
    # objects.json #67 "ring" collides with ration #67 "DEAD BUG" --
    # without a category guard, the ration showed up in the WEAR list
    # and toggling it flipped RING_WORN on an unrelated food item.

    def test_dead_bug_ration_not_wearable(self):
        player = _make_player()
        dead_bug = _item('DEAD BUG', item_id=67, category=ItemCategory.FOOD, kind='food')
        player.inventory.add(dead_bug)
        entries = _wearable_entries(player)
        self.assertEqual(entries, [])

    def test_real_ring_still_wearable(self):
        player = _make_player()
        ring = _item('ring', item_id=67, category=ItemCategory.ITEM)
        player.inventory.add(ring)
        entries = _wearable_entries(player)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].item.name, 'ring')


class TestWearCommandRingCollision(unittest.IsolatedAsyncioTestCase):

    async def test_wear_dead_bug_does_not_toggle_ring_worn(self):
        player = _make_player()
        dead_bug = _item('DEAD BUG', item_id=67, category=ItemCategory.FOOD, kind='food')
        player.inventory.add(dead_bug)
        ctx = _FakeCtx(player)
        cmd = WearCommand()
        await cmd.execute(ctx, 'dead bug')
        self.assertIn('nothing to wear', ctx.sent().lower())
        player.set_flag.assert_not_called()

    async def test_wear_real_ring_toggles_ring_worn(self):
        player = _make_player()
        ring = _item('ring', item_id=67, category=ItemCategory.ITEM)
        player.inventory.add(ring)
        ctx = _FakeCtx(player)
        cmd = WearCommand()
        await cmd.execute(ctx, 'ring')
        player.set_flag.assert_called_once_with(PlayerFlags.RING_WORN)


if __name__ == '__main__':
    unittest.main(verbosity=2)
