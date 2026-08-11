"""tests/test_new_player_roll_stats.py

Regression tests for a real report from an alpha tester: character
creation's stat-rolling step never explained the 4d6-drop-lowest
technique, and race/class bonuses/penalties were applied to the rolled
stats silently -- the only way the tester noticed was comparing the
accepted stats against what ended up on the finished character by hand.

commands/new_player.py's _roll_stats() now:
  - Shows a one-line explanation of the 4d6-drop-lowest technique before
    the rolled-stats table.
  - After acceptance, reports every stat race/class bonuses touched, with
    its before -> after value and signed delta.

Run with:
    python -m pytest tests/test_new_player_roll_stats.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from base_classes import PlayerClass, PlayerRace, PlayerStat
from commands.new_player import _roll_stats


class _FakePlayer:
    def __init__(self, char_race=None, char_class=None):
        self.stats      = {}
        self.char_race  = char_race
        self.char_class = char_class


class _FakeCtx:
    def __init__(self, responses, char_race=None, char_class=None):
        self._q = list(responses)
        self.sent: list = []
        self.player = _FakePlayer(char_race, char_class)

    async def send(self, *args):
        for a in args:
            self.sent.append(a)

    async def prompt(self, prompt_text: str = '', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        out = []
        for item in self.sent:
            if isinstance(item, (list, tuple)):
                out.extend(str(x) for x in item)
            else:
                out.append(str(item))
        return '\n'.join(out)


def _fixed_rolls(*groups, hp_roll=5):
    """Return a side_effect list feeding random.randint(1, 6) calls: each
    group of 4 ints becomes one stat's 4d6 roll, in _STAT_ORDER order.

    A trailing *hp_roll* is appended for _roll_stats()'s post-acceptance
    random.randint(0, 9) HP roll (SPUR-code/SPUR.NEW.S "stat1"/"stat2")."""
    flat = []
    for g in groups:
        flat.extend(g)
    flat.append(hp_roll)
    return flat


class TestRollStatsExplanation(unittest.IsolatedAsyncioTestCase):

    async def test_explains_4d6_drop_lowest_technique(self):
        ctx = _FakeCtx(['y'])
        with patch('random.randint', side_effect=_fixed_rolls(*([[3, 3, 3, 3]] * 7))):
            result = await _roll_stats(ctx)
        self.assertTrue(result)
        text = ctx._flat()
        self.assertIn('4 six-sided dice', text)
        self.assertIn('lowest', text)
        self.assertIn('dropped', text)

    async def test_shows_individual_rolls_and_drop_per_stat(self):
        ctx = _FakeCtx(['y'])
        with patch('random.randint', side_effect=_fixed_rolls([6, 5, 4, 1], *([[3, 3, 3, 3]] * 6))):
            await _roll_stats(ctx)
        text = ctx._flat()
        self.assertIn('rolled', text)
        self.assertIn('dropped 1', text)


class TestRollStatsBonusReporting(unittest.IsolatedAsyncioTestCase):

    async def test_race_and_class_deltas_are_reported(self):
        # OGRE: CON+2 DEX-1 INT-2 STR+3 WIS-1 ; FIGHTER: CON+2 DEX-1 INT-2 STR+2 EGY+2
        ctx = _FakeCtx(['y'], char_race=PlayerRace.OGRE, char_class=PlayerClass.FIGHTER)
        with patch('random.randint', side_effect=_fixed_rolls(*([[3, 3, 3, 3]] * 7))):
            await _roll_stats(ctx)
        text = ctx._flat()
        self.assertIn('Ogre', text)
        self.assertIn('Fighter', text)
        self.assertIn('bonuses', text)
        # STR rolled 9 (3+3+3, lowest 3 dropped), then Ogre +3 and Fighter +2 -> 14
        self.assertEqual(ctx.player.stats[PlayerStat.STR], 14)
        self.assertIn('STR', text)
        self.assertIn('9 -> 14', text)
        self.assertIn('(+5)', text)

    async def test_no_bonus_report_when_nothing_changes(self):
        ctx = _FakeCtx(['y'], char_race=None, char_class=None)
        with patch('random.randint', side_effect=_fixed_rolls(*([[3, 3, 3, 3]] * 7))):
            await _roll_stats(ctx)
        text = ctx._flat()
        self.assertNotIn('bonuses', text)

    async def test_accepted_stats_include_deltas_not_just_raw_rolls(self):
        """The bug as reported: before/after stats differ silently. Assert
        the player's final stats actually reflect the applied deltas, and
        that this is visible in what was sent to the player."""
        ctx = _FakeCtx(['y'], char_race=PlayerRace.DWARF, char_class=None)
        with patch('random.randint', side_effect=_fixed_rolls(*([[3, 3, 3, 3]] * 7))):
            await _roll_stats(ctx)
        # DWARF: CON+1 DEX-1 CHR+2 -- CHR is now rolled like every other
        # stat (9, from three dropped-lowest 3s), plus the +2 race bonus.
        self.assertEqual(ctx.player.stats[PlayerStat.CHR], 11)
        text = ctx._flat()
        self.assertIn('CHR', text)
        self.assertIn('9 -> 11', text)
        self.assertIn('(+2)', text)


class TestRollStatsHitPoints(unittest.IsolatedAsyncioTestCase):
    """SPUR-code/SPUR.NEW.S "stat1"/"stat2": hp is rolled from the average
    of the post-race/class-delta stats plus random(0, 9), not a flat
    default -- see Player.hit_points' own flat-10 fallback, which this
    replaces for new characters."""

    async def test_hit_points_is_average_of_final_stats_plus_roll(self):
        ctx = _FakeCtx(['y'], char_race=None, char_class=None)
        with patch('random.randint', side_effect=_fixed_rolls(*([[3, 3, 3, 3]] * 7), hp_roll=4)):
            await _roll_stats(ctx)
        # All 7 stats (including CHR) roll to 9, but HP only averages the
        # original 6 SPUR stats (Charisma has no SPUR precedent -- see
        # CHARISMA_AUDIT.md), so the average is still exactly 9 regardless
        # of CHR's value.
        self.assertEqual(ctx.player.hit_points, 13)
        self.assertIn('Hit Points   : 13', ctx._flat())


if __name__ == '__main__':
    unittest.main()
