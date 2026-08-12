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
from item_system import ItemType
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


class TestWearPendantCollision(unittest.TestCase):
    # Same category guard as the ring collision above -- objects.json #82
    # "Crystal Pendant" collides with ration #82 "BUCKET OF WATER".

    def test_bucket_of_water_not_wearable(self):
        player = _make_player()
        bucket = _item('BUCKET OF WATER', item_id=82, category=ItemCategory.FOOD, kind='drink')
        player.inventory.add(bucket)
        entries = _wearable_entries(player)
        self.assertEqual(entries, [])

    def test_real_pendant_still_wearable(self):
        player = _make_player()
        pendant = _item('Crystal Pendant', item_id=82, category=ItemCategory.ITEM)
        player.inventory.add(pendant)
        entries = _wearable_entries(player)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].item.name, 'Crystal Pendant')


class TestWearCommandPendant(unittest.IsolatedAsyncioTestCase):

    async def test_wear_pendant_toggles_pendant_worn(self):
        player = _make_player()
        pendant = _item('Crystal Pendant', item_id=82, category=ItemCategory.ITEM)
        player.inventory.add(pendant)
        ctx = _FakeCtx(player)
        await WearCommand().execute(ctx, 'crystal pendant')
        player.set_flag.assert_called_once_with(PlayerFlags.PENDANT_WORN)
        self.assertIn('Crystal Pendant worn!', ctx.sent())

    async def test_wear_again_removes_pendant(self):
        player = _make_player()
        player.query_flag = MagicMock(return_value=True)
        pendant = _item('Crystal Pendant', item_id=82, category=ItemCategory.ITEM)
        player.inventory.add(pendant)
        ctx = _FakeCtx(player)
        await WearCommand().execute(ctx, 'crystal pendant')
        player.clear_flag.assert_called_once_with(PlayerFlags.PENDANT_WORN)
        self.assertIn('returned to your pack', ctx.sent().lower())


class TestWearArmorSetsActiveArmorId(unittest.IsolatedAsyncioTestCase):
    # Regression: WEAR used to boost player.armor's flat percentage without
    # ever recording *which* armor item was worn, so STAT/the login banner
    # had nothing to look up a name for. Every armor-equip path should now
    # set player.active_armor_id to the worn item's number.

    async def test_generic_armor_sets_active_armor_id(self):
        # As of the 2026-08-08 per-item durability redesign, WEAR derives
        # player.armor from the item's own .condition (100 = fresh, no
        # attribute at all defaults to fresh too) rather than a price*10
        # boost -- a fresh, uncapped-class item wears in at 100%.
        player = _make_player()
        player.armor = 0
        player.char_class = None
        player.char_race  = None
        armor = _item('leather armor', item_id=24, category=ItemCategory.ARMOR)
        armor.type  = ItemType.ARMOR
        player.inventory.add(armor)
        ctx = _FakeCtx(player)
        await WearCommand().execute(ctx, 'leather armor')
        self.assertEqual(player.active_armor_id, 24)
        self.assertEqual(player.armor, 100)

    async def test_worn_armor_rating_reflects_its_own_condition(self):
        player = _make_player()
        player.armor = 0
        player.char_class = None
        player.char_race  = None
        armor = _item('battered leather armor', item_id=24, category=ItemCategory.ARMOR)
        armor.type      = ItemType.ARMOR
        armor.condition = 40
        player.inventory.add(armor)
        ctx = _FakeCtx(player)
        await WearCommand().execute(ctx, 'battered leather armor')
        self.assertEqual(player.armor, 40)

    async def test_wear_does_not_consume_the_item(self):
        player = _make_player()
        player.armor = 0
        player.char_class = None
        player.char_race  = None
        armor = _item('leather armor', item_id=24, category=ItemCategory.ARMOR)
        armor.type = ItemType.ARMOR
        player.inventory.add(armor)
        ctx = _FakeCtx(player)
        await WearCommand().execute(ctx, 'leather armor')
        self.assertEqual(len(player.inventory.find(item_id=24)), 1)

    async def test_wearing_a_second_piece_swaps_the_equipped_id(self):
        player = _make_player()
        player.armor = 0
        player.char_class = None
        player.char_race  = None
        first  = _item('leather armor', item_id=24, category=ItemCategory.ARMOR)
        first.type = ItemType.ARMOR
        second = _item('chainmail armor', item_id=28, category=ItemCategory.ARMOR)
        second.type      = ItemType.ARMOR
        second.condition = 70
        player.inventory.add(first)
        player.inventory.add(second)
        ctx = _FakeCtx(player)
        await WearCommand().execute(ctx, 'leather armor')
        await WearCommand().execute(ctx, 'chainmail armor')
        self.assertEqual(player.active_armor_id, 28)
        self.assertEqual(player.armor, 70)
        # the old piece is still in the pack, untouched
        self.assertEqual(len(player.inventory.find(item_id=24)), 1)

    async def test_battle_armor_sets_active_armor_id(self):
        player = _make_player()
        armor = _item('battle armor', item_id=113, category=ItemCategory.ARMOR)
        armor.type = ItemType.ARMOR
        player.inventory.add(armor)
        ctx = _FakeCtx(player)
        await WearCommand().execute(ctx, 'battle armor')
        self.assertEqual(player.active_armor_id, 113)
        self.assertEqual(player.armor, 125)


if __name__ == '__main__':
    unittest.main(verbosity=2)
