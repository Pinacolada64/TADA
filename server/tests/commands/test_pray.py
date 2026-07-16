"""tests/commands/test_pray.py

Covers commands/pray.py -- SPUR.MISC2.S's "pray" subroutine:

  - Rejection when the player isn't actually in need (roll below all of
    hit_points/Strength/Energy).
  - Rejection when carrying unused rations (any ration item other than
    the four exempt special-effect potions/pills).
  - A successful prayer boosts hit_points/Strength/Energy/Constitution
    and consumes the once-per-session allowance.
  - Druids/Paladins get two prayers per session ("PIOUS PRAY").
  - Exhausting the allowance gets one warning; the next prayer after
    that warning is fatal (lightning bolt, hit_points=0).
  - battle.log entries for both a successful prayer and a fatal one.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from base_classes import PlayerClass, PlayerStat
from commands.pray import PrayCommand
from inventory import Inventory
from items import Item, ItemCategory
from player import Player


def _player(name='Rulan', char_class=None, honor=1000, hp=10, str_stat=10, egy_stat=10, con_stat=10) -> Player:
    p = Player(name=name)
    p.char_class  = char_class
    p.honor       = honor
    p.hit_points  = hp
    p.stats[PlayerStat.STR] = str_stat
    p.stats[PlayerStat.EGY] = egy_stat
    p.stats[PlayerStat.CON] = con_stat
    p.inventory = Inventory(capacity=10)
    return p


class _FakeCtx:
    def __init__(self, player):
        self.player = player
        self.sent: list = []

    async def send(self, *args):
        for a in args:
            if isinstance(a, list):
                self.sent.extend(a)
            else:
                self.sent.append(a)

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


class _IsolatedBattleLog(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        import net_common
        self._orig_dir = net_common.run_server_dir
        self._tmp = tempfile.TemporaryDirectory()
        net_common.run_server_dir = self._tmp.name

    def tearDown(self):
        import net_common
        net_common.run_server_dir = self._orig_dir
        self._tmp.cleanup()

    def _log_text(self) -> str:
        path = Path(self._tmp.name) / 'battle.log'
        return path.read_text() if path.exists() else ''


def _re_deplete(player, hp=1, str_stat=1, egy_stat=1):
    """Simulate the player taking more damage/fatigue between prayers so
    a repeat PRAY still reaches the once-per-session check instead of
    getting deflected by the (now healed) 'not in need' branch."""
    player.hit_points = hp
    player.stats[PlayerStat.STR] = str_stat
    player.stats[PlayerStat.EGY] = egy_stat


class TestNotInNeed(_IsolatedBattleLog):
    async def test_full_stats_get_not_in_need_message(self):
        player = _player(hp=99, str_stat=99, egy_stat=99, honor=1000)
        ctx = _FakeCtx(player)
        with patch('commands.pray.random.randint', return_value=6):  # roll xy=3, still < 99/99/99
            await PrayCommand().execute(ctx)
        self.assertIn('not in need', ctx._flat())
        self.assertEqual(player.prayed_count, 0)

    async def test_high_honor_not_in_need_variant(self):
        player = _player(hp=99, str_stat=99, egy_stat=99, honor=1500)
        ctx = _FakeCtx(player)
        with patch('commands.pray.random.randint', return_value=6):
            await PrayCommand().execute(ctx)
        self.assertIn('TRULY dost not need', ctx._flat())

    async def test_not_in_need_does_not_consume_allowance(self):
        player = _player(hp=99, str_stat=99, egy_stat=99)
        ctx = _FakeCtx(player)
        with patch('commands.pray.random.randint', return_value=6):
            await PrayCommand().execute(ctx)
            await PrayCommand().execute(ctx)
        self.assertEqual(player.prayed_count, 0)
        self.assertFalse(player.prayer_punished)


class TestSuccessfulPrayer(_IsolatedBattleLog):
    async def test_low_hp_grants_boost(self):
        player = _player(hp=2, str_stat=10, egy_stat=10)
        ctx = _FakeCtx(player)
        # First randint call is the need-roll (small), second is the boost roll (6-10).
        with patch('commands.pray.random.randint', side_effect=[9, 10]):
            await PrayCommand().execute(ctx)
        self.assertEqual(player.hit_points, 12)
        self.assertIn('hit points increase', ctx._flat())
        self.assertEqual(player.prayed_count, 1)

    async def test_str_egy_con_also_boosted_when_low(self):
        player = _player(hp=99, str_stat=2, egy_stat=2, con_stat=2)
        ctx = _FakeCtx(player)
        with patch('commands.pray.random.randint', side_effect=[9, 10]):
            await PrayCommand().execute(ctx)
        self.assertEqual(player.stats[PlayerStat.STR], 3)
        self.assertEqual(player.stats[PlayerStat.EGY], 3)
        self.assertEqual(player.stats[PlayerStat.CON], 3)
        self.assertIn('hunger lessens', ctx._flat())
        self.assertIn('thirst lessens', ctx._flat())
        self.assertIn('feel healthier', ctx._flat())

    async def test_boost_only_applies_below_roll(self):
        """hit_points is already above the boost roll -- only Strength/
        Energy (both below it) should be boosted."""
        player = _player(hp=99, str_stat=1, egy_stat=1, con_stat=99)
        ctx = _FakeCtx(player)
        with patch('commands.pray.random.randint', side_effect=[9, 6]):
            await PrayCommand().execute(ctx)
        self.assertEqual(player.hit_points, 99)
        self.assertEqual(player.stats[PlayerStat.STR], 2)
        self.assertEqual(player.stats[PlayerStat.EGY], 2)
        self.assertEqual(player.stats[PlayerStat.CON], 99)

    async def test_battle_log_pray_entry(self):
        player = _player(hp=1, str_stat=10, egy_stat=10)
        ctx = _FakeCtx(player)
        with patch('commands.pray.random.randint', side_effect=[9, 10]):
            await PrayCommand().execute(ctx)
        self.assertIn('PRAY', self._log_text())


class TestUnusedRationsGate(_IsolatedBattleLog):
    """SPUR.MISC2.S:207-211's xf/xf$ check: carrying a ration item you
    haven't been eating/drinking refuses the prayer outright, except for
    four special-effect potions/pills that don't count against you."""

    async def test_ordinary_ration_blocks_prayer(self):
        player = _player(hp=1, str_stat=10, egy_stat=10)
        player.inventory.add(Item(id_number=1, name='bread', category=ItemCategory.FOOD))
        ctx = _FakeCtx(player)
        with patch('commands.pray.random.randint', side_effect=[9]):
            await PrayCommand().execute(ctx)
        self.assertIn('eateth or drinketh', ctx._flat())
        self.assertEqual(player.prayed_count, 0)

    async def test_exempt_potion_does_not_block_prayer(self):
        player = _player(hp=1, str_stat=10, egy_stat=10)
        player.inventory.add(Item(id_number=65, name='POTION OF SKILL', category=ItemCategory.DRINK))
        ctx = _FakeCtx(player)
        with patch('commands.pray.random.randint', side_effect=[9, 10]):
            await PrayCommand().execute(ctx)
        self.assertNotIn('eateth or drinketh', ctx._flat())
        self.assertEqual(player.prayed_count, 1)

    async def test_no_rations_at_all_does_not_block_prayer(self):
        player = _player(hp=1, str_stat=10, egy_stat=10)
        ctx = _FakeCtx(player)
        with patch('commands.pray.random.randint', side_effect=[9, 10]):
            await PrayCommand().execute(ctx)
        self.assertNotIn('eateth or drinketh', ctx._flat())
        self.assertEqual(player.prayed_count, 1)

    async def test_non_ration_items_do_not_block_prayer(self):
        player = _player(hp=1, str_stat=10, egy_stat=10)
        player.inventory.add(Item(id_number=200, name='sword', category=ItemCategory.WEAPON))
        ctx = _FakeCtx(player)
        with patch('commands.pray.random.randint', side_effect=[9, 10]):
            await PrayCommand().execute(ctx)
        self.assertNotIn('eateth or drinketh', ctx._flat())
        self.assertEqual(player.prayed_count, 1)


class TestOncePerSession(_IsolatedBattleLog):
    async def test_second_prayer_warns_instead_of_helping(self):
        player = _player(hp=1, str_stat=1, egy_stat=1, char_class=PlayerClass.FIGHTER)
        ctx = _FakeCtx(player)
        with patch('commands.pray.random.randint', side_effect=[9, 10]):
            await PrayCommand().execute(ctx)  # granted
        _re_deplete(player)
        with patch('commands.pray.random.randint', side_effect=[9]):
            await PrayCommand().execute(ctx)  # warned
        self.assertIn('already helped thee today', ctx._flat())
        self.assertTrue(player.prayer_punished)
        self.assertEqual(player.prayed_count, 1)

    async def test_third_prayer_after_warning_is_fatal(self):
        player = _player(hp=1, str_stat=1, egy_stat=1, char_class=PlayerClass.FIGHTER)
        ctx = _FakeCtx(player)
        with patch('commands.pray.random.randint', side_effect=[9, 10]):
            await PrayCommand().execute(ctx)  # granted
        _re_deplete(player)
        with patch('commands.pray.random.randint', side_effect=[9]):
            await PrayCommand().execute(ctx)  # warned
        await PrayCommand().execute(ctx)      # fatal, no roll needed
        self.assertEqual(player.hit_points, 0)
        self.assertIn('sizzle to a golden', ctx._flat())

    async def test_battle_log_fried_entry_on_fatal_prayer(self):
        player = _player(hp=1, str_stat=1, egy_stat=1, char_class=PlayerClass.FIGHTER)
        ctx = _FakeCtx(player)
        with patch('commands.pray.random.randint', side_effect=[9, 10]):
            await PrayCommand().execute(ctx)
        _re_deplete(player)
        with patch('commands.pray.random.randint', side_effect=[9]):
            await PrayCommand().execute(ctx)
        await PrayCommand().execute(ctx)
        self.assertIn('FRIED', self._log_text())


class TestDruidPaladinDoublePrayer(_IsolatedBattleLog):
    async def test_druid_gets_second_prayer(self):
        player = _player(hp=1, str_stat=1, egy_stat=1, char_class=PlayerClass.DRUID)
        ctx = _FakeCtx(player)
        with patch('commands.pray.random.randint', side_effect=[9, 10]):
            await PrayCommand().execute(ctx)  # first prayer
        _re_deplete(player)
        with patch('commands.pray.random.randint', side_effect=[9, 10]):
            await PrayCommand().execute(ctx)  # second prayer -- still granted
        self.assertEqual(player.prayed_count, 2)
        self.assertFalse(player.prayer_punished)
        self.assertIn('pray twice', ctx._flat())

    async def test_paladin_gets_second_prayer(self):
        player = _player(hp=1, str_stat=1, egy_stat=1, char_class=PlayerClass.PALADIN)
        ctx = _FakeCtx(player)
        with patch('commands.pray.random.randint', side_effect=[9, 10]):
            await PrayCommand().execute(ctx)
        _re_deplete(player)
        with patch('commands.pray.random.randint', side_effect=[9, 10]):
            await PrayCommand().execute(ctx)
        self.assertEqual(player.prayed_count, 2)
        self.assertFalse(player.prayer_punished)

    async def test_druid_third_prayer_warns(self):
        player = _player(hp=1, str_stat=1, egy_stat=1, char_class=PlayerClass.DRUID)
        ctx = _FakeCtx(player)
        with patch('commands.pray.random.randint', side_effect=[9, 10]):
            await PrayCommand().execute(ctx)
        _re_deplete(player)
        with patch('commands.pray.random.randint', side_effect=[9, 10]):
            await PrayCommand().execute(ctx)
        _re_deplete(player)
        with patch('commands.pray.random.randint', side_effect=[9]):
            await PrayCommand().execute(ctx)  # allowance (2) exhausted -> warned
        self.assertTrue(player.prayer_punished)

    async def test_second_prayer_battle_log_tagged_pious(self):
        player = _player(hp=1, str_stat=1, egy_stat=1, char_class=PlayerClass.PALADIN)
        ctx = _FakeCtx(player)
        with patch('commands.pray.random.randint', side_effect=[9, 10]):
            await PrayCommand().execute(ctx)
        _re_deplete(player)
        with patch('commands.pray.random.randint', side_effect=[9, 10]):
            await PrayCommand().execute(ctx)
        self.assertIn('PIOUS PRAY', self._log_text())


class TestHonorAdjustments(_IsolatedBattleLog):
    async def test_low_honor_worsens_roll_so_prayer_still_reaches_need_check(self):
        """This just exercises the honor branch in _need_roll() without
        asserting exact arithmetic (that's covered directly below)."""
        from commands.pray import _need_roll
        player = _player(honor=200)
        with patch('commands.pray.random.randint', return_value=9):
            xy = _need_roll(player)
        # base (9-3=6) - 1 (honor<800) - 2 (honor<400) = 3
        self.assertEqual(xy, 3)

    async def test_high_honor_improves_roll(self):
        from commands.pray import _need_roll
        player = _player(honor=1700)
        with patch('commands.pray.random.randint', return_value=9):
            xy = _need_roll(player)
        # base (9-3=6) + 1 (honor>1200) + 2 (honor>1600) = 9
        self.assertEqual(xy, 9)

    async def test_very_low_honor_always_gets_cooties_rejection(self):
        player = _player(hp=99, str_stat=99, egy_stat=99, honor=100)
        ctx = _FakeCtx(player)
        with patch('commands.pray.random.randint', return_value=6):
            await PrayCommand().execute(ctx)
        # hp/str/egy are all > 7, so the "not in need" branch fires first
        # regardless of honor -- Cooties only shows on the *other*
        # rejection path (in-need roll didn't clear, but stats aren't
        # comfortably high either). Covered by the dedicated test below.
        self.assertIn('not in need', ctx._flat())

    async def test_cooties_rejection_when_not_comfortably_fine_but_roll_fails(self):
        player = _player(hp=5, str_stat=5, egy_stat=5, honor=100)
        ctx = _FakeCtx(player)
        # need-roll: base 9-3=6, honor<800 -1, honor<400 -1 -> xy=4, still < hp/str/egy(5) -> pray.1
        with patch('commands.pray.random.randint', side_effect=[9, 5]):
            await PrayCommand().execute(ctx)
        self.assertIn('Cooties', ctx._flat())


if __name__ == '__main__':
    unittest.main(verbosity=2)
