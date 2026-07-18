"""tests/combat/test_stats_guild_follow.py — commands/stats.py's Guild
Follow line: only shown for real guild members (SPUR.MISC5.S:202's
vv>=3 -- Civilian AND Outlaw are both below that cutoff). Ryan's request.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from base_classes import Guild, PlayerStat
from commands.stats import _build_stats_lines
from party import Party


def _make_player(guild):
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
    player.guild = guild
    player.char_class = None
    player.char_race = None
    player.active_shield_id = None
    player.shield_proficiency = {}
    player.query_flag = lambda f: False
    player.wizard_glow = None
    player.tuts_treasure = None
    player.time_remaining_minutes = None
    player.party = Party()
    return player


class TestGuildFollowLine(unittest.TestCase):
    def test_civilian_shows_no_guild_follow_line(self):
        lines = _build_stats_lines(_make_player(Guild.CIVILIAN))
        self.assertFalse(any('Guild Follow' in l for l in lines))

    def test_outlaw_shows_no_guild_follow_line(self):
        """Outlaw was previously missed -- only Civilian was excluded."""
        lines = _build_stats_lines(_make_player(Guild.OUTLAW))
        self.assertFalse(any('Guild Follow' in l for l in lines))

    def test_sword_shows_guild_follow_line(self):
        lines = _build_stats_lines(_make_player(Guild.SWORD))
        self.assertTrue(any('Guild Follow' in l for l in lines))

    def test_claw_shows_guild_follow_line(self):
        lines = _build_stats_lines(_make_player(Guild.CLAW))
        self.assertTrue(any('Guild Follow' in l for l in lines))

    def test_fist_shows_guild_follow_line(self):
        lines = _build_stats_lines(_make_player(Guild.FIST))
        self.assertTrue(any('Guild Follow' in l for l in lines))


if __name__ == '__main__':
    unittest.main()
