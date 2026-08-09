"""tests/commands/test_inv_worn_condition.py — INV tags the equipped
armor/shield entry with its real condition (2026-08-08 per-item
durability redesign), mirroring the existing ammo-carrier
[cur/cap rounds] display.
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from commands.inv import InvCommand
from inventory import Inventory
from item_system import ItemType
from items import Item, ItemCategory
from party import Party


def _item(name, item_id, itype, condition) -> Item:
    item = Item(id_number=item_id, name=name, category=ItemCategory.ITEM)
    item.type = itype
    item.condition = condition
    return item


def _make_player():
    player = MagicMock()
    player.inventory = Inventory(capacity=10)
    player.max_inventory_size = 10
    player.party = Party()
    player.active_armor_id  = None
    player.active_shield_id = None
    return player


def _make_ctx(player):
    ctx = MagicMock()
    ctx.player = player
    ctx.send = AsyncMock()
    return ctx


def _sent_text(ctx) -> str:
    out = []
    for call in ctx.send.await_args_list:
        for a in call.args:
            if isinstance(a, list):
                out.extend(str(x) for x in a)
            else:
                out.append(str(a))
    return '\n'.join(out)


class TestInvWornCondition(unittest.IsolatedAsyncioTestCase):

    async def test_worn_shield_shows_condition_tag(self):
        player = _make_player()
        shield = _item('small shield', 4, ItemType.SHIELD, condition=65)
        player.inventory.add(shield)
        player.active_shield_id = 4
        ctx = _make_ctx(player)
        await InvCommand().execute(ctx)
        self.assertIn('small shield [65% left]', _sent_text(ctx))

    async def test_unworn_armor_has_no_tag(self):
        player = _make_player()
        armor = _item('leather armor', 24, ItemType.ARMOR, condition=80)
        player.inventory.add(armor)
        ctx = _make_ctx(player)
        await InvCommand().execute(ctx)
        text = _sent_text(ctx)
        self.assertIn('leather armor', text)
        self.assertNotIn('left', text)

    async def test_worn_armor_and_worn_shield_both_tagged(self):
        player = _make_player()
        armor  = _item('leather armor', 24, ItemType.ARMOR,  condition=90)
        shield = _item('small shield',  4,  ItemType.SHIELD, condition=40)
        player.inventory.add(armor)
        player.inventory.add(shield)
        player.active_armor_id  = 24
        player.active_shield_id = 4
        ctx = _make_ctx(player)
        await InvCommand().execute(ctx)
        text = _sent_text(ctx)
        self.assertIn('leather armor [90% left]', text)
        self.assertIn('small shield [40% left]', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
