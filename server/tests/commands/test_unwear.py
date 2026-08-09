"""tests/commands/test_unwear.py — commands/unwear.py: UNWEAR (take off
equipped armor/shield). Sibling of commands/unready.py's UnreadyCommand,
new as part of the 2026-08-08 per-item durability redesign that made
WEAR/USE non-consuming.

Run with:
    python -m pytest tests/commands/test_unwear.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from commands.unwear import UnwearCommand
from inventory import Inventory
from item_system import ItemType
from items import Item, ItemCategory


def _item(name, item_id, itype) -> Item:
    item = Item(id_number=item_id, name=name, category=ItemCategory.ITEM)
    item.type = itype
    return item


def _make_player():
    player = MagicMock()
    player.name = 'Rulan'
    player.inventory = Inventory()
    player.char_class = None
    player.char_race  = None
    player.active_armor_id  = None
    player.active_shield_id = None
    player.armor  = 0
    player.shield = 0
    return player


class _FakeCtx:
    def __init__(self, player, prompt_reply: str = ''):
        self.player = player
        self._sent: list[str] = []
        self._prompt_reply = prompt_reply

    async def send(self, msg, **kwargs):
        if isinstance(msg, list):
            self._sent.extend(str(m) for m in msg)
        else:
            self._sent.append(str(msg))

    async def prompt(self, *args, **kwargs):
        return self._prompt_reply

    def sent(self) -> str:
        return '\n'.join(self._sent)


def _equip(player, slot: str, item: Item) -> None:
    player.inventory.add(item)
    setattr(player, f'active_{slot}_id', item.id_number)
    setattr(player, slot, 100)


class TestUnwearSingleSlot(unittest.IsolatedAsyncioTestCase):

    async def test_unwear_bare_takes_off_the_only_worn_piece(self):
        player = _make_player()
        armor = _item('leather armor', 24, ItemType.ARMOR)
        _equip(player, 'armor', armor)
        ctx = _FakeCtx(player)
        await UnwearCommand().execute(ctx)
        self.assertIsNone(player.active_armor_id)
        self.assertEqual(player.armor, 0)
        self.assertIn('leather armor', ctx.sent())

    async def test_unwear_does_not_remove_the_item_from_inventory(self):
        player = _make_player()
        shield = _item('small shield', 4, ItemType.SHIELD)
        _equip(player, 'shield', shield)
        ctx = _FakeCtx(player)
        await UnwearCommand().execute(ctx)
        self.assertEqual(len(player.inventory.find(item_id=4)), 1)

    async def test_unwear_nothing_worn_says_so(self):
        player = _make_player()
        ctx = _FakeCtx(player)
        await UnwearCommand().execute(ctx)
        self.assertIn('not wearing', ctx.sent().lower())


class TestUnwearBySlotName(unittest.IsolatedAsyncioTestCase):

    async def test_unwear_shield_leaves_armor_worn(self):
        player = _make_player()
        _equip(player, 'armor', _item('leather armor', 24, ItemType.ARMOR))
        _equip(player, 'shield', _item('small shield', 4, ItemType.SHIELD))
        ctx = _FakeCtx(player)
        await UnwearCommand().execute(ctx, 'shield')
        self.assertIsNone(player.active_shield_id)
        self.assertEqual(player.active_armor_id, 24)

    async def test_unwear_by_item_name(self):
        player = _make_player()
        _equip(player, 'armor', _item('leather armor', 24, ItemType.ARMOR))
        ctx = _FakeCtx(player)
        await UnwearCommand().execute(ctx, 'leather', 'armor')
        self.assertIsNone(player.active_armor_id)


class TestUnwearBothWornPrompts(unittest.IsolatedAsyncioTestCase):

    async def test_bare_unwear_with_both_worn_prompts_and_removes_choice(self):
        player = _make_player()
        _equip(player, 'armor', _item('leather armor', 24, ItemType.ARMOR))
        _equip(player, 'shield', _item('small shield', 4, ItemType.SHIELD))
        ctx = _FakeCtx(player, prompt_reply='shield')
        await UnwearCommand().execute(ctx)
        self.assertIsNone(player.active_shield_id)
        self.assertEqual(player.active_armor_id, 24)

    async def test_bare_unwear_with_both_worn_cancel_on_blank(self):
        player = _make_player()
        _equip(player, 'armor', _item('leather armor', 24, ItemType.ARMOR))
        _equip(player, 'shield', _item('small shield', 4, ItemType.SHIELD))
        ctx = _FakeCtx(player, prompt_reply='')
        await UnwearCommand().execute(ctx)
        self.assertEqual(player.active_armor_id, 24)
        self.assertEqual(player.active_shield_id, 4)


if __name__ == '__main__':
    unittest.main(verbosity=2)
