"""tests/combat/test_stats_wizard_glow.py — commands/stats.py's Wizard
Glow line: "xx/yy rounds remaining" for Wizards, "Not cast" when
inactive, and no line at all for non-Wizards. Ryan's request.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from base_classes import Guild, PlayerClass, PlayerStat
from commands.stats import _build_stats_lines
from party import Party


def _make_player(char_class=None, wizard_glow=None):
    player = MagicMock()
    player.name = 'Rulan'
    player.stats = {s: 10 for s in PlayerStat}
    player.shield = 0
    player.armor = 0
    player.get_silver = lambda k: 100
    player.experience = 0
    player.monsters_killed = []
    player.honor = 1000
    player.xp_level = 1
    player.hit_points = 20
    player.guild = Guild.CIVILIAN
    player.char_class = char_class
    player.char_race = None
    player.active_shield_id = None
    player.shield_proficiency = {}
    player.query_flag = lambda f: False
    player.wizard_glow = wizard_glow
    player.tuts_treasure = None
    player.time_remaining_minutes = None
    player.party = Party()
    return player


class TestWizardGlowLine(unittest.TestCase):
    def test_non_wizard_shows_no_glow_line(self):
        lines = _build_stats_lines(_make_player(char_class=PlayerClass.FIGHTER))
        self.assertFalse(any('Wizard Glow' in l for l in lines))

    def test_wizard_with_no_glow_shows_not_cast(self):
        lines = _build_stats_lines(_make_player(char_class=PlayerClass.WIZARD, wizard_glow=None))
        self.assertIn('Wizard Glow: Not cast', lines)

    def test_wizard_with_zero_rounds_shows_not_cast(self):
        lines = _build_stats_lines(_make_player(char_class=PlayerClass.WIZARD, wizard_glow=0))
        self.assertIn('Wizard Glow: Not cast', lines)

    def test_wizard_with_active_glow_shows_rounds(self):
        lines = _build_stats_lines(_make_player(char_class=PlayerClass.WIZARD, wizard_glow=7))
        self.assertIn('Wizard Glow: 7/20 rounds remaining', lines)


if __name__ == '__main__':
    unittest.main()
