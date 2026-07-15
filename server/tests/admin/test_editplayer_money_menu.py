"""tests/test_editplayer_money_menu.py

Unit tests for commands/editplayer.py's Money menu Vinny Loan entry --
displays/edits player.loan_amount / player.loan_days (bar/vinny.py's Vinny
the Loan Shark debt tracking).

Run with:
    python -m pytest tests/test_editplayer_money_menu.py -v
"""
from __future__ import annotations

import asyncio
import unittest

from commands.editplayer import _money_menu
from player import Player


class _FakeCtx:
    def __init__(self, responses=None, player=None):
        self._q = list(responses or [])
        self.sent: list[str] = []
        self.player = player or Player()

    async def send(self, *args) -> None:
        for a in args:
            if isinstance(a, (list, tuple)):
                self.sent.extend(str(x) for x in a)
            else:
                self.sent.append(str(a))

    async def prompt(self, prompt_text: str = '', preamble_lines=None) -> str:
        if preamble_lines:
            await self.send(preamble_lines)
        return self._q.pop(0) if self._q else ''


def _find_item(menu, label):
    return next(i for i in menu.menu_items if getattr(i, 'text', None) == label)


class TestVinnyLoanMenuItem(unittest.TestCase):

    def test_no_loan_shows_none(self):
        player = Player()
        ctx = _FakeCtx(player=player)
        menu = _money_menu(ctx)
        item = _find_item(menu, 'Vinny Loan')
        self.assertEqual(item.dot_leader_handler(ctx), 'None')

    def test_existing_loan_shows_amount_and_days(self):
        player = Player()
        player.loan_amount = 2500
        player.loan_days = 3
        ctx = _FakeCtx(player=player)
        menu = _money_menu(ctx)
        item = _find_item(menu, 'Vinny Loan')
        status = item.dot_leader_handler(ctx)
        self.assertIn('2,500', status)
        self.assertIn('3 days', status)

    def test_singular_day(self):
        player = Player()
        player.loan_amount = 500
        player.loan_days = 1
        ctx = _FakeCtx(player=player)
        menu = _money_menu(ctx)
        item = _find_item(menu, 'Vinny Loan')
        self.assertIn('1 day left', item.dot_leader_handler(ctx))

    def test_edit_sets_amount_and_days(self):
        player = Player()
        ctx = _FakeCtx(responses=['1000', '5'], player=player)
        menu = _money_menu(ctx)
        item = _find_item(menu, 'Vinny Loan')
        asyncio.run(item.action(ctx))
        self.assertEqual(player.loan_amount, 1000)
        self.assertEqual(player.loan_days, 5)
        self.assertTrue(player.unsaved_changes)

    def test_setting_amount_to_zero_clears_days(self):
        player = Player()
        player.loan_amount = 2000
        player.loan_days = 4
        ctx = _FakeCtx(responses=['0'], player=player)
        menu = _money_menu(ctx)
        item = _find_item(menu, 'Vinny Loan')
        asyncio.run(item.action(ctx))
        self.assertEqual(player.loan_amount, 0)
        self.assertEqual(player.loan_days, 0)
        self.assertIn('Loan cleared.', ctx.sent)

    def test_cancel_amount_prompt_leaves_loan_unchanged(self):
        player = Player()
        player.loan_amount = 750
        player.loan_days = 2
        ctx = _FakeCtx(responses=[''], player=player)
        menu = _money_menu(ctx)
        item = _find_item(menu, 'Vinny Loan')
        asyncio.run(item.action(ctx))
        self.assertEqual(player.loan_amount, 750)
        self.assertEqual(player.loan_days, 2)


if __name__ == '__main__':
    unittest.main()
