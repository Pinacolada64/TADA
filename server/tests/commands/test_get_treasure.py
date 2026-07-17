"""tests/commands/test_get_treasure.py

Covers commands/get.py's port of SPUR.MISC.S's get.itm4 (the treasure ->
gold conversion, reached from get.itm's instr("COIN"/"DIAMOND"/"GOLD"/
"SILVER"/"JEWEL", it$) chain):

  - Picking up a "type": "treasure" item never occupies an inventory
    slot -- it converts straight to player.silver[IN_HAND] instead,
    amount = the item's own price times a random multiplier that
    depends on which of the five keywords its name contains (checked in
    SPUR's exact order, so a name matching more than one keyword, e.g.
    "gold coins", uses whichever is checked first -- COIN, not GOLD).
  - Gated on objects.json's own "type": "treasure" tag (Ryan's call)
    rather than SPUR's raw substring match, avoiding false positives
    like "gold shield" (type: shield) or "gold coffin" (type: cursed).
  - The item is marked picked_up (via the same remove_fn()/
    _record()/picked_up_items mechanism every other static room item
    uses), so it can't be re-gotten for unlimited silver farming.
"""
from __future__ import annotations

import random
import unittest
from unittest.mock import MagicMock, patch

from base_classes import PlayerMoneyTypes
from commands.get import (
    GetCommand, _is_treasure, _room_available_items,
    _treasure_conversion, _treasure_gold_multiplier,
)
from inventory import Inventory, InventoryEntry
from items import Item, ItemCategory
from player import Player


def _player(silver=0) -> Player:
    p = Player(name='Rulan')
    p.set_silver_absolute(PlayerMoneyTypes.IN_HAND, silver)
    p.inventory = Inventory(capacity=10)
    p.picked_up_items = []
    return p


class _FakeCtx:
    def __init__(self, player, server):
        self.player = player
        self.server = server
        self.client = MagicMock()
        self.client.room = 1
        self.sent: list = []

    async def send(self, *args):
        for a in args:
            if isinstance(a, list):
                self.sent.extend(a)
            else:
                self.sent.append(a)

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


def _server(items=None):
    server = MagicMock()
    server.items      = items or []
    server.weapons    = []
    server.rations    = []
    server.monsters   = []
    server.room_items = {}
    return server


class TestIsTreasure(unittest.TestCase):

    def test_treasure_type(self):
        self.assertTrue(_is_treasure({'type': 'treasure'}))

    def test_not_treasure(self):
        self.assertFalse(_is_treasure({'type': 'cursed'}))

    def test_gold_shield_is_not_treasure(self):
        # SPUR's raw substring match would have caught "gold shield" too --
        # gating on "type" instead deliberately excludes it.
        self.assertFalse(_is_treasure({'type': 'shield', 'name': 'gold shield'}))

    def test_gold_coffin_is_not_treasure(self):
        self.assertFalse(_is_treasure({'type': 'cursed', 'name': 'gold coffin'}))

    def test_none_raw(self):
        self.assertFalse(_is_treasure(None))


class TestTreasureGoldMultiplier(unittest.TestCase):

    def test_coin_uses_1_to_20_range(self):
        with patch.object(random, 'randint', return_value=99) as m:
            _treasure_gold_multiplier('rare coins')
        m.assert_called_once_with(1, 20)

    def test_diamond_uses_1_to_30_range(self):
        with patch.object(random, 'randint', return_value=99) as m:
            _treasure_gold_multiplier('huge diamond')
        m.assert_called_once_with(1, 30)

    def test_gold_uses_1_to_15_range(self):
        with patch.object(random, 'randint', return_value=99) as m:
            _treasure_gold_multiplier('gold nugget')
        m.assert_called_once_with(1, 15)

    def test_silver_uses_1_to_10_range(self):
        with patch.object(random, 'randint', return_value=99) as m:
            _treasure_gold_multiplier('silver chalice')
        m.assert_called_once_with(1, 10)

    def test_jewel_uses_1_to_8_range(self):
        with patch.object(random, 'randint', return_value=99) as m:
            _treasure_gold_multiplier('mound of jewels')
        m.assert_called_once_with(1, 8)

    def test_name_matching_multiple_keywords_uses_first_checked(self):
        # "gold coins" matches both COIN and GOLD -- COIN is checked
        # first in SPUR's instr() chain, so it should win.
        with patch.object(random, 'randint', return_value=99) as m:
            _treasure_gold_multiplier('gold coins')
        m.assert_called_once_with(1, 20)

    def test_case_insensitive(self):
        with patch.object(random, 'randint', return_value=99) as m:
            _treasure_gold_multiplier('Silver Cup')
        m.assert_called_once_with(1, 10)

    def test_unmatched_name_falls_back_to_1_to_10(self):
        with patch.object(random, 'randint', return_value=99) as m:
            _treasure_gold_multiplier('unknown Picasso')
        m.assert_called_once_with(1, 10)


class TestTreasureConversion(unittest.TestCase):

    def test_adds_price_times_multiplier_to_silver(self):
        p = _player(silver=100)
        with patch.object(random, 'randint', return_value=5):
            _treasure_conversion(p, 'gold nugget', price=3)
        self.assertEqual(p.get_silver(PlayerMoneyTypes.IN_HAND), 115)  # 100 + 3*5

    def test_message_mentions_amount_and_total(self):
        p = _player(silver=0)
        with patch.object(random, 'randint', return_value=4):
            lines = _treasure_conversion(p, 'gold nugget', price=2)
        self.assertIn('8', lines[0])

    def test_marks_unsaved_changes(self):
        p = _player()
        p.unsaved_changes = False
        _treasure_conversion(p, 'gold nugget', price=2)
        self.assertTrue(p.unsaved_changes)


class TestGetTreasureIntegration(unittest.IsolatedAsyncioTestCase):
    """Through GetCommand._pick_up() -- the actual GET code path."""

    async def test_treasure_never_added_to_inventory(self):
        p = _player()
        server = _server(items=[{'number': 37, 'name': 'gold nugget', 'type': 'treasure', 'price': 3}])
        ctx = _FakeCtx(p, server)
        item  = Item(id_number=37, name='gold nugget', category=ItemCategory.ITEM)
        entry = InventoryEntry(item=item)

        await GetCommand()._pick_up(ctx, p.inventory, 'gold nugget', entry, MagicMock())

        self.assertEqual(p.inventory.find(item_id=37), [])

    async def test_treasure_adds_silver_to_player(self):
        p = _player(silver=0)
        server = _server(items=[{'number': 37, 'name': 'gold nugget', 'type': 'treasure', 'price': 3}])
        ctx = _FakeCtx(p, server)
        item  = Item(id_number=37, name='gold nugget', category=ItemCategory.ITEM)
        entry = InventoryEntry(item=item)

        await GetCommand()._pick_up(ctx, p.inventory, 'gold nugget', entry, MagicMock())

        self.assertGreater(p.get_silver(PlayerMoneyTypes.IN_HAND), 0)

    async def test_treasure_removed_from_room(self):
        p = _player()
        server = _server(items=[{'number': 37, 'name': 'gold nugget', 'type': 'treasure', 'price': 3}])
        ctx = _FakeCtx(p, server)
        item  = Item(id_number=37, name='gold nugget', category=ItemCategory.ITEM)
        entry = InventoryEntry(item=item)
        remove_fn = MagicMock()

        await GetCommand()._pick_up(ctx, p.inventory, 'gold nugget', entry, remove_fn)

        remove_fn.assert_called_once()

    async def test_full_flow_marks_picked_up_and_blocks_refarming(self):
        """End-to-end through _room_available_items() -> GET -> a second
        'get' no longer lists (or converts) the same treasure again --
        this is the explicit anti-farming requirement."""
        # NOTE: _room_available_items() resolves item_id from raw.get(
        # 'id_number', idx + 1) -- objects.json entries have no 'id_number'
        # key (they use 'number'), so this always falls back to the item's
        # 1-based position in server.items, not its 'number' field. Setting
        # 'number' to match here (rather than a more "realistic" 37) keeps
        # this test aligned with that -- a pre-existing quirk, not something
        # this treasure-conversion change introduces or needs to fix.
        room = MagicMock()
        room.item = 1
        room.weapon = 0
        room.food = 0
        room.monster = 0

        p = _player(silver=0)
        server = _server(items=[{'number': 1, 'name': 'gold nugget', 'type': 'treasure', 'price': 3}])
        server.game_map.get_room.return_value = room
        ctx = _FakeCtx(p, server)

        available = _room_available_items(ctx)
        self.assertEqual(len(available), 1)
        name, entry, remove_fn = available[0]

        await GetCommand()._pick_up(ctx, p.inventory, name, entry, remove_fn)

        self.assertIn(1, p.picked_up_items)
        first_silver = p.get_silver(PlayerMoneyTypes.IN_HAND)
        self.assertGreater(first_silver, 0)

        # Second look at the room: item no longer offered at all.
        available_again = _room_available_items(ctx)
        self.assertEqual(available_again, [])

    async def test_non_treasure_item_unaffected(self):
        p = _player()
        server = _server(items=[{'number': 5, 'name': 'plain rock', 'type': 'junk', 'price': 1}])
        ctx = _FakeCtx(p, server)
        item  = Item(id_number=5, name='plain rock', category=ItemCategory.ITEM)
        entry = InventoryEntry(item=item)

        await GetCommand()._pick_up(ctx, p.inventory, 'plain rock', entry, MagicMock())

        self.assertNotEqual(p.inventory.find(item_id=5), [])
        self.assertEqual(p.get_silver(PlayerMoneyTypes.IN_HAND), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
