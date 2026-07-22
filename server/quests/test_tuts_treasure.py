"""tests/test_tuts_treasure.py — quest #16, "Tut's Treasure"
(quests/tuts_treasure.py). See quests/README.md's full writeup.
"""
from __future__ import annotations

import dataclasses
import unittest
from unittest.mock import AsyncMock, MagicMock

from flags import TutTreasure
from player import Player
from quests.tuts_treasure import GetOutcome, examine, get, is_tuts_treasure


class _FakePlayer:
    def __init__(self, examined=False, taken=False, silver_in_hand=0,
                 intelligence=10, constitution=10, hit_points=30, experience=0):
        self.tuts_treasure = TutTreasure(examined=examined, taken=taken)
        self.stats = {'Intelligence': intelligence, 'Constitution': constitution}
        self.hit_points = hit_points
        self.experience = experience
        self.unsaved_changes = False
        self._silver = {'IN_HAND': silver_in_hand}

    def get_silver(self, kind):
        return self._silver.get(str(kind).split('.')[-1], self._silver.get('IN_HAND', 0))

    def set_silver_absolute(self, kind, amount):
        self._silver['IN_HAND'] = amount


class TestIsTutsTreasure(unittest.TestCase):
    def test_matches_item_86(self):
        self.assertTrue(is_tuts_treasure(86))
        self.assertTrue(is_tuts_treasure('86'))

    def test_rejects_other_ids(self):
        self.assertFalse(is_tuts_treasure(35))
        self.assertFalse(is_tuts_treasure(None))
        self.assertFalse(is_tuts_treasure('not a number'))


class TestExamine(unittest.TestCase):
    def test_first_examine_disarms_trap_and_marks_examined(self):
        player = _FakePlayer()
        lines = examine(player)
        self.assertIsNotNone(lines)
        self.assertTrue(any('deadly trap' in l for l in lines))
        self.assertTrue(player.tuts_treasure.examined)
        self.assertTrue(player.unsaved_changes)

    def test_int_gain_gated_below_25_but_can_overshoot(self):
        # SPUR's own `if pi<25 pi=pi+2` -- a single application can push
        # slightly past 25 (24 -> 26); it just stops applying once at/above.
        player = _FakePlayer(intelligence=24)
        lines = examine(player)
        self.assertEqual(player.stats['Intelligence'], 26)
        self.assertIn('You feel a bit smarter', lines)

        player2 = _FakePlayer(intelligence=25)
        lines2 = examine(player2)
        self.assertEqual(player2.stats['Intelligence'], 25)
        self.assertNotIn('You feel a bit smarter', lines2)

    def test_repeat_examine_returns_none(self):
        player = _FakePlayer(examined=True)
        self.assertIsNone(examine(player))


class TestGetWithoutExamining(unittest.TestCase):
    def test_triggers_mummys_curse(self):
        player = _FakePlayer(experience=150, constitution=10, intelligence=10, hit_points=30)
        outcome = get(player)
        self.assertIsInstance(outcome, GetOutcome)
        self.assertFalse(outcome.remove_from_room)
        self.assertFalse(player.tuts_treasure.taken)
        self.assertEqual(outcome.gold_awarded, 0)
        joined = ' '.join(outcome.lines)
        self.assertIn("Mummy's curse", joined)
        self.assertIn('STRANGE SMOKE', joined)

    def test_curse_caps_xp_con_int_and_hp(self):
        player = _FakePlayer(experience=500, constitution=20, intelligence=20, hit_points=30)
        get(player)
        self.assertEqual(player.experience, 100)
        self.assertEqual(player.stats['Constitution'], 5)
        self.assertEqual(player.stats['Intelligence'], 15)  # -5, not capped like the others
        self.assertEqual(player.hit_points, 5)

    def test_curse_does_not_reduce_already_low_stats(self):
        player = _FakePlayer(experience=50, constitution=3, intelligence=3, hit_points=4)
        get(player)
        self.assertEqual(player.experience, 50)
        self.assertEqual(player.stats['Constitution'], 3)
        self.assertEqual(player.stats['Intelligence'], 3)
        self.assertEqual(player.hit_points, 4)


class TestGetAfterExamining(unittest.TestCase):
    def test_awards_gold_and_marks_taken(self):
        player = _FakePlayer(examined=True, silver_in_hand=1000)
        outcome = get(player)
        self.assertTrue(player.tuts_treasure.taken)
        self.assertTrue(outcome.remove_from_room)
        self.assertEqual(outcome.gold_awarded, 9000)
        self.assertEqual(player.get_silver('IN_HAND'), 10000)
        self.assertIn('BINGO! SUCH WEALTH!!', outcome.lines)

    def test_already_taken_is_a_harmless_no_op(self):
        player = _FakePlayer(examined=True, taken=True, silver_in_hand=500)
        outcome = get(player)
        self.assertTrue(outcome.remove_from_room)
        self.assertEqual(outcome.gold_awarded, 0)
        self.assertEqual(player.get_silver('IN_HAND'), 500)


class TestPlayerIntegration(unittest.TestCase):
    """player.tuts_treasure exists on a real Player and round-trips through
    save()/_load() -- see player.py's simple_keys/shield_proficiency-style
    merge blocks."""

    def test_default_player_has_untouched_tuts_treasure(self):
        # Compare by shape (dataclasses.fields), not isinstance/class identity:
        # tests/test_reload.py exercises RELOAD on flags.py mid-suite via
        # importlib.reload(), which -- as commands/reload.py's own docstring
        # warns -- mints a brand-new TutTreasure class object; any module
        # not reloaded in the same breath (this test file's own top-level
        # `from flags import TutTreasure`, captured at collection time)
        # would then hold a stale reference that fails isinstance() against
        # a same-shape-but-different-identity class from a later Player().
        player = Player()
        self.assertEqual(
            {f.name for f in dataclasses.fields(player.tuts_treasure)},
            {'examined', 'taken'},
        )
        self.assertFalse(player.tuts_treasure.examined)
        self.assertFalse(player.tuts_treasure.taken)

    def test_save_and_load_round_trip(self, tmp_path=None):
        import tempfile
        import net_common

        with tempfile.TemporaryDirectory() as tmp:
            net_common.run_server_dir = tmp
            player = Player(id='tutsave', name='Tutsave')
            player.tuts_treasure.examined = True
            player.tuts_treasure.taken = True
            player.unsaved_changes = True
            self.assertTrue(player.save(force=True))

            reloaded = Player(id='tutsave', name='Tutsave')
            self.assertTrue(reloaded._load())
            self.assertTrue(reloaded.tuts_treasure.examined)
            self.assertTrue(reloaded.tuts_treasure.taken)


class TestGetCommandHook(unittest.IsolatedAsyncioTestCase):
    async def test_get_command_routes_tuts_treasure_through_quest_module(self):
        from commands.get import GetCommand
        from inventory import InventoryEntry
        from items import Item, ItemCategory

        ctx = MagicMock()
        ctx.player = _FakePlayer(examined=True, silver_in_hand=0)
        ctx.player.inventory = MagicMock()
        ctx.player.inventory.find.return_value = None
        ctx.player.inventory.is_full.return_value = False
        ctx.send = AsyncMock()

        item = Item(id_number=86, name="Tut's Treasure", category=ItemCategory.ITEM)
        entry = InventoryEntry(item=item)
        removed = []
        result = await GetCommand()._pick_up(ctx, ctx.player.inventory, "Tut's Treasure", entry, lambda: removed.append(True))

        self.assertTrue(ctx.player.tuts_treasure.taken)
        self.assertEqual(len(removed), 1)   # remove_fn() called -- item leaves the room
        ctx.player.inventory.add.assert_not_called()  # never added as an inventory item


class TestExamineCommandHook(unittest.IsolatedAsyncioTestCase):
    async def test_examine_examines_room_item_before_pickup(self):
        from commands.examine import ExamineCommand

        ctx = MagicMock()
        ctx.player = _FakePlayer()
        ctx.player.inventory = MagicMock()
        ctx.player.inventory.entries.return_value = []
        ctx.send = AsyncMock()
        ctx.send_room = AsyncMock()

        from items import Item, ItemCategory
        from inventory import InventoryEntry
        item = Item(id_number=86, name="Tut's Treasure", category=ItemCategory.ITEM)
        entry = InventoryEntry(item=item)

        import commands.get as get_mod
        orig = get_mod._room_available_items
        get_mod._room_available_items = lambda c: [("Tut's Treasure", entry, lambda: None)]
        try:
            await ExamineCommand().execute(ctx, "tut's", "treasure")
        finally:
            get_mod._room_available_items = orig

        self.assertTrue(ctx.player.tuts_treasure.examined)
        sent = ' '.join(str(c) for call in ctx.send.await_args_list for c in call.args)
        self.assertIn('deadly trap', sent)


if __name__ == '__main__':
    unittest.main()
