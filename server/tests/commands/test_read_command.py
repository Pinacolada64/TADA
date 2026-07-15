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

from base_classes import Combination, CombinationTypes, PlayerStat
from commands.read import ReadCommand
from inventory import Inventory
from item_system import Item, ItemType
from shoppe.elevator import get_combination

_SCRAP_ID = 69


def make_player(*, with_scrap: bool = True, honor: int = 1000, intelligence: int = 10) -> MagicMock:
    p = MagicMock()
    p.name = 'TestPlayer'
    p.honor = honor
    p.combinations = {}
    p.unsaved_changes = False
    p.stats = {PlayerStat.INT: intelligence}
    p.read_books = []
    p.inventory = Inventory(capacity=10)
    if with_scrap:
        p.inventory.add(Item(number=_SCRAP_ID, name='scrap of paper', type=ItemType.BOOK, price=4))
    return p


def make_ctx(player, prompts: list) -> MagicMock:
    ctx = MagicMock()
    ctx.player = player
    ctx.send = AsyncMock()
    ctx.server.books = {}  # no recovered book text by default; tests opt in explicitly
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


class TestIntelligenceGate(unittest.IsolatedAsyncioTestCase):
    """SPUR.MISC2.S read: `if pi<6 print "Not smart enough to read!":goto advent`."""

    async def test_low_intelligence_blocks_reading_entirely(self):
        player = make_player(intelligence=5)
        ctx = make_ctx(player, [])
        res = await ReadCommand().execute(ctx, 'scrap')
        self.assertTrue(res.success)
        self.assertIn('not smart enough', _sent(ctx).lower())
        self.assertNotIn(CombinationTypes.ELEVATOR, player.combinations)

    async def test_intelligence_at_threshold_allows_reading(self):
        player = make_player(intelligence=6)
        ctx = make_ctx(player, [])
        res = await ReadCommand().execute(ctx)
        self.assertNotIn('not smart enough', _sent(ctx).lower())


class TestReadOrdinaryBook(unittest.IsolatedAsyncioTestCase):
    async def test_reading_other_book_does_not_touch_combinations(self):
        player = make_player(with_scrap=False)
        player.inventory.add(Item(number=30, name='The Howling', type=ItemType.BOOK, price=1))
        ctx = make_ctx(player, [])
        res = await ReadCommand().execute(ctx, 'howling')
        self.assertTrue(res.success)
        self.assertNotIn(CombinationTypes.ELEVATOR, player.combinations)
        self.assertIn('howling', _sent(ctx).lower())

    async def test_reading_other_book_does_not_consume_it(self):
        """Deliberate deviation from SPUR: reference books stay re-readable
        instead of vanishing after one read."""
        player = make_player(with_scrap=False)
        player.inventory.add(Item(number=30, name='The Howling', type=ItemType.BOOK, price=1))
        ctx = make_ctx(player, [])
        await ReadCommand().execute(ctx, 'howling')
        self.assertEqual(len(player.inventory.find(name='The Howling')), 1)


class TestReadingWisdomBonus(unittest.IsolatedAsyncioTestCase):
    """SPUR.MISC2.S:316's `if pw<25 pw=pw+1:print "(You feel wiser..)"` --
    fires on every consumed book there (scroll or not); ported as a
    first-read-only bonus (player.read_books) since reference books stay
    re-readable in this port instead of being consumed."""

    def _player_with_book(self, wis=10):
        player = make_player(with_scrap=False)
        player.stats = {PlayerStat.INT: 10, PlayerStat.WIS: wis}
        player.inventory.add(Item(number=30, name='The Howling', type=ItemType.BOOK, price=1))
        return player

    async def test_first_read_grants_one_wisdom(self):
        player = self._player_with_book(wis=10)
        ctx = make_ctx(player, [])
        await ReadCommand().execute(ctx, 'howling')
        self.assertEqual(player.stats[PlayerStat.WIS], 11)
        self.assertIn('You feel wiser..', _sent(ctx))
        self.assertEqual(player.read_books, [30])

    async def test_second_read_of_same_book_grants_nothing(self):
        player = self._player_with_book(wis=10)
        ctx1 = make_ctx(player, [])
        await ReadCommand().execute(ctx1, 'howling')
        ctx2 = make_ctx(player, [])
        await ReadCommand().execute(ctx2, 'howling')
        self.assertEqual(player.stats[PlayerStat.WIS], 11)  # only +1, not +2
        self.assertNotIn('You feel wiser..', _sent(ctx2))

    async def test_no_bonus_at_or_above_cap(self):
        player = self._player_with_book(wis=25)
        ctx = make_ctx(player, [])
        await ReadCommand().execute(ctx, 'howling')
        self.assertEqual(player.stats[PlayerStat.WIS], 25)
        self.assertNotIn('You feel wiser..', _sent(ctx))
        # Still marked read, even though no points were gained.
        self.assertEqual(player.read_books, [30])

    async def test_scroll_of_endurance_also_grants_wisdom(self):
        from base_classes import PlayerRace
        player = make_player(with_scrap=False)
        player.stats = {PlayerStat.INT: 10, PlayerStat.WIS: 10}
        player.xp_level = 1
        player.char_race = PlayerRace.HUMAN
        player.inventory.add(_make_scroll(89, 'Scroll of Endurance'))
        ctx = make_ctx(player, ['1'])
        await ReadCommand().execute(ctx)
        self.assertEqual(player.stats[PlayerStat.WIS], 11)
        self.assertIn('You feel wiser..', _sent(ctx))

    async def test_scrap_of_paper_grants_wisdom_too(self):
        """SPUR's `a=69` branch also reaches scroll.b's Wisdom gain."""
        player = make_player(with_scrap=True, honor=1000)
        player.stats[PlayerStat.WIS] = 10
        # '1' selects the scrap of paper from the book list; then the two
        # scrap-of-paper flavor prompts (Art thou true of heart / Good or Evil).
        ctx = make_ctx(player, ['1', '', 'G'])
        await ReadCommand().execute(ctx)
        self.assertEqual(player.stats[PlayerStat.WIS], 11)
        self.assertIn('You feel wiser..', _sent(ctx))

    async def test_claim_tag_does_not_grant_wisdom(self):
        """A TADA-original item, no SPUR precedent for a reading bonus."""
        p = make_player(with_scrap=False)
        p.stats[PlayerStat.WIS] = 10
        p.inventory.add(_make_claim_tag())
        combo = Combination(CombinationTypes.LOCKER)
        combo.combination = (1, 2, 3)
        p.combinations[CombinationTypes.LOCKER] = combo
        ctx = make_ctx(p, ['1'])
        await ReadCommand().execute(ctx)
        self.assertEqual(p.stats[PlayerStat.WIS], 10)
        self.assertEqual(p.read_books, [])


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
        p.stats[PlayerStat.INT] = 10  # ensure the intelligence gate doesn't block reading
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


_CLAIM_TAG_ID = 164


def _make_claim_tag():
    """The real item, as constructed by shoppe/locker.py -- items.Item with
    only `.category` set, no `.type` -- to catch the ItemType.BOOK-only
    filter mismatch rather than a test double that sidesteps it."""
    from items import Item as RealItem, ItemCategory
    return RealItem(id_number=_CLAIM_TAG_ID, name='brass claim tag', category=ItemCategory.ITEM)


class TestReadClaimTag(unittest.IsolatedAsyncioTestCase):

    def _player_with_tag_and_combo(self, combo_digits=(11, 22, 33)):
        p = make_player(with_scrap=False)
        p.inventory.add(_make_claim_tag())
        combo = Combination(CombinationTypes.LOCKER)
        combo.combination = combo_digits
        p.combinations[CombinationTypes.LOCKER] = combo
        return p

    async def test_claim_tag_listed_despite_no_type_attribute(self):
        """Regression: items.Item (the real construction path, via
        shoppe/locker.py) never sets `.type`, only `.category` -- the old
        ItemType.BOOK-only filter would silently hide it from `read`."""
        p = self._player_with_tag_and_combo()
        ctx = make_ctx(p, [''])
        await ReadCommand().execute(ctx)
        self.assertIn('brass claim tag', _sent(ctx))

    async def test_reading_claim_tag_shows_locker_combination(self):
        p = self._player_with_tag_and_combo((11, 22, 33))
        ctx = make_ctx(p, ['1'])
        await ReadCommand().execute(ctx)
        self.assertIn('11-22-33', _sent(ctx))

    async def test_reading_claim_tag_does_not_consume_it(self):
        p = self._player_with_tag_and_combo()
        ctx = make_ctx(p, ['1'])
        await ReadCommand().execute(ctx)
        self.assertEqual(len(p.inventory.find(name='brass claim tag')), 1)

    async def test_reading_by_name(self):
        p = self._player_with_tag_and_combo((5, 6, 7))
        ctx = make_ctx(p, [])
        await ReadCommand().execute(ctx, 'brass', 'claim', 'tag')
        self.assertIn('05-06-07', _sent(ctx))

    async def test_claim_tag_without_combination_does_not_crash(self):
        """Shouldn't normally happen -- the tag is only ever handed over
        alongside the combination -- but must not raise if it does."""
        p = make_player(with_scrap=False)
        p.inventory.add(_make_claim_tag())
        ctx = make_ctx(p, ['1'])
        await ReadCommand().execute(ctx)
        self.assertIn("can't quite make it out", _sent(ctx))


def _make_scroll(number, name):
    """A scroll as it actually arrives in inventory via commands/get.py:
    items.Item with only .category set -- .type gets tagged on separately
    (see commands/get.py's raw_type handling), matching the real pickup
    path rather than a test double that sidesteps it."""
    from items import Item as RealItem, ItemCategory
    item = RealItem(id_number=number, name=name, category=ItemCategory.ITEM)
    item.type = ItemType.BOOK
    return item


class TestReadScroll(unittest.IsolatedAsyncioTestCase):

    def _player_with_scroll(self, number, name, **attrs):
        p = make_player(with_scrap=False)
        p.inventory.add(_make_scroll(number, name))
        for k, v in attrs.items():
            setattr(p, k, v)
        return p

    async def test_scroll_of_endurance_sets_hp(self):
        from base_classes import PlayerRace
        p = self._player_with_scroll(89, 'Scroll of Endurance',
                                     xp_level=5, char_race=PlayerRace.HUMAN,
                                     hit_points=1)
        ctx = make_ctx(p, ['1'])
        await ReadCommand().execute(ctx)
        self.assertEqual(p.hit_points, 35)  # 30 + xp_level(5), no Ogre bonus

    async def test_scroll_of_endurance_ogre_bonus(self):
        from base_classes import PlayerRace
        p = self._player_with_scroll(92, 'Scroll of Endurance',  # the "other" duplicate
                                     xp_level=5, char_race=PlayerRace.OGRE,
                                     hit_points=1)
        ctx = make_ctx(p, ['1'])
        await ReadCommand().execute(ctx)
        self.assertEqual(p.hit_points, 37)  # 30 + 5 + 2 (Ogre)

    async def test_scroll_of_endurance_consumed(self):
        p = self._player_with_scroll(89, 'Scroll of Endurance', xp_level=1)
        ctx = make_ctx(p, ['1'])
        await ReadCommand().execute(ctx)
        self.assertEqual(len(p.inventory.find(name='Scroll of Endurance')), 0)
        self.assertIn('The scroll catches fire and burns..', _sent(ctx))

    async def test_scroll_of_anti_magic_clears_spells(self):
        from items import Item as RealItem, ItemCategory
        p = self._player_with_scroll(88, 'Scroll of Anti-Magic')
        spell = RealItem(id_number=1, name='Fireball', category=ItemCategory.SPELL)
        p.inventory.add(spell)
        self.assertEqual(len(p.inventory.entries(category=str(ItemCategory.SPELL))), 1)

        # Books list only shows BOOK-typed entries; the spell isn't one, so
        # the scroll is still the only (and first) entry shown.
        ctx = make_ctx(p, ['1'])
        await ReadCommand().execute(ctx)
        self.assertEqual(len(p.inventory.entries(category=str(ItemCategory.SPELL))), 0)

    async def test_scroll_of_doorways_not_yet_implemented(self):
        p = self._player_with_scroll(90, 'Scroll of Doorways')
        ctx = make_ctx(p, ['1'])
        await ReadCommand().execute(ctx)
        flat = _sent(ctx)
        self.assertIn("isn't available yet", flat)
        # Still consumed like any other scroll, matching SPUR.
        self.assertEqual(len(p.inventory.find(name='Scroll of Doorways')), 0)

    async def test_unrelated_scroll_gets_generic_burn_message_only(self):
        """A scroll name matching none of the three special substrings
        still gets consumed with the generic burn message (SPUR: every
        'SCROLL'-named book goes through scroll.b regardless)."""
        p = self._player_with_scroll(93, "Some Other Scroll")
        ctx = make_ctx(p, ['1'])
        await ReadCommand().execute(ctx)
        flat = _sent(ctx)
        self.assertIn('The scroll catches fire and burns..', flat)
        self.assertNotIn('invigorated', flat)
        self.assertNotIn('fade from memory', flat)


if __name__ == '__main__':
    unittest.main()
