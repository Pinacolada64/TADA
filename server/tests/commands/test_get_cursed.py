"""tests/commands/test_get_cursed.py

Covers commands/get.py's port of SPUR.MISC.S's 'cursed' subroutine
(i1$/wt$/ft$="C" checks in get.itm/get.wpn/get.fd, all three routed to
the same label):

  - Picking up a cursed item/weapon/food always inflicts INT+HP damage
    scaled by the item's own price (or a flat 10 if it has none), split
    randomly between the two -- unconditionally, whether or not the item
    was examined first (EXAMINE only reveals the "Cursed" flavor text in
    advance; it doesn't set any flag GET checks).
  - The cursed item is never added to inventory either way.
  - Fatal if HP would drop to 0 or below -- this codebase's centralized
    post-command check (simple_server.py) picks up hit_points<=0 and
    runs the full death/respawn flow, mirroring survival.py's own
    inline "just set hit_points=0" pattern for non-combat death.
  - objects.json uses "type": "cursed"; weapons.json/rations.json (no
    "type" field) use "kind": "cursed" instead -- both need to work.
"""
from __future__ import annotations

import random
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from base_classes import PlayerStat
from commands.get import GetCommand, _cursed_penalty, _is_cursed, _raw_item_data
from inventory import Inventory, InventoryEntry
from items import Item, ItemCategory
from player import Player


def _player(hp=20, intel=10) -> Player:
    p = Player(name='Rulan')
    p.hit_points = hp
    p.stats[PlayerStat.INT] = intel
    p.inventory = Inventory(capacity=10)
    return p


class _FakeCtx:
    def __init__(self, player, server):
        self.player = player
        self.server = server
        self.client = MagicMock()
        self.sent: list = []

    async def send(self, *args):
        for a in args:
            if isinstance(a, list):
                self.sent.extend(a)
            else:
                self.sent.append(a)

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


def _server(items=None, weapons=None, rations=None):
    server = MagicMock()
    server.items      = items or []
    server.weapons    = weapons or []
    server.rations    = rations or []
    server.room_items = {}
    return server


class TestIsCursed(unittest.TestCase):

    def test_objects_json_type_field(self):
        self.assertTrue(_is_cursed({'type': 'cursed'}))

    def test_rations_json_kind_field(self):
        self.assertTrue(_is_cursed({'kind': 'cursed'}))

    def test_not_cursed(self):
        self.assertFalse(_is_cursed({'type': 'treasure'}))

    def test_none_raw(self):
        self.assertFalse(_is_cursed(None))

    def test_empty_dict(self):
        self.assertFalse(_is_cursed({}))


class TestRawItemData(unittest.TestCase):

    def test_finds_item_category_in_items_pool(self):
        server = _server(items=[{'number': 20, 'name': 'gold coffin', 'type': 'cursed', 'price': 3}])
        ctx = _FakeCtx(None, server)
        item = Item(id_number=20, name='gold coffin', category=ItemCategory.ITEM)
        raw = _raw_item_data(ctx, item)
        self.assertEqual(raw['name'], 'gold coffin')

    def test_finds_weapon_category_in_weapons_pool(self):
        server = _server(
            items=[{'number': 20, 'name': 'decoy', 'type': 'cursed', 'price': 99}],
            weapons=[{'number': 20, 'name': 'cursed blade', 'kind': 'cursed', 'price': 12}],
        )
        ctx = _FakeCtx(None, server)
        item = Item(id_number=20, name='cursed blade', category=ItemCategory.WEAPON)
        raw = _raw_item_data(ctx, item)
        self.assertEqual(raw['name'], 'cursed blade')

    def test_finds_food_category_in_rations_pool(self):
        server = _server(rations=[{'number': 31, 'name': 'EMBALMING FLUID', 'kind': 'cursed', 'price': 50}])
        ctx = _FakeCtx(None, server)
        item = Item(id_number=31, name='EMBALMING FLUID', category=ItemCategory.FOOD)
        raw = _raw_item_data(ctx, item)
        self.assertEqual(raw['name'], 'EMBALMING FLUID')

    def test_no_match_returns_none(self):
        server = _server(items=[])
        ctx = _FakeCtx(None, server)
        item = Item(id_number=999, name='nothing', category=ItemCategory.ITEM)
        self.assertIsNone(_raw_item_data(ctx, item))

    def test_no_id_number_returns_none(self):
        server = _server(items=[{'number': 1, 'name': 'x'}])
        ctx = _FakeCtx(None, server)
        item = Item(name='no id', category=ItemCategory.ITEM)
        self.assertIsNone(_raw_item_data(ctx, item))


class TestCursedPenalty(unittest.TestCase):

    def test_damages_intelligence_and_hp(self):
        p = _player(hp=50, intel=18)
        with patch.object(random, 'randint', return_value=4):
            _cursed_penalty(p, 'gold coffin', price=10)
        # severity=10, intel_loss=4 (mocked), hp_loss=10-4=6
        self.assertEqual(p.stats[PlayerStat.INT], 14)
        self.assertEqual(p.hit_points, 44)

    def test_zero_price_uses_minimum_severity_of_ten(self):
        p = _player(hp=50, intel=18)
        with patch.object(random, 'randint', return_value=0):
            _cursed_penalty(p, 'x', price=0)
        # severity=10 (floor), intel_loss=0, hp_loss=10
        self.assertEqual(p.hit_points, 40)

    def test_intelligence_never_goes_negative(self):
        p = _player(hp=50, intel=2)
        with patch.object(random, 'randint', return_value=100):
            _cursed_penalty(p, 'x', price=100)
        self.assertEqual(p.stats[PlayerStat.INT], 0)

    def test_lethal_curse_sets_hp_to_zero_not_negative(self):
        p = _player(hp=5, intel=18)
        with patch.object(random, 'randint', return_value=0):
            lines = _cursed_penalty(p, 'x', price=20)
        self.assertEqual(p.hit_points, 0)
        self.assertTrue(any('slain' in l.lower() for l in lines))

    def test_survives_curse_shows_examine_reminder(self):
        p = _player(hp=50, intel=18)
        with patch.object(random, 'randint', return_value=1):
            lines = _cursed_penalty(p, 'x', price=5)
        self.assertTrue(any('examining' in l.lower() for l in lines))

    def test_names_the_item_in_first_line(self):
        p = _player(hp=50, intel=18)
        lines = _cursed_penalty(p, 'gold coffin', price=5)
        self.assertIn('gold coffin is Cursed!', lines)

    def test_marks_unsaved_changes(self):
        p = _player()
        p.unsaved_changes = False
        _cursed_penalty(p, 'x', price=5)
        self.assertTrue(p.unsaved_changes)


class TestGetCursedItemIntegration(unittest.IsolatedAsyncioTestCase):
    """Through GetCommand._pick_up() -- the actual GET code path."""

    async def test_cursed_item_never_added_to_inventory(self):
        p = _player(hp=50, intel=18)
        server = _server(items=[{'number': 20, 'name': 'gold coffin', 'type': 'cursed', 'price': 3}])
        ctx = _FakeCtx(p, server)
        item  = Item(id_number=20, name='gold coffin', category=ItemCategory.ITEM)
        entry = InventoryEntry(item=item)
        remove_fn = MagicMock()

        await GetCommand()._pick_up(ctx, p.inventory, 'gold coffin', entry, remove_fn)

        self.assertEqual(p.inventory.find(item_id=20), [])

    async def test_cursed_item_removed_from_room(self):
        p = _player(hp=50, intel=18)
        server = _server(items=[{'number': 20, 'name': 'gold coffin', 'type': 'cursed', 'price': 3}])
        ctx = _FakeCtx(p, server)
        item  = Item(id_number=20, name='gold coffin', category=ItemCategory.ITEM)
        entry = InventoryEntry(item=item)
        remove_fn = MagicMock()

        await GetCommand()._pick_up(ctx, p.inventory, 'gold coffin', entry, remove_fn)

        remove_fn.assert_called_once()

    async def test_cursed_item_sends_curse_message(self):
        p = _player(hp=50, intel=18)
        server = _server(items=[{'number': 20, 'name': 'gold coffin', 'type': 'cursed', 'price': 3}])
        ctx = _FakeCtx(p, server)
        item  = Item(id_number=20, name='gold coffin', category=ItemCategory.ITEM)
        entry = InventoryEntry(item=item)

        await GetCommand()._pick_up(ctx, p.inventory, 'gold coffin', entry, MagicMock())

        self.assertIn('gold coffin is Cursed!', ctx._flat())

    async def test_cursed_food_item_uses_kind_field(self):
        p = _player(hp=50, intel=18)
        server = _server(rations=[{'number': 31, 'name': 'EMBALMING FLUID', 'kind': 'cursed', 'price': 50}])
        ctx = _FakeCtx(p, server)
        item  = Item(id_number=31, name='EMBALMING FLUID', category=ItemCategory.FOOD)
        entry = InventoryEntry(item=item)

        await GetCommand()._pick_up(ctx, p.inventory, 'EMBALMING FLUID', entry, MagicMock())

        self.assertIn('EMBALMING FLUID is Cursed!', ctx._flat())
        self.assertEqual(p.inventory.find(item_id=31), [])

    async def test_non_cursed_item_unaffected(self):
        p = _player(hp=50, intel=18)
        server = _server(items=[{'number': 5, 'name': 'plain rock', 'type': 'junk', 'price': 1}])
        ctx = _FakeCtx(p, server)
        item  = Item(id_number=5, name='plain rock', category=ItemCategory.ITEM)
        entry = InventoryEntry(item=item)

        await GetCommand()._pick_up(ctx, p.inventory, 'plain rock', entry, MagicMock())

        self.assertNotEqual(p.inventory.find(item_id=5), [])
        self.assertNotIn('Cursed', ctx._flat())

    async def test_lethal_curse_zeroes_hp(self):
        p = _player(hp=2, intel=18)
        server = _server(items=[{'number': 20, 'name': 'gold coffin', 'type': 'cursed', 'price': 50}])
        ctx = _FakeCtx(p, server)
        item  = Item(id_number=20, name='gold coffin', category=ItemCategory.ITEM)
        entry = InventoryEntry(item=item)

        with patch.object(random, 'randint', return_value=0):
            await GetCommand()._pick_up(ctx, p.inventory, 'gold coffin', entry, MagicMock())

        self.assertEqual(p.hit_points, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
