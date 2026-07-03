"""tests/test_read_command.py

Unit tests for commands/read.py (ReadCommand) and the elevator-combination
gating it feeds into (shoppe/elevator.py's get_combination), covering the
"Elevator Combination (Scrap of Paper)" mechanic from MECHANICS.md.

Coverage:
  - no books in inventory -> "You have no books!"
  - reading a non-scrap book -> generic acknowledgement, item untouched
  - reading the scrap of paper the first time -> flavor prompts, generates
    and stores a CombinationTypes.ELEVATOR combination, item NOT consumed
  - answering "Evil" costs 2 honor (if honor > 2); "Good" does not
  - reading the scrap again -> re-prints the same combination, no reroll,
    no further flavor prompts
  - elevator refuses access before the scrap is read, accepts the generated
    combination afterwards (shoppe/elevator.get_combination)

Run with:
    python -m pytest tests/test_read_command.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from base_classes import Combination, CombinationTypes
from commands.read import ReadCommand
from inventory import Inventory
from item_system import Item, ItemType
from shoppe.elevator import get_combination

_SCRAP_ID = 69


def make_player(*, with_scrap: bool = True, honor: int = 1000) -> MagicMock:
    p = MagicMock()
    p.name = 'TestPlayer'
    p.honor = honor
    p.combinations = {}
    p.unsaved_changes = False
    p.inventory = Inventory(capacity=10)
    if with_scrap:
        p.inventory.add(Item(number=_SCRAP_ID, name='scrap of paper', type=ItemType.BOOK, price=4))
    return p


def make_ctx(player, prompts: list) -> MagicMock:
    ctx = MagicMock()
    ctx.player = player
    ctx.send = AsyncMock()
    it = iter(prompts)
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(it, None))
    return ctx


def _sent(ctx) -> str:
    parts = []
    for call in ctx.send.await_args_list:
        for arg in call.args:
            if isinstance(arg, list):
                parts.extend(str(x) for x in arg)
            else:
                parts.append(str(arg))
    return '\n'.join(parts)


class TestReadCommandNoBooks(unittest.IsolatedAsyncioTestCase):
    async def test_no_books_in_inventory(self):
        player = make_player(with_scrap=False)
        ctx = make_ctx(player, [])
        res = await ReadCommand().execute(ctx)
        self.assertTrue(res.success)
        self.assertIn('no books', _sent(ctx).lower())


class TestReadOrdinaryBook(unittest.IsolatedAsyncioTestCase):
    async def test_reading_other_book_does_not_touch_combinations(self):
        player = make_player(with_scrap=False)
        player.inventory.add(Item(number=30, name='The Howling', type=ItemType.BOOK, price=1))
        ctx = make_ctx(player, [])
        res = await ReadCommand().execute(ctx, 'howling')
        self.assertTrue(res.success)
        self.assertNotIn(CombinationTypes.ELEVATOR, player.combinations)
        self.assertIn('howling', _sent(ctx).lower())


class TestReadScrapOfPaper(unittest.IsolatedAsyncioTestCase):
    async def test_first_read_generates_and_shows_combination(self):
        player = make_player(honor=1000)
        ctx = make_ctx(player, ['Y', 'G'])

        res = await ReadCommand().execute(ctx, 'scrap')

        self.assertTrue(res.success)
        self.assertIn(CombinationTypes.ELEVATOR, player.combinations)
        combo = player.combinations[CombinationTypes.ELEVATOR]
        self.assertIsInstance(combo, Combination)
        digits = '-'.join(f'{n:02}' for n in combo.combination)
        self.assertIn(digits, _sent(ctx))
        self.assertEqual(player.honor, 1000)  # Good costs nothing

    async def test_scrap_of_paper_is_not_consumed(self):
        player = make_player()
        ctx = make_ctx(player, ['Y', 'G'])
        await ReadCommand().execute(ctx, 'scrap')
        still_has = any(getattr(e.item, 'number', None) == _SCRAP_ID
                        for e in player.inventory.entries())
        self.assertTrue(still_has)

    async def test_answering_evil_costs_two_honor(self):
        player = make_player(honor=10)
        ctx = make_ctx(player, ['Y', 'E'])
        await ReadCommand().execute(ctx, 'scrap')
        self.assertEqual(player.honor, 8)

    async def test_evil_does_not_cost_honor_when_honor_at_or_below_two(self):
        player = make_player(honor=2)
        ctx = make_ctx(player, ['Y', 'E'])
        await ReadCommand().execute(ctx, 'scrap')
        self.assertEqual(player.honor, 2)

    async def test_second_read_does_not_reroll_or_reprompt(self):
        player = make_player()
        ctx = make_ctx(player, ['Y', 'G'])
        await ReadCommand().execute(ctx, 'scrap')
        combo_after_first = player.combinations[CombinationTypes.ELEVATOR].combination

        ctx2 = make_ctx(player, [])  # no prompts queued -- should not be consulted
        await ReadCommand().execute(ctx2, 'scrap')
        combo_after_second = player.combinations[CombinationTypes.ELEVATOR].combination

        self.assertEqual(combo_after_first, combo_after_second)
        digits = '-'.join(f'{n:02}' for n in combo_after_second)
        self.assertIn(digits, _sent(ctx2))
        self.assertEqual(ctx2.prompt.await_count, 0)


class TestElevatorGatedOnScrap(unittest.IsolatedAsyncioTestCase):
    async def test_elevator_refuses_without_reading_scrap(self):
        player = make_player()  # has the scrap, hasn't read it yet
        ctx = make_ctx(player, [])
        ok = await get_combination(ctx, is_interactive=False, provided_ans='01-02-03')
        self.assertFalse(ok)
        self.assertIn('combination', _sent(ctx).lower())

    async def test_elevator_accepts_combination_after_reading_scrap(self):
        player = make_player()
        read_ctx = make_ctx(player, ['Y', 'G'])
        await ReadCommand().execute(read_ctx, 'scrap')
        combo = player.combinations[CombinationTypes.ELEVATOR].combination
        ans = '-'.join(f'{n:02}' for n in combo)

        elevator_ctx = make_ctx(player, [])
        ok = await get_combination(elevator_ctx, is_interactive=False, provided_ans=ans)
        self.assertTrue(ok)


class TestCombinationPersistence(unittest.IsolatedAsyncioTestCase):
    """player.combinations round-trips through Player.save()/_load() (dict shape),
    and Player._load() still migrates the older list-of-dicts shape already
    written to disk by existing player saves."""

    def setUp(self):
        import shutil, tempfile
        import net_common
        self._tmpdir = tempfile.mkdtemp(prefix='tada-combo-test-')
        self._orig_run_dir = getattr(net_common, 'run_server_dir', None)
        net_common.run_server_dir = self._tmpdir
        self._shutil = shutil

    def tearDown(self):
        import net_common
        net_common.run_server_dir = self._orig_run_dir
        self._shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_elevator_combination_round_trips_through_save_load(self):
        from player import Player

        p = Player(id='combo-roundtrip-user', name='Tester')
        p.inventory.add(Item(number=_SCRAP_ID, name='scrap of paper', type=ItemType.BOOK, price=4))
        ctx = make_ctx(p, ['Y', 'G'])
        await ReadCommand().execute(ctx, 'scrap')
        original = p.combinations[CombinationTypes.ELEVATOR].combination

        self.assertTrue(p.save(force=True))

        reloaded = Player(id='combo-roundtrip-user', name='Tester')
        self.assertIn(CombinationTypes.ELEVATOR, reloaded.combinations)
        self.assertEqual(reloaded.combinations[CombinationTypes.ELEVATOR].combination, original)

    def test_load_migrates_legacy_list_shaped_combinations(self):
        import json, os
        from player import Player

        path = os.path.join(self._tmpdir, 'player-legacy-combo-user.json')
        with open(path, 'w') as f:
            json.dump({
                'combinations': [
                    {'name': 'Castle', 'combination': [42, 87, 10]},
                    {'name': 'Elevator', 'combination': [71, 95, 91]},
                    {'name': 'Locker', 'combination': [19, 94, 27]},
                ],
            }, f)

        p = Player(id='legacy-combo-user', name='Tester')
        self.assertEqual(p.combinations[CombinationTypes.ELEVATOR].combination, (71, 95, 91))
        self.assertEqual(p.combinations[CombinationTypes.CASTLE].combination, (42, 87, 10))


if __name__ == '__main__':
    unittest.main()
