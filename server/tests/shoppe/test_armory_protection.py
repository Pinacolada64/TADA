"""tests/shoppe/test_armory.py — shoppe/armory.py's protection() (buying
armor/shields at the regular Merchant Shoppe).

Regression coverage for the 2026-08-08 per-item durability redesign:
buying protection used to auto-equip (set player.armor/player.shield and,
for shields only, active_shield_id directly), bypassing WEAR/USE entirely
and leaving armor purchases -- unlike shield ones -- never setting
active_armor_id at all. It now just adds a fresh (condition=100), properly
typed item to inventory, same as any other purchase; equipping is an
explicit WEAR/USE step.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from base_classes import PlayerMoneyTypes
from flags import PlayerFlags
from inventory import Inventory
from item_system import ItemType
from items import Item, ItemCategory
from player import Player
from shoppe.armory import _condition_label, _repair, protection


def _new_player(name: str = 'Rulan') -> Player:
    player = Player(name=name)
    player.clear_flag(PlayerFlags.DEBUG_MODE)
    player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 100000)
    player.inventory = Inventory()
    player.char_class = None
    player.char_race  = None
    return player


class _FakeCtx:
    def __init__(self, responses, player):
        self._q = list(responses)
        self.sent: list = []
        self.player = player

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


class TestBuyingArmorDoesNotAutoEquip(unittest.IsolatedAsyncioTestCase):

    async def test_buying_leather_armor_does_not_set_player_armor(self):
        player = _new_player()
        # listing position 9 = leather armor (objects.json #24) -- confirm, then leave
        ctx = _FakeCtx(['9', 'y', 'q'], player)
        await protection(ctx)
        self.assertIsNone(player.armor)
        self.assertIsNone(player.active_armor_id)

    async def test_buying_leather_armor_adds_a_wearable_item(self):
        player = _new_player()
        ctx = _FakeCtx(['9', 'y', 'q'], player)
        await protection(ctx)
        entries = player.inventory.find(item_id=24)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].item.type, ItemType.ARMOR)
        self.assertEqual(entries[0].item.condition, 100)

    async def test_buying_a_shield_does_not_auto_equip_either(self):
        # listing position 3 = small shield (objects.json #4) -- confirm, then leave
        player = _new_player()
        ctx = _FakeCtx(['3', 'y', 'q'], player)
        await protection(ctx)
        self.assertIsNone(player.shield)
        self.assertIsNone(player.active_shield_id)
        entries = player.inventory.find(item_id=4)
        self.assertEqual(entries[0].item.type, ItemType.SHIELD)
        self.assertEqual(entries[0].item.condition, 100)

    async def test_bought_armor_is_actually_wearable(self):
        from commands.wear import WearCommand

        player = _new_player()
        ctx = _FakeCtx(['9', 'y', 'q'], player)
        await protection(ctx)
        ctx.sent.clear()
        await WearCommand().execute(ctx, 'leather', 'armor')
        self.assertEqual(player.active_armor_id, 24)
        self.assertEqual(player.armor, 100)

    async def test_hint_message_shown_for_non_expert(self):
        player = _new_player()
        self.assertFalse(player.is_expert)
        ctx = _FakeCtx(['9', 'y', 'q'], player)
        await protection(ctx)
        self.assertIn('WEAR it to put it on.', ctx._flat())


def _damaged_armor(condition: int, item_id: int = 24, price: int = 3) -> Item:
    item = Item(id_number=item_id, name='leather armor', category=ItemCategory.ITEM,
                type=ItemType.ARMOR, condition=condition, price=price)
    return item


class TestConditionLabel(unittest.TestCase):

    def test_tiers(self):
        self.assertEqual(_condition_label(100), 'EXCELLENT')
        self.assertEqual(_condition_label(80), 'GOOD')
        self.assertEqual(_condition_label(60), 'SERVICABLE')
        self.assertEqual(_condition_label(30), 'POOR')
        self.assertEqual(_condition_label(10), 'TERRIBLE')
        self.assertEqual(_condition_label(0), 'TERRIBLE')


class TestRepair(unittest.IsolatedAsyncioTestCase):
    """shoppe/armory.py's _repair() -- adapted from origin/skip's
    SPUR.ARMORY.S, absent from master before this. Repairs a carried
    armor/shield item's condition back to 100% for silver."""

    async def test_listing_shows_condition_and_label(self):
        player = _new_player()
        player.inventory.add(_damaged_armor(condition=60))
        ctx = _FakeCtx(['q'], player)
        await _repair(ctx, player, player.inventory)
        flat = ctx._flat()
        self.assertIn('leather armor', flat)
        self.assertIn('60%', flat)
        self.assertIn('SERVICABLE', flat)

    async def test_repair_restores_condition_and_charges_silver(self):
        player = _new_player()
        player.inventory.add(_damaged_armor(condition=40, price=3))
        # select item 1, confirm, then leave
        ctx = _FakeCtx(['1', 'y', 'q'], player)
        await _repair(ctx, player, player.inventory)
        entry = player.inventory.find(item_id=24)[0]
        self.assertEqual(entry.item.condition, 100)
        # missing=60, price=3 -> cost=180
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 100000 - 180)

    async def test_declining_confirmation_leaves_condition_unchanged(self):
        player = _new_player()
        player.inventory.add(_damaged_armor(condition=40))
        ctx = _FakeCtx(['1', 'n', 'q'], player)
        await _repair(ctx, player, player.inventory)
        entry = player.inventory.find(item_id=24)[0]
        self.assertEqual(entry.item.condition, 40)
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 100000)

    async def test_already_full_condition_refuses(self):
        player = _new_player()
        player.inventory.add(_damaged_armor(condition=100))
        ctx = _FakeCtx(['1', 'q'], player)
        await _repair(ctx, player, player.inventory)
        self.assertIn('already in perfect condition', ctx._flat())
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 100000)

    async def test_insufficient_silver_refuses(self):
        player = _new_player()
        player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 10)
        player.inventory.add(_damaged_armor(condition=40, price=3))
        ctx = _FakeCtx(['1', 'y', 'q'], player)
        await _repair(ctx, player, player.inventory)
        entry = player.inventory.find(item_id=24)[0]
        self.assertEqual(entry.item.condition, 40)
        self.assertIn('do not have enough silver', ctx._flat())

    async def test_no_armor_or_shield_carried(self):
        player = _new_player()
        ctx = _FakeCtx([], player)
        await _repair(ctx, player, player.inventory)
        self.assertIn("don't have any armor or shields", ctx._flat())

    async def test_repairing_the_worn_item_refreshes_live_rating(self):
        from commands.wear import WearCommand

        player = _new_player()
        armor = _damaged_armor(condition=40, price=3)
        player.inventory.add(armor)
        wear_ctx = _FakeCtx([], player)
        await WearCommand().execute(wear_ctx, 'leather', 'armor')
        self.assertEqual(player.armor, 40)

        repair_ctx = _FakeCtx(['1', 'y', 'q'], player)
        await _repair(repair_ctx, player, player.inventory)
        self.assertEqual(player.armor, 100)

    async def test_repairing_an_unworn_item_does_not_touch_the_rating(self):
        player = _new_player()
        player.armor = 0
        player.inventory.add(_damaged_armor(condition=40, price=3))
        # active_armor_id left unset -- this item was never worn
        ctx = _FakeCtx(['1', 'y', 'q'], player)
        await _repair(ctx, player, player.inventory)
        self.assertEqual(player.armor, 0)


class TestProtectionRoutesToRepair(unittest.IsolatedAsyncioTestCase):

    async def test_r_choice_opens_repair_flow(self):
        player = _new_player()
        player.inventory.add(_damaged_armor(condition=40))
        # R -> repair menu -> leave repair -> leave protection
        ctx = _FakeCtx(['r', 'q', 'q'], player)
        await protection(ctx)
        self.assertIn("What kin eye fix fer ye?", ctx._flat())


if __name__ == '__main__':
    unittest.main(verbosity=2)
