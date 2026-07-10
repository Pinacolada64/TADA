"""tests/test_editplayer_combination_clear.py

commands/editplayer.py's Combinations editor: typing X clears only the one
combination type being edited, not all three (Castle/Elevator/Locker).

Regression this guards against: combos are stored under three aliased dict
keys per type (the enum member, its .value, and its .name -- CombinationTypes
is a StrEnum, so the enum member and its .value collapse to the same dict
key, but .name is a distinct one). An earlier version of the clear branch
only popped the enum-keyed alias, leaving the .name-keyed alias holding the
stale Combination object, so _fmt() kept showing the old value as "cleared".
The fix mutates .combination = None on the shared object (all three aliases
reference the same instance) instead of doing incomplete dict surgery.

Run with:
    python -m pytest tests/test_editplayer_combination_clear.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from base_classes import Combination, CombinationTypes
from commands.editplayer import _combinations_menu


def _make_player_with_combos():
    player = MagicMock()
    player.combinations = {}
    for ct, digits in ((CombinationTypes.CASTLE, (23, 97, 49)),
                       (CombinationTypes.ELEVATOR, (11, 22, 33)),
                       (CombinationTypes.LOCKER, (90, 97, 50))):
        combo = Combination(ct)
        combo.combination = digits
        player.combinations[ct] = combo
        player.combinations[ct.value] = combo
        player.combinations[ct.name] = combo
    return player


def _action_for(menu, shortcut):
    for item in menu.menu_items:
        if shortcut in item.shortcuts:
            return item.action
    raise AssertionError(f'no menu item with shortcut {shortcut!r}')


def _make_ctx(player, responses):
    ctx = MagicMock()
    ctx.player = player
    ctx.send = AsyncMock()
    it = iter(responses)
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(it, None))
    return ctx


class TestClearOnlyEditedCombo(unittest.IsolatedAsyncioTestCase):

    async def test_clearing_castle_leaves_elevator_and_locker_intact(self):
        player = _make_player_with_combos()
        ctx = _make_ctx(player, ['x'])
        menu = _combinations_menu(ctx)

        await _action_for(menu, 'ca')(ctx)

        self.assertIsNone(player.combinations[CombinationTypes.CASTLE].combination)
        self.assertIsNone(player.combinations['CASTLE'].combination)
        self.assertEqual(player.combinations[CombinationTypes.ELEVATOR].combination, (11, 22, 33))
        self.assertEqual(player.combinations['ELEVATOR'].combination, (11, 22, 33))
        self.assertEqual(player.combinations[CombinationTypes.LOCKER].combination, (90, 97, 50))
        self.assertEqual(player.combinations['LOCKER'].combination, (90, 97, 50))

    async def test_clearing_locker_leaves_castle_and_elevator_intact(self):
        player = _make_player_with_combos()
        ctx = _make_ctx(player, ['x'])
        menu = _combinations_menu(ctx)

        await _action_for(menu, 'lo')(ctx)

        self.assertIsNone(player.combinations[CombinationTypes.LOCKER].combination)
        self.assertEqual(player.combinations[CombinationTypes.CASTLE].combination, (23, 97, 49))
        self.assertEqual(player.combinations[CombinationTypes.ELEVATOR].combination, (11, 22, 33))

    async def test_cleared_combo_displays_as_none(self):
        player = _make_player_with_combos()
        ctx = _make_ctx(player, ['x'])
        menu = _combinations_menu(ctx)

        await _action_for(menu, 'el')(ctx)

        flat = '\n'.join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn('Elevator cleared.', flat)

    async def test_blank_input_leaves_all_combos_unchanged(self):
        player = _make_player_with_combos()
        ctx = _make_ctx(player, [''])
        menu = _combinations_menu(ctx)

        await _action_for(menu, 'ca')(ctx)

        self.assertEqual(player.combinations[CombinationTypes.CASTLE].combination, (23, 97, 49))
        self.assertEqual(player.combinations[CombinationTypes.ELEVATOR].combination, (11, 22, 33))
        self.assertEqual(player.combinations[CombinationTypes.LOCKER].combination, (90, 97, 50))


if __name__ == '__main__':
    unittest.main(verbosity=2)
