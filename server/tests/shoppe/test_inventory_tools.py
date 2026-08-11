"""tests/shoppe/test_inventory_tools.py — shoppe/inventory_tools.py's
[I]nventory (view/sort/drop) and [T]ransfer (to party ally/mount) tools,
plus shoppe/main.py's conditional [T] menu gating.
"""
import unittest
from unittest.mock import AsyncMock, MagicMock

from bar.ally_data import Ally, AllyFlags, AllyStatus
from inventory import Inventory, InventoryEntry
from items import Item, ItemCategory
from party import Party


def _servant_ally(name='Grog', flags=None):
    ally = Ally(name=name, gender='m', strength=15, to_hit=5, flags=flags or [])
    ally.status = AllyStatus.SERVANT
    ally.items = []
    return ally


def _mount(name='Trigger', saddlebags=True):
    flags = [AllyFlags.MOUNT]
    if saddlebags:
        flags.append(AllyFlags.SADDLEBAGS)
    return _servant_ally(name, flags=flags)


def _make_player(party=None, own_items=None, capacity=10):
    player = MagicMock()
    inv = Inventory(capacity=capacity)
    for item in (own_items or []):
        inv.add(item)
    player.inventory = inv
    player.max_inventory_size = capacity
    player.party = party if party is not None else Party()
    player.is_expert = True
    player.unsaved_changes = False
    player.readied_weapon = None
    player.active_armor_id = None
    player.active_shield_id = None
    return player


def _make_ctx(player, prompts):
    ctx = MagicMock()
    ctx.player = player
    ctx.send = AsyncMock()
    it = iter(prompts)
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(it, None))
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


class TestHasTransferTargets(unittest.TestCase):
    def test_false_with_no_party(self):
        from shoppe.inventory_tools import has_transfer_targets
        player = _make_player()
        self.assertFalse(has_transfer_targets(player))

    def test_true_with_ally(self):
        from shoppe.inventory_tools import has_transfer_targets
        player = _make_player(party=Party(members=[_servant_ally()]))
        self.assertTrue(has_transfer_targets(player))

    def test_true_with_mount(self):
        from shoppe.inventory_tools import has_transfer_targets
        player = _make_player(party=Party(members=[_mount()]))
        self.assertTrue(has_transfer_targets(player))

    def test_false_with_free_status_ally(self):
        """A FREE-status party entry (not actually owned/hired) shouldn't count."""
        from shoppe.inventory_tools import has_transfer_targets
        wild = Ally(name='Wildling', gender='m', strength=10, to_hit=0)
        player = _make_player(party=Party(members=[wild]))
        self.assertFalse(has_transfer_targets(player))


class TestInventoryMain(unittest.IsolatedAsyncioTestCase):
    async def test_lists_pack_contents(self):
        from shoppe.inventory_tools import inventory_main
        torch = Item(id_number=1, name='Torch', category=ItemCategory.ITEM)
        player = _make_player(own_items=[torch])
        ctx = _make_ctx(player, [''])
        await inventory_main(ctx)
        self.assertIn('Torch', _sent_text(ctx))

    async def test_sort_reorders_by_category(self):
        from shoppe.inventory_tools import inventory_main
        rope = Item(id_number=1, name='Rope', category=ItemCategory.ITEM)
        sword = Item(id_number=2, name='Sword', category=ItemCategory.WEAPON)
        player = _make_player(own_items=[rope, sword])
        ctx = _make_ctx(player, ['s', ''])
        await inventory_main(ctx)
        names = [getattr(e.item, 'name') for e in player.inventory]
        self.assertEqual(names, ['Sword', 'Rope'])
        self.assertTrue(player.unsaved_changes)

    async def test_drop_removes_item_after_confirmation(self):
        from shoppe.inventory_tools import inventory_main
        torch = Item(id_number=1, name='Torch', category=ItemCategory.ITEM)
        player = _make_player(own_items=[torch])
        ctx = _make_ctx(player, ['d', '1', 'y', ''])
        await inventory_main(ctx)
        self.assertEqual(len(player.inventory), 0)
        self.assertIn('You discard the Torch.', _sent_text(ctx))

    async def test_drop_declined_keeps_item(self):
        from shoppe.inventory_tools import inventory_main
        torch = Item(id_number=1, name='Torch', category=ItemCategory.ITEM)
        player = _make_player(own_items=[torch])
        ctx = _make_ctx(player, ['d', '1', 'n', ''])
        await inventory_main(ctx)
        self.assertEqual(len(player.inventory), 1)


class TestTransferMain(unittest.IsolatedAsyncioTestCase):
    async def test_no_targets_declines(self):
        from shoppe.inventory_tools import transfer_main
        torch = Item(id_number=1, name='Torch', category=ItemCategory.ITEM)
        player = _make_player(own_items=[torch])
        ctx = _make_ctx(player, [])
        await transfer_main(ctx)
        self.assertIn('no party members or horse to send anything to', _sent_text(ctx))
        self.assertEqual(len(player.inventory), 1)

    async def test_transfers_item_to_ally(self):
        from shoppe.inventory_tools import transfer_main
        torch = Item(id_number=1, name='Torch', category=ItemCategory.ITEM)
        ally = _servant_ally('Grog')
        player = _make_player(party=Party(members=[ally]), own_items=[torch])
        ctx = _make_ctx(player, ['1', '1'])
        await transfer_main(ctx)
        self.assertEqual(len(player.inventory), 0)
        self.assertEqual(len(ally.items), 1)
        self.assertEqual(ally.items[0].item.name, 'Torch')
        self.assertIn('You hand the Torch to Grog.', _sent_text(ctx))
        self.assertTrue(player.unsaved_changes)

    async def test_mount_without_saddlebags_refuses(self):
        from shoppe.inventory_tools import transfer_main
        torch = Item(id_number=1, name='Torch', category=ItemCategory.ITEM)
        mount = _mount('Trigger', saddlebags=False)
        player = _make_player(party=Party(members=[mount]), own_items=[torch])
        ctx = _make_ctx(player, ['1', '1'])
        await transfer_main(ctx)
        self.assertEqual(len(player.inventory), 1)
        self.assertIn('needs saddlebags first', _sent_text(ctx))

    async def test_mount_full_saddlebags_refuses(self):
        from shoppe.inventory_tools import transfer_main
        torch = Item(id_number=1, name='Torch', category=ItemCategory.ITEM)
        mount = _mount('Trigger', saddlebags=True)
        mount.items = [
            InventoryEntry(item=Item(id_number=100 + i, name=f'Junk{i}', category=ItemCategory.ITEM))
            for i in range(5)
        ]
        player = _make_player(party=Party(members=[mount]), own_items=[torch])
        ctx = _make_ctx(player, ['1', '1'])
        await transfer_main(ctx)
        self.assertEqual(len(player.inventory), 1)
        self.assertIn("saddlebags are full", _sent_text(ctx))

    async def test_transfer_clears_readied_weapon(self):
        from shoppe.inventory_tools import transfer_main
        from items import Weapon
        weapon = Weapon(id_number=5, name='Dagger', category=ItemCategory.WEAPON)
        ally = _servant_ally('Grog')
        player = _make_player(party=Party(members=[ally]), own_items=[weapon])
        player.readied_weapon = weapon
        player.is_expert = False
        ctx = _make_ctx(player, ['1', '1'])
        await transfer_main(ctx)
        self.assertIsNone(player.readied_weapon)
        self.assertIn('no longer wielding', _sent_text(ctx))


class TestShoppeMenuGating(unittest.TestCase):
    """shoppe/main.py's [T]ransfer entry should only appear once there's a
    party ally or horse to send items to; [I]nventory is always offered."""

    def test_inventory_always_listed(self):
        from shoppe.main import _menu_entries
        ctx = MagicMock()
        ctx.player = _make_player()
        keys = [key for key, _, _ in _menu_entries(ctx)]
        self.assertIn('I', keys)

    def test_transfer_hidden_with_no_party(self):
        from shoppe.main import _menu_entries
        ctx = MagicMock()
        ctx.player = _make_player()
        keys = [key for key, _, _ in _menu_entries(ctx)]
        self.assertNotIn('T', keys)

    def test_transfer_shown_with_ally(self):
        from shoppe.main import _menu_entries
        ctx = MagicMock()
        ctx.player = _make_player(party=Party(members=[_servant_ally()]))
        keys = [key for key, _, _ in _menu_entries(ctx)]
        self.assertIn('T', keys)


if __name__ == '__main__':
    unittest.main()
