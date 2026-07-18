"""tests/combat/test_stats_allies.py — commands/stats.py's ally section.

SPUR.MISC5.S's "status" subroutine (STATS/STAT2) never mentions allies
at all -- new addition, Ryan's request.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from bar.ally_data import Ally, AllyFlags, AllyStatus
from base_classes import Guild, PlayerStat
from commands.stats import _build_stats_lines
from party import Party


def _make_player(party=None):
    player = MagicMock()
    player.name = 'Rulan'
    player.stats = {s: 10 for s in PlayerStat}
    player.shield = 0
    player.armor = 0
    player.get_silver = lambda k: 100
    player.experience = 0
    player.dead_monsters = []
    player.honor = 1000
    player.xp_level = 1
    player.hit_points = 20
    player.guild = Guild.CIVILIAN
    player.char_class = None
    player.char_race = None
    player.active_shield_id = None
    player.shield_proficiency = {}
    player.query_flag = lambda f: False
    player.wizard_glow = False
    player.tuts_treasure = None
    player.time_remaining_minutes = None
    player.party = party if party is not None else Party()
    return player


def _make_ally(name='Grog', strength=15, to_hit=5, hit_points=30, flags=None):
    a = Ally(name=name, gender='m', strength=strength, to_hit=to_hit, flags=flags)
    a.hit_points = hit_points
    return a


class TestStatsAllySection(unittest.TestCase):
    def test_no_allies_shows_zero_of_three(self):
        lines = _build_stats_lines(_make_player())
        self.assertIn('Allies: 0/3', lines)

    def test_no_allies_shows_sniff_message(self):
        lines = _build_stats_lines(_make_player())
        self.assertIn('  No allies... sniff...', lines)

    def test_owned_ally_listed_with_stats(self):
        ally = _make_ally('Grog', strength=15, to_hit=5, hit_points=30)
        ally.status = AllyStatus.SERVANT
        player = _make_player(party=Party(members=[ally]))
        lines = _build_stats_lines(player)
        self.assertIn('Allies: 1/3', lines)
        row = next(l for l in lines if 'Grog' in l)
        self.assertIn('Str 15', row)
        self.assertIn('HP  30', row)
        self.assertIn('50%', row)  # to_hit * 10

    def test_elite_ally_tagged(self):
        ally = _make_ally('Grog', flags=[AllyFlags.ELITE])
        ally.status = AllyStatus.SERVANT
        player = _make_player(party=Party(members=[ally]))
        lines = _build_stats_lines(player)
        row = next(l for l in lines if 'Grog' in l)
        self.assertIn('[Elite]', row)

    def test_servant_status_not_tagged(self):
        """SERVANT (a normally-owned ally) is the expected steady state --
        no [SERVANT] noise, matching pick_ally()'s own convention."""
        ally = _make_ally('Grog')
        ally.status = AllyStatus.SERVANT
        player = _make_player(party=Party(members=[ally]))
        lines = _build_stats_lines(player)
        row = next(l for l in lines if 'Grog' in l)
        self.assertNotIn('[SERVANT]', row)

    def test_unconscious_ally_tagged(self):
        ally = _make_ally('Grog')
        ally.status = AllyStatus.UNCONSCIOUS
        player = _make_player(party=Party(members=[ally]))
        lines = _build_stats_lines(player)
        row = next(l for l in lines if 'Grog' in l)
        self.assertIn('[UNCONSCIOUS]', row)

    def test_multiple_allies_all_listed(self):
        a1 = _make_ally('Grog')
        a2 = _make_ally('Persephone')
        player = _make_player(party=Party(members=[a1, a2]))
        lines = _build_stats_lines(player)
        self.assertIn('Allies: 2/3', lines)
        self.assertTrue(any('Grog' in l for l in lines))
        self.assertTrue(any('Persephone' in l for l in lines))

    def test_goddess_ally_tagged(self):
        ally = _make_ally('Persephone', flags=[AllyFlags.GODDESS])
        player = _make_player(party=Party(members=[ally]))
        lines = _build_stats_lines(player)
        row = next(l for l in lines if 'Persephone' in l)
        self.assertIn('[Goddess]', row)

    def test_mount_ally_tagged(self):
        ally = _make_ally('Trigger', flags=[AllyFlags.MOUNT])
        player = _make_player(party=Party(members=[ally]))
        lines = _build_stats_lines(player)
        row = next(l for l in lines if 'Trigger' in l)
        self.assertIn('[Mount]', row)

    def test_multiple_flags_all_tagged(self):
        ally = _make_ally('Trigger', flags=[AllyFlags.MOUNT, AllyFlags.SADDLED, AllyFlags.ARMORED])
        player = _make_player(party=Party(members=[ally]))
        lines = _build_stats_lines(player)
        row = next(l for l in lines if 'Trigger' in l)
        self.assertIn('[Mount]', row)
        self.assertIn('[Saddled]', row)
        self.assertIn('[Armored]', row)

    def test_tracking_flag_shows_range(self):
        ally = _make_ally('Grog', flags=[AllyFlags.TRACKING])
        ally.tracking_range = 5
        player = _make_player(party=Party(members=[ally]))
        lines = _build_stats_lines(player)
        row = next(l for l in lines if 'Grog' in l)
        self.assertIn('[Tracking r5]', row)

    def test_find_things_flag_shows_percentage(self):
        ally = _make_ally('Grog', flags=[AllyFlags.FIND_THINGS])
        ally.find_percentage = 40
        player = _make_player(party=Party(members=[ally]))
        lines = _build_stats_lines(player)
        row = next(l for l in lines if 'Grog' in l)
        self.assertIn('[Finder 40%]', row)

    def test_body_build_flag_shows_level(self):
        ally = _make_ally('Grog', flags=[AllyFlags.BODY_BUILD])
        ally.body_build = 3
        player = _make_player(party=Party(members=[ally]))
        lines = _build_stats_lines(player)
        row = next(l for l in lines if 'Grog' in l)
        self.assertIn('[Body Built +3]', row)

    def test_no_flags_no_tags(self):
        ally = _make_ally('Grog', flags=[])
        player = _make_player(party=Party(members=[ally]))
        lines = _build_stats_lines(player)
        row = next(l for l in lines if 'Grog' in l)
        self.assertNotIn('[', row)


if __name__ == '__main__':
    unittest.main()
