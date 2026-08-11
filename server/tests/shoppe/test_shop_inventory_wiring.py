"""tests/shoppe/test_shop_inventory_wiring.py — each Merchant's Annex shop's
own browsing loop (general store, armory buy/sell/protection, Olly's booby
section & top menu, the Wizard, the pawn shop) now accepts [I]nventory and
[T]ransfer directly, via shoppe.inventory_tools.handle_shop_key(), without
backing out to the Shoppe's own top-level menu. Ryan's request.

[T] itself is only *offered*, and only actually dispatches, once the player
has an owned ally/mount (shoppe.inventory_tools.has_transfer_targets()) --
covered per-shop below with a bare Player (no party: 'T' falls through to
that shop's normal invalid-input handling) and with a party ally added.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bar.ally_data import Ally, AllyStatus
from base_classes import PlayerMoneyTypes
from flags import PlayerFlags
from inventory import Inventory
from party import Party
from player import Player

from shoppe.armory import _buy as armory_buy, _sell as armory_sell, protection as armory_protection
from shoppe.main import _general_store
from shoppe.ollys import _booby_section, main as ollys_main
from shoppe.pawn import main as pawn_main
from shoppe.wizard import main as wizard_main


def _servant_ally(name='Grog'):
    ally = Ally(name=name, gender='m', strength=15, to_hit=5)
    ally.status = AllyStatus.SERVANT
    ally.items = []
    return ally


def _new_player(name: str = 'Rulan', with_ally: bool = False, **kwargs) -> Player:
    player = Player(name=name, **kwargs)
    player.clear_flag(PlayerFlags.DEBUG_MODE)
    player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 100_000)
    player.inventory = Inventory(capacity=14)
    if with_ally:
        player.party = Party(members=[_servant_ally()])
    return player


class _FakeCtx:
    def __init__(self, responses, player, **server_kwargs):
        self._q = list(responses)
        self.sent: list = []
        self.player = player
        self.server = SimpleNamespace(items=[], weapons=[], rations=[], pawn_stock=[], **server_kwargs)

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


class TestGeneralStore(unittest.IsolatedAsyncioTestCase):
    async def test_i_opens_inventory_tool_and_stays_in_shop(self):
        player = _new_player()
        ctx = _FakeCtx(['i', ''], player)
        with patch('shoppe.inventory_tools.inventory_main', new=AsyncMock()) as inv_mock:
            await _general_store(ctx)
        inv_mock.assert_awaited_once_with(ctx)

    async def test_t_hidden_without_party(self):
        player = _new_player()
        ctx = _FakeCtx(['t', ''], player)
        with patch('shoppe.inventory_tools.transfer_main', new=AsyncMock()) as tr_mock:
            await _general_store(ctx)
        tr_mock.assert_not_awaited()

    async def test_t_opens_transfer_tool_with_party(self):
        player = _new_player(with_ally=True)
        ctx = _FakeCtx(['t', ''], player)
        with patch('shoppe.inventory_tools.transfer_main', new=AsyncMock()) as tr_mock:
            await _general_store(ctx)
        tr_mock.assert_awaited_once_with(ctx)


class TestArmory(unittest.IsolatedAsyncioTestCase):
    async def test_buy_loop_i_opens_inventory(self):
        player = _new_player()
        ctx = _FakeCtx(['i', 'q'], player)
        with patch('shoppe.inventory_tools.inventory_main', new=AsyncMock()) as inv_mock:
            await armory_buy(ctx, player, player.inventory, [])
        inv_mock.assert_awaited_once_with(ctx)

    async def test_sell_loop_t_opens_transfer_with_party(self):
        from items import Weapon, ItemCategory
        player = _new_player(with_ally=True)
        player.inventory.add(Weapon(id_number=1, name='Dagger', category=ItemCategory.WEAPON))
        ctx = _FakeCtx(['t', 'q'], player)
        with patch('shoppe.inventory_tools.transfer_main', new=AsyncMock()) as tr_mock:
            await armory_sell(ctx, player, player.inventory, [])
        tr_mock.assert_awaited_once_with(ctx)

    async def test_protection_loop_i_opens_inventory(self):
        player = _new_player()
        ctx = _FakeCtx(['i', 'q'], player)
        with patch('shoppe.inventory_tools.inventory_main', new=AsyncMock()) as inv_mock:
            await armory_protection(ctx)
        inv_mock.assert_awaited_once_with(ctx)


class TestOllys(unittest.IsolatedAsyncioTestCase):
    async def test_booby_section_i_opens_inventory(self):
        player = _new_player()
        ctx = _FakeCtx(['i', 'q'], player)
        with patch('shoppe.inventory_tools.inventory_main', new=AsyncMock()) as inv_mock:
            await _booby_section(ctx, player, player.inventory, {})
        inv_mock.assert_awaited_once_with(ctx)

    async def test_top_menu_t_opens_transfer_with_party(self):
        player = _new_player(with_ally=True)
        ctx = _FakeCtx(['t', 'q'], player)
        with patch('shoppe.inventory_tools.transfer_main', new=AsyncMock()) as tr_mock:
            await ollys_main(ctx)
        tr_mock.assert_awaited_once_with(ctx)


class TestWizard(unittest.IsolatedAsyncioTestCase):
    async def test_spell_loop_i_opens_inventory(self):
        player = _new_player()
        ctx = _FakeCtx(['y', 'i', 'q'], player)
        with patch('shoppe.inventory_tools.inventory_main', new=AsyncMock()) as inv_mock:
            await wizard_main(ctx)
        inv_mock.assert_awaited_once_with(ctx)


class TestPawn(unittest.IsolatedAsyncioTestCase):
    async def test_i_opens_inventory(self):
        player = _new_player()
        player.once_per_day = []
        ctx = _FakeCtx(['i', 'q'], player)
        with patch('shoppe.inventory_tools.inventory_main', new=AsyncMock()) as inv_mock:
            await pawn_main(ctx)
        inv_mock.assert_awaited_once_with(ctx)


class TestHelpFallback(unittest.IsolatedAsyncioTestCase):
    """Ryan's report: a player standing in the Shoppe with no locker
    combination yet had no way to type 'help combination' -- every shop's
    own prompt loop bypassed CommandProcessor entirely, so 'help' just
    fell into that shop's own 'invalid selection' handling (or, at the
    Shoppe's top-level menu, was silently truncated to its first letter
    before ever being recognized as anything). Each loop now tries
    presence.try_global_command() on unrecognized input before giving up."""

    async def test_general_store_falls_back_to_help(self):
        player = _new_player()
        ctx = _FakeCtx(['help combination', ''], player)
        with patch('shoppe.main.try_global_command', new=AsyncMock(return_value=True)) as gc:
            await _general_store(ctx)
        gc.assert_awaited_once_with(ctx, 'help combination')

    async def test_armory_buy_falls_back_to_help(self):
        player = _new_player()
        ctx = _FakeCtx(['help combination', 'q'], player)
        with patch('shoppe.armory.try_global_command', new=AsyncMock(return_value=True)) as gc:
            await armory_buy(ctx, player, player.inventory, [])
        gc.assert_awaited_once_with(ctx, 'help combination')

    async def test_wizard_falls_back_to_help(self):
        player = _new_player()
        ctx = _FakeCtx(['y', 'help combination', 'q'], player)
        with patch('shoppe.wizard.try_global_command', new=AsyncMock(return_value=True)) as gc:
            await wizard_main(ctx)
        gc.assert_awaited_once_with(ctx, 'help combination')

    async def test_pawn_falls_back_to_help(self):
        player = _new_player()
        player.once_per_day = []
        ctx = _FakeCtx(['help combination', 'q'], player)
        with patch('shoppe.pawn.try_global_command', new=AsyncMock(return_value=True)) as gc:
            await pawn_main(ctx)
        gc.assert_awaited_once_with(ctx, 'help combination')

    async def test_booby_section_falls_back_to_help_not_code_h(self):
        """'help' truncates to 'H' -- itself a valid disarm code (A-I) --
        so this must be checked as a real command before the single-letter
        code table, not after."""
        player = _new_player()
        ctx = _FakeCtx(['help combination', 'q'], player)
        with patch('shoppe.ollys.try_global_command', new=AsyncMock(return_value=True)) as gc:
            await _booby_section(ctx, player, player.inventory, {})
        gc.assert_awaited_once_with(ctx, 'help combination')

    async def test_booby_section_bare_h_still_selects_code_h(self):
        """A real single-letter disarm code must keep working -- 'H' alone
        (len 1) should never reach try_global_command at all."""
        player = _new_player()
        player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 100_000)
        ctx = _FakeCtx(['h', 'n'], player)
        with patch('shoppe.ollys.try_global_command', new=AsyncMock(return_value=True)) as gc:
            await _booby_section(ctx, player, player.inventory, {152: {'name': 'trap'}})
        gc.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
