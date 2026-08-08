"""tests/combat/test_stats_equipped_names.py — commands/stats.py's Shield/
Armor line naming the actual equipped item, not just the flat percentage.

Regression coverage: STAT used to show only "Shield  :  40%   Armor    :
30%" with no way to tell *which* shield/armor item those percentages came
from. Fixed 2026-08-08 alongside player.active_armor_id (new, mirrors
active_shield_id) and commands/wear.py/commands/use.py setting both ids
on equip -- STAT now looks the ids up against ctx.server.items and appends
"(<name>)" when a ctx is available to resolve them against.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from base_classes import Guild, PlayerStat
from commands.stats import _build_stats_lines
from party import Party


def _make_player():
    player = MagicMock()
    player.name = 'Rulan'
    player.stats = {s: 10 for s in PlayerStat}
    player.shield = 40
    player.armor = 30
    player.get_silver = lambda k: 100
    player.experience = 0
    player.dead_monsters = []
    player.honor = 1000
    player.xp_level = 1
    player.hit_points = 20
    player.guild = Guild.CIVILIAN
    player.char_class = None
    player.char_race = None
    player.active_shield_id = 4
    player.active_armor_id  = 24
    player.shield_proficiency = {}
    player.query_flag = lambda f: False
    player.wizard_glow = False
    player.tuts_treasure = None
    player.time_remaining_minutes = None
    player.party = Party()
    return player


def _make_ctx():
    ctx = MagicMock()
    ctx.server.items = [
        {'number': 4,  'name': 'small shield'},
        {'number': 24, 'name': 'leather armor'},
    ]
    return ctx


class TestStatsEquippedNames(unittest.TestCase):

    def test_shield_and_armor_line_names_the_equipped_items(self):
        lines = _build_stats_lines(_make_player(), _make_ctx())
        row = next(l for l in lines if l.strip().startswith('Shield'))
        self.assertIn('(small shield)', row)
        self.assertIn('(leather armor)', row)

    def test_no_ctx_omits_names_without_erroring(self):
        lines = _build_stats_lines(_make_player())
        row = next(l for l in lines if l.strip().startswith('Shield'))
        self.assertNotIn('(', row)

    def test_no_active_id_omits_that_side_only(self):
        player = _make_player()
        player.active_armor_id = None
        lines = _build_stats_lines(player, _make_ctx())
        row = next(l for l in lines if l.strip().startswith('Shield'))
        self.assertIn('(small shield)', row)
        self.assertNotIn('(leather armor)', row)


if __name__ == '__main__':
    unittest.main(verbosity=2)
