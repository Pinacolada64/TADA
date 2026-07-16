"""tests/commands/test_inv_allies.py — commands/inv.py's ally-carried-items
section. INV previously only ever showed the player's own inventory --
allies carrying gifted items (ally.items) were invisible here entirely.
Ryan's request.
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from bar.ally_data import Ally, AllyFlags
from commands.inv import InvCommand
from inventory import Inventory, InventoryEntry
from items import Item, ItemCategory
from party import Party


def _make_player(party=None, own_items=None):
    player = MagicMock()
    inv = Inventory(capacity=10)
    for item in (own_items or []):
        inv.add(item)
    player.inventory = inv
    player.max_inventory_size = 10
    player.party = party if party is not None else Party()
    return player


def _make_ctx(player):
    ctx = MagicMock()
    ctx.player = player
    ctx.send = AsyncMock()
    return ctx


def _sent_text(ctx):
    out = []
    for call in ctx.send.await_args_list:
        for a in call.args:
            if isinstance(a, list):
                out.extend(str(x) for x in a)
            else:
                out.append(str(a))
    return '\n'.join(out)


def _mount(name='Trigger', saddlebags=False):
    flags = [AllyFlags.MOUNT]
    if saddlebags:
        flags.append(AllyFlags.SADDLEBAGS)
    return Ally(name=name, gender='m', strength=20, to_hit=0, flags=flags)


def _plain_ally(name='Grog'):
    return Ally(name=name, gender='m', strength=15, to_hit=5)


class TestInvAllySection(unittest.IsolatedAsyncioTestCase):
    async def test_no_allies_no_extra_section(self):
        ctx = _make_ctx(_make_player())
        await InvCommand().execute(ctx)
        text = _sent_text(ctx)
        self.assertNotIn('pack', text.lower())

    async def test_mount_without_saddlebags_shown_as_carrying_nothing(self):
        mount = _mount(saddlebags=False)
        player = _make_player(party=Party(members=[mount]))
        ctx = _make_ctx(player)
        await InvCommand().execute(ctx)
        text = _sent_text(ctx)
        self.assertIn('Trigger: no saddlebags (nothing carried).', text)

    async def test_mount_with_saddlebags_and_items_shown(self):
        mount = _mount(saddlebags=True)
        torch = Item(id_number=1, name='Torch', category=ItemCategory.ITEM)
        mount.items = [InventoryEntry(item=torch)]
        player = _make_player(party=Party(members=[mount]))
        ctx = _make_ctx(player)
        await InvCommand().execute(ctx)
        text = _sent_text(ctx)
        self.assertIn("Trigger's pack (1/5 items):", text)
        self.assertIn('Torch', text)

    async def test_mount_with_saddlebags_but_empty(self):
        mount = _mount(saddlebags=True)
        mount.items = []
        player = _make_player(party=Party(members=[mount]))
        ctx = _make_ctx(player)
        await InvCommand().execute(ctx)
        text = _sent_text(ctx)
        self.assertIn('Trigger: carrying nothing.', text)

    async def test_non_mount_ally_no_capacity_shown(self):
        ally = _plain_ally('Grog')
        rope = Item(id_number=2, name='Rope', category=ItemCategory.ITEM)
        ally.items = [InventoryEntry(item=rope)]
        player = _make_player(party=Party(members=[ally]))
        ctx = _make_ctx(player)
        await InvCommand().execute(ctx)
        text = _sent_text(ctx)
        self.assertIn("Grog's pack (1 items):", text)
        self.assertNotIn('/5', text)

    async def test_ally_section_shown_even_when_player_inventory_empty(self):
        mount = _mount(saddlebags=True)
        torch = Item(id_number=1, name='Torch', category=ItemCategory.ITEM)
        mount.items = [InventoryEntry(item=torch)]
        player = _make_player(party=Party(members=[mount]))  # player.inventory empty
        ctx = _make_ctx(player)
        await InvCommand().execute(ctx)
        text = _sent_text(ctx)
        self.assertIn('You are carrying nothing.', text)
        self.assertIn("Trigger's pack", text)

    async def test_test_mode_skips_ally_section(self):
        mount = _mount(saddlebags=True)
        torch = Item(id_number=1, name='Torch', category=ItemCategory.ITEM)
        mount.items = [InventoryEntry(item=torch)]
        player = _make_player(party=Party(members=[mount]))
        ctx = _make_ctx(player)
        await InvCommand().execute(ctx, '#test')
        text = _sent_text(ctx)
        self.assertNotIn("Trigger's pack", text)


if __name__ == '__main__':
    unittest.main()
