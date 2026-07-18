"""tests/shoppe/test_ollys.py

Covers shoppe/ollys.py — Olly's Ammo & Trap Shop (SPUR.MISC5.S ammo/booby
sections):

  - Ammo listing/purchase, including the ammo-carrier rows (New in TADA --
    carriers get a Capacity column instead of Dmg, since they don't deal
    damage themselves).
  - Booby trap purchase (disarm code A-I baked into which item is bought).
  - The 'I'nventory shortcut added to the ammo listing (New in TADA, Ryan's
    request: browsing the ammo list makes it easy to lose track of what
    you're already carrying).
  - Top-level [A]mmo/[B]ooby/[H]elp/Q dispatch, falling through to
    try_global_command() for anything else.
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from base_classes import PlayerMoneyTypes
from formatting import PlainCodec, highlight_brackets
from player import Player
from shoppe.ollys import (
    _ammo_section,
    _booby_section,
    _load_objects,
    main as ollys_main,
)


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


def _funded_player(silver: int = 1000) -> Player:
    player = Player(name='Rulan')
    player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, silver)
    return player


class TestLoadObjects(unittest.TestCase):
    def test_loads_real_ammo_and_carrier_items(self):
        objects_by_num = {o['number']: o for o in _load_objects()}
        self.assertIn(100, objects_by_num)  # arrows
        self.assertEqual(objects_by_num[100]['name'], 'arrows')
        self.assertIn(147, objects_by_num)  # cartridge box (carrier)


class TestAmmoSectionTableFormatting(unittest.IsolatedAsyncioTestCase):
    """New in TADA: the ammo/carrier listings used to be hand-rolled
    f-strings (_ammo_line()/_carrier_line()) that broke column alignment on
    wide names like 'Armor Piercing arrows' -- the fixed-width field just
    overflowed into the next column. Switched to table.py's
    Table(border=False), which computes real column widths and wraps
    overflow instead. Ryan's request."""

    def setUp(self):
        self.objects_by_num = {o['number']: o for o in _load_objects()}

    async def test_headers_present_and_no_redundant_labels(self):
        player = _funded_player()
        ctx = _FakeCtx(['q'], player)
        await _ammo_section(ctx, player, player.inventory, self.objects_by_num)
        flat = ctx._flat()
        self.assertIn('Rnds', flat)
        self.assertIn('Dmg', flat)
        self.assertIn('Capacity', flat)
        self.assertNotIn('rnd', flat)
        self.assertNotIn('dmg:', flat)
        self.assertNotIn('cap:', flat)

    async def test_wide_name_does_not_break_column_alignment(self):
        """'Armor Piercing arrows' (#111) is the widest ammo name -- it must
        wrap onto its own line rather than shoving the Rnds/Dmg/Cost columns
        out of alignment the way the old fixed-width f-string did."""
        player = _funded_player()
        ctx = _FakeCtx(['q'], player)
        await _ammo_section(ctx, player, player.inventory, self.objects_by_num)
        lines = [str(s) for s in ctx.sent]
        idx = next(i for i, l in enumerate(lines) if 'Armor Piercing' in l)
        # The Cost column ('30s', price 3 * 10) must still land on the same
        # visual row as the item's own leading columns.
        self.assertIn('30s', lines[idx])

    async def test_shop_local_numbering_not_raw_object_numbers(self):
        player = _funded_player()
        ctx = _FakeCtx(['q'], player)
        await _ammo_section(ctx, player, player.inventory, self.objects_by_num)
        flat = ctx._flat()
        self.assertIn('cartridge box', flat)
        # 147 is the raw objects.json number for cartridge box -- must not
        # leak into the display, which uses shop-local numbering instead.
        self.assertNotIn('147', flat)


class TestAmmoSectionHeaderEscaping(unittest.IsolatedAsyncioTestCase):
    """Regression: the decorative '[]...[OLLY]...[]' banner used to break
    highlight_brackets() for the *entire* line -- the empty '[]' pair has no
    content, so the bracket regex kept scanning past it for the next ']'
    and swallowed everything up through OLLY's closing bracket too. Fixed
    by dropping the empty brackets and double-escaping '[[OLLY]]' and
    '[[ Ammo Carriers ]]'."""

    async def test_header_lines_survive_bracket_highlighting_intact(self):
        player = _funded_player()
        ctx = _FakeCtx(['q'], player)
        await _ammo_section(ctx, player, player.inventory, {o['number']: o for o in _load_objects()})
        codec = PlainCodec()
        for line in ctx.sent:
            highlight_brackets(str(line), codec)  # must not raise
        flat = '\n'.join(highlight_brackets(str(l), codec) for l in ctx.sent)
        self.assertIn('OLLY', flat)
        self.assertIn('Ammo Carriers', flat)
        # The escape must not leak literal double brackets into the output.
        self.assertNotIn('[[', flat)
        self.assertNotIn(']]', flat)


class TestAmmoSectionInventoryShortcut(unittest.IsolatedAsyncioTestCase):
    """New in TADA: 'I' at the ammo prompt shows the player's own inventory
    without leaving the shop, via presence.try_global_command()."""

    async def test_i_dispatches_inventory_and_relists(self):
        player = _funded_player()
        objects_by_num = {o['number']: o for o in _load_objects()}
        ctx = _FakeCtx(['i', 'q'], player)
        with patch('shoppe.ollys.try_global_command', new=AsyncMock(return_value=True)) as mocked:
            await _ammo_section(ctx, player, player.inventory, objects_by_num)
        mocked.assert_awaited_once_with(ctx, 'inventory')
        # Loop continued and re-showed the listing rather than exiting.
        self.assertIn('OLLY', ctx._flat())

    async def test_uppercase_i_also_works(self):
        player = _funded_player()
        objects_by_num = {o['number']: o for o in _load_objects()}
        ctx = _FakeCtx(['I', 'q'], player)
        with patch('shoppe.ollys.try_global_command', new=AsyncMock(return_value=True)) as mocked:
            await _ammo_section(ctx, player, player.inventory, objects_by_num)
        mocked.assert_awaited_once_with(ctx, 'inventory')


class TestAmmoSectionPurchase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.objects_by_num = {o['number']: o for o in _load_objects()}

    async def test_buy_ammo_deducts_silver_and_adds_item(self):
        player = _funded_player(1000)
        ctx = _FakeCtx(['3', 'y', 'q'], player)  # arrows (shop-local #3), cost 10
        await _ammo_section(ctx, player, player.inventory, self.objects_by_num)
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 990)
        self.assertEqual(len(player.inventory.find(name='arrows')), 1)
        self.assertIn('Done!', ctx._flat())
        self.assertTrue(player.unsaved_changes)

    async def test_bought_ammo_carries_flags_for_use_command(self):
        """Regression: the purchased item used to drop objects.json's
        flags dict entirely (rounds/damage/used_with), so commands/use.py
        could never actually load it -- see that module's _apply_item
        docstring. The item in inventory must carry the same flags dict
        objects.json defines for this ammo."""
        player = _funded_player(1000)
        ctx = _FakeCtx(['3', 'y', 'q'], player)  # arrows (shop-local #3)
        await _ammo_section(ctx, player, player.inventory, self.objects_by_num)
        entry = player.inventory.find(name='arrows')[0]
        self.assertIsInstance(entry.item.flags, dict)
        self.assertIn('rounds', entry.item.flags)
        self.assertIn('used_with', entry.item.flags)

    async def test_buy_carrier_shows_auto_ammo_note(self):
        player = _funded_player(1000)
        ctx = _FakeCtx(['15', 'y', 'q'], player)  # cartridge box (shop-local #15), cost 50
        await _ammo_section(ctx, player, player.inventory, self.objects_by_num)
        self.assertIn('automatically be placed', ctx._flat())

    async def test_declining_confirmation_does_not_charge(self):
        player = _funded_player(1000)
        ctx = _FakeCtx(['3', 'n', 'q'], player)
        await _ammo_section(ctx, player, player.inventory, self.objects_by_num)
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 1000)
        self.assertEqual(len(player.inventory.find(name='arrows')), 0)

    async def test_insufficient_gold_rejected(self):
        player = _funded_player(5)
        ctx = _FakeCtx(['3', 'q'], player)  # arrows cost 10
        await _ammo_section(ctx, player, player.inventory, self.objects_by_num)
        self.assertIn('You do not have enough gold.', ctx._flat())
        self.assertEqual(len(player.inventory.find(name='arrows')), 0)

    async def test_full_pack_rejected(self):
        from inventory import Inventory
        player = _funded_player(1000)
        player.inventory = Inventory(capacity=0)
        ctx = _FakeCtx(['3', 'q'], player)
        await _ammo_section(ctx, player, player.inventory, self.objects_by_num)
        self.assertIn('You have no room in your pack!', ctx._flat())

    async def test_invalid_number_rejected(self):
        player = _funded_player(1000)
        ctx = _FakeCtx(['999', 'q'], player)
        await _ammo_section(ctx, player, player.inventory, self.objects_by_num)
        self.assertIn('Enter 1-18, or Q.', ctx._flat())

    async def test_non_numeric_choice_rejected(self):
        player = _funded_player(1000)
        ctx = _FakeCtx(['xyz', 'q'], player)
        await _ammo_section(ctx, player, player.inventory, self.objects_by_num)
        self.assertIn('Enter a number, ? to list, I)nventory, or Q to leave.', ctx._flat())

    async def test_question_mark_relists(self):
        player = _funded_player(1000)
        ctx = _FakeCtx(['?', 'q'], player)
        await _ammo_section(ctx, player, player.inventory, self.objects_by_num)
        self.assertGreaterEqual(ctx._flat().count('OLLY'), 2)

    async def test_blank_quits(self):
        player = _funded_player(1000)
        ctx = _FakeCtx([''], player)
        await _ammo_section(ctx, player, player.inventory, self.objects_by_num)
        self.assertEqual(len(player.inventory.find(name='arrows')), 0)

    async def test_disconnect_mid_prompt_returns(self):
        player = _funded_player(1000)
        ctx = _FakeCtx([], player)
        await _ammo_section(ctx, player, player.inventory, self.objects_by_num)  # must not raise


class TestBoobySection(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.objects_by_num = {o['number']: o for o in _load_objects()}

    async def test_buy_trap_with_code_deducts_and_adds_item(self):
        player = _funded_player(2000)
        ctx = _FakeCtx(['a', 'y'], player)
        await _booby_section(ctx, player, player.inventory, self.objects_by_num)
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 1000)
        entries = player.inventory.find(name='booby trap (code A)')
        self.assertEqual(len(entries), 1)
        self.assertTrue(player.unsaved_changes)

    async def test_invalid_code_rejected(self):
        player = _funded_player(2000)
        ctx = _FakeCtx(['z', 'q'], player)
        await _booby_section(ctx, player, player.inventory, self.objects_by_num)
        self.assertIn('pretends not to notice', ctx._flat())

    async def test_insufficient_gold_rejected(self):
        player = _funded_player(5)
        ctx = _FakeCtx(['a', 'q'], player)
        await _booby_section(ctx, player, player.inventory, self.objects_by_num)
        self.assertIn('You do not have enough gold.', ctx._flat())

    async def test_full_pack_returns(self):
        from inventory import Inventory
        player = _funded_player(2000)
        player.inventory = Inventory(capacity=0)
        ctx = _FakeCtx(['a'], player)
        await _booby_section(ctx, player, player.inventory, self.objects_by_num)
        self.assertIn('You have no room in your pack!', ctx._flat())

    async def test_quit_leaves_display(self):
        player = _funded_player(2000)
        ctx = _FakeCtx(['q'], player)
        await _booby_section(ctx, player, player.inventory, self.objects_by_num)
        self.assertIn('You leave the booby trap display.', ctx._flat())


class TestOllysMainDispatch(unittest.IsolatedAsyncioTestCase):
    async def test_greets_player_by_name(self):
        player = _funded_player()
        ctx = _FakeCtx(['q'], player)
        await ollys_main(ctx)
        self.assertIn("Welcome, Rulan!!", ctx._flat())

    async def test_a_enters_ammo_section(self):
        player = _funded_player()
        ctx = _FakeCtx(['a', 'q', 'q'], player)
        await ollys_main(ctx)
        self.assertIn('OLLY', ctx._flat())

    async def test_b_enters_booby_section(self):
        player = _funded_player()
        ctx = _FakeCtx(['b', 'q', 'q'], player)
        await ollys_main(ctx)
        self.assertIn('Booby Trap display', ctx._flat())

    async def test_h_shows_help(self):
        player = _funded_player()
        ctx = _FakeCtx(['h', 'q'], player)
        await ollys_main(ctx)
        self.assertIn('AMMUNITION GUIDE', ctx._flat())

    async def test_q_leaves_immediately(self):
        player = _funded_player()
        ctx = _FakeCtx(['q'], player)
        await ollys_main(ctx)
        self.assertNotIn('OLLY', ctx._flat())

    async def test_unrecognized_falls_back_to_global_command(self):
        player = _funded_player()
        ctx = _FakeCtx(['whereat', 'q'], player)
        with patch('shoppe.ollys.try_global_command', new=AsyncMock(return_value=True)) as mocked:
            await ollys_main(ctx)
        mocked.assert_awaited_once_with(ctx, 'whereat')

    async def test_unrecognized_and_unmatched_shows_menu_error(self):
        player = _funded_player()
        ctx = _FakeCtx(['zzz', 'q'], player)
        with patch('shoppe.ollys.try_global_command', new=AsyncMock(return_value=False)):
            await ollys_main(ctx)
        self.assertIn('A)mmo, B)ooby traps, H)elp, or Q to leave.', ctx._flat())


if __name__ == '__main__':
    unittest.main(verbosity=2)
