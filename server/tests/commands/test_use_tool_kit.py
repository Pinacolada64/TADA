"""tests/commands/test_use_tool_kit.py — unit tests for commands/use.py's
tool kit branch (USE tool kit).

Ported from SPUR.USE.S's 'tool' label (~lines 58-70). Traced (not
invented) from source: two independent repairs, checked unconditionally
in the same USE --

  - broken spacesuit (#134) + spacesuit parts (#135) together become a
    spacesuit (#122). Having exactly one of the two prints "You don't
    have all the parts to the spacesuit." instead; having neither says
    nothing about the spacesuit at all.
  - broken communicator (#141) alone becomes a communicator (#66).

If neither repair happens: "Playing with the tools does no good..". The
tool kit itself is never consumed (SPUR's own clr.item calls never touch
133) -- reusable across multiple repairs.
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from commands.use import UseCommand
from inventory import Inventory
from items import Item, ItemCategory


def _tool_kit() -> Item:
    return Item(id_number=133, name='tool kit', category=ItemCategory.ITEM)


def _broken_spacesuit() -> Item:
    return Item(id_number=134, name='broken spacesuit', category=ItemCategory.ITEM)


def _spacesuit_parts() -> Item:
    return Item(id_number=135, name='spacesuit parts', category=ItemCategory.ITEM)


def _broken_communicator() -> Item:
    return Item(id_number=141, name='broken communicator', category=ItemCategory.ITEM)


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
        self.server.items = [
            {'number': 122, 'name': 'spacesuit', 'type': 'misc', 'price': 9},
            {'number': 66, 'name': 'communicator', 'type': 'misc', 'price': 9},
        ]
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


class TestSpacesuitRepair(unittest.IsolatedAsyncioTestCase):

    async def test_both_parts_present_repairs_spacesuit(self):
        player = _make_player()
        player.inventory.add(_tool_kit())
        player.inventory.add(_broken_spacesuit())
        player.inventory.add(_spacesuit_parts())
        ctx = _FakeCtx(player)

        await UseCommand().execute(ctx, 'tool', 'kit')

        self.assertIn('Bingo! Using the tools, you repair the spacesuit!', ctx.flat())
        self.assertEqual(len(player.inventory.find(item_id=134)), 0)
        self.assertEqual(len(player.inventory.find(item_id=135)), 0)
        crafted = player.inventory.find(item_id=122)
        self.assertEqual(len(crafted), 1)
        self.assertEqual(crafted[0].item.name, 'spacesuit')
        self.assertTrue(player.unsaved_changes)

    async def test_tool_kit_itself_is_not_consumed(self):
        player = _make_player()
        player.inventory.add(_tool_kit())
        player.inventory.add(_broken_spacesuit())
        player.inventory.add(_spacesuit_parts())
        ctx = _FakeCtx(player)

        await UseCommand().execute(ctx, 'tool', 'kit')

        self.assertEqual(len(player.inventory.find(item_id=133)), 1)

    async def test_only_broken_suit_reports_missing_parts(self):
        player = _make_player()
        player.inventory.add(_tool_kit())
        player.inventory.add(_broken_spacesuit())
        ctx = _FakeCtx(player)

        await UseCommand().execute(ctx, 'tool', 'kit')

        self.assertIn("You don't have all the parts to the spacesuit.", ctx.flat())
        self.assertEqual(len(player.inventory.find(item_id=134)), 1)  # not consumed
        self.assertEqual(len(player.inventory.find(item_id=122)), 0)  # not crafted

    async def test_only_parts_reports_missing_broken_suit(self):
        player = _make_player()
        player.inventory.add(_tool_kit())
        player.inventory.add(_spacesuit_parts())
        ctx = _FakeCtx(player)

        await UseCommand().execute(ctx, 'tool', 'kit')

        self.assertIn("You don't have all the parts to the spacesuit.", ctx.flat())

    async def test_neither_part_present_no_spacesuit_message(self):
        player = _make_player()
        player.inventory.add(_tool_kit())
        ctx = _FakeCtx(player)

        await UseCommand().execute(ctx, 'tool', 'kit')

        self.assertNotIn('spacesuit', ctx.flat().lower())
        self.assertIn('Playing with the tools does no good..', ctx.flat())


class TestCommunicatorRepair(unittest.IsolatedAsyncioTestCase):

    async def test_broken_communicator_repaired(self):
        player = _make_player()
        player.inventory.add(_tool_kit())
        player.inventory.add(_broken_communicator())
        ctx = _FakeCtx(player)

        await UseCommand().execute(ctx, 'tool', 'kit')

        self.assertIn('You repair the communicator!', ctx.flat())
        self.assertEqual(len(player.inventory.find(item_id=141)), 0)
        crafted = player.inventory.find(item_id=66)
        self.assertEqual(len(crafted), 1)
        self.assertEqual(crafted[0].item.name, 'communicator')

    async def test_no_broken_communicator_no_message(self):
        player = _make_player()
        player.inventory.add(_tool_kit())
        player.inventory.add(_broken_spacesuit())
        player.inventory.add(_spacesuit_parts())
        ctx = _FakeCtx(player)

        await UseCommand().execute(ctx, 'tool', 'kit')

        self.assertNotIn('communicator', ctx.flat().lower())


class TestBothRepairsAtOnce(unittest.IsolatedAsyncioTestCase):

    async def test_spacesuit_and_communicator_both_repaired_in_one_use(self):
        player = _make_player()
        player.inventory.add(_tool_kit())
        player.inventory.add(_broken_spacesuit())
        player.inventory.add(_spacesuit_parts())
        player.inventory.add(_broken_communicator())
        ctx = _FakeCtx(player)

        await UseCommand().execute(ctx, 'tool', 'kit')

        flat = ctx.flat()
        self.assertIn('Bingo! Using the tools, you repair the spacesuit!', flat)
        self.assertIn('You repair the communicator!', flat)
        self.assertEqual(len(player.inventory.find(item_id=122)), 1)
        self.assertEqual(len(player.inventory.find(item_id=66)), 1)


class TestNothingToRepair(unittest.IsolatedAsyncioTestCase):

    async def test_no_repairable_items_says_no_good(self):
        player = _make_player()
        player.inventory.add(_tool_kit())
        ctx = _FakeCtx(player)

        await UseCommand().execute(ctx, 'tool', 'kit')

        self.assertIn('Playing with the tools does no good..', ctx.flat())


if __name__ == '__main__':
    unittest.main(verbosity=2)
